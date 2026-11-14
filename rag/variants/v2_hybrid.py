"""V2 hybrid: keyword search (BM25) plus dense search, joined by reciprocal rank fusion.

BM25 catches exact tool names ("dbt", "Celery") that embeddings blur; dense catches
meaning when the words differ. RRF only looks at ranks, so the two score scales never mix.
"""
from __future__ import annotations

from functools import lru_cache

from agent.settings import get_settings
from rag.index.bm25 import BM25Index
from rag.ingest.loaders import load_items
from rag.variants import v0_naive


@lru_cache
def bm25(persona: str) -> BM25Index:
    return BM25Index(list(load_items(persona)))


def keyword_search(persona: str, query: str) -> list[tuple[dict, float]]:
    return bm25(persona).search(query, k=10_000)


def rrf(rankings: list[list[tuple[dict, float]]]) -> list[tuple[dict, float]]:
    """Reciprocal rank fusion: an item's score is the sum of 1 / (k + its rank) over every list it is in."""
    k, score, items = get_settings()["rag"]["rrf_k"], {}, {}
    for ranking in rankings:
        for rank, (item, _) in enumerate(ranking, start=1):
            items[item["id"]] = item
            score[item["id"]] = score.get(item["id"], 0.0) + 1.0 / (k + rank)
    return sorted(((items[i], s) for i, s in score.items()), key=lambda x: -x[1])


def search(persona: str, query: str) -> list[tuple[dict, float]]:
    return rrf([keyword_search(persona, query), v0_naive.search(persona, query)])
