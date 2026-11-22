# Project Sankalp pilot: starter

The project is up and running at [https://project-smilling-budhdha.vercel.app](https://project-smilling-budhdha.vercel.app).

An optional skeleton for the recommended path. It already deploys to Vercel: a FastAPI backend, a LangGraph tool loop and a
plain HTML page. It proves your pipeline works on day one. Replace the graph, the tools and
the page with your own design.

```
app.py                   FastAPI entrypoint (Vercel looks for `app` here)
agent/llm.py             the only file that knows the model provider (OpenRouter)
agent/cleaning.py        input cleaning and prompt-injection screening
agent/tools/             @tool data lookups (batches, claims, sales, stock); facts come from here
agent/rules/             plain-Python business rules (claims, expiry risk, scheme, savings)
agent/graphs/            LangGraph flows
  claim_mail.py            email -> intent -> extract -> checks -> summary (3 model calls)
  expiry_risk.py           allocation proposal -> evidence -> risk score (no model)
  scheme.py                near-expiry C&F stock -> scheme eligibility + money saved (no model)
  question.py              legacy question loop; not for new work
data/                    the CSVs from the data pack
public/                  index.html, app.js, style.css: the frontend
tests/                   run with pytest; no API key needed
AGENTS.md                instructions for your AI coding agent
```

## Run it on your laptop

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt uvicorn pytest httpx
cp .env.example .env               # then put your OpenRouter key in .env
pytest -q
uvicorn app:app --reload
```

Open http://127.0.0.1:8000. The pilot includes a claim inbox, manual email intake, a claim workqueue,
evidence checks, reviewer decisions, JSON case export, and an expiry-risk assessment screen.

## Pilot workflows

Claim analysis classifies and extracts fields with the LLM, then checks invoice/stockist, batch/SKU,
claim quantity against invoiced plus free quantity, claimed PTS, and prior claim history using the CSVs.
Missing evidence and low-confidence fields remain for human review. Claim windows are marked unverified
until an authoritative policy is supplied. Review decisions never post credits or execute stock changes.

Expiry prediction uses batch expiry, C&F stock snapshots, historical outward as a proxy, prior claims,
and optional scheme history. Old or missing inventory data produces an `unverified` result. Every result
includes reason codes, evidence and any FEFO alternative.

The pilot keeps newly created cases and audit events in process memory. They are lost when the server
restarts; the claim register remains read-only. Claim evidence can be exported as JSON before a restart.
Basic `.eml`/`.txt` email upload is supported; attachment extraction, OCR and mailbox integration are not connected. Durable production storage is also not configured.

For Vercel, configure `SANKALP_ROLE_TOKENS` as a JSON object in an environment variable, mapping role
names (`analyst`, `reviewer`, `approver`, `administrator`, `auditor`) to distinct bearer tokens. The page
accepts a token in the access field. Local development bypasses role-token checks. Never commit token values.

Implemented API routes include `/api/claims/analyse`, `/api/claims/workqueue`, `/api/claims/{caseId}`,
`/api/claims/{caseId}/decision`, `/api/expiry/predict`, `/api/expiry/{proposalId}/decision`, and
`/api/audit/{caseId}`.

## Deploy

Follow the step-by-step section in the Build and Deploy Guide. In short: push to GitHub,
import the repository in Vercel, add `OPENROUTER_API_KEY` as an environment variable, deploy.
