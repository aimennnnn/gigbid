# Signature extension: X2, proposal experiments

**What it is.** Two proposal strategies are run as an A/B test in GigSim, and the difference in reply
rate gets a significance test, so "B looks better" is never decided by eye.

**What was built.** `evals/runners/ab_test.py`. It reads the proposals each strategy wrote
(`evals/results/proposals_<strategy>.jsonl`, from `gigsim_outcomes`), compares what GigSim's clients did,
and writes `evals/results/ab_test.json`.

```
uv run python -m evals.runners.ab_test                       # A = v0_naive, B = best
uv run python -m evals.runners.ab_test --a v0_naive --b best --event hired
```

- Both strategies bid on the **same 30 fixed dev jobs**, so each job is its own control. The right test for
  that is **McNemar's exact test** on the pairs. **Fisher's exact test** on the two totals is reported too,
  for the case where the job sets differ.
- Each rate comes with a 95% Wilson interval.
- It also says how many jobs per strategy would be needed to detect a gap of the observed size
  (5% level, 80% power).
- No SciPy. The tests are exact arithmetic, checked against textbook values in `tests/unit/test_evals.py`.

**The two strategies compared.** A = proposals written from dense-only retrieval (`v0_naive`).
B = proposals written from hybrid retrieval (`best`). Everything else is the same: model
(`gpt-oss:20b`), prompts, pricing, jobs.

## Result (real model, Kaggle run of 14 Nov, commit 2ba4e4d)

| | A: dense only | B: hybrid |
|---|---|---|
| Proposals | 30 | 30 |
| Replies | 25 (83%, 95% CI 66% to 93%) | 23 (77%, 95% CI 59% to 88%) |
| Hires | 6 | 6 |

| Pairs (same job) | Jobs |
|---|---|
| Both got a reply | 20 |
| Only A got a reply | 5 |
| Only B got a reply | 3 |
| Neither | 2 |

- Reply rate: McNemar exact p = 0.73, Fisher exact p = 0.75. **Not significant.**
- Hire rate: identical (6 and 6), p = 1.0.
- To detect a gap of this size (6.7 points) you would need about **562 jobs per strategy**. 30 is far too few.

**What it changed.** The shipped retrieval variant was chosen on retrieval quality and cost, not on reply
rate, because this test says the reply rates cannot be told apart.

## Limits

- The "strategies" are two retrieval variants, not two writing styles. The script takes any two strategy
  names, but only this pair has been run.
- One run per strategy. The model's own run-to-run variation is not measured.
- GigSim's client is a fixed rule over hidden preferences, not a person.
- The A/B test is an evaluation script. It is not a screen in the web app.
