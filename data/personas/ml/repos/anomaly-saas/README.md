# anomaly-saas

Internal tooling built for a SaaS client. The goal was simple: warn us when a machine starts behaving oddly.

## Layout
- `src/` main pipeline
- `tests/` checks on the outputs
- `notebooks/` exploration, not used in production

## Notes
Outcome after rollout: flagged 9 of 10 real failures a median of 14 hours early. Depends on `sklearn` and `kafka`.
