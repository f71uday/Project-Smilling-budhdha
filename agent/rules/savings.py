"""Money saved by catching a duplicate claim before a credit is raised."""
from collections.abc import Mapping
from decimal import Decimal

from agent.rules.parsing import parse_quantity


def duplicate_claim_saving(
    status: str,
    claimed_quantity: Decimal | None,
    prior_claims: list[Mapping[str, object]],
) -> dict[str, object]:
    """Value the repeat claim at the unit value of the prior claim it duplicates (claim value / qty)."""
    if status != "possible_duplicate":
        return {"status": "not_applicable", "amount_inr": None, "reason": "No duplicate was flagged."}
    if claimed_quantity is None or claimed_quantity <= 0:
        return {"status": "unverified", "amount_inr": None, "reason": "A comparable claimed quantity is required."}
    for claim in prior_claims:
        value = parse_quantity(str(claim.get("claim_value_inr", "")).replace(",", ""))
        quantity = parse_quantity(str(claim.get("qty_claimed", "")))
        if value is not None and quantity:
            amount = (value / quantity * claimed_quantity).quantize(Decimal("0.01"))
            return {
                "status": "estimated",
                "amount_inr": format(amount, "f"),
                "basis": f"Unit value of prior claim {claim.get('claim_no', '')}",
            }
    return {"status": "unverified", "amount_inr": None, "reason": "No prior claim had a usable value and quantity."}
