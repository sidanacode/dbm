"""Local DBM project configuration."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class AlembicSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config: str = "alembic.ini"


class LocalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1)
    server: str = "http://localhost:8000"
    api_token: str | None = None
    alembic: AlembicSettings = AlembicSettings()


class ConfigError(Exception):
    pass


def load_config(path: Path = Path(".dbm.toml")) -> LocalConfig:
    if not path.is_file():
        raise ConfigError(f"DBM config not found at {path}. Run `dbm init` first.")
    try:
        return LocalConfig.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))
    except (tomllib.TOMLDecodeError, ValueError) as exc:
        raise ConfigError(f"Invalid DBM config at {path}: {exc}") from exc


def write_config(config: LocalConfig, path: Path = Path(".dbm.toml")) -> None:
    if path.exists():
        raise ConfigError(f"Refusing to overwrite existing config at {path}.")
    token_line = f'api_token = "{_escape(config.api_token)}"\n' if config.api_token else ""
    content = (
        f'project_id = "{_escape(config.project_id)}"\n'
        f'server = "{_escape(config.server)}"\n'
        f"{token_line}"
        "\n[alembic]\n"
        f'config = "{_escape(config.alembic.config)}"\n'
    )
    path.write_text(content, encoding="utf-8")


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
