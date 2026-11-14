"""Promotion rules (R7): the ONLY way anything enters long-term memory.

Nothing is written to memory straight from a tool result or a model reply. An edit or an
outcome is first counted as a candidate; it becomes a memory only when the rule below says
it has been seen enough times (thresholds in config: memory.*).
"""
from __future__ import annotations

from agent.guards import sentences
from agent.settings import get_settings


def style_rule_from_edit(before: str, after: str) -> str | None:
    """Turn one user edit into a candidate style rule, or None if no clear pattern."""
    b, a = sentences(before), sentences(after)
    if b and a and b[0] not in after and b[1:2] and b[1] in after:
        return "always cut the first sentence"
    gone = [w for w in ("passionate", "hard-working", "very interested", "dear hiring manager", "i hope you are doing well")
            if w in before.lower() and w not in after.lower()]
    if gone:
        return f"never say '{gone[0]}'"
    if len(after.split()) < 0.75 * len(before.split()):
        return f"keep proposals short (about {round(len(after.split()), -1)} words)"
    return None


def should_promote_style(times_seen: int) -> bool:
    return times_seen >= get_settings()["memory"]["style_promote_after"]


def should_trust_outcomes(proposals_sent: int) -> bool:
    return proposals_sent >= get_settings()["memory"]["outcome_min_samples"]
