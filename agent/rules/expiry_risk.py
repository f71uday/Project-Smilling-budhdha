"""Transparent pilot expiry-risk scoring for proposed allocations.

Weights come from a backtest of sales against later expiry claims (analysis/expiry_risk_backtest.py):
scheme sales and stock with under 12 months of shelf life drive most expiry returns.
They are pilot heuristics, not approved policy.
"""
from decimal import Decimal

SHELF_LIFE_12_MONTHS_DAYS = 365
SHELF_LIFE_9_MONTHS_DAYS = 270
LARGE_ORDER_MULTIPLE = Decimal(2)   # proposed quantity against the stockist's usual order for the product
MIN_PRIOR_ORDERS = 3                # fewer than this and "usual order" is not reliable

WEIGHTS = {
    "SHELF_LIFE_UNDER_12_MONTHS": 30,
    "SHELF_LIFE_UNDER_9_MONTHS": 15,
    "LOW_DAYS_TO_EXPIRY": 15,          # 90 days or less
    "VERY_LOW_DAYS_TO_EXPIRY": 30,     # 30 days or less
    "SCHEME_SALE": 30,
    "ORDER_ABOVE_USUAL_SIZE": 20,
    "HIGH_PROJECTED_DAYS_OF_COVER": 25,
    "PROPOSED_ABOVE_MONTHLY_OUTWARD": 30,
    "PRIOR_EXPIRY_CLAIM": 10,
    "FEFO_BATCH_NOT_USED": 10,
}


def expiry_risk_score(
    days_to_expiry: int,
    projected_days_of_cover: int | float | Decimal | None,
    proposed_quantity: int | float | Decimal,
    average_monthly_outward: int | float | Decimal | None,
    prior_claim: bool = False,
    fefo_not_used: bool = False,
    on_scheme: bool = False,
    usual_order_quantity: int | float | Decimal | None = None,
) -> tuple[int, list[str]]:
    """Score transparent pilot risk signals; this is not a claim or allocation decision.

    Stock-cover signals are skipped when the C&F snapshot is unavailable (pass None).
    """
    signals = {
        "SHELF_LIFE_UNDER_12_MONTHS": days_to_expiry <= SHELF_LIFE_12_MONTHS_DAYS,
        "SHELF_LIFE_UNDER_9_MONTHS": days_to_expiry <= SHELF_LIFE_9_MONTHS_DAYS,
        "LOW_DAYS_TO_EXPIRY": days_to_expiry <= 90,
        "VERY_LOW_DAYS_TO_EXPIRY": days_to_expiry <= 30,
        "SCHEME_SALE": on_scheme,
        "ORDER_ABOVE_USUAL_SIZE": bool(
            usual_order_quantity and proposed_quantity > LARGE_ORDER_MULTIPLE * Decimal(str(usual_order_quantity))
        ),
        "HIGH_PROJECTED_DAYS_OF_COVER": projected_days_of_cover is not None and projected_days_of_cover > 90,
        "PROPOSED_ABOVE_MONTHLY_OUTWARD": (
            average_monthly_outward is not None and proposed_quantity > average_monthly_outward
        ),
        "PRIOR_EXPIRY_CLAIM": prior_claim,
        "FEFO_BATCH_NOT_USED": fefo_not_used,
    }
    reasons = [name for name, hit in signals.items() if hit]
    return min(sum(WEIGHTS[name] for name in reasons), 100), reasons


def usual_order_quantity(prior_quantities: list[Decimal]) -> Decimal | None:
    """Median of the stockist's earlier orders for this product; None when there are too few."""
    if len(prior_quantities) < MIN_PRIOR_ORDERS:
        return None
    ordered = sorted(prior_quantities)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def expiry_risk_band(score: int, unverified: bool = False) -> tuple[str, str]:
    if unverified:
        return "unverified", "human_review"
    if score >= 60:
        return "high", "hold_or_reallocate"
    if score >= 30:
        return "medium", "reduce_or_approval"
    return "low", "allow"
