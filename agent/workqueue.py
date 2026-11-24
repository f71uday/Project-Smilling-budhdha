"""Read-only claim work queue: every register claim scored with the control rules."""
from collections import Counter
from datetime import date
from decimal import Decimal
from functools import lru_cache

from agent.rules import (
    claim_priority,
    evaluate_claim_tat,
    evaluate_pts_difference,
    evaluate_register_claim_window,
    evaluate_supplied_quantity,
    parse_quantity,
)
from agent.rules.claim_control import HIGH_VALUE_INR
from agent.tools import data

BAND_ORDER = {"P1": 0, "P2": 1, "P3": 2, "P4": 3, "P5": 4}


@lru_cache(maxsize=1)
def _invoice_index() -> dict[tuple, dict[str, Decimal]]:
    """Invoiced and free packs per invoice/stockist/SKU/batch. Exact duplicate source rows count once."""
    totals: dict[tuple, dict[str, Decimal]] = {}
    for row in {tuple(r.items()): r for r in data.sales()}.values():
        key = (data.code(row["invoice_no"]), data.code(row["stockist_code"]),
               data.sku_key(row["sku_code"]), data.code(row["batch_no"]))
        t = totals.setdefault(key, {"invoiced": Decimal(0), "free": Decimal(0)})
        t["invoiced"] += parse_quantity(row["invoiced_qty"].replace(",", "")) or Decimal(0)
        t["free"] += parse_quantity(row["free_qty"].replace(",", "")) or Decimal(0)
    return totals


@lru_cache(maxsize=4)
def _scored_claims(as_of: date) -> tuple[dict, ...]:
    claims = data.expiry_claims()
    signature = Counter(tuple(r.items()) for r in claims)
    group = Counter((data.code(r["stockist_code"]), data.sku_key(r["sku_code"]), data.code(r["batch_no"])) for r in claims)
    skus = {data.sku_key(k): v for k, v in data.skus().items()}
    batches = data.batches()
    out = []
    for r in claims:
        stockist, sku, batch = data.code(r["stockist_code"]), data.sku_key(r["sku_code"]), data.code(r["batch_no"])
        invoice_ref = r["original_invoice_ref"].strip()
        invoice = _invoice_index().get((data.code(invoice_ref), stockist, sku, batch)) if invoice_ref else None
        qty = parse_quantity(r["qty_claimed"].replace(",", ""))
        tat = evaluate_claim_tat(r["status"].strip(), r["claim_date"], r["credit_note_date"], as_of)
        window = evaluate_register_claim_window(
            r["claim_type"].strip(), r["claim_date"],
            (batches.get(batch) or {}).get("expiry_date") or r["expiry_date_as_claimed"])
        supplied = (evaluate_supplied_quantity(qty, invoice["invoiced"], invoice["free"])
                    if invoice else {"status": "unverified", "reason": "No matching invoice line."})
        pts = evaluate_pts_difference(r["claim_value_inr"], r["qty_claimed"], (skus.get(sku) or {}).get("pts_inr"))
        value = parse_quantity(r["claim_value_inr"].replace(",", "")) or Decimal(0)
        exact_dup = signature[tuple(r.items())] > 1
        flags = {
            "missing_invoice": invoice is None,
            "policy_breach": window["status"] == "breach" or supplied["status"] == "exceeds_supplied",
            "tat_over_30": tat["status"] == "over_target",
            "pending_over_30": tat["status"] == "pending_over_target",
            "duplicate": exact_dup or group[(stockist, sku, batch)] > 1,
            "high_value": value >= HIGH_VALUE_INR,
            "quantity_or_price_mismatch": supplied["status"] == "exceeds_supplied" or pts["status"] == "exception",
            "pending": r["status"].strip() == "Pending",
        }
        out.append({
            "claim_no": r["claim_no"], "status": r["status"].strip(), "claim_type": r["claim_type"].strip(),
            "claim_date": r["claim_date"], "stockist_code": stockist, "sku_code": sku, "batch_no": batch,
            "claim_value_inr": float(value), "invoice_ref": invoice_ref or None,
            "tat": tat, "window": window, "supplied_quantity": supplied, "pts": pts,
            "exact_duplicate_row": exact_dup, "repeated_combination": group[(stockist, sku, batch)] > 1,
            "priority": claim_priority(flags),
        })
    return tuple(out)


def claim_workqueue(as_of: date, status: str | None = "Pending", limit: int = 50) -> dict:
    """Claims ranked by priority band, then score, then value. status=None returns every claim."""
    rows = [c for c in _scored_claims(as_of) if status is None or c["status"] == status]
    rows.sort(key=lambda c: (BAND_ORDER[c["priority"]["band"]], -c["priority"]["score"], -c["claim_value_inr"]))
    bands = Counter(c["priority"]["band"] for c in rows)
    return {
        "as_of": as_of.isoformat(),
        "status_filter": status,
        "total_claims": len(rows),
        "total_value_inr": round(sum(c["claim_value_inr"] for c in rows), 2),
        "by_band": {b: bands.get(b, 0) for b in BAND_ORDER},
        "claims": rows[:limit],
    }
