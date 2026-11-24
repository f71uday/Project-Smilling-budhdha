"""Expiry-risk graph for a proposed stock allocation. Deterministic: tools gather, rules score.

validate -> entities -> snapshot (optional) -> history -> score
A missing C&F stock snapshot no longer stops the assessment: shelf life, scheme and order-size
signals still score, and the stock-cover signals are reported as unavailable.
"""
from decimal import Decimal

from langgraph.graph import END, START, StateGraph

from agent.graphs.stock_evidence import (
    StockState, fmt, load_snapshot, resolve_entities, route_unverified, to_decimal,
    unverified_result, validate_proposal,
)
from agent.rules import expiry_risk_band, expiry_risk_score, parse_date, usual_order_quantity
from agent.tools import ALL_TOOLS
from agent.tools.data import code


def load_snapshot_optional(state: StockState) -> dict:
    """Use the snapshot when it exists; otherwise record the gap and carry on."""
    update = load_snapshot(state)
    gap = update.pop("unverified", None)
    if gap is None:
        return update
    ctx = {**state["ctx"], "snapshot_gap": gap, "inventory": None, "outward": None, "latest_rows": []}
    return {**update, "ctx": ctx}


def gather_history(state: StockState) -> dict:
    """Earlier expiry claims, the stockist's usual order size, and the FEFO batch at the C&F."""
    ctx, evidence = state["ctx"], dict(state["evidence"])
    history = ALL_TOOLS["lookup_claim_history"].invoke(
        {"stockist_code": ctx["stockist"], "sku_code": ctx["sku"], "batch_no": ctx["batch_no"]}
    )
    prior = [
        c for c in history["claims"]
        if "expir" in c["claim_type"].casefold()
        and (parse_date(c["claim_date"]) or ctx["date"]) < ctx["date"]   # only claims made before the proposal
    ]
    evidence["prior_expiry_claims"] = [
        {k: c[k] for k in ("claim_no", "claim_date", "claim_type")} for c in prior
    ]

    purchases = ALL_TOOLS["lookup_purchase_history"].invoke(
        {"stockist_code": ctx["stockist"], "sku_code": ctx["sku"]}
    )["purchases"]
    earlier = [
        to_decimal(p["invoiced_qty"]) for p in purchases
        if (parse_date(p["invoice_date"]) or ctx["date"]) < ctx["date"]
    ]
    usual = usual_order_quantity([q for q in earlier if q is not None and q > 0])
    evidence["usual_order"] = {"prior_orders": len(earlier), "median_quantity_packs": fmt(usual) if usual else None}

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
        "ctx": {
            **ctx, "prior_claim": bool(prior), "usual": usual, "fefo": fefo,
            "fefo_not_used": bool(fefo and fefo[1] != ctx["batch_no"]),
        },
    }


def score(state: StockState) -> dict:
    ctx = state["ctx"]
    inventory, outward, qty, days = ctx["inventory"], ctx["outward"], ctx["qty"], ctx["days_to_expiry"]
    has_stock = inventory is not None and outward is not None
    projected = inventory + qty if has_stock else None
    cover = projected * Decimal(30) / outward if has_stock else None
    points, reasons = expiry_risk_score(
        days, cover, qty, outward if has_stock else None,
        prior_claim=ctx["prior_claim"], fefo_not_used=ctx["fefo_not_used"],
        on_scheme=ctx["on_scheme"], usual_order_quantity=ctx["usual"],
    )
    if not has_stock:
        reasons.append("STOCK_COVER_UNAVAILABLE")
    elif ctx["fefo"] is None:
        reasons.append("FEFO_EVIDENCE_UNAVAILABLE")
    level, recommendation = expiry_risk_band(points)

    metrics = {"days_to_expiry": days, "proposed_quantity_packs": fmt(qty)}
    if ctx["usual"]:
        metrics["usual_order_packs"] = fmt(ctx["usual"])
    if has_stock:
        sellable = outward * Decimal(max(days, 0)) / Decimal(30)
        metrics.update({
            "current_inventory_packs": fmt(inventory),
            "projected_inventory_packs": fmt(projected),
            "average_monthly_outward_packs": fmt(outward),
            "projected_days_of_cover": round(float(cover), 1),
            "estimated_at_risk_packs": fmt(max(Decimal(0), projected - sellable)),
        })
    return {"result": {
        "risk_level": level,
        "risk_score": points,
        "recommendation": recommendation,
        "reasons": reasons,
        "confidence": "proxy" if has_stock else "partial",
        "data_basis": (
            "Batch expiry, scheme flag and the stockist's order history; "
            + ("C&F stock snapshot with its average monthly outward as the demand proxy."
               if has_stock else f"no usable C&F stock snapshot ({ctx['snapshot_gap']}), so stock cover was not scored.")
        ),
        "metrics": metrics,
        "evidence": state["evidence"],
    }}


def stop(state: StockState) -> dict:
    return {"result": unverified_result(state["unverified"], state["evidence"])}


def build_graph():
    g = StateGraph(StockState)
    for name, fn in [
        ("validate", validate_proposal), ("entities", resolve_entities), ("snapshot", load_snapshot_optional),
        ("history", gather_history), ("score", score), ("stop", stop),
    ]:
        g.add_node(name, fn)
    g.add_edge(START, "validate")
    for src, nxt in [("validate", "entities"), ("entities", "snapshot")]:
        g.add_conditional_edges(src, route_unverified, {"continue": nxt, "stop": "stop"})
    g.add_edge("snapshot", "history")
    g.add_edge("history", "score")
    g.add_edge("score", END)
    g.add_edge("stop", END)
    return g.compile()


expiry_risk_graph = build_graph()


def predict_expiry_risk(proposal: dict) -> dict:
    return expiry_risk_graph.invoke({"proposal": proposal})["result"]
