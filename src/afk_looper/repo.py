import json
from dataclasses import dataclass
from pathlib import Path

from afk_looper.proc import run


@dataclass(frozen=True)
class Repo:
    root: Path
    worktree: Path
    logs: Path
    name: str
    base: str


def find_repo(cwd: Path) -> Repo:
    # The common dir, so running from inside the afk worktree finds the same checkout.
    common = run("git", "rev-parse", "--path-format=absolute", "--git-common-dir", cwd=cwd)
    root = Path(common).parent
    view = json.loads(run("gh", "repo", "view", "--json", "nameWithOwner,defaultBranchRef", cwd=root))
    return Repo(
        root=root,
        worktree=root.parent / f"{root.name}-afk",
        logs=root / ".afk-logs",
        name=view["nameWithOwner"],
        base=view["defaultBranchRef"]["name"],
    )
