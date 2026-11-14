"""Ablation (R&D question B): take the `best` pipeline and remove one step at a time.

    uv run python -m evals.runners.ablation

If removing a step makes the numbers go UP, that step is hurting: take it out of
rag.variants.best in agent/config.yaml. Writes evals/results/ablation.json, with the
same breakdown by persona and job kind as rag_eval.
"""
from __future__ import annotations

import argparse

from agent.settings import get_settings
from evals.runners.common import dev_rows, save
from evals.runners.rag_eval import evaluate, show


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="first N jobs per persona")
    a = ap.parse_args(argv)
    rows, variants = dev_rows(a.limit), get_settings()["rag"]["variants"]
    full = evaluate("best", rows)
    show("best", full["overall"])
    out = {}
    for step in variants["best"]:
        name = f"best without {step}"
        variants[name] = [s for s in variants["best"] if s != step]       # a temporary variant, only in memory
        out[step] = evaluate(name, rows)
        out[step]["change_vs_best"] = {m: round(out[step]["overall"][m] - full["overall"][m], 4)
                                       for m in ("recall_at_5", "mrr", "ndcg_at_10", "refused_no_evidence")}
        show(name, out[step]["overall"])
        del variants[name]
    save("ablation", {"jobs": len(rows), "best": full, "without": out})


if __name__ == "__main__":
    main()
