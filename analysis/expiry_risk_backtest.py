#!/usr/bin/env python3
"""Backtest the expiry-risk score: would it have flagged the sales that later became expiry claims?

Run from the project folder:
    python analysis/expiry_risk_backtest.py

Every sale line whose batch is in the batch master is scored as it stood on its invoice date,
using only information available then. A line is a "claim line" when a near-expiry or expired
claim later cites the same invoice, stockist, product and batch.
The weights were chosen on this same data, so this is an in-sample check, not a forecast.
"""
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.graphs import predict_expiry_risk  # noqa: E402
from agent.rules import parse_date, parse_quantity  # noqa: E402
from agent.tools import data  # noqa: E402

NO_SCHEME = ("", "NA", "-")


def number(value: str) -> float:
    return float(parse_quantity((value or "").replace(",", "")) or 0)


def main() -> None:
    batches = data.batches()
    claims = {tuple(r.items()): r for r in data.expiry_claims()}.values()
    claim_value: dict[tuple, float] = defaultdict(float)
    for r in claims:
        if r["claim_type"].strip() in ("Near expiry", "Expired"):
            key = (data.code(r["original_invoice_ref"]), data.code(r["stockist_code"]),
                   data.sku_key(r["sku_code"]), data.code(r["batch_no"]))
            claim_value[key] += number(r["claim_value_inr"])

    sales = [s for s in {tuple(r.items()): r for r in data.sales()}.values() if data.code(s["batch_no"]) in batches]
    by_level = defaultdict(lambda: {"lines": 0, "claim_lines": 0, "claim_value": 0.0})
    for s in sales:
        result = predict_expiry_risk({
            "proposal_date": parse_date(s["invoice_date"]).isoformat(),
            "stockist_code": s["stockist_code"], "cnf_code": s["cnf_code"],
            "sku_code": s["sku_code"], "batch_no": s["batch_no"],
            "proposed_quantity": number(s["invoiced_qty"]) or 1,
            "on_scheme": s["scheme_code"].strip() not in NO_SCHEME,
        })
        key = (data.code(s["invoice_no"]), data.code(s["stockist_code"]),
               data.sku_key(s["sku_code"]), data.code(s["batch_no"]))
        row = by_level[result["risk_level"]]
        row["lines"] += 1
        if key in claim_value:
            row["claim_lines"] += 1
            row["claim_value"] += claim_value[key]

    total_lines = sum(r["lines"] for r in by_level.values())
    total_value = sum(r["claim_value"] for r in by_level.values())
    print(f"Sale lines scored: {total_lines:,}")
    print(f"Expiry claim value traced to a sale: INR {total_value:,.0f}")
    print(f"{'Risk level':<12}{'Sale lines':>12}{'Share':>8}{'Became a claim':>16}{'Rate':>8}{'Claim value INR':>18}{'Share':>8}")
    for level in ("high", "medium", "low", "unverified"):
        r = by_level.get(level)
        if not r:
            continue
        print(f"{level:<12}{r['lines']:>12,}{r['lines'] / total_lines:>8.1%}{r['claim_lines']:>16,}"
              f"{r['claim_lines'] / r['lines']:>8.1%}{r['claim_value']:>18,.0f}{r['claim_value'] / total_value:>8.1%}")


if __name__ == "__main__":
    main()
