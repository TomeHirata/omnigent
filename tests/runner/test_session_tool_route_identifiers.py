"""Session tool arguments remain one REST route identifier."""

from __future__ import annotations

import json

import httpx
import pytest

from omnigent.runner.tool_dispatch import (
    _execute_agent_tool,
    _execute_rest_tool,
    _execute_session_query_tool,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name",
    [
        "sys_session_get_info",
        "sys_session_get_history",
        "sys_session_close",
        "sys_agent_get",
        "sys_agent_download",
        "sys_cancel_async",
    ],
)
@pytest.mark.parametrize("identifier", ["notes?draft", "notes#draft", "two/parts", ".", "%20"])
async def test_session_tool_refuses_non_identifier_before_http(
    tool_name: str,
    identifier: str,
) -> None:
    calls: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(404)

    args = {"session_id": identifier, "conversation_id": identifier, "handle_id": identifier}
    async with httpx.AsyncClient(
        base_url="https://server.example",
        transport=httpx.MockTransport(respond),
    ) as client:
        if tool_name.startswith("sys_agent_"):
            result = await _execute_agent_tool(
                tool_name,
                args,
                server_client=client,
                agent_spec=None,
                conversation_id="conv_parent",
                runner_workspace=None,
            )
        elif tool_name == "sys_cancel_async":
            result = await _execute_rest_tool(tool_name, args, client)
        else:
            result = await _execute_session_query_tool(
                tool_name,
                json.dumps(args),
                conversation_id="conv_parent",
                server_client=client,
            )
    assert "Session id must contain" in result
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("identifier", ["a" * 32, "conv_legacy-1"])
async def test_session_tool_preserves_supported_identifiers(identifier: str) -> None:
    paths: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(404)

    async with httpx.AsyncClient(
        base_url="https://server.example",
        transport=httpx.MockTransport(respond),
    ) as client:
        result = await _execute_session_query_tool(
            "sys_session_get_info",
            json.dumps({"session_id": identifier}),
            conversation_id="conv_parent",
            server_client=client,
        )
    assert json.loads(result)["error"] == "session_not_found"
    assert paths == [f"/v1/sessions/{identifier}"]
