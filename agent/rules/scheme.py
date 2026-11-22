"""Scheme eligibility from C&F stock. Thresholds are provisional until policy confirms them."""
from decimal import Decimal

SCHEME_MIN_DAYS_TO_EXPIRY = 30    # provisional: too close to expiry to be sold through
SCHEME_MAX_DAYS_TO_EXPIRY = 365   # provisional: snapshots never hold stock under 182 days, so 180 would never fire
DAYS_PER_MONTH = Decimal(30)


def evaluate_scheme_eligibility(
    days_to_expiry: int,
    qty_on_hand: Decimal,
    avg_monthly_outward: Decimal,
    pts_inr: Decimal,
) -> dict[str, object]:
    """A scheme may be offered when near-expiry stock exceeds what normal outward can sell.

    Money saved is the value, at price to stockist, of the packs that would otherwise expire.
    """
    base = {
        "rule": "near_expiry_stock_exceeds_sell_through",
        "provisional": True,
        "window_days": [SCHEME_MIN_DAYS_TO_EXPIRY, SCHEME_MAX_DAYS_TO_EXPIRY],
        "days_to_expiry": days_to_expiry,
    }
    if days_to_expiry < SCHEME_MIN_DAYS_TO_EXPIRY:
        return {**base, "status": "not_eligible", "reason": "Too close to expiry for a scheme to move stock."}
    if days_to_expiry > SCHEME_MAX_DAYS_TO_EXPIRY:
        return {**base, "status": "not_eligible", "reason": "Batch is not yet near expiry."}

    sellable = avg_monthly_outward * Decimal(days_to_expiry) / DAYS_PER_MONTH
    excess = max(Decimal(0), qty_on_hand - sellable)
    if excess == 0:
        return {**base, "status": "not_eligible", "reason": "Normal outward is expected to clear this stock."}
    return {
        **base,
        "status": "eligible",
        "reason": "Stock on hand exceeds expected sell-through before expiry.",
        "packs_at_risk": _fmt(excess),
        "money_saved_inr": _fmt(excess * pts_inr),
    }


def _fmt(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")).normalize(), "f")
