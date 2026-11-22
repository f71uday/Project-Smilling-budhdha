from datetime import date

from agent.workflows import claim_workqueue, predict_expiry_risk


def test_claim_workqueue_is_sorted_by_priority():
    rows = claim_workqueue(date(2026, 11, 21))
    order = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}
    assert rows
    assert [order[row["priority"]] for row in rows] == sorted(order[row["priority"]] for row in rows)


def test_expiry_prediction_uses_snapshot_and_batch_evidence():
    result = predict_expiry_risk({
        "proposal_date": "30-06-2024",
        "stockist_code": "STK0001",
        "cnf_code": "CF-N01",
        "sku_code": "PFL1001",
        "batch_no": "M2300102",
        "proposed_quantity": 100,
    })
    assert result["evidence"]["batch"]["found"] is True
    assert result["evidence"]["snapshot"] is not None
    assert result["confidence"] == "proxy"


def test_expiry_prediction_is_unverified_without_batch_data():
    result = predict_expiry_risk({
        "proposal_date": "30-06-2024",
        "stockist_code": "STK0001",
        "cnf_code": "CF-N01",
        "sku_code": "PFL1001",
        "batch_no": "UNKNOWN",
        "proposed_quantity": 100,
    })
    assert result["risk_level"] == "unverified"
    assert result["recommendation"] == "human_review"
