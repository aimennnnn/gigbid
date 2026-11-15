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


def test_gate_fails_on_a_missed_threshold_and_on_a_missing_result():
    from evals.runners.gate import check
    gates = {"bid_or_skip_f1_min": 0.85, "unsupported_after_max": 0.0, "canary_leaked_max": 0}
    assert check({"bid_or_skip_f1": 0.93, "unsupported_after": 0.0, "canary_leaked": 0}, gates) == []
    missed = check({"bid_or_skip_f1": 0.80, "unsupported_after": 0.1, "canary_leaked": None}, gates)
    assert len(missed) == 3 and "no result found" in missed[2], "a missing number can never pass a gate"


def test_gate_passes_on_the_committed_results():
    from evals.runners.gate import main
    assert main([]) == 0


def test_ab_test_statistics_match_known_values():
    from evals.runners.ab_test import fisher_exact, jobs_needed, mcnemar_exact, wilson
    assert fisher_exact(1, 9, 11, 3) == pytest.approx(0.002759, abs=1e-6)       # a textbook 2x2 table
    assert fisher_exact(5, 5, 5, 5) == 1.0
    assert mcnemar_exact(5, 3) == pytest.approx(186 / 256)                      # 2 * (1 + 8 + 28 + 56) / 2^8
    assert mcnemar_exact(0, 0) == 1.0 and mcnemar_exact(10, 0) == pytest.approx(2 / 1024)
    low, high = wilson(25, 30)
    assert 0.66 < low < 0.67 and 0.92 < high < 0.93
    assert jobs_needed(0.5, 0.5) is None and jobs_needed(0.8, 0.6) < jobs_needed(0.8, 0.75)


def test_ab_test_counts_pairs_on_the_same_jobs():
    from evals.runners.ab_test import compare
    a = [{"job_id": j, "letter": "x", "events": e} for j, e in (("1", ["replied"]), ("2", ["replied"]), ("3", []))]
    b = [{"job_id": j, "letter": "x", "events": e} for j, e in (("1", ["replied"]), ("2", []), ("3", ["replied"]))]
    t = compare(a, b, "replied")
    assert t["paired"] == {"jobs": 3, "only_a": 1, "only_b": 1, "both": 1, "neither": 0, "mcnemar_exact_p": 1.0}
    assert t["difference_b_minus_a"] == 0 and t["significant_at_0.05"] is False
