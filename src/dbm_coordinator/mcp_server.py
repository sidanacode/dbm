"""MCP tools backed by the shared DBM coordinator API."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from dbm_coordinator.client import CoordinatorClient, CoordinatorClientError
from dbm_coordinator.settings import Settings, get_settings

T = TypeVar("T")


def create_mcp_server(settings: Settings | None = None) -> MCPServer:
    runtime = settings or get_settings()
    server = MCPServer(
        "DBM",
        description="Coordinate database migration intent before migrations are finalized.",
        instructions=(
            "Check project state and active intents before generating an Alembic migration. "
            "Never treat a semantic reinterpretation as approved unless the developer confirms it."
        ),
        version="0.1.0",
    )

    def call(operation: Callable[[CoordinatorClient], T]) -> T:
        try:
            with CoordinatorClient(runtime.coordinator_url, runtime.api_token) as client:
                return operation(client)
        except CoordinatorClientError as exc:
            raise ToolError(f"{exc.code}: {exc.message}") from exc

    @server.tool()
    def get_project_state(project_id: str) -> dict[str, Any]:
        """Return accepted Alembic heads and graph digest for a DBM project."""
        return call(lambda client: client.get_project_state(project_id))

    @server.tool()
    def submit_intent(project_id: str, intent: dict[str, Any]) -> dict[str, Any]:
        """Submit a version 1 structured schema-change intent."""
        return call(lambda client: client.submit_intent(project_id, intent))

    @server.tool()
    def list_intents(project_id: str) -> list[dict[str, Any]]:
        """List migration intents known to a DBM project."""
        return call(lambda client: client.list_intents(project_id))

    @server.tool()
    def check_intent(intent_id: str) -> dict[str, Any]:
        """Check an intent for conflicts, dependencies, and stale base state."""
        return call(lambda client: client.check_intent(intent_id))

    @server.tool()
    def approve_intent(intent_id: str) -> dict[str, Any]:
        """Record explicit developer approval for a non-conflicting intent."""
        return call(lambda client: client.approve_intent(intent_id))

    @server.tool()
    def cancel_intent(intent_id: str) -> dict[str, Any]:
        """Cancel an active migration intent."""
        return call(lambda client: client.cancel_intent(intent_id))

    @server.tool()
    def acquire_finalization_lease(intent_id: str) -> dict[str, Any]:
        """Acquire a short-lived lease before final migration generation."""
        return call(lambda client: client.acquire_lease(intent_id))

    @server.tool()
    def release_finalization_lease(lease_id: str) -> dict[str, Any]:
        """Release a migration finalization lease."""
        return call(lambda client: client.release_lease(lease_id))

    @server.custom_route("/health", methods=["GET"])  # type: ignore[untyped-decorator]
    async def health(_: Request) -> Response:
        return JSONResponse({"status": "ok", "service": "dbm-mcp"})

    return server


mcp = create_mcp_server()


def run() -> None:
    settings = get_settings()
    server = create_mcp_server(settings)
    if settings.mcp_transport == "stdio":
        server.run(transport="stdio")
        return
    server.run(
        transport="streamable-http",
        host=settings.mcp_host,
        port=settings.mcp_port,
        streamable_http_path=settings.mcp_path,
        json_response=True,
        stateless_http=True,
    )


if __name__ == "__main__":
    run()
