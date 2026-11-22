"""Cached CSV loaders for data/. Every other module reads data through these."""
import csv
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent.parent / "data"


def code(value: object) -> str:
    """Normalise an identifier (batch, SKU, invoice, stockist) so lookups do not miss."""
    return str(value or "").strip().upper()


def cnf_key(value: object) -> str:
    """C&F codes appear as both CF-N01 and CFN01 in the snapshot; compare on letters and digits only."""
    return "".join(ch for ch in code(value) if ch.isalnum())


def _read(name: str) -> list[dict[str, str]]:
    with open(DATA / name, newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


@lru_cache(maxsize=1)
def skus() -> dict[str, dict[str, str]]:
    return {code(r["sku_code"]): r for r in _read("sku_master.csv")}


@lru_cache(maxsize=1)
def batches() -> dict[str, dict[str, str]]:
    """Batch master joined to the SKU master, keyed by cleaned batch number."""
    out = {}
    for r in _read("batch_master.csv"):
        sku = code(r["sku_code"])
        out[code(r["batch_no"])] = {**skus().get(sku, {}), **r, "sku_code": sku}
    return out


@lru_cache(maxsize=1)
def expiry_claims() -> list[dict[str, str]]:
    return _read("expiry_claims.csv")


@lru_cache(maxsize=1)
def sales() -> list[dict[str, str]]:
    return _read("primary_sales.csv")


@lru_cache(maxsize=1)
def stockists() -> list[dict[str, str]]:
    return _read("stockist_master.csv")


@lru_cache(maxsize=1)
def snapshots() -> list[dict[str, str]]:
    return _read("cnf_stock_snapshot.csv")
