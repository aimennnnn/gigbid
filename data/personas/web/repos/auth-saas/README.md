# auth-saas

Internal tooling built for a SaaS client. The goal was simple: let staff sign in with their company account.

## Layout
- `src/` main pipeline
- `tests/` checks on the outputs
- `notebooks/` exploration, not used in production

## Notes
Outcome after rollout: removed 300 password-reset tickets a month. Depends on `passport` and `jose`.
