"""Synchronous HTTP client shared by CLI and MCP adapters."""

from __future__ import annotations

from typing import Any, cast

import httpx


class CoordinatorClientError(Exception):
    def __init__(self, code: str, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class CoordinatorClient:
    def __init__(
        self,
        base_url: str,
        api_token: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        headers = {"Authorization": f"Bearer {api_token}"} if api_token else {}
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> CoordinatorClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def create_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_object("POST", "/v1/projects", json=payload)

    def get_project_state(self, project_id: str) -> dict[str, Any]:
        return self._request_object("GET", f"/v1/projects/{project_id}/state")

    def update_project_state(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_object("PUT", f"/v1/projects/{project_id}/state", json=payload)

    def submit_intent(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_object("POST", f"/v1/projects/{project_id}/intents", json=payload)

    def list_intents(self, project_id: str) -> list[dict[str, Any]]:
        result = self._request("GET", f"/v1/projects/{project_id}/intents")
        if not isinstance(result, list):
            raise CoordinatorClientError("invalid_response", "Expected an intent list.")
        if not all(isinstance(item, dict) for item in result):
            raise CoordinatorClientError("invalid_response", "Expected intent objects.")
        return cast(list[dict[str, Any]], result)

    def get_intent(self, intent_id: str) -> dict[str, Any]:
        return self._request_object("GET", f"/v1/intents/{intent_id}")

    def check_intent(self, intent_id: str) -> dict[str, Any]:
        return self._request_object("POST", f"/v1/intents/{intent_id}/check")

    def approve_intent(self, intent_id: str) -> dict[str, Any]:
        return self._request_object("POST", f"/v1/intents/{intent_id}/approve")

    def cancel_intent(self, intent_id: str) -> dict[str, Any]:
        return self._request_object("POST", f"/v1/intents/{intent_id}/cancel")

    def acquire_lease(self, intent_id: str) -> dict[str, Any]:
        return self._request_object("POST", f"/v1/intents/{intent_id}/leases")

    def release_lease(self, lease_id: str) -> dict[str, Any]:
        return self._request_object("POST", f"/v1/leases/{lease_id}/release")

    def _request_object(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        result = self._request(method, path, **kwargs)
        if not isinstance(result, dict):
            raise CoordinatorClientError("invalid_response", "Expected a JSON object.")
        return cast(dict[str, Any], result)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise CoordinatorClientError(
                "coordinator_unavailable", f"Coordinator request failed: {exc}"
            ) from exc
        if response.is_success:
            return response.json()
        try:
            error = response.json().get("error", {})
        except ValueError:
            error = {}
        raise CoordinatorClientError(
            str(error.get("code", "coordinator_error")),
            str(error.get("message", response.text or response.reason_phrase)),
            response.status_code,
        )
