"""Keyword index (BM25). Good at exact tool names like "dbt" or "Celery" that embeddings blur."""
from __future__ import annotations

import re

from rank_bm25 import BM25Okapi


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9+#.\-]*[a-z0-9+#]|[a-z0-9]", text.lower())


class BM25Index:
    def __init__(self, docs: list[dict]):
        self.docs = docs
        self.bm25 = BM25Okapi([tokenize(d["title"] + " " + d["text"] + " " + " ".join(d["skills"])) for d in docs])

    def search(self, query: str, k: int = 5) -> list[tuple[dict, float]]:
        scores = self.bm25.get_scores(tokenize(query))
        order = sorted(range(len(self.docs)), key=lambda i: scores[i], reverse=True)[:k]
        return [(self.docs[i], float(scores[i])) for i in order if scores[i] > 0]
