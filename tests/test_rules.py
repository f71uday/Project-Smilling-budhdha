from decimal import Decimal

from agent.rules import duplicate_claim_saving, evaluate_scheme_eligibility, expiry_risk_band, expiry_risk_score


def test_expiry_risk_score_adds_each_signal_and_caps_at_100():
    score, reasons = expiry_risk_score(80, 150, 100, 60, prior_claim=True)
    assert score == 95 and len(reasons) == 4
    assert expiry_risk_score(20, 150, 100, 60, prior_claim=True, fefo_not_used=True)[0] == 100


def test_expiry_risk_bands():
    assert expiry_risk_band(29) == ("low", "allow")
    assert expiry_risk_band(30) == ("medium", "reduce_or_approval")
    assert expiry_risk_band(60) == ("high", "hold_or_reallocate")
    assert expiry_risk_band(95, unverified=True) == ("unverified", "human_review")


def test_scheme_eligible_when_stock_exceeds_sell_through():
    r = evaluate_scheme_eligibility(90, Decimal(1000), Decimal(100), Decimal("10"))
    assert r["status"] == "eligible"
    assert r["packs_at_risk"] == "700" and r["money_saved_inr"] == "7000"
    assert r["provisional"] is True


def test_scheme_not_eligible_outside_window_or_when_stock_will_clear():
    assert evaluate_scheme_eligibility(10, Decimal(1000), Decimal(100), Decimal(10))["status"] == "not_eligible"
    assert evaluate_scheme_eligibility(500, Decimal(1000), Decimal(100), Decimal(10))["status"] == "not_eligible"
    assert evaluate_scheme_eligibility(90, Decimal(100), Decimal(100), Decimal(10))["status"] == "not_eligible"


def test_duplicate_saving_uses_prior_claim_unit_value():
    prior = [{"claim_no": "C1", "claim_value_inr": "1,000", "qty_claimed": "10"}]
    assert duplicate_claim_saving("possible_duplicate", Decimal(5), prior)["amount_inr"] == "500.00"
    assert duplicate_claim_saving("no_prior_match", Decimal(5), prior)["status"] == "not_applicable"
    assert duplicate_claim_saving("possible_duplicate", None, prior)["status"] == "unverified"
