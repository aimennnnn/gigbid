"""Risk Assessor: rules first (agent/guards.py), then the model. The model can raise the
risk the rules found, but it can never lower it or drop a flag."""
from agent.guards import scan_job
from agent.handoffs import RiskReport
from agent.llm import ask
from agent.nodes.base import Deps, ids


async def run(deps: Deps, state: dict, config: dict) -> dict:
    job = state["job"]
    client = await deps.toolbox.call("risk", "marketplace", "get_client_history", {"client_id": job["client_id"]}, **ids(state, config))
    found = scan_job(job["title"] + "\n" + job["description"], client)
    report, tokens = await ask("risk", {"job_post": job, "client_history": client, "rule_findings": found},
                               RiskReport, untrusted=("job_post",))
    report.job_id = state["job_id"]
    report.flags = sorted(set(report.flags) | set(found["flags"]))
    floor = 0.8 if {"scam", "free_work", "off_platform"} & set(found["flags"]) else 0.0
    report.risk_score = max(report.risk_score, floor)
    report.injected_text = found["injected_text"] or report.injected_text
    return {"risk": report, "tokens_used": tokens}
