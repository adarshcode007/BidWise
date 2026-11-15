"""End-to-end scenario tests for BidWise tender evaluation system (CSE476 Task 2).

All scenarios run offline without requiring an external LLM or API key.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from logs.logger import RunLogger
from orchestrator import run_tender_evaluation
from tools.rag_tools import parse_weights
from tools.ranking_tools import normalize_price


def test_scenario_1_clean_winner():
    """Scenario 1: Clean winner with compliant bids only.

    When evaluating Bid A and Bid B, Bid A ranks first with hand-computed totals matching.
    Bid A total = 40 (Tech) + 20 (Exp) + 7 (Delivery) + 24 (Comm) = 91.00.
    Bid B total = 25.5 (Tech) + 12 (Exp) + 5 (Delivery) + 30 (Comm) = 72.50.
    Score difference = 18.5 > 2.0 margin, so no tie-break triggers.
    """
    scorecard = asyncio.run(run_tender_evaluation(selected_bids=["bid_A", "bid_B"], print_trace=False))

    assert scorecard.bids["bid_A"]["disqualified"] is False
    assert scorecard.bids["bid_B"]["disqualified"] is False

    assert scorecard.bids["bid_A"]["rank"] == 1
    assert scorecard.bids["bid_B"]["rank"] == 2

    assert round(scorecard.bids["bid_A"]["total"], 2) == 91.00
    assert round(scorecard.bids["bid_B"]["total"], 2) == 72.50

    assert scorecard.winner == "bid_A"
    assert scorecard.tie_break_applied is False
    assert "bid_A" in scorecard.justification


def test_scenario_2_disqualification():
    """Scenario 2: Disqualification of non-compliant bid.

    Bid C is missing the mandatory EMD receipt.
    It must be disqualified, excluded from final ranking, and have its reason recorded.
    """
    scorecard = asyncio.run(run_tender_evaluation(selected_bids=["bid_A", "bid_B", "bid_C"], print_trace=False))

    bid_c = scorecard.bids["bid_C"]
    assert bid_c["disqualified"] is True
    assert bid_c["rank"] is None
    assert "EMD Receipt" in bid_c["disqualification_reason"]

    # Compliant bids should still be ranked
    assert scorecard.bids["bid_A"]["rank"] == 1
    assert scorecard.bids["bid_B"]["rank"] == 2
    assert scorecard.winner == "bid_A"


def test_scenario_3_tie_break():
    """Scenario 3: Tie-break resolution within margin.

    When evaluating Bid A and Bid D (or all bids), their totals are within TIE_MARGIN (2.0 pts).
    Bid D: 92.09, Bid A: 91.00 (difference = 1.09 <= 2.0).
    The tie-break agent applies the secondary criterion (delivery timeline).
    Bid D (20 days) wins over Bid A (45 days), and tie_break_applied is True.
    """
    scorecard = asyncio.run(run_tender_evaluation(selected_bids=["bid_A", "bid_D"], print_trace=False))

    assert scorecard.tie_break_applied is True
    assert scorecard.winner == "bid_D"
    assert scorecard.bids["bid_D"]["rank"] == 1
    assert scorecard.bids["bid_A"]["rank"] == 2

    # Verification of scores
    diff = abs(scorecard.bids["bid_D"]["total"] - scorecard.bids["bid_A"]["total"])
    assert diff <= 2.0
    assert "tie-break was triggered" in scorecard.justification.lower()


def test_scenario_4_weight_normalization_handled_failure():
    """Scenario 4a: Handled failure - weights not summing to 100 get normalized proportionally."""
    raw_text = "Technical: 50%\nCommercial: 50%\nExperience: 25%"  # Sum = 125%
    result = parse_weights(raw_text)

    assert result["normalized"] is True
    assert result["warning"] is not None
    assert round(result["sum"], 1) == 100.0

    # Proportional check: 50/125 = 40%, 25/125 = 20%
    assert result["weights"]["technical"] == 40.0
    assert result["weights"]["commercial"] == 40.0
    assert result["weights"]["experience"] == 20.0


def test_scenario_4_append_only_log_guarantee(tmp_path: Path):
    """Scenario 4b: Verifies that the run logger is strictly append-only and never truncates."""
    test_log_file = tmp_path / "test_run_log.jsonl"
    logger = RunLogger(log_path=test_log_file)

    # Initial append
    logger.log("run_1", "AgentA", "tool_1", "in_1", "out_1")
    logger.log("run_1", "AgentB", "tool_2", "in_2", "out_2")

    records_1 = logger.get_records()
    assert len(records_1) == 2

    size_after_run1 = test_log_file.stat().st_size

    # Second run append
    logger.log("run_2", "AgentC", "tool_3", "in_3", "out_3")
    records_2 = logger.get_records()
    assert len(records_2) == 3

    size_after_run2 = test_log_file.stat().st_size
    # Size must strictly increase (never truncate)
    assert size_after_run2 > size_after_run1
