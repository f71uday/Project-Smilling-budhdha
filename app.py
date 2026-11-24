"""FastAPI entrypoint. Vercel finds the FastAPI instance named `app` in app.py.

Run locally:   uvicorn app:app --reload        then open http://127.0.0.1:8000
On Vercel:     the files in public/ are served from the CDN; /api/* reaches this app.
"""
import csv
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from agent.graphs import analyze_claim_mail, check_scheme_eligibility, predict_expiry_risk, run_question
from agent.tools import expiry_risk_options
from agent.workqueue import claim_workqueue

app = FastAPI(title="Project Sankalp pilot")
ROOT = Path(__file__).resolve().parent
CLAIM_EMAILS = ROOT / "data" / "claim_emails.csv"


class Ask(BaseModel):
    question: str


class ClaimMailRequest(BaseModel):
    email_id: str = Field(min_length=1)
    received_date: str = ""
    from_name: str = ""
    stockist_code_by_mailbox_rule: str = ""
    subject: str = ""
    body: str = Field(min_length=1)


class ExpiryRiskRequest(BaseModel):
    proposal_date: str = Field(min_length=1)
    stockist_code: str = Field(min_length=1)
    cnf_code: str = Field(min_length=1)
    sku_code: str = Field(min_length=1)
    batch_no: str = Field(min_length=1)
    proposed_quantity: Decimal = Field(gt=0)


def _read_claim_emails() -> list[dict[str, str]]:
    with CLAIM_EMAILS.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


@app.get("/api/health")
def health():
    """Quick check that the deployment is alive and the key is configured."""
    return {"ok": True, "model_key_set": bool(os.getenv("OPENROUTER_API_KEY"))}


@app.post("/api/ask")
def ask(body: Ask):
    """Run one question through the graph and return the answer and the evidence."""
    try:
        return run_question(body.question)
    except ValueError as err:  # missing key or bad input: say so instead of a bare 500
        return JSONResponse({"error": str(err)}, status_code=503)


@app.get("/api/claims/mails")
def list_claim_mails():
    """List sample emails for the claim review screen without loading their full bodies."""
    return [
        {
            "email_id": email["email_id"],
            "received_date": email["received_date"],
            "from_name": email["from_name"],
            "subject": email["subject"],
        }
        for email in _read_claim_emails()
    ]


@app.get("/api/claims/mails/{email_id}")
def get_claim_mail(email_id: str):
    """Return one complete sample email for review."""
    for email in _read_claim_emails():
        if email["email_id"] == email_id:
            return email
    raise HTTPException(status_code=404, detail="Email not found")


@app.get("/api/claims/workqueue")
def get_claim_workqueue(status: str = "Pending", limit: int = 50, as_of: date | None = None):
    """Read-only prioritised claim queue. status=all returns every claim; as_of defaults to today."""
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 500")
    return claim_workqueue(as_of or date.today(), None if status.lower() == "all" else status, limit)


@app.post("/api/claims/analyze-mail")
def analyze_mail(body: ClaimMailRequest):
    """Classify a selected email and check any stated batches against the batch master."""
    try:
        return {"email_id": body.email_id, **analyze_claim_mail(body.model_dump())}
    except ValueError as err:
        return JSONResponse({"error": str(err)}, status_code=503)


@app.get("/api/expiry/options")
def list_expiry_risk_options():
    """Provide CSV-backed choices for the expiry risk form."""
    return expiry_risk_options()


@app.post("/api/expiry/predict")
def predict_expiry_risk_route(body: ExpiryRiskRequest):
    """Return a deterministic expiry risk estimate with its source evidence."""
    return predict_expiry_risk(body.model_dump())


@app.post("/api/scheme/check")
def check_scheme_route(body: ExpiryRiskRequest):
    """Say whether a scheme can be offered on near-expiry C&F stock, and the money it would save."""
    return check_scheme_eligibility(body.model_dump())


@app.get("/")
def index():
    return FileResponse(ROOT / "public" / "index.html")


# On Vercel the public/ folder is served by the platform, and Vercel's docs say not to
# mount it. On your laptop nothing serves it, so mount it only when not on Vercel.
if not os.getenv("VERCEL"):
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=ROOT / "public"), name="public")
