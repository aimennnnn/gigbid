# AI usage

| Tool | Files | Notes |
|---|---|---|
| Claude | `gigsim/`, `data/synth/`, `mcp_servers/` and their tests, `rag/ingest/loaders.py`, `rag/index/bm25.py`, `docs/TOOLS.md`, `docs/DATA_CARD.md` | Drafted with Claude, reviewed and run by me. |
| Claude | repo skeleton, `agent/config.yaml`, `agent/settings.py`, `agent/handoffs.py`, `agent/state.py`, `agent/marketplace_port.py`, `tests/unit/` | Drafted with Claude, reviewed and run by me. |

## Things it got wrong that I caught

- It first installed the MCP Python SDK 2.x. `langchain-mcp-adapters` 0.3.2 needs `mcp<2`, and 2.x renamed `FastMCP` to `MCPServer`, so the two could not work together. Pinned `mcp>=1.24,<2`.
