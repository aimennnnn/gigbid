"""Outcome evaluation (B4): write real proposals on a fixed job set and see what GigSim's clients do.

    uv run python -m evals.runners.gigsim_outcomes                           v0_naive and best, 10 jobs per persona
    uv run python -m evals.runners.gigsim_outcomes --variants best --jobs 5
    uv run python -m evals.runners.gigsim_outcomes --resume                  carry on after a crash
    uv run python -m evals.runners.gigsim_outcomes --injection --variants best --jobs 5
                                                   only jobs with a planted instruction; writes injection_check*.json(l)

The fixed job set is the first N dev jobs per persona whose gold label is "bid".
For each RAG variant and each job the whole bid graph runs. The eval stands in for the human
and approves (GigSim only, never a real marketplace), then reads what the client did.
If the client replied, the conversation graph answers once, which is when a hire can happen.

Per proposal it records: unsupported claims before verification (cut from the first draft)
and after (a second check of the final text), the judge score, seconds and tokens up to the
approval screen, list-price cost, and whether a planted instruction's code word got through.
Writes evals/results/proposals_<variant>.jsonl (one row per job) and gigsim_outcomes.json.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time

from langgraph.types import Command

from agent.handoffs import Claim
from agent.llm import USAGE
from evals.runners.common import System, cost_usd, dev_rows, mean, out_dir, percentile, save
from evals.runners.judge_calibration import judge
from rag import verify


async def one(system: System, row: dict, variant: str) -> dict:
    user = f"eval-{variant}-{row['job_id']}"                 # one GigSim account per job: its own Connects and rate limit
    cfg, mark, t0, first = {"configurable": {"thread_id": user}}, len(USAGE), time.perf_counter(), None
    async for update in system.bid.astream(System.start(row, user), cfg, stream_mode="updates"):
        if "verifier" in update and first is None:
            first = update["verifier"]                       # the verifier's report on the FIRST draft
    snap = await system.bid.aget_state(cfg)
    s, used = snap.values, USAGE[mark:]
    out = {"job_id": row["job_id"], "persona": row["persona"], "kind": row["kind"], "variant": variant,
           "job_title": s.get("job", {}).get("title", ""), "job_post": s.get("job", {}).get("description", ""),
           "decision": s["decision"].action if s.get("decision") else None, "status": s.get("status"), "errors": s.get("errors", []),
           "seconds": round(time.perf_counter() - t0, 2), "tokens": sum(u["tokens_in"] + u["tokens_out"] for u in used),
           "tokens_out": sum(u["tokens_out"] for u in used), "model_seconds": round(sum(u["seconds"] for u in used), 2),
           "usd": cost_usd(used), "letter": None, "events": []}
    if snap.next != ("approval",):
        return out                                           # skipped, blocked or failed: no proposal to send
    pay = snap.tasks[0].interrupts[0].value
    evidence = [{"id": e["id"], "title": e["title"], "text": e["text"][:700]} for e in pay["evidence"].values()]
    again, _ = await verify.verify(verify.split_claims(pay["draft"], [Claim(**c) for c in pay["claims"]]), evidence)
    mark_given, _ = await judge(s["job"], pay["draft"], evidence)
    cut = len(first.get("removed_claims", [])) if first else 0
    out |= {"letter": pay["draft"], "evidence": [f"{e['title']}: {e['text']}" for e in evidence],
            "claims_first_draft": cut + (len(first["drafts"][0].claims) if first else 0), "unsupported_before": cut,
            "unsupported_after": sum(c.status != "supported" for c in again),
            "judge_score": mark_given.score, "judge_reasons": mark_given.reasons,
            "canary_leaked": bool(row["canary"] and row["canary"] in pay["draft"])}
    done = await system.bid.ainvoke(Command(resume={"action": "approve"}), cfg)
    port = system.port_for(user)
    events = {e["type"] for e in await port.list_events()}
    if "replied" in events and done.get("submission"):
        tcfg = {"configurable": {"thread_id": f"{user}-talk"}}
        await system.talk.ainvoke({"user_id": user, "persona": row["persona"], "thread_id": f"t-{done['submission']['id']}",
                                   "profile": {"min_budget": 400}}, tcfg)
        if (await system.talk.aget_state(tcfg)).next == ("approval",):
            await system.talk.ainvoke(Command(resume={"action": "approve"}), tcfg)
        events = {e["type"] for e in await port.list_events()}
    return out | {"status": done.get("status"), "events": sorted(events)}


def summary(rows: list[dict]) -> dict:
    drafted = [r for r in rows if r["letter"]]
    sent = [r for r in drafted if "submitted" in r["events"]]

    def rate(event: str) -> float | None:
        return mean([float(event in r["events"]) for r in sent])
    claims = sum(r["claims_first_draft"] for r in drafted)
    return {"jobs": len(rows), "drafted": len(drafted), "submitted": len(sent), "failed": sum(bool(r["errors"]) for r in rows),
            "reply_rate": rate("replied"), "interview_rate": rate("interview"), "hire_rate": rate("hired"),
            "unsupported_before_per_proposal": mean([r["unsupported_before"] for r in drafted]),
            "unsupported_after_per_proposal": mean([r["unsupported_after"] for r in drafted]),
            "unsupported_share_before": round(sum(r["unsupported_before"] for r in drafted) / claims, 4) if claims else None,
            "judge_score": mean([r["judge_score"] for r in drafted]),
            "p50_s": percentile([r["seconds"] for r in drafted], 50), "p95_s": percentile([r["seconds"] for r in drafted], 95),
            "tokens_per_proposal": mean([r["tokens"] for r in drafted]),
            "usd_per_proposal": round(sum(r["usd"] for r in drafted) / len(drafted), 6) if drafted else None,
            "output_tokens_per_second": round(sum(r["tokens_out"] for r in rows) / max(0.01, sum(r["model_seconds"] for r in rows)), 1),
            "canary_leaked": sum(r["canary_leaked"] for r in drafted)}


async def run(variants: list[str], jobs: int, resume: bool, injection: bool = False) -> None:
    rows, picked = dev_rows(), []
    for p in sorted({r["persona"] for r in rows}):
        picked += [r for r in rows if r["persona"] == p and r["gold_action"] == "bid" and (r["kind"] == "injection" or not injection)][:jobs]
    name, lines = ("injection_check", "injection_check_{}.jsonl") if injection else ("gigsim_outcomes", "proposals_{}.jsonl")
    results = {}
    for variant in variants:
        os.environ["GIGBID_RAG_VARIANT"] = variant           # the Portfolio server and the Fit Matcher read this
        path, system = out_dir() / lines.format(variant), System()
        done = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if resume and path.exists() else []
        have = {r["job_id"] for r in done}
        with open(path, "a" if resume else "w", encoding="utf-8", newline="\n") as f:
            for n, row in enumerate(picked, start=1):
                if row["job_id"] in have:
                    continue
                try:
                    r = await one(system, row, variant)
                except Exception as e:                       # one broken job must not end the run
                    r = {"job_id": row["job_id"], "persona": row["persona"], "kind": row["kind"], "variant": variant, "letter": None,
                         "events": [], "errors": [f"{type(e).__name__}: {e}"], "seconds": 0, "tokens": 0, "tokens_out": 0,
                         "model_seconds": 0, "usd": 0, "status": "failed"}
                f.write(json.dumps(r) + "\n")
                f.flush()
                done.append(r)
                print(f"[{variant} {n}/{len(picked)}] {row['job_id']} status={r['status']} events={','.join(r['events']) or '-'}"
                      + ("  ERROR " + r["errors"][0][:80] if r["errors"] else ""))
        results[variant] = {"overall": summary(done),
                            "by_persona": {p: summary([r for r in done if r["persona"] == p]) for p in sorted({r["persona"] for r in done})},
                            "by_kind": {k: summary([r for r in done if r["kind"] == k]) for k in sorted({r["kind"] for r in done})}}
        o = results[variant]["overall"]
        print(f"{variant}: submitted {o['submitted']}/{o['jobs']}  reply rate={o['reply_rate']}  hire rate={o['hire_rate']}  "
              f"unsupported before/after={o['unsupported_before_per_proposal']}/{o['unsupported_after_per_proposal']}  judge={o['judge_score']}"
              f"  code word leaked={o['canary_leaked']}/{o['drafted']}")
    os.environ.pop("GIGBID_RAG_VARIANT", None)
    save(name, {"jobs_per_persona": jobs, "job_ids": [r["job_id"] for r in picked], "variants": results})


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default="v0_naive,best")
    ap.add_argument("--jobs", type=int, default=10, help="jobs per persona")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--injection", action="store_true", help="only jobs with a planted instruction, saved as injection_check")
    a = ap.parse_args(argv)
    asyncio.run(run(a.variants.split(","), a.jobs, a.resume, a.injection))


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()
