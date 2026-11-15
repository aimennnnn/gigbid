# The API: FastAPI + GigSim + the MCP servers + both agent graphs, in one process.
# Build from the repo root:  docker build -f infra/docker/api.Dockerfile .
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy PYTHONUNBUFFERED=1
# dependencies first, so a code change does not reinstall them
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY agent agent
COPY apps/api apps/api
COPY apps/__init__.py apps/__init__.py
COPY data data
COPY gigsim gigsim
COPY mcp_servers mcp_servers
COPY rag rag
COPY conftest.py ./
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
