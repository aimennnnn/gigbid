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
