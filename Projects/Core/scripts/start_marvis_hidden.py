"""Run MARVIS without a console, with bounded binary output logs."""
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime
import traceback
import ctypes
import threading


_lifetime_handles = []


def wrapper_chain(parent_pid, entries):
    """Return consecutive Python ancestors, or the direct non-Python parent."""
    result = []
    seen = set()
    while parent_pid:
        if parent_pid in seen or len(result) >= 64:
            raise RuntimeError("Invalid or excessively deep launcher ancestry")
        seen.add(parent_pid)
        if parent_pid not in entries:
            raise RuntimeError("Launcher ancestor exited during startup")
        ancestor, name = entries[parent_pid]
        if name.casefold() not in {"python.exe", "pythonw.exe"}:
            if not result:
                result.append(parent_pid)
            break
        result.append(parent_pid)
        parent_pid = ancestor
    if not result:
        raise RuntimeError("No launcher parent found")
    return result


def protect_process_tree():
    """Windows 8+: bind descendants to this launcher and watch its wrappers.

    Keep the non-inheritable job handle until process exit. Closing it early
    would terminate this process too. The parent watch also covers Windows
    virtual-environment launchers, where Scheduler may stop the outer wrapper.
    Call only in the dedicated launcher process, before starting any children.
    """
    from ctypes import wintypes as w

    class BasicLimits(ctypes.Structure):
        _fields_ = [("ProcessTime", ctypes.c_int64), ("JobTime", ctypes.c_int64),
                    ("Flags", w.DWORD), ("MinWorkingSet", ctypes.c_size_t),
                    ("MaxWorkingSet", ctypes.c_size_t), ("ActiveProcesses", w.DWORD),
                    ("Affinity", ctypes.c_size_t), ("Priority", w.DWORD),
                    ("Scheduling", w.DWORD)]

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in
                    ("ReadOps", "WriteOps", "OtherOps", "ReadBytes", "WriteBytes", "OtherBytes")]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [("Basic", BasicLimits), ("IO", IoCounters),
                    ("ProcessMemory", ctypes.c_size_t), ("JobMemory", ctypes.c_size_t),
                    ("PeakProcessMemory", ctypes.c_size_t), ("PeakJobMemory", ctypes.c_size_t)]

    class ProcessEntry(ctypes.Structure):
        _fields_ = [("Size", w.DWORD), ("Usage", w.DWORD), ("PID", w.DWORD),
                    ("Heap", ctypes.c_size_t), ("Module", w.DWORD),
                    ("Threads", w.DWORD), ("Parent", w.DWORD),
                    ("Priority", w.LONG), ("Flags", w.DWORD),
                    ("Name", w.WCHAR * 260)]

    api = ctypes.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreateJobObjectW": ([ctypes.c_void_p, w.LPCWSTR], w.HANDLE),
        "SetInformationJobObject": ([w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD], w.BOOL),
        "AssignProcessToJobObject": ([w.HANDLE, w.HANDLE], w.BOOL),
        "GetCurrentProcess": ([], w.HANDLE),
        "OpenProcess": ([w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
        "WaitForSingleObject": ([w.HANDLE, w.DWORD], w.DWORD),
        "CloseHandle": ([w.HANDLE], w.BOOL),
        "CreateToolhelp32Snapshot": ([w.DWORD, w.DWORD], w.HANDLE),
        "Process32FirstW": ([w.HANDLE, ctypes.POINTER(ProcessEntry)], w.BOOL),
        "Process32NextW": ([w.HANDLE, ctypes.POINTER(ProcessEntry)], w.BOOL),
    }
    for name, (args, result) in signatures.items():
        function = getattr(api, name)
        function.argtypes, function.restype = args, result

    snapshot = api.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry = ProcessEntry()
        entry.Size = ctypes.sizeof(entry)
        entries = {}
        if not api.Process32FirstW(snapshot, ctypes.byref(entry)):
            raise ctypes.WinError(ctypes.get_last_error())
        while True:
            entries[entry.PID] = (entry.Parent, entry.Name)
            if not api.Process32NextW(snapshot, ctypes.byref(entry)):
                if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
                    raise ctypes.WinError(ctypes.get_last_error())
                break
        parent_ids = wrapper_chain(os.getppid(), entries)
    finally:
        api.CloseHandle(snapshot)

    parents = []
    try:
        for parent_id in parent_ids:
            parent = api.OpenProcess(0x00100000, False, parent_id)  # SYNCHRONIZE
            if not parent:
                raise ctypes.WinError(ctypes.get_last_error())
            parents.append(parent)
    except BaseException:
        for parent in parents:
            api.CloseHandle(parent)
        raise
    job = api.CreateJobObjectW(None, None)
    if not job:
        error = ctypes.WinError(ctypes.get_last_error())
        for parent in parents:
            api.CloseHandle(parent)
        raise error
    try:
        limits = ExtendedLimits()
        limits.Basic.Flags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not api.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not api.AssignProcessToJobObject(job, api.GetCurrentProcess()):
            raise ctypes.WinError(ctypes.get_last_error())
    except BaseException:
        api.CloseHandle(job)
        for parent in parents:
            api.CloseHandle(parent)
        raise

    _lifetime_handles.extend([job, *parents])

    def watch_parent(parent):
        # Any unexpected wait failure also stops this launcher and its job.
        api.WaitForSingleObject(parent, 0xFFFFFFFF)
        os._exit(1)

    for parent in parents:
        threading.Thread(target=watch_parent, args=(parent,),
                         name="marvis-parent-watch", daemon=True).start()


class BoundedLog:
    """Single-writer log; preserves raw child output, even without newlines."""

    def __init__(self, path, max_bytes=5 * 1024 * 1024, backups=5):
        if max_bytes < 1 or backups < 1:
            raise ValueError("Log limits must be positive")
        self.path = Path(path)
        self.max_bytes = max_bytes
        self.backups = backups
        self.file = self.path.open("ab", buffering=0)

    def write(self, data):
        while data:
            available = self.max_bytes - self.file.tell()
            if available <= 0:
                self.file.close()
                for index in range(self.backups - 1, 0, -1):
                    source = self.path.with_name(f"{self.path.name}.{index}")
                    if source.exists():
                        source.replace(self.path.with_name(f"{self.path.name}.{index + 1}"))
                self.path.replace(self.path.with_name(f"{self.path.name}.1"))
                self.file = self.path.open("ab", buffering=0)
                available = self.max_bytes
            chunk, data = data[:available], data[available:]
            self.file.write(chunk)

    def close(self):
        self.file.close()


def run_logged(command, cwd, output, creationflags=0):
    """Drain combined output in bounded chunks and preserve the child status."""
    process = subprocess.Popen(
        command, cwd=cwd, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    try:
        while True:
            chunk = process.stdout.read1(65536)
            if not chunk:
                break
            output.write(chunk)
        return process.wait()
    except BaseException:
        process.kill()
        process.wait()
        raise
    finally:
        process.stdout.close()


def main():
    core = Path(__file__).resolve().parent.parent
    logs = Path(os.environ["LOCALAPPDATA"]) / "ConlonHub" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    output = BoundedLog(logs / "marvis-runtime.log")
    try:
        script = core / "scripts" / "start_marvis.ps1"
        if not script.is_file():
            raise FileNotFoundError(script)
        protect_process_tree()
        powershell = Path(os.environ["SystemRoot"]) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        output.write(f"\nMARVIS launch: {datetime.now().isoformat()}\nWorking directory: {core}\n".encode("utf-8"))
        result = run_logged(
            [str(powershell), "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-File", str(script)],
            core, output, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output.write(f"\nMARVIS exit code: {result}\n".encode("utf-8"))
        return result
    except Exception:
        output.write(traceback.format_exc().encode("utf-8"))
        return 1
    finally:
        output.close()


if __name__ == "__main__":
    sys.exit(main())
