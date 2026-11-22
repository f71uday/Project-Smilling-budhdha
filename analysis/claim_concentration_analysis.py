#!/usr/bin/env python3
"""Analyze claim value by therapy area and C&F."""

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


def normalize_cnf(series):
    compact = clean_code(series).str.replace("-", "", regex=False)
    mapping = {
        "CFE01": "CF-E01", "CFN01": "CF-N01", "CFN02": "CF-N02",
        "CFW01": "CF-W01", "CFS01": "CF-S01", "CFS02": "CF-S02",
    }
    return compact.map(mapping).fillna(clean_code(series))


def default_data_dir():
    return Path(__file__).resolve().parent.parent / "data"


def run(data_dir, export=True):
    claims = pd.read_csv(data_dir / "expiry_claims.csv", dtype=str)
    sku = pd.read_csv(data_dir / "sku_master.csv", dtype=str)
    claims["sku_code"] = clean_sku(claims["sku_code"])
    claims["cnf_code"] = normalize_cnf(claims["cnf_code"])
    claims["claim_value_inr"] = pd.to_numeric(
        claims["claim_value_inr"].str.replace(",", "", regex=False),
        errors="coerce",
    )
    sku["sku_code"] = clean_sku(sku["sku_code"])

    joined = claims.merge(
        sku[["sku_code", "therapy_area"]],
        on="sku_code",
        how="left",
    )
    by_therapy = joined.groupby("therapy_area")["claim_value_inr"].sum()
    by_therapy = by_therapy.sort_values(ascending=False)
    by_cnf = joined.groupby("cnf_code")["claim_value_inr"].sum()
    by_cnf = by_cnf.sort_values(ascending=False)

    result = {
        "claim_value_by_therapy_inr": {
            str(k): float(v) for k, v in by_therapy.items()
        },
        "claim_value_by_cnf_inr": {
            str(k): float(v) for k, v in by_cnf.items()
        },
        "top_three_therapy_value_inr": float(by_therapy.head(3).sum()),
    }

    if export:
        out = data_dir.parent / "analysis"
        out.mkdir(parents=True, exist_ok=True)
        joined.to_csv(out / "claims_with_therapy_area.csv", index=False)
        by_therapy.to_csv(out / "claim_value_by_therapy.csv")
        by_cnf.to_csv(out / "claim_value_by_cnf.csv")

        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        by_therapy.div(1_000_000).plot(
            kind="bar", ax=axes[0], color="#315A7D"
        )
        axes[0].set_title("Claim Value by Therapy Area")
        axes[0].set_xlabel("Therapy area")
        axes[0].set_ylabel("Claim value (INR million)")
        axes[0].tick_params(axis="x", rotation=45)

        by_cnf.div(1_000_000).plot(
            kind="bar", ax=axes[1], color="#A35D2A"
        )
        axes[1].set_title("Claim Value by C&F")
        axes[1].set_xlabel("C&F")
        axes[1].set_ylabel("Claim value (INR million)")
        axes[1].tick_params(axis="x", rotation=45)
        fig.tight_layout()
        fig.savefig(out / "claim_concentration.png", dpi=160)
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
          f"Top-three therapy claim value: INR "
          f"{result['top_three_therapy_value_inr']:,.2f}")


if __name__ == "__main__":
    main()
