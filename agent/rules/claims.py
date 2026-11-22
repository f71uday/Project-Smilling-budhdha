"""Deterministic claim checks. These findings support review; they do not decide claims."""
from collections.abc import Mapping
from datetime import date, timedelta

from agent.rules.parsing import (
    format_quantity,
    normalise_invoice,
    parse_date,
    parse_email_quantity,
    parse_quantity,
)

EXPIRY_CLAIM_WINDOW_DAYS = 90


def evaluate_claim_quantity(
    claimed_quantity: str | None,
    invoiced_quantity: str | None,
) -> dict[str, object]:
    """Require the email's claimed quantity to be strictly below invoiced quantity."""
    claimed = parse_email_quantity(claimed_quantity)
    invoiced = parse_quantity(invoiced_quantity)
    if claimed is None or invoiced is None:
        return {
            "status": "unverified",
            "reason": "A single, comparable claimed quantity and invoice quantity are required.",
            "rule": "claimed_quantity < invoiced_quantity",
        }

    details = {
        "claimed_quantity": format_quantity(claimed),
        "invoiced_quantity": format_quantity(invoiced),
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
        invoice = normalise_invoice(item.get("invoice_reference"))
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
    invoice = normalise_invoice(invoice_reference)
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
        and normalise_invoice(row.get("original_invoice_ref")) == invoice
    ]
    if not invoice_matches:
        return {
            **base,
            "status": "repeated_history",
            "reason": "Prior claims exist for this stockist, SKU and batch, but not for the same invoice.",
        }

    quantity_text = (claimed_quantity or "").strip()
    candidate_quantity = parse_quantity(claimed_quantity)
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
            if parse_quantity(str(row.get("qty_claimed", ""))) == candidate_quantity
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
    received = parse_date(claim_received_date)
    expiry = parse_date(batch_expiry_date)
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
