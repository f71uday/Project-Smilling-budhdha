#!/usr/bin/env python3
"""Measure exact stockist/SKU/batch matches between scheme sales and later claims."""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def clean_code(series):
    return series.astype("string").str.strip().str.upper()


def clean_sku(series):
    return clean_code(series).str.replace("-", "", regex=False)


def parse_dates(series):
    parsed = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d-%b-%Y", "%d-%B-%Y"):
        missing = parsed.isna()
        if missing.any():
            parsed.loc[missing] = pd.to_datetime(
                series.loc[missing], format=fmt, errors="coerce"
            )
    return parsed


def default_data_dir():
    return Path(__file__).resolve().parent.parent / "data"


def run(data_dir, export=True):
    sales = pd.read_csv(data_dir / "primary_sales.csv", dtype=str)
    claims = pd.read_csv(data_dir / "expiry_claims.csv", dtype=str)

    sales["stockist_code"] = clean_code(sales["stockist_code"])
    sales["sku_code"] = clean_sku(sales["sku_code"])
    sales["batch_no"] = clean_code(sales["batch_no"])
    sales["invoice_date"] = parse_dates(sales["invoice_date"])
    sales["pts_inr"] = pd.to_numeric(sales["pts_inr"], errors="coerce")
    sales["scheme_code"] = sales["scheme_code"].fillna("")
    sales["has_scheme"] = ~sales["scheme_code"].isin(["", "-", "NA"])

    claims["stockist_code"] = clean_code(claims["stockist_code"])
    claims["sku_code"] = clean_sku(claims["sku_code"])
    claims["batch_no"] = clean_code(claims["batch_no"])
    claims["claim_date"] = parse_dates(claims["claim_date"])
    claims["claim_value_inr"] = pd.to_numeric(
        claims["claim_value_inr"].str.replace(",", "", regex=False),
        errors="coerce",
    )

    scheme = sales[sales["has_scheme"]].copy()
    expiry_claims = claims[
        claims["claim_type"].isin(["Near expiry", "Expired"])
    ].copy()

    matched = scheme.merge(
        expiry_claims,
        on=["stockist_code", "sku_code", "batch_no"],
        how="inner",
        suffixes=("_sale", "_claim"),
    )
    matched["days_after_sale"] = (
        matched["claim_date"] - matched["invoice_date"]
    ).dt.days
    matched = matched[
        matched["days_after_sale"].between(0, 270)
    ].copy()
    matched_unique_claims = matched.drop_duplicates("claim_no")

    by_cnf = (
        matched_unique_claims.groupby("cnf_code_claim", dropna=False)
        ["claim_value_inr"]
        .sum()
        .sort_values(ascending=False)
    )

    result = {
        "scheme_invoice_claim_join_rows": len(matched),
        "unique_claim_count": matched_unique_claims["claim_no"].nunique(),
        "matched_claim_value_inr": float(
            matched_unique_claims["claim_value_inr"].sum()
        ),
        "matched_claim_value_by_cnf_inr": {
            str(k): float(v) for k, v in by_cnf.items()
        },
    }

    if export:
        out = data_dir.parent / "analysis"
        out.mkdir(parents=True, exist_ok=True)
        matched_unique_claims.to_csv(
            out / "scheme_claim_timing_matches.csv", index=False
        )
        by_cnf.to_csv(out / "scheme_claim_value_by_cnf.csv")

        fig, ax = plt.subplots(figsize=(8, 5))
        by_cnf.div(1_000_000).plot(kind="bar", ax=ax, color="#315A7D")
        ax.set_title("Scheme-to-Claim Value Within 270 Days")
        ax.set_xlabel("C&F")
        ax.set_ylabel("Matched claim value (INR million)")
        ax.tick_params(axis="x", rotation=45)
        fig.tight_layout()
        fig.savefig(out / "scheme_claim_timing_by_cnf.png", dpi=160)
        plt.close(fig)

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    data_dir = args.data.resolve() if args.data else default_data_dir()
    result = run(data_dir)
    print(result if args.json else
          f"Unique matched claims: {result['unique_claim_count']:,}\n"
          f"Matched claim value: INR {result['matched_claim_value_inr']:,.2f}")


if __name__ == "__main__":
    main()
