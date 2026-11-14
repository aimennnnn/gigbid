"""Dense index: every chunk of every evidence item as a vector; search by cosine similarity."""
from __future__ import annotations

from agent.settings import get_settings
from rag.index.embed import embedder
from rag.ingest.chunker import chunks


class VectorIndex:
    def __init__(self, items: list[dict]):
        cfg = get_settings()["rag"]
        self.items = {i["id"]: i for i in items}
        self.chunks = [c for i in items for c in chunks(i, cfg["chunk_words"], cfg["chunk_overlap"])]
        self.vecs = embedder().embed([c["text"] for c in self.chunks], "document")

    def search(self, query: str) -> list[tuple[dict, float]]:
        """Every item, best first. An item's score is the score of its best chunk."""
        sims = self.vecs @ embedder().embed([query], "query")[0]
        best: dict[str, float] = {}
        for c, s in zip(self.chunks, sims):
            best[c["item_id"]] = max(best.get(c["item_id"], -1.0), float(s))
        return sorted(((self.items[i], s) for i, s in best.items()), key=lambda x: -x[1])
