"""Transparent pilot expiry-risk scoring for proposed allocations."""
from decimal import Decimal


def expiry_risk_score(
    days_to_expiry: int,
    projected_days_of_cover: int | float | Decimal,
    proposed_quantity: int | float | Decimal,
    average_monthly_outward: int | float | Decimal,
    prior_claim: bool = False,
    fefo_not_used: bool = False,
) -> tuple[int, list[str]]:
    """Score transparent pilot risk signals; this is not a claim or allocation decision."""
    score = 0
    reasons = []

    if days_to_expiry <= 90:
        score += 30
        reasons.append("LOW_DAYS_TO_EXPIRY")
    if days_to_expiry <= 30:
        score += 30
        reasons.append("VERY_LOW_DAYS_TO_EXPIRY")
    if projected_days_of_cover > 90:
        score += 25
        reasons.append("HIGH_PROJECTED_DAYS_OF_COVER")
    if proposed_quantity > average_monthly_outward:
        score += 30
        reasons.append("PROPOSED_ABOVE_MONTHLY_OUTWARD")
    if prior_claim:
        score += 10
        reasons.append("PRIOR_EXPIRY_CLAIM")
    if fefo_not_used:
        score += 10
        reasons.append("FEFO_BATCH_NOT_USED")

    return min(score, 100), reasons


def expiry_risk_band(score: int, unverified: bool = False) -> tuple[str, str]:
    if unverified:
        return "unverified", "human_review"
    if score >= 60:
        return "high", "hold_or_reallocate"
    if score >= 30:
        return "medium", "reduce_or_approval"
    return "low", "allow"
