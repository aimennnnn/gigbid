# Runbook

How to run GigBid, check that it is healthy, and what to do when something breaks.

## Start it

Two terminals (PowerShell shown; the commands are the same on Linux without the `$env:` lines).

```powershell
# 1. API on http://localhost:8000  (stand-in models: no key, nothing heavy)
uv sync
$env:GIGBID_LLM="fake"; $env:GIGBID_RAG_MODELS="fake"; uv run uvicorn apps.api.main:app --port 8000

# 2. Web app on http://localhost:3000
cd apps/web
npm install
npm run dev
```

Sign in as `reviewer` / `reviewer`. For a real model, put `GROQ_API_KEY` in `.env` and start the API without
`GIGBID_LLM`. On a machine with 8 GB of memory also set `GIGBID_RAG_VARIANT=keyword`, so the embedding model is
not loaded.

With Docker (written, not yet run): `make dev`.

## Settings that matter

| Variable | Meaning |
|---|---|
| `GIGBID_LLM=fake` | Stand-in rules instead of a model (tests, CI, demos) |
| `GIGBID_RAG_MODELS=fake` | Stand-in embeddings and reranker (no download) |
| `GIGBID_RAG_VARIANT` | Override the retrieval variant from `agent/config.yaml` |
| `GIGBID_PROVIDER` | Force one model provider (`groq`, `ollama`, ...) |
| `OLLAMA_URL` | Address of a local model, e.g. `http://localhost:11434/v1` |
| `GIGBID_STATE_DIR` | Where the API keeps its state (default `data/processed/app`) |
| `GIGBID_PERSIST=0` | Keep API state in memory only |
| `GIGBID_WEB_ORIGIN` | Web origins the API accepts (CORS) |

Keys live in `.env`, which is git-ignored. Never commit it.

## Is it healthy?

- `GET http://localhost:8000/api/health` answers.
- The run viewer (`/runs`) shows each step of a run with its time and errors.
- `make test` (90+ tests), `make lint`, `make eval-smoke` then `make gate`.
- GitHub Actions runs all of that plus the web build and the browser tests on every push.

## When something goes wrong

| What you see | Likely cause | What to do |
|---|---|---|
| Web app shows a "marketplace unavailable" banner | The marketplace MCP server or GigSim is not answering | Runs wait; nothing is lost. Restart the API. Parked jobs can be analysed again from the inbox |
| A run ends with `dead_letter` | A critical node failed (model down, tool rejected) | Open the run in the run viewer, read the error on the failed step, fix the cause, analyse the job again |
| `no model provider is configured` | No key in `.env` and no `OLLAMA_URL` | Add a key, or start with `GIGBID_LLM=fake` |
| `rate limited` in a run | Groq free tier: 8,000 tokens per minute per model | It waits and retries by itself. For evals use Ollama on a GPU, or a smaller sample |
| A proposal was approved but I am not sure it was sent | A retry after a timeout | Safe to approve again: the idempotency key makes the marketplace return the first result |
| API restarted while a draft was waiting | Deploy, crash | Nothing to do: the draft is still waiting (state is on disk). Covered by `test_a_pending_approval_survives_an_api_restart` |
| State looks wrong after experiments | Old files in the state folder | Stop the API, delete `data/processed/app/`, start again (this resets GigSim and all accounts) |
| Laptop freezes when the API starts with real models | The embedding model does not fit in 8 GB | Use `GIGBID_RAG_MODELS=fake` or `GIGBID_RAG_VARIANT=keyword` |
| CI fails at "Gate" | A result is worse than its threshold in `eval_gates` | Read the gate's output: it names the number and the threshold. Fix the cause; do not lower the threshold to pass |

## Stopping an agent from sending

It cannot send by itself. Both graphs stop at `approval`, and the API refuses to start if `autonomy.auto_send`
is true. To stop everything, stop the API: pending drafts stay pending.

## Evaluations

`make eval-rag` (retrieval, no LLM), `make eval-agent` (needs a model), `make eval` (all). Real-model runs were
done on Kaggle (2 x T4, `gpt-oss:20b` on Ollama) with the notebooks in `evals/`. Every number in the report comes
from a file in `evals/results/`; each file records the commit, model and machine it came from.

## Logs

MCP audit logs are JSON lines, one per tool call, with a trace id that is the same across all three servers.
In the API they are under `data/processed/app/audit/`. Emails, phone numbers and card numbers are masked.
