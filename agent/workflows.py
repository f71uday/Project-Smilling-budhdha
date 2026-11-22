"""Deterministic workflows that combine source evidence with review rules."""
from decimal import Decimal, InvalidOperation
from typing import Any

from agent.rules import _parse_date, expiry_risk_band, expiry_risk_score
from agent.tools import (
    batch_record,
    lookup_expiry_claims,
    lookup_stock_snapshots,
    lookup_stockist_record,
)


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        number = Decimal(str(value).replace(",", "").strip())
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _unverified_result(
    reason_codes: list[str],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "risk_level": "unverified",
        "risk_score": None,
        "recommendation": "human_review",
        "reasons": reason_codes,
        "confidence": "unverified",
        "data_basis": "Insufficient matched source evidence for a reliable estimate.",
        "metrics": {},
        "evidence": evidence,
    }


def predict_expiry_risk(proposal: dict[str, Any]) -> dict[str, Any]:
    """Assess a proposed allocation using batch, stock snapshot and claim-history evidence."""
    evidence: dict[str, Any] = {
        "stockist": None,
        "batch": None,
        "snapshot": None,
        "prior_expiry_claims": [],
        "fefo": None,
    }
    proposal_date = _parse_date(proposal.get("proposal_date"))
    if proposal_date is None:
        return _unverified_result(["INVALID_PROPOSAL_DATE"], evidence)

    proposed_quantity = _decimal(proposal.get("proposed_quantity"))
    if proposed_quantity is None or proposed_quantity <= 0:
        return _unverified_result(["INVALID_PROPOSED_QUANTITY"], evidence)

    stockist_code = str(proposal.get("stockist_code", "")).strip().upper()
    cnf_code = str(proposal.get("cnf_code", "")).strip().upper()
    sku_code = str(proposal.get("sku_code", "")).strip().upper()
    batch_no = str(proposal.get("batch_no", "")).strip().upper()

    batch = batch_record(batch_no)
    evidence["batch"] = batch
    if not batch["found"]:
        return _unverified_result(["BATCH_NOT_FOUND"], evidence)
    if batch.get("sku_code", "").strip().upper() != sku_code:
        return _unverified_result(["BATCH_SKU_MISMATCH"], evidence)

    stockist = lookup_stockist_record(stockist_code)
    if stockist is None:
        return _unverified_result(["STOCKIST_NOT_FOUND"], evidence)
    evidence["stockist"] = {
        "stockist_code": stockist.get("stockist_code", ""),
        "stockist_name": stockist.get("stockist_name", ""),
        "cnf_code": stockist.get("cnf_code", ""),
    }
    if stockist.get("cnf_code", "").strip().upper() != cnf_code:
        return _unverified_result(["STOCKIST_CNF_MISMATCH"], evidence)

    snapshots = lookup_stock_snapshots(cnf_code, sku_code)
    dated_snapshots = [
        (row, _parse_date(row.get("snapshot_date")))
        for row in snapshots
    ]
    eligible_snapshots = [
        (row, snapshot_date)
        for row, snapshot_date in dated_snapshots
        if snapshot_date is not None and snapshot_date <= proposal_date
    ]
    if not eligible_snapshots:
        return _unverified_result(["SNAPSHOT_NOT_FOUND"], evidence)

    latest_snapshot_date = max(snapshot_date for _, snapshot_date in eligible_snapshots)
    latest_rows = [
        row for row, snapshot_date in eligible_snapshots
        if snapshot_date == latest_snapshot_date
    ]
    batch_rows = [
        row for row in latest_rows
        if row.get("batch_no", "").strip().upper() == batch_no
    ]
    distinct_batch_rows = {tuple(sorted(row.items())): row for row in batch_rows}
    if not distinct_batch_rows:
        return _unverified_result(["BATCH_SNAPSHOT_NOT_FOUND"], evidence)
    if len(distinct_batch_rows) > 1:
        return _unverified_result(["AMBIGUOUS_BATCH_SNAPSHOT"], evidence)

    snapshot = next(iter(distinct_batch_rows.values()))
    evidence["snapshot"] = snapshot
    inventory = _decimal(snapshot.get("qty_on_hand_packs"))
    average_monthly_outward = _decimal(snapshot.get("avg_monthly_outward_packs"))
    if inventory is None or inventory < 0:
        return _unverified_result(["INVALID_INVENTORY_QUANTITY"], evidence)
    if average_monthly_outward is None or average_monthly_outward <= 0:
        return _unverified_result(["SELL_THROUGH_UNAVAILABLE"], evidence)

    expiry_date = _parse_date(batch.get("expiry_date"))
    if expiry_date is None:
        return _unverified_result(["BATCH_EXPIRY_DATE_UNAVAILABLE"], evidence)
    days_to_expiry = (expiry_date - proposal_date).days

    prior_claim_rows = lookup_expiry_claims(stockist_code, sku_code, batch_no)
    prior_expiry_claims = [
        row for row in prior_claim_rows
        if "expir" in row.get("claim_type", "").casefold()
        or "expired" in row.get("claim_type", "").casefold()
    ]
    evidence["prior_expiry_claims"] = [
        {
            "claim_no": row.get("claim_no", ""),
            "claim_date": row.get("claim_date", ""),
            "claim_type": row.get("claim_type", ""),
        }
        for row in prior_expiry_claims
    ]

    fefo_candidates = []
    for row in latest_rows:
        candidate_quantity = _decimal(row.get("qty_on_hand_packs"))
        candidate_batch_no = row.get("batch_no", "").strip().upper()
        candidate_batch = batch_record(candidate_batch_no)
        candidate_expiry = _parse_date(candidate_batch.get("expiry_date"))
        if (
            candidate_quantity is not None
            and candidate_quantity > 0
            and candidate_batch["found"]
            and candidate_batch.get("sku_code", "").strip().upper() == sku_code
            and candidate_expiry is not None
            and candidate_expiry >= proposal_date
        ):
            fefo_candidates.append(
                (candidate_expiry, candidate_batch_no, candidate_quantity)
            )
    fefo_candidates.sort(key=lambda candidate: (candidate[0], candidate[1]))
    fefo_candidate = fefo_candidates[0] if fefo_candidates else None
    if fefo_candidate is not None:
        evidence["fefo"] = {
            "batch_no": fefo_candidate[1],
            "expiry_date": fefo_candidate[0].isoformat(),
            "qty_on_hand_packs": _format_decimal(fefo_candidate[2]),
        }

    fefo_not_used = fefo_candidate is not None and fefo_candidate[1] != batch_no
    projected_inventory = inventory + proposed_quantity
    projected_days_of_cover = projected_inventory * Decimal(30) / average_monthly_outward
    sell_through_before_expiry = (
        average_monthly_outward * Decimal(max(days_to_expiry, 0)) / Decimal(30)
    )
    at_risk_quantity = max(Decimal(0), projected_inventory - sell_through_before_expiry)

    score, reasons = expiry_risk_score(
        days_to_expiry,
        projected_days_of_cover,
        proposed_quantity,
        average_monthly_outward,
        prior_claim=bool(prior_expiry_claims),
        fefo_not_used=fefo_not_used,
    )
    if fefo_candidate is None:
        reasons.append("FEFO_EVIDENCE_UNAVAILABLE")
    risk_level, recommendation = expiry_risk_band(score)

    return {
        "risk_level": risk_level,
        "risk_score": score,
        "recommendation": recommendation,
        "reasons": reasons,
        "confidence": "proxy",
        "data_basis": "C&F stock snapshot; average monthly outward is a primary-sales proxy.",
        "metrics": {
            "days_to_expiry": days_to_expiry,
            "current_inventory_packs": _format_decimal(inventory),
            "proposed_quantity_packs": _format_decimal(proposed_quantity),
            "projected_inventory_packs": _format_decimal(projected_inventory),
            "average_monthly_outward_packs": _format_decimal(average_monthly_outward),
            "projected_days_of_cover": round(float(projected_days_of_cover), 1),
            "estimated_at_risk_packs": _format_decimal(at_risk_quantity),
        },
        "evidence": evidence,
    }
