"""Retriever factory: the one place the Portfolio server, the agents and the evals get evidence from.

Which RAG variant answers is chosen by config (rag.variant, or env GIGBID_RAG_VARIANT),
never by the caller. A variant is a list of steps; each step lives in rag/variants/:

    decompose   v1  one query per requirement instead of the whole job post
    hybrid      v2  BM25 + dense, fused            (bm25 = keyword only; neither = dense only, V0)
    rerank      v3  cross-encoder reorders the candidates
    outcome     v4  boost projects whose past proposals won
    corrective  v8  grade the evidence, re-query when weak, return nothing when none

search()   answers ONE query (what the Portfolio tool search_evidence calls).
retrieve() answers a whole JOB: it makes the queries, searches each, and merges the lists.
"""
from __future__ import annotations

import os

from agent.settings import get_settings
from rag.ingest.loaders import load_items
from rag.variants import v0_naive, v1_decompose, v2_hybrid, v3_rerank, v4_outcome, v8_corrective


def steps(variant: str | None = None) -> list[str]:
    cfg = get_settings()["rag"]
    name = variant or os.getenv("GIGBID_RAG_VARIANT") or cfg["variant"]
    if name not in cfg["variants"]:
        raise ValueError(f"unknown RAG variant '{name}': add it under rag.variants in agent/config.yaml")
    return cfg["variants"][name]


def _keep(item: dict, filters: dict) -> bool:
    return ((not filters.get("types") or item["type"] in filters["types"])
            and (not filters.get("outcomes") or item["outcome"] in filters["outcomes"])
            and (not filters.get("client_industry") or item["client_industry"] == filters["client_industry"])
            and (not filters.get("date_from") or (item["date"] or "") >= filters["date_from"]))


def _once(persona: str, query: str, todo: list[str], filters: dict, how: str = "normal") -> list[tuple[dict, float]]:
    """One plain search: first stage -> filter -> candidates -> rerank -> outcome boost."""
    if how == "keyword" or "bm25" in todo:
        hits = v2_hybrid.keyword_search(persona, query)
    elif "hybrid" in todo:
        hits = v2_hybrid.search(persona, query)
    else:
        hits = v0_naive.search(persona, query)
    n = get_settings()["rag"]["candidates"] * (3 if how == "wide" else 1)
    hits = [h for h in hits if _keep(h[0], filters)][:n]
    if "rerank" in todo:
        hits = v3_rerank.rerank(query, hits)
    if "outcome" in todo:
        hits = v4_outcome.boost(persona, hits)
    return hits


def search(persona: str, query: str, k: int = 5, filters: dict | None = None, variant: str | None = None) -> list[tuple[dict, float]]:
    """Evidence for one query, best first. With the corrective step the list can be empty."""
    todo, filters = steps(variant), filters or {}
    if "corrective" in todo:
        return v8_corrective.search(query, lambda q, how: _once(persona, q, todo, filters, how))[:k]
    return _once(persona, query, todo, filters)[:k]


def queries(job: dict, variant: str | None = None) -> list[str]:
    """What to search for: each requirement if the variant decomposes, else the whole post. Main need first."""
    return v1_decompose.requirements(job) if "decompose" in steps(variant) else [v1_decompose.whole_post(job)]


def retrieve(persona: str, job: dict, k: int = 10, variant: str | None = None) -> list[tuple[dict, float]]:
    """Evidence for a whole job. Only the evidence types named in config count as proof."""
    cfg = get_settings()["rag"]
    lists = [search(persona, q, cfg["candidates"], {"types": cfg["evidence_types"]}, variant) for q in queries(job, variant)]
    if "corrective" in steps(variant) and not lists[0]:
        return []                          # nothing proves the job's main need: refuse instead of padding with loose matches
    return (v2_hybrid.rrf(lists) if len(lists) > 1 else lists[0])[:k]


def reindex(persona: str | None = None) -> None:
    """Call after the user adds or changes portfolio work. Chunks already embedded are read
    from the disk cache, so only new text is embedded."""
    load_items.cache_clear()
    v0_naive.index.cache_clear()
    v2_hybrid.bm25.cache_clear()
    v4_outcome.win_rates.cache_clear()
