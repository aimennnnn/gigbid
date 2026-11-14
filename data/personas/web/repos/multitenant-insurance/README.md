# multitenant-insurance

Internal tooling built for a insurance client. The goal was simple: one system that keeps each customer's data separate.

## Layout
- `src/` main pipeline
- `tests/` checks on the outputs
- `notebooks/` exploration, not used in production

## Notes
Outcome after rollout: onboarded 120 tenants with row-level isolation. Depends on `django-tenants` and `celery`.
