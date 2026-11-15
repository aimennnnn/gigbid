"""The LLM judge, and the check that it can be trusted (B4).

The judge gives each finished proposal a score from 1 to 5. The rubric is the prompt
file agent/prompts/judge.md. A judge is only worth reporting if it agrees with a person,
so 30 proposals are also scored by hand and the agreement is measured with Cohen's kappa.

    uv run python -m evals.runners.judge_calibration --sheet   write evals/datasets/judge_labels.csv (30 proposals, no judge scores)
    ... fill in the human_score column (1 to 5, same rubric) ...
    uv run python -m evals.runners.judge_calibration           write evals/results/judge_calibration.json

    uv run python -m evals.runners.judge_calibration --pairs   write evals/datasets/pairwise_panel.csv for classmates (blind A/B)
    ... classmates fill in the winner column (A, B or tie) ...
    uv run python -m evals.runners.judge_calibration --tally   write evals/results/pairwise_panel.json

Proposals come from evals/results/proposals_<variant>.jsonl, written by gigsim_outcomes.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from typing import Annotated

from pydantic import BaseModel, Field

from agent.llm import ask
from evals.runners.common import ROOT, out_dir, save

LABELS = ROOT / "evals" / "datasets" / "judge_labels.csv"
PAIRS = ROOT / "evals" / "datasets" / "pairwise_panel.csv"


class JudgeScore(BaseModel):
    score: Annotated[int, Field(ge=1, le=5)]
    reasons: list[str] = []


async def judge(job: dict, proposal: str, evidence: list[dict]) -> tuple[JudgeScore, int]:
    return await ask("judge", {"job_post": job, "proposal": proposal, "evidence": evidence}, JudgeScore, untrusted=("job_post", "proposal"))


def kappa(a: list[int], b: list[int], weighted: bool = False) -> float:
    """Cohen's kappa: agreement between two raters beyond what chance alone would give.
    1 = perfect, 0 = no better than chance. Weighted: being 1 point apart costs less than 4 apart."""
    cats, n = sorted(set(a) | set(b)), len(a)
    span = max(1, cats[-1] - cats[0])

    def cost(x: int, y: int) -> float:
        return ((x - y) / span) ** 2 if weighted else float(x != y)
    seen = sum(cost(x, y) for x, y in zip(a, b)) / n
    chance = sum(a.count(x) / n * b.count(y) / n * cost(x, y) for x in cats for y in cats)
    return round(1 - seen / chance, 4) if chance else 1.0


def proposals() -> list[dict]:
    rows = [json.loads(line) for f in sorted(out_dir().glob("proposals_*.jsonl")) for line in f.read_text(encoding="utf-8").splitlines()]
    return [r for r in rows if r.get("letter")]


def write_csv(path, header: list[str], rows: list[list]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([header] + rows)
    print(f"wrote {path.relative_to(ROOT)} ({len(rows)} rows)")


def make_sheet(n: int = 30) -> None:
    rows = proposals()
    random.Random(4016).shuffle(rows)                     # fixed seed: the same 30 every time
    write_csv(LABELS, ["id", "job_title", "job_post", "evidence_shown", "proposal", "human_score"],
              [[f"{r['variant']}|{r['job_id']}", r["job_title"], r["job_post"], " || ".join(r["evidence"]), r["letter"], ""] for r in rows[:n]])
    print("Score each proposal 1 to 5 in the human_score column, using the rubric in agent/prompts/judge.md.")


def calibrate() -> None:
    if not LABELS.exists():
        return print("no evals/datasets/judge_labels.csv yet: run with --sheet, label it, then run again")
    judged = {f"{r['variant']}|{r['job_id']}": r for r in proposals()}
    rows = [r for r in csv.DictReader(open(LABELS, encoding="utf-8")) if r["human_score"].strip() and r["id"] in judged]
    if len(rows) < 2:
        return print("judge_labels.csv has no human scores yet: fill in the human_score column")
    human, model = [int(r["human_score"]) for r in rows], [judged[r["id"]]["judge_score"] for r in rows]
    apart = sorted(rows, key=lambda r: -abs(int(r["human_score"]) - judged[r["id"]]["judge_score"]))[:5]
    run = out_dir() / "gigsim_outcomes.json"  # the run that produced the judge scores; "meta" below is only this calculation
    save("judge_calibration", {
        "judge_scores_from": json.loads(run.read_text(encoding="utf-8"))["meta"] if run.exists() else None,
        "items": len(rows), "kappa": kappa(human, model), "weighted_kappa": kappa(human, model, weighted=True),
        "kappa_pass_fail": kappa([int(h >= 4) for h in human], [int(m >= 4) for m in model]),
        "exact_agreement": round(sum(h == m for h, m in zip(human, model)) / len(rows), 4),
        "within_one_point": round(sum(abs(h - m) <= 1 for h, m in zip(human, model)) / len(rows), 4),
        "biggest_disagreements": [{"id": r["id"], "human": int(r["human_score"]), "judge": judged[r["id"]]["judge_score"],
                                   "judge_reasons": judged[r["id"]]["judge_reasons"], "proposal": r["proposal"]} for r in apart]})


def make_pairs(first: str, second: str) -> None:
    """Same job, one proposal from each variant, shown as A and B in a random order."""
    by = {(r["variant"], r["job_id"]): r for r in proposals()}
    rng, rows, key = random.Random(4016), [], {}
    for job_id in sorted({j for v, j in by if v == first} & {j for v, j in by if v == second}):
        a, b = (first, second) if rng.random() < 0.5 else (second, first)
        key[job_id] = {"A": a, "B": b}
        rows.append([job_id, by[a, job_id]["job_title"], by[a, job_id]["job_post"], by[a, job_id]["letter"], by[b, job_id]["letter"], ""])
    write_csv(PAIRS, ["job_id", "job_title", "job_post", "proposal_A", "proposal_B", "winner"], rows)
    (out_dir() / "pairwise_key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    print("Do not show pairwise_key.json to the panel. They fill in winner with A, B or tie.")


def tally() -> None:
    key, wins = json.loads((out_dir() / "pairwise_key.json").read_text(encoding="utf-8")), {}
    for r in csv.DictReader(open(PAIRS, encoding="utf-8")):
        pick = r["winner"].strip().upper()
        if pick:
            name = key[r["job_id"]].get(pick, "tie")
            wins[name] = wins.get(name, 0) + 1
    save("pairwise_panel", {"votes": sum(wins.values()), "wins": wins})


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", action="store_true")
    ap.add_argument("--pairs", action="store_true")
    ap.add_argument("--tally", action="store_true")
    ap.add_argument("--variants", default="v0_naive,best", help="the two variants compared by --pairs")
    a = ap.parse_args(argv)
    if a.sheet:
        make_sheet()
    elif a.pairs:
        make_pairs(*a.variants.split(",")[:2])
    elif a.tally:
        tally()
    else:
        calibrate()


if __name__ == "__main__":
    main()
