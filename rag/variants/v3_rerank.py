"""V3 cross-encoder reranking: a second, slower model reads the query and each candidate
together and gives a relevance score. Used to reorder the first-stage candidates.

The model is named in config (profiles.<name>.reranker). Scores are squashed to 0..1.
GIGBID_RAG_MODELS=fake swaps it for a word-overlap score (tests and CI only).
"""
from __future__ import annotations

import math
from functools import lru_cache

from agent.settings import get_settings
from rag.index.bm25 import tokenize
from rag.index.embed import fake

FILLER = {"experience", "with", "need", "help", "company", "business", "want", "looking", "freelancer", "deliver",
          "for", "the", "and", "our", "are", "that", "you", "this", "from", "please", "small"}
use_cache = True                                 # evals switch this off while timing
_seen: dict[tuple[str, str], float] = {}         # (query, item id) -> score, so the same pair is never scored twice


@lru_cache
def _model():
    from fastembed.rerank.cross_encoder import TextCrossEncoder     # downloads the model the first time
    return TextCrossEncoder(get_settings().profile["reranker"], threads=get_settings()["rag"]["threads"])


def _overlap(query: str, text: str) -> float:
    """Stand-in score: the share of the query's meaningful words that appear in the text."""
    want = {w for w in tokenize(query) if len(w) > 2 and w not in FILLER}
    return len(want & set(tokenize(text))) / len(want) if want else 0.0


def scores(query: str, items: list[dict]) -> list[float]:
    """How well each item answers the query, from 0 (unrelated) to 1."""
    todo = [i for i in items if not use_cache or (query, i["id"]) not in _seen]
    if todo:
        texts = [f"{i['title']}. {i['text']}"[:1500] for i in todo]
        new = [_overlap(query, t) for t in texts] if fake() else [1 / (1 + math.exp(-x)) for x in _model().rerank(query, texts, batch_size=get_settings()["rag"]["batch"])]
        _seen.update({(query, i["id"]): s for i, s in zip(todo, new)})
    return [_seen[(query, i["id"])] for i in items]


def rerank(query: str, hits: list[tuple[dict, float]]) -> list[tuple[dict, float]]:
    new = scores(query, [item for item, _ in hits])
    return sorted(((item, s) for (item, _), s in zip(hits, new)), key=lambda x: -x[1])
