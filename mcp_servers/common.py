"""Pieces every GigBid MCP server shares: who is calling, the audit log, the rate
limiter, idempotency, PII masking and bearer-token auth for the HTTP endpoint."""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Context
from starlette.responses import JSONResponse

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<![\w-])(?!\d{4}-\d{2}-\d{2})\+?\d[\d\s().-]{7,}\d(?![\w-])")   # a date such as 2026-11-16 14:00 is not a phone number
CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def mask_pii(value: Any) -> Any:
    """Replace emails, phone numbers and card numbers before anything is logged."""
    if isinstance(value, str):
        return PHONE.sub("[phone]", CARD.sub("[card]", EMAIL.sub("[email]", value)))
    if isinstance(value, dict):
        return {k: mask_pii(v) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_pii(v) for v in value]
    return value


def token_users() -> dict[str, str]:
    """MCP_TOKENS="token1:user1,token2:user2". One token per user."""
    return dict(p.split(":", 1) for p in os.getenv("MCP_TOKENS", "dev-mcp-token:reviewer").split(","))


def caller(ctx: Context | None) -> tuple[str, str]:
    """(user id, trace id) of the current call. The trace id comes in the MCP `_meta` field."""
    user, trace = "local", ""
    try:
        rc = ctx.request_context
        meta = rc.meta.model_dump() if rc.meta else {}
        trace = str(meta.get("trace_id") or "")
        user = str(meta.get("user_id") or user)
        if rc.request is not None:                       # HTTP transport: trust the token, not _meta
            token = rc.request.headers.get("authorization", "").removeprefix("Bearer ").strip()
            user = token_users().get(token, user)
            trace = trace or rc.request.headers.get("x-trace-id", "")
    except (AttributeError, LookupError, ValueError):
        pass
    return user, trace


class AuditLog:
    """Append-only JSON-lines file: one line per tool call, never edited or deleted."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, user: str, tool: str, arguments: dict, result: Any, trace_id: str) -> None:
        line = {"ts": round(time.time(), 3), "user": user, "tool": tool, "trace_id": trace_id,
                "arguments": mask_pii(arguments), "result": mask_pii(result)}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, default=str)[:4000] + "\n")


class RateLimiter:
    """Per-user sliding window. Waits politely for a free slot; gives up after max_wait seconds."""

    def __init__(self, per_minute: int, max_wait: float = 5.0):
        self.per_minute, self.max_wait = per_minute, max_wait
        self.calls: dict[str, list[float]] = {}

    async def acquire(self, user: str) -> None:
        waited = 0.0
        while True:
            now = time.monotonic()
            recent = [t for t in self.calls.get(user, []) if now - t < 60]
            if len(recent) < self.per_minute:
                self.calls[user] = recent + [now]
                return
            if waited >= self.max_wait:
                raise RuntimeError("rate_limited: too many marketplace calls this minute, try again shortly")
            await asyncio.sleep(0.25)
            waited += 0.25


class IdempotencyStore:
    """Remembers the result of every write by (user, tool, key), so a retry returns the
    saved result instead of doing the write again."""

    def __init__(self):
        self.done: dict[tuple[str, str, str], dict] = {}

    def get(self, user: str, tool: str, key: str) -> dict | None:
        return self.done.get((user, tool, key))

    def put(self, user: str, tool: str, key: str, result: dict) -> None:
        self.done[(user, tool, key)] = result


class BearerAuth:
    """ASGI wrapper: every HTTP request to the MCP endpoint needs a known bearer token."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path") != "/health":
            headers = dict(scope.get("headers") or [])
            token = headers.get(b"authorization", b"").decode().removeprefix("Bearer ").strip()
            if token not in token_users():
                await JSONResponse({"error": "unauthorized"}, status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)
