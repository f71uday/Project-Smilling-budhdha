#!/usr/bin/env python3
"""Analyze latest C&F inventory, zero-stock records, and 365-day expiry risk."""

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
    stock = pd.read_csv(data_dir / "cnf_stock_snapshot.csv", dtype=str)
    batch = pd.read_csv(data_dir / "batch_master.csv", dtype=str)
    sku = pd.read_csv(data_dir / "sku_master.csv", dtype=str)

    stock["snapshot_date"] = parse_dates(stock["snapshot_date"])
    stock["expiry_date"] = parse_dates(stock["expiry_date"])
    stock["qty"] = pd.to_numeric(stock["qty_on_hand_packs"], errors="coerce")
    stock["cnf_code"] = normalize_cnf(stock["cnf_code"])
    stock["sku_code"] = clean_sku(stock["sku_code"])
    batch["batch_no"] = clean_code(batch["batch_no"])
    batch["expiry_date"] = parse_dates(batch["expiry_date"])
    sku["sku_code"] = clean_sku(sku["sku_code"])
    sku["pts_inr"] = pd.to_numeric(sku["pts_inr"], errors="coerce")

    latest = stock["snapshot_date"].max()
    latest_stock = stock[stock["snapshot_date"] == latest].copy()
    latest_stock = latest_stock.merge(
        batch[["batch_no", "expiry_date"]],
        on="batch_no",
        how="left",
        suffixes=("_stock", "_batch"),
    ).merge(
        sku[["sku_code", "pts_inr", "therapy_area"]],
        on="sku_code",
        how="left",
    )
    latest_stock["expiry_date"] = latest_stock[
        "expiry_date_stock"
    ].fillna(latest_stock["expiry_date_batch"])
    latest_stock["days_to_expiry"] = (
        latest_stock["expiry_date"] - latest
    ).dt.days
    latest_stock["stock_value_inr"] = (
        latest_stock["qty"].fillna(0) * latest_stock["pts_inr"]
    )
    latest_stock["risk_365"] = (
        latest_stock["qty"].fillna(0).gt(0)
        & latest_stock["days_to_expiry"].between(0, 365)
    )

    by_cnf = latest_stock.groupby("cnf_code").agg(
        positive_packs=("qty", lambda s: float(s.fillna(0).clip(lower=0).sum())),
        stock_value_inr=("stock_value_inr", "sum"),
        zero_stock_records=("qty", lambda s: int((s.fillna(0) == 0).sum())),
        packs_expiring_365=("qty", lambda s: float(
            s.where(latest_stock.loc[s.index, "risk_365"]).fillna(0).sum()
        )),
        value_expiring_365=("stock_value_inr", lambda s: float(
            s.where(latest_stock.loc[s.index, "risk_365"]).fillna(0).sum()
        )),
    ).sort_values("stock_value_inr", ascending=False)

    risk = latest_stock[latest_stock["risk_365"]].copy()
    result = {
        "latest_snapshot": latest.strftime("%Y-%m-%d"),
        "latest_stock_rows": len(latest_stock),
        "zero_stock_records": int((latest_stock["qty"].fillna(0) == 0).sum()),
        "packs_expiring_365": float(risk["qty"].sum()),
        "value_expiring_365_inr": float(risk["stock_value_inr"].sum()),
        "by_cnf": by_cnf.to_dict(orient="index"),
    }

    if export:
        out = data_dir.parent / "analysis"
        out.mkdir(parents=True, exist_ok=True)
        risk.to_csv(out / "cnf_stock_expiring_365_days.csv", index=False)
        by_cnf.to_csv(out / "cnf_stock_summary.csv")

        fig, axes = plt.subplots(1, 2, figsize=(11, 5))
        by_cnf["stock_value_inr"].div(1_000_000).plot(
            kind="bar", ax=axes[0], color="#315A7D"
        )
        axes[0].set_title("Latest C&F Inventory Value")
        axes[0].set_xlabel("C&F")
        axes[0].set_ylabel("Inventory value (INR million)")
        axes[0].tick_params(axis="x", rotation=45)

        by_cnf["zero_stock_records"].plot(
            kind="bar", ax=axes[1], color="#A35D2A"
        )
        axes[1].set_title("Zero-Stock Records")
        axes[1].set_xlabel("C&F")
        axes[1].set_ylabel("Zero-stock rows")
        axes[1].tick_params(axis="x", rotation=45)
        fig.tight_layout()
        fig.savefig(out / "cnf_stock_mismatch.png", dpi=160)
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
          f"Latest snapshot: {result['latest_snapshot']}\n"
          f"Zero-stock records: {result['zero_stock_records']:,}\n"
          f"365-day expiry risk: INR {result['value_expiring_365_inr']:,.2f}")


if __name__ == "__main__":
    main()
