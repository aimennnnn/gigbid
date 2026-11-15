import pytest
from pydantic import ValidationError

from agent.handoffs import BidDecision, PriceQuote, RiskReport


def test_scores_must_be_between_0_and_1():
    with pytest.raises(ValidationError):
        RiskReport(job_id="j1", risk_score=1.4, client_quality=0.5)


def test_decision_action_is_limited():
    with pytest.raises(ValidationError):
        BidDecision(job_id="j1", action="maybe", reasons=[])


def test_price_must_be_positive():
    with pytest.raises(ValidationError):
        PriceQuote(job_id="j1", amount=0, price_type="fixed", connects_cost=4,
                   worth_connects=True, rationale="x")


def test_unknown_risk_flag_rejected():
    with pytest.raises(ValidationError):
        RiskReport(job_id="j1", risk_score=0.2, client_quality=0.5, flags=["weird"])


def test_wrapper_tags_around_a_letter_are_removed():
    from agent.guards import strip_markup
    assert strip_markup("<text>\nYou need a model that spots fraud.\n</text>") == "You need a model that spots fraud."
    assert strip_markup("Costs are < 5% and > 1%.") == "Costs are < 5% and > 1%.", "ordinary text is left alone"
