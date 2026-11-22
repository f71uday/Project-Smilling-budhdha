"""Tools read the data pack. Exact facts come from here, never from the model."""
from agent.tools.batches import batch_record, lookup_batch, lookup_sku_price
from agent.tools.claims import claim_rows, lookup_claim_history
from agent.tools.sales import lookup_invoice_quantity
from agent.tools.stock import (
    expiry_risk_options,
    lookup_stock_snapshot,
    lookup_stockist,
    snapshot_rows,
    stockist_record,
)

# Tools a model may call freely in the legacy question graph.
TOOLS = [lookup_batch]
# Every data tool, by name, for graph nodes that call tools deterministically.
ALL_TOOLS = {
    t.name: t
    for t in (
        lookup_batch,
        lookup_sku_price,
        lookup_claim_history,
        lookup_invoice_quantity,
        lookup_stockist,
        lookup_stock_snapshot,
    )
}
