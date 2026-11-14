"""Retrieval evaluation (B4): every RAG variant against the gold evidence in the dev set.

    uv run python -m evals.runners.rag_eval                      all variants, all 600 dev jobs
    uv run python -m evals.runners.rag_eval --variants v0_naive,best --limit 10
    uv run python -m evals.runners.rag_eval --sweep              try corrective.min_score values for V8
    uv run python -m evals.runners.rag_eval --resume             carry on after a stopped run (same settings only)

Per variant, on jobs that HAVE gold evidence:
  recall_at_5   share of the gold items found in the top 5
  mrr           1 / rank of the first gold item (0 if none in the top 10)
  ndcg_at_10    ranking quality in the top 10, using the gold grades (1 to 3)
And on refusing (only the corrective step ever refuses):
  refused_no_evidence     share of jobs with NO gold evidence where nothing was returned (higher is better)
  refused_with_evidence   share of jobs WITH gold evidence where nothing was returned (lower is better)
Latency is measured on --timing jobs spread over the dev set, with the caches off. No LLM is used here.
Writes evals/results/rag_eval.json.
"""
from __future__ import annotations

import argparse
import math
import time

from agent.settings import get_settings
from evals.runners.common import dev_rows, mean, percentile, save, saved, settings_used
from rag import retriever
from rag.index import embed
from rag.variants import v3_rerank


def score(ranked: list[str], gold: dict[str, int]) -> dict:
    """Metrics for one job. ranked = evidence ids, best first. gold = id -> grade."""
    first = next((n for n, i in enumerate(ranked[:10], start=1) if i in gold), None)
    dcg = sum((2 ** gold.get(i, 0) - 1) / math.log2(n + 1) for n, i in enumerate(ranked[:10], start=1))
    ideal = sum((2 ** g - 1) / math.log2(n + 1) for n, g in enumerate(sorted(gold.values(), reverse=True)[:10], start=1))
    return {"recall_at_5": len(set(ranked[:5]) & set(gold)) / len(gold), "mrr": 1 / first if first else 0.0, "ndcg_at_10": dcg / ideal}


def summary(rows: list[dict]) -> dict:
    """Average the per-job results of one group of jobs."""
    has, none = [r for r in rows if r["gold"]], [r for r in rows if not r["gold"]]
    out = {"jobs_with_evidence": len(has), "jobs_without_evidence": len(none)}
    for m in ("recall_at_5", "mrr", "ndcg_at_10"):
        out[m] = mean([r[m] for r in has])
    out["refused_with_evidence"] = mean([float(not r["ranked"]) for r in has])
    out["refused_no_evidence"] = mean([float(not r["ranked"]) for r in none])
    return out


def evaluate(variant: str, rows: list[dict], timing: int = 30) -> dict:
    # 1. latency on a few jobs, caches off, so it is what one fresh request costs
    for p in {r["persona"] for r in rows}:                   # load the models and build each persona's index first
        retriever.retrieve(p, rows[0]["job"], 10, variant)
    embed.use_cache = v3_rerank.use_cache = False
    took = []
    for r in rows[::max(1, len(rows) // timing)][:timing] if timing else []:     # spread over all personas
        t = time.perf_counter()
        retriever.retrieve(r["persona"], r["job"], 10, variant)
        took.append((time.perf_counter() - t) * 1000)
    embed.use_cache = v3_rerank.use_cache = True
    # 2. quality on every job
    done = []
    for n, r in enumerate(rows, start=1):
        if n % 100 == 0:
            print(f"  {variant}: {n}/{len(rows)} jobs")
        ranked = [item["id"] for item, _ in retriever.retrieve(r["persona"], r["job"], 10, variant)]
        style = "named_skills" if r["job"]["skills"] else "vague_post"
        done.append({"persona": r["persona"], "kind": r["kind"], "style": style, "gold": r["gold_evidence"], "ranked": ranked}
                    | (score(ranked, r["gold_evidence"]) if r["gold_evidence"] else {}))

    def by(key: str) -> dict:
        return {v: summary([d for d in done if d[key] == v]) for v in sorted({d[key] for d in done})}
    speed = {"p50_ms": round(percentile(took, 50), 1), "p95_ms": round(percentile(took, 95), 1)} if took else {}
    return {"steps": retriever.steps(variant), "overall": summary(done) | speed,
            "by_persona": by("persona"), "by_kind": by("kind"), "by_style": by("style")}


def show(name: str, o: dict) -> None:
    print(f"{name:22} recall@5={o['recall_at_5']:.3f} mrr={o['mrr']:.3f} ndcg@10={o['ndcg_at_10']:.3f} "
          f"refused(no evidence)={o['refused_no_evidence']:.2f} refused(with evidence)={o['refused_with_evidence']:.2f}"
          + (f" p95={o['p95_ms']:.0f}ms" if "p95_ms" in o else ""))


def sweep(rows: list[dict]) -> None:
    """Try values of corrective.min_score for V8 and report both sides of the trade."""
    cfg, table = get_settings()["rag"]["corrective"], []
    keep = cfg["min_score"]
    for t in [x / 20 for x in range(1, 20)]:
        cfg["min_score"] = t
        o = evaluate("v8_corrective", rows, timing=0)["overall"]
        table.append({"min_score": t, "recall_at_5": o["recall_at_5"], "refused_no_evidence": o["refused_no_evidence"],
                      "refused_with_evidence": o["refused_with_evidence"]})
        print(f"min_score={t:.2f} recall@5={o['recall_at_5']:.3f} refused(no evidence)={o['refused_no_evidence']:.2f} "
              f"refused(with evidence)={o['refused_with_evidence']:.2f}")
    cfg["min_score"] = keep
    best = max(table, key=lambda r: r["recall_at_5"] + r["refused_no_evidence"])
    print(f"\nbest balance: min_score={best['min_score']}. To use it, set rag.corrective.min_score in agent/config.yaml (now {keep}).")
    save("corrective_sweep", {"note": "V8 on the dev set for each min_score; suggested = highest recall_at_5 + refused_no_evidence",
                              "suggested_min_score": best["min_score"], "in_config": keep, "table": table})


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default="")
    ap.add_argument("--limit", type=int, default=None, help="first N jobs per persona")
    ap.add_argument("--timing", type=int, default=30, help="jobs used to measure latency")
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--resume", action="store_true", help="skip variants an interrupted run already finished")
    a = ap.parse_args(argv)
    rows = dev_rows(a.limit)
    if a.sweep:
        return sweep(rows)
    names = a.variants.split(",") if a.variants else list(get_settings()["rag"]["variants"])
    # checkpoint: each finished variant is saved at once; --resume picks up after the last finished one
    done = saved("rag_eval_progress", len(rows)) if a.resume else {}
    results = {}
    for name in names:
        results[name] = done[name] if name in done else evaluate(name, rows, a.timing)
        show(name + (" (saved)" if name in done else ""), results[name]["overall"])
        save("rag_eval_progress", {"jobs": len(rows), "settings": settings_used(), "done": results})
    save("rag_eval", {"jobs": len(rows), "timing_jobs": min(a.timing, len(rows)), "variants": results})


if __name__ == "__main__":
    main()
