"""Retriever factory: the one function the Portfolio server and the agents call.

Which RAG variant answers is chosen by config (rag.variant), never by the caller.
Until the variants are compared (Part B) the default is the keyword baseline.
"""
from __future__ import annotations

from functools import lru_cache

from rag.index.bm25 import BM25Index
from rag.ingest.loaders import load_items


@lru_cache
def _bm25(persona: str) -> BM25Index:
    return BM25Index(list(load_items(persona)))


def _keep(item: dict, filters: dict) -> bool:
    return ((not filters.get("types") or item["type"] in filters["types"])
            and (not filters.get("outcomes") or item["outcome"] in filters["outcomes"])
            and (not filters.get("client_industry") or item["client_industry"] == filters["client_industry"])
            and (not filters.get("date_from") or (item["date"] or "") >= filters["date_from"]))


def search(persona: str, query: str, k: int = 5, filters: dict | None = None) -> list[tuple[dict, float]]:
    hits = _bm25(persona).search(query, k=200)
    return [(i, s) for i, s in hits if _keep(i, filters or {})][:k]
