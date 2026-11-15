"""Analytics, the memory viewer, health, and two dev-only switches used by the UI tests."""
import os
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException

import gigsim.app as gigsim
from agent.marketplace_port import MarketplaceUnavailable
from agent.memory.store import all_memories, forget
from apps.api.auth.users import current_user
from apps.api.deps import first_wait
from apps.api.runtime import Runtime, runtime
from apps.api.schemas.models import Analytics, CategoryStats, Health, Memories, Memory

router = APIRouter(tags=["analytics"])


def why(reason: str) -> str:
    """Group a decision's first reason into a few plain buckets."""
    r = reason.lower()
    return ("High risk or scam" if "risk" in r and "at or above" in r else "Budget below your floor" if "budget" in r
            else "Watching: medium fit" if "between watch" in r else "Not enough portfolio evidence" if "fit" in r else reason[:60])


@router.get("/analytics", response_model=Analytics)
async def analytics(user: str = Depends(current_user), rt: Runtime = Depends(runtime)) -> Analytics:
    events: dict[str, set[str]] = {}
    for e in await rt.sync_events(user):
        events.setdefault(e["job_id"], set()).add(e["type"])
    cats: dict[str, dict] = {}
    reasons: Counter = Counter(rt.skipped.get(user, {}).values())
    spent, tokens, seconds = 0, [], []
    for run in rt.runs.values():
        if run.user != user or run.kind != "bid":
            continue
        v = (await rt.state(run))["values"]
        if v.get("decision") and v["decision"]["action"] != "bid":
            reasons[why(v["decision"]["reasons"][0])] += 1
        if v.get("status") == "rejected":
            reasons["Rejected by you: " + (v.get("approval") or {}).get("reason", "no reason")[:60]] += 1
        if v.get("drafts"):
            tokens.append(v.get("tokens_used", 0))
            if first_wait(run) is not None:
                seconds.append(first_wait(run))
        if v.get("status") == "submitted":
            c = cats.setdefault(v["job"]["category"], {"submitted": 0, "replied": 0, "hired": 0})
            c["submitted"] += 1
            c["replied"] += "replied" in events.get(run.job_id, ())
            c["hired"] += "hired" in events.get(run.job_id, ())
            spent += (v.get("submission") or {}).get("connects_cost") or 0
    rows = [CategoryStats(category=k, **c, reply_rate=round(c["replied"] / c["submitted"], 3), hire_rate=round(c["hired"] / c["submitted"], 3))
            for k, c in sorted(cats.items())]
    return Analytics(by_category=rows, connects_spent=spent, proposals=sum(r.submitted for r in rows), replies=sum(r.replied for r in rows),
                     hires=sum(r.hired for r in rows), tokens_per_proposal=round(sum(tokens) / len(tokens), 1) if tokens else None,
                     seconds_per_proposal=round(sum(seconds) / len(seconds), 1) if seconds else None,
                     top_rejection_reasons=reasons.most_common(6))


@router.get("/memory", response_model=Memories)
async def memory(user: str = Depends(current_user), rt: Runtime = Depends(runtime)) -> Memories:
    """Everything GigBid has learned about this user: style rules from their edits, and outcome counts."""
    items = []
    for m in await all_memories(rt.deps.store, user):
        text = (f"Style rule: {m['rule']} (seen in {m['seen']} of your edits)" if m["kind"] == "style" else
                f"{m['category']}: {m['submitted']} submitted, {m['replied']} replied, {m['hired']} hired")
        items.append(Memory(kind=m["kind"], key=m["key"], text=text))
    return Memories(items=items)


@router.delete("/memory/{kind}/{key}", status_code=204)
async def delete_memory(kind: str, key: str, user: str = Depends(current_user), rt: Runtime = Depends(runtime)) -> None:
    if kind not in ("style", "outcome"):
        raise HTTPException(404, "no such memory")
    await forget(rt.deps.store, user, kind, key)


@router.get("/health", response_model=Health)
async def health(user: str = Depends(current_user), rt: Runtime = Depends(runtime)) -> Health:
    try:
        await rt.port_for(user).get_connects_balance()
        market = "ok"
    except MarketplaceUnavailable:
        market = "unavailable"
    llm = "stand-in rules (GIGBID_LLM=fake)" if os.getenv("GIGBID_LLM", "").lower() == "fake" else "real model from .env"
    return Health(ok=market == "ok", marketplace=market, degraded=rt.deps.toolbox.degraded, llm=llm)


def dev_only() -> None:
    if os.getenv("GIGBID_DEV", "1") != "1":
        raise HTTPException(404, "not found")


@router.post("/dev/marketplace", dependencies=[Depends(dev_only)], include_in_schema=False)
def marketplace_switch(down: bool) -> dict:
    """Make GigSim answer 503 to everything (or stop doing so), to show degraded mode."""
    os.environ["GIGSIM_ERROR_RATE"] = "1" if down else "0"
    return {"down": down}


@router.post("/dev/release", dependencies=[Depends(dev_only)], include_in_schema=False)
def release(n: int = 5) -> dict:
    """Publish the next n jobs of GigSim's live stream now, instead of waiting for its clock."""
    return gigsim.release(n)
