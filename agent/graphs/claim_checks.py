"""Per-line deterministic claim checks. Facts come from tools; verdicts come from rules."""
from typing import Any

from agent.rules import (
    duplicate_claim_saving,
    evaluate_claim_quantity,
    evaluate_duplicate_claim,
    evaluate_expiry_claim_window,
    find_duplicate_claim_line_indices,
    parse_email_quantity,
)
from agent.tools import ALL_TOOLS


def _unverified(reason: str) -> dict:
    return {"status": "unverified", "reason": reason}


def _no_history(reason: str) -> dict:
    return {**_unverified(reason), "prior_claim_count": 0, "prior_claim_refs": [], "exact_duplicate_register_rows": 0}


def appears_in_email(value: str | None, body: str) -> bool:
    return bool(value and value.strip() and value.strip().casefold() in body.casefold())


def verify_items(items: list[Any], body: str) -> list[dict[str, str | None]]:
    """Keep only extracted values that literally appear in the email body."""
    def keep(value):
        return value if appears_in_email(value, body) else None

    return [
        {
            "batch_number": keep(i.batch_number),
            "invoice_reference": keep(i.invoice_reference),
            "claimed_quantity": keep(i.claimed_quantity),
        }
        for i in items
    ]


def _expiry_check(reason: str, received: str | None, expiry: str | None) -> dict:
    if reason != "expiry":
        return {"status": "not_applicable", "reason": "The claim was not classified as an expiry claim."}
    return evaluate_expiry_claim_window(received, expiry)


def _prior_claim_details(history: dict, duplicate: dict) -> list[dict]:
    refs = set(duplicate.get("prior_claim_refs", []))
    fields = ("claim_no", "claim_date", "claim_type", "original_invoice_ref", "qty_claimed")
    return [
        {f: str(c.get(f, "")).strip() for f in fields}
        for c in history.get("claims", [])
        if str(c.get("claim_no", "")).strip() in refs
    ][:5]


def _quantity_check(stockist: str, batch: dict, invoice_ref: str | None, claimed: str | None) -> dict:
    if not invoice_ref:
        return _unverified("An invoice reference copied from the email is required.")
    if not stockist:
        return _unverified("A stockist code is required to match the invoice.")
    if not batch.get("sku_code"):
        return _unverified("A verified SKU is required to match the invoice.")
    invoice = ALL_TOOLS["lookup_invoice_quantity"].invoke({
        "invoice_no": invoice_ref,
        "stockist_code": stockist,
        "sku_code": batch["sku_code"],
        "batch_no": batch["batch_no"],
    })
    if not invoice["found"]:
        return _unverified(invoice["reason"])
    result = evaluate_claim_quantity(claimed, invoice["invoiced_qty"])
    return {**result, "invoiced_quantity": invoice["invoiced_qty"]} if result["status"] == "unverified" else result


def _details(item: dict, reason: str, batch: dict | None = None) -> dict:
    ok = bool(batch and batch.get("found"))
    return {
        "claim_reason": reason,
        "batch_no": batch.get("batch_no") if ok else item["batch_number"],
        "batch_verified": ok,
        "sku_code": batch.get("sku_code") if ok else None,
        "sku_name": batch.get("product_description") if ok else None,
        "claimed_quantity": item["claimed_quantity"],
        "expiry_date": batch.get("expiry_date") if ok else None,
        "invoice_reference": item["invoice_reference"],
        "invoiced_quantity": None,
    }


def _mark_repeat_in_email(finding: dict, repeated: bool) -> dict:
    if not repeated:
        return finding
    return {
        **finding,
        "status": "possible_duplicate",
        "within_email_repeat": True,
        "reason": "The same batch, invoice and quantity line appears more than once in this email. "
        + str(finding["reason"]),
    }


def check_line(email: dict, reason: str, item: dict, repeated: bool) -> tuple[dict, dict]:
    """Run every deterministic check for one claim line. Returns (batch evidence, claim check)."""
    batch_no = (item["batch_number"] or "").strip()
    if not batch_no:
        why = "A verified batch is needed to search claim history."
        evidence = {"found": False, "reason": "No batch number was verified in this claim line."}
        batch = None
    else:
        batch = ALL_TOOLS["lookup_batch"].invoke({"batch_no": batch_no})
        evidence = {"found": True, **batch} if batch["found"] else {"found": False, "reason": batch["reason"]}
        why = "The batch could not be matched to the batch master."

    if not batch or not batch["found"]:
        check = {
            "claim_details": _details(item, reason),
            "duplicate": _mark_repeat_in_email(_no_history(why), repeated),
            "expiry": _expiry_check(reason, email.get("received_date"), None),
            "quantity": _unverified(why.replace("search claim history", "find the matching invoice line")),
            "saving": duplicate_claim_saving("unverified", None, []),
        }
        return evidence, check

    stockist = email.get("stockist_code_by_mailbox_rule", "").strip()
    details = _details(item, reason, batch)
    history: dict = {}
    if stockist and batch.get("sku_code"):
        history = ALL_TOOLS["lookup_claim_history"].invoke(
            {"stockist_code": stockist, "sku_code": batch["sku_code"], "batch_no": batch["batch_no"]}
        )
        duplicate = evaluate_duplicate_claim(history, item["invoice_reference"], item["claimed_quantity"])
        duplicate["prior_claim_details"] = _prior_claim_details(history, duplicate)
    else:
        duplicate = _no_history(
            "A stockist code is needed to search claim history." if not stockist
            else "A SKU match is needed to search claim history."
        )
    duplicate = _mark_repeat_in_email(duplicate, repeated)
    quantity = _quantity_check(stockist, batch, item["invoice_reference"], item["claimed_quantity"])
    details["invoiced_quantity"] = quantity.get("invoiced_quantity")
    refs = set(duplicate.get("prior_claim_refs", []))
    prior = [c for c in history.get("claims", []) if str(c.get("claim_no", "")).strip() in refs]
    return evidence, {
        "batch_no": batch["batch_no"],
        "claim_details": details,
        "duplicate": duplicate,
        "expiry": _expiry_check(reason, email.get("received_date"), batch.get("expiry_date")),
        "quantity": quantity,
        "saving": duplicate_claim_saving(
            duplicate["status"], parse_email_quantity(item["claimed_quantity"]), prior
        ),
    }


def check_all_lines(email: dict, reason: str, items: list[Any]) -> tuple[list[dict], list[dict]]:
    verified = verify_items(items, email.get("body", ""))
    repeats = find_duplicate_claim_line_indices(verified)
    pairs = [check_line(email, reason, item, i in repeats) for i, item in enumerate(verified)]
    return [p[0] for p in pairs], [p[1] for p in pairs]
