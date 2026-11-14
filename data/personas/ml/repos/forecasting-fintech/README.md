# forecasting-fintech

Internal tooling built for a fintech client. The goal was simple: predict how much stock we need each week.

## Layout
- `src/` main pipeline
- `tests/` checks on the outputs
- `notebooks/` exploration, not used in production

## Notes
Outcome after rollout: cut weekly forecast error (MAPE) from 24% to 13%. Depends on `prophet` and `lightgbm`.
