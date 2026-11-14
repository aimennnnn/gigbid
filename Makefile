dev:
	docker compose -f infra/docker-compose.yml up --build

test:
	uv run pytest -q

lint:
	uv run ruff check .

eval:
	@echo "added in the RAG step"

seed:
	uv run python -m data.synth.generate

snapshot:
	uv run python -m mcp_servers.describe

gigsim:
	uv run uvicorn gigsim.app:app --port 8081

demo:
	@echo "added in the web step"

.PHONY: dev test lint eval seed demo snapshot gigsim
