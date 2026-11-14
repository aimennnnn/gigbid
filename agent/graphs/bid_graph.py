"""The bid graph (C1): one thread per job.

load_job -> [analyst | risk | matcher] in parallel (Send) -> decide
  skip / watch -> END
  bid -> pricing -> writer -> verifier -> critic --(revise, max 2)--> writer
                                             \\-> compliance -> approval (interrupt) -> submit -> END

Nothing reaches the marketplace before `approval` returns "approve". The graph pauses there
with interrupt(); the pause is saved by the checkpointer, so it survives a crash or restart.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send, interrupt

from agent.memory.store import record_edit, record_outcome
from agent.nodes import analyst, compliance, critic, matcher, pricing, risk, scout, verifier, writer
from agent.nodes.base import Deps, ids, node
from agent.state import BidState


def fan_out(state: BidState):
    """Start the three analysis agents at the same time."""
    if state.get("status") == "dead_letter":
        return END
    return [Send("analyst", state), Send("risk", state), Send("matcher", state)]


async def preview(deps: Deps, state: dict, config: dict) -> dict:
    """dry_run: ask the marketplace exactly what would be sent and what it costs. Sends nothing."""
    text = state["compliance"].cleaned_text
    r = await deps.toolbox.call("sender", "marketplace", "create_proposal_draft", {
        "job_id": state["job_id"], "cover_letter": text, "amount": state["price"].amount,
        "screening_answers": state["drafts"][-1].screening_answers,
        "idempotency_key": f"{config['configurable']['thread_id']}-preview", "dry_run": True}, **ids(state, config))
    return {"preview": r, "status": "awaiting_approval"}


def approval(state: BidState) -> dict:
    """Human in the loop (C5). The payload is everything the approval screen shows."""
    draft = state["drafts"][-1]
    answer = interrupt({
        "kind": "proposal", "job_id": state["job_id"], "draft": state["compliance"].cleaned_text,
        "screening_answers": draft.screening_answers,
        "claims": [c.model_dump() for c in draft.claims],
        "evidence": {e.id: e.model_dump() for e in state["evidence"] if any(e.id in c.evidence_ids for c in draft.claims)},
        "risk": state["risk"].model_dump(), "price": state["price"].model_dump(),
        "critique": state["critiques"][-1].model_dump() if state.get("critiques") else None,
        "compliance": state["compliance"].model_dump(), "removed_claims": state.get("removed_claims", []),
        "dry_run": state.get("preview")})
    if answer.get("action") not in ("approve", "edit", "reject"):
        raise ValueError("approval must be approve, edit or reject")
    return {"approval": answer, "steps_used": 1}


def after_approval(state: BidState) -> str:
    return {"approve": "submit", "edit": "learn_edit", "reject": "rejected"}[state["approval"]["action"]]


async def learn_edit(deps: Deps, state: dict, config: dict) -> dict:
    """The user edited the draft: diff it, count it for style memory, then re-check compliance."""
    await record_edit(deps.store, state.get("user_id", "local"), state["compliance"].cleaned_text, state["approval"]["text"])
    return {}


async def rejected(deps: Deps, state: dict, config: dict) -> dict:
    return {"status": "rejected", "outcome": f"rejected by user: {state['approval'].get('reason', 'no reason given')}"}


async def submit(deps: Deps, state: dict, config: dict) -> dict:
    """Runs only after approval. The idempotency keys come from the thread id, so if the
    process dies here and this node runs again, the marketplace sees the same keys and
    the proposal is submitted exactly once."""
    thread, who = config["configurable"]["thread_id"], ids(state, config)
    text = state["compliance"].cleaned_text
    d = await deps.toolbox.call("sender", "marketplace", "create_proposal_draft", {
        "job_id": state["job_id"], "cover_letter": text, "amount": state["price"].amount,
        "screening_answers": state["drafts"][-1].screening_answers, "idempotency_key": f"{thread}-draft"}, **who)
    s = await deps.toolbox.call("sender", "marketplace", "submit_proposal", {
        "draft_id": d["id"], "job_id": state["job_id"], "idempotency_key": f"{thread}-submit"}, **who)
    if not s.get("replayed"):
        await record_outcome(deps.store, state.get("user_id", "local"), state["job"]["category"], "submitted")
    return {"submission": s, "status": "submitted"}


def build_bid_graph(deps: Deps, checkpointer=None):
    g = StateGraph(BidState)
    g.add_node("load_job", node("scout", scout.load_job, deps, critical=True))
    g.add_node("analyst", node("analyst", analyst.run, deps, critical=True))
    g.add_node("risk", node("risk", risk.run, deps, critical=True))
    g.add_node("matcher", node("matcher", matcher.run, deps, critical=True))
    g.add_node("decide", pricing.decide)
    g.add_node("pricing", node("pricing", pricing.run, deps, critical=True))
    g.add_node("writer", node("writer", writer.run, deps, critical=True))
    g.add_node("verifier", node("verifier", verifier.run, deps, critical=True))
    g.add_node("critic", node("critic", critic.run, deps, critical=True))
    g.add_node("compliance", node("compliance", compliance.run, deps, critical=True))
    g.add_node("preview", node("sender", preview, deps, critical=True))
    g.add_node("approval", approval)
    g.add_node("learn_edit", node("learn_edit", learn_edit, deps))
    g.add_node("recheck", node("compliance", compliance.run, deps, critical=True))
    g.add_node("rejected", node("rejected", rejected, deps))
    g.add_node("submit", node("sender", submit, deps, critical=True))

    def go(next_node: str, ok=lambda s: True):
        """Continue to next_node unless the job was parked (dead letter, skipped, blocked)."""
        return lambda s: next_node if s.get("status") not in ("dead_letter", "skipped", "needs_attention") and ok(s) else END

    g.add_edge(START, "load_job")
    g.add_conditional_edges("load_job", fan_out, ["analyst", "risk", "matcher", END])
    g.add_edge(["analyst", "risk", "matcher"], "decide")
    g.add_conditional_edges("decide", go("pricing", lambda s: s["decision"].action == "bid"), ["pricing", END])
    g.add_conditional_edges("pricing", go("writer"), ["writer", END])
    g.add_conditional_edges("writer", go("verifier"), ["verifier", END])
    g.add_conditional_edges("verifier", go("critic"), ["critic", END])
    g.add_conditional_edges("critic", lambda s: END if s.get("status") == "dead_letter" else critic.after_critic(s),
                            {"writer": "writer", "compliance": "compliance", "needs_attention": END, END: END})
    g.add_conditional_edges("compliance", go("preview"), ["preview", END])
    g.add_conditional_edges("preview", go("approval"), ["approval", END])
    g.add_conditional_edges("approval", after_approval, ["submit", "learn_edit", "rejected"])
    g.add_edge("learn_edit", "recheck")
    g.add_conditional_edges("recheck", go("submit"), ["submit", END])
    g.add_edge("rejected", END)
    g.add_edge("submit", END)
    return g.compile(checkpointer=checkpointer, store=deps.store)
