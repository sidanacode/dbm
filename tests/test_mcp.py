import asyncio

from dbm_coordinator.mcp_server import create_mcp_server
from dbm_coordinator.settings import Settings


def test_mcp_exposes_required_tools() -> None:
    server = create_mcp_server(Settings(coordinator_url="http://coordinator:8000"))
    tools = asyncio.run(server.list_tools())
    assert {tool.name for tool in tools} == {
        "get_project_state",
        "submit_intent",
        "list_intents",
        "check_intent",
        "approve_intent",
        "cancel_intent",
        "acquire_finalization_lease",
        "release_finalization_lease",
    }
