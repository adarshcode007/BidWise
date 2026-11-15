"""Award Manager Agent for BidWise tender evaluation system.

Fans in all evaluation streams, applies criterion weights, ranks compliant bids,
and generates winning justification.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import GROQ_API_KEY, GROQ_MODEL, OFFLINE_MODE, USE_LLM, has_groq_api_key
from logs.logger import log_event
from state.scorecard import Scorecard
from tools.ranking_tools import RankingTools, apply_weights, rank_bids


class AwardManager:
    """Agent that aggregates scores, applies weights, ranks bids, and justifies the award."""

    def __init__(self, kernel: Any = None):
        self.agent_name = "AwardManager"
        self.ranking_tools = RankingTools()
        self.kernel = kernel
        if self.kernel:
            self.kernel.add_plugin(self.ranking_tools, plugin_name="RankingPlugin")

    async def aggregate_and_rank(self, scorecard: Scorecard) -> List[Dict[str, Any]]:
        """Computes weighted totals for all compliant bids and assigns initial ranks."""
        run_id = scorecard.run_id
        weights = scorecard.criteria.get(
            "weights",
            {"technical": 40.0, "commercial": 30.0, "experience": 20.0, "delivery": 10.0},
        )

        disqualified_bids: List[str] = [
            bid_id for bid_id, data in scorecard.bids.items() if data.get("disqualified", False)
        ]

        totals: Dict[str, float] = {}
        for bid_id, data in scorecard.bids.items():
            if bid_id in disqualified_bids:
                totals[bid_id] = 0.0
                continue
            scores = data.get("scores", {})
            # Tool 1: Apply weights
            total = self.ranking_tools.apply_weights(scores=scores, weights=weights)
            totals[bid_id] = total

        # Tool 2: Rank eligible bids
        ranked = self.ranking_tools.rank_bids(totals=totals, disqualified_bids=disqualified_bids)

        # Update totals and ranks in scorecard
        await scorecard.update_totals_and_ranks(ranked_bids=ranked, agent=self.agent_name)

        log_event(
            run_id=run_id,
            agent=self.agent_name,
            tool="AwardManager.aggregate_and_rank",
            input_summary=f"Eligible: {len(ranked)}, Disqualified: {len(disqualified_bids)}",
            output_summary=f"Top candidate: {ranked[0]['bid_id'] if ranked else 'None'} ({ranked[0]['total'] if ranked else 0:.2f})",
        )

        return ranked

    async def generate_award_recommendation(
        self,
        scorecard: Scorecard,
    ) -> Dict[str, Any]:
        """Formulates the final award decision and detailed weighted justification."""
        run_id = scorecard.run_id

        # Find rank 1 bid
        ranked_bids = [
            (bid_id, data)
            for bid_id, data in scorecard.bids.items()
            if not data.get("disqualified", False) and data.get("rank") == 1
        ]

        if not ranked_bids:
            winner_id = "NO_COMPLIANT_WINNER"
            justification = "No compliant bids met the mandatory tender specifications."
        else:
            winner_id, winner_data = ranked_bids[0]
            scores = winner_data.get("scores", {})
            weights = scorecard.criteria.get(
                "weights",
                {"technical": 40.0, "commercial": 30.0, "experience": 20.0, "delivery": 10.0},
            )
            total = winner_data.get("total", 0.0)
            vendor_name = winner_data.get("vendor_name", winner_id)
            delivery_days = winner_data.get("delivery_days", "N/A")
            price = winner_data.get("price", "N/A")

            # Check if Groq LLM should be used or offline template fallback
            if USE_LLM and has_groq_api_key() and self.kernel:
                justification = await self._generate_llm_justification(
                    winner_id=winner_id,
                    vendor_name=vendor_name,
                    scores=scores,
                    weights=weights,
                    total=total,
                    delivery_days=delivery_days,
                    price=price,
                    tie_break_applied=scorecard.tie_break_applied,
                )
            else:
                justification = self._generate_template_justification(
                    winner_id=winner_id,
                    vendor_name=vendor_name,
                    scores=scores,
                    weights=weights,
                    total=total,
                    delivery_days=delivery_days,
                    price=price,
                    tie_break_applied=scorecard.tie_break_applied,
                )

        await scorecard.set_final_award(winner_id=winner_id, justification=justification, agent=self.agent_name)

        log_event(
            run_id=run_id,
            agent=self.agent_name,
            tool="AwardManager.generate_award_recommendation",
            input_summary=f"Winner: {winner_id}",
            output_summary=justification,
        )

        return {
            "winner": winner_id,
            "justification": justification,
        }

    def _generate_template_justification(
        self,
        winner_id: str,
        vendor_name: str,
        scores: Dict[str, float],
        weights: Dict[str, float],
        total: float,
        delivery_days: Any,
        price: Any,
        tie_break_applied: bool,
    ) -> str:
        """Deterministic template-based justification citing per-criterion scores and weights."""
        tech_score = scores.get("technical", 0.0)
        tech_wt = weights.get("technical", 40.0)
        comm_score = scores.get("commercial", 0.0)
        comm_wt = weights.get("commercial", 30.0)
        exp_score = scores.get("experience", 0.0)
        exp_wt = weights.get("experience", 20.0)
        deliv_score = scores.get("delivery", 0.0)
        deliv_wt = weights.get("delivery", 10.0)

        tie_note = (
            " A margin tie-break was triggered (score difference <= 2.0 points); "
            f"the secondary criterion was applied, and {winner_id} was awarded the contract "
            f"due to its committed delivery timeline of {delivery_days} days."
            if tie_break_applied
            else ""
        )

        return (
            f"Award Recommendation: Vendor '{vendor_name}' ({winner_id}) is recommended for the award "
            f"with an overall weighted score of {total:.2f} / 100.00.\n"
            f"Evaluation Breakdown (Score achieved vs Weight):\n"
            f"- Technical Capability: {tech_score:.2f} pts (Weight: {tech_wt:.1f}%)\n"
            f"- Commercial & Price Competitiveness: {comm_score:.2f} pts (Weight: {comm_wt:.1f}%, Quoted: ${price:,.2f})\n"
            f"- Experience & Track Record: {exp_score:.2f} pts (Weight: {exp_wt:.1f}%)\n"
            f"- Delivery Timeline: {deliv_score:.2f} pts (Weight: {deliv_wt:.1f}%, Timeline: {delivery_days} days)\n"
            f"Justification Summary: The vendor successfully fulfilled all mandatory compliance requirements. "
            f"Its strong technical capabilities, verified certifications, and balanced pricing yielded the highest overall score.{tie_note}"
        )

    async def _generate_llm_justification(
        self,
        winner_id: str,
        vendor_name: str,
        scores: Dict[str, float],
        weights: Dict[str, float],
        total: float,
        delivery_days: Any,
        price: Any,
        tie_break_applied: bool,
    ) -> str:
        """LLM-backed justification generation via Groq & Semantic Kernel."""
        prompt = (
            f"You are the Award Manager for a university campus networking tender.\n"
            f"Write a formal, comprehensive procurement award justification recommending {vendor_name} ({winner_id}).\n"
            f"Total Score: {total:.2f}/100. Quoted Price: ${price}. Delivery Timeline: {delivery_days} days.\n"
            f"Score breakdown against weights:\n"
            f"- Technical Capability: {scores.get('technical', 0)} pts out of {weights.get('technical', 40)}% weight\n"
            f"- Commercial & Price Competitiveness: {scores.get('commercial', 0)} pts out of {weights.get('commercial', 30)}% weight\n"
            f"- Experience & Track Record: {scores.get('experience', 0)} pts out of {weights.get('experience', 20)}% weight\n"
            f"- Delivery Timeline: {scores.get('delivery', 0)} pts out of {weights.get('delivery', 10)}% weight\n"
            f"Tie-Break Invoked: {tie_break_applied}.\n"
            f"Format requirements:\n"
            f"1. Award Recommendation header\n"
            f"2. Explicit numerical score citation for each criterion\n"
            f"3. Executive justification summary explaining why the vendor won, including compliance confirmation and tie-break notes if applicable.\n"
            f"Keep the tone professional, objective, and audit-compliant."
        )

        # Attempt 1: Via Semantic Kernel chat service (connected to Groq)
        try:
            from semantic_kernel.contents.chat_history import ChatHistory

            chat_service = self.kernel.get_service(service_id="groq_chat") or self.kernel.get_service()
            if chat_service:
                chat_history = ChatHistory()
                chat_history.add_user_message(prompt)
                response = await chat_service.get_chat_message_content(chat_history)
                if response and str(response).strip():
                    return str(response).strip()
        except Exception:
            pass

        # Attempt 2: Direct Groq SDK fallback
        try:
            from groq import AsyncGroq

            client = AsyncGroq(api_key=GROQ_API_KEY)
            completion = await client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            content = completion.choices[0].message.content
            if content and content.strip():
                return content.strip()
        except Exception:
            pass

        # Fallback to deterministic template
        return self._generate_template_justification(
            winner_id=winner_id,
            vendor_name=vendor_name,
            scores=scores,
            weights=weights,
            total=total,
            delivery_days=delivery_days,
            price=price,
            tie_break_applied=tie_break_applied,
        )
