"""GigBid API (Part D).

    uv run uvicorn apps.api.main:app --port 8000            real model from .env
    GIGBID_LLM=fake GIGBID_RAG_MODELS=fake uv run uvicorn apps.api.main:app --port 8000     stand-ins, no key, no network

Single process: GigSim, the MCP servers and both graphs run inside this API (apps/api/runtime.py).
Interactive docs at /docs; the typed client in apps/web/src/lib/api is generated from /openapi.json.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv()

from agent.marketplace_port import MarketplaceRejected, MarketplaceUnavailable  # noqa: E402
from agent.settings import get_settings  # noqa: E402
from apps.api.routers import analytics, approvals, auth, jobs, messages, proposals, runs  # noqa: E402

if get_settings()["autonomy"]["auto_send"]:
    raise SystemExit("autonomy.auto_send must stay false: GigBid never sends without a human approval")

app = FastAPI(title="GigBid API", version="0.1.0",
              description="Freelancer copilot: job inbox, grounded proposals, approvals that resume the agent graph.")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("GIGBID_WEB_ORIGIN", "http://localhost:3000,http://127.0.0.1:3000").split(","),
                   allow_methods=["*"], allow_headers=["*"])
for r in (auth, jobs, proposals, approvals, messages, runs, analytics):
    app.include_router(r.router, prefix="/api")


@app.exception_handler(MarketplaceUnavailable)
async def marketplace_down(request: Request, exc: MarketplaceUnavailable) -> JSONResponse:
    """Degraded mode: the UI shows a banner and keeps everything that does not need the marketplace."""
    return JSONResponse({"detail": "marketplace unavailable", "degraded": True}, status_code=503)


@app.exception_handler(MarketplaceRejected)
async def marketplace_said_no(request: Request, exc: MarketplaceRejected) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=404 if str(exc).startswith("404") else 400)
