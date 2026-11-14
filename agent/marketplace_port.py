"""The one marketplace port (R1).

Every agent talks to "the marketplace" through this interface only.
Two adapters implement it: GigSim (mcp_servers/marketplace/adapters/gigsim.py)
and live Upwork (adapters/upwork_live.py). Config picks one, so the graph
cannot tell which marketplace it is using.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MarketplacePort(Protocol):
    # ---- read ----
    async def search_jobs(self, query: str, filters: dict[str, Any] | None = None,
                          limit: int = 20) -> list[dict]: ...
    async def get_job(self, job_id: str) -> dict: ...
    async def get_client_history(self, client_id: str) -> dict: ...
    async def get_connects_balance(self) -> int: ...
    async def list_messages(self, thread_id: str | None = None) -> list[dict]: ...

    # ---- write: only ever called after a human approved in the UI ----
    async def create_proposal_draft(self, job_id: str, cover_letter: str, amount: float,
                                    screening_answers: dict[str, str],
                                    idempotency_key: str, dry_run: bool = False) -> dict: ...
    async def submit_proposal(self, draft_id: str, idempotency_key: str,
                              dry_run: bool = False) -> dict: ...
    async def send_message(self, thread_id: str, text: str,
                           idempotency_key: str, dry_run: bool = False) -> dict: ...


READ_TOOLS = ["search_jobs", "get_job", "get_client_history", "get_connects_balance", "list_messages"]
WRITE_TOOLS = ["create_proposal_draft", "submit_proposal", "send_message"]
