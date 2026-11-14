"""V1 requirement decomposition: one search per requirement instead of one for the whole post.

A job that asks for five different things gets five small, focused queries. The result
lists are merged with reciprocal rank fusion (see v2_hybrid.rrf).
"""
from __future__ import annotations

from agent.guards import sentences


def whole_post(job: dict) -> str:
    """The query when the job is NOT decomposed: title and description as one text."""
    return f"{job['title']}. {job['description']}"[:500]


def requirements(job: dict) -> list[str]:
    """The job's main need (its title) first, then one line per named skill.
    A vague post with no skills gives the title plus its "we want ..." sentences."""
    if job.get("skills"):
        return [job["title"]] + [f"Experience with {s}" for s in job["skills"]]
    return [job["title"]] + [s for s in sentences(job["description"]) if "want" in s.lower()][:2]
