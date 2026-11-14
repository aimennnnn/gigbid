# ner-e-commerce

Internal tooling built for a e-commerce client. The goal was simple: pull names, dates and amounts out of contracts.

## Layout
- `src/` main pipeline
- `tests/` checks on the outputs
- `notebooks/` exploration, not used in production

## Notes
Outcome after rollout: extracted 14 entity types at 92% F1 and halved review time. Depends on `spacy` and `seqeval`.
