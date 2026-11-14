"""The conversation graph (C1): one thread per client conversation.

read messages -> classify intent and draft a reply -> compliance -> approval (interrupt) -> send

Same approval gate as the bid graph: no message leaves before the human approves it.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from agent.memory.store import record_edit
from agent.nodes import compliance, liaison
from agent.nodes.base import Deps, ids, node
from agent.state import ConversationState


async def check(deps: Deps, state: dict, config: dict) -> dict:
    edited = (state.get("approval") or {}).get("action") == "edit"
    verdict, tokens = await compliance.check(state["approval"]["text"] if edited else state["reply"].text)
    return {"compliance": verdict, "tokens_used": tokens} | ({} if verdict.passed else {"status": "needs_attention"})


def approval(state: ConversationState) -> dict:
    answer = interrupt({"kind": "message", "thread_id": state["thread_id"], "intent": state["intent"],
                        "draft": state["compliance"].cleaned_text, "interview_slots": state["reply"].interview_slots,
                        "compliance": state["compliance"].model_dump(), "messages": state["messages"][-6:]})
    if answer.get("action") not in ("approve", "edit", "reject"):
        raise ValueError("approval must be approve, edit or reject")
    return {"approval": answer, "steps_used": 1, "status": "rejected" if answer["action"] == "reject" else "awaiting_approval"}


async def learn_edit(deps: Deps, state: dict, config: dict) -> dict:
    await record_edit(deps.store, state.get("user_id", "local"), state["compliance"].cleaned_text, state["approval"]["text"])
    return {}


async def send(deps: Deps, state: dict, config: dict) -> dict:
    """Only after approval. Keys come from the graph thread id, so a re-run never sends twice."""
    thread, who = config["configurable"]["thread_id"], ids(state, config)
    r = await deps.toolbox.call("sender", "marketplace", "send_message", {
        "thread_id": state["thread_id"], "text": state["compliance"].cleaned_text, "idempotency_key": f"{thread}-send"}, **who)
    if state["intent"] == "interview_request" and state["reply"].interview_slots:
        await deps.toolbox.call("sender", "workspace", "create_interview_hold", {
            "start": state["reply"].interview_slots[0], "title": f"Client call ({state['thread_id']})",
            "idempotency_key": f"{thread}-hold"}, **who)
    return {"sent": r, "status": "submitted"}


def build_conversation_graph(deps: Deps, checkpointer=None):
    g = StateGraph(ConversationState)
    g.add_node("read", node("liaison", liaison.read, deps, critical=True))
    g.add_node("draft", node("liaison", liaison.draft, deps, critical=True))
    g.add_node("compliance", node("compliance", check, deps, critical=True))
    g.add_node("approval", approval)
    g.add_node("learn_edit", node("learn_edit", learn_edit, deps))
    g.add_node("recheck", node("compliance", check, deps, critical=True))
    g.add_node("send", node("sender", send, deps, critical=True))

    def go(nxt):
        return lambda s: nxt if s.get("status") not in ("dead_letter", "needs_attention") else END
    g.add_edge(START, "read")
    g.add_conditional_edges("read", go("draft"), ["draft", END])
    g.add_conditional_edges("draft", go("compliance"), ["compliance", END])
    g.add_conditional_edges("compliance", go("approval"), ["approval", END])
    g.add_conditional_edges("approval", lambda s: {"approve": "send", "edit": "learn_edit", "reject": END}[s["approval"]["action"]],
                            ["send", "learn_edit", END])
    g.add_edge("learn_edit", "recheck")
    g.add_conditional_edges("recheck", go("send"), ["send", END])
    g.add_edge("send", END)
    return g.compile(checkpointer=checkpointer, store=deps.store)
