"""Client threads. A suggested reply is a conversation-graph run that pauses for approval before sending."""
from fastapi import APIRouter, Depends, HTTPException

from apps.api.auth.users import current_user, onboarded
from apps.api.runtime import Runtime, runtime
from apps.api.schemas.models import ChatMessage, Conversation, Conversations, Started, Suggested

router = APIRouter(tags=["messages"])


async def threads_of(rt: Runtime, user: str) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for m in await rt.port_for(user).list_messages():
        grouped.setdefault(m["thread_id"], []).append(m)
    return grouped


async def job_of(rt: Runtime, user: str, marketplace_thread: str) -> tuple[str, str]:
    """The job a marketplace thread belongs to: threads are named t-<proposal id>."""
    for run in rt.runs.values():
        if run.user == user and run.kind == "bid":
            v = (await rt.state(run))["values"]
            if (v.get("submission") or {}).get("proposal_id") == marketplace_thread.removeprefix("t-"):
                return run.job_id, v["job"]["title"]
    return "", marketplace_thread


@router.get("/messages", response_model=Conversations)
async def conversations(user: str = Depends(current_user), rt: Runtime = Depends(runtime)) -> Conversations:
    out = []
    for thread, msgs in (await threads_of(rt, user)).items():
        job_id, title = await job_of(rt, user, thread)
        suggested, run = None, rt.mine(user, f"{user}:talk:{thread}:{len(msgs)}")
        if run:
            s = await rt.state(run)
            v, p = s["values"], s["pending"] or {}
            suggested = Suggested(thread_id=run.thread_id, running=run.running, pending=bool(p), status=v.get("status"),
                                  intent=p.get("intent") or v.get("intent"),
                                  draft=p.get("draft") or (v.get("compliance") or {}).get("cleaned_text"),
                                  interview_slots=p.get("interview_slots") or [], compliance=p.get("compliance") or v.get("compliance"),
                                  errors=v.get("errors", []))
        out.append(Conversation(thread_id=thread, job_id=job_id, title=title, needs_reply=msgs[-1]["sender"] == "client",
                                messages=[ChatMessage(sender=m["sender"], text=m["text"], created=m.get("created")) for m in msgs],
                                suggested=suggested))
    return Conversations(threads=sorted(out, key=lambda c: not c.needs_reply))


@router.post("/messages/{thread_id}/suggest", response_model=Started)
async def suggest(thread_id: str, user: str = Depends(current_user), rt: Runtime = Depends(runtime)) -> Started:
    msgs = (await threads_of(rt, user)).get(thread_id)
    if not msgs:
        raise HTTPException(404, "no such thread")
    job_id, _ = await job_of(rt, user, thread_id)
    run = rt.start_talk(user, thread_id, len(msgs), job_id, onboarded(user))
    return Started(thread_id=run.thread_id, running=run.running)
