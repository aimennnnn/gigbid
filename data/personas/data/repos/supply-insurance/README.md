# supply-insurance

Internal tooling built for a insurance client. The goal was simple: track deliveries and stock in one report.

## Layout
- `src/` main pipeline
- `tests/` checks on the outputs
- `notebooks/` exploration, not used in production

## Notes
Outcome after rollout: reduced late-shipment reporting lag from 5 days to 1. Depends on `ssis` and `dax`.
