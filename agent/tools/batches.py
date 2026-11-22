"""Batch and SKU master lookups."""
from langchain_core.tools import tool

from agent.tools import data


def batch_record(batch_no: str) -> dict:
    """Plain function: easy to test without a model."""
    row = data.batches().get(data.code(batch_no))
    if row is None:
        return {"found": False, "batch_no": batch_no, "reason": "No such batch in the batch master"}
    return {"found": True, **row}


@tool
def lookup_batch(batch_no: str) -> dict:
    """Look up one batch in the batch master. Returns the SKU, product, manufacturing date,
    expiry date and price to stockist, or found=False if the batch does not exist.
    Use it whenever a question mentions a batch number."""
    return batch_record(batch_no)


@tool
def lookup_sku_price(sku_code: str) -> dict:
    """Return the price to stockist (PTS, INR per pack) for one SKU from the SKU master."""
    row = data.skus().get(data.code(sku_code))
    if row is None:
        return {"found": False, "sku_code": sku_code, "reason": "No such SKU in the SKU master"}
    return {
        "found": True,
        "sku_code": data.code(sku_code),
        "product_description": row["product_description"].strip(),
        "pts_inr": row["pts_inr"].strip(),
    }
