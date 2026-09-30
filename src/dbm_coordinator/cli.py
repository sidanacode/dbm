"""Command-line interface for local DBM workflows."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, Never, TypeVar

import typer

from dbm_coordinator.alembic_adapter import AlembicInspectionError, inspect_alembic_graph
from dbm_coordinator.client import CoordinatorClient, CoordinatorClientError
from dbm_coordinator.config import (
    AlembicSettings,
    ConfigError,
    LocalConfig,
    load_config,
    write_config,
)
from dbm_coordinator.git_adapter import GitInspectionError, inspect_git

app = typer.Typer(
    name="dbm",
    help="Coordinate database migration intent before generating migrations.",
    no_args_is_help=True,
)
DEFAULT_CONFIG_PATH = Path(".dbm.toml")
T = TypeVar("T")


@app.command("init")
def initialize(
    project_id: Annotated[str, typer.Option(help="Coordinator project UUID.")],
    server: Annotated[str, typer.Option(help="Coordinator base URL.")] = "http://localhost:8000",
    alembic_config: Annotated[str, typer.Option(help="Path to alembic.ini.")] = "alembic.ini",
    config_path: Annotated[Path, typer.Option(help="Config file to create.")] = DEFAULT_CONFIG_PATH,
) -> None:
    """Create a local .dbm.toml file."""
    _handle(
        lambda: write_config(
            LocalConfig(
                project_id=project_id,
                server=server,
                alembic=AlembicSettings(config=alembic_config),
            ),
            config_path,
        )
    )
    typer.echo(f"Created {config_path}")


@app.command()
def inspect(
    config_path: Annotated[Path, typer.Option(help="DBM config path.")] = DEFAULT_CONFIG_PATH,
) -> None:
    """Inspect local Git and Alembic state without contacting the coordinator."""
    config = _load(config_path)
    repository = config_path.resolve().parent
    graph = _handle(lambda: inspect_alembic_graph(repository / config.alembic.config))
    git = _handle(lambda: inspect_git(repository))
    _print(
        {
            "git": {
                "branch": git.branch,
                "commit_sha": git.commit_sha,
                "is_dirty": git.is_dirty,
            },
            "alembic": {
                "heads": graph.heads,
                "graph_digest": graph.graph_digest,
                "revision_count": graph.revision_count,
            },
        }
    )


@app.command()
def state(
    config_path: Annotated[Path, typer.Option()] = DEFAULT_CONFIG_PATH,
) -> None:
    """Show accepted coordinator state for this project."""
    config = _load(config_path)
    _call(config, lambda client: client.get_project_state(config.project_id))


@app.command("sync-state")
def sync_state(
    config_path: Annotated[Path, typer.Option()] = DEFAULT_CONFIG_PATH,
) -> None:
    """Publish the local Alembic heads and graph digest as accepted state."""
    config = _load(config_path)
    repository = config_path.resolve().parent
    graph = _handle(lambda: inspect_alembic_graph(repository / config.alembic.config))
    _call(
        config,
        lambda client: client.update_project_state(
            config.project_id,
            {"current_heads": graph.heads, "graph_digest": graph.graph_digest},
        ),
    )


@app.command()
def submit(
    intent_file: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    config_path: Annotated[Path, typer.Option()] = DEFAULT_CONFIG_PATH,
) -> None:
    """Submit a versioned intent JSON document."""
    config = _load(config_path)
    try:
        payload = json.loads(intent_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"Unable to read intent file: {exc}")
    _call(config, lambda client: client.submit_intent(config.project_id, payload))


@app.command()
def intents(
    config_path: Annotated[Path, typer.Option()] = DEFAULT_CONFIG_PATH,
) -> None:
    """List project intents."""
    config = _load(config_path)
    _call(config, lambda client: client.list_intents(config.project_id))


@app.command()
def check(
    intent_id: str,
    config_path: Annotated[Path, typer.Option()] = DEFAULT_CONFIG_PATH,
) -> None:
    """Check an intent against accepted and active work."""
    config = _load(config_path)
    _call(config, lambda client: client.check_intent(intent_id))


@app.command()
def approve(
    intent_id: str,
    config_path: Annotated[Path, typer.Option()] = DEFAULT_CONFIG_PATH,
) -> None:
    """Record developer approval for a non-conflicting intent."""
    config = _load(config_path)
    _call(config, lambda client: client.approve_intent(intent_id))


@app.command()
def cancel(
    intent_id: str,
    config_path: Annotated[Path, typer.Option()] = DEFAULT_CONFIG_PATH,
) -> None:
    """Cancel an active intent."""
    config = _load(config_path)
    _call(config, lambda client: client.cancel_intent(intent_id))


@app.command()
def lease(
    intent_id: str,
    config_path: Annotated[Path, typer.Option()] = DEFAULT_CONFIG_PATH,
) -> None:
    """Acquire a short-lived migration finalization lease."""
    config = _load(config_path)
    _call(config, lambda client: client.acquire_lease(intent_id))


@app.command("release-lease")
def release_lease(
    lease_id: str,
    config_path: Annotated[Path, typer.Option()] = DEFAULT_CONFIG_PATH,
) -> None:
    """Release a finalization lease."""
    config = _load(config_path)
    _call(config, lambda client: client.release_lease(lease_id))


def _load(path: Path) -> LocalConfig:
    return _handle(lambda: load_config(path))


def _call(config: LocalConfig, operation: Any) -> None:
    def execute() -> Any:
        with CoordinatorClient(config.server, config.api_token) as client:
            return operation(client)

    _print(_handle(execute))


def _print(value: Any) -> None:
    typer.echo(json.dumps(value, indent=2, sort_keys=True, default=str))


def _handle(operation: Callable[[], T]) -> T:
    try:
        return operation()
    except (ConfigError, AlembicInspectionError, GitInspectionError) as exc:
        _fail(str(exc))
    except CoordinatorClientError as exc:
        _fail(f"{exc.code}: {exc.message}")


def _fail(message: str) -> Never:
    typer.echo(message, err=True)
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
