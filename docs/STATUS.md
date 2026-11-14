# Build status and hand-over notes

Working notes for whoever continues the build (me, or an AI assistant in a new session).
Updated 14 Nov 2026. Deadline: Sunday 15 Nov, 11:59 PM PKT.

## Where things are
- Repo: `C:\Users\aimen\Downloads\Agentic A2\gigbid`, pushed to `github.com/aimennnnn/gigbid` (branch `main`).
- `uv run pytest -q` passes (70 tests). `uv run python -m agent.demo` runs one job on the real model to the approval step.
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
- Part B code (14 Nov): everything below is built and tested with stand-in models. **No real evaluation has been run yet.**
  - Ingestion: `rag/ingest/chunker.py` (fixed chunks that keep metadata), `rag/index/embed.py` (fastembed, vectors cached
    on disk by text hash, so re-indexing only embeds new chunks), `rag/index/vector.py`.
  - Variants, one step per file in `rag/variants/`: V0 naive dense, V1 decomposition, V2 hybrid BM25 + dense (RRF),
    V3 cross-encoder rerank, V4 outcome-aware boost, V8 corrective loop in LangGraph (grade, re-query, refuse).
  - A variant is a list of steps under `rag.variants` in `agent/config.yaml`. `rag/retriever.py` builds it. The app uses
    `rag.variant` (still `keyword`, the old behaviour, until the evals pick a winner). The Fit Matcher follows it.
  - Evals in `evals/runners/`: `rag_eval`, `ablation`, `decision_eval`, `gigsim_outcomes`, `judge_calibration`,
    `results_table`, `run_all` (`make eval`). Kaggle notebook: `evals/kaggle_eval.ipynb`.
  - `GIGBID_RAG_MODELS=fake` (hash embeddings, word-overlap reranker) is for tests and CI only, like `GIGBID_LLM=fake`.

## Part B: what is left, in order (all of it is running things, not writing code)
1. On the laptop: `uv run python -m evals.runners.run_all --only rag` (downloads the embedding and reranker models the
   first time, then a few minutes, no LLM). Then `uv run python -m evals.runners.rag_eval --sweep`.
2. Read the output and edit `agent/config.yaml`: set `rag.corrective.min_score` to the suggested value, and remove from
   `rag.variants.best` any step whose removal made the numbers go up in `evals/results/ablation.json`. Re-run step 1.
3. Commit and push. Open `evals/kaggle_eval.ipynb` on Kaggle (GPU T4 x2, Internet on) and Run All. Download the zip.
4. Unzip over the project. Score the 30 proposals in `evals/datasets/judge_labels.csv` (rubric: `agent/prompts/judge.md`),
   then `uv run python -m evals.runners.judge_calibration`. Send `evals/datasets/pairwise_panel.csv` to classmates,
   then `uv run python -m evals.runners.judge_calibration --tally`.
5. Set `rag.variant` in config to the variant that won, write the one-paragraph decision and the R&D question B
   hypothesis and findings in the report, commit `evals/results/`.
- Not built in Part B: a PDF loader for CVs (the synthetic CVs are Markdown), repo ingestion through the GitHub MCP
  server (Part A leftover), V5/V6/V7/V9 (optional), the CI job that fails on eval thresholds (Part E).

## Not done, in priority order
1. Part B: run the evaluations (steps above).
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
- Confirmed on the real model (Groq, 14 Nov): `agent.demo` on `dev-ml-000` reaches approval in about 7 seconds and about 10,300 tokens, decision bid (fit 0.80), draft keeps two supported claims with evidence ids.
- Only one job has been run on the real model so far. No evaluation numbers exist yet.
- Part B was built in a sandbox that cannot download models, so the real embedding model (nomic-embed-text-v1.5),
  the real reranker (ms-marco-MiniLM-L-12-v2) and Ollama have not been run with this code yet. First real run = step 1.
- The reranker in config is the small MiniLM one, chosen for laptop CPU speed, not by measurement. `BAAI/bge-reranker-v2-m3`
  can be put in `profiles.*.reranker` to compare.
- `rag.corrective.min_score` (0.3) and `rag.outcome_boost` (0.3) are starting guesses until the sweep and ablation are run.
- In the outcome eval the script approves proposals in place of the human. It refuses to run unless the marketplace is GigSim.
- Ollama timeouts are 6x the hosted ones (`timeout_scale`); if Kaggle still times out, raise it in config.
- The change-request "platform policy update" file has not been received; `gigsim/seed/policy.json` is version 1.

## Rules we are keeping
- Real commit dates only, small commits per piece. Every number in README and report must come from `evals/results/`.
- No scraping, no browser automation of marketplaces, nothing sent without human approval.
