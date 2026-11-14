"""Fit Matcher: every requirement -> portfolio evidence -> fit score with reasons."""
from agent.handoffs import EvidenceItem, FitReport
from agent.llm import ask
from agent.nodes.base import Deps, ids
from agent.settings import get_settings
from rag import retriever
from rag.variants.v1_decompose import requirements


async def run(deps: Deps, state: dict, config: dict) -> dict:
    job, found, evidence = state["job"], {}, {}
    # Runs in parallel with the Analyst, so requirements are read straight from the post.
    # The RAG variant in config decides the queries: one per requirement, or the whole post.
    asked = retriever.queries(job)
    for q in asked:
        r = await deps.toolbox.call("matcher", "portfolio", "search_evidence",
                                    {"requirement": q, "k": 3 if len(asked) > 1 else 5, "persona": state["persona"],
                                     "filters": {"types": get_settings()["rag"]["evidence_types"]}}, **ids(state, config))
        found[q] = [i["id"] for i in r["items"]]
        evidence.update({i["id"]: i for i in r["items"]})
    # a requirement that had its own search keeps its own candidates; otherwise it shares everything found
    rows = [{"requirement": req, "candidate_ids": found.get(req, list(evidence))} for req in requirements(job)]
    # each evidence item is sent once, shortened: keeps the request small and cheap
    short = [{"id": e["id"], "type": e["type"], "title": e["title"], "skills": e["skills"], "text": e["text"][:650]} for e in evidence.values()]
    fit, tokens = await ask("matcher", {"job_id": state["job_id"], "requirements": rows, "evidence": short}, FitReport)
    fit.job_id = state["job_id"]
    for m in fit.matches:                               # drop any evidence id the model made up
        m.evidence_ids = [i for i in m.evidence_ids if i in evidence]
        if not m.evidence_ids and m.status == "supported":
            m.status = "unsupported"
    # rule on top of the model: a named skill that is literally in a candidate's skills list or text is
    # supported, whatever the model said. The model can add support, it cannot take this away.
    cands = {r["requirement"]: r["candidate_ids"] for r in rows}
    for m in fit.matches:
        if m.requirement.startswith("Experience with "):
            skill = m.requirement.removeprefix("Experience with ").lower()
            proof = [i for i in cands.get(m.requirement, [])
                     if skill in [s.lower() for s in evidence[i]["skills"]] or skill in evidence[i]["text"].lower()]
            if proof:
                m.status, m.evidence_ids = "supported", proof
    # the score is worked out here, not taken from the model, so the thresholds mean the same thing every run
    points = sum({"supported": 1.0, "partly": 0.5}.get(m.status, 0.0) for m in fit.matches)
    fit.fit_score = round(points / len(fit.matches), 2) if fit.matches else 0.0
    return {"fit": fit, "evidence": [EvidenceItem(**{k: v for k, v in e.items() if k in EvidenceItem.model_fields}) for e in evidence.values()],
            "tokens_used": tokens}
