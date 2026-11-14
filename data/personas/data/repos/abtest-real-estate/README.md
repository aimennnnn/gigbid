# abtest-real-estate

Internal tooling built for a real estate client. The goal was simple: tell us whether the new checkout actually works better.

## Layout
- `src/` main pipeline
- `tests/` checks on the outputs
- `notebooks/` exploration, not used in production

## Notes
Outcome after rollout: found the variant won by 3.1% with 95% confidence. Depends on `scipy` and `statsmodels`.
