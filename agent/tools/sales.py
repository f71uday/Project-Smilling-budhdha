"""Primary-sales (invoice) lookups."""
from decimal import Decimal, InvalidOperation

from langchain_core.tools import tool

from agent.tools import data


@tool
def lookup_invoice_quantity(invoice_no: str, stockist_code: str, sku_code: str, batch_no: str) -> dict:
    """Find invoiced quantity for the exact invoice, stockist, SKU and batch; free quantity is excluded."""
    key = tuple(data.code(v) for v in (invoice_no, stockist_code, sku_code, batch_no))
    matching = [
        row for row in data.sales()
        if tuple(data.code(row[f]) for f in ("invoice_no", "stockist_code", "sku_code", "batch_no")) == key
    ]
    unique = list({tuple(row.items()): row for row in matching}.values())
    if not unique:
        return {"found": False, "reason": "No matching invoice line was found in the sales data."}

    quantities = []
    for row in unique:
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
        "invoice_line_count": len(unique),
        "duplicate_source_rows_removed": len(matching) - len(unique),
    }
