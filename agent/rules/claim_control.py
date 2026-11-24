"""Register-level claim control rules from the Solution Design (section 6.3 and 6.5)."""
from datetime import date
from decimal import Decimal

from agent.rules.claims import evaluate_expiry_claim_window
from agent.rules.parsing import parse_date, parse_quantity

TAT_TARGET_DAYS = 30
PTS_TOLERANCE_INR = Decimal(1)
HIGH_VALUE_INR = Decimal(50000)  # provisional: confirm with Commercial

# Visible and changeable weights for the pilot; not approved policy.
PRIORITY_WEIGHTS = {
    "missing_invoice": 25,
    "policy_breach": 25,
    "tat_over_30": 20,
    "pending_over_30": 20,
    "duplicate": 15,
    "high_value": 15,
}
P1_MIN_SCORE = 60


def evaluate_claim_tat(
    status: str, claim_date: str | date | None, credit_date: str | date | None, as_of: date
) -> dict[str, object]:
    """Credited claims: claim-to-credit days (over target when above 30). Pending: age so far."""
    claimed = parse_date(claim_date)
    if claimed is None:
        return {"status": "unverified", "reason": "A valid claim date is required."}
    if status == "Credited":
        credited = parse_date(credit_date)
        if credited is None:
            return {"status": "unverified", "reason": "A credited claim needs a valid credit note date."}
        days = (credited - claimed).days
        return {"status": "over_target" if days > TAT_TARGET_DAYS else "within_target", "days": days}
    if status == "Pending":
        age = max((as_of - claimed).days, 0)
        return {"status": "pending_over_target" if age > TAT_TARGET_DAYS else "pending", "days": age}
    return {"status": "closed", "days": None}


def evaluate_pts_difference(claim_value: str | None, quantity: str | None, pts_inr: str | None) -> dict[str, object]:
    """Recalculate quantity x PTS and flag a difference of more than INR 1."""
    value = parse_quantity((claim_value or "").replace(",", ""))
    qty = parse_quantity(quantity)
    pts = parse_quantity(pts_inr)
    if value is None or qty is None or pts is None:
        return {"status": "unverified", "reason": "Claim value, quantity and SKU PTS are all required."}
    difference = abs(value - qty * pts)
    return {
        "status": "exception" if difference > PTS_TOLERANCE_INR else "match",
        "difference_inr": format(difference.quantize(Decimal("0.01")), "f"),
    }


def evaluate_supplied_quantity(claimed: Decimal | None, invoiced: Decimal | None, free: Decimal | None) -> dict[str, object]:
    """Design rule: flag a claim above invoiced quantity plus free packs."""
    if claimed is None or invoiced is None:
        return {"status": "unverified", "reason": "Claimed and invoiced quantities are required."}
    supplied = invoiced + (free or Decimal(0))
    return {
        "status": "exceeds_supplied" if claimed > supplied else "within_supplied",
        "supplied_quantity": format(supplied.normalize(), "f"),
    }


def evaluate_register_claim_window(
    claim_type: str, claim_date: str | None, batch_expiry: str | None
) -> dict[str, object]:
    """Near-expiry claims must fall within 90 days before expiry; expired claims within 90 days after."""
    if claim_type not in ("Near expiry", "Expired"):
        return {"status": "not_applicable"}
    window = evaluate_expiry_claim_window(claim_date, batch_expiry)
    if window["status"] == "unverified":
        return {"status": "unverified", "reason": window["reason"]}
    wanted = "near_expiry" if claim_type == "Near expiry" else "post_expiry"
    ok = window["window_type"] == wanted and window["status"] == "within_provisional_window"
    return {"status": "within_window" if ok else "breach", "days_from_expiry": window["days_from_expiry"]}


def claim_priority(flags: dict[str, bool]) -> dict[str, object]:
    """Score visible signals and map to P1-P5. P5 is for pending claims with no other signal."""
    reasons = [name for name in PRIORITY_WEIGHTS if flags.get(name)]
    score = sum(PRIORITY_WEIGHTS[name] for name in reasons)
    if score >= P1_MIN_SCORE:
        band = "P1"
    elif flags.get("missing_invoice") or flags.get("quantity_or_price_mismatch"):
        band = "P2"
    elif flags.get("duplicate"):
        band = "P3"
    elif flags.get("pending") and not reasons:
        band = "P5"
    else:
        band = "P4"
    return {"score": score, "band": band, "reasons": reasons}
