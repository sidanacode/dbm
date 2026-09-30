from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dbm_coordinator.api.main import create_app
from dbm_coordinator.settings import Settings


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}")
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def project_payload() -> dict[str, object]:
    return {
        "slug": "example-project",
        "name": "Example Project",
        "default_branch": "main",
        "current_heads": ["m10"],
        "graph_digest": "sha256:accepted",
    }


def intent_payload(
    *,
    title: str,
    kind: str,
    table: str,
    column: str | None = None,
    new_column: str | None = None,
    digest: str = "sha256:accepted",
) -> dict[str, object]:
    operation: dict[str, object] = {
        "kind": kind,
        "object": {"schema_name": "public", "table_name": table, "column_name": column},
    }
    if new_column:
        operation["new_object"] = {
            "schema_name": "public",
            "table_name": table,
            "column_name": new_column,
        }
    return {
        "protocol_version": 1,
        "title": title,
        "source": {
            "branch": f"feature/{title}",
            "commit_sha": "abc123",
            "base_heads": ["m10"],
            "migration_graph_digest": digest,
        },
        "operations": [operation],
    }


def create_project(client: TestClient) -> str:
    response = client.post("/v1/projects", json=project_payload())
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def submit(client: TestClient, project_id: str, payload: dict[str, object]) -> dict[str, object]:
    response = client.post(f"/v1/projects/{project_id}/intents", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_health_is_public(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_provider_catalog_can_be_filtered(client: TestClient) -> None:
    response = client.get("/v1/providers", params={"kind": "source_control"})
    assert response.status_code == 200
    providers = response.json()
    assert {item["id"] for item in providers} >= {"local-git", "github", "gitlab"}
    gitlab = next(item for item in providers if item["id"] == "gitlab")
    assert gitlab["lifecycle"] == "planned"
    assert gitlab["capabilities"] == []


def test_ac_001_conflict_story_over_http(client: TestClient) -> None:
    project_id = create_project(client)
    rename = submit(
        client,
        project_id,
        intent_payload(
            title="rename-name",
            kind="rename_column",
            table="users",
            column="name",
            new_column="full_name",
        ),
    )
    assert client.post(f"/v1/intents/{rename['id']}/check").json()["status"] == "safe"

    alter = submit(
        client,
        project_id,
        intent_payload(title="widen-name", kind="alter_column", table="users", column="name"),
    )
    response = client.post(f"/v1/intents/{alter['id']}/check")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "conflict"
    assert body["findings"][0]["code"] == "object_renamed"
    assert body["findings"][0]["new_object"]["column_name"] == "full_name"


def test_conflicting_intent_cannot_be_approved(client: TestClient) -> None:
    project_id = create_project(client)
    first = submit(
        client,
        project_id,
        intent_payload(title="first", kind="alter_column", table="users", column="name"),
    )
    second = submit(
        client,
        project_id,
        intent_payload(title="second", kind="alter_column", table="users", column="name"),
    )
    response = client.post(f"/v1/intents/{second['id']}/approve")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "intent_has_conflicts"
    assert first["status"] == "submitted"


def test_ac_005_only_one_project_lease_is_active(client: TestClient) -> None:
    project_id = create_project(client)
    first = submit(
        client,
        project_id,
        intent_payload(title="phone", kind="add_column", table="users", column="phone"),
    )
    second = submit(
        client,
        project_id,
        intent_payload(title="reference", kind="add_column", table="orders", column="reference"),
    )
    assert client.post(f"/v1/intents/{first['id']}/approve").status_code == 200
    assert client.post(f"/v1/intents/{second['id']}/approve").status_code == 200

    first_lease = client.post(f"/v1/intents/{first['id']}/leases")
    assert first_lease.status_code == 201
    blocked = client.post(f"/v1/intents/{second['id']}/leases")
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "project_lease_held"

    released = client.post(f"/v1/leases/{first_lease.json()['id']}/release")
    assert released.status_code == 200
    assert client.post(f"/v1/intents/{second['id']}/leases").status_code == 201


def test_stale_intent_cannot_acquire_lease(client: TestClient) -> None:
    project_id = create_project(client)
    stale = submit(
        client,
        project_id,
        intent_payload(
            title="timezone",
            kind="add_column",
            table="users",
            column="timezone",
            digest="sha256:old",
        ),
    )
    assert client.post(f"/v1/intents/{stale['id']}/approve").status_code == 200
    response = client.post(f"/v1/intents/{stale['id']}/leases")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "stale_intent"


def test_ac_006_optional_authentication(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'auth.db'}",
        api_token="secret-token",
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").status_code == 200
        unauthorized = client.post("/v1/projects", json=project_payload())
        assert unauthorized.status_code == 401
        authorized = client.post(
            "/v1/projects",
            json=project_payload(),
            headers={"Authorization": "Bearer secret-token"},
        )
        assert authorized.status_code == 201
