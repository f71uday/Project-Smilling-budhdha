"""Stockist master and C&F stock-snapshot lookups."""
from langchain_core.tools import tool

from agent.tools import data


def stockist_record(stockist_code: str) -> dict | None:
    key = data.code(stockist_code)
    return next((r for r in data.stockists() if data.code(r["stockist_code"]) == key), None)


def snapshot_rows(cnf_code: str, sku_code: str) -> list[dict[str, str]]:
    key = data.cnf_key(cnf_code), data.code(sku_code)
    return [r for r in data.snapshots() if (data.cnf_key(r["cnf_code"]), data.code(r["sku_code"])) == key]


@tool
def lookup_stockist(stockist_code: str) -> dict:
    """Find one stockist and its C&F in the stockist master."""
    row = stockist_record(stockist_code)
    if row is None:
        return {"found": False, "reason": "No such stockist in the stockist master"}
    return {
        "found": True,
        "stockist_code": row["stockist_code"].strip(),
        "stockist_name": row["stockist_name"].strip(),
        "cnf_code": row["cnf_code"].strip(),
    }


@tool
def lookup_stock_snapshot(cnf_code: str, sku_code: str) -> dict:
    """Return every C&F stock-snapshot row (all dates and batches) for one C&F and SKU."""
    rows = snapshot_rows(cnf_code, sku_code)
    return {"found": bool(rows), "rows": rows}


def expiry_risk_options() -> dict[str, list[dict[str, str]]]:
    """Master-data choices for the expiry risk form."""
    stockists = sorted(
        (
            {
                "stockist_code": r["stockist_code"].strip(),
                "stockist_name": r["stockist_name"].strip(),
                "cnf_code": r["cnf_code"].strip(),
            }
            for r in data.stockists()
        ),
        key=lambda r: r["stockist_code"],
    )
    skus = {
        r["sku_code"]: {"sku_code": r["sku_code"], "product_description": r["product_description"].strip()}
        for r in data.batches().values() if r.get("sku_code")
    }
    batches = sorted(
        (
            {"batch_no": r["batch_no"].strip(), "sku_code": r["sku_code"].strip(), "expiry_date": r["expiry_date"].strip()}
            for r in data.batches().values()
        ),
        key=lambda r: r["batch_no"],
    )
    cnfs = sorted({r["cnf_code"].strip() for r in data.stockists() if r["cnf_code"].strip()})
    return {
        "stockists": stockists,
        "cnfs": [{"cnf_code": c} for c in cnfs],
        "skus": sorted(skus.values(), key=lambda r: r["sku_code"]),
        "batches": batches,
    }
