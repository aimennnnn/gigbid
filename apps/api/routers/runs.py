"""Agent run viewer: the steps of a run, live, and its trace (every MCP tool call, by trace id)."""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from apps.api.auth.users import current_user
from apps.api.deps import my_run
from apps.api.runtime import Run, Runtime, runtime
from apps.api.schemas.models import RunDetail, RunEvent, RunSummary, TraceLine
from apps.api.streaming import run_events

router = APIRouter(tags=["runs"])


@router.get("/runs", response_model=list[RunSummary])
def runs(user: str = Depends(current_user), rt: Runtime = Depends(runtime)) -> list[RunSummary]:
    mine = [r for r in rt.runs.values() if r.user == user]
    return [RunSummary(**r.summary()) for r in sorted(mine, key=lambda r: -r.started)]


@router.get("/runs/{thread_id}", response_model=RunDetail)
async def run_detail(run: Run = Depends(my_run), rt: Runtime = Depends(runtime)) -> RunDetail:
    v = (await rt.state(run))["values"]
    return RunDetail(run=RunSummary(**run.summary()), events=[RunEvent(**e) for e in run.events], trace_id=run.thread_id,
                     trace=[TraceLine(**t) for t in rt.trace(run)], status=v.get("status"), tokens=v.get("tokens_used", 0))


@router.get("/runs/{thread_id}/stream")
def stream(after: int = 0, run: Run = Depends(my_run)) -> StreamingResponse:
    """text/event-stream. Each `step` event is one finished graph node; the stream ends when the run stops or pauses."""
    return StreamingResponse(run_events(run, after), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
