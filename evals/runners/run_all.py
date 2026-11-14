"""`make eval`: every evaluation, then the results table. Results go to evals/results/*.json.

    uv run python -m evals.runners.run_all                the full run, with the models in .env
    uv run python -m evals.runners.run_all --only rag     retrieval + ablation only (no LLM)
    uv run python -m evals.runners.run_all --only agent   decisions + proposals only (needs an LLM)
    uv run python -m evals.runners.run_all --smoke        30 jobs, stand-in models, no network (CI)

--smoke writes to evals/results/smoke/, so stand-in numbers can never overwrite real ones.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--only", choices=["rag", "agent"])
    ap.add_argument("--jobs", type=int, default=10, help="proposal jobs per persona (agent part)")
    ap.add_argument("--decisions", type=int, default=20, help="decision jobs per persona (agent part)")
    ap.add_argument("--resume", action="store_true", help="carry on a proposal run that stopped half way")
    a = ap.parse_args()
    load_dotenv()
    if a.smoke:
        os.environ.update(GIGBID_LLM="fake", GIGBID_RAG_MODELS="fake",
                          EVAL_OUT=str(Path(__file__).resolve().parents[2] / "evals" / "results" / "smoke"))
        a.jobs, a.decisions, limit = 3, 10, ["--limit", "10"]
    else:
        limit = []
    # imported after the environment is set, because they read it
    from evals.runners import ablation, decision_eval, gigsim_outcomes, judge_calibration, rag_eval, results_table
    if a.only != "agent":
        rag_eval.main(limit)
        ablation.main(limit)
    if a.only != "rag":
        decision_eval.main(["--limit", str(a.decisions)])
        gigsim_outcomes.main(["--jobs", str(a.jobs)] + (["--resume"] if a.resume else []))
        judge_calibration.main([])
    results_table.main([] if a.smoke else ["--readme"])


if __name__ == "__main__":
    main()
