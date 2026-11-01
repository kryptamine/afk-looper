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
    "Bash(git *)", "Bash(gh issue view *)", "Bash(gh issue comment *)", "Bash(make *)",
    "Bash(ls *)", "Bash(cat *)", "Bash(head *)", "Bash(tail *)", "Bash(wc *)", "Bash(rg *)",
    "Bash(grep *)", "Bash(find *)", "Bash(sed *)", "Bash(awk *)", "Bash(perl *)", "Bash(jq *)",
    "Bash(mkdir *)", "Bash(mv *)", "Bash(cp *)", "Bash(rm *)", "Bash(chmod *)",
)
DENIED = ("Bash(git push *)", "Bash(gh pr *)")


@dataclass(frozen=True)
class AgentResult:
    session_id: str | None
    subtype: str
    status: str
    question: str
    pr_title: str
    pr_body: str


def run_agent(prompt: str, session: str | None, cwd: Path, log: Path, config: Config) -> AgentResult:
    args = [
        "claude", "-p", prompt,
        "--output-format", "stream-json", "--verbose", "--json-schema", SCHEMA,
        "--permission-mode", "acceptEdits", "--max-budget-usd", str(config.budget_usd),
        "--allowedTools", *ALLOWED, *config.allow,
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
            _show(event)
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


def _show(event: dict) -> None:
    if event.get("type") != "assistant":
        return
    for block in event.get("message", {}).get("content", []):
        if block.get("type") == "text":
            print(block["text"])
        elif block.get("type") == "tool_use":
            print(f"  -> {block['name']}")
