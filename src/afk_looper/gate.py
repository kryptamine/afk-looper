import re
import subprocess
from pathlib import Path

from afk_looper.proc import describe, run

BRANCH = re.compile(r"(feat|fix|docs|test|refactor|perf|chore)/[a-z0-9-]+")
CO_AUTHOR = re.compile(r"^co-authored-by:", re.IGNORECASE | re.MULTILINE)


def refusal(worktree: Path, base: str, check: str) -> str | None:
    """Says why the branch may not merge, or None when it may."""
    try:
        return _refusal(worktree, base, check)
    except subprocess.CalledProcessError as error:
        return f"A gate command failed: {describe(error)}"


def _refusal(worktree: Path, base: str, check: str) -> str | None:
    def git(*args: str) -> str:
        return run("git", *args, cwd=worktree)

    upstream = f"origin/{base}"
    branch = git("branch", "--show-current")
    if not BRANCH.fullmatch(branch):
        return f"The worktree is on '{branch}', not a branch named <type>/<kebab-summary>."
    if status := git("status", "--short"):
        return f"The worktree has uncommitted changes:\n{status}"
    git("fetch", "-q", "origin", base)
    behind = subprocess.run(
        ["git", "merge-base", "--is-ancestor", upstream, "HEAD"], cwd=worktree
    )
    if behind.returncode != 0:
        return f"The branch is behind {upstream}. Rebase it onto {upstream}."
    if not git("rev-list", f"{upstream}..HEAD"):
        return f"The branch has no commits on top of {upstream}."
    if CO_AUTHOR.search(git("log", f"{upstream}..HEAD", "--format=%B")):
        return "A commit carries a co-author trailer, which afk refuses. Remove it."
    # Last, as it is the slow one.
    checked = subprocess.run(
        check, shell=True, cwd=worktree, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    if checked.returncode != 0:
        tail = "\n".join(checked.stdout.splitlines()[-80:])
        return f"`{check}` failed:\n{tail}"
    return None
