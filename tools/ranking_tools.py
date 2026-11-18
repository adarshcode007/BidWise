"""Commercial scoring, weighting, ranking, and tie-breaking tools.

Functions are plain Python callables and decorated with @kernel_function for Semantic Kernel plugin integration.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from semantic_kernel.functions import kernel_function


class RankingTools:
    """Plugin wrapper and direct functions for commercial scoring and ranking."""

    @kernel_function(
        description="Compute normalized commercial scores using the inverse-price tender formula.",
        name="normalize_price",
    )
    def normalize_price(
        self,
        prices: Dict[str, float],
        max_marks: float = 30.0,
    ) -> Dict[str, float]:
        """Calculates commercial scores: (lowest / price) * max_marks."""
        if not prices:
            return {}

        valid_prices = {k: v for k, v in prices.items() if v > 0}
        if not valid_prices:
            return {k: 0.0 for k in prices}

        lowest_price = min(valid_prices.values())
        scores: Dict[str, float] = {}

        for bid_id, price in prices.items():
            if price <= 0:
                scores[bid_id] = 0.0
            else:
                score = (lowest_price / price) * max_marks
                scores[bid_id] = round(score, 4)

        return scores

    @kernel_function(
        description="Check if bid payment terms satisfy the required net 30 to 45 days window.",
        name="check_payment_terms",
    )
    def check_payment_terms(self, bid_text: str) -> bool:
        """Verifies payment terms compliance (e.g. net 30, net 45)."""
        lower = bid_text.lower()
        if "advance" in lower and "100%" in lower:
            return False
        # Matches milestone or net 30/45
        if re.search(r"\bnet\s*(?:30|45)\b", lower) or "milestone" in lower:
            return True
        return False

    @kernel_function(
        description="Apply weights to individual criterion scores to compute weighted total.",
        name="apply_weights",
    )
    def apply_weights(
        self,
        scores: Dict[str, float],
        weights: Dict[str, float],
    ) -> float:
        """Calculates total weighted score.

        If custom weights are supplied, scales rubric subscores proportionally to their new maximum weight.
        If scores are passed as 0-100 scales, multiplies by (weight / 100).
        """
        ref_max = {"technical": 40.0, "experience": 20.0, "delivery": 10.0}
        total = 0.0

        # Check if scores are out of 100
        is_percentage_scale = any(scores.get(k, 0.0) > weights.get(k, 100.0) for k in scores)

        for crit, weight in weights.items():
            raw_score = scores.get(crit, 0.0)
            if is_percentage_scale:
                total += raw_score * (weight / 100.0)
            elif crit in ref_max and ref_max[crit] > 0:
                scaled_score = (raw_score / ref_max[crit]) * weight
                total += scaled_score
            else:
                total += raw_score

        return round(total, 4)

    @kernel_function(
        description="Rank eligible bids by descending total score, excluding disqualified bids.",
        name="rank_bids",
    )
    def rank_bids(
        self,
        totals: Dict[str, float],
        disqualified_bids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Sorts compliant bids and assigns integer ranks (1, 2, ...)."""
        disqualified_set = set(disqualified_bids or [])

        eligible_items = [
            {"bid_id": bid_id, "total": total}
            for bid_id, total in totals.items()
            if bid_id not in disqualified_set
        ]

        # Sort descending by total score
        eligible_items.sort(key=lambda x: x["total"], reverse=True)

        ranked = []
        for i, item in enumerate(eligible_items, start=1):
            ranked.append({
                "bid_id": item["bid_id"],
                "total": item["total"],
                "rank": i,
            })

        return ranked

    @kernel_function(
        description="Detect if the score difference between top bids is within the margin.",
        name="detect_ties",
    )
    def detect_ties(
        self,
        ranked: List[Dict[str, Any]],
        margin: float = 2.0,
    ) -> bool:
        """Checks if rank 1 and rank 2 scores are within the tie margin."""
        if len(ranked) < 2:
            return False
        score_diff = abs(ranked[0]["total"] - ranked[1]["total"])
        return score_diff <= margin

    @kernel_function(
        description="Apply secondary criterion (delivery timeline or custom criterion) to resolve tie and re-rank.",
        name="apply_secondary_criterion",
    )
    def apply_secondary_criterion(
        self,
        bids_data: List[Dict[str, Any]],
        secondary_criterion: str = "delivery_days",
    ) -> List[Dict[str, Any]]:
        """Resolves ties between top candidates using secondary criterion (e.g. delivery_days, price, technical)."""
        if len(bids_data) < 2:
            return bids_data

        # Clone list to avoid mutating input
        resolved = [dict(b) for b in bids_data]

        first = resolved[0]
        second = resolved[1]

        lower_is_better = secondary_criterion in ["delivery_days", "price", "quoted_price"]
        first_val = first.get(secondary_criterion, 999999 if lower_is_better else 0)
        second_val = second.get(secondary_criterion, 999999 if lower_is_better else 0)

        should_swap = (second_val < first_val) if lower_is_better else (second_val > first_val)
        if should_swap:
            resolved[0] = second
            resolved[1] = first

        # Reassign ranks 1..N
        for idx, item in enumerate(resolved, start=1):
            item["rank"] = idx

        return resolved


_default_ranking_tools = RankingTools()


def normalize_price(prices: Dict[str, float], max_marks: float = 30.0) -> Dict[str, float]:
    return _default_ranking_tools.normalize_price(prices=prices, max_marks=max_marks)


def check_payment_terms(bid_text: str) -> bool:
    return _default_ranking_tools.check_payment_terms(bid_text=bid_text)


def apply_weights(scores: Dict[str, float], weights: Dict[str, float]) -> float:
    return _default_ranking_tools.apply_weights(scores=scores, weights=weights)


def rank_bids(totals: Dict[str, float], disqualified_bids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    return _default_ranking_tools.rank_bids(totals=totals, disqualified_bids=disqualified_bids)


def detect_ties(ranked: List[Dict[str, Any]], margin: float = 2.0) -> bool:
    return _default_ranking_tools.detect_ties(ranked=ranked, margin=margin)


def apply_secondary_criterion(bids_data: List[Dict[str, Any]], secondary_criterion: str = "delivery_days") -> List[Dict[str, Any]]:
    return _default_ranking_tools.apply_secondary_criterion(bids_data=bids_data, secondary_criterion=secondary_criterion)
