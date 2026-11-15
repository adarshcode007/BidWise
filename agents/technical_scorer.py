"""Technical Scorer Agent for BidWise tender evaluation system.

Extracts technical specifications and scores features against the tender rubric.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from logs.logger import log_event
from state.scorecard import Scorecard
from tools.scoring_tools import ScoringTools, extract_bid_features, score_against_rubric


class TechnicalScorer:
    """Agent that extracts bid features and scores technical, experience, and delivery criteria."""

    def __init__(self, kernel: Any = None):
        self.agent_name = "TechnicalScorer"
        self.scoring_tools = ScoringTools()
        self.kernel = kernel
        if self.kernel:
            self.kernel.add_plugin(self.scoring_tools, plugin_name="ScoringPlugin")

    async def score_bid(
        self,
        bid_id: str,
        bid_text: str,
        scorecard: Scorecard,
    ) -> Dict[str, Any]:
        """Runs technical scoring for a single bid and updates scorecard."""
        run_id = scorecard.run_id
        log_event(
            run_id=run_id,
            agent=self.agent_name,
            tool="TechnicalScorer.score_bid",
            input_summary=f"Extracting technical features for {bid_id}",
            output_summary="Starting feature extraction",
        )

        # Tool 1: Extract features from bid text
        features = self.scoring_tools.extract_bid_features(bid_text=bid_text)

        # Tool 2: Score extracted features against rubric
        rubric_scores = self.scoring_tools.score_against_rubric(features=features)

        tech_score = rubric_scores["technical_score"]
        exp_score = rubric_scores["experience_score"]
        delivery_score = rubric_scores["delivery_score"]
        delivery_days = features.get("delivery_days", 90)

        # Update technical & experience slice
        await scorecard.update_technical_slice(
            bid_id=bid_id,
            tech_score=tech_score,
            exp_score=exp_score,
            features=features,
            agent=self.agent_name,
        )

        # Update delivery slice
        await scorecard.update_delivery_slice(
            bid_id=bid_id,
            delivery_days=delivery_days,
            delivery_score=delivery_score,
            agent=self.agent_name,
        )

        log_event(
            run_id=run_id,
            agent=self.agent_name,
            tool="TechnicalScorer.score_bid",
            input_summary=f"Features for {bid_id}: Exp={features['years_of_experience']}y, Team={features['team_size']}, Proj={features['similar_projects']}",
            output_summary=f"Scores: Tech={tech_score}, Exp={exp_score}, Delivery={delivery_score}",
        )

        return {
            "bid_id": bid_id,
            "features": features,
            "technical_score": tech_score,
            "experience_score": exp_score,
            "delivery_score": delivery_score,
            "delivery_days": delivery_days,
            "breakdown": rubric_scores["breakdown"],
        }
