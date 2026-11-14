# pwa-telecom

Internal tooling built for a telecom client. The goal was simple: an app that still works when the signal drops.

## Layout
- `src/` main pipeline
- `tests/` checks on the outputs
- `notebooks/` exploration, not used in production

## Notes
Outcome after rollout: let field staff complete 100% of forms offline. Depends on `workbox` and `idb`.
