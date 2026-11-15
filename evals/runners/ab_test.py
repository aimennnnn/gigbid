"""Signature extension X2: proposal experiments. Two proposal strategies as an A/B test in GigSim,
with a significance test on reply rate.

    uv run python -m evals.runners.ab_test                       A = v0_naive, B = best (the two committed runs)
    uv run python -m evals.runners.ab_test --a v0_naive --b best --event hired

Reads evals/results/proposals_<strategy>.jsonl (written by gigsim_outcomes) and writes ab_test.json.
Both strategies were run on the SAME fixed jobs, so there are two tests:
  - McNemar's exact test on the pairs (the right one here: each job is its own control)
  - Fisher's exact test on the two totals (what you would use if the job sets were different)
No SciPy: both tests are a few lines of exact arithmetic, checked against known values in tests/unit/test_evals.py.
"""
from __future__ import annotations

import argparse
import json
import math

from evals.runners.common import out_dir, save

Z95, Z80 = 1.959964, 0.841621


def fisher_exact(a: int, b: int, c: int, d: int) -> float:
    """Two-sided p for the table [[a, b], [c, d]]: the chance of a table at least as unlikely as this one."""
    row1, row2, col1, n = a + b, c + d, a + c, a + b + c + d

    def p(x: int) -> float:
        return math.comb(row1, x) * math.comb(row2, col1 - x) / math.comb(n, col1)
    seen = p(a)
    return min(1.0, sum(p(x) for x in range(max(0, col1 - row2), min(row1, col1) + 1) if p(x) <= seen * (1 + 1e-9)))


def mcnemar_exact(only_a: int, only_b: int) -> float:
    """Two-sided exact p for paired yes/no outcomes. Only the pairs that disagree carry information."""
    n, k = only_a + only_b, min(only_a, only_b)
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def wilson(successes: int, n: int) -> list[float]:
    """95% interval for a rate; behaves well for small n and rates near 0 or 1."""
    if n == 0:
        return [0.0, 1.0]
    p, z2 = successes / n, Z95 ** 2
    mid, half = (p + z2 / (2 * n)) / (1 + z2 / n), Z95 * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    return [round(max(0.0, mid - half), 4), round(min(1.0, mid + half), 4)]


def jobs_needed(p1: float, p2: float) -> int | None:
    """Jobs per strategy to see a difference this size at the usual 5% level with 80% power."""
    if p1 == p2:
        return None
    return math.ceil((Z95 + Z80) ** 2 * (p1 * (1 - p1) + p2 * (1 - p2)) / (p1 - p2) ** 2)


def compare(rows_a: list[dict], rows_b: list[dict], event: str) -> dict:
    a = {r["job_id"]: event in r["events"] for r in rows_a if r.get("letter")}
    b = {r["job_id"]: event in r["events"] for r in rows_b if r.get("letter")}
    both = sorted(set(a) & set(b))
    ya, yb = sum(a.values()), sum(b.values())
    only_a, only_b = sum(a[j] and not b[j] for j in both), sum(b[j] and not a[j] for j in both)
    pa, pb = ya / len(a), yb / len(b)
    p_paired, p_unpaired = mcnemar_exact(only_a, only_b), fisher_exact(ya, len(a) - ya, yb, len(b) - yb)
    return {"event": event,
            "a": {"proposals": len(a), "yes": ya, "rate": round(pa, 4), "ci95": wilson(ya, len(a))},
            "b": {"proposals": len(b), "yes": yb, "rate": round(pb, 4), "ci95": wilson(yb, len(b))},
            "difference_b_minus_a": round(pb - pa, 4),
            "paired": {"jobs": len(both), "only_a": only_a, "only_b": only_b, "both": sum(a[j] and b[j] for j in both),
                       "neither": sum(not a[j] and not b[j] for j in both), "mcnemar_exact_p": round(p_paired, 4)},
            "unpaired": {"fisher_exact_p": round(p_unpaired, 4)},
            "significant_at_0.05": p_paired < 0.05,
            "jobs_per_strategy_to_detect_this_difference": jobs_needed(pa, pb)}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="v0_naive")
    ap.add_argument("--b", default="best")
    ap.add_argument("--event", default="replied", choices=["replied", "interview", "hired", "viewed"])
    args = ap.parse_args(argv)

    def load(name: str) -> list[dict]:
        return [json.loads(line) for line in (out_dir() / f"proposals_{name}.jsonl").read_text(encoding="utf-8").splitlines()]
    run = out_dir() / "gigsim_outcomes.json"
    result = {"strategy_a": args.a, "strategy_b": args.b,
              "proposals_from": json.loads(run.read_text(encoding="utf-8"))["meta"] if run.exists() else None,
              "tests": [compare(load(args.a), load(args.b), e) for e in dict.fromkeys([args.event, "replied", "hired"])]}
    save("ab_test", result)
    for t in result["tests"]:
        print(f"{t['event']}: A {t['a']['yes']}/{t['a']['proposals']} ({t['a']['rate']})  B {t['b']['yes']}/{t['b']['proposals']} ({t['b']['rate']})  "
              f"McNemar p={t['paired']['mcnemar_exact_p']}  Fisher p={t['unpaired']['fisher_exact_p']}  "
              f"{'significant' if t['significant_at_0.05'] else 'not significant'}; "
              f"jobs per strategy needed for this gap: {t['jobs_per_strategy_to_detect_this_difference']}")


if __name__ == "__main__":
    main()
