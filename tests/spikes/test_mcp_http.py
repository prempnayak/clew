"""V9/V10 (partial, no Gemini): the MCP server over streamable HTTP with bearer auth, called by the MCP client."""

from __future__ import annotations

import socket
import threading
import time

import httpx
import pytest


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.asyncio
async def test_mcp_over_http(graph, monkeypatch):
    import httpx2
    import uvicorn
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    from clew.mcp_server import server
    from clew.mcp_server.tools import Tools

    port = free_port()
    monkeypatch.setenv("MCP_TOKEN_REPORTER", "tok-r")
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", f"127.0.0.1:{port}")
    server._tools = Tools(graph)
    srv = uvicorn.Server(uvicorn.Config(server.app(), host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=srv.run, daemon=True).start()
    while not srv.started:
        time.sleep(0.05)
    url = f"http://127.0.0.1:{port}/mcp"
    try:
        assert httpx.post(url, json={}).status_code == 401
        client = httpx2.AsyncClient(headers={"Authorization": "Bearer tok-r"})
        async with streamable_http_client(url, http_client=client) as (read, write, *_):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = {t.name for t in (await session.list_tools()).tools}
                assert {"get_bug", "file_issue", "repro_steps", "add_cases"} <= names
                res = await session.call_tool("map_summary", {})
                assert not res.is_error
        calls = graph.run("Q44", {"limit": 5})
        assert calls and calls[0]["tool"] == "map_summary" and calls[0]["agent"] == "reporter"
    finally:
        srv.should_exit = True
        server._tools = None
