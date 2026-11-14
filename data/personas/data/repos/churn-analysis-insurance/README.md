# churn-analysis-insurance

Internal tooling built for a insurance client. The goal was simple: explain why customers cancel.

## Layout
- `src/` main pipeline
- `tests/` checks on the outputs
- `notebooks/` exploration, not used in production

## Notes
Outcome after rollout: showed onboarding delay explained most early churn. Depends on `lifelines` and `pandas`.
