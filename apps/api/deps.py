"""Small helpers shared by the routers."""
from __future__ import annotations

from fastapi import Depends, HTTPException

from apps.api.auth.users import current_user
from apps.api.runtime import Run, Runtime, runtime


def my_run(thread_id: str, user: str = Depends(current_user), rt: Runtime = Depends(runtime)) -> Run:
    """The run with this thread id, only if it belongs to the signed-in user (tenant scoping)."""
    run = rt.mine(user, thread_id)
    if not run:
        raise HTTPException(404, "no such run")
    return run


def first_wait(run: Run) -> float | None:
    """Seconds from the start of the run to the approval screen."""
    return next((e["seconds"] for e in run.events if e.get("waiting")), None)
