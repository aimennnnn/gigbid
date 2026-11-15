"""Proposal studio (one proposal waiting for approval, or already decided) and the pipeline board."""
from fastapi import APIRouter, Depends

from apps.api.auth.users import current_user
from apps.api.deps import my_run
from apps.api.runtime import STAGES, Run, Runtime, runtime
from apps.api.schemas.models import Card, Pipeline, Studio

router = APIRouter(tags=["proposals"])


@router.get("/proposals/{thread_id}", response_model=Studio)
async def studio(run: Run = Depends(my_run), rt: Runtime = Depends(runtime)) -> Studio:
    s = await rt.state(run)
    v, p = s["values"], s["pending"] or {}
    draft = v["drafts"][-1] if v.get("drafts") else {}
    return Studio(
        thread_id=run.thread_id, job_id=run.job_id, job_title=v.get("job", {}).get("title", run.job_id), running=run.running,
        status=v.get("status"), pending=bool(p),
        draft=p.get("draft") or (v.get("compliance") or {}).get("cleaned_text") or draft.get("cover_letter"),
        screening_answers=p.get("screening_answers") or draft.get("screening_answers", {}),
        claims=p.get("claims") or draft.get("claims", []),
        evidence=p.get("evidence") or {e["id"]: e for e in v.get("evidence", [])},
        removed_claims=p.get("removed_claims") or v.get("removed_claims", []), risk=p.get("risk") or v.get("risk"),
        price=p.get("price") or v.get("price"), critique=p.get("critique") or (v["critiques"][-1] if v.get("critiques") else None),
        compliance=p.get("compliance") or v.get("compliance"), dry_run=p.get("dry_run") or v.get("preview"),
        submission=v.get("submission"), outcome=v.get("outcome"), errors=v.get("errors", []))


@router.get("/pipeline", response_model=Pipeline)
async def pipeline(user: str = Depends(current_user), rt: Runtime = Depends(runtime)) -> Pipeline:
    """Kanban. A card's stage is the furthest marketplace event its proposal has reached."""
    events, cards = {}, []
    for e in await rt.sync_events(user):
        events.setdefault(e["job_id"], []).append(e["type"])
    for run in rt.runs.values():
        if run.user != user or run.kind != "bid":
            continue
        v = (await rt.state(run))["values"]
        if v.get("status") not in ("awaiting_approval", "submitted"):
            continue
        seen = events.get(run.job_id, [])
        stage = "drafted" if v["status"] == "awaiting_approval" else "lost" if "lost" in seen else max(
            ["submitted", *[s for s in seen if s in STAGES]], key=STAGES.index)
        cards.append(Card(thread_id=run.thread_id, job_id=run.job_id, title=v["job"]["title"], category=v["job"]["category"],
                          amount=(v.get("price") or {}).get("amount"), stage=stage, events=seen))
    return Pipeline(stages=STAGES, cards=cards)
