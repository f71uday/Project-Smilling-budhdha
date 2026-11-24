from decimal import Decimal

from agent.rules import (
    duplicate_claim_saving, evaluate_scheme_eligibility, expiry_risk_band, expiry_risk_score, usual_order_quantity,
)


def test_expiry_risk_shelf_life_tiers_add_up():
    assert expiry_risk_score(400, None, 100, None) == (0, [])
    assert expiry_risk_score(365, None, 100, None) == (30, ["SHELF_LIFE_UNDER_12_MONTHS"])
    assert expiry_risk_score(270, None, 100, None)[0] == 45
    assert expiry_risk_score(90, None, 100, None)[0] == 60
    assert expiry_risk_score(30, None, 100, None)[0] == 90


def test_scheme_and_short_shelf_life_together_are_high_risk():
    score, reasons = expiry_risk_score(300, None, 100, None, on_scheme=True)
    assert score == 60 and reasons == ["SHELF_LIFE_UNDER_12_MONTHS", "SCHEME_SALE"]
    assert expiry_risk_band(score) == ("high", "hold_or_reallocate")
    assert expiry_risk_band(expiry_risk_score(500, None, 100, None, on_scheme=True)[0])[0] == "medium"


def test_order_size_signal_needs_more_than_twice_the_usual_order():
    assert "ORDER_ABOVE_USUAL_SIZE" not in expiry_risk_score(500, None, 200, None, usual_order_quantity=100)[1]
    assert expiry_risk_score(500, None, 201, None, usual_order_quantity=100) == (20, ["ORDER_ABOVE_USUAL_SIZE"])
    assert expiry_risk_score(500, None, 999, None, usual_order_quantity=None) == (0, [])


def test_stock_cover_signals_and_cap_at_100():
    score, reasons = expiry_risk_score(500, 150, 100, 60, prior_claim=True, fefo_not_used=True)
    assert score == 75 and reasons == [
        "HIGH_PROJECTED_DAYS_OF_COVER", "PROPOSED_ABOVE_MONTHLY_OUTWARD", "PRIOR_EXPIRY_CLAIM", "FEFO_BATCH_NOT_USED"]
    assert expiry_risk_score(20, 150, 100, 60, prior_claim=True, on_scheme=True)[0] == 100


def test_usual_order_is_the_median_and_needs_three_orders():
    assert usual_order_quantity([Decimal(10), Decimal(30)]) is None
    assert usual_order_quantity([Decimal(10), Decimal(50), Decimal(30)]) == Decimal(30)
    assert usual_order_quantity([Decimal(10), Decimal(20), Decimal(30), Decimal(40)]) == Decimal(25)


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
