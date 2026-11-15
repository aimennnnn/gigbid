dev:
	docker compose -f infra/docker-compose.yml up --build

test:
	uv run pytest -q

lint:
	uv run ruff check .

# every evaluation, then the results table; needs the models in .env (see docs/STATUS.md)
eval:
	uv run python -m evals.runners.run_all

# retrieval and ablation only: no LLM, a few minutes on a laptop
eval-rag:
	uv run python -m evals.runners.run_all --only rag

# decisions and proposals only: needs an LLM (Groq, or Ollama on Kaggle)
eval-agent:
	uv run python -m evals.runners.run_all --only agent

# 30 jobs with stand-in models, no network: what CI runs
eval-smoke:
	uv run python -m evals.runners.run_all --smoke

# what CI checks after the smoke eval: fails if a threshold in agent/config.yaml (eval_gates) is missed
gate:
	uv run python -m evals.runners.gate --smoke
	uv run python -m evals.runners.gate

# try values of rag.corrective.min_score for V8
tune:
	uv run python -m evals.runners.rag_eval --sweep

# the web app: API on :8000 (real model from .env), web on :3000. Run each in its own terminal.
api:
	uv run uvicorn apps.api.main:app --port 8000

# the same API with stand-in models: no key, no network, nothing heavy on the laptop
api-demo:
	GIGBID_LLM=fake GIGBID_RAG_MODELS=fake uv run uvicorn apps.api.main:app --port 8000

web:
	cd apps/web && npm install && npm run dev

# rebuild the typed client after changing the API
client:
	uv run python -m apps.api.openapi
	cd apps/web && npm run gen:api

e2e:
	cd apps/web && npm run build && npx playwright test

seed:
	uv run python -m data.synth.generate

snapshot:
	uv run python -m mcp_servers.describe

gigsim:
	uv run uvicorn gigsim.app:app --port 8081

demo:
	uv run python -m agent.demo

.PHONY: dev test lint eval eval-rag eval-agent eval-smoke gate tune api api-demo web client e2e seed demo snapshot gigsim
