from agent.tools import ALL_TOOLS, batch_record


def test_known_batch_is_found():
    r = batch_record("K2300101")
    assert r["found"] and r["sku_code"] == "PFL1001" and r["expiry_date"] == "30-09-2025"


def test_unknown_batch_is_reported_not_invented():
    assert batch_record("NOPE")["found"] is False


def test_batch_lookup_ignores_case_and_spaces():
    assert batch_record(" k2300101 ")["found"] is True


def test_every_data_tool_is_a_named_langchain_tool():
    assert set(ALL_TOOLS) == {
        "lookup_batch", "lookup_sku_price", "lookup_claim_history",
        "lookup_invoice_quantity", "lookup_purchase_history", "lookup_stockist", "lookup_stock_snapshot",
    }


def test_sku_price_and_stockist_tools():
    assert ALL_TOOLS["lookup_sku_price"].invoke({"sku_code": "pfl1001"})["pts_inr"] == "71.4"
    assert ALL_TOOLS["lookup_stockist"].invoke({"stockist_code": "STK0001"})["cnf_code"] == "CF-N01"
    assert ALL_TOOLS["lookup_stockist"].invoke({"stockist_code": "NOPE"})["found"] is False


def test_invoice_tool_reports_missing_line():
    r = ALL_TOOLS["lookup_invoice_quantity"].invoke(
        {"invoice_no": "X", "stockist_code": "STK0001", "sku_code": "PFL1001", "batch_no": "K2300101"})
    assert r["found"] is False


def test_purchase_history_returns_dated_orders_for_a_stockist_and_product():
    r = ALL_TOOLS["lookup_purchase_history"].invoke({"stockist_code": " stk0054 ", "sku_code": "PFL-1102"})
    assert r["found"] and {"invoice_date", "invoiced_qty"} == set(r["purchases"][0])
    assert ALL_TOOLS["lookup_purchase_history"].invoke({"stockist_code": "NOPE", "sku_code": "PFL1001"})["found"] is False
