# Solution Design Document

## Project Sankalp: Claim Control and Expiry Risk

**Document status:** Proposed MVP design  
**Prepared for:** Pfizer domestic-channel engagement pilot  
**Prepared by:** Uday  
**Date:** 21 November 2026

---

## 1. Purpose

This document defines the design for a two-feature solution:

1. **AI Claim Mail Analyser** — convert claim emails and attachments into structured, reviewable claim records.
2. **Expiry Risk Predictor** — assess a proposed stock allocation or sale before it creates avoidable expiry risk.

The solution is a decision-support system. AI may extract, classify and recommend, but authorised commercial users remain responsible for claim credits and stock actions.

---

## 2. Business problem

### Claim processing problem

The supplied claim extract contains 4,526 claim rows worth INR 79.82 million:

- 884 claims have no invoice reference.
- 2,639 claim rows match the recorded invoice/batch/stockist/SKU combination.
- 28 claims claim more than invoiced quantity plus free packs.
- 242 near-expiry and 46 expired claims occur outside their policy windows.
- 995 claim rows belong to 462 stockist/SKU/batch groups.
- 23 rows are exact duplicate register rows.

Claim settlement is also slow:

- Average claim-to-credit time is 45.17 days against a 30-day target.
- 3,130 credited claims took more than 30 days.
- Their claim value is INR 52.84 million.
- 366 claims are pending, worth INR 9.51 million.
- 31 claims are rejected.

The business needs faster evidence collection, consistent validation and a prioritised workqueue.

### Expiry prevention problem

The data confirms 277 unique near-expiry or expired claims with an exact stockist/SKU/batch match to a scheme sale 0–270 days earlier. These claims represent approximately INR 6.12 million.

This timing relationship is not final proof that schemes caused every claim. The predictor will therefore use transparent risk factors, show the reason for a score and require secondary-sales evidence before making an automated restriction.

---

## 3. Solution objectives

1. Convert claim emails into auditable claim records.
2. Reconcile claims against invoice, batch, stockist, SKU and PTS data.
3. Rank claims by money, age, evidence completeness and policy risk.
4. Predict expiry risk before a proposed allocation or sale.
5. Recommend allow, reduce, hold or reallocate actions.
6. Keep every recommendation explainable.
7. Record reviewer decisions and overrides.

---

## 4. Scope

### In scope for MVP

- Email or manual claim upload.
- Attachment text and image extraction.
- Claim-field extraction and confidence.
- Invoice, batch, stockist, SKU and PTS reconciliation.
- Duplicate and quantity checks.
- Claim-window and expiry checks.
- TAT and pending-claim calculation.
- Risk-ranked claim workqueue.
- Batch, stockist, SKU and proposed-quantity expiry scoring.
- FEFO and allow/reduce/hold/reallocate recommendations.
- Human review and override.
- Exportable case evidence and audit trail.

### Out of scope for MVP

- Direct posting of credits to Finance systems.
- Automatic sales or stock transfer execution.
- Fraud-identity conclusion or fraud accusation.
- Fully automated claim rejection.
- Destruction approval.
- Secondary-sales model training without verified sell-through data.
- Direct access to email servers until security and mailbox ownership are confirmed.
- Replacement of C&F, ERP or finance systems.

---

## 5. High-level architecture

```text
Claim email / upload
        |
        v
Mail intake adapter ----> Original email and attachments
        |
        v
AI extraction service <--> LLM provider
        |
        v
Claim record and extraction confidence
        |
        v
Deterministic validation engine
  invoice, batch, stockist, SKU, quantity,
  PTS, expiry window, duplicates, TAT
        |
        v
Claim workqueue and audit trail
        |
        v
Human reviewer ----> approve / review / hold / reject / escalate


Proposed allocation / sale
        |
        v
Expiry risk engine
  batch expiry, inventory age, stock cover,
  demand, scheme purchase, previous claims
        |
        v
Risk score, reason codes and recommended action
        |
        v
Human Commercial / Supply Chain approver
        |
        v
Approved or amended allocation ----> actual outcome and claim feedback
```

The implementation uses the existing FastAPI, plain frontend and local data-pack pattern:

- `app.py` — API and static application entrypoint.
- `agent/llm.py` — model-provider access only.
- `agent/tools.py` — evidence and CSV data access.
- `agent/graph.py` — orchestration.
- `agent/rules.py` — deterministic money and policy rules.
- `public/` — plain HTML, CSS and JavaScript frontend.
- `analysis/` — offline verification and evidence scripts.
- `data/` — source CSV extracts.

The LLM does not calculate claim value, apply approval rules or change money-moving decisions. These remain plain Python operations.

---

## 6. Feature 1: AI Claim Mail Analyser

### 6.1 Functional flow

1. User forwards or uploads a claim email and attachments.
2. The intake layer records the original message and attachments unchanged.
3. The AI extracts structured fields and document text.
4. The deterministic engine normalises stockist and SKU identifiers.
5. The engine matches the claim against the register and master data.
6. The case receives an evidence score and policy findings.
7. The case enters the workqueue.
8. A user confirms the extracted fields or resolves low-confidence values.
9. The reviewer records a decision and reason.

### 6.2 Extracted fields

| Field | Source | Confidence handling |
|---|---|---|
| Claim reference | Email or attachment | Review if missing or ambiguous |
| Claim date | Email or attachment | Normalise to ISO date |
| Stockist code | Email, invoice or attachment | Match against master data |
| SKU | Email or invoice | Normalise hyphens and spaces |
| Batch number | Email or batch document | Match against batch master |
| Claimed quantity | Email or attachment | Reconcile against invoices/free goods |
| Claimed PTS value | Email or SKU master | Recalculate and compare |
| Invoice reference | Email or attachment | Flag missing invoice |
| Claim reason | Email text | Classify as expiry, damage, shortage or other |
| Attached evidence | Attachments | Record presence and document type |

### 6.3 Deterministic policy findings

| Finding | Rule |
|---|---|
| Missing invoice | Invoice reference is blank or has no match |
| Quantity exception | Claimed quantity exceeds invoiced quantity plus free packs |
| Policy-window breach | Claim is outside the batch expiry policy window |
| PTS exception | Recalculated PTS differs from claim PTS by more than INR 1 |
| Exact duplicate | Register fields match another claim row exactly |
| Repeated combination | Stockist/SKU/batch appears in multiple claim records |
| Over-30-day TAT | A credited claim took more than 30 calendar days |
| Pending claim | Claim has no credit or rejection outcome |

Rules remain in `agent/rules.py` and each rule must have a pytest test.

### 6.4 Claim status model

- `EXTRACTED` — New email converted into a draft record.
- `NEEDS_INFO` — Required evidence or field is missing.
- `READY_FOR_REVIEW` — Evidence and calculations are complete.
- `APPROVED` — Authorised user approved the claim.
- `HOLD` — Decision requires further evidence or escalation.
- `REJECTED` — Authorised user rejected under an identified policy rule.
- `DUPLICATE` — Authorised user confirmed an exact duplicate.
- `CREDITED` — Credit outcome recorded from the source system.

The model cannot place a claim directly into `APPROVED`, `REJECTED`, `DUPLICATE` or `CREDITED`.

### 6.5 Workqueue prioritisation

Suggested initial score:

| Factor | Priority logic |
|---|---|
| Claim value | Higher value receives higher priority |
| TAT | Credit older than 30 days receives higher priority |
| Missing evidence | Missing invoices and fields receive higher priority |
| Policy breach | Expiry-window or quantity exceptions receive higher priority |
| Duplicate risk | Duplicate or repeated combinations receive review priority |
| Pending age | Older pending claims receive higher priority |

Priority bands:

- **P1 — Immediate:** High value, policy breach or long ageing.
- **P2 — Evidence review:** Missing invoice or mismatched claim details.
- **P3 — Duplicate review:** Exact or repeated combination.
- **P4 — Standard:** Evidence complete and checks pass.
- **P5 — Monitoring:** Pending, low risk or awaiting external evidence.

The initial implementation may use configurable rule weights rather than a learned model. All weights must be visible and changeable for controlled pilot tuning.

---

## 7. Feature 2: Expiry Risk Predictor

### 7.1 Functional flow

1. User submits a proposed allocation or sale.
2. The system resolves stockist, SKU, batch, quantity and proposed date.
3. The engine checks inventory, batch expiry and normal demand.
4. It calculates risk and reason codes.
5. The system recommends allow, reduce, hold or reallocate.
6. A Commercial or Supply Chain user accepts, overrides or escalates.
7. The actual allocation and later outcome feed the evidence loop.

### 7.2 MVP risk inputs

| Input | Purpose |
|---|---|
| Batch expiry date | Time remaining before expiry |
| Proposed quantity | Order or allocation size |
| Inventory on hand | Risk of excess stock |
| Historical sales | Approximate consumption rate |
| Stock age | Remaining days of cover |
| Stockist/SKU buying pattern | Unusual purchase detection |
| Scheme quantity and scheme date | Compare large scheme-led purchases |
| Previous expiry claims | Stockist/SKU historical exposure |
| Previous duplicate or repeat claims | Suspicious repetition, without fraud conclusions |
| Region and C&F data | Routing and stock availability context |
| Secondary sales, where available | Improve actual sell-through measurement |

### 7.3 Explainable MVP rule

The initial predictor uses plain rules, for example:

```text
Estimated days of cover =
    proposed and existing inventory / normal daily sell-through

At-risk quantity =
    max(0, projected inventory - quantity needed before batch expiry)

Risk reasons =
    low days remaining,
    high days of stock,
    proposed quantity above normal purchase,
    scheme purchase above normal pattern,
    prior expiry claim,
    FEFO batch not used
```

Where sell-through is unavailable, the system labels the estimate as **primary-sales or historical proxy** and does not present it as confirmed secondary sell-through.

#### Current pilot scoring

The expiry-risk screen uses the C&F stock snapshot's average monthly outward as a demand proxy. Its provisional score is the sum of these signals, capped at 100:

| Signal | Points |
|---|---:|
| 90 days or less until expiry | 30 |
| 30 days or less until expiry | +30 |
| Projected cover above 90 days | 25 |
| Proposed quantity above average monthly outward | 30 |
| Prior expiry-related claim for the same stockist, SKU and batch | 10 |
| An earlier-expiring available batch was not selected | 10 |

Scores below 30 are Low, 30–59 are Medium, and 60 or above are High. Missing matched batch, stockist or snapshot evidence, or unavailable demand data, produces Unverified and a human-review recommendation. These weights and cut-offs are pilot heuristics, not approved commercial policy; validate them with Commercial and Supply Chain before operational use. A prior claim is only a review signal and never triggers a restriction by itself.

The current form does not capture proposed scheme details or persist reviewer overrides. It uses primary-sales proxy data and reports the matched CSV evidence; recommendations do not execute stock actions.

### 7.4 Risk output

| Risk level | Meaning | Recommended action |
|---|---|---|
| Low | Adequate cover and no material risk factors | Allow |
| Medium | One or more warning factors | Reduce quantity, alternate batch or obtain approval |
| High | Multiple risk factors or very low expiry cover | Hold and reallocate or escalate |
| Unverified | Critical evidence unavailable | Human review; no automatic restriction |

An output must include:

- Risk level.
- Risk score.
- Reason codes.
- Data confidence.
- FEFO batch recommendation.
- Proposed quantity reduction or reallocation suggestion.
- Evidence used.
- Reviewer override field.

### 7.5 Guardrails

- Never restrict a sale solely because a stockist previously raised a claim.
- Do not infer causality from scheme and claim co-occurrence alone.
- Use secondary sales for sell-through only when the records are available and matched.
- Keep a scheme purchase as a risk factor, not a fraud or policy conclusion.
- Prevent a rule from combining unidentified stockists or SKUs into a decision.
- No automatic cancellation or transfer in MVP.

---

## 8. Integrated workflow

```text
Incoming claim email
        -> AI extraction
        -> evidence validation
        -> ranked workqueue
        -> reviewer decision
        -> credit outcome

Proposed allocation
        -> expiry risk
        -> allow / reduce / hold / reallocate
        -> reviewer decision
        -> allocation outcome
        -> later claim and sell-through feedback
```

The claim history becomes feedback for future expiry risk:

- Confirmed expiry claim.
- Policy-window breach.
- Stockist/SKU/batch combination.
- Scheme and allocation timing.
- Whether the stock was later sold or returned.

The system must not treat claim feedback as cause unless the attribution is supported.

---

## 9. Data design

### Minimum claim case fields

- Case identifier.
- Source email or manual-upload identifier.
- Claim date.
- Claim reference.
- Stockist code.
- SKU code.
- Batch number.
- Claimed quantity.
- Claimed value.
- Invoice reference.
- Claim status.
- Extraction confidence.
- Evidence completeness.
- Policy findings.
- Priority.
- Owner.
- Reviewer.
- Final decision.
- Decision reason.
- Decision and override timestamps.

### Minimum allocation case fields

- Proposal identifier.
- Proposal date.
- Stockist code.
- SKU code.
- Proposed batch number.
- Proposed quantity.
- Source C&F code.
- Opening and projected inventory.
- Expiry date.
- Scheme code and scheme date.
- Risk level and score.
- Reason codes.
- Recommendation.
- Confidence.
- Reviewer and override.
- Final allocation quantity.
- Actual sell-through or claim outcome, where available.

For the pilot, records may be stored in the existing application environment or export files. A database is not required for the initial proof. Production storage should be selected after security and retention requirements are confirmed.

---

## 10. API design

The existing FastAPI entrypoint can expose these endpoints:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/health` | GET | Application and model availability |
| `/api/claims/analyse` | POST | Upload or submit claim email data |
| `/api/claims/{caseId}` | GET | Retrieve case evidence and status |
| `/api/claims/{caseId}/decision` | POST | Record authorised human decision |
| `/api/claims/workqueue` | GET | Retrieve prioritised claim cases |
| `/api/expiry/predict` | POST | Assess a proposed allocation or sale |
| `/api/expiry/{proposalId}/decision` | POST | Record allocation decision or override |
| `/api/audit/{caseId}` | GET | Retrieve case audit events |

Money-moving decision endpoints must enforce authentication and role checks before exposure in production.

---

## 11. AI design and guardrails

### AI responsibilities

- Read email text and documents.
- Extract and normalise candidate fields.
- Summarise evidence.
- Classify claim reasons and risk explanations.
- Ask for missing information.
- Generate human-readable reason text.

### AI exclusions

- No PTS or claim-value calculation.
- No policy-window calculation.
- No automatic credit amount.
- No automatic claim approval or rejection.
- No automatic allocation restriction.
- No unsupported cause or fraud statement.
- No deletion or overwrite of source records.

### Extraction safety

- Preserve the original email and attachments.
- Return field-level confidence.
- Require human confirmation for low-confidence or conflicting fields.
- Keep source text references or attachment names with extracted values.
- Never combine a field from an unrelated email or document.
- Mask sensitive fields in logs.

---

## 12. Human experience

### Claim email review

For each claim line, show the proposed claim reason, SKU code and name, claimed quantity, batch and batch expiry, and matched invoiced quantity. If the line is a possible duplicate, show the existing matching claim reference and its date, invoice and claimed quantity. Mark unavailable or unmatched fields as unverified.

### Claim workqueue screen

Required sections:

- Priority and claim value.
- Claim age and TAT.
- Stockist, SKU and batch.
- Invoice and evidence status.
- Policy findings.
- Extracted email summary.
- Attachment preview.
- PTS comparison.
- Repeated or duplicate finding.
- Suggested action.
- Reviewer decision and notes.

### Expiry risk screen

Required sections:

- Proposed stockist, SKU, batch and quantity.
- Days to expiry and estimated stock cover.
- Risk level and score.
- Individual reason codes.
- Scheme purchase and claim history context.
- FEFO alternative.
- Data gaps and confidence.
- Allow, reduce, hold or reallocate options.
- Reviewer decision and override reason.

---

## 13. Security and privacy

- Store credentials only in environment variables or a secrets manager.
- Do not commit API keys or `.env` files.
- Restrict claim and email access by role.
- Encrypt data in transit and at production rest.
- Retain original emails and attachments according to policy.
- Log access and every override.
- Remove or mask personal or unnecessary sensitive fields from prompts.
- Confirm whether the mailbox and source documents permit AI processing.

Recommended pilot roles:

- `analyst` — Extracts evidence and prepares review.
- `reviewer` — Reviews claims and expiry proposals.
- `approver` — Makes final credit or allocation decisions.
- `administrator` — Configures users and rule weights.
- `auditor` — Reads audit history.

---

## 14. Performance and reliability

### MVP targets

| Measure | Initial target |
|---|---|
| Claim mail extraction | < 60 seconds for a normal email |
| Workqueue refresh | < 5 seconds for a 5,000-row extract |
| Expiry prediction | < 3 seconds |
| Extraction availability | 99% during pilot hours |
| Source record preservation | 100% |
| Reviewer audit event recording | 100% |

Targets may be revised after pilot instrumentation.

The system should fail safely:

- Model unavailable: manual extraction remains available.
- Master data unavailable: mark evidence unverified.
- Ambiguous SKU or stockist: require review.
- Missing expiry: do not approve an expiry recommendation automatically.
- Missing sell-through: present as unverified proxy data.

---

## 15. Verification and test strategy

### Deterministic rule tests

pytest tests must cover:

- Missing invoice.
- Invoice/batch/stockist/SKU match.
- Quantity exceeds invoiced quantity plus free packs.
- Near-expiry policy window.
- Expired policy window.
- Exact duplicate register row.
- PTS difference above and below INR 1.
- Repeated stockist/SKU/batch group.
- TAT exactly at 30 days.
- TAT above 30 days.
- Pending and rejected claim states.

### AI extraction tests

- Structured email.
- Missing subject or body fields.
- PDF attachment.
- Image attachment.
- Conflicting fields in email and attachment.
- Unknown stockist or SKU.
- Two claims in one email.
- Low-quality document.
- Prompt-injection text inside an attachment.

### End-to-end tests

- Email to workqueue.
- Evidence match to reviewer screen.
- High-risk claim priority.
- AI field override.
- Claim approval or rejection audit event.
- Low, medium, high and unverified expiry outputs.
- FEFO recommendation.
- Allocation override and reason capture.
- Model unavailable fallback.

### Accuracy measures

- Field extraction precision and recall.
- Human correction rate.
- Invoice and batch match accuracy.
- Workqueue priority agreement.
- Expiry high-risk false-positive rate.
- Expiry high-risk false-negative rate.
- Time saved per claim.

The pilot must evaluate model errors by field and document type, not by a single average score.

---

## 16. Success metrics

### Claim processing

- Percentage of claims with complete evidence.
- Percentage with missing invoices.
- Average claim-to-credit time.
- Claims older than 30 days.
- Pending claim value.
- Manual review time per claim.
- Exact and repeated duplicate claims identified.
- Claim PTS differences found.
- Reviewer override rate.

### Expiry prevention

- High-risk allocations intercepted.
- High-risk allocations amended or held.
- Confirmed expiry claims after intervention.
- Stock value exposed by preventable expiry risk.
- FEFO compliance.
- False-positive and false-negative prediction rates.
- Human override reasons.

The pilot should report both:

- Potential value protected, and
- Verified outcome only after claims or inventory records confirm the result.

---

## 17. Deployment plan

### Phase 1 — Data and rule baseline

- Re-run the supplied analysis scripts.
- Confirm source file ownership and refresh process.
- Implement and test the deterministic rule engine.
- Establish baseline TAT and backlog.

### Phase 2 — Claim MVP

- Add mail or manual-upload intake.
- Add AI extraction and evidence review.
- Add claim workqueue and audit trail.
- Pilot with a small reviewed claim batch.

### Phase 3 — Expiry MVP

- Add proposed-allocation input.
- Add explainable expiry risk rules.
- Add FEFO and recommendation output.
- Pilot in selected stockist/SKU groups.

### Phase 4 — Feedback and evaluation

- Record actual allocation and claim outcomes.
- Validate whether the risk factors add predictive value.
- Tune only visible rules and thresholds.
- Consider supervised modelling only after sufficient outcome history.

---

## 18. Risks and mitigations

| Risk | Mitigation |
|---|---|
| AI extracts incorrect fields | Confidence scores, source references and human confirmation |
| Model provider outage | Manual entry and source-document review |
| Duplicate claims are valid repeated purchases | Present repeated combinations as review signals, not automatic fraud |
| Scheme sales are incorrectly treated as causes | Show co-occurrence; require additional sell-through evidence |
| Secondary sales are unavailable | Label proxy estimates and exclude them from confirmed attribution |
| High-risk recommendation blocks valid sales | Human override, explainable reasons and pilot tuning |
| Incomplete history biases the predictor | Report data gaps and prohibit high-confidence conclusions |
| Sensitive email data reaches logs or prompts | Data minimisation, masking and retention controls |
| Decision records are not reproducible | Save source data, rule version, model version and reviewer action |
| Regional stock transfer damages service | Keep transfers as draft recommendations requiring human approval |

---

## 19. Acceptance criteria

The pilot is ready for business evaluation when:

- Claim emails produce structured review records.
- Invoice, batch, stockist, SKU and PTS checks match source data.
- All deterministic money and policy checks are covered by tests.
- High-risk claims appear in a prioritised workqueue.
- Low-confidence extraction requires human review.
- Proposals produce low, medium, high or unverified expiry risk.
- Every recommendation shows evidence and reason codes.
- Humans can approve, hold or override with captured reasons.
- Source emails, fields, rule results and decisions remain auditable.
- No claim or allocation decision is executed without authorised human confirmation.
- Validation reports show both AI extraction quality and policy-rule accuracy.

---

## 20. Open decisions

The following should be confirmed before implementation:

1. Which mailbox or upload channel receives claims.
2. Which claim fields are mandatory.
3. Which role can approve, reject or hold a claim.
4. How pending, credited and rejected states are sourced.
5. Which expiry windows and quantity rules are authoritative.
6. Whether secondary-sales files exist and can be refreshed.
7. Which C&F and stockist fields are authoritative.
8. Which retention period applies to emails and attachments.
9. Whether pilot records remain local or use approved hosted storage.
10. Which user interface is needed for the first pilot.

---

## 21. Recommended MVP

Build the two features as a shared decision-support pilot:

1. **Claim mail analyser:** structure evidence and surface inconsistencies.
2. **Deterministic claim control:** validate policy and prioritise work.
3. **Expiry risk predictor:** score proposed allocations using explainable rules.
4. **Human workqueues:** combine claim review and allocation review.
5. **Audit feedback:** preserve every decision and actual outcome.

The goal is not to replace Commercial Operations. It is to give analysts and approvers complete evidence, consistent rules and a prioritized action trail before money or stock is exposed.
