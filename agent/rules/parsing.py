"""Shared parsing helpers for dates and quantities."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re


def parse_date(value: date | str | None) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        return None

    for date_format in ("%Y-%m-%d", "%d-%m-%Y", "%d-%b-%Y", "%d-%B-%Y"):
        try:
            return datetime.strptime(value.strip(), date_format).date()
        except ValueError:
            continue
    return None


def parse_quantity(value: str | None) -> Decimal | None:
    if not value or not value.strip():
        return None
    try:
        quantity = Decimal(value.strip())
    except InvalidOperation:
        return None
    return quantity if quantity.is_finite() else None


def parse_email_quantity(value: str | None) -> Decimal | None:
    if not value or not value.strip():
        return None
    numbers = re.findall(r"(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?(?![\w.])", value)
    if len(numbers) != 1:
        return None
    return parse_quantity(numbers[0].replace(",", ""))


def format_quantity(value: Decimal) -> str:
    return format(value.normalize(), "f")


def normalise_invoice(value: object) -> str:
    return str(value or "").strip().casefold()

