"""Job inbox and job detail. Analysing a job starts a bid-graph run in the background."""
from fastapi import APIRouter, Body, Depends, HTTPException

from apps.api.auth.users import current_user, onboarded
from apps.api.runtime import Runtime, runtime
from apps.api.schemas.models import Inbox, InboxJob, JobDetail, Started

router = APIRouter(tags=["jobs"])
ORDER = {"analysed": 0, "analysing": 1, "new": 2, "skipped_by_you": 3}


async def inbox_row(rt: Runtime, user: str, job: dict) -> InboxJob:
    row = InboxJob(job_id=job["job_id"], title=job["title"], category=job["category"], posted_at=job.get("posted_at"),
                   budget_min=job.get("budget", {}).get("min"), budget_max=job.get("budget", {}).get("max"),
                   connects_cost=job.get("connects_cost"), state="new")
    run = rt.mine(user, f"{user}:{job['job_id']}")
    if job["job_id"] in rt.skipped.get(user, {}):
        row.state, row.reasons = "skipped_by_you", [rt.skipped[user][job["job_id"]]]
    if run:
        v = (await rt.state(run))["values"]
        row.thread_id, row.status = run.thread_id, v.get("status")
        row.state = "skipped_by_you" if row.state == "skipped_by_you" else "analysing" if run.running and not v.get("decision") else "analysed"
        if v.get("fit"):
            row.fit = v["fit"]["fit_score"]
        if v.get("risk"):
            row.risk, row.risk_flags = v["risk"]["risk_score"], v["risk"]["flags"]
        if v.get("decision"):
            row.action, row.reasons = v["decision"]["action"], v["decision"]["reasons"]
        if v.get("price"):
            row.price, row.connects_cost = v["price"]["amount"], v["price"]["connects_cost"]
        if v.get("errors") and not v.get("decision"):
            row.reasons = v["errors"]
    return row


async def visible_jobs(rt: Runtime, user: str, q: str, category: str | None) -> list[dict]:
    profile = onboarded(user)
    jobs = await rt.port_for(user).search_jobs(q, category, limit=50)
    wanted = profile["categories"] if not category else [category]
    return [j for j in jobs if not j["job_id"].startswith("dev-") and (not wanted or j["category"] in wanted)]   # dev jobs are the eval set


@router.get("/jobs", response_model=Inbox)
async def inbox(q: str = "", category: str | None = None, user: str = Depends(current_user), rt: Runtime = Depends(runtime)) -> Inbox:
    rows = [await inbox_row(rt, user, j) for j in await visible_jobs(rt, user, q, category)]
    rows.sort(key=lambda r: (ORDER[r.state], {"bid": 0, "watch": 1, "skip": 2, None: 1}[r.action], -(r.fit or 0)))
    return Inbox(jobs=rows, total=len(rows))


@router.post("/jobs/analyse-new", response_model=list[Started])
async def analyse_new(limit: int = 5, user: str = Depends(current_user), rt: Runtime = Depends(runtime)) -> list[Started]:
    """Start a run for the newest jobs that have none yet (at most `limit`, at most 10)."""
    profile, started = onboarded(user), []
    for job in await visible_jobs(rt, user, "", None):
        if len(started) >= min(limit, 10):
            break
        if not rt.mine(user, f"{user}:{job['job_id']}") and job["job_id"] not in rt.skipped.get(user, {}):
            run = rt.start_bid(user, job["job_id"], profile)
            started.append(Started(thread_id=run.thread_id, running=run.running))
    return started


@router.post("/jobs/{job_id}/analyse", response_model=Started)
async def analyse(job_id: str, user: str = Depends(current_user), rt: Runtime = Depends(runtime)) -> Started:
    await rt.port_for(user).get_job(job_id)                 # 404 from the marketplace if it does not exist
    run = rt.start_bid(user, job_id, onboarded(user))
    return Started(thread_id=run.thread_id, running=run.running)


@router.post("/jobs/{job_id}/skip", status_code=204)
def skip(job_id: str, reason: str = Body(default="skipped by you", embed=True), user: str = Depends(current_user),
         rt: Runtime = Depends(runtime)) -> None:
    rt.skipped.setdefault(user, {})[job_id] = reason or "skipped by you"


@router.get("/jobs/{job_id}", response_model=JobDetail)
async def detail(job_id: str, user: str = Depends(current_user), rt: Runtime = Depends(runtime)) -> JobDetail:
    run = rt.mine(user, f"{user}:{job_id}")
    if not run:
        return JobDetail(job=await rt.port_for(user).get_job(job_id))
    v = (await rt.state(run))["values"]
    if not v.get("job"):
        v["job"] = await rt.port_for(user).get_job(job_id)
    if v["job"].get("job_id") != job_id:
        raise HTTPException(404, "no such job")
    return JobDetail(job=v["job"], thread_id=run.thread_id, running=run.running, status=v.get("status"), job_spec=v.get("job_spec"),
                     risk=v.get("risk"), fit=v.get("fit"), evidence=v.get("evidence", []), price=v.get("price"),
                     decision=v.get("decision"), errors=v.get("errors", []))
