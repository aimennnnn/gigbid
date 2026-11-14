"""RAG pieces, run with the offline stand-in models (see conftest.py at the repo root)."""
import json

import numpy as np
import pytest

from rag import retriever
from rag.index.embed import embedder
from rag.ingest.chunker import chunks
from rag.variants import v1_decompose, v2_hybrid, v4_outcome

JOBS = {j["job_id"]: j for j in json.load(open("gigsim/seed/jobs_dev.json", encoding="utf-8"))}
DEV = [json.loads(line) for line in open("evals/datasets/dev_ml.jsonl", encoding="utf-8")]
FIT = next(JOBS[r["job_id"]] for r in DEV if r["kind"] == "fit" and JOBS[r["job_id"]]["skills"])
VARIANTS = ["keyword", "v0_naive", "v1_decompose", "v2_hybrid", "v3_rerank", "v4_outcome", "v8_corrective", "best"]


def item(text="one two three four five six seven eight nine ten"):
    return {"id": "ml:case:x", "text": text, "persona": "ml", "type": "case", "project": "x", "skills": ["Python"],
            "date": "2025-01-01", "client_industry": "retail", "outcome": None}


def test_chunks_are_fixed_size_overlap_and_keep_metadata():
    out = chunks(item(), size=4, overlap=1)
    assert [c["text"] for c in out] == ["one two three four", "four five six seven", "seven eight nine ten"]
    assert all(c["item_id"] == "ml:case:x" and c["skills"] == ["Python"] and c["type"] == "case" for c in out)
    assert len(chunks(item("short text"), size=4, overlap=1)) == 1


def test_stand_in_embeddings_are_repeatable_and_unit_length():
    a, b = embedder().embed(["fraud detection with XGBoost"], "query"), embedder().embed(["fraud detection with XGBoost"], "query")
    assert np.array_equal(a, b) and abs(float(np.linalg.norm(a[0])) - 1.0) < 1e-5


def test_rrf_puts_an_item_found_by_both_lists_first():
    a, b, c = ({"id": x} for x in "abc")
    merged = v2_hybrid.rrf([[(a, 9.0), (b, 1.0)], [(c, 0.9), (b, 0.8)]])
    assert [i["id"] for i, _ in merged][0] == "b"


@pytest.mark.parametrize("variant", VARIANTS)
def test_every_variant_returns_only_proof_types_for_a_job(variant):
    hits = retriever.retrieve("ml", FIT, 5, variant)
    assert hits and len(hits) <= 5 and all(i["type"] in ("case", "repo", "review") for i, _ in hits)


def test_decompose_makes_one_query_per_requirement_with_the_main_need_first():
    qs = retriever.queries(FIT, "v1_decompose")
    assert qs[0] == FIT["title"] and len(qs) == len(FIT["skills"]) + 1
    assert retriever.queries(FIT, "v0_naive") == [v1_decompose.whole_post(FIT)]


def test_corrective_refuses_when_nothing_in_the_portfolio_matches():
    assert retriever.search("ml", "underwater basket weaving instructor", 5, None, "v8_corrective") == []
    assert retriever.search("ml", "underwater basket weaving instructor", 5, None, "v0_naive")       # the baseline always answers


def test_outcome_boost_lifts_a_project_whose_proposals_won(monkeypatch):
    monkeypatch.setattr(v4_outcome, "win_rates", lambda persona: {"winner": 1.0})
    hits = [({"id": "a", "project": "other"}, 0.50), ({"id": "b", "project": "winner"}, 0.45)]
    assert [i["id"] for i, _ in v4_outcome.boost("ml", hits)] == ["b", "a"]


def test_unknown_variant_is_an_error():
    with pytest.raises(ValueError):
        retriever.steps("v99_magic")
