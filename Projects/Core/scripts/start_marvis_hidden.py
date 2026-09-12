"""Windowless Windows launcher for the existing MARVIS PowerShell script."""
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime
import traceback


def main():
    core = Path(__file__).resolve().parent.parent
    logs = Path(os.environ["LOCALAPPDATA"]) / "ConlonHub" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    log_path = logs / f"marvis-{stamp}.log"
    with log_path.open("a", encoding="utf-8", buffering=1) as output:
        try:
            script = core / "scripts" / "start_marvis.ps1"
            if not script.is_file():
                raise FileNotFoundError(script)
            powershell = Path(os.environ["SystemRoot"]) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
            output.write(f"MARVIS launch: {datetime.now().isoformat()}\nWorking directory: {core}\n")
            output.flush()
            result = subprocess.run(
                [str(powershell), "-NoProfile", "-NonInteractive",
                 "-ExecutionPolicy", "Bypass", "-File", str(script)],
                cwd=core, stdin=subprocess.DEVNULL, stdout=output,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            output.write(f"MARVIS exit code: {result.returncode}\n")
            return result.returncode
        except Exception:
            traceback.print_exc(file=output)
            return 1


if __name__ == "__main__":
    sys.exit(main())
