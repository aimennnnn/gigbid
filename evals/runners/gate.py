"""CI gate (E2): fail the build when the evaluation results are worse than the thresholds in agent/config.yaml.

    uv run python -m evals.runners.gate            checks the committed real-model results in evals/results/
    uv run python -m evals.runners.gate --smoke    checks evals/results/smoke/ (run `make eval-smoke` first)

Exit code 1 lists every threshold that was missed. A missing result file is a failure too,
so a gate can never pass because an evaluation silently did not run.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent.settings import get_settings

ROOT = Path(__file__).resolve().parents[2]


def measured(folder: Path) -> dict[str, float | None]:
    """The numbers the gates look at, read from the result files. None = file or field missing."""
    def load(name: str) -> dict:
        path = folder / name
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    rag, dec, out, inj = load("rag_eval.json"), load("decision_eval.json"), load("gigsim_outcomes.json"), load("injection_check.json")
    variants = list(out.get("variants", {}).values())
    best = out.get("variants", {}).get("best", {}).get("overall", {})
    leaks = [v["overall"]["canary_leaked"] for v in inj.get("variants", {}).values()] or [v["overall"]["canary_leaked"] for v in variants]
    return {
        "recall_at_5": rag.get("variants", {}).get("best", {}).get("overall", {}).get("recall_at_5"),
        "bid_or_skip_f1": dec.get("overall", {}).get("bid_or_skip", {}).get("f1"),
        "scam_recall": dec.get("overall", {}).get("scam", {}).get("recall"),
        "unsupported_after": best.get("unsupported_after_per_proposal"),
        "canary_leaked": max(leaks) if leaks else None,
        "failed_jobs": sum(v["overall"]["failed"] for v in variants) + dec.get("overall", {}).get("failed", 0) if variants and dec else None,
    }


def check(values: dict[str, float | None], gates: dict[str, float]) -> list[str]:
    """One line per missed gate. A gate is `<metric>_min` or `<metric>_max`."""
    missed = []
    for gate, limit in gates.items():
        metric, kind = gate.rsplit("_", 1)
        value = values.get(metric)
        if value is None:
            missed.append(f"{metric}: no result found (gate {gate}={limit})")
        elif (kind == "min" and value < limit) or (kind == "max" and value > limit):
            missed.append(f"{metric} = {value}, gate {gate} = {limit}")
    return missed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args(argv)
    name = "smoke" if a.smoke else "committed"
    folder = ROOT / "evals" / "results" / ("smoke" if a.smoke else "")
    values, gates = measured(folder), get_settings()["eval_gates"][name]
    missed = check(values, gates)
    for gate in gates:
        metric = gate.rsplit("_", 1)[0]
        print(f"  {'FAIL' if any(m.startswith(metric) for m in missed) else 'ok  '}  {metric} = {values.get(metric)}  ({gate} = {gates[gate]})")
    print(f"eval gate ({name}): " + ("FAILED\n  " + "\n  ".join(missed) if missed else "passed"))
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
