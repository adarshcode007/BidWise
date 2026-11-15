"""Compliance Agent for BidWise tender evaluation system.

Validates bid submissions against mandatory document requirements and validity dates.
Can disqualify non-compliant bids.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from logs.logger import log_event
from state.scorecard import Scorecard
from tools.compliance_tools import ComplianceTools, check_required_docs, check_validity_dates


class ComplianceAgent:
    """Agent that performs compliance verification and potential bid disqualification."""

    def __init__(self, kernel: Any = None):
        self.agent_name = "ComplianceAgent"
        self.compliance_tools = ComplianceTools()
        self.kernel = kernel
        if self.kernel:
            self.kernel.add_plugin(self.compliance_tools, plugin_name="CompliancePlugin")

    async def evaluate_bid(
        self,
        bid_id: str,
        bid_text: str,
        scorecard: Scorecard,
        as_of: str = "2026-12-31",
    ) -> Dict[str, Any]:
        """Evaluates bid compliance. Disqualifies if mandatory documents are missing or date is invalid."""
        run_id = scorecard.run_id
        # Obtain required mandatory docs from scorecard criteria (populated by CriteriaAgent)
        required_docs = scorecard.criteria.get(
            "mandatory_documents",
            ["Registration Certificate", "Tax Clearance", "EMD Receipt", "Experience Certificate"],
        )

        log_event(
            run_id=run_id,
            agent=self.agent_name,
            tool="ComplianceAgent.evaluate_bid",
            input_summary=f"Evaluating compliance for {bid_id}",
            output_summary=f"Mandatory checklist count={len(required_docs)}",
        )

        # Tool 1: Check mandatory documents
        doc_result = self.compliance_tools.check_required_docs(bid_text=bid_text, required_docs=required_docs)

        # Tool 2: Check validity date
        date_result = self.compliance_tools.check_validity_dates(bid_text=bid_text, as_of=as_of)

        all_reasons: List[str] = []
        is_compliant = True
        disqualified = False
        disqualification_reason: Optional[str] = None

        if not doc_result["compliant"]:
            is_compliant = False
            disqualified = True
            all_reasons.extend(doc_result["reasons"])
            disqualification_reason = f"Disqualified: Missing mandatory documents: {', '.join(doc_result['missing_docs'])}"

        if not date_result["valid"]:
            is_compliant = False
            all_reasons.extend(date_result["reasons"])
            if not disqualified:
                disqualified = True
                disqualification_reason = f"Disqualified: Invalid validity date ({', '.join(date_result['reasons'])})"

        # Write compliance slice into shared thread-safe scorecard
        await scorecard.update_compliance_slice(
            bid_id=bid_id,
            is_compliant=is_compliant,
            reasons=all_reasons,
            disqualified=disqualified,
            disqualification_reason=disqualification_reason,
            agent=self.agent_name,
        )

        log_event(
            run_id=run_id,
            agent=self.agent_name,
            tool="ComplianceAgent.evaluate_bid",
            input_summary=f"Result for {bid_id}: compliant={is_compliant}, disqualified={disqualified}",
            output_summary=disqualification_reason or "Compliant",
        )

        return {
            "bid_id": bid_id,
            "compliant": is_compliant,
            "disqualified": disqualified,
            "disqualification_reason": disqualification_reason,
            "doc_check": doc_result,
            "date_check": date_result,
        }
