#!/usr/bin/env python3
"""Auditable claim-control analysis for the Project Sankalp data pack.

Run from the starter folder:
    python analysis/claim_control_analysis.py

Use --data /path/to/data to override the default data location.
"""

import argparse
import csv
import json
from collections import Counter
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


def clean_code(value):
    return (value or "").strip().upper()


def clean_sku(value):
    return clean_code(value).replace("-", "")


def read_csv(path):
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def default_data_dir():
    starter = Path(__file__).resolve().parent.parent
    candidates = (
        starter / "data",
        starter.parent / "data-pack" / "data",
    )
    for candidate in candidates:
        required = (
            "sku_master.csv",
            "batch_master.csv",
            "primary_sales.csv",
            "expiry_claims.csv",
        )
        if all((candidate / name).is_file() for name in required):
            return candidate
    raise FileNotFoundError(
        "Could not find the data pack. Pass --data /path/to/data."
    )


def exact_duplicate_count(rows):
    return sum(
        count - 1
        for count in Counter(tuple(sorted(row.items())) for row in rows).values()
        if count > 1
    )


def claim_control_analysis(data_dir):
    sku_rows = read_csv(data_dir / "sku_master.csv")
    batch_rows = read_csv(data_dir / "batch_master.csv")
    sales_rows = read_csv(data_dir / "primary_sales.csv")
    claim_rows = read_csv(data_dir / "expiry_claims.csv")

    sku_by_code = {
        clean_sku(row["sku_code"]): {
            **row,
            "pts": decimal_value(row["pts_inr"]),
        }
        for row in sku_rows
    }
    batch_expiry_by_code = {
        clean_code(row["batch_no"]): parse_date(row["expiry_date"])
        for row in batch_rows
    }

    invoice_totals = {}
    for row in sales_rows:
        key = (
            (row.get("invoice_no") or "").strip(),
            clean_code(row.get("stockist_code")),
            clean_sku(row.get("sku_code")),
            clean_code(row.get("batch_no")),
        )
        if key not in invoice_totals:
            invoice_totals[key] = {
                "invoiced_qty": Decimal("0"),
                "free_qty": Decimal("0"),
            }
        invoice_totals[key]["invoiced_qty"] += decimal_value(row.get("invoiced_qty"))
        invoice_totals[key]["free_qty"] += decimal_value(row.get("free_qty"))

    missing_invoice_ref = 0
    invoice_match_count = 0
    quantity_exceeds_count = 0
    outside_near_expiry_count = 0
    outside_expired_count = 0
    pts_difference_over_one_count = 0
    pts_difference_over_one_value = Decimal("0")
    claim_value_total = Decimal("0")

    repeated_claim_keys = Counter()
    exact_claim_rows = [dict(row) for row in claim_rows]

    for row in claim_rows:
        stockist = clean_code(row.get("stockist_code"))
        sku = clean_sku(row.get("sku_code"))
        batch = clean_code(row.get("batch_no"))
        claim_date = parse_date(row.get("claim_date"))
        claimed_expiry = parse_date(row.get("expiry_date_as_claimed"))
        batch_expiry = batch_expiry_by_code.get(batch)
        expiry = batch_expiry or claimed_expiry

        claim_qty = decimal_value(row.get("qty_claimed"))
        claim_value = decimal_value(row.get("claim_value_inr"))
        claim_value_total += claim_value

        repeated_claim_keys[(stockist, sku, batch)] += 1

        invoice_ref = (row.get("original_invoice_ref") or "").strip()
        if not invoice_ref:
            missing_invoice_ref += 1

        invoice_key = (invoice_ref, stockist, sku, batch)
        invoice = invoice_totals.get(invoice_key)
        if invoice is not None:
            invoice_match_count += 1
            supplied_qty = invoice["invoiced_qty"] + invoice["free_qty"]
            if claim_qty > supplied_qty:
                quantity_exceeds_count += 1

        sku_record = sku_by_code.get(sku)
        if sku_record is not None and row.get("claim_value_inr", "").strip():
            recalculated_value = claim_qty * sku_record["pts"]
            difference = abs(claim_value - recalculated_value)
            if difference > Decimal("1"):
                pts_difference_over_one_count += 1
                pts_difference_over_one_value += difference

        claim_type = (row.get("claim_type") or "").strip()
        if claim_date is not None and expiry is not None:
            if claim_type == "Near expiry":
                valid = (
                    expiry - claim_date
                ).days >= 0 and (
                    expiry - claim_date
                ).days <= 90
                if not valid:
                    outside_near_expiry_count += 1
            elif claim_type == "Expired":
                valid = (
                    claim_date >= expiry
                    and (claim_date - expiry).days <= 90
                )
                if not valid:
                    outside_expired_count += 1

    repeated_groups = sum(1 for count in repeated_claim_keys.values() if count > 1)
    repeated_claim_rows = sum(
        count for count in repeated_claim_keys.values() if count > 1
    )

    exact_duplicates = exact_duplicate_count(exact_claim_rows)

    return {
        "claim_row_count": len(claim_rows),
        "claim_value_inr": float(claim_value_total),
        "missing_invoice_reference_count": missing_invoice_ref,
        "missing_invoice_reference_pct": round(
            missing_invoice_ref * 100 / len(claim_rows), 2
        ) if claim_rows else 0,
        "invoice_batch_stockist_sku_match_count": invoice_match_count,
        "quantity_exceeds_invoiced_plus_free_count": quantity_exceeds_count,
        "outside_near_expiry_window_count": outside_near_expiry_count,
        "outside_expired_window_count": outside_expired_count,
        "repeated_stockist_sku_batch_group_count": repeated_groups,
        "repeated_stockist_sku_batch_row_count": repeated_claim_rows,
        "exact_duplicate_register_row_count": exact_duplicates,
        "pts_value_difference_over_inr_1_count": pts_difference_over_one_count,
        "pts_value_difference_over_inr_1_total": float(
            pts_difference_over_one_value
        ),
    }


def export_duplicate_claim_rows(data_dir, analysis_dir):
    claim_rows = read_csv(data_dir / "expiry_claims.csv")
    repeated_counts = Counter(
        (
            clean_code(row.get("stockist_code")),
            clean_sku(row.get("sku_code")),
            clean_code(row.get("batch_no")),
        )
        for row in claim_rows
    )
    repeated_keys = {
        key for key, count in repeated_counts.items() if count > 1
    }

    repeated_rows = []
    for row in claim_rows:
        key = (
            clean_code(row.get("stockist_code")),
            clean_sku(row.get("sku_code")),
            clean_code(row.get("batch_no")),
        )
        if key in repeated_keys:
            repeated_rows.append(
                {
                    **row,
                    "duplicate_group_row_count": str(repeated_counts[key]),
                }
            )

    seen_exact_rows = set()
    exact_extra_rows = []
    for row in claim_rows:
        exact_key = tuple(sorted(row.items()))
        if exact_key in seen_exact_rows:
            exact_extra_rows.append({**row, "duplicate_type": "exact_extra_row"})
        else:
            seen_exact_rows.add(exact_key)

    analysis_dir.mkdir(parents=True, exist_ok=True)
    repeated_path = analysis_dir / "duplicate_claim_rows.csv"
    exact_path = analysis_dir / "exact_duplicate_claim_rows.csv"

    if repeated_rows:
        fieldnames = list(repeated_rows[0].keys())
        with repeated_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(repeated_rows)
    else:
        repeated_path.write_text("", encoding="utf-8")

    if exact_extra_rows:
        fieldnames = list(exact_extra_rows[0].keys())
        with exact_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(exact_extra_rows)
    else:
        exact_path.write_text("", encoding="utf-8")

    return repeated_path, exact_path, repeated_rows, exact_extra_rows


def main():
    parser = argparse.ArgumentParser(
        description="Analyze claim-control findings from the Pfizer data pack."
    )
    parser.add_argument(
        "--data",
        type=Path,
        help="Data directory containing the project CSV files",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print only JSON output",
    )
    parser.add_argument(
        "--export-duplicates",
        action="store_true",
        help="Export duplicate claim rows to the analysis folder",
    )
    args = parser.parse_args()

    data_dir = args.data.resolve() if args.data else default_data_dir()
    result = claim_control_analysis(data_dir)
    result["data_directory"] = str(data_dir)

    if args.export_duplicates:
        repeated_path, exact_path, repeated_rows, exact_extra_rows = (
            export_duplicate_claim_rows(
                data_dir,
                Path(__file__).resolve().parent,
            )
        )
        if args.json:
            print(json.dumps({
                **result,
                "repeated_claim_rows_exported": len(repeated_rows),
                "exact_duplicate_extra_rows_exported": len(exact_extra_rows),
                "repeated_claim_rows_file": str(repeated_path),
                "exact_duplicate_claim_rows_file": str(exact_path),
            }, indent=2))
            return
        print(
            f"Repeated claim rows exported: {len(repeated_rows):,} "
            f"-> {repeated_path}"
        )
        print(
            f"Exact duplicate extra rows exported: {len(exact_extra_rows):,} "
            f"-> {exact_path}"
        )
        print()

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print("Project Sankalp claim-control analysis")
    print(f"Data: {data_dir}")
    print(f"Claim rows: {result['claim_row_count']:,}")
    print(f"Claim value: INR {result['claim_value_inr']:,.2f}")
    print(
        "Claims without invoice reference: "
        f"{result['missing_invoice_reference_count']:,} "
        f"({result['missing_invoice_reference_pct']:.2f}%)"
    )
    print(
        "Invoice/batch/stockist/SKU matches: "
        f"{result['invoice_batch_stockist_sku_match_count']:,}"
    )
    print(
        "Claims exceeding invoiced plus free quantity: "
        f"{result['quantity_exceeds_invoiced_plus_free_count']:,}"
    )
    print(
        "Outside policy windows: "
        f"Near expiry {result['outside_near_expiry_window_count']:,}, "
        f"Expired {result['outside_expired_window_count']:,}"
    )
    print(
        "Repeated stockist/SKU/batch groups: "
        f"{result['repeated_stockist_sku_batch_group_count']:,} "
        f"({result['repeated_stockist_sku_batch_row_count']:,} rows)"
    )
    print(
        "Exact duplicate register rows: "
        f"{result['exact_duplicate_register_row_count']:,}"
    )
    


if __name__ == "__main__":
    main()
