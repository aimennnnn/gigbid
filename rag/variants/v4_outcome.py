"""V4 outcome-aware ranking: learn from what actually worked.

Past proposals are labelled won / replied / ignored and many name the project they cited.
Evidence from a project whose proposals tended to win is lifted; nothing is pushed down
below where it started, and a project never cited in a proposal is left alone.
"""
from __future__ import annotations

from functools import lru_cache

from agent.settings import get_settings
from rag.ingest.loaders import load_items

WORTH = {"won": 1.0, "replied": 0.5, "ignored": 0.0}


@lru_cache
def win_rates(persona: str) -> dict[str, float]:
    """project -> average outcome of the past proposals that cited it (0 = always ignored, 1 = always won)."""
    seen: dict[str, list[float]] = {}
    for p in load_items(persona):
        if p["type"] == "proposal" and p["project"]:
            seen.setdefault(p["project"], []).append(WORTH[p["outcome"]])
    return {project: sum(v) / len(v) for project, v in seen.items()}


def boost(persona: str, hits: list[tuple[dict, float]]) -> list[tuple[dict, float]]:
    rates, weight = win_rates(persona), get_settings()["rag"]["outcome_boost"]
    return sorted(((item, s + weight * rates.get(item["project"], 0.0) * abs(s)) for item, s in hits), key=lambda x: -x[1])
