"""The maths behind the eval numbers, checked on tiny hand-worked cases."""
import pytest

from evals.runners.common import percentile
from evals.runners.decision_eval import prf
from evals.runners.judge_calibration import kappa
from evals.runners.rag_eval import score


def test_retrieval_metrics_on_a_hand_worked_ranking():
    gold = {"a": 2, "b": 1}
    perfect = score(["a", "b", "x"], gold)
    assert perfect == {"recall_at_5": 1.0, "mrr": 1.0, "ndcg_at_10": 1.0}
    late = score(["x", "y", "a"], gold)
    assert late["recall_at_5"] == 0.5 and late["mrr"] == pytest.approx(1 / 3) and 0 < late["ndcg_at_10"] < 1
    assert score(["x", "y"], gold) == {"recall_at_5": 0.0, "mrr": 0.0, "ndcg_at_10": 0.0}


def test_gold_past_rank_five_does_not_count_for_recall_at_5():
    assert score(["1", "2", "3", "4", "5", "a"], {"a": 1})["recall_at_5"] == 0.0


def test_kappa_is_1_for_full_agreement_and_0_for_chance():
    assert kappa([1, 2, 3, 4], [1, 2, 3, 4]) == 1.0
    assert kappa([1, 1, 2, 2], [1, 2, 1, 2]) == 0.0
    assert kappa([1, 2, 3, 4, 5], [2, 3, 4, 5, 5], weighted=True) > kappa([1, 2, 3, 4, 5], [2, 3, 4, 5, 5])   # near misses cost less


def test_precision_recall_f1():
    rows = [{"said": True, "gold": True}, {"said": True, "gold": False}, {"said": False, "gold": True}, {"said": False, "gold": False}]
    assert prf(rows, "said", "gold") == {"precision": 0.5, "recall": 0.5, "f1": 0.5}


def test_percentile():
    assert percentile([1, 2, 3, 4, 5], 50) == 3 and percentile([1, 2, 3, 4, 5], 95) == 5 and percentile([], 95) is None
