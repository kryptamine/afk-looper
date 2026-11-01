import os
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

CONFIG_FILE = ".afk.toml"


@dataclass(frozen=True)
class Config:
    label: str = "ready-for-agent"
    install: str = "make install"
    check: str = "make check"
    budget_usd: float = 30
    allow: tuple[str, ...] = ()


def load_config(root: Path) -> Config:
    path = root / CONFIG_FILE
    values = tomllib.loads(path.read_text()) if path.exists() else {}
    unknown = values.keys() - {field.name for field in fields(Config)}
    if unknown:
        raise SystemExit(f"{CONFIG_FILE}: unknown keys: {', '.join(sorted(unknown))}")
    values["allow"] = tuple(values.get("allow", ()))
    if budget := os.environ.get("AFK_BUDGET_USD"):
        values["budget_usd"] = float(budget)
    return Config(**values)
