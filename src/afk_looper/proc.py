import subprocess
from pathlib import Path


def run(*args: str, cwd: Path) -> str:
    done = subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)
    return done.stdout.strip()


def describe(error: subprocess.CalledProcessError) -> str:
    command = error.cmd if isinstance(error.cmd, str) else " ".join(error.cmd)
    return f"`{command}` exited {error.returncode}:\n{(error.stderr or '').strip()}"
