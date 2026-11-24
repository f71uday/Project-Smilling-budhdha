"""Shared LangGraph nodes that gather batch, stockist and C&F stock evidence through tools.

A node that cannot continue sets `unverified` to a reason code; graphs route that to END.
"""
from decimal import Decimal, InvalidOperation
from typing import Any, TypedDict

from typing_extensions import NotRequired

from agent.rules import parse_date
from agent.tools import ALL_TOOLS
from agent.tools.data import cnf_key, code


class StockState(TypedDict):
    proposal: dict[str, Any]
    evidence: NotRequired[dict[str, Any]]
    unverified: NotRequired[str]
    ctx: NotRequired[dict[str, Any]]
    result: NotRequired[dict[str, Any]]


def to_decimal(value: Any) -> Decimal | None:
    try:
        number = Decimal(str(value).replace(",", "").strip())
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def fmt(value: Decimal) -> str:
    return format(value.normalize(), "f")


def unverified_result(reason: str, evidence: dict) -> dict:
    return {
        "risk_level": "unverified",
        "risk_score": None,
        "recommendation": "human_review",
        "reasons": [reason],
        "confidence": "unverified",
        "data_basis": "Insufficient matched source evidence for a reliable estimate.",
        "metrics": {},
        "evidence": evidence,
    }


def route_unverified(state: StockState) -> str:
    return "stop" if state.get("unverified") else "continue"


def validate_proposal(state: StockState) -> dict:
    p = state["proposal"]
    date = parse_date(p.get("proposal_date"))
    qty = to_decimal(p.get("proposed_quantity"))
    ctx = {
        "date": date,
        "qty": qty,
        "stockist": code(p.get("stockist_code")),
        "cnf": cnf_key(p.get("cnf_code")),
        "sku": code(p.get("sku_code")),
        "batch_no": code(p.get("batch_no")),
        "on_scheme": bool(p.get("on_scheme")),
    }
    evidence = {"stockist": None, "batch": None, "snapshot": None, "prior_expiry_claims": [], "fefo": None}
    if date is None:
        return {"ctx": ctx, "evidence": evidence, "unverified": "INVALID_PROPOSAL_DATE"}
    if qty is None or qty <= 0:
        return {"ctx": ctx, "evidence": evidence, "unverified": "INVALID_PROPOSED_QUANTITY"}
    return {"ctx": ctx, "evidence": evidence}


def resolve_entities(state: StockState) -> dict:
    ctx, evidence = state["ctx"], dict(state["evidence"])
    batch = ALL_TOOLS["lookup_batch"].invoke({"batch_no": ctx["batch_no"]})
    evidence["batch"] = batch
    if not batch["found"]:
        return {"evidence": evidence, "unverified": "BATCH_NOT_FOUND"}
    if code(batch.get("sku_code")) != ctx["sku"]:
        return {"evidence": evidence, "unverified": "BATCH_SKU_MISMATCH"}

    stockist = ALL_TOOLS["lookup_stockist"].invoke({"stockist_code": ctx["stockist"]})
    if not stockist["found"]:
        return {"evidence": evidence, "unverified": "STOCKIST_NOT_FOUND"}
    evidence["stockist"] = {k: stockist[k] for k in ("stockist_code", "stockist_name", "cnf_code")}
    if cnf_key(stockist["cnf_code"]) != ctx["cnf"]:
        return {"evidence": evidence, "unverified": "STOCKIST_CNF_MISMATCH"}

    expiry = parse_date(batch.get("expiry_date"))
    if expiry is None:
        return {"evidence": evidence, "unverified": "BATCH_EXPIRY_DATE_UNAVAILABLE"}
    return {"evidence": evidence, "ctx": {**ctx, "expiry": expiry, "days_to_expiry": (expiry - ctx["date"]).days}}


def load_snapshot(state: StockState) -> dict:
    """Pick the latest snapshot on or before the proposal date and the one row for this batch."""
    ctx, evidence = state["ctx"], dict(state["evidence"])
    rows = ALL_TOOLS["lookup_stock_snapshot"].invoke({"cnf_code": ctx["cnf"], "sku_code": ctx["sku"]})["rows"]
    dated = [(r, parse_date(r.get("snapshot_date"))) for r in rows]
    eligible = [(r, d) for r, d in dated if d is not None and d <= ctx["date"]]
    if not eligible:
        return {"unverified": "SNAPSHOT_NOT_FOUND"}
    latest = max(d for _, d in eligible)
    latest_rows = [r for r, d in eligible if d == latest]
    mine = {tuple(sorted(r.items())): r for r in latest_rows if code(r.get("batch_no")) == ctx["batch_no"]}
    if not mine:
        return {"unverified": "BATCH_SNAPSHOT_NOT_FOUND"}
    if len(mine) > 1:
        return {"unverified": "AMBIGUOUS_BATCH_SNAPSHOT"}
    snapshot = next(iter(mine.values()))
    evidence["snapshot"] = snapshot
    inventory = to_decimal(snapshot.get("qty_on_hand_packs"))
    outward = to_decimal(snapshot.get("avg_monthly_outward_packs"))
    if inventory is None or inventory < 0:
        return {"evidence": evidence, "unverified": "INVALID_INVENTORY_QUANTITY"}
    if outward is None or outward <= 0:
        return {"evidence": evidence, "unverified": "SELL_THROUGH_UNAVAILABLE"}
    return {
        "evidence": evidence,
        "ctx": {**ctx, "inventory": inventory, "outward": outward, "latest_rows": latest_rows},
    }
