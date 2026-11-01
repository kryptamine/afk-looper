import os
import shutil
import subprocess


def notify(title: str, message: str) -> None:
    if not shutil.which("osascript"):
        return
    script = ["on run argv", "display notification (item 1 of argv) with title (item 2 of argv)", "end run"]
    args = [part for line in script for part in ("-e", line)]
    subprocess.run(["osascript", *args, message, title], capture_output=True)


def keep_awake() -> None:
    """A sleeping Mac would stall the run; caffeinate exits along with this process."""
    if shutil.which("caffeinate"):
        subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
