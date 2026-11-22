#!/usr/bin/env python3
"""Analyze duplicate and master-reconciliation risks in the supplied CSV files."""

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


def default_data_dir():
    return Path(__file__).resolve().parent.parent / "data"


def run(data_dir, export=True):
    names = [
        "batch_master",
        "claim_emails",
        "cnf_stock_snapshot",
        "expiry_claims",
        "primary_sales",
        "sku_master",
        "stockist_master",
    ]
    frames = {
        name: pd.read_csv(data_dir / f"{name}.csv", dtype=str)
        for name in names
    }

    sku = frames["sku_master"].copy()
    stockist = frames["stockist_master"].copy()
    batch = frames["batch_master"].copy()
    sales = frames["primary_sales"].copy()
    claims = frames["expiry_claims"].copy()
    stock = frames["cnf_stock_snapshot"].copy()

    sku["sku_code"] = clean_sku(sku["sku_code"])
    batch["sku_code"] = clean_sku(batch["sku_code"])
    batch["batch_no"] = clean_code(batch["batch_no"])
    stockist["stockist_code"] = clean_code(stockist["stockist_code"])
    sales["sku_code"] = clean_sku(sales["sku_code"])
    sales["stockist_code"] = clean_code(sales["stockist_code"])
    claims["sku_code"] = clean_sku(claims["sku_code"])
    claims["stockist_code"] = clean_code(claims["stockist_code"])
    stock["sku_code"] = clean_sku(stock["sku_code"])
    stock["batch_no"] = clean_code(stock["batch_no"])

    unknown_sales_sku = int(
        (~sales["sku_code"].isin(set(sku["sku_code"]))).sum()
    )
    unknown_claim_sku = int(
        (~claims["sku_code"].isin(set(sku["sku_code"]))).sum()
    )
    unknown_sales_stockist = int(
        (~sales["stockist_code"].isin(set(stockist["stockist_code"]))).sum()
    )
    unknown_claim_stockist = int(
        (~claims["stockist_code"].isin(set(stockist["stockist_code"]))).sum()
    )
    blank_stock_batch = int((
        stock["batch_no"].isna()
        | stock["batch_no"].fillna("").str.strip().eq("")
    ).sum())
    missing_invoice_ref = int(
        claims["original_invoice_ref"].fillna("").str.strip().eq("").sum()
    )

    duplicate_counts = pd.Series({
        "sales_exact_duplicates": int(sales.duplicated().sum()),
        "claim_exact_duplicates": int(claims.duplicated().sum()),
        "stock_exact_duplicates": int(stock.duplicated().sum()),
        "batch_exact_duplicates": int(batch.duplicated().sum()),
    })

    result = {
        "sales_exact_duplicate_rows": int(sales.duplicated().sum()),
        "claim_exact_duplicate_rows": int(claims.duplicated().sum()),
        "stock_exact_duplicate_rows": int(stock.duplicated().sum()),
        "batch_exact_duplicate_rows": int(batch.duplicated().sum()),
        "claims_missing_invoice_reference_rows": missing_invoice_ref,
        "unknown_sales_sku_rows": unknown_sales_sku,
        "unknown_claim_sku_rows": unknown_claim_sku,
        "unknown_sales_stockist_rows": unknown_sales_stockist,
        "unknown_claim_stockist_rows": unknown_claim_stockist,
        "blank_stock_batch_rows": blank_stock_batch,
    }

    if export:
        out = data_dir.parent / "analysis"
        out.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([result]).to_csv(
            out / "data_quality_summary.csv", index=False
        )

        plot_counts = duplicate_counts.to_frame("rows")
        plot_counts["rows"] = plot_counts["rows"].clip(lower=0)
        fig, ax = plt.subplots(figsize=(8, 5))
        plot_counts["rows"].plot(kind="bar", ax=ax, color="#A35D2A")
        ax.set_title("Exact Duplicate Rows")
        ax.set_xlabel("CSV")
        ax.set_ylabel("Duplicate rows")
        ax.tick_params(axis="x", rotation=45)
        fig.tight_layout()
        fig.savefig(out / "data_quality_duplicates.png", dpi=160)
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
          f"Sales duplicate rows: {result['sales_exact_duplicate_rows']:,}\n"
          f"Claim duplicate rows: {result['claim_exact_duplicate_rows']:,}\n"
          f"Claims missing invoice: "
          f"{result['claims_missing_invoice_reference_rows']:,}")


if __name__ == "__main__":
    main()
