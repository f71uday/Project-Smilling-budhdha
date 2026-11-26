"""Business rules in plain Python. Each rule has a pytest test."""
from agent.rules.claims import (
    EXPIRY_CLAIM_WINDOW_DAYS,
    evaluate_claim_quantity,
    evaluate_duplicate_claim,
    evaluate_expiry_claim_window,
    find_duplicate_claim_line_indices,
)
from agent.rules.expiry_risk import expiry_risk_band, expiry_risk_score, usual_order_quantity
from agent.rules.parsing import parse_date, parse_email_quantity, parse_quantity
from agent.rules.savings import duplicate_claim_saving
from agent.rules.scheme import evaluate_scheme_eligibility
from agent.rules.claim_control import (
    claim_priority,
    evaluate_claim_tat,
    evaluate_pts_difference,
    evaluate_register_claim_window,
    evaluate_supplied_quantity,
)
