"""Read-only inspection of an Alembic migration graph."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError


class AlembicInspectionError(Exception):
    pass


@dataclass(frozen=True)
class AlembicGraphState:
    heads: list[str]
    graph_digest: str
    revision_count: int


def inspect_alembic_graph(config_path: Path) -> AlembicGraphState:
    try:
        config = Config(str(config_path))
        script_location = config.get_main_option("script_location")
        if (
            script_location
            and not Path(script_location).is_absolute()
            and ":" not in script_location
        ):
            config.set_main_option(
                "script_location",
                str((config_path.resolve().parent / script_location).resolve()),
            )
        script = ScriptDirectory.from_config(config)
        heads = sorted(script.get_heads())
        revisions = [_revision_record(revision) for revision in script.walk_revisions()]
    except (OSError, CommandError, KeyError) as exc:
        raise AlembicInspectionError(
            f"Unable to inspect Alembic graph using {config_path}: {exc}"
        ) from exc

    revisions.sort(key=lambda item: str(item["revision"]))
    encoded = json.dumps(revisions, sort_keys=True, separators=(",", ":")).encode()
    digest = f"sha256:{hashlib.sha256(encoded).hexdigest()}"
    return AlembicGraphState(
        heads=heads,
        graph_digest=digest,
        revision_count=len(revisions),
    )


def _revision_record(revision: Any) -> dict[str, Any]:
    return {
        "revision": revision.revision,
        "down_revision": _sorted_value(revision.down_revision),
        "dependencies": _sorted_value(revision.dependencies),
        "branch_labels": _sorted_value(revision.branch_labels),
    }


def _sorted_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return sorted(str(item) for item in value)
