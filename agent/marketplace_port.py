"""The one marketplace port (R1).

Every agent talks to "the marketplace" through this interface only.
Two adapters implement it: GigSim (mcp_servers/marketplace/adapters/gigsim.py)
and live Upwork (adapters/upwork_live.py). Config picks one, so the graph
cannot tell which marketplace it is using.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


class MarketplaceUnavailable(Exception):
    """The marketplace did not answer after all retries. Callers switch to degraded mode."""


class MarketplaceRejected(Exception):
    """The marketplace answered and said no (not found, not enough Connects, bad input)."""


@runtime_checkable
class MarketplacePort(Protocol):
    # ---- read ----
    async def search_jobs(self, query: str, category: str | None = None, limit: int = 20) -> list[dict]: ...
    async def get_job(self, job_id: str) -> dict: ...
    async def get_client_history(self, client_id: str) -> dict: ...
    async def get_connects_balance(self) -> dict: ...
    async def list_messages(self, thread_id: str | None = None) -> list[dict]: ...
    async def get_market_stats(self, category: str, skills: list[str]) -> dict: ...
    async def list_events(self, since_id: int = 0) -> list[dict]: ...
    async def get_policy(self) -> dict: ...

    # ---- write: only ever called after a human approved in the UI ----
    async def create_proposal_draft(self, job_id: str, cover_letter: str, amount: float,
                                    screening_answers: dict[str, str], idempotency_key: str) -> dict: ...
    async def submit_proposal(self, draft_id: str, idempotency_key: str) -> dict: ...
    async def send_message(self, thread_id: str, text: str, idempotency_key: str) -> dict: ...


READ_TOOLS = ["search_jobs", "get_job", "get_client_history", "get_connects_balance",
              "list_messages", "get_market_stats", "list_events", "get_policy"]
WRITE_TOOLS = ["create_proposal_draft", "submit_proposal", "send_message"]
