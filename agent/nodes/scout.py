"""Scout: runs saved searches, drops duplicates, and hands each new job to the bid graph."""
from __future__ import annotations

import hashlib
import re

from agent.nodes.base import Deps, ids


def fingerprint(job: dict) -> str:
    """Same client problem reposted with small edits -> same fingerprint."""
    text = re.sub(r"\(urgent\)|reposting, still open\.?", "", (job["title"] + " " + job["description"]).lower())
    return hashlib.sha256(" ".join(re.findall(r"[a-z0-9]+", text)[:60]).encode()).hexdigest()[:16]


async def find_new_jobs(deps: Deps, user: str, searches: list[dict], seen: set[str], trace_id: str = "") -> list[dict]:
    """seen holds job ids and fingerprints already queued. Returns only genuinely new jobs."""
    new = []
    for s in searches:
        r = await deps.toolbox.call("scout", "marketplace", "search_jobs",
                                    {"query": s["query"], "category": s.get("category"), "limit": s.get("limit", 20)},
                                    user=user, trace_id=trace_id)
        for job in r["jobs"]:
            fp = fingerprint(job)
            if job["job_id"] not in seen and fp not in seen:
                seen.update({job["job_id"], fp})
                new.append(job)
    return new


async def load_job(deps: Deps, state: dict, config: dict) -> dict:
    """First node of the bid graph: make sure the full job post is in state."""
    if state.get("job"):
        return {"status": "analysing"}
    job = await deps.toolbox.call("scout", "marketplace", "get_job", {"job_id": state["job_id"]}, **ids(state, config))
    return {"job": job, "status": "analysing"}
