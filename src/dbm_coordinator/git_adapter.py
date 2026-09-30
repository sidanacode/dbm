"""Read-only Git metadata used as intent provenance."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class GitInspectionError(Exception):
    pass


@dataclass(frozen=True)
class GitState:
    branch: str
    commit_sha: str
    is_dirty: bool


def inspect_git(repository: Path | None = None) -> GitState:
    repository = repository or Path.cwd()
    return GitState(
        branch=_git(repository, "branch", "--show-current") or "HEAD",
        commit_sha=_git(repository, "rev-parse", "HEAD"),
        is_dirty=bool(_git(repository, "status", "--porcelain")),
    )


def _git(repository: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise GitInspectionError(f"Unable to inspect Git repository at {repository}.") from exc
    return result.stdout.strip()
