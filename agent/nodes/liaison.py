"""Client Liaison: reads the client's messages, classifies the intent, drafts a reply
and offers interview slots. Client messages are untrusted, exactly like job posts."""
from datetime import date, timedelta

from agent.guards import scan_job
from agent.handoffs import ReplyDraft
from agent.llm import ask
from agent.memory.store import style_rules
from agent.nodes.base import Deps, ids


async def read(deps: Deps, state: dict, config: dict) -> dict:
    r = await deps.toolbox.call("liaison", "marketplace", "list_messages", {"thread_id": state["thread_id"]}, **ids(state, config))
    slots = await deps.toolbox.call("liaison", "workspace", "get_free_slots",
                                    {"date_from": (date.today() + timedelta(days=1)).isoformat(), "days": 5}, **ids(state, config))
    return {"messages": r["messages"], "slots": slots["slots"], "status": "drafting"}


async def draft(deps: Deps, state: dict, config: dict) -> dict:
    last = next((m["text"] for m in reversed(state["messages"]) if m["sender"] == "client"), "")
    found = scan_job(last)
    reply, tokens = await ask("liaison", {
        "messages": state["messages"], "thread_id": state["thread_id"], "slots": state["slots"],
        "price_floor": state.get("profile", {}).get("min_budget", 0),
        "style_rules": await style_rules(deps.store, state.get("user_id", "local")), "rule_findings": found},
        ReplyDraft, untrusted=("messages",))
    reply.thread_id = state["thread_id"]
    if "off_platform" in found["flags"]:                 # the rules outrank the model
        reply.intent = "scam_signal"
    return {"reply": reply, "intent": reply.intent, "tokens_used": tokens}
