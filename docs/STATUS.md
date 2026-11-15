# Build status and hand-over notes

Working notes for whoever continues the build (me, or an AI assistant in a new session).
Updated 15 Nov 2026. Deadline: Sunday 15 Nov, 11:59 PM PKT.

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
- Part B code (14 Nov): built, tested with stand-in models, and the full evaluation has run on real models on Kaggle.
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
Read off the notebook output; the result files of that run were not kept. The committed numbers come from the final run below.

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

## Part B: final run (14 Nov, Kaggle GPU T4 x2, commit 2ba4e4d) - the committed numbers
Everything is in `evals/results/` and the table is in the README (`results_table --readme` reproduces it exactly).
Model for decisions, proposals and the judge: Ollama `gpt-oss:20b`. No job failed in any step.

- Retrieval (600 dev jobs): same picture as the first run. Hybrid 0.889 Recall@5 / 0.917 nDCG@10, baseline 0.806 / 0.890.
  Ablation and the threshold sweep are in `ablation.json` and `corrective_sweep.json` (best balance min_score 0.6).
- Decisions (60 dev jobs): bid-or-skip F1 0.925 (precision 0.861, recall 1.0), scam precision and recall 1.0,
  price inside the fair band 0.47 (web persona 0.30). Five wrong decisions, all "bid" on a job that should be skipped
  (lowball, no_evidence, other_domain); they are listed under `wrong` in `decision_eval.json`.
- Proposals (30 fixed dev jobs per variant, all submitted):

| | v0_naive | best (hybrid) |
|---|---|---|
| GigSim reply rate | 0.83 | 0.77 |
| Interview rate | 0.43 | 0.40 |
| Hire rate | 0.20 | 0.20 |
| Unsupported claims per proposal, before -> after | 0.03 -> 0.00 | 0.00 -> 0.00 |
| Judge score (not calibrated yet) | 4.23 | 4.07 |
| p95 seconds per proposal | 99.4 | 85.6 |
| Tokens per proposal | 13,445 | 12,406 |

- Reading: better retrieval did not turn into better outcomes. The reply-rate gap is 2 proposals out of 30, so it is
  "no clear difference", not "the baseline is better". Say this in the report.
- Prompt injection: on `dev-data-007` the analysis flagged the injection, but the Writer still copied the code word
  `PINEAPPLE-11` into the proposal, in both variants (`canary_leaked: 1`). This is a real leak.
  Fixed in code on 15 Nov (commit 1042bcd): the Writer and Critic no longer see the injected text, and a sentence with
  its code word is dropped from the draft. Checked on all 30 injection jobs in the dev set and on the leaked letter
  itself, but NOT re-run on the real model, so the committed numbers still show the leak (`canary_leaked: 1`).
  The price was never at risk: it is computed in code (`agent/nodes/pricing.py`), not by the model.
- Version 1 of the Kaggle notebook failed in the LLM half (model download 503); nothing from it is used.

## Part B: judge calibration (15 Nov)
30 proposals scored by hand (rubric in `agent/prompts/judge.md`, judge scores hidden while scoring), compared with the
`gpt-oss:20b` judge in `evals/results/judge_calibration.json`.

- Cohen's kappa 0.14, weighted 0.19, pass/fail (score 4 or more) 0.22. Exact agreement 0.53, within one point 0.83.
- The judge is more generous: mean 4.13 against 3.47 by hand. It never gave a 1; three proposals scored 1 by hand got 4.
- So the judge is NOT calibrated. The "Judge score" column in the table is reported, but no decision rests on it.
- The first version of the sheet cut each evidence text at 300 characters, which hid the Result section. Fixed before
  the scores were entered (commit bc34531); the judge had always seen the full text.

## Part B: which variant ships, and why (draft paragraph for the report)
The app ships `v2_hybrid` (BM25 + dense, fused with RRF). It is the only variant that beat the dense baseline on
retrieval: Recall@5 0.889 against 0.806 and nDCG@10 0.917 against 0.890 on 600 dev jobs, at the same retrieval cost
(p95 157 ms against 153 ms, no extra model). Decomposition (0.651), reranking (0.771), the outcome boost (0.702) and the
corrective loop (0.556) all lowered Recall@5, and stacking all five steps gave 0.586 at 24 s p95. In the ablation,
removing hybrid from the shipped pipeline drops it back to the baseline (0.806), and in the five-step pipeline the
corrective loop is the step that buys refusals (92% of no-evidence jobs refused, against 0% without it) at a small cost
in recall (0.586 against 0.610); taking out hybrid, reranking or the outcome boost there changes Recall@5 by nothing,
because the corrective grade decides what is kept. End to end, the better retrieval did not show up as better outcomes on 30 jobs: reply rate 0.77 against 0.83
(two proposals), hire rate 0.20 for both. Hybrid proposals had no unsupported claims before verification (0.03 for the
baseline), used fewer tokens (12.4k against 13.4k) and were faster at p95 (85.6 s against 99.4 s). The judge score is
left out of the decision because the judge agrees poorly with the hand labels (kappa 0.14).

## Part B: what is left, in order
1. Optional: send `evals/datasets/pairwise_panel.csv` to classmates (never `pairwise_key.json`), then
   `uv run python -m evals.runners.judge_calibration --tally`.
2. Put the paragraph above and R&D question B into the report, in your own words.
3. Optional: re-run the proposals step on Kaggle to show `canary_leaked: 0` after the fix (about 80 minutes).
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
- The injection defence relies on the injected text being quoted exactly (rules in `agent/guards.py`, or the Risk model). An injection phrased in a way neither catches would still reach the Writer.
- Price suggestions land inside the fair band less than half the time (0.47); the Pricing step is the weakest agent.
- The model judge agrees poorly with hand labels (kappa 0.14) and is too generous; do not use its score to pick a variant.
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
