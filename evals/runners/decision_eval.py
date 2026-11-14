"""Decision evaluation (B4): does GigBid bid, skip, spot scams and price sensibly?

    uv run python -m evals.runners.decision_eval              20 jobs per persona
    uv run python -m evals.runners.decision_eval --limit 200  the whole dev set

Runs the real bid graph on dev jobs and stops before the Writer, so only the cheap
analysis nodes are paid for. Compared with the gold labels:
  bid-or-skip precision, recall and F1 ("watch" counts as not bidding)
  scam detection precision and recall (scam = risk at or above thresholds.risk_block)
  price inside the fair band
  planted instructions that were flagged
plus latency, tokens and list-price cost per job analysed.
Writes evals/results/decision_eval.json, including every wrong decision with its reasons.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import time

from agent.llm import USAGE
from agent.settings import get_settings
from evals.runners.common import System, cost_usd, dev_rows, mean, percentile, save


def prf(rows: list[dict], said: str, gold: str) -> dict:
    """Precision, recall and F1 of the yes/no field `said` against the yes/no field `gold`."""
    tp = sum(r[said] and r[gold] for r in rows)
    p = tp / max(1, sum(r[said] for r in rows))
    r = tp / max(1, sum(r[gold] for r in rows))
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(2 * p * r / (p + r), 4) if p + r else 0.0}


def summary(rows: list[dict]) -> dict:
    priced = [r for r in rows if r["price"] is not None]
    planted = [r for r in rows if r["gold_injection"]]
    return {"jobs": len(rows), "failed": sum(bool(r["errors"]) for r in rows),
            "bid_or_skip": prf(rows, "said_bid", "gold_bid"), "scam": prf(rows, "said_scam", "gold_scam"),
            "price_in_fair_band": mean([float(r["in_band"]) for r in priced]), "priced_jobs": len(priced),
            "injection_flagged": mean([float(r["flagged_injection"]) for r in planted]), "injection_jobs": len(planted)}


async def run(limit: int) -> None:
    rows, system, block, out = dev_rows(limit), System(), get_settings()["thresholds"]["risk_block"], []
    for n, r in enumerate(rows, start=1):
        mark, t0 = len(USAGE), time.perf_counter()
        try:
            s = await system.bid.ainvoke(System.start(r, f"eval-{r['job_id']}"), {"configurable": {"thread_id": f"decide-{r['job_id']}"}},
                                         interrupt_before=["writer"])
        except Exception as e:                                # one broken job must not end the run
            s = {"errors": [f"{type(e).__name__}: {e}"]}
        used, d, risk, price = USAGE[mark:], s.get("decision"), s.get("risk"), s.get("price")
        lo, hi = r["fair_price"]
        out.append({"job_id": r["job_id"], "persona": r["persona"], "kind": r["kind"],
                    "gold_bid": r["gold_action"] == "bid", "said_bid": bool(d and d.action == "bid" and s.get("status") != "skipped"),
                    "gold_scam": r["gold_scam"], "said_scam": bool(risk and risk.risk_score >= block),
                    "gold_injection": r["gold_injection"], "flagged_injection": bool(risk and "prompt_injection" in risk.flags),
                    "fit": s["fit"].fit_score if s.get("fit") else None, "risk": risk.risk_score if risk else None,
                    "price": price.amount if price else None, "fair_price": r["fair_price"], "in_band": bool(price and lo <= price.amount <= hi),
                    "reasons": d.reasons if d else [], "errors": s.get("errors", []),
                    "seconds": round(time.perf_counter() - t0, 2), "tokens": sum(u["tokens_in"] + u["tokens_out"] for u in used),
                    "usd": cost_usd(used)})
        print(f"[{n}/{len(rows)}] {r['job_id']} {r['kind']:13} gold={r['gold_action']:4} said={'bid' if out[-1]['said_bid'] else 'skip'}"
              + ("  ERROR" if out[-1]["errors"] else ""))
    took = [r["seconds"] for r in out]
    save("decision_eval", {
        "overall": summary(out), "by_persona": {p: summary([r for r in out if r["persona"] == p]) for p in sorted({r["persona"] for r in out})},
        "per_job_analysed": {"p50_s": percentile(took, 50), "p95_s": percentile(took, 95), "tokens": mean([r["tokens"] for r in out]),
                             "usd": round(sum(r["usd"] for r in out) / len(out), 6)},
        "rag_variant": os.getenv("GIGBID_RAG_VARIANT") or get_settings()["rag"]["variant"],
        "wrong": [r for r in out if r["said_bid"] != r["gold_bid"] or r["said_scam"] != r["gold_scam"] or r["errors"]]})
    o = summary(out)
    print(f"bid-or-skip F1={o['bid_or_skip']['f1']}  scam P={o['scam']['precision']} R={o['scam']['recall']}  price in band={o['price_in_fair_band']}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20, help="first N jobs per persona")
    asyncio.run(run(ap.parse_args(argv).limit))


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()
