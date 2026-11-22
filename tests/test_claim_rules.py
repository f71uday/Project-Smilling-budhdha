from agent.rules import (
    evaluate_claim_quantity,
    evaluate_duplicate_claim,
    evaluate_expiry_claim_window,
    find_duplicate_claim_line_indices,
)


def test_claim_quantity_must_be_strictly_less_than_invoiced_quantity():
    assert evaluate_claim_quantity("9 strips", "10")["status"] == "within_invoice_quantity"
    assert evaluate_claim_quantity("10", "10")["status"] == "equal_to_invoice_quantity"
    assert evaluate_claim_quantity("11", "10")["status"] == "exceeds_invoice_quantity"


def test_claim_quantity_is_unverified_when_email_expression_is_ambiguous():
    result = evaluate_claim_quantity("43 boxes (10 strips each)", "50")
    assert result["status"] == "unverified"


def test_near_expiry_window_includes_both_90_day_boundaries():
    expiry_date = "30-09-2025"
    assert evaluate_expiry_claim_window("02-07-2025", expiry_date)["status"] == "within_provisional_window"
    assert evaluate_expiry_claim_window("01-07-2025", expiry_date)["status"] == "outside_provisional_window"
    assert evaluate_expiry_claim_window(expiry_date, expiry_date)["window_type"] == "near_expiry"


def test_post_expiry_window_includes_90_days_and_excludes_day_91():
    expiry_date = "30-09-2025"
    assert evaluate_expiry_claim_window("29-12-2025", expiry_date)["status"] == "within_provisional_window"
    assert evaluate_expiry_claim_window("30-12-2025", expiry_date)["status"] == "outside_provisional_window"


def test_expiry_check_is_unverified_when_dates_are_missing_or_invalid():
    result = evaluate_expiry_claim_window("not-a-date", "30-09-2025")
    assert result["status"] == "unverified"
    assert result["rule"] == "provisional_90_day"


def test_duplicate_check_requires_matching_invoice_and_quantity_for_comparable_match():
    history = {
        "found": True,
        "claims": [
            {
                "claim_no": "CLM-1",
                "original_invoice_ref": "INV/001",
                "qty_claimed": "38.0",
                "exact_duplicate_group_size": 1,
            }
        ],
    }

    match = evaluate_duplicate_claim(history, " inv/001 ", "38")
    mismatch = evaluate_duplicate_claim(history, "INV/001", "39")

    assert match["status"] == "possible_duplicate"
    assert match["prior_claim_refs"] == ["CLM-1"]
    assert mismatch["status"] == "repeated_history"


def test_duplicate_check_distinguishes_repeated_combination_from_duplicate():
    history = {
        "found": True,
        "claims": [
            {
                "claim_no": "CLM-2",
                "original_invoice_ref": "INV/002",
                "qty_claimed": "12",
                "exact_duplicate_group_size": 1,
            }
        ],
    }

    result = evaluate_duplicate_claim(history, None, "12")

    assert result["status"] == "repeated_history"
    assert result["prior_claim_refs"] == ["CLM-2"]


def test_duplicate_check_does_not_flag_when_no_prior_history_exists():
    result = evaluate_duplicate_claim({"found": False, "claims": []}, "INV/003", "5")
    assert result["status"] == "no_prior_match"


def test_duplicate_check_marks_invoice_match_with_uncomparable_quantity_as_possible():
    history = {
        "found": True,
        "claims": [
            {
                "claim_no": "CLM-4",
                "original_invoice_ref": "INV/004",
                "qty_claimed": "10",
                "exact_duplicate_group_size": 1,
            }
        ],
    }

    result = evaluate_duplicate_claim(history, "INV/004", "10 boxes")

    assert result["status"] == "possible_duplicate"
    assert result["quantity_comparable"] is False


def test_duplicate_lines_require_the_same_batch_invoice_and_quantity():
    indices = find_duplicate_claim_line_indices([
        {
            "batch_number": "K2300101",
            "invoice_reference": "INV/005",
            "claimed_quantity": "38 strips",
        },
        {
            "batch_number": " k2300101 ",
            "invoice_reference": "inv/005",
            "claimed_quantity": "38   strips",
        },
        {
            "batch_number": "K2300101",
            "invoice_reference": "INV/006",
            "claimed_quantity": "38 strips",
        },
    ])

    assert indices == {0, 1}
