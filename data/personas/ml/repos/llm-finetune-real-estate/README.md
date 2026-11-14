# llm-finetune-real-estate

Internal tooling built for a real estate client. The goal was simple: make an AI model write in our house style.

## Layout
- `src/` main pipeline
- `tests/` checks on the outputs
- `notebooks/` exploration, not used in production

## Notes
Outcome after rollout: improved blind human preference over the base model from 31% to 68%. Depends on `peft` and `bitsandbytes`.
