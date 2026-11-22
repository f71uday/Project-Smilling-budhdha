"""Scheme-eligibility graph: can this stockist be offered a scheme on near-expiry C&F stock?"""
from langgraph.graph import END, START, StateGraph

from agent.graphs.stock_evidence import (
    StockState, load_snapshot, resolve_entities, route_unverified, to_decimal, validate_proposal,
)
from agent.rules import evaluate_scheme_eligibility
from agent.tools import ALL_TOOLS


def decide(state: StockState) -> dict:
    ctx = state["ctx"]
    sku = ALL_TOOLS["lookup_sku_price"].invoke({"sku_code": ctx["sku"]})
    pts = to_decimal(sku.get("pts_inr")) if sku["found"] else None
    if pts is None:
        return {"unverified": "SKU_PRICE_UNAVAILABLE"}
    verdict = evaluate_scheme_eligibility(ctx["days_to_expiry"], ctx["inventory"], ctx["outward"], pts)
    return {"result": {**verdict, "pts_inr": sku["pts_inr"], "evidence": state["evidence"], "recommendation": (
        "offer_scheme_with_approval" if verdict["status"] == "eligible" else "no_scheme"
    )}}


def stop(state: StockState) -> dict:
    return {"result": {
        "status": "unverified", "recommendation": "human_review",
        "reason": state["unverified"], "evidence": state["evidence"],
    }}


def build_graph():
    g = StateGraph(StockState)
    for name, fn in [
        ("validate", validate_proposal), ("entities", resolve_entities),
        ("snapshot", load_snapshot), ("decide", decide), ("stop", stop),
    ]:
        g.add_node(name, fn)
    g.add_edge(START, "validate")
    for src, nxt in [("validate", "entities"), ("entities", "snapshot"), ("snapshot", "decide")]:
        g.add_conditional_edges(src, route_unverified, {"continue": nxt, "stop": "stop"})
    g.add_conditional_edges("decide", route_unverified, {"continue": END, "stop": "stop"})
    g.add_edge("stop", END)
    return g.compile()


scheme_graph = build_graph()


def check_scheme_eligibility(proposal: dict) -> dict:
    return scheme_graph.invoke({"proposal": proposal})["result"]
