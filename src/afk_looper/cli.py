import argparse
import shutil
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

from afk_looper.config import load_config
from afk_looper.issues import list_issues
from afk_looper.looper import Looper
from afk_looper.proc import describe
from afk_looper.repo import find_repo

PACKAGE = "afk-looper"


def main() -> int:
    sys.stdout.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser(prog="afk", description="Work through ready-for-agent issues, merging each.")
    parser.add_argument("--version", action="version", version=f"afk {version(PACKAGE)}")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("run", help="work through the issues and merge them")
    commands.add_parser("list", help="show the labelled issues and which are blocked")
    commands.add_parser("update", help="upgrade afk to the latest commit on main")
    command = parser.parse_args().command
    try:
        return {"run": _run, "list": _list, "update": _update}[command]()
    except subprocess.CalledProcessError as error:
        print(f"afk: {describe(error)}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


def _run() -> int:
    repo = find_repo(Path.cwd())
    Looper(repo, load_config(repo.root)).run()
    return 0


def _list() -> int:
    repo = find_repo(Path.cwd())
    for issue in list_issues(repo, load_config(repo.root).label):
        state = "blocked" if issue.open_blockers else "ready  "
        print(f"#{issue.number} {state}  {issue.title}")
    return 0


def _update() -> int:
    if not shutil.which("uv"):
        print("afk: uv not found; afk is installed and upgraded with uv", file=sys.stderr)
        return 1
    return subprocess.run(["uv", "tool", "upgrade", PACKAGE]).returncode
