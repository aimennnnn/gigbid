# AI usage

| Tool | Files | Notes |
|---|---|---|
| Claude | `gigsim/`, `data/synth/`, `mcp_servers/` and their tests, `rag/ingest/loaders.py`, `rag/index/bm25.py`, `docs/TOOLS.md`, `docs/DATA_CARD.md` | Drafted with Claude, reviewed and run by me. |
| Claude | `agent/llm.py`, `agent/fake_llm.py`, `agent/guards.py`, `agent/mcp_client.py`, `agent/nodes/`, `agent/graphs/bid_graph.py`, `agent/memory/`, `agent/prompts/`, `rag/verify.py`, `tests/integration/` | Drafted with Claude, reviewed and run by me. |
| Claude | repo skeleton, `agent/config.yaml`, `agent/settings.py`, `agent/handoffs.py`, `agent/state.py`, `agent/marketplace_port.py`, `tests/unit/` | Drafted with Claude, reviewed and run by me. |
| Claude | `rag/ingest/chunker.py`, `rag/index/embed.py`, `rag/index/vector.py`, `rag/variants/`, `rag/retriever.py`, `evals/runners/`, `evals/kaggle_eval.ipynb`, `agent/prompts/judge.md`, `tests/unit/test_rag.py`, `tests/unit/test_evals.py`, RAG section of `agent/config.yaml` | Drafted with Claude and tested with stand-in models only. Every evaluation number comes from runs I do myself. |
| Claude | `apps/api/`, `apps/web/`, `tests/integration/test_api.py`, `apps/web/tests/e2e/`, `evals/runners/gate.py`, `.github/workflows/ci.yml`, the injection guard in `agent/guards.py` and `agent/nodes/writer.py` | Drafted with Claude on 15 Nov. Tested with stand-in models: the API tests, the five Playwright tests and the eval gates pass. The web app has not been run against a real model. |
| Claude | `evals/runners/ab_test.py`, `docs/EXTENSION.md`, `evals/runners/tool_study.py`, `evals/datasets/tool_tasks.jsonl`, `evals/kaggle_tool_study.ipynb`, `apps/web/tests/demo/record-demo.mjs`, `docs/demo/inbox-to-reply.mp4` | Drafted with Claude on 15 Nov. The A/B test reads the real proposals from my Kaggle run. The tool study ran on Kaggle from my account; its result file was copied out of the run log and its SHA-256 checked against the one the notebook printed. The demo video was recorded by a script against stand-in models. |
| Claude | SQLite persistence in `apps/api/runtime.py`, `infra/docker-compose.yml`, `infra/docker/*.Dockerfile` | Drafted with Claude on 15 Nov. The restart test passes; the Docker files were never run (no Docker daemon available). |
| Claude | `evals/runners/arch_study.py`, `agent/prompts/arch_*.md`, `evals/kaggle_arch_study.ipynb`, `tests/integration/test_arch_study.py`, `docs/ARCHITECTURE.md`, `docs/RUNBOOK.md` | Drafted with Claude on 15 Nov. The architecture study is tested with stand-in models; any real number comes from a Kaggle run on my account. |
| Claude | `infra/space/Dockerfile`, `infra/space/start.sh`, the `/api` forwarding in `apps/web/next.config.mjs`, the Render service setup | Drafted and set up with Claude on 15 Nov, in my Render account, on the free plan. The live site runs stand-in models. |
| Claude | `docs/report/GigBid_RnD_Report.docx` and `.pdf` | Drafted with Claude from the result files in `evals/results/`. Sections for work that was not done say so. I read it and am responsible for what it claims. |

## Things it got wrong that I caught

- It first installed the MCP Python SDK 2.x. `langchain-mcp-adapters` 0.3.2 needs `mcp<2`, and 2.x renamed `FastMCP` to `MCPServer`, so the two could not work together. Pinned `mcp>=1.24,<2`.
- Node functions typed `config: dict` were not given the run config by LangGraph, so the thread id was missing and the first graph test failed. Fixed by typing it as `RunnableConfig`.
- The first scoring sheet for the judge calibration cut each evidence text at 300 characters, which hid the result numbers from me while the judge saw the full text. I noticed while scoring; it was fixed before my scores were entered.
- During the first Kaggle run it told me the model was answering when every call was failing (the progress counter moves on failures too). The model download had failed; that run's decision and proposal numbers were thrown away.
- The Writer copied a planted code word from a job post into a proposal. The evaluation caught it; the fix is in `agent/guards.py` and was re-measured (`evals/results/injection_check.json`).
- The compliance check treated `2026-11-15 10:00` in a client reply as a phone number and masked it. Seen while recording the demo; fixed in `mcp_servers/common.py` with a test.
- It opened the SQLite memory store with Python's default transaction mode, so two jobs analysed at once failed with "cannot start a transaction within a transaction". The restart test caught it before anything was committed.
- The first deployment build failed: the Dockerfile let uv pick the newest Python (3.15), which `onnxruntime` does not support yet. Pinned to 3.12.
- Render's form pre-selected the $7 per month plan. It was switched to the free plan before the service was created.
