"""Verifier: checks every claim against the evidence and cuts what is not supported,
BEFORE the Critic sees the draft (B3)."""
from agent.nodes.base import Deps
from rag import verify


async def run(deps: Deps, state: dict, config: dict) -> dict:
    draft = state["drafts"][-1]
    evidence = [e.model_dump() for e in state["evidence"]]
    claims, tokens = await verify.verify(verify.split_claims(draft.cover_letter, draft.claims), evidence)
    cleaned = draft.model_copy(update={
        "cover_letter": verify.remove_unsupported(draft.cover_letter, claims),
        "claims": [c for c in claims if c.status == "supported"]})
    return {"drafts": [cleaned], "tokens_used": tokens, "unsupported_before": verify.unsupported_rate(claims),
            "removed_claims": [c.text for c in claims if c.status != "supported"]}
