"""RAG retrieval and parsing tools for Criteria Agent.

Functions are plain Python callables and decorated with @kernel_function for Semantic Kernel plugin integration.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from semantic_kernel.functions import kernel_function

from rag.retriever import Retriever

logger = logging.getLogger(__name__)


class RagTools:
    """Plugin wrapper and direct functions for RAG and criteria extraction."""

    def __init__(self, retriever: Optional[Retriever] = None):
        self.retriever = retriever or Retriever()

    @kernel_function(
        description="Retrieve relevant clauses from the tender document based on query.",
        name="retrieve_clauses",
    )
    def retrieve_clauses(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """Retrieves matching clauses from the tender index."""
        return self.retriever.retrieve(query=query, top_k=top_k)

    @kernel_function(
        description="Parse evaluation criteria and weights from text, normalizing to 100 if necessary.",
        name="parse_weights",
    )
    def parse_weights(self, text: str) -> Dict[str, Any]:
        """Extracts criterion weights and normalizes them if sum != 100."""
        # Matches patterns like "Technical Capability: 40% weight", "Commercial: 30", etc.
        patterns = [
            r"(\bTechnical\b[^\n\d]*?(\d+(?:\.\d+)?)\s*%)",
            r"(\bCommercial\b[^\n\d]*?(\d+(?:\.\d+)?)\s*%)",
            r"(\bExperience\b[^\n\d]*?(\d+(?:\.\d+)?)\s*%)",
            r"(\bDelivery\b[^\n\d]*?(\d+(?:\.\d+)?)\s*%)",
        ]

        extracted: Dict[str, float] = {}

        # Scan text for standard tender criteria
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                val = float(match.group(2))
                if "technical" in pat.lower():
                    extracted["technical"] = val
                elif "commercial" in pat.lower():
                    extracted["commercial"] = val
                elif "experience" in pat.lower():
                    extracted["experience"] = val
                elif "delivery" in pat.lower():
                    extracted["delivery"] = val

        # Fallback if regex was specific or different format: scan key: weight
        if not extracted:
            line_pattern = re.compile(r"([A-Za-z\s]+)[:\-]\s*(\d+(?:\.\d+)?)\s*(?:%|points)?", re.IGNORECASE)
            for line in text.splitlines():
                m = line_pattern.search(line)
                if m:
                    key = m.group(1).strip().lower()
                    val = float(m.group(2))
                    if "tech" in key:
                        extracted["technical"] = val
                    elif "comm" in key or "price" in key:
                        extracted["commercial"] = val
                    elif "exp" in key:
                        extracted["experience"] = val
                    elif "deliv" in key:
                        extracted["delivery"] = val

        # Default fallback if nothing found
        if not extracted:
            extracted = {"technical": 40.0, "commercial": 30.0, "experience": 20.0, "delivery": 10.0}

        total_weight = sum(extracted.values())
        normalized = False
        warning = None

        if abs(total_weight - 100.0) > 1e-4:
            normalized = True
            warning = f"Weights sum to {total_weight:.2f}, not 100.0. Normalizing proportionally."
            logger.warning(warning)
            extracted = {k: round((v / total_weight) * 100.0, 2) for k, v in extracted.items()}

        return {
            "weights": extracted,
            "sum": sum(extracted.values()),
            "normalized": normalized,
            "warning": warning,
        }

    @kernel_function(
        description="Extract mandatory required documents from clause text.",
        name="parse_mandatory_docs",
    )
    def parse_mandatory_docs(self, text: str) -> List[str]:
        """Extracts required compliance document titles from clause text."""
        docs = []
        # Look for bullet points like "- Registration Certificate"
        bullet_matches = re.findall(r"^[\s*\-•]+\s*([A-Za-z\s]+?)(?:\s*\(.*?\))?$", text, re.MULTILINE)
        if bullet_matches:
            for b in bullet_matches:
                clean = b.strip()
                if clean and len(clean) > 3 and not clean.lower().startswith("failure"):
                    docs.append(clean)
        if not docs:
            # Fallback expected standard docs
            docs = ["Registration Certificate", "Tax Clearance", "EMD Receipt", "Experience Certificate"]
        return docs


# Pure standalone functional interfaces for direct calls
_default_rag_tools = RagTools()


def retrieve_clauses(query: str, top_k: int = 2) -> List[Dict[str, Any]]:
    return _default_rag_tools.retrieve_clauses(query=query, top_k=top_k)


def parse_weights(text: str) -> Dict[str, Any]:
    return _default_rag_tools.parse_weights(text=text)


def parse_mandatory_docs(text: str) -> List[str]:
    return _default_rag_tools.parse_mandatory_docs(text=text)
