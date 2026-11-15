"""The human gate. Approving, editing or rejecting resumes the interrupted graph thread.
Works for both graphs: a proposal (bid graph) and a reply to a client (conversation graph)."""
from fastapi import APIRouter, Depends, HTTPException

from apps.api.deps import my_run
from apps.api.runtime import Run, Runtime, runtime
from apps.api.schemas.models import ApprovalIn, Started

router = APIRouter(tags=["approvals"])


@router.post("/approvals/{thread_id}", response_model=Started)
async def decide(body: ApprovalIn, run: Run = Depends(my_run), rt: Runtime = Depends(runtime)) -> Started:
    if run.running or not (await rt.state(run))["pending"]:
        raise HTTPException(409, "nothing is waiting for approval on this run")
    if body.action == "edit" and not (body.text or "").strip():
        raise HTTPException(422, "an edit needs the edited text")
    if body.action == "reject" and not (body.reason or "").strip():
        raise HTTPException(422, "say why you are rejecting it")
    rt.resume(run, body.model_dump(exclude_none=True))
    return Started(thread_id=run.thread_id, running=True)
