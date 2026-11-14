dev:
	docker compose -f infra/docker-compose.yml up --build

test:
	uv run pytest -q

lint:
	uv run ruff check .

eval:
	@echo "added in the RAG step"

seed:
	@echo "added in the RAG step"

demo:
	@echo "added in the web step"

.PHONY: dev test lint eval seed demo
