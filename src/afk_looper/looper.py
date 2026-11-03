import subprocess

from afk_looper.agent import run_agent
from afk_looper.config import Config
from afk_looper.gate import refusal
from afk_looper.issues import Issue, list_issues, open_blockers
from afk_looper.notify import keep_awake, notify
from afk_looper.proc import describe, run
from afk_looper.prompts import implement_prompt, review_prompt
from afk_looper.publish import publish
from afk_looper.repo import Repo

MAX_GATE_RETRIES = 2


class Skip(Exception):
    """The human skipped the issue."""


class Stop(Exception):
    """The human ended the run."""


class Looper:
    def __init__(self, repo: Repo, config: Config, danger: bool = False) -> None:
        self.repo = repo
        self.config = config
        self.danger = danger
        self.merged: list[int] = []
        self.skipped: list[int] = []
        self.runs = 0

    def run(self) -> None:
        self.repo.logs.mkdir(exist_ok=True)
        # Ignores itself, so a target repository needs no .gitignore entry.
        (self.repo.logs / ".gitignore").write_text("*\n")
        keep_awake()
        try:
            while (issue := self._next_issue()) is not None:
                print(f"=== Issue #{issue.number}: {issue.title} ===")
                try:
                    self._work_on(issue.number)
                    self.merged.append(issue.number)
                except Skip:
                    self.skipped.append(issue.number)
        except Stop:
            pass
        finally:
            self._summary()

    def _next_issue(self) -> Issue | None:
        done = self.merged + self.skipped
        # GitHub lists a just-closed issue as open for a while after the merge.
        for issue in list_issues(self.repo, self.config.label):
            if issue.number not in done and self._unblocked(issue):
                return issue
        return None

    def _unblocked(self, issue: Issue) -> bool:
        if issue.open_blockers == 0:
            return True
        # The summary lags behind a merge too; the blocker list is fresh enough.
        return bool(self.merged) and open_blockers(self.repo, issue.number) <= set(self.merged)

    def _work_on(self, issue: int) -> None:
        base, check = self.repo.base, self.config.check
        print("--- Preparing the worktree")
        self._retrying(issue, "Preparing the worktree", lambda: self._prepare_worktree(issue))
        prompt = implement_prompt(issue, base, check)
        session = None
        title = body = ""
        reviewed = False
        retries = 0
        while True:
            log = self.repo.logs / f"issue-{issue}-run-{self._next_run()}.jsonl"
            print(f"--- {'Reviewing' if reviewed else 'Implementing'} (log: {log.name})")
            result = run_agent(prompt, session, self.repo.worktree, log, self.config, self.danger)
            session = result.session_id or session
            if result.status == "needs_human":
                prompt = f"The human answered: {self._ask(issue, result.question)}"
                continue
            if result.status != "done":
                question = (
                    f"The agent stopped with no result ({result.subtype}). "
                    f"See {log}. Instructions to resume with?"
                )
                prompt = f"Carry on. The human says: {self._ask(issue, question)}"
                continue

            if not reviewed:
                title, body = result.pr_title, result.pr_body
            failure = self._gate() if title else "Report pr_title and pr_body with status done."
            if failure is None:
                if reviewed:
                    break
                reviewed = True
                retries = 0
                session = None  # The reviewer must not inherit the author's reasoning.
                prompt = review_prompt(issue, base, check)
                continue

            retries += 1
            if retries > MAX_GATE_RETRIES:
                answer = self._ask(issue, f"The gate still fails after {MAX_GATE_RETRIES} retries:\n{failure}")
                retries = 0
                prompt = f"The gate failed:\n{failure}\nThe human says: {answer}"
            else:
                print(f"Gate refused (retry {retries}/{MAX_GATE_RETRIES}):\n{failure}")
                prompt = f"The gate refused the branch. Fix it, commit, and report again.\n{failure}"

        branch = run("git", "branch", "--show-current", cwd=self.repo.worktree)
        print(f"--- Publishing {branch}")
        self._retrying(issue, f"Publishing {branch}", lambda: publish(self.repo, issue, branch, title, body))

    def _gate(self) -> str | None:
        print(f"--- Gate: {self.config.check}")
        failure = refusal(self.repo.worktree, self.repo.base, self.config.check)
        if failure is None:
            print("Gate passed")
        return failure

    def _next_run(self) -> int:
        self.runs += 1
        return self.runs

    def _prepare_worktree(self, issue: int) -> None:
        repo = self.repo
        upstream = f"origin/{repo.base}"
        run("git", "fetch", "-q", "origin", repo.base, cwd=repo.root)
        if not repo.worktree.is_dir():
            run("git", "worktree", "add", "-q", "--detach", str(repo.worktree), upstream, cwd=repo.root)
        # A stash, because an interrupted run may have left work worth keeping.
        if run("git", "status", "--porcelain", cwd=repo.worktree):
            run("git", "stash", "push", "-q", "-u", "-m", f"afk leftovers before #{issue}", cwd=repo.worktree)
            print(f"Stashed leftovers in {repo.worktree}")
        run("git", "switch", "-q", "--detach", upstream, cwd=repo.worktree)
        subprocess.run(self.config.install, shell=True, cwd=repo.worktree, check=True)

    def _retrying(self, issue: int, what: str, step) -> None:
        while True:
            try:
                return step()
            except subprocess.CalledProcessError as error:
                self._ask(issue, f"{what} failed: {describe(error)}\nFix it, then reply anything to retry.")

    def _ask(self, issue: int, question: str) -> str:
        notify(self._title(), f"Issue #{issue} needs you")
        print(f"\a\n=== Issue #{issue} needs you ===\n{question}\n")
        answer = ""
        while not answer:
            try:
                answer = input("Reply (skip = next issue, stop = quit): ").strip()
            except EOFError:
                raise Stop from None
        if answer == "stop":
            raise Stop
        if answer == "skip":
            raise Skip
        return answer

    def _summary(self) -> None:
        merged = _numbers(self.merged)
        print(f"\nMerged: {merged}\nSkipped: {_numbers(self.skipped)}\nLogs: {self.repo.logs}")
        notify(self._title(), f"Run finished. Merged: {merged}")

    def _title(self) -> str:
        return f"AFK {self.repo.name}"


def _numbers(issues: list[int]) -> str:
    return " ".join(f"#{n}" for n in issues) or "none"
