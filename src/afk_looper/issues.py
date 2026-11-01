import json
from dataclasses import dataclass

from afk_looper.proc import run
from afk_looper.repo import Repo


@dataclass(frozen=True)
class Issue:
    number: int
    open_blockers: int
    title: str


def list_issues(repo: Repo, label: str) -> list[Issue]:
    listed = run(
        "gh", "issue", "list", "--label", label, "--state", "open",
        "--limit", "100", "--json", "number", cwd=repo.root,
    )
    return [_fetch(repo, number) for number in sorted(i["number"] for i in json.loads(listed))]


def _fetch(repo: Repo, number: int) -> Issue:
    # `gh issue view` lacks this summary, and GitHub counts only open blockers in it.
    issue = json.loads(run("gh", "api", f"repos/{repo.name}/issues/{number}", cwd=repo.root))
    summary = issue.get("issue_dependencies_summary") or {}
    return Issue(number, summary.get("blocked_by", 0), issue["title"])
