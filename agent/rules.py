"""Deterministic claim checks. These findings support review; they do not decide claims."""
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import re

EXPIRY_CLAIM_WINDOW_DAYS = 90


def _parse_date(value: date | str | None) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        return None

    for date_format in ("%Y-%m-%d", "%d-%m-%Y", "%d-%b-%Y", "%d-%B-%Y"):
        try:
            return datetime.strptime(value.strip(), date_format).date()
        except ValueError:
            continue
    return None


def _parse_quantity(value: str | None) -> Decimal | None:
    if not value or not value.strip():
        return None
    try:
        quantity = Decimal(value.strip())
    except InvalidOperation:
        return None
    return quantity if quantity.is_finite() else None


def _parse_email_quantity(value: str | None) -> Decimal | None:
    if not value or not value.strip():
        return None
    numbers = re.findall(r"(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?(?![\w.])", value)
    if len(numbers) != 1:
        return None
    return _parse_quantity(numbers[0].replace(",", ""))


def _format_quantity(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _normalise_invoice(value: object) -> str:
    return str(value or "").strip().casefold()


def evaluate_claim_quantity(
    claimed_quantity: str | None,
    invoiced_quantity: str | None,
) -> dict[str, object]:
    """Require the email's claimed quantity to be strictly below invoiced quantity."""
    claimed = _parse_email_quantity(claimed_quantity)
    invoiced = _parse_quantity(invoiced_quantity)
    if claimed is None or invoiced is None:
        return {
            "status": "unverified",
            "reason": "A single, comparable claimed quantity and invoice quantity are required.",
            "rule": "claimed_quantity < invoiced_quantity",
        }

    details = {
        "claimed_quantity": _format_quantity(claimed),
        "invoiced_quantity": _format_quantity(invoiced),
        "rule": "claimed_quantity < invoiced_quantity",
    }
    if claimed < invoiced:
        return {
            **details,
            "status": "within_invoice_quantity",
            "reason": "Claimed quantity is less than invoiced quantity.",
        }
    if claimed == invoiced:
        return {
            **details,
            "status": "equal_to_invoice_quantity",
            "reason": "Claimed quantity equals invoiced quantity; the rule requires it to be strictly less.",
        }
    return {
        **details,
        "status": "exceeds_invoice_quantity",
        "reason": "Claimed quantity exceeds invoiced quantity.",
    }


def find_duplicate_claim_line_indices(items: list[Mapping[str, str | None]]) -> set[int]:
    """Find repeated batch/invoice/quantity lines within a single email."""
    seen: dict[tuple[str, str, str], int] = {}
    duplicates: set[int] = set()
    for index, item in enumerate(items):
        batch = (item.get("batch_number") or "").strip().upper()
        invoice = _normalise_invoice(item.get("invoice_reference"))
        quantity = " ".join((item.get("claimed_quantity") or "").split()).casefold()
        if not batch or not invoice or not quantity:
            continue

        signature = (batch, invoice, quantity)
        previous = seen.get(signature)
        if previous is None:
            seen[signature] = index
        else:
            duplicates.update((previous, index))
    return duplicates


def evaluate_duplicate_claim(
    history: Mapping[str, object],
    invoice_reference: str | None,
    claimed_quantity: str | None,
) -> dict[str, object]:
    """Compare an email line with historical claims for the same stockist/SKU/batch."""
    rows = history.get("claims")
    if not history.get("found") or not isinstance(rows, list) or not rows:
        return {
            "status": "no_prior_match",
            "reason": "No prior claim was found for this stockist, SKU and batch.",
            "prior_claim_count": 0,
            "prior_claim_refs": [],
            "exact_duplicate_register_rows": 0,
        }

    prior_claim_refs = [
        str(row.get("claim_no", "")).strip()
        for row in rows
        if isinstance(row, Mapping) and str(row.get("claim_no", "")).strip()
    ]
    base = {
        "prior_claim_count": len(rows),
        "prior_claim_refs": prior_claim_refs[:5],
        "exact_duplicate_register_rows": 0,
        "quantity_comparable": None,
    }
    invoice = _normalise_invoice(invoice_reference)
    if not invoice:
        return {
            **base,
            "status": "repeated_history",
            "reason": "Prior claims exist for this stockist, SKU and batch; an invoice reference is needed to compare them.",
        }

    invoice_matches = [
        row
        for row in rows
        if isinstance(row, Mapping)
        and _normalise_invoice(row.get("original_invoice_ref")) == invoice
    ]
    if not invoice_matches:
        return {
            **base,
            "status": "repeated_history",
            "reason": "Prior claims exist for this stockist, SKU and batch, but not for the same invoice.",
        }

    quantity_text = (claimed_quantity or "").strip()
    candidate_quantity = _parse_quantity(claimed_quantity)
    if quantity_text and candidate_quantity is None:
        matching_refs = [
            str(row.get("claim_no", "")).strip()
            for row in invoice_matches
            if isinstance(row, Mapping) and str(row.get("claim_no", "")).strip()
        ]
        return {
            **base,
            "status": "possible_duplicate",
            "reason": "The invoice matches a prior claim, but the quantity text could not be compared safely.",
            "prior_claim_refs": matching_refs[:5],
            "quantity_comparable": False,
        }

    if candidate_quantity is None:
        matches = invoice_matches
        reason = "The stockist, SKU, batch and invoice match prior claim history; quantity still needs review."
    else:
        matches = [
            row
            for row in invoice_matches
            if _parse_quantity(str(row.get("qty_claimed", ""))) == candidate_quantity
        ]
        if not matches:
            return {
                **base,
                "status": "repeated_history",
                "reason": "The invoice matches a prior claim, but the claimed quantity differs.",
                "quantity_comparable": True,
            }
        reason = "The stockist, SKU, batch, invoice and quantity match prior claim history."

    exact_register_rows = max(
        (
            int(row.get("exact_duplicate_group_size", 1)) - 1
            for row in matches
            if isinstance(row, Mapping)
        ),
        default=0,
    )
    matching_refs = [
        str(row.get("claim_no", "")).strip()
        for row in matches
        if isinstance(row, Mapping) and str(row.get("claim_no", "")).strip()
    ]
    return {
        **base,
        "status": "possible_duplicate",
        "reason": reason,
        "prior_claim_refs": matching_refs[:5],
        "exact_duplicate_register_rows": exact_register_rows,
        "quantity_comparable": candidate_quantity is not None,
    }


def evaluate_expiry_claim_window(
    claim_received_date: date | str | None,
    batch_expiry_date: date | str | None,
) -> dict[str, object]:
    """Apply the provisional 90-day window, using email receipt as the claim-date proxy."""
    received = _parse_date(claim_received_date)
    expiry = _parse_date(batch_expiry_date)
    if received is None or expiry is None:
        return {
            "status": "unverified",
            "rule": "provisional_90_day",
            "window_days": EXPIRY_CLAIM_WINDOW_DAYS,
            "date_basis": "email_received_date",
            "reason": "A valid email received date and batch-master expiry date are required.",
        }

    if received <= expiry:
        window_type = "near_expiry"
        window_start = expiry - timedelta(days=EXPIRY_CLAIM_WINDOW_DAYS)
        window_end = expiry
    else:
        window_type = "post_expiry"
        window_start = expiry
        window_end = expiry + timedelta(days=EXPIRY_CLAIM_WINDOW_DAYS)

    inside_window = window_start <= received <= window_end
    return {
        "status": "within_provisional_window" if inside_window else "outside_provisional_window",
        "rule": "provisional_90_day",
        "window_days": EXPIRY_CLAIM_WINDOW_DAYS,
        "window_type": window_type,
        "date_basis": "email_received_date",
        "received_date": received.isoformat(),
        "expiry_date": expiry.isoformat(),
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "days_from_expiry": (received - expiry).days,
    }


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
