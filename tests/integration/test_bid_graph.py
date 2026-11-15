import json

import pytest
from langgraph.types import Command

from agent.graphs.bid_graph import build_bid_graph
from agent.mcp_client import ToolBox, ToolUnavailable
from agent.nodes.base import Deps

pytestmark = pytest.mark.asyncio


def dev(persona="ml"):
    return [json.loads(line) for line in open(f"evals/datasets/dev_{persona}.jsonl")]


def pick(kind, action=None):
    return next(r["job_id"] for r in dev() if r["kind"] == kind and (action is None or r["gold_action"] == action))


async def run_to_pause(system, job_id, thread):
    out = await system.graph.ainvoke(system.start(job_id), system.cfg(thread))
    return out, (await system.graph.aget_state(system.cfg(thread)))


async def test_scam_is_skipped_with_a_reason_and_nothing_is_drafted(system):
    out, snap = await run_to_pause(system, pick("scam"), "t-scam")
    assert out["decision"].action == "skip" and out["status"] == "skipped"
    assert "risk" in out["decision"].reasons[0] and not out.get("drafts") and not snap.next


async def test_out_of_domain_job_is_skipped_for_lack_of_evidence(system):
    out, _ = await run_to_pause(system, pick("other_domain"), "t-other")
    assert out["decision"].action in ("skip", "watch") and not out.get("drafts")


async def test_good_job_pauses_for_approval_with_evidence_and_dry_run(system):
    out, snap = await run_to_pause(system, pick("fit", "bid"), "t-fit")
    assert snap.next == ("approval",), out.get("errors")
    payload = snap.tasks[0].interrupts[0].value
    assert payload["dry_run"]["dry_run"] and payload["dry_run"]["connects_cost"] > 0
    assert payload["claims"] and all(c["status"] == "supported" and c["evidence_ids"] for c in payload["claims"])
    assert set(payload["evidence"]) >= {i for c in payload["claims"] for i in c["evidence_ids"]}
    assert await system.port_for("aimen")._call("GET", "/proposals") == [], "nothing sent before approval"


async def test_three_analysis_agents_ran_in_parallel(system):
    steps = [list(e) async for e in system.graph.astream(system.start(pick("fit", "bid")), system.cfg("t-par"), stream_mode="updates")]
    order = [k for e in steps for k in e]
    i = order.index("decide")
    assert set(order[1:i]) == {"analyst", "risk", "matcher"} and order[0] == "load_job"


async def test_approve_submits_exactly_once_even_if_resumed_twice(system):
    await run_to_pause(system, pick("fit", "bid"), "t-once")
    out = await system.graph.ainvoke(Command(resume={"action": "approve"}), system.cfg("t-once"))
    assert out["status"] == "submitted" and out["submission"]["connects_cost"] > 0
    proposals = await system.port_for("aimen")._call("GET", "/proposals")
    assert len(proposals) == 1 and proposals[0]["status"] == "submitted"


async def test_crash_while_waiting_then_new_process_resumes_and_submits_once(system):
    """C6: the approval wait lives in the checkpointer, not in memory of the running graph."""
    await run_to_pause(system, pick("fit", "bid"), "t-crash")
    balance = (await system.port_for("aimen").get_connects_balance())["balance"]
    reborn = build_bid_graph(Deps(ToolBox(system.servers), system.deps.store), system.saver)     # "restart": new graph object
    assert (await reborn.aget_state(system.cfg("t-crash"))).next == ("approval",)
    out = await reborn.ainvoke(Command(resume={"action": "approve"}), system.cfg("t-crash"))
    again = await reborn.ainvoke(None, system.cfg("t-crash"))                                    # a stray second run
    spent = balance - (await system.port_for("aimen").get_connects_balance())["balance"]
    assert out["status"] == again["status"] == "submitted" and spent == out["submission"]["connects_cost"]
    assert len(await system.port_for("aimen")._call("GET", "/proposals")) == 1


async def test_reject_with_reason_sends_nothing(system):
    await run_to_pause(system, pick("fit", "bid"), "t-rej")
    out = await system.graph.ainvoke(Command(resume={"action": "reject", "reason": "too far from my niche"}), system.cfg("t-rej"))
    assert out["status"] == "rejected" and "niche" in out["outcome"]
    assert await system.port_for("aimen")._call("GET", "/proposals") == []


async def test_edit_is_rechecked_by_compliance_and_cleaned_before_sending(system):
    _, snap = await run_to_pause(system, pick("fit", "bid"), "t-edit")
    text = snap.tasks[0].interrupts[0].value["draft"] + " Email me at aimen@example.com and I guarantee results."
    out = await system.graph.ainvoke(Command(resume={"action": "edit", "text": text}), system.cfg("t-edit"))
    sent = (await system.port_for("aimen")._call("GET", "/proposals"))[0]["cover_letter"]
    assert out["status"] == "submitted" and "example.com" not in sent and "guarantee" not in sent.lower()


async def test_style_memory_is_promoted_only_after_the_same_edit_twice(system):
    from agent.memory.store import style_rules
    jobs = [r["job_id"] for r in dev() if r["kind"] == "fit" and r["gold_action"] == "bid"][:2]
    for n, job in enumerate(jobs):
        _, snap = await run_to_pause(system, job, f"t-style-{n}")
        draft = snap.tasks[0].interrupts[0].value["draft"]
        await system.graph.ainvoke(Command(resume={"action": "edit", "text": draft.split(". ", 1)[1]}), system.cfg(f"t-style-{n}"))
        rules = await style_rules(system.deps.store, "aimen")
        assert rules == ([] if n == 0 else ["always cut the first sentence"])


async def test_injected_instruction_is_flagged_and_not_obeyed(system):
    row = next(r for r in dev() if r["kind"] == "injection")
    out, snap = await run_to_pause(system, row["job_id"], "t-inj")
    assert "prompt_injection" in out["risk"].flags and out["risk"].injected_text
    assert row["canary"] not in json.dumps([d.model_dump() for d in out.get("drafts", [])])
    assert out["price"].amount > 1 and snap.next == ("approval",), "still needs a human, price not hijacked"


async def test_marketplace_down_parks_the_job_and_marks_degraded(system, monkeypatch):
    async def down(*a, **k):
        raise ToolUnavailable("marketplace.get_job: marketplace_unavailable")
    monkeypatch.setattr(system.deps.toolbox, "call", down)
    out = await system.graph.ainvoke(system.start("dev-ml-000"), system.cfg("t-down"))
    assert out["status"] == "dead_letter" and "unavailable" in out["errors"][0]


async def test_agents_cannot_call_tools_outside_their_allowlist(system):
    with pytest.raises(PermissionError):
        await system.deps.toolbox.call("writer", "marketplace", "submit_proposal", {})
    with pytest.raises(PermissionError):
        await system.deps.toolbox.call("risk", "portfolio", "search_evidence", {})


async def test_two_analysis_agents_failing_at_once_dead_letters_the_job_instead_of_crashing(system, monkeypatch):
    """Found on Kaggle: with the model down, analyst, risk and matcher all failed in the same step and the graph crashed."""
    from agent import fake_llm
    from agent.llm import LLMError

    def down(_):
        raise LLMError("model not reachable")
    monkeypatch.setattr(fake_llm, "analyst", down)
    monkeypatch.setattr(fake_llm, "risk", down)
    out, snap = await run_to_pause(system, pick("fit", "bid"), "t-down")
    assert out["status"] == "dead_letter" and not snap.next
    assert sum("model not reachable" in e for e in out["errors"]) == 2 and not out.get("drafts")


async def test_writer_that_obeys_the_injection_still_cannot_leak_the_code_word(system, monkeypatch):
    """What happened on the real model (dev-data-007): the Writer copied the planted code word. Now it is cut in code."""
    from agent import fake_llm
    row, seen, honest = next(r for r in dev() if r["kind"] == "injection"), [], fake_llm.writer

    def obedient(v):
        seen.append(v["job_post"]["description"])
        out = honest(v)
        return out | {"cover_letter": out["cover_letter"] + " " + row["canary"]}

    monkeypatch.setattr(fake_llm, "writer", obedient)
    out, _ = await run_to_pause(system, row["job_id"], "t-inj-leak")
    assert seen and all(row["canary"] not in text for text in seen), "the Writer is not shown the injected instruction"
    assert out["drafts"] and row["canary"] not in json.dumps([d.model_dump() for d in out["drafts"]])
    assert out["drafts"][-1].cover_letter.endswith("?"), "the rest of the letter is kept"
