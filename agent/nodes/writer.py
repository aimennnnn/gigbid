"""Proposal Writer: cover letter and screening answers, every claim tied to evidence ids."""
from agent.guards import drop_planted, planted_words, without_injection
from agent.handoffs import ProposalDraft, WriterOutput
from agent.llm import ask
from agent.memory.store import outcome_notes, style_rules
from agent.nodes.base import Deps
from agent.settings import get_settings


async def run(deps: Deps, state: dict, config: dict) -> dict:
    user, spec = state.get("user_id", "local"), state["job_spec"]
    proven = {i for m in state["fit"].matches if m.status == "supported" for i in m.evidence_ids}
    picked = [e for e in state["evidence"] if e.id in proven] or state["evidence"][:4]
    evidence = [{"id": e.id, "type": e.type, "title": e.title, "skills": e.skills, "text": e.text[:700]} for e in picked[:5]]
    last = state["critiques"][-1].comments if state.get("critiques") else []
    injected = state["risk"].injected_text if state.get("risk") else None      # quoted by the Risk Assessor
    out, tokens = await ask("writer", {
        "job_post": without_injection(state["job"], injected), "job_spec": spec.model_dump(), "evidence": evidence,
        "price": state["price"].model_dump(), "word_limits": get_settings()["rules"]["proposal"],
        "screening_questions": spec.screening_questions or state["job"].get("screening_questions", []),
        "style_rules": await style_rules(deps.store, user),
        "outcome_notes": await outcome_notes(deps.store, user, state["job"]["category"]),
        "critic_comments": last}, WriterOutput, untrusted=("job_post",))
    known = {e["id"] for e in evidence}
    for c in out.claims:
        c.evidence_ids = [i for i in c.evidence_ids if i in known]
    # rule on top of the model: a code word that exists only in the injected instruction never leaves this node
    planted = planted_words(state["job"], injected)
    draft = ProposalDraft(job_id=state["job_id"], cover_letter=drop_planted(out.cover_letter, planted),
                          screening_answers={q: drop_planted(a, planted) for q, a in out.screening_answers.items()},
                          claims=[c for c in out.claims if not any(w in c.text for w in planted)],
                          revision=len(state.get("drafts", [])))
    return {"drafts": [draft], "tokens_used": tokens, "status": "drafting"}
