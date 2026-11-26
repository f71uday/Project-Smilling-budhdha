from agent.tools import ALL_TOOLS
from agent.graphs import check_scheme_eligibility, predict_expiry_risk

BASE = {"proposal_date": "30-06-2024", "stockist_code": "STK0001", "cnf_code": "CF-N01",
        "sku_code": "PFL1001", "batch_no": "M2300102", "proposed_quantity": 100}


def test_expiry_prediction_uses_snapshot_and_batch_evidence():
    r = predict_expiry_risk(BASE)
    assert r["evidence"]["batch"]["found"] and r["evidence"]["snapshot"] and r["confidence"] == "proxy"


def test_expiry_prediction_is_unverified_without_batch_data():
    r = predict_expiry_risk({**BASE, "batch_no": "UNKNOWN"})
    assert (r["risk_level"], r["recommendation"], r["reasons"]) == ("unverified", "human_review", ["BATCH_NOT_FOUND"])


def test_wrong_cnf_for_stockist_is_unverified():
    assert predict_expiry_risk({**BASE, "cnf_code": "CF-S02"})["reasons"] == ["STOCKIST_CNF_MISMATCH"]


def test_scheme_graph_unverified_and_not_eligible_paths():
    assert check_scheme_eligibility({**BASE, "batch_no": "UNKNOWN"})["status"] == "unverified"
    assert check_scheme_eligibility(BASE)["recommendation"] == "no_scheme"


def test_cnf_code_variants_in_the_snapshot_are_matched():
    assert predict_expiry_risk({**BASE, "cnf_code": "CFN01"})["evidence"]["snapshot"] is not None


def test_scheme_graph_offers_a_scheme_when_stock_exceeds_sell_through(monkeypatch):
    row = {"snapshot_date": "30-06-2024", "cnf_code": "CF-N01", "sku_code": "PFL1001", "batch_no": "M2300102",
           "expiry_date": "30-11-2025", "qty_on_hand_packs": "50,000.00", "avg_monthly_outward_packs": "1000"}

    class Snap:
        def invoke(self, _args):
            return {"found": True, "rows": [row]}

    monkeypatch.setitem(ALL_TOOLS, "lookup_stock_snapshot", Snap())
    r = check_scheme_eligibility({**BASE, "proposal_date": "30-06-2025"})  # 153 days to expiry
    assert r["status"] == "eligible" and r["recommendation"] == "offer_scheme_with_approval"
    assert float(r["money_saved_inr"]) > 0


def test_missing_snapshot_no_longer_blocks_the_assessment():
    r = predict_expiry_risk({**BASE, "proposal_date": "01-05-2024"})  # before the first snapshot
    assert r["risk_level"] != "unverified" and r["confidence"] == "partial"
    assert "STOCK_COVER_UNAVAILABLE" in r["reasons"] and "current_inventory_packs" not in r["metrics"]


def test_scheme_flag_raises_the_risk_level():
    plain = predict_expiry_risk(BASE)
    scheme = predict_expiry_risk({**BASE, "on_scheme": True})
    assert scheme["risk_score"] == plain["risk_score"] + 30 and "SCHEME_SALE" in scheme["reasons"]


def test_prior_claim_signal_ignores_claims_made_after_the_proposal(monkeypatch):
    class History:
        def invoke(self, _args):
            return {"found": True, "claims": [
                {"claim_no": "LATER", "claim_date": "01-01-2026", "claim_type": "Near expiry"},
                {"claim_no": "EARLIER", "claim_date": "01-01-2024", "claim_type": "Expired"}]}

    monkeypatch.setitem(ALL_TOOLS, "lookup_claim_history", History())
    r = predict_expiry_risk(BASE)  # proposal date 30-06-2024
    assert [c["claim_no"] for c in r["evidence"]["prior_expiry_claims"]] == ["EARLIER"]


def test_usual_order_uses_only_orders_before_the_proposal(monkeypatch):
    class Purchases:
        def invoke(self, _args):
            return {"found": True, "purchases": [
                {"invoice_date": "01-04-2024", "invoiced_qty": "10"}, {"invoice_date": "01-05-2024", "invoiced_qty": "20"},
                {"invoice_date": "01-06-2024", "invoiced_qty": "30"}, {"invoice_date": "01-01-2026", "invoiced_qty": "9000"}]}

    monkeypatch.setitem(ALL_TOOLS, "lookup_purchase_history", Purchases())
    r = predict_expiry_risk({**BASE, "proposed_quantity": 41})
    assert r["evidence"]["usual_order"] == {"prior_orders": 3, "median_quantity_packs": "20"}
    assert "ORDER_ABOVE_USUAL_SIZE" in r["reasons"]
