"""Commercial Scorer Agent for BidWise tender evaluation system.

Evaluates price proposals, payment terms, and applies the commercial normalization formula.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from logs.logger import log_event
from state.scorecard import Scorecard
from tools.ranking_tools import RankingTools, check_payment_terms, normalize_price


class CommercialScorer:
    """Agent that assesses payment terms and calculates normalized commercial scores."""

    def __init__(self, kernel: Any = None):
        self.agent_name = "CommercialScorer"
        self.ranking_tools = RankingTools()
        self.kernel = kernel
        if self.kernel:
            self.kernel.add_plugin(self.ranking_tools, plugin_name="CommercialPlugin")

    async def score_bid(
        self,
        bid_id: str,
        bid_text: str,
        scorecard: Scorecard,
        all_compliant_prices: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Scores a bid's commercial proposal and updates scorecard."""
        run_id = scorecard.run_id

        # Tool 1: Check payment terms compliance
        payment_terms_ok = self.ranking_tools.check_payment_terms(bid_text=bid_text)

        # Extract price from bid text
        price_match = re.search(r"(?:Total Quoted Price|Price|Quoted Price)[\s:\$]*([0-9]+(?:\.[0-9]+)?)", bid_text, re.IGNORECASE)
        price = float(price_match.group(1)) if price_match else 0.0

        # Tool 2: Normalize price using tender formula
        commercial_max_marks = float(scorecard.criteria.get("weights", {}).get("commercial", 30.0))
        prices_dict = dict(all_compliant_prices) if all_compliant_prices else {bid_id: price}
        if bid_id not in prices_dict:
            prices_dict[bid_id] = price

        normalized_scores = self.ranking_tools.normalize_price(prices=prices_dict, max_marks=commercial_max_marks)
        commercial_score = normalized_scores.get(bid_id, 0.0)

        # Update commercial slice in scorecard
        await scorecard.update_commercial_slice(
            bid_id=bid_id,
            price=price,
            commercial_score=commercial_score,
            payment_terms_ok=payment_terms_ok,
            agent=self.agent_name,
        )

        log_event(
            run_id=run_id,
            agent=self.agent_name,
            tool="CommercialScorer.score_bid",
            input_summary=f"Bid {bid_id} quoted price: {price}",
            output_summary=f"Commercial score: {commercial_score:.4f}, Payment terms ok: {payment_terms_ok}",
        )

        return {
            "bid_id": bid_id,
            "price": price,
            "commercial_score": commercial_score,
            "payment_terms_ok": payment_terms_ok,
        }

    async def update_all_commercial_scores(
        self,
        scorecard: Scorecard,
    ) -> Dict[str, float]:
        """Recalculates normalized commercial scores across all compliant bids once all prices are known."""
        run_id = scorecard.run_id
        commercial_max_marks = float(scorecard.criteria.get("weights", {}).get("commercial", 30.0))

        # Filter compliant bid prices
        compliant_prices: Dict[str, float] = {}
        for bid_id, b_data in scorecard.bids.items():
            if not b_data.get("disqualified", False):
                p = b_data.get("price")
                if p and p > 0:
                    compliant_prices[bid_id] = p

        normalized_scores = self.ranking_tools.normalize_price(prices=compliant_prices, max_marks=commercial_max_marks)

        for bid_id, score in normalized_scores.items():
            price = compliant_prices[bid_id]
            payment_terms_ok = scorecard.bids[bid_id].get("features", {}).get("payment_terms_ok", True)
            await scorecard.update_commercial_slice(
                bid_id=bid_id,
                price=price,
                commercial_score=score,
                payment_terms_ok=payment_terms_ok,
                agent=self.agent_name,
            )

        log_event(
            run_id=run_id,
            agent=self.agent_name,
            tool="CommercialScorer.update_all_commercial_scores",
            input_summary=f"Prices: {compliant_prices}",
            output_summary=f"Normalized scores: {normalized_scores}",
        )

        return normalized_scores
