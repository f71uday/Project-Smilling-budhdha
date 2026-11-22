from agent.rules import (
    claim_priority_band,
    claim_priority_score,
    claim_quantity_within_invoice,
    expiry_risk_band,
    expiry_risk_score,
    pts_difference_exceeds_tolerance,
    valid_allocation_quantity,
)


def test_claim_quantity_must_not_exceed_invoice_plus_free_packs():
    assert claim_quantity_within_invoice(38, 38) is True
    assert claim_quantity_within_invoice(41, 38, 3) is True
    assert claim_quantity_within_invoice(42, 38, 3) is False


def test_claim_priority_score_and_band_are_explainable():
    score = claim_priority_score(
        missing_invoice=True,
        pending_over_30_days=True,
        credited_tat_over_30_days=False,
        exact_duplicate=False,
        high_value=False,
    )
    assert score == 50
    assert claim_priority_band(score) == "P1"
    assert claim_priority_band(0, monitoring=True) == "P5"


def test_expiry_risk_reasons_include_cover_and_prior_claim_as_signal():
    score, reasons = expiry_risk_score(80, 150, 100, 60, prior_claim=True)
    assert score == 95
    assert len(reasons) == 4
    assert expiry_risk_band(score, unverified=False) == ("high", "hold_or_reallocate")
    assert expiry_risk_band(score, unverified=True) == ("unverified", "human_review")


def test_expiry_risk_score_recommends_review_when_data_is_unverified():
    score, reasons = expiry_risk_score(20, 200, 100, 100, prior_claim=False)
    assert score >= 60
    assert reasons
    assert expiry_risk_band(score, unverified=True) == ("unverified", "human_review")


def test_pts_exception_is_more_than_one_rupee():
    assert pts_difference_exceeds_tolerance(100, 101) is False
    assert pts_difference_exceeds_tolerance(100, 101.01) is True


def test_allocation_decisions_keep_quantity_within_recommendation_limits():
    assert valid_allocation_quantity("allow", 100, 100) is True
    assert valid_allocation_quantity("reduce", 100, 80) is True
    assert valid_allocation_quantity("reduce", 100, 100) is False
    assert valid_allocation_quantity("reallocate", 100, 100) is True
