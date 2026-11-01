import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from afk_looper.config import Config

SCHEMA = json.dumps({
    "type": "object",
    "required": ["status"],
    "additionalProperties": False,
    "properties": {
        "status": {"enum": ["done", "needs_human"]},
        "question": {"type": "string"},
        "pr_title": {"type": "string"},
        "pr_body": {"type": "string"},
    },
})

# The commands afk runs itself stay denied, so the base branch only moves through the gate.
# Not a security boundary: make and friends can run anything on this machine.
ALLOWED = (
    "Read", "Edit", "Write", "Glob", "Grep", "WebFetch", "WebSearch", "TodoWrite",
    "Bash(git *)", "Bash(gh issue view *)", "Bash(gh issue list *)", "Bash(gh issue comment *)",
    "Bash(gh pr view *)", "Bash(gh pr list *)", "Bash(gh pr diff *)", "Bash(gh pr checks *)",
    "Bash(gh repo view *)", "Bash(gh auth status *)", "Bash(make *)",
    "Bash(ls *)", "Bash(cat *)", "Bash(head *)", "Bash(tail *)", "Bash(wc *)", "Bash(rg *)",
    "Bash(grep *)", "Bash(find *)", "Bash(sed *)", "Bash(awk *)", "Bash(perl *)", "Bash(jq *)",
    "Bash(mkdir *)", "Bash(mv *)", "Bash(cp *)", "Bash(rm *)", "Bash(chmod *)",
)
# A deny outranks an allow, so `gh pr` is denied by verb to leave the read-only ones open.
# `gh pr -*` covers a flag before the verb, as in `gh pr -R owner/repo merge`.
DENIED = (
    "Bash(git push *)", "Bash(gh pr -*)", "Bash(gh pr create *)", "Bash(gh pr merge *)",
    "Bash(gh pr close *)", "Bash(gh pr reopen *)", "Bash(gh pr edit *)", "Bash(gh pr ready *)",
    "Bash(gh pr review *)", "Bash(gh pr comment *)", "Bash(gh pr update-branch *)",
    "Bash(gh pr revert *)", "Bash(gh pr lock *)", "Bash(gh pr unlock *)",
)

# The input field that says what a tool call is doing.
TOOL_DETAIL = {
    "Bash": "command", "Read": "file_path", "Edit": "file_path", "Write": "file_path",
    "Glob": "pattern", "Grep": "pattern", "WebFetch": "url", "WebSearch": "query",
}
MAX_LINE = 120


@dataclass(frozen=True)
class AgentResult:
    session_id: str | None
    subtype: str
    status: str
    question: str
    pr_title: str
    pr_body: str


def run_agent(prompt: str, session: str | None, cwd: Path, log: Path, config: Config, danger: bool) -> AgentResult:
    permissions = (
        ["--dangerously-skip-permissions"] if danger
        else ["--permission-mode", "acceptEdits", "--allowedTools", *ALLOWED, *config.allow]
    )
    args = [
        "claude", "-p", prompt,
        "--output-format", "stream-json", "--verbose", "--json-schema", SCHEMA,
        "--max-budget-usd", str(config.budget_usd),
        *permissions,
        "--disallowedTools", *DENIED,
    ]
    if session:
        args += ["--resume", session]
    final: dict = {}
    with log.open("w") as out, subprocess.Popen(
        args, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True
    ) as agent:
        for line in agent.stdout:
            out.write(line)
            out.flush()
            event = _parse(line)
            _show(event, cwd)
            if event.get("type") == "result":
                final = event
    report = final.get("structured_output") or {}
    return AgentResult(
        session_id=final.get("session_id"),
        subtype=final.get("subtype", "process died"),
        status=report.get("status", ""),
        question=report.get("question", ""),
        pr_title=report.get("pr_title", ""),
        pr_body=report.get("pr_body", ""),
    )


def _parse(line: str) -> dict:
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return {}
    return event if isinstance(event, dict) else {}


def _show(event: dict, cwd: Path) -> None:
    kind = event.get("type")
    if kind == "result":
        seconds = event.get("duration_ms", 0) // 1000
        cost = event.get("total_cost_usd", 0)
        print(f"  Agent stopped: {event.get('subtype')}, {seconds // 60}m{seconds % 60:02d}s, ${cost:.2f}")
        return
    # Other events can carry a plain string as their message.
    if kind not in ("assistant", "user"):
        return
    content = event.get("message", {}).get("content")
    # A user event's content can be a plain string.
    for block in content if isinstance(content, list) else []:
        if kind == "assistant" and block.get("type") == "text":
            print(block["text"])
        elif kind == "assistant" and block.get("type") == "tool_use":
            print(f"  -> {_describe_call(block, cwd)}")
        elif kind == "user" and block.get("type") == "tool_result" and block.get("is_error"):
            print(f"  !! {_one_line(_result_text(block.get('content')))}")


def _describe_call(block: dict, cwd: Path) -> str:
    name = block["name"]
    detail = block.get("input", {}).get(TOOL_DETAIL.get(name))
    if detail is None:
        return name
    return f"{name}: {_one_line(str(detail).removeprefix(f'{cwd}/'))}"


def _result_text(content: object) -> str:
    if isinstance(content, list):
        return " ".join(part.get("text", "") for part in content)
    return str(content)


def _one_line(text: str) -> str:
    line = " ".join(text.split())
    return line if len(line) <= MAX_LINE else f"{line[:MAX_LINE - 3]}..."
