"""Expiry-claim register lookups."""
from collections import Counter, defaultdict
from functools import lru_cache

from langchain_core.tools import tool

from agent.tools import data

_FIELDS = ("claim_no", "claim_date", "claim_type", "original_invoice_ref", "qty_claimed", "claim_value_inr", "status")


@lru_cache(maxsize=1)
def _claims_by_key() -> dict[tuple[str, str, str], list[dict[str, str]]]:
    index: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in data.expiry_claims():
        index[(data.code(row["stockist_code"]), data.sku_key(row["sku_code"]), data.code(row["batch_no"]))].append(row)
    return index


def claim_rows(stockist_code: str, sku_code: str, batch_no: str) -> list[dict[str, str]]:
    return _claims_by_key().get((data.code(stockist_code), data.sku_key(sku_code), data.code(batch_no)), [])


@tool
def lookup_claim_history(stockist_code: str, sku_code: str, batch_no: str) -> dict:
    """Find source-register claims for one stockist, SKU and batch combination."""
    rows = claim_rows(stockist_code, sku_code, batch_no)
    signatures = [tuple(row.items()) for row in rows]
    counts = Counter(signatures)
    return {
        "found": bool(rows),
        "claim_count": len(rows),
        "exact_duplicate_row_count": sum(n - 1 for n in counts.values()),
        "claims": [
            {**{field: row[field] for field in _FIELDS}, "exact_duplicate_group_size": counts[sig]}
            for row, sig in zip(rows, signatures)
        ],
    }
