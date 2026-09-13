import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
import os
import subprocess
import time
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "hidden_launcher", Path(__file__).resolve().parents[1] / "scripts" / "start_marvis_hidden.py"
)
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


class HiddenLauncherTests(unittest.TestCase):
    def test_wrapper_chain_watches_all_python_layers_only(self):
        entries = {10: (20, "pythonw.exe"), 20: (30, "PYTHON.EXE"),
                   30: (40, "python.exe"), 40: (50, "powershell.exe")}
        self.assertEqual(launcher.wrapper_chain(10, entries), [10, 20, 30])

    def test_direct_non_python_parent_is_watched(self):
        self.assertEqual(launcher.wrapper_chain(40, {40: (50, "taskeng.exe")}), [40])

    def test_invalid_ancestry_fails_closed(self):
        for parent, entries in [(0, {}), (10, {}), (10, {10: (10, "python.exe")})]:
            with self.assertRaises(RuntimeError):
                launcher.wrapper_chain(parent, entries)

    def test_missing_start_script_is_logged_and_returns_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_file = str(Path(directory) / "core" / "scripts" / "start_marvis_hidden.py")
            with patch.object(launcher, "__file__", fake_file), patch.dict(
                launcher.os.environ, {"LOCALAPPDATA": directory}
            ):
                self.assertEqual(launcher.main(), 1)
            log = Path(directory) / "ConlonHub" / "logs" / "marvis-runtime.log"
            self.assertIn("FileNotFoundError", log.read_text())

    def test_main_uses_windowless_flag_and_preserves_failure_status(self):
        with tempfile.TemporaryDirectory() as directory:
            scripts = Path(directory) / "core" / "scripts"
            scripts.mkdir(parents=True)
            (scripts / "start_marvis.ps1").touch()
            with patch.object(launcher, "__file__", str(scripts / "start_marvis_hidden.py")), patch.dict(
                launcher.os.environ, {"LOCALAPPDATA": directory, "SystemRoot": directory}
            ), patch.object(launcher.subprocess, "CREATE_NO_WINDOW", 0x08000000, create=True), patch.object(
                launcher, "run_logged", return_value=9
            ) as run, patch.object(launcher, "protect_process_tree") as protect:
                self.assertEqual(launcher.main(), 9)
                protect.assert_called_once()
                self.assertEqual(run.call_args.kwargs["creationflags"], 0x08000000)
                self.assertEqual(run.call_args.args[1], scripts.parent)
            log = Path(directory) / "ConlonHub" / "logs" / "marvis-runtime.log"
            self.assertIn("MARVIS exit code: 9", log.read_text())

    def test_protection_failure_prevents_server_start_and_is_logged(self):
        with tempfile.TemporaryDirectory() as directory:
            scripts = Path(directory) / "core" / "scripts"
            scripts.mkdir(parents=True)
            (scripts / "start_marvis.ps1").touch()
            with patch.object(launcher, "__file__", str(scripts / "start_marvis_hidden.py")), patch.dict(
                launcher.os.environ, {"LOCALAPPDATA": directory}
            ), patch.object(launcher, "protect_process_tree", side_effect=OSError("job refused")), patch.object(
                launcher, "run_logged"
            ) as run:
                self.assertEqual(launcher.main(), 1)
                run.assert_not_called()
            log = Path(directory) / "ConlonHub" / "logs" / "marvis-runtime.log"
            self.assertIn("job refused", log.read_text())

    @unittest.skipUnless(os.name == "nt", "Requires real Windows Job Objects")
    def test_stopping_outer_wrapper_kills_descendant_server(self):
        # No MARVIS, network ports, or scheduled tasks: only disposable helpers.
        import ctypes
        from ctypes import wintypes as w
        with tempfile.TemporaryDirectory() as directory:
            ready = Path(directory) / "ready"
            descendant = "import time; time.sleep(120)"
            protected = (
                "import sys,subprocess,time; from pathlib import Path; "
                f"sys.path.insert(0,{str(Path(launcher.__file__).parent)!r}); "
                "from start_marvis_hidden import protect_process_tree; protect_process_tree(); "
                f"p=subprocess.Popen([sys.executable,'-c',{descendant!r}]); "
                f"Path({str(ready)!r}).write_text(str(p.pid)); time.sleep(120)"
            )
            wrapper = "import subprocess,sys; p=subprocess.Popen([sys.executable,'-c'," + repr(protected) + "]); p.wait()"
            process = subprocess.Popen([sys.executable, "-c", wrapper])
            api = ctypes.WinDLL("kernel32", use_last_error=True)
            api.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
            api.OpenProcess.restype = w.HANDLE
            api.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
            api.WaitForSingleObject.restype = w.DWORD
            api.CloseHandle.argtypes = [w.HANDLE]
            handle = None
            try:
                deadline = time.monotonic() + 15
                while not ready.exists() and time.monotonic() < deadline:
                    if process.poll() is not None:
                        self.fail("Protected helper exited before readiness")
                    time.sleep(0.05)
                self.assertTrue(ready.exists(), "Helper did not start")
                # File creation precedes its write; retry until the PID is present.
                pid_text = ready.read_text()
                while not pid_text and time.monotonic() < deadline:
                    time.sleep(0.05)
                    pid_text = ready.read_text()
                handle = api.OpenProcess(0x00100000, False, int(pid_text))
                self.assertTrue(handle, "Could not observe descendant")
                process.kill()
                process.wait(timeout=10)
                self.assertEqual(api.WaitForSingleObject(handle, 10000), 0,
                                 "Descendant survived outer-wrapper termination")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)
                if handle:
                    api.CloseHandle(handle)

    def test_rotation_retains_exact_newest_bytes_with_bounded_disk_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "marvis-runtime.log"
            old = Path(directory) / "marvis-old.log"
            old.write_bytes(b"old log")
            output = launcher.BoundedLog(path, max_bytes=8, backups=2)
            data = bytes(range(80))
            try:
                output.write(data)
            finally:
                output.close()
            files = [path.with_name(path.name + ".2"), path.with_name(path.name + ".1"), path]
            self.assertEqual(b"".join(p.read_bytes() for p in files), data[-24:])
            self.assertTrue(all(p.stat().st_size <= 8 for p in files))
            self.assertEqual(old.read_bytes(), b"old log")
            self.assertEqual(len(list(Path(directory).iterdir())), 4)

    def test_restart_appends_and_rotates_existing_log(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.log"
            for data in [b"abcdef", b"ghijk"]:
                output = launcher.BoundedLog(path, max_bytes=8, backups=2)
                try:
                    output.write(data)
                finally:
                    output.close()
            self.assertEqual(path.with_name("runtime.log.1").read_bytes(), b"abcdefgh")
            self.assertEqual(path.read_bytes(), b"ijk")

    def test_child_stdout_stderr_and_nonzero_status_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.log"
            output = launcher.BoundedLog(path)
            try:
                status = launcher.run_logged(
                    [sys.executable, "-c", "import os; os.write(1,b'hello'); os.write(2,b'error'); raise SystemExit(7)"],
                    directory, output,
                )
            finally:
                output.close()
            self.assertEqual(status, 7)
            self.assertEqual(path.read_bytes(), b"helloerror")

    def test_long_output_without_newlines_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.log"
            output = launcher.BoundedLog(path, max_bytes=1024, backups=2)
            try:
                status = launcher.run_logged(
                    [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'x'*200000)"],
                    directory, output,
                )
            finally:
                output.close()
            self.assertEqual(status, 0)
            files = list(Path(directory).iterdir())
            self.assertEqual(len(files), 3)
            self.assertLessEqual(sum(p.stat().st_size for p in files), 3072)

    def test_invalid_limits_rejected(self):
        for size, count in [(0, 2), (8, 0), (-1, 2)]:
            with self.assertRaises(ValueError):
                launcher.BoundedLog("unused.log", size, count)


if __name__ == "__main__":
    unittest.main()
