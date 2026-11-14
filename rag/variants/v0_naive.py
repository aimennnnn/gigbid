"""V0 naive dense (the baseline everything else must beat).

Fixed-size chunks, one embedding per chunk, and the query is ranked against them by
cosine similarity. Nothing else: no keywords, no reranking, no query rewriting.
"""
from __future__ import annotations

from functools import lru_cache

from rag.index.vector import VectorIndex
from rag.ingest.loaders import load_items


@lru_cache
def index(persona: str) -> VectorIndex:
    return VectorIndex(list(load_items(persona)))


def search(persona: str, query: str) -> list[tuple[dict, float]]:
    """Every portfolio item with its cosine score, best first."""
    return index(persona).search(query)
