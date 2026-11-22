#!/usr/bin/env python3
"""Analyze scheme free-goods value and quarter-end primary-sales exposure."""

import argparse
import csv
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


DATE_FORMATS = (
    "%d-%m-%Y",
    "%Y-%m-%d",
    "%d-%b-%Y",
    "%d-%B-%Y",
)


def parse_date(value):
    value = (value or "").strip()
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(value, date_format)
        except ValueError:
            pass
    return None


def decimal_value(value):
    try:
        return Decimal(str(value or "").strip().replace(",", "") or "0")
    except InvalidOperation:
        return Decimal("0")


def read_csv(path):
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def default_data_dir():
    starter = Path(__file__).resolve().parent.parent
    candidate = starter / "data"
    if (candidate / "primary_sales.csv").is_file():
        return candidate
    raise FileNotFoundError(
        "Could not find data/primary_sales.csv. Pass --data /path/to/data."
    )


def percentage(numerator, denominator):
    if denominator == 0:
        return Decimal("0")
    return numerator * Decimal("100") / denominator


def analyze_scheme_free_goods(data_dir):
    sales = read_csv(data_dir / "primary_sales.csv")

    gross_primary_value = Decimal("0")
    free_goods_value = Decimal("0")
    scheme_line_count = 0
    scheme_line_free_value = Decimal("0")

    q1_gross_primary_value = Decimal("0")
    q1_free_goods_value = Decimal("0")
    q1_scheme_line_count = 0

    q1_start = datetime(2026, 4, 1)
    q1_end = datetime(2026, 6, 30)

    q1_rows = []
    scheme_rows = []

    for row in sales:
        invoiced_qty = decimal_value(row.get("invoiced_qty"))
        free_qty = decimal_value(row.get("free_qty"))
        pts = decimal_value(row.get("pts_inr"))

        gross_value = invoiced_qty * pts
        free_value = free_qty * pts
        gross_primary_value += gross_value
        free_goods_value += free_value

        scheme_code = (row.get("scheme_code") or "").strip()
        has_scheme = scheme_code not in ("", "-", "NA")
        if has_scheme:
            scheme_line_count += 1
            scheme_line_free_value += free_value
            scheme_rows.append({
                **row,
                "gross_line_value_inr": str(gross_value),
                "free_goods_value_inr": str(free_value),
            })

        invoice_date = parse_date(row.get("invoice_date"))
        if invoice_date is not None and q1_start <= invoice_date <= q1_end:
            q1_gross_primary_value += gross_value
            q1_free_goods_value += free_value
            if has_scheme:
                q1_scheme_line_count += 1
            q1_rows.append({
                **row,
                "gross_line_value_inr": str(gross_value),
                "free_goods_value_inr": str(free_value),
            })

    return {
        "sales_row_count": len(sales),
        "gross_primary_value_inr": float(gross_primary_value),
        "free_goods_value_inr": float(free_goods_value),
        "free_goods_pct_of_primary": round(
            float(percentage(free_goods_value, gross_primary_value)), 3
        ),
        "scheme_line_count": scheme_line_count,
        "scheme_line_free_goods_value_inr": float(scheme_line_free_value),
        "q1_fy27_gross_primary_value_inr": float(q1_gross_primary_value),
        "q1_fy27_free_goods_value_inr": float(q1_free_goods_value),
        "q1_fy27_free_goods_pct_of_primary": round(
            float(percentage(
                q1_free_goods_value,
                q1_gross_primary_value,
            )),
            3,
        ),
        "q1_fy27_scheme_line_count": q1_scheme_line_count,
        "policy_free_goods_cap_pct": 3.0,
        "free_goods_exceeds_policy_cap": (
            percentage(free_goods_value, gross_primary_value) > Decimal("3")
        ),
        "q1_fy27_free_goods_exceeds_policy_cap": (
            percentage(q1_free_goods_value, q1_gross_primary_value)
            > Decimal("3")
        ),
    }, scheme_rows, q1_rows


def export_rows(rows, output_path):
    if not rows:
        output_path.write_text("", encoding="utf-8")
        return

    fieldnames = list(rows[0].keys())
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze scheme free goods from primary_sales.csv."
    )
    parser.add_argument(
        "--data",
        type=Path,
        help="Data directory containing primary_sales.csv",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print only JSON output",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export scheme rows and Q1 FY27 rows",
    )
    args = parser.parse_args()

    data_dir = args.data.resolve() if args.data else default_data_dir()
    result, scheme_rows, q1_rows = analyze_scheme_free_goods(data_dir)
    result["data_directory"] = str(data_dir)

    if args.export:
        analysis_dir = Path(__file__).resolve().parent
        scheme_path = analysis_dir / "scheme_sales_rows.csv"
        q1_path = analysis_dir / "q1_fy27_sales_rows.csv"
        export_rows(scheme_rows, scheme_path)
        export_rows(q1_rows, q1_path)
        result["scheme_sales_export"] = str(scheme_path)
        result["q1_fy27_sales_export"] = str(q1_path)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print("Project Sankalp scheme free-goods analysis")
    print(f"Data: {data_dir}")
    print(
        "Primary-sales PTS gross value: "
        f"INR {result['gross_primary_value_inr']:,.2f}"
    )
    print(
        "Free-goods PTS value: "
        f"INR {result['free_goods_value_inr']:,.2f}"
    )
    print(
        "Free goods: "
        f"{result['free_goods_pct_of_primary']:.3f}% "
        "of primary-sales PTS value"
    )
    print(
        "Scheme sales lines: "
        f"{result['scheme_line_count']:,}"
    )
    print(
        "Scheme sales-line free goods: "
        f"INR {result['scheme_line_free_goods_value_inr']:,.2f}"
    )
    print(
        "Q1 FY27 gross primary-sales PTS value: "
        f"INR {result['q1_fy27_gross_primary_value_inr']:,.2f}"
    )
    print(
        "Q1 FY27 free goods: "
        f"INR {result['q1_fy27_free_goods_value_inr']:,.2f}"
    )
    print(
        "Q1 FY27 free goods: "
        f"{result['q1_fy27_free_goods_pct_of_primary']:.3f}% "
        "of primary-sales PTS value"
    )
    print(
        "Policy cap: "
        f"{result['policy_free_goods_cap_pct']:.1f}%"
    )
    print(
        "Exceeds policy cap across extract: "
        f"{'Yes' if result['free_goods_exceeds_policy_cap'] else 'No'}"
    )
    print(
        "Exceeds policy cap in Q1 FY27: "
        f"{'Yes' if result['q1_fy27_free_goods_exceeds_policy_cap'] else 'No'}"
    )

    if args.export:
        print(f"Scheme sales export: {scheme_path}")
        print(f"Q1 FY27 sales export: {q1_path}")


if __name__ == "__main__":
    main()
