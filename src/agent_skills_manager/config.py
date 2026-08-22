"""Application configuration."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_AGENT_TARGETS: list[dict[str, str]] = [
    {"name": "Cursor", "path": "~/.cursor/skills/"},
    {"name": "Claude", "path": "~/.claude/skills/"},
    {"name": "Codex", "path": "~/.codex/skills/"},
    {"name": "OpenCode", "path": "~/.config/opencode/skills/"},
]

PROJECT_SKILL_PATHS: list[str] = [
    ".agents/skills",
    ".cursor/skills",
    ".claude/skills",
    ".codex/skills",
    ".opencode/skills",
]


class Settings(BaseSettings):
    """Runtime settings."""

    skills_dir: Path = Path.home() / ".agents" / "skills"
    config_dir: Path = Path.home() / ".agents" / "skill-manager"
    app_title: str = "Agent Skills Manager"
    app_version: str = "0.1.0"
    host: str = "127.0.0.1"
    port: int = 8000

    model_config = SettingsConfigDict(env_prefix="asm_")

    def ensure_dirs(self) -> None:
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    return Settings()
