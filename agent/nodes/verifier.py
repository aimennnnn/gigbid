"""Verifier: checks every claim against the evidence and cuts what is not supported,
BEFORE the Critic sees the draft (B3)."""
from agent.nodes.base import Deps
from rag import verify


async def run(deps: Deps, state: dict, config: dict) -> dict:
    draft = state["drafts"][-1]
    todo = verify.split_claims(draft.cover_letter, draft.claims)
    cited = {i for c in todo for i in c.evidence_ids}
    evidence = [{"id": e.id, "title": e.title, "text": e.text[:700]} for e in state["evidence"] if e.id in cited]   # only what was cited
    claims, tokens = await verify.verify(todo, evidence)
    cleaned = draft.model_copy(update={
        "cover_letter": verify.remove_unsupported(draft.cover_letter, claims),
        "claims": [c for c in claims if c.status == "supported"]})
    return {"drafts": [cleaned], "tokens_used": tokens, "unsupported_before": verify.unsupported_rate(claims),
            "removed_claims": [c.text for c in claims if c.status != "supported"]}
