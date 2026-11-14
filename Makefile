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

# try values of rag.corrective.min_score for V8
tune:
	uv run python -m evals.runners.rag_eval --sweep

seed:
	uv run python -m data.synth.generate

snapshot:
	uv run python -m mcp_servers.describe

gigsim:
	uv run uvicorn gigsim.app:app --port 8081

demo:
	uv run python -m agent.demo

.PHONY: dev test lint eval eval-rag eval-agent eval-smoke tune seed demo snapshot gigsim
