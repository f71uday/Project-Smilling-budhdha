"""Expiry-risk graph for a proposed stock allocation. Deterministic: tools gather, rules score."""
from decimal import Decimal

from langgraph.graph import END, START, StateGraph

from agent.graphs.stock_evidence import (
    StockState, fmt, load_snapshot, resolve_entities, route_unverified, to_decimal,
    unverified_result, validate_proposal,
)
from agent.rules import expiry_risk_band, expiry_risk_score, parse_date
from agent.tools import ALL_TOOLS
from agent.tools.data import code


def gather_history(state: StockState) -> dict:
    """Prior expiry claims for this stockist/SKU/batch, and the FEFO batch at the C&F."""
    ctx, evidence = state["ctx"], dict(state["evidence"])
    history = ALL_TOOLS["lookup_claim_history"].invoke(
        {"stockist_code": ctx["stockist"], "sku_code": ctx["sku"], "batch_no": ctx["batch_no"]}
    )
    prior = [c for c in history["claims"] if "expir" in c["claim_type"].casefold()]
    evidence["prior_expiry_claims"] = [
        {k: c[k] for k in ("claim_no", "claim_date", "claim_type")} for c in prior
    ]

    candidates = []
    for row in ctx["latest_rows"]:
        qty = to_decimal(row.get("qty_on_hand_packs"))
        batch_no = code(row.get("batch_no"))
        batch = ALL_TOOLS["lookup_batch"].invoke({"batch_no": batch_no})
        expiry = parse_date(batch.get("expiry_date"))
        if (
            qty and qty > 0 and batch["found"] and code(batch.get("sku_code")) == ctx["sku"]
            and expiry is not None and expiry >= ctx["date"]
        ):
            candidates.append((expiry, batch_no, qty))
    candidates.sort(key=lambda c: (c[0], c[1]))
    fefo = candidates[0] if candidates else None
    if fefo:
        evidence["fefo"] = {"batch_no": fefo[1], "expiry_date": fefo[0].isoformat(), "qty_on_hand_packs": fmt(fefo[2])}
    return {
        "evidence": evidence,
        "ctx": {**ctx, "prior_claim": bool(prior), "fefo": fefo, "fefo_not_used": bool(fefo and fefo[1] != ctx["batch_no"])},
    }


def score(state: StockState) -> dict:
    ctx = state["ctx"]
    inventory, outward, qty, days = ctx["inventory"], ctx["outward"], ctx["qty"], ctx["days_to_expiry"]
    projected = inventory + qty
    cover = projected * Decimal(30) / outward
    sellable = outward * Decimal(max(days, 0)) / Decimal(30)
    points, reasons = expiry_risk_score(
        days, cover, qty, outward, prior_claim=ctx["prior_claim"], fefo_not_used=ctx["fefo_not_used"]
    )
    if ctx["fefo"] is None:
        reasons.append("FEFO_EVIDENCE_UNAVAILABLE")
    level, recommendation = expiry_risk_band(points)
    return {"result": {
        "risk_level": level,
        "risk_score": points,
        "recommendation": recommendation,
        "reasons": reasons,
        "confidence": "proxy",
        "data_basis": "C&F stock snapshot; average monthly outward is a primary-sales proxy.",
        "metrics": {
            "days_to_expiry": days,
            "current_inventory_packs": fmt(inventory),
            "proposed_quantity_packs": fmt(qty),
            "projected_inventory_packs": fmt(projected),
            "average_monthly_outward_packs": fmt(outward),
            "projected_days_of_cover": round(float(cover), 1),
            "estimated_at_risk_packs": fmt(max(Decimal(0), projected - sellable)),
        },
        "evidence": state["evidence"],
    }}


def stop(state: StockState) -> dict:
    return {"result": unverified_result(state["unverified"], state["evidence"])}


def build_graph():
    g = StateGraph(StockState)
    for name, fn in [
        ("validate", validate_proposal), ("entities", resolve_entities), ("snapshot", load_snapshot),
        ("history", gather_history), ("score", score), ("stop", stop),
    ]:
        g.add_node(name, fn)
    g.add_edge(START, "validate")
    for src, nxt in [("validate", "entities"), ("entities", "snapshot"), ("snapshot", "history")]:
        g.add_conditional_edges(src, route_unverified, {"continue": nxt, "stop": "stop"})
    g.add_edge("history", "score")
    g.add_edge("score", END)
    g.add_edge("stop", END)
    return g.compile()


expiry_risk_graph = build_graph()


def predict_expiry_risk(proposal: dict) -> dict:
    return expiry_risk_graph.invoke({"proposal": proposal})["result"]
