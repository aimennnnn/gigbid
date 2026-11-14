"""Proposal Writer: cover letter and screening answers, every claim tied to evidence ids."""
from agent.handoffs import ProposalDraft, WriterOutput
from agent.llm import ask
from agent.memory.store import outcome_notes, style_rules
from agent.nodes.base import Deps
from agent.settings import get_settings


async def run(deps: Deps, state: dict, config: dict) -> dict:
    user, spec = state.get("user_id", "local"), state["job_spec"]
    proven = {i for m in state["fit"].matches if m.status == "supported" for i in m.evidence_ids}
    evidence = [e.model_dump() for e in state["evidence"] if e.id in proven] or [e.model_dump() for e in state["evidence"][:4]]
    last = state["critiques"][-1].comments if state.get("critiques") else []
    out, tokens = await ask("writer", {
        "job_post": state["job"], "job_spec": spec.model_dump(), "evidence": evidence,
        "price": state["price"].model_dump(), "word_limits": get_settings()["rules"]["proposal"],
        "screening_questions": spec.screening_questions or state["job"].get("screening_questions", []),
        "style_rules": await style_rules(deps.store, user),
        "outcome_notes": await outcome_notes(deps.store, user, state["job"]["category"]),
        "critic_comments": last}, WriterOutput, untrusted=("job_post",))
    known = {e["id"] for e in evidence}
    for c in out.claims:
        c.evidence_ids = [i for i in c.evidence_ids if i in known]
    draft = ProposalDraft(job_id=state["job_id"], cover_letter=out.cover_letter, screening_answers=out.screening_answers,
                          claims=out.claims, revision=len(state.get("drafts", [])))
    return {"drafts": [draft], "tokens_used": tokens, "status": "drafting"}
