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
