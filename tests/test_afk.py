import pytest
from conftest import World, git

DONE = {"status": "done", "pr_title": "feat: add thing", "pr_body": "Because."}
REVIEWED = {"status": "done"}
COMMIT = "git switch -q -c feat/thing && touch thing && git add . && git commit -qm 'feat: add thing'"


def prompt_of(run: list[str]) -> str:
    return run[run.index("-p") + 1]


def test_list_marks_blocked_issues(world: World):
    world.issues(i1={"title": "Free"}, i2={"title": "Waiting", "blocked": 1})
    out = world.afk("list").stdout
    assert "#1 ready    Free" in out
    assert "#2 blocked  Waiting" in out


def test_a_clean_issue_is_reviewed_by_a_fresh_agent_then_merged(world: World):
    world.issues(i1={"title": "Thing"})
    world.scenario({"sh": COMMIT, "report": DONE}, {"report": REVIEWED})
    done = world.afk("run")
    assert done.returncode == 0, done.stderr
    assert "Merged: #1" in done.stdout
    assert world.origin_log()[0] == "feat: add thing"
    assert world.origin_branches() == ["main"]
    pr = world.github()["prs"]["https://fake/pr/1"]
    assert pr["title"] == "feat: add thing"
    assert pr["body"] == "Because.\n\nCloses #1"
    implement, review = world.agent_runs()
    assert "--resume" not in review
    assert "You review the branch" in prompt_of(review)
    assert "issue #1" in prompt_of(implement)


def test_blocked_issue_waits(world: World):
    world.issues(i1={"title": "Waiting", "blocked": 1})
    done = world.afk("run")
    assert "Merged: none" in done.stdout
    assert world.agent_runs() == []


def test_the_terminal_shows_what_the_agent_does(world: World):
    worktree = world.checkout.parent / "widget-afk"
    calls = [
        {"type": "tool_use", "name": "Bash", "input": {"command": "uv run\n  pytest"}},
        {"type": "tool_use", "name": "Bash", "input": {"command": "x" * 200}},
        {"type": "tool_use", "name": "Read", "input": {"file_path": f"{worktree}/src/a.py"}},
        {"type": "tool_use", "name": "TodoWrite", "input": {"todos": []}},
    ]
    results = [
        {"type": "tool_result", "is_error": True, "content": "Exit code 1\nboom"},
        {"type": "tool_result", "is_error": True, "content": [{"type": "text", "text": "denied"}]},
        {"type": "tool_result", "content": "quiet success"},
    ]
    events = [
        {"type": "system", "subtype": "permission_denied", "message": "a plain string"},
        {"type": "assistant", "message": {"content": calls}},
        {"type": "user", "message": {"content": results}},
        {"type": "user", "message": {"content": "a plain string"}},
    ]
    world.issues(i1={"title": "Thing"})
    world.scenario({"sh": COMMIT, "report": DONE, "events": events}, {"report": REVIEWED})
    done = world.afk("run")
    assert done.returncode == 0, done.stderr
    lines = done.stdout.splitlines()
    assert "  -> Bash: uv run pytest" in lines
    assert f"  -> Bash: {'x' * 117}..." in lines
    assert "  -> Read: src/a.py" in lines
    assert "  -> TodoWrite" in lines
    assert "  !! Exit code 1 boom" in lines
    assert "  !! denied" in lines
    assert "quiet success" not in done.stdout
    assert "  Agent stopped: success, 1m01s, $0.50" in lines


def test_the_terminal_shows_each_phase_in_order(world: World):
    world.issues(i1={"title": "Thing"})
    world.scenario({"sh": COMMIT, "report": DONE}, {"report": REVIEWED})
    out = world.afk("run").stdout
    phases = [
        "=== Issue #1: Thing ===",
        "--- Preparing the worktree",
        "--- Implementing (log: issue-1-run-1.jsonl)",
        "--- Gate: test ! -e broken",
        "Gate passed",
        "--- Reviewing (log: issue-1-run-2.jsonl)",
        "--- Gate: test ! -e broken",
        "Gate passed",
        "--- Publishing feat/thing",
        "Merged https://fake/pr/1",
    ]
    position = 0
    for phase in phases:
        position = out.index(phase, position) + len(phase)


def test_a_question_goes_to_the_human_and_the_answer_resumes_the_session(world: World):
    world.issues(i1={"title": "Thing"})
    world.scenario(
        {"report": {"status": "needs_human", "question": "Red or blue?"}},
        {"sh": COMMIT, "report": DONE},
        {"report": REVIEWED},
    )
    done = world.afk("run", stdin="blue\n")
    assert "Red or blue?" in done.stdout
    assert "Merged: #1" in done.stdout
    resumed = world.agent_runs()[1]
    assert prompt_of(resumed) == "The human answered: blue"
    assert resumed[resumed.index("--resume") + 1] == "session-0"


def test_skip_moves_on_without_merging(world: World):
    world.issues(i1={"title": "Hard"}, i2={"title": "Easy"})
    world.scenario(
        {"report": {"status": "needs_human", "question": "Which?"}},
        {"sh": COMMIT, "report": DONE},
        {"report": REVIEWED},
    )
    done = world.afk("run", stdin="skip\n")
    assert "Merged: #2" in done.stdout
    assert "Skipped: #1" in done.stdout
    assert world.github()["issues"]["1"]["state"] == "OPEN"


def test_a_merged_issue_github_still_lists_is_not_picked_again(world: World):
    world.issues(i1={"title": "Thing", "stale": True})
    world.scenario({"sh": COMMIT, "report": DONE}, {"report": REVIEWED})
    done = world.afk("run")
    assert done.returncode == 0, done.stderr
    assert done.stdout.count("=== Issue #1") == 1
    assert len(world.agent_runs()) == 2


def test_an_issue_blocked_only_by_a_merged_one_goes_next(world: World):
    # The fake never lowers "blocked", like GitHub's summary right after a merge.
    world.issues(i1={"title": "First"}, i2={"title": "Second", "blocked": 1, "blocked_by": [1]})
    second = "git switch -q -c feat/second && touch second && git add . && git commit -qm 'feat: second'"
    world.scenario(
        {"sh": COMMIT, "report": DONE}, {"report": REVIEWED},
        {"sh": second, "report": DONE}, {"report": REVIEWED},
    )
    done = world.afk("run")
    assert done.returncode == 0, done.stderr
    assert "Merged: #1 #2" in done.stdout


def test_an_issue_with_another_open_blocker_still_waits(world: World):
    world.issues(
        i1={"title": "First"},
        i2={"title": "Second", "blocked": 2, "blocked_by": [1, 3]},
        i3={"title": "Third", "blocked": 1, "blocked_by": [2]},
    )
    world.scenario({"sh": COMMIT, "report": DONE}, {"report": REVIEWED})
    done = world.afk("run")
    assert done.returncode == 0, done.stderr
    assert "Merged: #1\n" in done.stdout


def test_stop_ends_the_run_with_a_summary(world: World):
    world.issues(i1={"title": "Hard"})
    world.scenario({"report": {"status": "needs_human", "question": "Which?"}})
    done = world.afk("run", stdin="stop\n")
    assert done.returncode == 0
    assert "Merged: none" in done.stdout
    assert world.github()["prs"] == {}


def test_a_dead_review_does_not_fall_back_to_the_author_session(world: World):
    # The reviewer stays independent even when its first run leaves no session to resume.
    world.issues(i1={"title": "Thing"})
    world.scenario({"sh": COMMIT, "report": DONE})
    done = world.afk("run", stdin="go on\n")
    assert "The agent stopped with no result (process died)" in done.stdout
    assert world.github()["prs"] == {}
    _, review, retry = world.agent_runs()
    assert "--resume" not in review
    assert "--resume" not in retry
    assert prompt_of(retry) == "Carry on. The human says: go on"


def test_a_failing_check_returns_to_the_agent_and_blocks_the_merge(world: World):
    world.issues(i1={"title": "Thing"})
    world.scenario(
        {"sh": COMMIT + " && touch broken && git add . && git commit -qm 'feat: break'", "report": DONE},
        {"sh": "git rm -q broken && git commit -qm 'fix: repair'", "report": DONE},
        {"report": REVIEWED},
    )
    done = world.afk("run")
    assert "Merged: #1" in done.stdout
    assert "Gate refused (retry 1/2):\n`test ! -e broken` failed" in done.stdout
    retry = prompt_of(world.agent_runs()[1])
    assert "The gate refused the branch" in retry
    assert "`test ! -e broken` failed" in retry


@pytest.mark.parametrize(
    ("reason", "bad", "fix"),
    [
        ("not a branch named", "git switch -q -c Bad_Name && touch a && git add . && git commit -qm x", "git branch -m feat/fixed"),
        ("uncommitted changes", "git switch -q -c feat/a && touch a && git add . && git commit -qm x && touch b", "git add . && git commit -qm y"),
        ("no commits on top", "git switch -q -c feat/a", "touch a && git add . && git commit -qm x"),
        ("co-author trailer", "git switch -q -c feat/a && touch a && git add . && git commit -qm 'x\n\nCo-Authored-By: Bot <b@b>'", "git commit -q --amend -m x"),
    ],
)
def test_the_gate_refuses_what_would_break_the_merge(world: World, reason: str, bad: str, fix: str):
    world.issues(i1={"title": "Thing"})
    world.scenario({"sh": bad, "report": DONE}, {"sh": fix, "report": DONE}, {"report": REVIEWED})
    done = world.afk("run")
    assert "Merged: #1" in done.stdout
    assert reason in prompt_of(world.agent_runs()[1])


def test_a_gate_that_keeps_failing_asks_the_human(world: World):
    world.issues(i1={"title": "Thing"})
    world.scenario(*[{"sh": "git switch -q -c feat/a || true", "report": DONE}] * 3)
    done = world.afk("run", stdin="stop\n")
    assert "The gate still fails after 2 retries" in done.stdout
    assert world.github()["prs"] == {}


def test_a_behind_branch_is_refused(world: World):
    world.issues(i1={"title": "Thing"})
    advance = (
        f"git clone -q {world.origin} {world.tmp}/other && cd {world.tmp}/other && touch z && "
        "git add . && git commit -qm 'chore: advance' && git push -q origin main"
    )
    world.scenario(
        {"sh": f"{COMMIT} && ({advance})", "report": DONE},
        {"sh": "git fetch -q origin main && git rebase -q origin/main", "report": DONE},
        {"report": REVIEWED},
    )
    done = world.afk("run")
    assert "Merged: #1" in done.stdout
    assert "behind origin/main" in prompt_of(world.agent_runs()[1])
    assert "chore: advance" in git("log", "--format=%s", "main", cwd=world.origin)


def test_config_reaches_the_agent_and_the_issue_query(world: World):
    (world.checkout / ".afk.toml").write_text(
        'label = "go"\ninstall = "true"\ncheck = "true"\nbudget_usd = 5\nallow = ["Bash(cargo *)"]\n'
    )
    world.issues(i1={"title": "Thing"})
    world.scenario({"sh": COMMIT, "report": DONE}, {"report": REVIEWED})
    world.afk("run")
    assert "go" in world.github()["labels"]
    implement = world.agent_runs()[0]
    assert "Bash(cargo *)" in implement
    assert implement[implement.index("--max-budget-usd") + 1] == "5"
    assert "Bash(git push *)" in implement[implement.index("--disallowedTools"):]


def test_the_agent_reads_pull_requests_but_cannot_change_them(world: World):
    world.issues(i1={"title": "Thing"})
    world.scenario({"sh": COMMIT, "report": DONE}, {"report": REVIEWED})
    world.afk("run")
    implement = world.agent_runs()[0]
    denied = implement.index("--disallowedTools")
    assert "Bash(gh pr view *)" in implement[:denied]
    assert "Bash(gh pr view *)" not in implement[denied:]
    assert "Bash(gh pr merge *)" in implement[denied:]
    assert "Bash(gh pr -*)" in implement[denied:]


def test_a_normal_run_keeps_the_permission_checks(world: World):
    world.issues(i1={"title": "Thing"})
    world.scenario({"sh": COMMIT, "report": DONE}, {"report": REVIEWED})
    done = world.afk("run")
    assert "DANGER" not in done.stdout
    for run in world.agent_runs():
        assert "--dangerously-skip-permissions" not in run
        assert run[run.index("--permission-mode") + 1] == "acceptEdits"


def test_danger_skips_permissions_on_every_agent_but_keeps_the_gate_commands_denied(world: World):
    world.issues(i1={"title": "Thing"})
    world.scenario({"sh": COMMIT, "report": DONE}, {"report": REVIEWED})
    done = world.afk("run", "--danger")
    assert done.returncode == 0, done.stderr
    assert "DANGER" in done.stdout
    assert "Merged: #1" in done.stdout
    runs = world.agent_runs()
    assert len(runs) == 2
    for run in runs:
        assert "--dangerously-skip-permissions" in run
        assert "--permission-mode" not in run
        assert "--allowedTools" not in run
        assert "Bash(git push *)" in run[run.index("--disallowedTools"):]


def test_danger_cannot_be_turned_on_from_the_repository_config(world: World):
    (world.checkout / ".afk.toml").write_text("danger = true\n")
    world.issues(i1={"title": "Thing"})
    done = world.afk("run")
    assert done.returncode != 0
    assert "unknown keys: danger" in done.stderr
    assert world.agent_runs() == []


def test_budget_env_overrides_the_config(world: World):
    world.issues(i1={"title": "Thing"})
    world.scenario({"sh": COMMIT, "report": DONE}, {"report": REVIEWED})
    world.env["AFK_BUDGET_USD"] = "7"
    world.afk("run")
    implement = world.agent_runs()[0]
    assert implement[implement.index("--max-budget-usd") + 1] == "7.0"


def test_an_unknown_config_key_is_refused_before_any_work(world: World):
    (world.checkout / ".afk.toml").write_text('chek = "typo"\n')
    world.issues(i1={"title": "Thing"})
    done = world.afk("run")
    assert done.returncode != 0
    assert "unknown keys: chek" in done.stderr
    assert world.agent_runs() == []


def test_logs_ignore_themselves_in_the_target_repository(world: World):
    world.afk("run")
    assert git("status", "--short", cwd=world.checkout) == ""


def test_update_upgrades_the_uv_tool(world: World):
    done = world.afk("update")
    assert done.returncode == 0
    assert (world.tmp / "uv-calls").read_text().strip() == "tool upgrade afk-looper"
