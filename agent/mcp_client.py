"""How agents reach MCP tools (A6).

One ToolBox for the whole app. Every call names the agent making it, and the agent's
allowlist in config decides whether the call is allowed. Calls have a timeout and bounded
retries with backoff. If a server stays down, the ToolBox records it as degraded so the
UI can say so, and raises ToolUnavailable so the graph can park the job and recover later.
"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from mcp.shared.memory import create_connected_server_and_client_session

from agent.settings import get_settings


class ToolUnavailable(Exception):
    """The server did not answer after all retries (degraded mode)."""


class ToolRejected(Exception):
    """The tool answered with an error that retrying will not fix."""


class ToolBox:
    def __init__(self, servers: dict | None = None):
        """servers: {"marketplace": FastMCP, ...} runs them in-process (tests, single-process mode).
        Without it, servers are reached over Streamable HTTP with MultiServerMCPClient."""
        self.servers = servers
        self.degraded: dict[str, str] = {}
        self._http = None

    def _client(self):
        if self._http is None:
            from langchain_mcp_adapters.client import MultiServerMCPClient
            token = os.getenv("MCP_CLIENT_TOKEN", "dev-mcp-token")
            self._http = MultiServerMCPClient({
                name: {"transport": "streamable_http", "url": os.getenv(f"{name.upper()}_MCP_URL", f"http://{name}-mcp:{port}/mcp"),
                       "headers": {"Authorization": f"Bearer {token}"}}
                for name, port in (("marketplace", 8101), ("portfolio", 8102), ("workspace", 8103))})
        return self._http

    @asynccontextmanager
    async def _session(self, server: str):
        if self.servers is not None:
            async with create_connected_server_and_client_session(self.servers[server]._mcp_server) as s:
                yield s
        else:
            async with self._client().session(server) as s:
                yield s

    async def call(self, agent: str, server: str, tool: str, args: dict | None = None, *,
                   user: str = "local", trace_id: str = "") -> dict:
        cfg = get_settings()
        if tool not in (cfg["tools"].get(agent) or {}).get(server, []):
            raise PermissionError(f"agent '{agent}' is not allowed to call {server}.{tool}")
        tc, last = cfg["tool_call"], ""
        for attempt in range(tc["retries"] + 1):
            try:
                async with self._session(server) as s:
                    r = await asyncio.wait_for(s.call_tool(tool, args or {}, meta={"trace_id": trace_id, "user_id": user}),
                                               tc["timeout_s"])
            except (asyncio.TimeoutError, OSError, ConnectionError, ExceptionGroup) as e:
                last = f"{server} server not reachable ({type(e).__name__})"
            else:
                if not r.isError:
                    self.degraded.pop(server, None)
                    return r.structuredContent or {}
                last = r.content[0].text if r.content else "tool error"
                if "unavailable" not in last and "rate_limited" not in last:
                    raise ToolRejected(f"{server}.{tool}: {last}")
            if attempt < tc["retries"]:
                await asyncio.sleep(tc["backoff_s"] * 2 ** attempt)
        self.degraded[server] = last
        raise ToolUnavailable(f"{server}.{tool}: {last}")
