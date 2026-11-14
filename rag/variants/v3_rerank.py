"""V3 cross-encoder reranking: a second, slower model reads the query and each candidate
together and gives a relevance score. Used to reorder the first-stage candidates.

The model is named in config (profiles.<name>.reranker). Scores are squashed to 0..1.
GIGBID_RAG_MODELS=fake swaps it for a word-overlap score (tests and CI only).
"""
from __future__ import annotations

import atexit
import json
import math
import re
from functools import lru_cache

from agent.settings import get_settings
from rag.index.bm25 import tokenize
from rag.index.embed import CACHE_DIR, fake

FILLER = {"experience", "with", "need", "help", "company", "business", "want", "looking", "freelancer", "deliver",
          "for", "the", "and", "our", "are", "that", "you", "this", "from", "please", "small"}
use_cache = True                                 # evals switch this off while timing
_seen: dict[tuple[str, str], float] = {}         # (query, item id) -> score, so the same pair is never scored twice
_new = 0                                         # scores worked out in this run and not yet saved to disk


def _file():
    name = re.sub(r"[^A-Za-z0-9]+", "-", get_settings().profile["reranker"])
    return CACHE_DIR.parent / "rerank" / f"{name}-{get_settings()['rag']['rerank_chars']}.json"


def _save() -> None:
    """Scores are kept on disk too: the ablation and the threshold sweep score the same pairs again and again."""
    if _new and not fake():
        _file().parent.mkdir(parents=True, exist_ok=True)
        _file().write_text(json.dumps({f"{q}\t{i}": round(s, 5) for (q, i), s in _seen.items()}), encoding="utf-8")


atexit.register(_save)


@lru_cache
def _model():
    if _file().exists():
        _seen.update({tuple(k.rsplit("\t", 1)): v for k, v in json.loads(_file().read_text(encoding="utf-8")).items()})
    from fastembed.rerank.cross_encoder import TextCrossEncoder     # downloads the model the first time
    return TextCrossEncoder(get_settings().profile["reranker"], threads=get_settings()["rag"]["threads"])


def _overlap(query: str, text: str) -> float:
    """Stand-in score: the share of the query's meaningful words that appear in the text."""
    want = {w for w in tokenize(query) if len(w) > 2 and w not in FILLER}
    return len(want & set(tokenize(text))) / len(want) if want else 0.0


def scores(query: str, items: list[dict]) -> list[float]:
    """How well each item answers the query, from 0 (unrelated) to 1."""
    global _new
    if not fake():
        _model()                                             # also loads the scores saved by earlier runs
    todo = [i for i in items if not use_cache or (query, i["id"]) not in _seen]
    if todo:
        if _new // 2000 != (_new + len(todo)) // 2000:
            _save()                                          # checkpoint: a stopped run keeps the scores it already paid for
        _new += len(todo)
        texts = [f"{i['title']}. {i['text']}"[:get_settings()["rag"]["rerank_chars"]] for i in todo]
        new = [_overlap(query, t) for t in texts] if fake() else [1 / (1 + math.exp(-x)) for x in _model().rerank(query, texts, batch_size=get_settings()["rag"]["batch"])]
        _seen.update({(query, i["id"]): s for i, s in zip(todo, new)})
    return [_seen[(query, i["id"])] for i in items]


def rerank(query: str, hits: list[tuple[dict, float]]) -> list[tuple[dict, float]]:
    new = scores(query, [item for item, _ in hits])
    return sorted(((item, s) for (item, _), s in zip(hits, new)), key=lambda x: -x[1])
