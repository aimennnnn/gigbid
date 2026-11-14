# Data card

## What data GigBid uses

| Data | Where | Real or synthetic | Made by |
|---|---|---|---|
| Three freelancer personas (CV, 18 case studies, 8 repos, 18 reviews, 150 past proposals each) | `data/personas/` | **Synthetic** | `data/synth/generate.py` |
| 1,500 closed historical jobs with the price paid | `gigsim/seed/jobs_history.json` | **Synthetic** | same script |
| Dev set: 200 jobs per persona with gold labels | `gigsim/seed/jobs_dev.json`, `evals/datasets/dev_*.jsonl` | **Synthetic** | same script |
| Live stream: 60 new jobs with scams, injections and duplicates | `gigsim/seed/jobs_stream.json` | **Synthetic** | same script |
| Clients and their hidden preferences | `gigsim/seed/clients.json`, `hidden.json` | **Synthetic** | same script |
| Policy pack | `data/policy_pack/` | From the course starter kit | instructor |
| Tiny sample files | `data/sample/` | Synthetic, from the starter kit | instructor |

No real client, freelancer or marketplace data is in this repository. Every synthetic job carries
`"synthetic": true` and every persona and client name ends in "(synthetic)".

## Why synthetic

The course starter kit is a scaffold: it has no GigSim, personas or dev set. The course announcement
allows realistic synthetic data where real data is unavailable, clearly marked. So GigSim
(`gigsim/`) and all its data are our own, built to the assignment's description.

## How it is generated

`python -m data.synth.generate` (or `make seed`), fixed seed 4016, so the files are reproducible.
Everything comes from one catalogue of 60 project types (`data/synth/catalog.py`): 20 each for
AI/ML, full-stack web and data analysis. Each type has named skills, a plain-language description
with no tool names, a measured result and a base price.

- **Personas.** Each persona has done 14 of the 20 project types in its field (4 of them twice, in
  different industries). The other 6 are jobs it should skip for lack of evidence.
- **Built to be hard for naive retrieval.** The same project appears three ways: a case study that
  names the skills, a repo whose README never names them (only the imports hint), and a client
  review in plain language.
- **Past proposals.** Outcome (won / replied / ignored) depends on the text: specific openings and a
  cited result win more often than generic openings.
- **Dev set gold labels** come from how each job was built: bid or skip, scam or not, injected or
  not, which portfolio items prove the job (graded 1 to 3), and a fair price band (0.8x to 1.25x of
  the job's true value).
- **Simulated clients** reply, interview or hire by a fixed rule over hidden preferences (two
  must-have skills, a budget ceiling, dislike of generic openings, wanting a measured result).

## Limitations

- Template-generated text is more regular than real job posts, so retrieval scores here are
  probably higher than they would be on real data.
- The simulated client is a rule, not an LLM and not a person. Reply rate measures "matches the
  hidden preferences", which is narrower than real persuasion.
- Prices come from our own base-price table, not from a real market.

## Real datasets (planned)

The course announcement lists Kaggle Upwork datasets. They are not in the repo yet; when added,
this section will record the source, licence, preprocessing and which numbers use them.
