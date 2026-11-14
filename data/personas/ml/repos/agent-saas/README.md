# agent-saas

Internal tooling built for a SaaS client. The goal was simple: have AI agents handle a multi-step back-office task.

## Layout
- `src/` main pipeline
- `tests/` checks on the outputs
- `notebooks/` exploration, not used in production

## Notes
Outcome after rollout: automated 70% of refund cases with human approval on the rest. Depends on `langgraph` and `mcp`.
