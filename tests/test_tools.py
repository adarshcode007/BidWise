"""Unit tests for standalone tools in tools/."""

import pytest

from tools.compliance_tools import check_required_docs, check_validity_dates
from tools.rag_tools import parse_mandatory_docs, parse_weights
from tools.ranking_tools import (
    apply_secondary_criterion,
    apply_weights,
    check_payment_terms,
    detect_ties,
    normalize_price,
    rank_bids,
)
from tools.scoring_tools import extract_bid_features, score_against_rubric


def test_parse_weights_exact():
    sample_text = (
        "Clause 4: Evaluation Criteria\n"
        "Technical Capability: 40% weight\n"
        "Commercial and Price Competitiveness: 30% weight\n"
        "Experience and Track Record: 20% weight\n"
        "Delivery Timeline: 10% weight\n"
    )
    res = parse_weights(sample_text)
    assert res["normalized"] is False
    assert res["weights"]["technical"] == 40.0
    assert res["weights"]["commercial"] == 30.0
    assert res["weights"]["experience"] == 20.0
    assert res["weights"]["delivery"] == 10.0
    assert res["sum"] == 100.0


def test_parse_weights_normalization():
    # Weights sum to 80 (not 100) -> should normalize proportionally
    sample_text = "Technical: 40%\nCommercial: 20%\nExperience: 20%"
    res = parse_weights(sample_text)
    assert res["normalized"] is True
    assert res["warning"] is not None
    assert round(res["sum"], 1) == 100.0


def test_check_required_docs():
    req = ["Registration Certificate", "Tax Clearance", "EMD Receipt"]
    compliant_text = "Submitted:\n- Registration Certificate\n- Tax Clearance\n- EMD Receipt"
    res1 = check_required_docs(compliant_text, req)
    assert res1["compliant"] is True
    assert len(res1["missing_docs"]) == 0

    non_compliant_text = "Submitted:\n- Registration Certificate\n- Tax Clearance"
    res2 = check_required_docs(non_compliant_text, req)
    assert res2["compliant"] is False
    assert "EMD Receipt" in res2["missing_docs"]


def test_check_validity_dates():
    valid_text = "Bid Validity: Valid until 2027-08-31"
    res1 = check_validity_dates(valid_text)
    assert res1["valid"] is True

    invalid_text = "Bid Validity: Valid until 2027-01-01"  # Tender requires 2027-06-30
    res2 = check_validity_dates(invalid_text)
    assert res2["valid"] is False


def test_normalize_price():
    prices = {"bid_B": 100000.0, "bid_A": 125000.0}
    scores = normalize_price(prices, max_marks=30.0)
    assert scores["bid_B"] == 30.0
    assert scores["bid_A"] == 24.0


def test_score_against_rubric():
    features = {
        "certifications": ["ISO 9001", "ISO 27001"],
        "team_size": 25,
        "similar_projects": 8,
        "years_of_experience": 12,
        "delivery_days": 45,
    }
    rubric_scores = score_against_rubric(features)
    assert rubric_scores["technical_score"] == 40.0
    assert rubric_scores["experience_score"] == 20.0
    assert rubric_scores["delivery_score"] == 7.0


def test_tie_break_detection_and_resolution():
    ranked = [
        {"bid_id": "bid_D", "total": 92.09, "rank": 1, "delivery_days": 20},
        {"bid_id": "bid_A", "total": 91.00, "rank": 2, "delivery_days": 45},
    ]
    # Margin is 2.0 -> score diff is 1.09 <= 2.0
    assert detect_ties(ranked, margin=2.0) is True

    # If first candidate had longer delivery days, tiebreak swaps them
    inverted = [
        {"bid_id": "bid_A", "total": 92.09, "rank": 1, "delivery_days": 45},
        {"bid_id": "bid_D", "total": 91.00, "rank": 2, "delivery_days": 20},
    ]
    resolved = apply_secondary_criterion(inverted, secondary_criterion="delivery_days")
    assert resolved[0]["bid_id"] == "bid_D"
    assert resolved[0]["rank"] == 1
