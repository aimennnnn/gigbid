# GigBid

A multi-agent freelancer copilot: LangGraph agents find freelance jobs, judge whether
they are worth bidding on, write proposals grounded in real portfolio evidence, and
manage client conversations. A human approves every proposal and message before it
leaves the system.

AI-4016 R&D assignment, FAST-NUCES. Work in progress; results, live link and traces are added as they are measured.

## Run the tests

```
uv sync
uv run pytest -q
```

## Run the evaluations

```
uv run python -m evals.runners.run_all --only rag     # retrieval + ablation, no LLM
uv run python -m evals.runners.run_all                # everything (same as `make eval`)
uv run python -m evals.runners.run_all --smoke        # 30 jobs with stand-in models, no network
```

Results are written to `evals/results/*.json`; `evals/runners/results_table.py` turns them into the table below.
`evals/kaggle_eval.ipynb` runs the same thing on a free Kaggle GPU with a local model.

## RAG results

Regenerate with `make eval`.

<!-- results:start -->
| Variant | Evidence Recall@5 | nDCG@10 | Unsupported claims per proposal (before -> after verification) | Judge score (1-5) | GigSim reply rate | p95 latency (s) | Cost per proposal (USD) | Retrieval p95 (ms) |
|---|---|---|---|---|---|---|---|---|
| keyword | 0.572 | 0.705 | - | - | - | - | - | 3 |
| v0_naive | 0.806 | 0.890 | 0.03 -> 0.00 | 4.23 | 0.83 | 99.4 | 0.00000 | 153 |
| v1_decompose | 0.651 | 0.764 | - | - | - | - | - | 220 |
| v2_hybrid | 0.889 | 0.917 | - | - | - | - | - | 155 |
| v3_rerank | 0.771 | 0.877 | - | - | - | - | - | 1152 |
| v4_outcome | 0.702 | 0.822 | - | - | - | - | - | 154 |
| v8_corrective | 0.556 | 0.709 | - | - | - | - | - | 3224 |
| hybrid_corrective | 0.557 | 0.704 | - | - | - | - | - | 3126 |
| all_steps | 0.586 | 0.729 | - | - | - | - | - | 24200 |
| best | 0.889 | 0.917 | 0.00 -> 0.00 | 4.07 | 0.77 | 85.6 | 0.00000 | 157 |

Retrieval: 600 dev jobs, embeddings `nomic-ai/nomic-embed-text-v1.5`, reranker `Xenova/ms-marco-MiniLM-L-6-v2`, commit 2ba4e4d (`evals/results/rag_eval.json`). Proposals: 30 fixed dev jobs per variant, model `ollama: gpt-oss:20b / gpt-oss:20b`, on Linux x86_64, 4 CPU cores, x86_64 (`evals/results/gigsim_outcomes.json`). Cost is the provider's list price; free tiers and local models cost 0.
<!-- results:end -->
