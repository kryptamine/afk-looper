import json
import subprocess

from afk_looper.proc import run
from afk_looper.repo import Repo


def publish(repo: Repo, issue: int, branch: str, title: str, body: str, direct: bool = False) -> None:
    if direct:
        return _push_to_base(repo, issue, branch)
    run("git", "push", "-u", "origin", branch, cwd=repo.worktree)
    url = _open_pull_request(repo, issue, branch, title, body)
    run("gh", "pr", "merge", url, repo.merge_flag, cwd=repo.root)
    print(f"Merged {url}")
    _clean_up(repo, branch)
    state = json.loads(run("gh", "issue", "view", str(issue), "--json", "state", cwd=repo.root))
    if state["state"] != "CLOSED":
        _best_effort(repo, "gh", "issue", "close", str(issue), "--comment", f"Merged in {url}")


def _push_to_base(repo: Repo, issue: int, branch: str) -> None:
    # The gate has just seen the branch on top of the base, so this is a fast-forward.
    run("git", "push", "origin", f"HEAD:refs/heads/{repo.base}", cwd=repo.worktree)
    sha = run("git", "rev-parse", "--short", "HEAD", cwd=repo.worktree)
    print(f"Pushed {sha} to {repo.base}")
    _best_effort(repo, "git", "switch", "-q", "--detach")
    _best_effort(repo, "git", "branch", "-qD", branch)
    _best_effort(repo, "gh", "issue", "close", str(issue), "--comment", f"Pushed to {repo.base} in {sha}")


def _open_pull_request(repo: Repo, issue: int, branch: str, title: str, body: str) -> str:
    try:
        view = run("gh", "pr", "view", branch, "--json", "url", cwd=repo.root)
        return json.loads(view)["url"]
    except subprocess.CalledProcessError:
        return run(
            "gh", "pr", "create", "--base", repo.base, "--head", branch, "--title", title,
            "--body", f"{body}\n\nCloses #{issue}", cwd=repo.root,
        )


def _clean_up(repo: Repo, branch: str) -> None:
    # Not gh's --delete-branch: it would switch to the base, which the main checkout holds.
    _best_effort(repo, "git", "switch", "-q", "--detach")
    _best_effort(repo, "git", "push", "-q", "origin", "--delete", branch)
    _best_effort(repo, "git", "branch", "-qD", branch)


def _best_effort(repo: Repo, *args: str) -> None:
    subprocess.run(args, cwd=repo.worktree, capture_output=True)
