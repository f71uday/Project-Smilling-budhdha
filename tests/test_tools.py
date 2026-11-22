"""Tests that run without an API key. Add one test for every rule you put in code."""
from agent.tools import batch_record, check_batch_sku, check_claim_pts, check_claim_quantity, check_invoice, lookup_sku


def test_known_batch_is_found():
    rec = batch_record("K2300101")
    assert rec["found"] is True
    assert rec["sku_code"] == "PFL1001"


def test_unknown_batch_is_reported_not_invented():
    rec = batch_record("ZZ999")
    assert rec["found"] is False


def test_batch_lookup_ignores_case_and_spaces():
    assert batch_record("  k2300101 ")["found"] is True


def test_invoice_tool_finds_primary_sales_invoice():
    result = check_invoice.invoke({"invoice_no": "INV/E01/2404/000881"})
    assert result["found"] is True


def test_invoice_tool_flags_wrong_stockist():
    result = check_invoice.invoke({"invoice_no": "INV/E01/2404/000881", "stockist": "STK0001"})
    assert result["found"] is True
    assert result["stockist_matches"] is False


def test_invoice_tool_reports_missing_reference():
    result = check_invoice.invoke({"invoice_no": "INV/UNKNOWN"})
    assert result["found"] is False


def test_batch_sku_tool_checks_match():
    result = check_batch_sku.invoke({"batch_no": "K2300101", "sku": "PFL1001"})
    assert result["matches"] is True


def test_batch_sku_tool_flags_mismatch():
    result = check_batch_sku.invoke({"batch_no": "K2300101", "sku": "PFL1002"})
    assert result["batch_found"] is True
    assert result["sku_found"] is True
    assert result["matches"] is False


def test_sku_lookup_finds_sku_master_record():
    result = lookup_sku.invoke({"sku": "PFL1001"})
    assert result["found"] is True
    assert result["product_description"] == "Azithromycin 500 mg tablets"


def test_claim_pts_tool_compares_with_sku_master():
    result = check_claim_pts.invoke({"claimed_pts": "72.41", "sku": "PFL1001"})
    assert result["checked"] is True
    assert result["exception"] is True


def test_claim_quantity_tool_compares_with_invoice_line():
    result = check_claim_quantity.invoke({
        "invoice_no": "INV/E01/2404/000881",
        "batch_no": "K2310267",
        "claim_quantity": "38 strips",
    })
    assert result["within_invoice"] is True


def test_claim_quantity_tool_flags_quantity_above_invoice_plus_free():
    result = check_claim_quantity.invoke({
        "invoice_no": "INV/E01/2404/000881",
        "batch_no": "K2310267",
        "claim_quantity": "293 strips",
    })
    assert result["checked"] is True
    assert result["within_invoice"] is False
