"""Compliance checking tools for Compliance Agent.

Functions are plain Python callables and decorated with @kernel_function for Semantic Kernel plugin integration.
"""

from __future__ import annotations

import datetime
import re
from typing import Any, Dict, List, Optional

from semantic_kernel.functions import kernel_function


class ComplianceTools:
    """Plugin wrapper and direct functions for tender compliance checking."""

    @kernel_function(
        description="Verify whether all mandatory required documents are submitted in the bid.",
        name="check_required_docs",
    )
    def check_required_docs(self, bid_text: str, required_docs: List[str]) -> Dict[str, Any]:
        """Checks for presence of each required document in the bid text."""
        submitted_docs: List[str] = []
        missing_docs: List[str] = []

        # Find documents section or lines with bullet points
        lower_bid = bid_text.lower()
        for doc in required_docs:
            clean_doc = doc.strip().lower()
            # Check for keyword matches (e.g. "emd receipt", "registration certificate")
            if clean_doc in lower_bid:
                submitted_docs.append(doc)
            else:
                missing_docs.append(doc)

        is_compliant = len(missing_docs) == 0
        reasons = []
        if not is_compliant:
            for m in missing_docs:
                reasons.append(f"Missing mandatory document: '{m}'")

        return {
            "compliant": is_compliant,
            "required_docs": required_docs,
            "submitted_docs": submitted_docs,
            "missing_docs": missing_docs,
            "reasons": reasons,
        }

    @kernel_function(
        description="Check if the bid submission validity date satisfies the tender requirement.",
        name="check_validity_dates",
    )
    def check_validity_dates(self, bid_text: str, as_of: str = "2026-12-31") -> Dict[str, Any]:
        """Checks whether the bid validity date meets or exceeds the required threshold."""
        # Find date pattern YYYY-MM-DD
        date_pattern = re.compile(r"valid\s+(?:until|through)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
        match = date_pattern.search(bid_text)

        valid_until_str = match.group(1) if match else None
        required_date = datetime.date.fromisoformat(as_of)

        is_valid = True
        reasons = []

        if valid_until_str:
            try:
                bid_date = datetime.date.fromisoformat(valid_until_str)
                # Tender requires validity through at least 2027-06-30
                tender_min_validity = datetime.date(2027, 6, 30)
                if bid_date < tender_min_validity:
                    is_valid = False
                    reasons.append(f"Bid validity {valid_until_str} is earlier than mandatory {tender_min_validity.isoformat()}")
            except ValueError:
                is_valid = False
                reasons.append(f"Malformed validity date: '{valid_until_str}'")
        else:
            is_valid = False
            reasons.append("No explicit bid validity date identified in proposal")

        return {
            "valid": is_valid,
            "bid_valid_until": valid_until_str,
            "as_of": as_of,
            "reasons": reasons,
        }


_default_compliance_tools = ComplianceTools()


def check_required_docs(bid_text: str, required_docs: List[str]) -> Dict[str, Any]:
    return _default_compliance_tools.check_required_docs(bid_text=bid_text, required_docs=required_docs)


def check_validity_dates(bid_text: str, as_of: str = "2026-12-31") -> Dict[str, Any]:
    return _default_compliance_tools.check_validity_dates(bid_text=bid_text, as_of=as_of)
