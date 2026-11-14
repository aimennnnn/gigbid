import json

import pytest
from langgraph.types import Command

from agent.graphs.conversation_graph import build_conversation_graph

pytestmark = pytest.mark.asyncio
LETTER = ("You need a model for this. I built one with {a} and {b} that caught 81% of cases. " * 3)


async def thread_with_reply(system, want):
    """Submit proposals straight to GigSim until a client replies with the wanted kind of message."""
    port, rows = system.port_for("aimen"), [json.loads(line) for line in open("evals/datasets/dev_ml.jsonl")]
    for r in rows:
        if (r["kind"] == "scam") != (want == "scam"):
            continue
        job = await port.get_job(r["job_id"])
        a, b = (job["skills"] + ["Python", "SQL"])[:2]
        d = await port.create_proposal_draft(r["job_id"], LETTER.format(a=a, b=b), job["budget"]["min"], {}, f"k-d-{r['job_id']}")
        await port.submit_proposal(d["proposal_id"], f"k-s-{r['job_id']}")
        msgs = await port.list_messages(f"t-{d['proposal_id']}")
        if msgs and (want != "call" or "call" in msgs[-1]["text"]):
            return f"t-{d['proposal_id']}"
    raise AssertionError("no client replied")


async def run(system, thread_id, name):
    graph = build_conversation_graph(system.deps, system.saver)
    cfg = system.cfg(name)
    await graph.ainvoke({"user_id": "aimen", "persona": "ml", "thread_id": thread_id, "profile": {"min_budget": 400}}, cfg)
    return graph, cfg, (await graph.aget_state(cfg)).tasks[0].interrupts[0].value


async def test_scam_signal_is_classified_and_reply_stays_on_platform(system):
    graph, cfg, payload = await run(system, await thread_with_reply(system, "scam"), "c-scam")
    assert payload["intent"] == "scam_signal" and "platform" in payload["draft"].lower()
    assert "555" not in payload["draft"]


async def test_interview_request_offers_slots_and_sends_only_after_approval(system):
    thread = await thread_with_reply(system, "call")
    graph, cfg, payload = await run(system, thread, "c-call")
    port = system.port_for("aimen")
    assert payload["intent"] == "interview_request" and len(payload["interview_slots"]) == 3
    assert [m["sender"] for m in await port.list_messages(thread)] == ["client"], "nothing sent before approval"
    out = await graph.ainvoke(Command(resume={"action": "approve"}), cfg)
    await graph.ainvoke(None, cfg)                                           # a stray re-run must not send again
    sent = [m for m in await port.list_messages(thread) if m["sender"] == "freelancer"]
    assert out["status"] == "submitted" and len(sent) == 1


async def test_reject_sends_nothing(system):
    thread = await thread_with_reply(system, "any")
    graph, cfg, _ = await run(system, thread, "c-rej")
    out = await graph.ainvoke(Command(resume={"action": "reject", "reason": "not now"}), cfg)
    assert out["status"] == "rejected"
    assert all(m["sender"] == "client" for m in await system.port_for("aimen").list_messages(thread))
