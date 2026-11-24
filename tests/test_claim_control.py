from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from app import app
from agent.rules import (
    claim_priority, evaluate_claim_tat, evaluate_pts_difference,
    evaluate_register_claim_window, evaluate_supplied_quantity,
)
from agent.tools import ALL_TOOLS
from agent.workqueue import claim_workqueue

AS_OF = date(2026, 11, 24)


def test_tat_exactly_30_days_is_within_target_and_31_is_over():
    assert evaluate_claim_tat("Credited", "01-01-2026", "31-01-2026", AS_OF)["status"] == "within_target"
    assert evaluate_claim_tat("Credited", "01-01-2026", "01-02-2026", AS_OF) == {"status": "over_target", "days": 31}


def test_tat_pending_rejected_and_unverified_states():
    assert evaluate_claim_tat("Pending", "01-11-2026", "", AS_OF) == {"status": "pending", "days": 23}
    assert evaluate_claim_tat("Pending", "01-10-2026", "", AS_OF)["status"] == "pending_over_target"
    assert evaluate_claim_tat("Rejected", "01-10-2026", "", AS_OF)["status"] == "closed"
    assert evaluate_claim_tat("Credited", "01-10-2026", "", AS_OF)["status"] == "unverified"


def test_pts_difference_is_flagged_only_above_one_rupee():
    assert evaluate_pts_difference("100", "10", "10")["status"] == "match"
    assert evaluate_pts_difference("101", "10", "10")["status"] == "match"
    assert evaluate_pts_difference("101.01", "10", "10")["status"] == "exception"
    assert evaluate_pts_difference("", "10", "10")["status"] == "unverified"


def test_supplied_quantity_allows_invoiced_plus_free_packs():
    assert evaluate_supplied_quantity(Decimal(41), Decimal(38), Decimal(3))["status"] == "within_supplied"
    assert evaluate_supplied_quantity(Decimal(42), Decimal(38), Decimal(3))["status"] == "exceeds_supplied"
    assert evaluate_supplied_quantity(None, Decimal(38), None)["status"] == "unverified"


def test_register_window_is_type_aware():
    assert evaluate_register_claim_window("Near expiry", "15-07-2026", "30-09-2026")["status"] == "within_window"
    assert evaluate_register_claim_window("Near expiry", "01-12-2026", "30-09-2026")["status"] == "breach"
    assert evaluate_register_claim_window("Expired", "01-10-2026", "30-09-2026")["status"] == "within_window"
    assert evaluate_register_claim_window("Expired", "01-07-2026", "30-09-2026")["status"] == "breach"
    assert evaluate_register_claim_window("Short supply", "01-07-2026", "30-09-2026")["status"] == "not_applicable"


def test_priority_score_bands():
    top = claim_priority({"missing_invoice": True, "policy_breach": True, "tat_over_30": True})
    assert (top["score"], top["band"]) == (70, "P1")
    assert claim_priority({"missing_invoice": True})["band"] == "P2"
    assert claim_priority({"duplicate": True})["band"] == "P3"
    assert claim_priority({})["band"] == "P4"
    assert claim_priority({"pending": True})["band"] == "P5"


def test_workqueue_totals_match_the_analysis_script():
    rows = claim_workqueue(AS_OF, None, 500)
    assert rows["total_claims"] == 4526
    all_rows = claim_workqueue(AS_OF, None, 500)["claims"]
    assert sum(c["claim_type"] == "Near expiry" and c["window"]["status"] == "breach"
               for c in claim_workqueue.__globals__["_scored_claims"](AS_OF)) == 242
    pending = claim_workqueue(AS_OF)
    assert pending["total_claims"] == 366 and pending["claims"][0]["priority"]["band"] == "P1"
    assert all_rows


def test_workqueue_is_sorted_best_band_first_and_api_validates_limit():
    bands = [c["priority"]["band"] for c in claim_workqueue(AS_OF, None, 500)["claims"]]
    assert bands == sorted(bands)
    client = TestClient(app)
    assert client.get("/api/claims/workqueue?limit=3&as_of=2026-11-24").json()["claims"].__len__() == 3
    assert client.get("/api/claims/workqueue?limit=0").status_code == 422


def test_claim_history_matches_hyphenated_sku_spelling():
    rows = ALL_TOOLS["lookup_claim_history"].invoke(
        {"stockist_code": "STK0001", "sku_code": "PFL1001", "batch_no": "K2300101"})
    hyphen = [r for r in __import__("agent.tools.data", fromlist=["x"]).expiry_claims() if "-" in r["sku_code"]][0]
    found = ALL_TOOLS["lookup_claim_history"].invoke({
        "stockist_code": hyphen["stockist_code"], "sku_code": hyphen["sku_code"].replace("-", ""),
        "batch_no": hyphen["batch_no"]})
    assert found["found"] and any(c["claim_no"] == hyphen["claim_no"] for c in found["claims"])
    assert isinstance(rows["found"], bool)
