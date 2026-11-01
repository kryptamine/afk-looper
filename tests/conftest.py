import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

FAKES = Path(__file__).parent / "fakes"
SRC = Path(__file__).parent.parent / "src"


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@dataclass
class World:
    checkout: Path
    origin: Path
    tmp: Path
    env: dict[str, str]

    def issues(self, **issues: dict) -> None:
        """issues(i1={"title": ..., "blocked": 0}), keyed i<number>."""
        state = {k[1:]: {"blocked": 0, "state": "OPEN", **v} for k, v in issues.items()}
        self._gh_state().write_text(json.dumps({"issues": state, "prs": {}}))

    def scenario(self, *steps: dict) -> None:
        (self.tmp / "scenario.json").write_text(json.dumps(list(steps)))

    def afk(self, *args: str, stdin: str = "") -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "afk_looper", *args],
            cwd=self.checkout, env=self.env, input=stdin, capture_output=True, text=True, timeout=120,
        )

    def agent_runs(self) -> list[list[str]]:
        calls = self.tmp / "claude-calls"
        return [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []

    def github(self) -> dict:
        return json.loads(self._gh_state().read_text())

    def origin_log(self) -> list[str]:
        return git("log", "--format=%s", "main", cwd=self.origin).splitlines()

    def origin_branches(self) -> list[str]:
        return git("branch", "--format=%(refname:short)", cwd=self.origin).splitlines()

    def _gh_state(self) -> Path:
        return self.tmp / "gh-state.json"


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    origin = tmp_path / "origin.git"
    checkout = tmp_path / "widget"
    env = {
        **os.environ,
        "PATH": f"{FAKES}{os.pathsep}{os.environ['PATH']}",
        "PYTHONPATH": str(SRC),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
        "FAKE_ORIGIN": str(origin),
        "FAKE_GH_STATE": str(tmp_path / "gh-state.json"),
        "FAKE_CLAUDE_CALLS": str(tmp_path / "claude-calls"),
        "FAKE_CLAUDE_SCENARIO": str(tmp_path / "scenario.json"),
        "FAKE_UV_CALLS": str(tmp_path / "uv-calls"),
    }
    env.pop("AFK_BUDGET_USD", None)
    for name in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM", "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
                 "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(name, env[name])
    git("init", "-q", "--bare", "-b", "main", str(origin), cwd=tmp_path)
    git("clone", "-q", str(origin), str(checkout), cwd=tmp_path)
    git("switch", "-q", "-c", "main", cwd=checkout)
    (checkout / ".afk.toml").write_text('install = "true"\ncheck = "test ! -e broken"\n')
    git("add", ".", cwd=checkout)
    git("commit", "-qm", "chore: start", cwd=checkout)
    git("push", "-q", "-u", "origin", "main", cwd=checkout)
    world = World(checkout, origin, tmp_path, env)
    world.issues()
    world.scenario()
    return world
