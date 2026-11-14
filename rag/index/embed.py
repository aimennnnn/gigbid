"""Embeddings: text -> vector, with the model named in config (profiles.<name>.embeddings).

Vectors are saved on disk by a hash of the text, so re-indexing after the user adds work
only embeds the new chunks (incremental re-indexing, B1).

GIGBID_RAG_MODELS=fake swaps the model for word hashing: no download, same result every
time. Tests and CI use it. Evaluation numbers must come from the real model.
"""
from __future__ import annotations

import hashlib
import os
import re
from functools import lru_cache
from pathlib import Path

import numpy as np

from agent.settings import get_settings
from rag.index.bm25 import tokenize

CACHE_DIR = Path(os.getenv("RAG_CACHE_DIR", Path(__file__).resolve().parents[2] / "data" / "processed" / "embeddings"))
use_cache = True          # evals switch this off while timing, so the latency is the real cost


def fake() -> bool:
    return os.getenv("GIGBID_RAG_MODELS", "").lower() == "fake"


def _hash_vectors(texts: list[str], dim: int = 512) -> np.ndarray:
    """Stand-in embedding: each word (and word pair) adds 1 to a slot picked by its hash."""
    out = np.zeros((len(texts), dim), dtype=np.float32)
    for row, text in enumerate(texts):
        words = tokenize(text)
        for w in words + [f"{a} {b}" for a, b in zip(words, words[1:])]:
            out[row, int(hashlib.md5(w.encode()).hexdigest()[:8], 16) % dim] += 1.0
    return out


class Embedder:
    def __init__(self) -> None:
        self.name = "hash-512 (offline stand-in)" if fake() else get_settings().profile["embeddings"]
        self.model = None
        self.file = CACHE_DIR / (re.sub(r"[^A-Za-z0-9]+", "-", self.name) + ".npz")
        self.saved: dict[str, np.ndarray] = {}
        if not fake() and self.file.exists():
            data = np.load(self.file)
            self.saved = dict(zip(data["keys"].tolist(), data["vecs"]))

    def _run(self, texts: list[str], kind: str) -> np.ndarray:
        if fake():
            vecs = _hash_vectors(texts)
        else:
            cfg = get_settings()["rag"]
            if self.model is None:
                from fastembed import TextEmbedding      # downloads the model the first time
                self.model = TextEmbedding(self.name, threads=cfg["threads"])
            prefix = cfg["embed_prefix"][kind]
            # small batches on purpose: memory grows with batch size, and a big batch can freeze an 8 GB laptop
            vecs = np.array(list(self.model.embed([prefix + t for t in texts], batch_size=cfg["batch"])), dtype=np.float32)
        return vecs / np.maximum(np.linalg.norm(vecs, axis=1, keepdims=True), 1e-9)    # length 1, so dot product = cosine

    def embed(self, texts: list[str], kind: str = "document") -> np.ndarray:
        """kind is "document" (portfolio chunks) or "query" (a job post or one requirement)."""
        keys = [hashlib.sha1(f"{kind}\n{t}".encode()).hexdigest() for t in texts]
        todo = [i for i, k in enumerate(keys) if k not in self.saved or (kind == "query" and not use_cache)]
        for start in range(0, len(todo), 64):               # 64 texts at a time, saved as it goes: a crash loses little
            part = todo[start:start + 64]
            for i, v in zip(part, self._run([texts[i] for i in part], kind)):
                self.saved[keys[i]] = v
            if kind == "document" and not fake():
                self.file.parent.mkdir(parents=True, exist_ok=True)
                np.savez(self.file, keys=np.array(list(self.saved)), vecs=np.stack(list(self.saved.values())))
                print(f"embedded {min(start + 64, len(todo))}/{len(todo)} new chunks", flush=True)
        return np.stack([self.saved[k] for k in keys])


@lru_cache
def embedder() -> Embedder:
    return Embedder()
