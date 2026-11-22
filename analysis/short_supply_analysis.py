#!/usr/bin/env python3
"""Analyze incomplete invoice quantities and regional short supply."""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def clean_code(series):
    return series.astype("string").str.strip().str.upper()


def default_data_dir():
    return Path(__file__).resolve().parent.parent / "data"


def run(data_dir, export=True):
    sales = pd.read_csv(data_dir / "primary_sales.csv", dtype=str)
    sales["cnf_code"] = clean_code(sales["cnf_code"])
    sales["ordered_qty"] = pd.to_numeric(sales["ordered_qty"], errors="coerce")
    sales["invoiced_qty"] = pd.to_numeric(sales["invoiced_qty"], errors="coerce")
    sales["pts_inr"] = pd.to_numeric(sales["pts_inr"], errors="coerce")
    sales["unfilled_qty"] = np.maximum(
        sales["ordered_qty"].fillna(0) - sales["invoiced_qty"].fillna(0),
        0,
    )
    short = sales[sales["ordered_qty"].notna()].copy()

    by_cnf = short.groupby("cnf_code").agg(
        first_line_rows=("invoice_no", "size"),
        short_line_rows=("unfilled_qty", lambda s: int((s > 0).sum())),
        unfilled_packs=("unfilled_qty", "sum"),
        unfilled_value_inr=(
            "unfilled_qty",
            lambda s: float((s * short.loc[s.index, "pts_inr"]).sum()),
        ),
    ).sort_values("unfilled_packs", ascending=False)

    result = {
        "first_line_rows": len(short),
        "short_line_rows": int((short["unfilled_qty"] > 0).sum()),
        "unfilled_packs": float(short["unfilled_qty"].sum()),
        "unfilled_value_inr": float(
            (short["unfilled_qty"] * short["pts_inr"]).sum()
        ),
        "by_cnf": by_cnf.to_dict(orient="index"),
    }

    if export:
        out = data_dir.parent / "analysis"
        out.mkdir(parents=True, exist_ok=True)
        short.to_csv(out / "short_supply_sales_lines.csv", index=False)
        by_cnf.to_csv(out / "short_supply_by_cnf.csv")

        fig, ax = plt.subplots(figsize=(8, 5))
        by_cnf["unfilled_packs"].div(1_000_000).plot(
            kind="bar", ax=ax, color="#A35D2A"
        )
        ax.set_title("Unfilled Packs by C&F")
        ax.set_xlabel("C&F")
        ax.set_ylabel("Unfilled packs (million)")
        ax.tick_params(axis="x", rotation=45)
        fig.tight_layout()
        fig.savefig(out / "short_supply_by_cnf.png", dpi=160)
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
          f"Short lines: {result['short_line_rows']:,}\n"
          f"Unfilled packs: {result['unfilled_packs']:,.0f}\n"
          f"At PTS: INR {result['unfilled_value_inr']:,.2f}")


if __name__ == "__main__":
    main()
