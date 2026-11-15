"""Technical feature extraction and rubric scoring tools for Technical Scorer.

Functions are plain Python callables and decorated with @kernel_function for Semantic Kernel plugin integration.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from semantic_kernel.functions import kernel_function

from config import RUBRIC_PATH


class ScoringTools:
    """Plugin wrapper and direct functions for technical feature scoring."""

    def __init__(self, rubric_path: Optional[Path] = None):
        self.rubric_path = Path(rubric_path) if rubric_path else RUBRIC_PATH
        self._cached_rubric: Optional[Dict[str, Any]] = None

    def get_rubric(self) -> Dict[str, Any]:
        """Loads technical rubric from JSON."""
        if self._cached_rubric is None:
            if self.rubric_path.exists():
                with open(self.rubric_path, "r", encoding="utf-8") as f:
                    self._cached_rubric = json.load(f)
            else:
                self._cached_rubric = {}
        return self._cached_rubric

    @kernel_function(
        description="Extract quantitative technical and commercial features from raw bid text.",
        name="extract_bid_features",
    )
    def extract_bid_features(self, bid_text: str) -> Dict[str, Any]:
        """Parses vendor bid text and extracts structured features."""
        features: Dict[str, Any] = {
            "years_of_experience": 0,
            "certifications": [],
            "team_size": 0,
            "similar_projects": 0,
            "delivery_days": 90,
            "quoted_price": 0.0,
            "payment_terms": "",
            "vendor_name": "",
        }

        # Vendor name
        vendor_match = re.search(r"Bidder Name:\s*([^\n]+)", bid_text, re.IGNORECASE)
        if vendor_match:
            features["vendor_name"] = vendor_match.group(1).strip()

        # Quoted price
        price_match = re.search(r"(?:Total Quoted Price|Price|Quoted Price)[\s:\$]*([0-9]+(?:\.[0-9]+)?)", bid_text, re.IGNORECASE)
        if price_match:
            features["quoted_price"] = float(price_match.group(1))

        # Payment terms
        terms_match = re.search(r"Payment Terms:\s*([^\n]+)", bid_text, re.IGNORECASE)
        if terms_match:
            features["payment_terms"] = terms_match.group(1).strip()

        # Experience years
        exp_match = re.search(r"Years of Experience:\s*(\d+)", bid_text, re.IGNORECASE)
        if exp_match:
            features["years_of_experience"] = int(exp_match.group(1))

        # Certifications
        cert_matches = []
        if "iso 9001" in bid_text.lower():
            cert_matches.append("ISO 9001")
        if "iso 27001" in bid_text.lower():
            cert_matches.append("ISO 27001")
        features["certifications"] = cert_matches

        # Team size
        team_match = re.search(r"(?:Technical Engineering Team Size|Team Size):\s*(\d+)", bid_text, re.IGNORECASE)
        if team_match:
            features["team_size"] = int(team_match.group(1))

        # Similar projects
        proj_match = re.search(r"(?:Similar Enterprise Network Projects|Similar Projects):\s*(\d+)", bid_text, re.IGNORECASE)
        if proj_match:
            features["similar_projects"] = int(proj_match.group(1))

        # Delivery timeline days
        delivery_match = re.search(r"(?:Committed Delivery Timeline|Delivery Timeline|Delivery):\s*(\d+)\s*days", bid_text, re.IGNORECASE)
        if delivery_match:
            features["delivery_days"] = int(delivery_match.group(1))

        return features

    @kernel_function(
        description="Score extracted bid features against the technical, experience, and delivery rubrics.",
        name="score_against_rubric",
    )
    def score_against_rubric(
        self,
        features: Dict[str, Any],
        rubric: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Calculates rubric scores for technical, experience, and delivery criteria."""
        rubric = rubric or self.get_rubric()

        # 1. Certifications Score (out of 15)
        certs = features.get("certifications", [])
        cert_score = 0.0
        if "ISO 9001" in certs and "ISO 27001" in certs:
            cert_score = 15.0
        elif "ISO 9001" in certs:
            cert_score = 9.0
        else:
            cert_score = 0.0

        # 2. Team Size Score (out of 10)
        team_size = features.get("team_size", 0)
        if team_size >= 20:
            team_score = 10.0
        elif team_size >= 15:
            team_score = 7.5
        else:
            team_score = 5.0

        # 3. Similar Projects Score (out of 15)
        sim_projects = features.get("similar_projects", 0)
        if sim_projects >= 7:
            proj_score = 15.0
        elif sim_projects >= 5:
            proj_score = 12.0
        elif sim_projects >= 3:
            proj_score = 9.0
        else:
            proj_score = 4.5

        # Technical subtotal (max 40)
        technical_subtotal = cert_score + team_score + proj_score

        # 4. Years of Experience Score (out of 20)
        exp_years = features.get("years_of_experience", 0)
        if exp_years >= 10:
            exp_score = 20.0
        elif exp_years >= 7:
            exp_score = 16.0
        elif exp_years >= 5:
            exp_score = 12.0
        else:
            exp_score = 8.0

        # 5. Delivery timeline Score (out of 10)
        delivery_days = features.get("delivery_days", 90)
        if delivery_days <= 25:
            delivery_score = 10.0
        elif delivery_days <= 35:
            delivery_score = 8.5
        elif delivery_days <= 50:
            delivery_score = 7.0
        elif delivery_days <= 70:
            delivery_score = 5.0
        else:
            delivery_score = 2.0

        return {
            "technical_score": round(technical_subtotal, 2),
            "experience_score": round(exp_score, 2),
            "delivery_score": round(delivery_score, 2),
            "breakdown": {
                "certifications": cert_score,
                "team_size": team_score,
                "similar_projects": proj_score,
                "experience_years": exp_score,
                "delivery_days": delivery_score,
            },
        }


_default_scoring_tools = ScoringTools()


def extract_bid_features(bid_text: str) -> Dict[str, Any]:
    return _default_scoring_tools.extract_bid_features(bid_text=bid_text)


def score_against_rubric(features: Dict[str, Any], rubric: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return _default_scoring_tools.score_against_rubric(features=features, rubric=rubric)
