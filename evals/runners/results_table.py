"""Builds the results table (B5) from the result files. It never computes or invents a number.

    uv run python -m evals.runners.results_table            write evals/results/results_table.md and .csv
    uv run python -m evals.runners.results_table --readme   also refresh the table inside README.md

Retrieval columns come from rag_eval.json (every variant). Proposal columns come from
gigsim_outcomes.json and are filled only for the variants that wrote proposals; "-" means not run.
"""
from __future__ import annotations

import argparse
import csv
import json

from evals.runners.common import ROOT, out_dir

START, END = "<!-- results:start -->", "<!-- results:end -->"
HEAD = ["Variant", "Evidence Recall@5", "nDCG@10", "Unsupported claims per proposal (before -> after verification)", "Judge score (1-5)",
        "GigSim reply rate", "p95 latency (s)", "Cost per proposal (USD)", "Retrieval p95 (ms)"]


def load(name: str) -> dict:
    path = out_dir() / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def cell(value, digits: int = 3) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def build() -> tuple[list[list[str]], str]:
    rag, out = load("rag_eval"), load("gigsim_outcomes")
    if not rag:
        raise SystemExit("no rag_eval.json yet: run `make eval` first")
    rows = []
    for name, r in rag["variants"].items():
        o, p = r["overall"], out.get("variants", {}).get(name, {}).get("overall", {})
        claims = f"{cell(p['unsupported_before_per_proposal'], 2)} -> {cell(p['unsupported_after_per_proposal'], 2)}" if p else "-"
        rows.append([name, cell(o["recall_at_5"]), cell(o["ndcg_at_10"]), claims, cell(p.get("judge_score"), 2), cell(p.get("reply_rate"), 2),
                     cell(p.get("p95_s"), 1), cell(p.get("usd_per_proposal"), 5), cell(o.get("p95_ms"), 0)])
    m, where = rag["meta"], out_dir().relative_to(ROOT).as_posix() if out_dir().is_relative_to(ROOT) else str(out_dir())
    note = (f"Retrieval: {rag['jobs']} dev jobs, embeddings `{m['embeddings']}`, reranker `{m['reranker']}`, commit {m['git_commit']} "
            f"(`{where}/rag_eval.json`).")
    if out:
        n = next(iter(out["variants"].values()))["overall"]["jobs"]
        note += (f" Proposals: {n} fixed dev jobs per variant, model `{out['meta']['llm']}`, on {out['meta']['machine']} "
                 f"(`{where}/gigsim_outcomes.json`). Cost is the provider's list price; free tiers and local models cost 0.")
    else:
        note += " Proposal columns are empty until `gigsim_outcomes` has been run."
    return rows, note


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--readme", action="store_true")
    a = ap.parse_args(argv)
    rows, note = build()
    table = "\n".join(["| " + " | ".join(HEAD) + " |", "|" + "---|" * len(HEAD)] + ["| " + " | ".join(r) + " |" for r in rows])
    text = f"{table}\n\n{note}\n"
    (out_dir() / "results_table.md").write_text(text, encoding="utf-8", newline="\n")
    with open(out_dir() / "results_table.csv", "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([HEAD] + rows)
    print(text)
    if a.readme:
        readme = ROOT / "README.md"
        old = readme.read_text(encoding="utf-8")
        block = f"{START}\n{text}{END}"
        new = old[:old.index(START)] + block + old[old.index(END) + len(END):] if START in old and END in old \
            else old.rstrip("\n") + f"\n\n## RAG results\n\nRegenerate with `make eval`.\n\n{block}\n"
        readme.write_text(new, encoding="utf-8", newline="\n")
        print("README.md updated")


if __name__ == "__main__":
    main()
