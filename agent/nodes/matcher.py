"""Fit Matcher: every requirement -> portfolio evidence -> fit score with reasons."""
from agent.guards import sentences
from agent.handoffs import EvidenceItem, FitReport
from agent.llm import ask
from agent.nodes.base import Deps, ids


def requirements_of(job: dict) -> list[str]:
    """Runs in parallel with the Analyst, so it reads requirements straight from the post."""
    if job.get("skills"):
        return [f"Experience with {s}" for s in job["skills"]] + [job["title"]]
    return [job["title"]] + [s for s in sentences(job["description"]) if "want" in s.lower()][:2]


async def run(deps: Deps, state: dict, config: dict) -> dict:
    job, rows, evidence = state["job"], [], {}
    for req in requirements_of(job):
        r = await deps.toolbox.call("matcher", "portfolio", "search_evidence",
                                    {"requirement": req[:500], "k": 4, "persona": state["persona"],
                                     "filters": {"types": ["case", "repo", "review"]}}, **ids(state, config))
        rows.append({"requirement": req, "evidence": r["items"]})
        evidence.update({i["id"]: i for i in r["items"]})
    fit, tokens = await ask("matcher", {"job_id": state["job_id"], "requirements": rows}, FitReport)
    fit.job_id = state["job_id"]
    for m in fit.matches:                               # drop any evidence id the model made up
        m.evidence_ids = [i for i in m.evidence_ids if i in evidence]
        if not m.evidence_ids and m.status == "supported":
            m.status = "unsupported"
    return {"fit": fit, "evidence": [EvidenceItem(**{k: v for k, v in e.items() if k in EvidenceItem.model_fields}) for e in evidence.values()],
            "tokens_used": tokens}
