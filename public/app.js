const mailSelect = document.getElementById("mail-select");
const analyzeButton = document.getElementById("analyze-button");
const statusMessage = document.getElementById("status");
const analysisPanel = document.getElementById("analysis-panel");
const reviewTabs = [...document.querySelectorAll('[role="tab"]')];
let selectedMail = null;
let expiryOptions = null;

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item) => item.msg).join("; ")
      : data.detail;
    throw new Error(detail || data.error || `Server returned ${response.status}`);
  }
  return data;
}

function showMail(mail) {
  selectedMail = mail;
  document.getElementById("mail-subject").textContent = mail.subject || "(No subject)";
  document.getElementById("mail-date").textContent = mail.received_date || "";
  document.getElementById("mail-sender").textContent = mail.from_name || "Unknown sender";
  document.getElementById("mail-body").textContent = mail.body || "(This email has no body.)";

  const hasStockist = Boolean(mail.stockist_code_by_mailbox_rule);
  document.getElementById("stockist-row").hidden = !hasStockist;
  document.getElementById("mail-stockist").textContent = mail.stockist_code_by_mailbox_rule || "";

  analysisPanel.hidden = true;
  analyzeButton.disabled = false;
  statusMessage.textContent = "Email loaded. Run analysis when you are ready.";
}

async function loadSelectedMail() {
  const emailId = mailSelect.value;
  if (!emailId) return;

  mailSelect.disabled = true;
  analyzeButton.disabled = true;
  statusMessage.textContent = "Loading the complete email...";
  try {
    const mail = await requestJson(`/api/claims/mails/${encodeURIComponent(emailId)}`);
    showMail(mail);
  } catch (error) {
    selectedMail = null;
    document.getElementById("mail-subject").textContent = "Email could not be loaded";
    document.getElementById("mail-date").textContent = "";
    document.getElementById("mail-sender").textContent = "";
    document.getElementById("mail-body").textContent = "";
    document.getElementById("stockist-row").hidden = true;
    analysisPanel.hidden = true;
    statusMessage.textContent = `Could not load this email: ${error.message}`;
  } finally {
    mailSelect.disabled = false;
    analyzeButton.disabled = !selectedMail;
  }
}

function formatClaimReason(reason) {
  const labels = {
    expiry: "Expiry",
    damage: "Damage",
    shortage: "Shortage",
    status_follow_up: "Claim status follow-up",
    other: "Other claim",
  };
  return labels[reason] || "Claim";
}

function renderBatchResults(evidence) {
  const list = document.getElementById("batch-results");
  list.replaceChildren();

  if (!evidence.length) {
    const item = document.createElement("li");
    item.textContent = "No batch number was identified in the email.";
    list.append(item);
    return;
  }

  for (const result of evidence) {
    const item = document.createElement("li");
    if (!result.found) {
      item.classList.add("not-found");
      item.textContent = "A batch number from the email was not found in the batch master.";
      list.append(item);
      continue;
    }

    const batchCode = document.createElement("span");
    batchCode.className = "batch-code";
    batchCode.textContent = result.batch_no;
    item.append(batchCode);

    const facts = [
      result.product_description,
      result.expiry_date ? `Expiry: ${result.expiry_date}` : "",
      result.pts_inr ? `PTS (INR): ${result.pts_inr}` : "",
    ].filter(Boolean);
    const detail = document.createElement("span");
    detail.textContent = facts.join(" | ") || "Batch found in the batch master.";
    item.append(detail);
    list.append(item);
  }
}

function statusLabel(status) {
  const labels = {
    possible_duplicate: "Possible duplicate",
    repeated_history: "Prior claims on this combination",
    no_prior_match: "No matching claim history",
    unverified: "Unverified",
    within_invoice_quantity: "Claim is less than invoiced quantity",
    equal_to_invoice_quantity: "Claim equals invoiced quantity",
    exceeds_invoice_quantity: "Claim exceeds invoiced quantity",
    within_provisional_window: "Within provisional 90-day window",
    outside_provisional_window: "Outside provisional 90-day window",
  };
  return labels[status] || "Not checked";
}

function renderClaimLineDetails(item, details, quantity) {
  const section = document.createElement("section");
  section.className = "claim-line-details";

  const heading = document.createElement("h5");
  heading.textContent = "Claim details";
  section.append(heading);

  const batch = details?.batch_no
    ? `${details.batch_no}${details.batch_verified ? "" : " (not verified in batch master)"}`
    : "Not stated in email";
  const invoicedQuantity = quantity?.invoiced_quantity ?? details?.invoiced_quantity;
  const fields = [
    ["Claim proposed", details?.claim_reason ? formatClaimReason(details.claim_reason) : "Not identified"],
    ["SKU", details?.sku_code || "Not verified from batch master"],
    ["SKU name", details?.sku_name || "Not verified from batch master"],
    ["Claimed quantity", details?.claimed_quantity || "Not stated in email"],
    ["Batch", batch],
    ["Batch expiry date", details?.expiry_date || "Not available from batch master"],
    ["Invoiced quantity", invoicedQuantity === undefined || invoicedQuantity === null
      ? "Not verified"
      : `${invoicedQuantity} packs`],
  ];
  const list = document.createElement("dl");
  list.className = "claim-fields claim-line-fields";
  for (const [label, value] of fields) {
    const field = document.createElement("div");
    const term = document.createElement("dt");
    term.textContent = label;
    const detail = document.createElement("dd");
    detail.textContent = value;
    field.append(term, detail);
    list.append(field);
  }
  section.append(list);
  item.append(section);
}

function appendCheck(item, title, result) {
  const row = document.createElement("div");
  row.className = "claim-check-row";

  const heading = document.createElement("div");
  heading.className = "claim-check-row-heading";

  const label = document.createElement("strong");
  label.textContent = title;
  heading.append(label);

  const badge = document.createElement("span");
  badge.className = `check-status is-${result.status}`;
  badge.textContent = statusLabel(result.status);
  heading.append(badge);
  row.append(heading);

  if (result.reason) {
    const reason = document.createElement("p");
    reason.textContent = result.reason;
    row.append(reason);
  }
  if (result.window_start && result.window_end) {
    const dates = document.createElement("p");
    dates.className = "check-dates";
    dates.textContent = `Window checked: ${result.window_start} to ${result.window_end}`;
    row.append(dates);
  }
  if (result.prior_claim_refs?.length) {
    const claims = result.prior_claim_details || [];
    if (claims.length) {
      for (const claim of claims) {
        const existing = document.createElement("p");
        existing.className = "check-dates";
        const label = result.status === "possible_duplicate" && !result.within_email_repeat
          ? "Matching existing claim"
          : "Prior claim";
        const details = [
          claim.claim_no,
          claim.claim_date ? `date ${claim.claim_date}` : "",
          claim.claim_type ? `type ${claim.claim_type}` : "",
          claim.original_invoice_ref ? `invoice ${claim.original_invoice_ref}` : "",
          claim.qty_claimed ? `claimed quantity ${claim.qty_claimed}` : "",
        ].filter(Boolean);
        existing.textContent = `${label}: ${details.join(" | ")}`;
        row.append(existing);
      }
    } else {
      const references = document.createElement("p");
      references.className = "check-dates";
      references.textContent = `Prior claim references: ${result.prior_claim_refs.join(", ")}`;
      row.append(references);
    }
  }
  if (result.within_email_repeat) {
    const repeatedLine = document.createElement("p");
    repeatedLine.className = "check-dates";
    repeatedLine.textContent = "The same batch, invoice and quantity line also appears in this email.";
    row.append(repeatedLine);
  }
  if (result.exact_duplicate_register_rows > 0) {
    const duplicateRows = document.createElement("p");
    duplicateRows.className = "check-dates";
    duplicateRows.textContent = `The matched register entry has ${result.exact_duplicate_register_rows} exact duplicate row(s).`;
    row.append(duplicateRows);
  }
  item.append(row);
}

function renderClaimChecks(checks) {
  const list = document.getElementById("claim-check-results");
  list.replaceChildren();
  const policyNote = document.getElementById("expiry-policy-note");
  const hasExpiryCheck = checks.some((check) => check.expiry?.status !== "not_applicable");
  policyNote.hidden = !hasExpiryCheck;

  if (!checks.length) {
    const item = document.createElement("li");
    item.textContent = "No claim lines were extracted. Review the email and run the analysis again.";
    list.append(item);
    return;
  }

  checks.forEach((check, index) => {
    const item = document.createElement("li");
    item.className = "claim-check-item";

    const heading = document.createElement("h4");
    heading.textContent = check.batch_no ? `Batch ${check.batch_no}` : `Claim line ${index + 1}`;
    item.append(heading);

    renderClaimLineDetails(item, check.claim_details, check.quantity);
    appendCheck(item, "Invoiced quantity check", check.quantity);
    appendCheck(item, "Duplicate check", check.duplicate);
    if (check.expiry?.status !== "not_applicable") {
      appendCheck(item, "Expiry-window check", check.expiry);
    }
    list.append(item);
  });
}

function showAnalysis(data) {
  const classification = data.classification;
  const isClaim = classification.mail_type === "claim";
  const badge = document.getElementById("mail-type");
  const intentLabels = {claim: "Claim email", damage: "Damage claim", complaint: "Complaint", safety: "Safety report", other: "Not a claim email"};
  badge.textContent = intentLabels[classification.intent] || (isClaim ? "Claim email" : "Not a claim email");
  badge.classList.toggle("is-other", !isClaim);

  const warnings = [];
  if (data.security?.injection_suspected) warnings.push("Possible prompt injection in this email; treat with care.");
  if (data.needs_human) warnings.push("Human review required.");
  if (data.estimated_saving_inr > 0) warnings.push(`Estimated saving from flagged duplicates: INR ${data.estimated_saving_inr.toLocaleString("en-IN")}.`);
  document.getElementById("analysis-message").textContent = [data.message, ...warnings].join(" ");
  document.getElementById("analysis-summary").textContent = isClaim
    ? `Claim reason: ${formatClaimReason(classification.claim_reason)}.`
    : "This message is not routed for claim checks.";

  const batchBlock = document.getElementById("batch-block");
  batchBlock.hidden = !isClaim;
  const claimChecksBlock = document.getElementById("claim-checks-block");
  claimChecksBlock.hidden = !isClaim;
  if (isClaim) {
    renderBatchResults(data.batch_evidence || []);
    renderClaimChecks(data.claim_checks || []);
  }

  analysisPanel.hidden = false;
}

async function loadEmails() {
  try {
    const emails = await requestJson("/api/claims/mails");
    if (!emails.length) {
      mailSelect.replaceChildren(new Option("No sample emails found", ""));
      statusMessage.textContent = "No sample emails are available.";
      return;
    }

    mailSelect.replaceChildren(
      ...emails.map((email) => new Option(
        `${email.subject} — ${email.from_name} (${email.received_date})`,
        email.email_id
      ))
    );
    mailSelect.disabled = false;
    await loadSelectedMail();
  } catch (error) {
    mailSelect.replaceChildren(new Option("Could not load emails", ""));
    statusMessage.textContent = `Could not load the email list: ${error.message}`;
  }
}

document.getElementById("custom-mail-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const [year, month, day] = document.getElementById("custom-date").value.split("-");
  showMail({
    email_id: "CUSTOM-" + Date.now(),
    received_date: year ? `${day}-${month}-${year}` : "",
    from_name: document.getElementById("custom-from").value.trim(),
    stockist_code_by_mailbox_rule: document.getElementById("custom-stockist").value.trim(),
    subject: document.getElementById("custom-subject").value.trim(),
    body: document.getElementById("custom-body").value,
  });
  statusMessage.textContent = "Your email is loaded. Run analysis when you are ready.";
});

mailSelect.addEventListener("change", loadSelectedMail);

analyzeButton.addEventListener("click", async () => {
  if (!selectedMail) return;

  mailSelect.disabled = true;
  analyzeButton.disabled = true;
  statusMessage.textContent = "Analyzing the email...";
  analysisPanel.hidden = true;
  try {
    const result = await requestJson("/api/claims/analyze-mail", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(selectedMail),
    });
    showAnalysis(result);
    statusMessage.textContent = "Analysis complete.";
  } catch (error) {
    statusMessage.textContent = `Analysis failed: ${error.message}`;
  } finally {
    mailSelect.disabled = false;
    analyzeButton.disabled = !selectedMail;
  }
});

function activateReviewTab(tab, moveFocus = false) {
  for (const candidate of reviewTabs) {
    const active = candidate === tab;
    candidate.setAttribute("aria-selected", String(active));
    candidate.tabIndex = active ? 0 : -1;
    document.getElementById(candidate.getAttribute("aria-controls")).hidden = !active;
  }
  if (moveFocus) tab.focus();
}

reviewTabs.forEach((tab, index) => {
  tab.addEventListener("click", () => activateReviewTab(tab));
  tab.addEventListener("keydown", (event) => {
    let nextIndex;
    if (event.key === "ArrowRight") nextIndex = (index + 1) % reviewTabs.length;
    else if (event.key === "ArrowLeft") nextIndex = (index - 1 + reviewTabs.length) % reviewTabs.length;
    else if (event.key === "Home") nextIndex = 0;
    else if (event.key === "End") nextIndex = reviewTabs.length - 1;
    else return;
    event.preventDefault();
    activateReviewTab(reviewTabs[nextIndex], true);
  });
});

const expiryForm = document.getElementById("expiry-form");
const expiryFormStatus = document.getElementById("expiry-form-status");
const expirySubmit = document.getElementById("expiry-submit");
const expiryResult = document.getElementById("expiry-result");
const stockistSelect = document.getElementById("proposal-stockist");
const cnfSelect = document.getElementById("proposal-cnf");
const skuSelect = document.getElementById("proposal-sku");
const batchSelect = document.getElementById("proposal-batch");

function clearExpiryResultOnEdit() {
  if (!expiryResult.hidden) {
    expiryResult.hidden = true;
    expiryFormStatus.textContent = "Proposal changed. Assess again to refresh the result.";
  }
}

expiryForm.addEventListener("input", clearExpiryResultOnEdit);
expiryForm.addEventListener("change", clearExpiryResultOnEdit);

function setSelectOptions(select, placeholder, options, valueFor, labelFor) {
  select.replaceChildren(new Option(placeholder, ""));
  for (const item of options) {
    select.add(new Option(labelFor(item), valueFor(item)));
  }
}

function localDateValue() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

function updateBatchOptions() {
  if (!expiryOptions) return;
  const skuCode = skuSelect.value;
  const batches = expiryOptions.batches.filter((batch) => batch.sku_code === skuCode);
  setSelectOptions(
    batchSelect,
    skuCode ? "Select a batch" : "Choose a product first",
    batches,
    (batch) => batch.batch_no,
    (batch) => `${batch.batch_no} (expires ${batch.expiry_date})`
  );
  batchSelect.disabled = !skuCode || !batches.length;
}

async function loadExpiryRiskOptions() {
  try {
    expiryOptions = await requestJson("/api/expiry/options");
    setSelectOptions(
      stockistSelect,
      "Select a stockist",
      expiryOptions.stockists,
      (stockist) => stockist.stockist_code,
      (stockist) => `${stockist.stockist_code} — ${stockist.stockist_name}`
    );
    setSelectOptions(
      cnfSelect,
      "Select a C&F centre",
      expiryOptions.cnfs,
      (cnf) => cnf.cnf_code,
      (cnf) => cnf.cnf_code
    );
    setSelectOptions(
      skuSelect,
      "Select a product",
      expiryOptions.skus,
      (sku) => sku.sku_code,
      (sku) => `${sku.sku_code} — ${sku.product_description}`
    );
    updateBatchOptions();
    stockistSelect.disabled = false;
    cnfSelect.disabled = false;
    skuSelect.disabled = false;
    document.getElementById("proposal-date").value = localDateValue();
    expirySubmit.disabled = false;
    expiryFormStatus.textContent = "Source lists loaded. Choose the proposal details.";
  } catch (error) {
    expiryFormStatus.textContent = `Could not load expiry risk options: ${error.message}`;
  }
}

function formatRiskReason(code) {
  const labels = {
    SHELF_LIFE_UNDER_12_MONTHS: "The batch has under 12 months of shelf life left.",
    SHELF_LIFE_UNDER_9_MONTHS: "The batch has under 9 months of shelf life left.",
    SCHEME_SALE: "This is a scheme sale. Scheme sales lead to expiry claims far more often.",
    ORDER_ABOVE_USUAL_SIZE: "The quantity is more than twice this stockist's usual order for the product.",
    STOCK_COVER_UNAVAILABLE: "No usable C&F stock snapshot, so stock cover and FEFO were not scored.",
    LOW_DAYS_TO_EXPIRY: "The batch has 90 days or less until expiry.",
    VERY_LOW_DAYS_TO_EXPIRY: "The batch has 30 days or less until expiry.",
    HIGH_PROJECTED_DAYS_OF_COVER: "Projected stock covers more than 90 days of average outward.",
    PROPOSED_ABOVE_MONTHLY_OUTWARD: "The proposed quantity is above average monthly outward.",
    PRIOR_EXPIRY_CLAIM: "An expiry-related claim exists for this stockist, product and batch. This is a review signal only.",
    FEFO_BATCH_NOT_USED: "Another available batch has an earlier expiry date.",
    FEFO_EVIDENCE_UNAVAILABLE: "No eligible batch was available in the snapshot for a FEFO comparison.",
    INVALID_PROPOSAL_DATE: "Enter a valid proposal date.",
    INVALID_PROPOSED_QUANTITY: "Enter a positive proposed quantity.",
    BATCH_NOT_FOUND: "The selected batch was not found in the batch master.",
    BATCH_SKU_MISMATCH: "The selected batch does not belong to the selected product.",
    STOCKIST_NOT_FOUND: "The stockist was not found in the stockist master.",
    STOCKIST_CNF_MISMATCH: "The selected stockist is not mapped to this C&F centre.",
    SNAPSHOT_NOT_FOUND: "No stock snapshot was found before the proposal date.",
    BATCH_SNAPSHOT_NOT_FOUND: "The selected batch is missing from the latest matching stock snapshot.",
    AMBIGUOUS_BATCH_SNAPSHOT: "More than one conflicting stock row exists for this batch and snapshot.",
    INVALID_INVENTORY_QUANTITY: "The snapshot inventory quantity is missing or invalid.",
    SELL_THROUGH_UNAVAILABLE: "Average monthly outward is missing or zero, so days of cover cannot be estimated.",
    BATCH_EXPIRY_DATE_UNAVAILABLE: "The batch expiry date is missing or invalid.",
  };
  return labels[code] || code.replaceAll("_", " ").toLowerCase();
}

function appendListItem(list, text) {
  const item = document.createElement("li");
  item.textContent = text;
  list.append(item);
}

function renderExpiryRisk(result, proposal) {
  const badge = document.getElementById("expiry-risk-badge");
  const riskLevel = result.risk_level || "unverified";
  badge.className = `risk-badge is-${riskLevel}`;
  badge.textContent = riskLevel;

  document.getElementById("expiry-risk-score").textContent =
    result.risk_score === null ? "Not available" : `${result.risk_score} / 100`;

  const recommendationText = {
    allow: "Low pilot signal. Normal review still applies.",
    reduce_or_approval: "Consider reducing the quantity or seeking approval.",
    hold_or_reallocate: "Hold for human review; consider FEFO or reallocation.",
    human_review: "Evidence is incomplete. Check the source records before deciding.",
  };
  document.getElementById("expiry-recommendation").textContent =
    recommendationText[result.recommendation] || "Human review is required.";

  const reasons = document.getElementById("expiry-reasons");
  reasons.replaceChildren();
  if (result.reasons?.length) {
    result.reasons.forEach((code) => appendListItem(reasons, formatRiskReason(code)));
  } else {
    appendListItem(reasons, "No pilot risk triggers were identified in the available evidence.");
  }

  const metricLabels = {
    days_to_expiry: "Days to expiry",
    current_inventory_packs: "Current inventory",
    proposed_quantity_packs: "Proposed quantity",
    usual_order_packs: "Usual order for this stockist",
    projected_inventory_packs: "Projected inventory",
    average_monthly_outward_packs: "Average monthly outward",
    projected_days_of_cover: "Projected days of cover",
    estimated_at_risk_packs: "Estimated quantity at risk",
  };
  const metrics = document.getElementById("expiry-metrics");
  metrics.replaceChildren();
  for (const [key, label] of Object.entries(metricLabels)) {
    if (result.metrics?.[key] === undefined) continue;
    let value = result.metrics[key];
    if (key === "days_to_expiry") {
      value = value < 0
        ? `Expired ${Math.abs(value)} days before the proposal`
        : value === 0
          ? "Expires on the proposal date"
          : `${value} days`;
    } else if (key === "projected_days_of_cover") {
      value = `${value} days`;
    } else {
      value = `${value} packs`;
    }
    const field = document.createElement("div");
    const term = document.createElement("dt");
    term.textContent = label;
    const detail = document.createElement("dd");
    detail.textContent = value;
    field.append(term, detail);
    metrics.append(field);
  }

  const batch = result.evidence?.batch;
  const fefo = result.evidence?.fefo;
  const fefoMessage = fefo
    ? fefo.batch_no === proposal.batch_no
      ? `${fefo.batch_no} is the earliest-expiring available batch in the snapshot (${fefo.expiry_date}).`
      : `Earlier-expiring available batch: ${fefo.batch_no}, expiring ${fefo.expiry_date}, with ${fefo.qty_on_hand_packs} packs recorded.`
    : "No eligible batch was available in the latest snapshot for a FEFO comparison.";
  document.getElementById("expiry-fefo").textContent = fefoMessage;

  const evidenceList = document.getElementById("expiry-evidence");
  evidenceList.replaceChildren();
  const stockist = result.evidence?.stockist;
  if (stockist) {
    appendListItem(evidenceList, `Stockist: ${stockist.stockist_code} — ${stockist.stockist_name}; mapped C&F: ${stockist.cnf_code}.`);
  } else if (proposal.stockist_code) {
    appendListItem(evidenceList, `Stockist code checked: ${proposal.stockist_code}.`);
  }
  if (batch?.found) {
    appendListItem(evidenceList, `Batch master: ${batch.batch_no}, ${batch.product_description || batch.sku_code}, expiry ${batch.expiry_date}.`);
  } else {
    appendListItem(evidenceList, "Batch master did not verify the selected batch.");
  }
  const snapshot = result.evidence?.snapshot;
  if (snapshot) {
    appendListItem(evidenceList, `C&F stock snapshot dated ${snapshot.snapshot_date}: ${snapshot.qty_on_hand_packs} packs on hand; average monthly outward ${snapshot.avg_monthly_outward_packs} packs.`);
  } else {
    appendListItem(evidenceList, "No matching C&F stock snapshot was available.");
  }
  const priorClaims = result.evidence?.prior_expiry_claims || [];
  appendListItem(
    evidenceList,
    priorClaims.length
      ? `Expiry-related claim history: ${priorClaims.map((claim) => claim.claim_no).filter(Boolean).join(", ") || `${priorClaims.length} matching record(s)`}.`
      : "No matching expiry-related claim was found."
  );
  document.getElementById("expiry-data-basis").textContent = result.data_basis || "";
  expiryResult.hidden = false;
}

stockistSelect.addEventListener("change", () => {
  const stockist = expiryOptions?.stockists.find((item) => item.stockist_code === stockistSelect.value);
  if (stockist?.cnf_code) cnfSelect.value = stockist.cnf_code;
});

skuSelect.addEventListener("change", updateBatchOptions);

expiryForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!expiryForm.reportValidity()) return;

  const proposal = {
    proposal_date: document.getElementById("proposal-date").value,
    stockist_code: stockistSelect.value,
    cnf_code: cnfSelect.value,
    sku_code: skuSelect.value,
    batch_no: batchSelect.value,
    proposed_quantity: Number(document.getElementById("proposal-quantity").value),
    on_scheme: document.getElementById("proposal-scheme").checked,
  };
  expirySubmit.disabled = true;
  expiryResult.hidden = true;
  expiryFormStatus.textContent = "Checking the selected data and calculating the estimate...";
  try {
    const result = await requestJson("/api/expiry/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(proposal),
    });
    renderExpiryRisk(result, proposal);
    expiryFormStatus.textContent = "Assessment complete. Review the evidence before making a decision.";
  } catch (error) {
    expiryFormStatus.textContent = `Assessment failed: ${error.message}`;
  } finally {
    expirySubmit.disabled = false;
  }
});

loadEmails();
loadExpiryRiskOptions();

// ---- Work queue ----
const queueStatus = document.getElementById("queue-status");
const queueLimit = document.getElementById("queue-limit");
const queueRefresh = document.getElementById("queue-refresh");
const queueMessage = document.getElementById("queue-status-message");
const BAND_LABELS = {
  P1: "Immediate",
  P2: "Evidence review",
  P3: "Duplicate review",
  P4: "Standard",
  P5: "Monitoring",
};
const REASON_LABELS = {
  missing_invoice: "No matching invoice",
  policy_breach: "Policy or quantity breach",
  tat_over_30: "Credit took over 30 days",
  pending_over_30: "Pending over 30 days",
  duplicate: "Duplicate or repeated",
  high_value: "High value",
};
let queueLoaded = false;

function queueFindings(claim) {
  const items = claim.priority.reasons.map((reason) => REASON_LABELS[reason] || reason);
  if (claim.window.status === "breach") items.push(`Outside ${claim.claim_type.toLowerCase()} window`);
  if (claim.supplied_quantity.status === "exceeds_supplied") items.push("Claims more than invoiced plus free");
  if (claim.pts.status === "exception") items.push(`Price differs by INR ${claim.pts.difference_inr}`);
  if (claim.exact_duplicate_row) items.push("Exact duplicate row");
  return [...new Set(items)];
}

function queueSettlement(tat) {
  if (tat.status === "over_target") return `${tat.days} days (over 30)`;
  if (tat.status === "within_target") return `${tat.days} days`;
  if (tat.status === "pending_over_target") return `Pending ${tat.days} days (over 30)`;
  if (tat.status === "pending") return `Pending ${tat.days} days`;
  if (tat.status === "closed") return "Closed";
  return "Unverified";
}

function queueCell(text, className) {
  const cell = document.createElement("td");
  if (className) cell.className = className;
  cell.textContent = text;
  return cell;
}

function renderQueue(data) {
  const money = (value) => value.toLocaleString("en-IN", { maximumFractionDigits: 0 });
  document.getElementById("queue-totals").textContent =
    `${data.total_claims.toLocaleString("en-IN")} claims, INR ${money(data.total_value_inr)} in total. Showing the top ${data.claims.length}.`;
  document.getElementById("queue-bands").replaceChildren(
    ...Object.entries(data.by_band).map(([band, count]) => {
      const item = document.createElement("li");
      item.className = `priority-badge ${band.toLowerCase()}`;
      item.textContent = `${band} ${BAND_LABELS[band]}: ${count.toLocaleString("en-IN")}`;
      return item;
    })
  );

  document.getElementById("queue-rows").replaceChildren(
    ...data.claims.map((claim) => {
      const row = document.createElement("tr");

      const priority = document.createElement("td");
      const badge = document.createElement("span");
      badge.className = `priority-badge ${claim.priority.band.toLowerCase()}`;
      badge.textContent = claim.priority.band;
      badge.title = `${BAND_LABELS[claim.priority.band]} (score ${claim.priority.score})`;
      priority.append(badge, document.createTextNode(` ${claim.priority.score}`));

      const claimCell = document.createElement("td");
      const claimNo = document.createElement("strong");
      claimNo.textContent = claim.claim_no;
      const claimMeta = document.createElement("div");
      claimMeta.className = "queue-meta";
      claimMeta.textContent = `${claim.claim_type} · ${claim.claim_date} · ${claim.status}`;
      claimCell.append(claimNo, claimMeta);

      const keys = document.createElement("td");
      keys.textContent = `${claim.stockist_code} / ${claim.sku_code} / ${claim.batch_no}`;
      const invoice = document.createElement("div");
      invoice.className = "queue-meta";
      invoice.textContent = claim.invoice_ref ? `Invoice ${claim.invoice_ref}` : "No invoice reference";
      keys.append(invoice);

      const findings = document.createElement("td");
      const list = document.createElement("ul");
      list.className = "queue-findings";
      const items = queueFindings(claim);
      for (const text of items.length ? items : ["No findings"]) {
        const li = document.createElement("li");
        li.textContent = text;
        list.append(li);
      }
      findings.append(list);

      row.append(
        priority,
        claimCell,
        queueCell(money(claim.claim_value_inr), "num"),
        keys,
        queueCell(queueSettlement(claim.tat)),
        findings
      );
      return row;
    })
  );
  document.getElementById("queue-summary").hidden = false;
  document.getElementById("queue-table-wrap").hidden = false;
}

async function loadQueue() {
  queueRefresh.disabled = true;
  queueMessage.textContent = "Loading the queue...";
  try {
    const params = new URLSearchParams({ status: queueStatus.value, limit: queueLimit.value });
    const data = await requestJson(`/api/claims/workqueue?${params}`);
    renderQueue(data);
    queueLoaded = true;
    queueMessage.textContent = data.total_claims
      ? `Queue as of ${data.as_of}.`
      : "No claims match this filter.";
  } catch (error) {
    queueMessage.textContent = `Could not load the queue: ${error.message}`;
  } finally {
    queueRefresh.disabled = false;
  }
}

queueRefresh.addEventListener("click", loadQueue);
queueStatus.addEventListener("change", loadQueue);
queueLimit.addEventListener("change", loadQueue);
document.getElementById("queue-tab").addEventListener("click", () => {
  if (!queueLoaded) loadQueue();
});
