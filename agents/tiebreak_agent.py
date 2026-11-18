"""Tie-Break Agent for BidWise tender evaluation system.

Detects near-ties within the defined margin and resolves them via the secondary criterion (delivery timeline).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from logs.logger import log_event
from state.scorecard import Scorecard
from tools.ranking_tools import RankingTools, apply_secondary_criterion, detect_ties


class TieBreakAgent:
    """Agent that handles margin ties using secondary evaluation rules."""

    def __init__(self, kernel: Any = None):
        self.agent_name = "TieBreakAgent"
        self.ranking_tools = RankingTools()
        self.kernel = kernel
        if self.kernel:
            self.kernel.add_plugin(self.ranking_tools, plugin_name="TieBreakPlugin")

    async def evaluate_and_resolve(
        self,
        scorecard: Scorecard,
        margin: float = 2.0,
        secondary_criterion: str = "delivery_days",
    ) -> Dict[str, Any]:
        """Checks for score ties and resolves them by secondary criterion (e.g. delivery timeline)."""
        run_id = scorecard.run_id

        # Collect current ranked compliant bids
        eligible_bids: List[Dict[str, Any]] = []
        for bid_id, b_data in scorecard.bids.items():
            if not b_data.get("disqualified", False) and b_data.get("rank") is not None:
                eligible_bids.append({
                    "bid_id": bid_id,
                    "total": b_data.get("total", 0.0),
                    "rank": b_data.get("rank"),
                    "delivery_days": b_data.get("delivery_days", 999),
                    "price": b_data.get("price", 999999),
                    "technical": b_data.get("scores", {}).get("technical", 0.0),
                    "experience": b_data.get("scores", {}).get("experience", 0.0),
                    "vendor_name": b_data.get("vendor_name", bid_id),
                })

        # Sort by current rank
        eligible_bids.sort(key=lambda x: x["rank"])

        # Tool 1: Detect ties within margin
        is_tie = self.ranking_tools.detect_ties(ranked=eligible_bids, margin=margin)

        tie_break_applied = False
        winner_id = eligible_bids[0]["bid_id"] if eligible_bids else None
        detail = "No tie detected within margin threshold."

        if is_tie and len(eligible_bids) >= 2:
            tie_break_applied = True
            first = eligible_bids[0]
            second = eligible_bids[1]
            diff = abs(first["total"] - second["total"])

            # Tool 2: Apply secondary criterion
            resolved = self.ranking_tools.apply_secondary_criterion(
                bids_data=eligible_bids,
                secondary_criterion=secondary_criterion,
            )
            winner_id = resolved[0]["bid_id"]

            crit_name = secondary_criterion.replace("_", " ").title()
            val_winner = resolved[0].get(secondary_criterion, "N/A")
            val_runner = resolved[1].get(secondary_criterion, "N/A")

            detail = (
                f"Score margin {diff:.2f} <= {margin:.1f} pts detected between {first['bid_id']} and {second['bid_id']}. "
                f"Secondary criterion applied: {crit_name}. "
                f"{winner_id} selected as winner ({val_winner} vs {val_runner})."
            )

            # Update rankings in scorecard
            await scorecard.update_totals_and_ranks(ranked_bids=resolved, agent=self.agent_name)

        # Update tie break status in scorecard
        await scorecard.set_tie_break_result(
            applied=tie_break_applied,
            winner_id=winner_id or "None",
            detail=detail,
            agent=self.agent_name,
        )

        log_event(
            run_id=run_id,
            agent=self.agent_name,
            tool="TieBreakAgent.evaluate_and_resolve",
            input_summary=f"Tie check margin={margin}, is_tie={is_tie}",
            output_summary=detail,
        )

        return {
            "tie_break_applied": tie_break_applied,
            "winner_id": winner_id,
            "detail": detail,
        }
