"""Tools read the data pack. Exact facts come from here, never from the model.

The data files live in data/. Paths are built from this file's location so they work
the same on your laptop and on Vercel.
"""
import csv
from collections import Counter
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path

from langchain_core.tools import tool

DATA = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=1)
def _batches() -> dict:
    """Batch master joined to the SKU master. Codes are cleaned so lookups do not miss."""
    with open(DATA / "sku_master.csv", newline="") as f:
        skus = {r["sku_code"].strip().upper(): r for r in csv.DictReader(f)}
    with open(DATA / "batch_master.csv", newline="") as f:
        out = {}
        for r in csv.DictReader(f):
            code = r["sku_code"].strip().upper()
            out[r["batch_no"].strip().upper()] = {**skus.get(code, {}), **r, "sku_code": code}
        return out


def batch_record(batch_no: str) -> dict:
    """Plain function: easy to test without a model."""
    row = _batches().get(batch_no.strip().upper())
    if row is None:
        return {"found": False, "batch_no": batch_no, "reason": "No such batch in the batch master"}
    return {"found": True, **row}


@lru_cache(maxsize=1)
def _claims() -> list[dict[str, str]]:
    with open(DATA / "expiry_claims.csv", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


@tool
def lookup_claim_history(stockist_code: str, sku_code: str, batch_no: str) -> dict:
    """Find source-register claims for one stockist, SKU and batch combination."""
    key = (stockist_code.strip().upper(), sku_code.strip().upper(), batch_no.strip().upper())
    matching_rows = [
        row
        for row in _claims()
        if (
            row["stockist_code"].strip().upper(),
            row["sku_code"].strip().upper(),
            row["batch_no"].strip().upper(),
        ) == key
    ]
    signatures = [tuple(row.items()) for row in matching_rows]
    signature_counts = Counter(signatures)
    fields = (
        "claim_no",
        "claim_date",
        "claim_type",
        "original_invoice_ref",
        "qty_claimed",
    )
    claims = [
        {
            **{field: row[field] for field in fields},
            "exact_duplicate_group_size": signature_counts[signature],
        }
        for row, signature in zip(matching_rows, signatures)
    ]
    return {
        "found": bool(matching_rows),
        "claim_count": len(matching_rows),
        "exact_duplicate_row_count": sum(count - 1 for count in signature_counts.values()),
        "claims": claims,
    }


@lru_cache(maxsize=1)
def _sales() -> list[dict[str, str]]:
    with open(DATA / "primary_sales.csv", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


@lru_cache(maxsize=1)
def _stockists() -> list[dict[str, str]]:
    with open(DATA / "stockist_master.csv", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


@lru_cache(maxsize=1)
def _snapshots() -> list[dict[str, str]]:
    with open(DATA / "cnf_stock_snapshot.csv", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def expiry_risk_options() -> dict[str, list[dict[str, str]]]:
    """Return master-data choices for the expiry risk form."""
    stockists = [
        {
            "stockist_code": row["stockist_code"].strip(),
            "stockist_name": row["stockist_name"].strip(),
            "cnf_code": row["cnf_code"].strip(),
        }
        for row in _stockists()
    ]
    skus = [
        {
            "sku_code": row["sku_code"].strip(),
            "product_description": row["product_description"].strip(),
        }
        for row in _batches().values()
        if row.get("sku_code")
    ]
    unique_skus = {row["sku_code"]: row for row in skus}
    batches = [
        {
            "batch_no": row["batch_no"].strip(),
            "sku_code": row["sku_code"].strip(),
            "expiry_date": row["expiry_date"].strip(),
        }
        for row in _batches().values()
    ]
    cnfs = sorted({row["cnf_code"].strip() for row in _snapshots() if row["cnf_code"].strip()})
    return {
        "stockists": sorted(stockists, key=lambda row: row["stockist_code"]),
        "cnfs": [{"cnf_code": code} for code in cnfs],
        "skus": sorted(unique_skus.values(), key=lambda row: row["sku_code"]),
        "batches": sorted(batches, key=lambda row: row["batch_no"]),
    }


def lookup_stockist_record(stockist_code: str) -> dict[str, str] | None:
    key = stockist_code.strip().upper()
    return next(
        (row for row in _stockists() if row["stockist_code"].strip().upper() == key),
        None,
    )


def lookup_stock_snapshots(cnf_code: str, sku_code: str) -> list[dict[str, str]]:
    key = cnf_code.strip().upper(), sku_code.strip().upper()
    return [
        row for row in _snapshots()
        if (row["cnf_code"].strip().upper(), row["sku_code"].strip().upper()) == key
    ]


def lookup_expiry_claims(
    stockist_code: str,
    sku_code: str,
    batch_no: str,
) -> list[dict[str, str]]:
    key = stockist_code.strip().upper(), sku_code.strip().upper(), batch_no.strip().upper()
    return [
        row for row in _claims()
        if (
            row["stockist_code"].strip().upper(),
            row["sku_code"].strip().upper(),
            row["batch_no"].strip().upper(),
        ) == key
    ]


@tool
def lookup_invoice_quantity(
    invoice_no: str,
    stockist_code: str,
    sku_code: str,
    batch_no: str,
) -> dict:
    """Find invoiced quantity for the exact invoice, stockist, SKU and batch; free quantity is excluded."""
    key = (
        invoice_no.strip().upper(),
        stockist_code.strip().upper(),
        sku_code.strip().upper(),
        batch_no.strip().upper(),
    )
    matching_rows = [
        row
        for row in _sales()
        if (
            row["invoice_no"].strip().upper(),
            row["stockist_code"].strip().upper(),
            row["sku_code"].strip().upper(),
            row["batch_no"].strip().upper(),
        ) == key
    ]
    unique_rows = list({tuple(row.items()): row for row in matching_rows}.values())
    if not unique_rows:
        return {"found": False, "reason": "No matching invoice line was found in the sales data."}

    quantities = []
    for row in unique_rows:
        try:
            quantity = Decimal(row["invoiced_qty"].strip())
        except InvalidOperation:
            return {"found": False, "reason": "A matching invoice line has no valid invoiced quantity."}
        if not quantity.is_finite():
            return {"found": False, "reason": "A matching invoice line has no finite invoiced quantity."}
        quantities.append(quantity)

    total = sum(quantities, Decimal(0))
    return {
        "found": True,
        "invoice_no": key[0],
        "stockist_code": key[1],
        "sku_code": key[2],
        "batch_no": key[3],
        "invoiced_qty": format(total.normalize(), "f"),
        "invoice_line_count": len(unique_rows),
        "duplicate_source_rows_removed": len(matching_rows) - len(unique_rows),
    }


@tool
def lookup_batch(batch_no: str) -> dict:
    """Look up one batch in the batch master. Returns the SKU, product, manufacturing date,
    expiry date and price to stockist, or found=False if the batch does not exist.
    Use it whenever a question mentions a batch number."""
    return batch_record(batch_no)


TOOLS = [lookup_batch]
