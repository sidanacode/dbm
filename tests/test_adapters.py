import subprocess
from pathlib import Path

from dbm_coordinator.alembic_adapter import inspect_alembic_graph
from dbm_coordinator.config import AlembicSettings, LocalConfig, load_config, write_config
from dbm_coordinator.git_adapter import inspect_git


def test_config_round_trip(tmp_path: Path) -> None:
    path = tmp_path / ".dbm.toml"
    expected = LocalConfig(
        project_id="project-123",
        server="https://dbm.example.com",
        api_token="token",
        alembic=AlembicSettings(config="database/alembic.ini"),
    )
    write_config(expected, path)
    assert load_config(path) == expected


def test_git_inspection(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True
    )

    state = inspect_git(tmp_path)

    assert state.branch == "main"
    assert len(state.commit_sha) == 40
    assert state.is_dirty is False


def test_alembic_graph_digest_changes_with_graph(tmp_path: Path) -> None:
    versions = tmp_path / "migrations" / "versions"
    versions.mkdir(parents=True)
    (tmp_path / "alembic.ini").write_text(
        "[alembic]\nscript_location = migrations\n",
        encoding="utf-8",
    )
    (tmp_path / "migrations" / "env.py").write_text("", encoding="utf-8")
    first = versions / "a1_initial.py"
    first.write_text(
        '"""initial"""\nrevision = "a1"\ndown_revision = None\n',
        encoding="utf-8",
    )

    before = inspect_alembic_graph(tmp_path / "alembic.ini")
    assert before.heads == ["a1"]
    assert before.revision_count == 1

    (versions / "b2_next.py").write_text(
        '"""next"""\nrevision = "b2"\ndown_revision = "a1"\n',
        encoding="utf-8",
    )
    after = inspect_alembic_graph(tmp_path / "alembic.ini")
    assert after.heads == ["b2"]
    assert after.graph_digest != before.graph_digest
