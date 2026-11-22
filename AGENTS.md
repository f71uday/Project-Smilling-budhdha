# Instructions for the coding agent

Read this file before every task. Keep it short and keep it true.

## What we are building
An internal Commercial Operations pilot for reviewing channel claim emails, reconciling them against claim, invoice, batch and SKU CSVs, prioritising work, and assessing proposed stock allocations for expiry risk. It provides evidence and recommendations for human decisions; it does not post credits or execute allocations.

## Architecture
```text
Claim email -> LangGraph LLM extraction/classification -> deterministic CSV tools/rules -> claim case/workqueue -> human decision + audit
Allocation proposal -> plain Python risk rules + CSV evidence -> risk recommendation -> approver decision + audit
```

## Rules
- Facts come from tools that read `data/`. The model never writes a batch number, date,
  quantity or amount that did not come from a tool result.
- Going forward, do not use `run_question` for new work; use a purpose-built LangGraph flow.
- Business rules (claim windows, quantity limits, thresholds) live in plain Python in
  `agent/rules.py`, each with a pytest test.
- One small change per task. Run `pytest -q` after each change. Do not touch files the task
  does not need.
- Do not add a database, a vector store, a new framework or a new folder without asking.
- The frontend stays in `public/` as plain HTML, CSS and JavaScript.
- Secrets live only in `.env` locally and in Vercel environment variables. Never commit them.

## How to run
pip install -r requirements.txt uvicorn pytest httpx
pytest -q
uvicorn app:app --reload

## Current task
Implement the Solution Design MVP in the existing FastAPI, LangGraph, CSV and plain-JS app. Keep unsupported policy windows unverified and keep human decisions separate from automated actions.
