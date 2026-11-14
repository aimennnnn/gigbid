"""Critic: grounding, personalisation, length. Can send a draft back at most twice (C4)."""
from agent.handoffs import Critique
from agent.llm import ask
from agent.nodes.base import Deps
from agent.settings import get_settings


async def run(deps: Deps, state: dict, config: dict) -> dict:
    draft = state["drafts"][-1]
    critique, tokens = await ask("critic", {"job_post": state["job"], "draft": draft.model_dump(),
                                            "word_limits": get_settings()["rules"]["proposal"]}, Critique, untrusted=("job_post",))
    # rule on top of the model: a letter left with no proven past work goes back to the writer
    cut = state.get("removed_claims", [])
    if not draft.claims and cut and len(state.get("critiques", [])) < get_settings()["limits"]["critic_max_revisions"]:
        critique.approved = critique.grounding_ok = False
        critique.comments.append("Your sentences about past work were removed because they added details that are not in the "
                                 "evidence. Write them again using only facts stated in the evidence text: " + " | ".join(cut[-2:]))
    return {"critiques": [critique], "tokens_used": tokens}


def after_critic(state: dict) -> str:
    limits = get_settings()["limits"]
    if state.get("steps_used", 0) > limits["step_budget"] or state.get("tokens_used", 0) > limits["token_budget"]:
        return "needs_attention"
    if state["critiques"][-1].approved or len(state["critiques"]) > limits["critic_max_revisions"]:
        return "compliance"
    return "writer"
