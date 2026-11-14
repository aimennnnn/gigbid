# pricing-insurance

Internal tooling built for a insurance client. The goal was simple: see where we are losing margin.

## Layout
- `src/` main pipeline
- `tests/` checks on the outputs
- `notebooks/` exploration, not used in production

## Notes
Outcome after rollout: identified 60 SKUs sold below cost. Depends on `statsmodels` and `openpyxl`.
