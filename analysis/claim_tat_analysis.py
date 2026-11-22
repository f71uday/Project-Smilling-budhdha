#!/usr/bin/env python3
"""Analyze claim-to-credit-note timing and claim settlement status."""

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
    if (candidate / "expiry_claims.csv").is_file():
        return candidate
    raise FileNotFoundError(
        "Could not find data/expiry_claims.csv. Pass --data /path/to/data."
    )


def analyze_claim_tat(data_dir):
    claims = read_csv(data_dir / "expiry_claims.csv")

    credited_ages = []
    over_30_count = 0
    over_30_value = Decimal("0")
    pending_count = 0
    pending_value = Decimal("0")
    rejected_count = 0
    rejected_value = Decimal("0")
    credited_missing_credit_date = 0

    over_30_rows = []
    pending_rows = []
    rejected_rows = []

    for row in claims:
        status = (row.get("status") or "").strip()
        claim_value = decimal_value(row.get("claim_value_inr"))

        if status == "Pending":
            pending_count += 1
            pending_value += claim_value
            pending_rows.append(row)
        elif status == "Rejected":
            rejected_count += 1
            rejected_value += claim_value
            rejected_rows.append(row)
        elif status == "Credited":
            claim_date = parse_date(row.get("claim_date"))
            credit_date = parse_date(row.get("credit_note_date"))
            if claim_date is not None and credit_date is not None:
                age_days = (credit_date - claim_date).days
                credited_ages.append(age_days)
                if age_days > 30:
                    over_30_count += 1
                    over_30_value += claim_value
                    over_30_rows.append({
                        **row,
                        "claim_to_credit_days": str(age_days),
                    })
            else:
                credited_missing_credit_date += 1

    average_tat = (
        sum(credited_ages) / len(credited_ages)
        if credited_ages
        else 0
    )

    return {
        "claim_row_count": len(claims),
        "credited_claim_count": len(credited_ages),
        "credited_claim_missing_date_count": credited_missing_credit_date,
        "average_claim_to_credit_days": round(average_tat, 2),
        "claims_over_30_days_count": over_30_count,
        "claims_over_30_days_value_inr": float(over_30_value),
        "pending_claim_count": pending_count,
        "pending_claim_value_inr": float(pending_value),
        "rejected_claim_count": rejected_count,
        "rejected_claim_value_inr": float(rejected_value),
    }, over_30_rows, pending_rows, rejected_rows


def export_rows(rows, output_path, extra_fields=()):
    if not rows:
        output_path.write_text("", encoding="utf-8")
        return

    fieldnames = list(extra_fields) + [
        key for key in rows[0].keys() if key not in extra_fields
    ]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze claim-to-credit-note time and claim status."
    )
    parser.add_argument(
        "--data",
        type=Path,
        help="Data directory containing expiry_claims.csv",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print only JSON output",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export over-30-day, pending, and rejected claims",
    )
    args = parser.parse_args()

    data_dir = args.data.resolve() if args.data else default_data_dir()
    result, over_30_rows, pending_rows, rejected_rows = (
        analyze_claim_tat(data_dir)
    )
    result["data_directory"] = str(data_dir)

    if args.export:
        analysis_dir = Path(__file__).resolve().parent
        over_30_path = analysis_dir / "claims_over_30_days.csv"
        pending_path = analysis_dir / "pending_claims.csv"
        rejected_path = analysis_dir / "rejected_claims.csv"
        export_rows(over_30_rows, over_30_path)
        export_rows(pending_rows, pending_path)
        export_rows(rejected_rows, rejected_path)
        result["claims_over_30_days_export"] = str(over_30_path)
        result["pending_claims_export"] = str(pending_path)
        result["rejected_claims_export"] = str(rejected_path)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print("Project Sankalp claim TAT analysis")
    print(f"Data: {data_dir}")
    print(
        "Average claim-to-credit-note time: "
        f"{result['average_claim_to_credit_days']:.2f} days "
        "(policy target: 30 days)"
    )
    print(
        "Credited claims over 30 days: "
        f"{result['claims_over_30_days_count']:,}"
    )
    print(
        "Their claim value: "
        f"INR {result['claims_over_30_days_value_inr']:,.2f}"
    )
    print(
        "Pending claims: "
        f"{result['pending_claim_count']:,}"
    )
    print(
        "Pending claim value: "
        f"INR {result['pending_claim_value_inr']:,.2f}"
    )
    print(
        "Rejected claims: "
        f"{result['rejected_claim_count']:,}"
    )
    print(
        "Rejected claim value: "
        f"INR {result['rejected_claim_value_inr']:,.2f}"
    )

    if args.export:
        print(f"Over-30-day export: {over_30_path}")
        print(f"Pending export: {pending_path}")
        print(f"Rejected export: {rejected_path}")


if __name__ == "__main__":
    main()
