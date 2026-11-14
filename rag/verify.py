"""Claim verification (B3): no sentence may claim experience the portfolio does not support.

1. split the cover letter into claims (the writer's own list, plus any sentence that
   talks about past work but was not listed)
2. label each claim against the evidence: supported / partly / unsupported
3. cut every sentence that is not fully supported, before the Critic sees the draft
"""
from __future__ import annotations

import re

from agent.guards import sentences
from agent.handoffs import Claim, VerifiedClaims
from agent.llm import ask

EXPERIENCE = re.compile(r"\b(i|my|we)\b.*\b(built|delivered|led|designed|trained|migrated|worked|experience|years|clients?)\b|\d+ ?%|\bon a similar project\b", re.I)


def split_claims(letter: str, listed: list[Claim]) -> list[Claim]:
    known = " ".join(c.text for c in listed)
    extra = [Claim(text=s) for s in sentences(letter) if EXPERIENCE.search(s) and s not in known and not s.endswith("?")]
    return list(listed) + extra


async def verify(claims: list[Claim], evidence: list[dict]) -> tuple[list[Claim], int]:
    if not claims:
        return [], 0
    out, tokens = await ask("verifier", {"claims": [c.model_dump() for c in claims], "evidence": evidence}, VerifiedClaims)
    return out.claims, tokens


def remove_unsupported(letter: str, claims: list[Claim]) -> str:
    bad = [c.text for c in claims if c.status != "supported"]
    kept = [s for s in sentences(letter) if not any(s in b or b in s for b in bad)]
    return " ".join(kept)


def unsupported_rate(claims: list[Claim]) -> float:
    return sum(c.status != "supported" for c in claims) / len(claims) if claims else 0.0
