import json
from dataclasses import dataclass
from pathlib import Path

from afk_looper.proc import run


# In order of preference: a merge commit keeps the agent's commits as it made them.
MERGE_FLAGS = (
    ("mergeCommitAllowed", "--merge"), ("squashMergeAllowed", "--squash"), ("rebaseMergeAllowed", "--rebase"),
)


@dataclass(frozen=True)
class Repo:
    root: Path
    worktree: Path
    logs: Path
    name: str
    base: str
    merge_flag: str


def find_repo(cwd: Path) -> Repo:
    # The common dir, so running from inside the afk worktree finds the same checkout.
    common = run("git", "rev-parse", "--path-format=absolute", "--git-common-dir", cwd=cwd)
    root = Path(common).parent
    fields = "nameWithOwner,defaultBranchRef,mergeCommitAllowed,squashMergeAllowed,rebaseMergeAllowed"
    view = json.loads(run("gh", "repo", "view", "--json", fields, cwd=root))
    allowed = [flag for key, flag in MERGE_FLAGS if view.get(key)]
    return Repo(
        root=root,
        worktree=root.parent / f"{root.name}-afk",
        logs=root / ".afk-logs",
        name=view["nameWithOwner"],
        base=view["defaultBranchRef"]["name"],
        merge_flag=(allowed or ["--merge"])[0],
    )
