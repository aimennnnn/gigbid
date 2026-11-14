"""GigSim adapter: implements the marketplace port over GigSim's REST API.

Handles the boring-but-important parts once, for every tool: timeouts, bounded
retries with backoff, GigSim's rate limit (429) and its occasional 5xx errors.
"""
from __future__ import annotations

import asyncio
import os

import httpx

from agent.marketplace_port import MarketplaceRejected, MarketplaceUnavailable


class GigSimAdapter:
    def __init__(self, base_url: str | None = None, token: str | None = None, *,
                 transport: httpx.AsyncBaseTransport | None = None,
                 timeout: float = 10.0, retries: int = 3, backoff: float = 0.5):
        self.retries, self.backoff = retries, backoff
        self.http = httpx.AsyncClient(
            base_url=base_url or os.getenv("GIGSIM_URL", "http://localhost:8081"),
            headers={"Authorization": f"Bearer {token or os.getenv('GIGSIM_API_KEY', 'dev-token')}"},
            timeout=timeout, transport=transport)

    async def _call(self, method: str, path: str, *, idempotency_key: str | None = None, **kw):
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else {}
        last = "no attempt made"
        for attempt in range(self.retries + 1):
            try:
                r = await self.http.request(method, path, headers=headers, **kw)
            except httpx.HTTPError as e:                      # timeout, connection refused...
                last = f"{type(e).__name__}: {e}"
            else:
                if r.status_code < 400:
                    return r.json()
                if r.status_code == 429:                      # rate limited: wait as told, then retry
                    last = "rate limited (429)"
                    await asyncio.sleep(min(float(r.headers.get("Retry-After", "1")), 5.0))
                    continue
                if r.status_code < 500:                       # our mistake: retrying will not help
                    raise MarketplaceRejected(f"{r.status_code}: {r.json().get('detail', r.text)}")
                last = f"server error ({r.status_code})"
            if attempt < self.retries:
                await asyncio.sleep(self.backoff * 2 ** attempt)   # 0.5s, 1s, 2s
        raise MarketplaceUnavailable(f"GigSim unavailable after {self.retries + 1} attempts: {last}")

    # ---- read ----
    async def search_jobs(self, query: str, category: str | None = None, limit: int = 20) -> list[dict]:
        params = {"q": query, "limit": limit} | ({"category": category} if category else {})
        return (await self._call("GET", "/jobs", params=params))["jobs"]

    async def get_job(self, job_id: str) -> dict:
        return await self._call("GET", f"/jobs/{job_id}")

    async def get_client_history(self, client_id: str) -> dict:
        return await self._call("GET", f"/clients/{client_id}")

    async def get_connects_balance(self) -> dict:
        return await self._call("GET", "/connects")

    async def list_messages(self, thread_id: str | None = None) -> list[dict]:
        return await self._call("GET", "/messages", params={"thread_id": thread_id} if thread_id else {})

    async def get_market_stats(self, category: str, skills: list[str]) -> dict:
        return await self._call("GET", "/market/stats", params={"category": category, "skills": ",".join(skills)})

    async def list_events(self, since_id: int = 0) -> list[dict]:
        return await self._call("GET", "/events", params={"since_id": since_id})

    async def get_policy(self) -> dict:
        return await self._call("GET", "/policy")

    # ---- write (the idempotency key goes to GigSim too, so a retry never double-spends) ----
    async def create_proposal_draft(self, job_id: str, cover_letter: str, amount: float,
                                    screening_answers: dict[str, str], idempotency_key: str) -> dict:
        body = {"job_id": job_id, "cover_letter": cover_letter, "amount": amount, "screening_answers": screening_answers}
        return await self._call("POST", "/proposals", json=body, idempotency_key=idempotency_key)

    async def submit_proposal(self, draft_id: str, idempotency_key: str) -> dict:
        return await self._call("POST", f"/proposals/{draft_id}/submit", idempotency_key=idempotency_key)

    async def send_message(self, thread_id: str, text: str, idempotency_key: str) -> dict:
        return await self._call("POST", "/messages", json={"thread_id": thread_id, "text": text},
                                idempotency_key=idempotency_key)
