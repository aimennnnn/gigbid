# Build status and hand-over notes

Working notes for whoever continues the build (me, or an AI assistant in a new session).
Updated 14 Nov 2026. Deadline: Sunday 15 Nov, 11:59 PM PKT.

## Where things are
- Repo: `C:\Users\aimen\Downloads\Agentic A2\gigbid`, pushed to `github.com/aimennnnn/gigbid` (branch `main`).
- `uv run pytest -q` passes (50 tests). `uv run python -m agent.demo` runs one job on the real model to the approval step.
- Keys live in `.env` (git-ignored): `GROQ_API_KEY`, `OPENROUTER_API_KEY`. Never commit or print them.

## Done
- Skeleton, `agent/config.yaml` (profiles, per-node models, thresholds, rules, tool allowlists, memory rules).
- GigSim simulator (`gigsim/app.py`) and seeded synthetic data (`data/synth/`): 3 personas, 1,500 history jobs,
  dev set of 200 jobs per persona with gold labels (`evals/datasets/dev_*.jsonl`), 60 stream jobs.
  The course kit had no GigSim or data; see `docs/DATA_CARD.md`.
- Part A: Marketplace, Portfolio and Workspace MCP servers with schemas, annotations, idempotency, dry_run,
  bearer auth, rate limiter, audit log, tests, `docs/TOOLS.md`, schema snapshot test. MCP SDK pinned `<2`.
- Part C: bid graph and conversation graph (parallel Send, critic loop max 2, interrupt approval, idempotent
  submit, style and outcome memory with promotion rules, dead-letter state). In-memory checkpointer so far.
- Model client (`agent/llm.py`): prompts in `agent/prompts/`, untrusted text delimited, tokens-per-minute pacing,
  backup providers (OpenRouter, Ollama), `GIGBID_LLM=fake` rule-based stand-in for tests and CI.

## Not done, in priority order
1. Part B: `rag/variants/` V0 dense + V1 decomposition + V2 hybrid RRF + V3 rerank + V8 corrective loop
   (V4 outcome-aware is cheap to add). Embeddings need a real model (fastembed or sentence-transformers) plus a
   hash-embedding fallback for CI. `evals/runners/` rag_eval, decision_eval, gigsim_outcomes, judge_calibration,
   ablation; `make eval` writes `evals/results/*.json`; results table script. Kaggle/Colab notebook that runs the
   evals against Ollama (`OLLAMA_URL`, `GIGBID_PROVIDER=ollama`). `rag/retriever.py` currently uses BM25 only.
2. Part D: FastAPI (`apps/api`: auth, jobs, proposals, approvals, messages, runs, analytics, SSE streaming) and
   Next.js/React TypeScript web app (inbox, job detail, proposal studio with approval, pipeline, messages,
   run viewer, analytics, settings with memory viewer), generated API client, 5 Playwright tests.
3. Part E: Postgres checkpointer and store, Redis worker with scheduled scouting, Docker Compose, CI with eval
   thresholds, tracing (Langfuse), deploy to a public host with a reviewer login.
4. Part A leftovers: live Upwork adapter (`adapters/upwork_live.py`), GitHub MCP, MCP Inspector screenshots,
   tool-granularity study (R&D question A).
5. Part C leftovers: single ReAct agent and `langgraph-supervisor` baselines (R&D question C), trace links.
6. README, R&D report PDF, ARCHITECTURE.md, RUNBOOK.md, EXTENSION.md, demo video, write-up.

## Known issues
- Groq free tier allows 8,000 tokens per minute per model; one proposal is about 10,000 tokens. Real-model evals
  must run on a sample, or on Ollama (Kaggle GPU), and the report must say which.
- OpenRouter model names in config use `:free` variants and are not yet confirmed.
- The simulated client in GigSim is a fixed rule, not an LLM.
- Writer/verifier fix (prompt v2, critic sends evidence-free drafts back) is not yet confirmed on the real model.
- The change-request "platform policy update" file has not been received; `gigsim/seed/policy.json` is version 1.

## Rules we are keeping
- Real commit dates only, small commits per piece. Every number in README and report must come from `evals/results/`.
- No scraping, no browser automation of marketplaces, nothing sent without human approval.
