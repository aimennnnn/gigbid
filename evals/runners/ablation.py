"""Ablation (R&D question B): take a pipeline and remove one step at a time.

    uv run python -m evals.runners.ablation                         best and all_steps
    uv run python -m evals.runners.ablation --pipelines best --resume

If removing a step makes the numbers go UP, that step is hurting. Writes
evals/results/ablation.json, with the same breakdown by persona and job kind as rag_eval.
Each finished line is saved at once, so --resume carries on after a stopped run.
"""
from __future__ import annotations

import argparse

from agent.settings import get_settings
from evals.runners.common import dev_rows, save, saved, settings_used
from evals.runners.rag_eval import evaluate, show

METRICS = ("recall_at_5", "mrr", "ndcg_at_10", "refused_no_evidence")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="first N jobs per persona")
    ap.add_argument("--pipelines", default="best,all_steps")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args(argv)
    rows, variants = dev_rows(a.limit), get_settings()["rag"]["variants"]
    todo = {p: list(variants[p]) for p in a.pipelines.split(",")}
    done = saved("ablation_progress", len(rows)) if a.resume else {}       # latency is measured in rag_eval, not here

    def run(name: str, steps: list[str]) -> dict:
        if name not in done:
            variants[name] = steps                                         # a temporary variant, only in memory
            done[name] = evaluate(name, rows, timing=0)
            if name not in todo:
                del variants[name]
            save("ablation_progress", {"jobs": len(rows), "settings": settings_used(), "done": done})
        show(name, done[name]["overall"])
        return done[name]

    out = {}
    for pipeline, steps in todo.items():
        full, without = run(pipeline, steps), {}
        for step in steps:
            without[step] = dict(run(f"{pipeline} without {step}", [s for s in steps if s != step]))
            without[step]["change_vs_full"] = {m: round(without[step]["overall"][m] - full["overall"][m], 4) for m in METRICS}
        out[pipeline] = {"steps": steps, "full": full, "without": without}
    save("ablation", {"jobs": len(rows), "pipelines": out})


if __name__ == "__main__":
    main()
