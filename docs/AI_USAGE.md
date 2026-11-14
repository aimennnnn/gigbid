# AI usage

| Tool | Files | Notes |
|---|---|---|
| Claude | `gigsim/`, `data/synth/`, `mcp_servers/` and their tests, `rag/ingest/loaders.py`, `rag/index/bm25.py`, `docs/TOOLS.md`, `docs/DATA_CARD.md` | Drafted with Claude, reviewed and run by me. |
| Claude | `agent/llm.py`, `agent/fake_llm.py`, `agent/guards.py`, `agent/mcp_client.py`, `agent/nodes/`, `agent/graphs/bid_graph.py`, `agent/memory/`, `agent/prompts/`, `rag/verify.py`, `tests/integration/` | Drafted with Claude, reviewed and run by me. |
| Claude | repo skeleton, `agent/config.yaml`, `agent/settings.py`, `agent/handoffs.py`, `agent/state.py`, `agent/marketplace_port.py`, `tests/unit/` | Drafted with Claude, reviewed and run by me. |
| Claude | `rag/ingest/chunker.py`, `rag/index/embed.py`, `rag/index/vector.py`, `rag/variants/`, `rag/retriever.py`, `evals/runners/`, `evals/kaggle_eval.ipynb`, `agent/prompts/judge.md`, `tests/unit/test_rag.py`, `tests/unit/test_evals.py`, RAG section of `agent/config.yaml` | Drafted with Claude and tested with stand-in models only. Every evaluation number comes from runs I do myself. |

## Things it got wrong that I caught

- It first installed the MCP Python SDK 2.x. `langchain-mcp-adapters` 0.3.2 needs `mcp<2`, and 2.x renamed `FastMCP` to `MCPServer`, so the two could not work together. Pinned `mcp>=1.24,<2`.
- Node functions typed `config: dict` were not given the run config by LangGraph, so the thread id was missing and the first graph test failed. Fixed by typing it as `RunnableConfig`.
