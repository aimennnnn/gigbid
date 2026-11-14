# cms-e-commerce

Internal tooling built for a e-commerce client. The goal was simple: move our blog off the old site builder without losing rankings.

## Layout
- `src/` main pipeline
- `tests/` checks on the outputs
- `notebooks/` exploration, not used in production

## Notes
Outcome after rollout: kept 100% of indexed URLs and halved page weight. Depends on `contentful` and `wpgraphql`.
