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
- Part B code (14 Nov): built, tested with stand-in models, and the retrieval part has run on real models on Kaggle.
  - Ingestion: `rag/ingest/chunker.py` (fixed chunks that keep metadata), `rag/index/embed.py` (fastembed, vectors cached
    on disk by text hash, so re-indexing only embeds new chunks), `rag/index/vector.py`.
  - Variants, one step per file in `rag/variants/`: V0 naive dense, V1 decomposition, V2 hybrid BM25 + dense (RRF),
    V3 cross-encoder rerank, V4 outcome-aware boost, V8 corrective loop in LangGraph (grade, re-query, refuse).
  - A variant is a list of steps under `rag.variants` in `agent/config.yaml`. `rag/retriever.py` builds it. The app uses
    `rag.variant`. The Fit Matcher follows it.
  - Evals in `evals/runners/`: `rag_eval`, `ablation`, `decision_eval`, `gigsim_outcomes`, `judge_calibration`,
    `results_table`, `run_all` (`make eval`). Kaggle notebook: `evals/kaggle_eval.ipynb`.
  - `GIGBID_RAG_MODELS=fake` (hash embeddings, word-overlap reranker) is for tests and CI only, like `GIGBID_LLM=fake`.

## Part B: first real retrieval run (14 Nov, Kaggle CPU, commit 2f0cab8, 600 dev jobs)
Read off the notebook output; the result files of that run were not kept. The committed numbers come from the final run.

| Variant | Recall@5 | nDCG@10 | Retrieval p95 |
|---|---|---|---|
| keyword (old behaviour) | 0.572 | 0.705 | 3 ms |
| V0 naive dense | 0.806 | 0.890 | 146 ms |
| V1 decomposition | 0.651 | 0.764 | 213 ms |
| V2 hybrid | 0.889 | 0.917 | 154 ms |
| V3 rerank | 0.771 | 0.877 | 1.1 s |
| V4 outcome boost | 0.702 | 0.822 | 181 ms |
| V8 corrective (min_score 0.3) | 0.590 | 0.745 | 3.1 s |
| all five steps stacked | 0.605 | 0.752 | 23.9 s |

- Only hybrid beat the baseline. Decomposition, reranking and the outcome boost each made retrieval worse. These are
  negative results to explain in the report, not bugs to hide.
- V8 refuses 91% of the jobs that have no evidence and 0% of the jobs that have some, but it returns short lists, so
  Recall@5 drops. The sweep's best balance was min_score 0.6 (Recall@5 0.556, 98% refused, 1% refused wrongly).
- Decision taken from this run, now in `agent/config.yaml`: `rag.variant: v2_hybrid`, `best: [hybrid]`,
  `corrective.min_score: 0.6`. `all_steps` keeps the five-step pipeline so the final run still reports and ablates it.

## Part B: what is left, in order
1. Final Kaggle run of `evals/kaggle_eval.ipynb` (GPU T4 x2, Internet on): retrieval, ablation, decisions, proposals with
   GigSim replies. Download `gigbid_results.zip` and unzip it over the project.
2. Score the 30 proposals in `evals/datasets/judge_labels.csv` (rubric: `agent/prompts/judge.md`), then
   `uv run python -m evals.runners.judge_calibration`. Send `evals/datasets/pairwise_panel.csv` to classmates, then
   `uv run python -m evals.runners.judge_calibration --tally`.
3. Write the one-paragraph decision and R&D question B in the report, commit `evals/results/`.
- A stopped eval can be continued with `--resume` (finished variants, ablation lines and proposals are kept), but only
  while the files in `evals/results/` still exist. A new Kaggle session starts with an empty disk.
- Do NOT run the real embedding model on the 8 GB laptop: the first attempt ended in a blue screen.
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
- The LLM part of the evals (decisions, proposals, judge) has not been run on a real model yet.
- Reranker: first real run on Kaggle (CPU, 4 cores) with `ms-marco-MiniLM-L-12-v2` took more than 13 minutes for one
  reranking variant (about 12,600 query-item pairs) and was stopped. Switched to the 6-layer `ms-marco-MiniLM-L-6-v2` and
  600 characters per item. This was a speed decision, not a quality measurement; the two models were not compared.
- `rag.outcome_boost` (0.3) was never tuned. V4 scored below the baseline with it; a smaller value was not tried.
- In the outcome eval the script approves proposals in place of the human. It refuses to run unless the marketplace is GigSim.
- Ollama timeouts are 6x the hosted ones (`timeout_scale`); if Kaggle still times out, raise it in config.
- The change-request "platform policy update" file has not been received; `gigsim/seed/policy.json` is version 1.

## Rules we are keeping
- Real commit dates only, small commits per piece. Every number in README and report must come from `evals/results/`.
- No scraping, no browser automation of marketplaces, nothing sent without human approval.
