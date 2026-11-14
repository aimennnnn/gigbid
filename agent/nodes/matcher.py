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
                                    {"requirement": req[:500], "k": 3, "persona": state["persona"],
                                     "filters": {"types": ["case", "repo", "review"]}}, **ids(state, config))
        rows.append({"requirement": req, "candidate_ids": [i["id"] for i in r["items"]]})
        evidence.update({i["id"]: i for i in r["items"]})
    # each evidence item is sent once, shortened: keeps the request small and cheap
    short = [{"id": e["id"], "type": e["type"], "title": e["title"], "skills": e["skills"], "text": e["text"][:650]} for e in evidence.values()]
    fit, tokens = await ask("matcher", {"job_id": state["job_id"], "requirements": rows, "evidence": short}, FitReport)
    fit.job_id = state["job_id"]
    for m in fit.matches:                               # drop any evidence id the model made up
        m.evidence_ids = [i for i in m.evidence_ids if i in evidence]
        if not m.evidence_ids and m.status == "supported":
            m.status = "unsupported"
    # the score is worked out here, not taken from the model, so the thresholds mean the same thing every run
    points = sum({"supported": 1.0, "partly": 0.5}.get(m.status, 0.0) for m in fit.matches)
    fit.fit_score = round(points / len(fit.matches), 2) if fit.matches else 0.0
    return {"fit": fit, "evidence": [EvidenceItem(**{k: v for k, v in e.items() if k in EvidenceItem.model_fields}) for e in evidence.values()],
            "tokens_used": tokens}
