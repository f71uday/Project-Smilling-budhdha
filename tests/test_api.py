"""The API answers without a model when we swap in a fake. No key, no cost."""
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

import agent.graph as g
from app import app


class FakeLLM:
    """Asks for one tool call, then answers. Enough to test the wiring."""

    def __init__(self):
        self.calls = 0

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.calls += 1
        if self.calls == 1:
            return AIMessage(content="", tool_calls=[{"name": "lookup_batch", "args": {"batch_no": "K2300101"}, "id": "t1"}])
        return AIMessage(content="Batch K2300101 expires on 30-09-2025.")


class FakeStructuredLLM:
    def __init__(self, result):
        self.result = result
        self.messages = None
        self.method = None

    def with_structured_output(self, schema, method=None):
        self.method = method
        return self

    def invoke(self, messages):
        self.messages = messages
        return self.result


def test_ask_runs_the_tool_loop(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr(g, "get_llm", lambda: fake)
    r = TestClient(app).post("/api/ask", json={"question": "When does K2300101 expire?"})
    assert r.status_code == 200
    body = r.json()
    assert "30-09-2025" in body["evidence"][0]
    assert body["model_calls"] == 2


def test_health():
    assert TestClient(app).get("/api/health").json()["ok"] is True


def test_list_and_get_claim_mail():
    client = TestClient(app)
    emails = client.get("/api/claims/mails").json()
    assert emails
    assert all("body" not in email for email in emails)

    response = client.get("/api/claims/mails/EML-022")
    assert response.status_code == 200
    assert response.json()["body"].startswith("Sir, resending our claim")


def test_analyze_claim_mail_uses_full_email_and_batch_master(monkeypatch):
    fake = FakeStructuredLLM(
        g.ClaimMailClassification(
            mail_type="claim",
            claim_reason="expiry",
            claim_items=[g.ClaimMailItem(batch_number="K2300101")],
        )
    )
    monkeypatch.setattr(g, "get_llm", lambda: fake)
    email = {
        "email_id": "TEST-001",
        "received_date": "01-10-2026",
        "from_name": "Example Medicals",
        "stockist_code_by_mailbox_rule": "STK0001",
        "subject": "Expiry claim",
        "body": "Please review batch K2300101.",
    }

    response = TestClient(app).post("/api/claims/analyze-mail", json=email)

    assert response.status_code == 200
    assert fake.method == "function_calling"
    assert "K2300101" in fake.messages[-1].content
    assert "Please review batch K2300101." in fake.messages[-1].content
    result = response.json()
    assert result["classification"] == {"mail_type": "claim", "claim_reason": "expiry"}
    assert result["batch_evidence"][0]["found"] is True
    assert result["batch_evidence"][0]["batch_no"] == "K2300101"
    assert result["batch_evidence"][0]["expiry_date"] == "30-09-2025"
    claim_details = result["claim_checks"][0]["claim_details"]
    assert claim_details["claim_reason"] == "expiry"
    assert claim_details["sku_code"] == "PFL1001"
    assert claim_details["sku_name"] == "Azithromycin 500 mg tablets"
    assert claim_details["expiry_date"] == "30-09-2025"
    assert claim_details["batch_verified"] is True
    assert result["claim_checks"][0]["expiry"]["status"] == "outside_provisional_window"
    assert "confidence" not in result["classification"]


def test_non_claim_mail_skips_batch_lookup(monkeypatch):
    fake = FakeStructuredLLM(
        g.ClaimMailClassification(mail_type="other", claim_reason="other", claim_items=[])
    )

    class UnexpectedBatchLookup:
        def invoke(self, _args):
            raise AssertionError("Non-claim emails must not look up batches")

    monkeypatch.setattr(g, "get_llm", lambda: fake)
    monkeypatch.setattr(g, "lookup_batch", UnexpectedBatchLookup())
    response = TestClient(app).post(
        "/api/claims/analyze-mail",
        json={
            "email_id": "TEST-002",
            "subject": "Scheme query",
            "body": "Will there be a December scheme?",
        },
    )

    assert response.status_code == 200
    assert response.json()["classification"]["mail_type"] == "other"
    assert response.json()["batch_evidence"] == []


def test_claim_analysis_checks_duplicate_history_and_provisional_expiry_window(monkeypatch):
    fake = FakeStructuredLLM(
        g.ClaimMailClassification(
            mail_type="claim",
            claim_reason="expiry",
            claim_items=[
                g.ClaimMailItem(
                    batch_number="K2300101",
                    invoice_reference="INV/001",
                    claimed_quantity="38",
                )
            ],
        )
    )

    class FakeClaimHistory:
        def invoke(self, args):
            assert args == {
                "stockist_code": "STK0001",
                "sku_code": "PFL1001",
                "batch_no": "K2300101",
            }
            return {
                "found": True,
                "claim_count": 1,
                "exact_duplicate_row_count": 0,
                "claims": [
                    {
                        "claim_no": "CLM-TEST-1",
                        "claim_date": "2025-08-01",
                        "claim_type": "Near expiry",
                        "original_invoice_ref": "INV/001",
                        "qty_claimed": "38",
                        "exact_duplicate_group_size": 1,
                    }
                ],
            }

    class FakeInvoiceQuantity:
        def invoke(self, args):
            assert args == {
                "invoice_no": "INV/001",
                "stockist_code": "STK0001",
                "sku_code": "PFL1001",
                "batch_no": "K2300101",
            }
            return {"found": True, "invoiced_qty": "40"}

    monkeypatch.setattr(g, "get_llm", lambda: fake)
    monkeypatch.setattr(g, "lookup_claim_history", FakeClaimHistory())
    monkeypatch.setattr(g, "lookup_invoice_quantity", FakeInvoiceQuantity())
    response = TestClient(app).post(
        "/api/claims/analyze-mail",
        json={
            "email_id": "TEST-003",
            "received_date": "15-08-2025",
            "from_name": "Example Medicals",
            "stockist_code_by_mailbox_rule": "STK0001",
            "subject": "Expiry claim",
            "body": "Batch K2300101, invoice INV/001, quantity 38.",
        },
    )

    assert response.status_code == 200
    checks = response.json()["claim_checks"][0]
    assert checks["duplicate"]["status"] == "possible_duplicate"
    assert checks["duplicate"]["prior_claim_refs"] == ["CLM-TEST-1"]
    assert checks["expiry"]["status"] == "within_provisional_window"
    assert checks["expiry"]["date_basis"] == "email_received_date"
    assert checks["quantity"]["status"] == "within_invoice_quantity"
    assert checks["quantity"]["invoiced_quantity"] == "40"
    assert checks["claim_details"]["claimed_quantity"] == "38"
    assert checks["claim_details"]["invoiced_quantity"] == "40"
    assert checks["duplicate"]["prior_claim_details"][0] == {
        "claim_no": "CLM-TEST-1",
        "claim_date": "2025-08-01",
        "claim_type": "Near expiry",
        "original_invoice_ref": "INV/001",
        "qty_claimed": "38",
    }


def test_get_unknown_claim_mail_returns_404():
    response = TestClient(app).get("/api/claims/mails/NOT-FOUND")
    assert response.status_code == 404
