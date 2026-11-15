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


def test_a_date_and_time_is_not_masked_as_a_phone_number():
    from agent.guards import scan_text
    from mcp_servers.common import mask_pii
    reply = "Happy to talk. I am free at: 2026-11-16 14:00; 2026-11-16 16:00 (Pakistan time). Which suits you?"
    assert mask_pii(reply) == reply and "2026-11-16 14:00" in scan_text(reply)["cleaned"]
    assert mask_pii("call me on +92 336 4205111 or 0336-4205111") == "call me on [phone] or [phone]"
    assert scan_text("Reach me on +1 555 0100 today.")["violations"], "a real phone number is still caught"
