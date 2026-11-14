"""Applies to every test: use the offline stand-ins for the embedding and reranker models,
so tests never download a model and always give the same result."""
import os

os.environ.setdefault("GIGBID_RAG_MODELS", "fake")
