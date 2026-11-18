"""Fan-Out / Fan-In Orchestrator for BidWise Multi-Agent Tender Evaluation.

Executes Criteria retrieval, concurrent per-bid scoring fan-out, fan-in ranking,
tie-break resolution, and final report generation.
"""

from __future__ import annotations

import asyncio
import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.award_manager import AwardManager
from agents.commercial_scorer import CommercialScorer
from agents.compliance_agent import ComplianceAgent
from agents.criteria_agent import CriteriaAgent
from agents.technical_scorer import TechnicalScorer
from agents.tiebreak_agent import TieBreakAgent
from config import (
    BIDS_DIR,
    GROQ_API_KEY,
    GROQ_BASE_URL,
    GROQ_MODEL,
    OFFLINE_MODE,
    REPORT_OUTPUT_PATH,
    SCORECARD_OUTPUT_PATH,
    TENDER_PATH,
    TIE_MARGIN,
    USE_LLM,
    has_groq_api_key,
)
from logs.logger import log_event
from rag.retriever import Retriever
from state.scorecard import Scorecard
from tools.compliance_tools import ComplianceTools
from tools.rag_tools import RagTools
from tools.ranking_tools import RankingTools
from tools.scoring_tools import ScoringTools


def build_semantic_kernel(use_llm: bool = USE_LLM) -> Any:
    """Builds and configures a Semantic Kernel instance with Groq LLM and tool plugins."""
    from semantic_kernel import Kernel

    kernel = Kernel()
    kernel.add_plugin(RagTools(), plugin_name="RagPlugin")
    kernel.add_plugin(ComplianceTools(), plugin_name="CompliancePlugin")
    kernel.add_plugin(ScoringTools(), plugin_name="ScoringPlugin")
    kernel.add_plugin(RankingTools(), plugin_name="RankingPlugin")

    if use_llm and has_groq_api_key():
        try:
            from openai import AsyncOpenAI
            from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion

            # Groq's OpenAI-compatible endpoint
            async_client = AsyncOpenAI(
                api_key=GROQ_API_KEY,
                base_url=GROQ_BASE_URL,
            )
            chat_service = OpenAIChatCompletion(
                ai_model_id=GROQ_MODEL,
                async_client=async_client,
                service_id="groq_chat",
            )
            kernel.add_service(chat_service)
        except Exception:
            pass

    return kernel


def format_bid_from_properties(bid_id: str, props: Dict[str, Any]) -> str:
    """Constructs standard tender bid text from user-specified property overrides."""
    vendor_name = props.get("vendor_name", bid_id)
    price = props.get("price", 100000)
    payment_terms = props.get("payment_terms", "Milestone payments net 30 days post acceptance")
    validity_date = props.get("validity_date", "2027-08-31")
    exp_years = props.get("years_of_experience", props.get("experience_years", 5))
    certs = props.get("certifications", ["ISO 9001"])
    if isinstance(certs, list):
        certs_str = ", ".join(certs)
    else:
        certs_str = str(certs)
    team_size = props.get("team_size", 15)
    similar_projects = props.get("similar_projects", 4)
    delivery_days = props.get("delivery_days", 30)
    submitted_docs = props.get("submitted_docs", props.get("documents", []))
    docs_lines = "\n".join(f"- {d}" for d in submitted_docs)

    return f"""BID SUBMISSION DETAILS
Bidder Name: {vendor_name}
Bid Reference: BID-{bid_id.upper()}-CUSTOM
Tender Reference: TDR-2026-CAMPUS-NET-019

1. Commercial Proposal
Total Quoted Price: {price} USD
Payment Terms: {payment_terms}
Bid Validity: Valid until {validity_date}

2. Technical Features & Capabilities
Years of Experience: {exp_years}
Quality & Security Certifications: {certs_str}
Technical Engineering Team Size: {team_size}
Similar Enterprise Network Projects: {similar_projects}
Committed Delivery Timeline: {delivery_days} days

3. Compliance Documents Submitted
{docs_lines}
"""


class TenderOrchestrator:
    """Coordinates multi-agent fan-out and fan-in procurement evaluation."""

    def __init__(
        self,
        tender_path: Optional[Path] = None,
        bids_dir: Optional[Path] = None,
        tie_margin: float = TIE_MARGIN,
        kernel: Any = None,
        use_semantic_kernel: bool = False,
        custom_weights: Optional[Dict[str, float]] = None,
        mandatory_documents: Optional[List[str]] = None,
        secondary_criterion: str = "delivery_days",
        custom_tender_text: Optional[str] = None,
        custom_bids: Optional[Dict[str, Any]] = None,
    ):
        self.tender_path = Path(tender_path) if tender_path else TENDER_PATH
        self.bids_dir = Path(bids_dir) if bids_dir else BIDS_DIR
        self.tie_margin = tie_margin if tie_margin is not None else TIE_MARGIN
        self.custom_weights = custom_weights
        self.mandatory_documents = mandatory_documents
        self.secondary_criterion = secondary_criterion or "delivery_days"
        self.custom_tender_text = custom_tender_text
        self.custom_bids = custom_bids

        if kernel is not None:
            self.kernel = kernel
        elif use_semantic_kernel:
            self.kernel = build_semantic_kernel()
        else:
            self.kernel = None

        # Initialize retriever and agents
        self.retriever = Retriever(corpus_path=self.tender_path)
        if self.custom_tender_text:
            self.retriever.index_text(self.custom_tender_text)

        self.criteria_agent = CriteriaAgent(retriever=self.retriever, kernel=self.kernel)
        self.compliance_agent = ComplianceAgent(kernel=self.kernel)
        self.technical_scorer = TechnicalScorer(kernel=self.kernel)
        self.commercial_scorer = CommercialScorer(kernel=self.kernel)
        self.award_manager = AwardManager(kernel=self.kernel)
        self.tiebreak_agent = TieBreakAgent(kernel=self.kernel)

    def load_bids(self, selected_bids: Optional[List[str]] = None) -> Dict[str, str]:
        """Loads bid files from disk, overlaid with any user custom bids."""
        bids_data: Dict[str, str] = {}
        if self.bids_dir.exists():
            bid_files = sorted(self.bids_dir.glob("*.txt"))
            for bf in bid_files:
                bid_id = bf.stem  # e.g. "bid_A"
                if selected_bids is None or bid_id in selected_bids:
                    with open(bf, "r", encoding="utf-8") as f:
                        bids_data[bid_id] = f.read()

        # Apply any custom bids or user overrides
        if self.custom_bids:
            for bid_id, bid_val in self.custom_bids.items():
                if selected_bids is not None and bid_id not in selected_bids:
                    continue
                if isinstance(bid_val, str):
                    bids_data[bid_id] = bid_val
                elif isinstance(bid_val, dict):
                    bids_data[bid_id] = format_bid_from_properties(bid_id, bid_val)

        return bids_data

    async def run(
        self,
        selected_bids: Optional[List[str]] = None,
        tender_id: str = "TDR-2026-CAMPUS-NET-019",
    ) -> Scorecard:
        """Executes the end-to-end multi-agent evaluation pipeline."""
        scorecard = Scorecard(tender_id=tender_id)
        run_id = scorecard.run_id

        await scorecard.record_event("Orchestrator", "pipeline_start", f"Initiated run {run_id} for tender {tender_id}")

        # 1. Run Criteria Agent (RAG)
        await self.criteria_agent.run(scorecard)

        # Apply custom criteria overrides if provided by user
        if self.custom_weights:
            tot = sum(self.custom_weights.values())
            normalized_wts = {k: float(v) for k, v in self.custom_weights.items()}
            if abs(tot - 100.0) > 1e-4 and tot > 0:
                normalized_wts = {k: round((v / tot) * 100.0, 2) for k, v in normalized_wts.items()}
            scorecard.criteria["weights"] = normalized_wts
            await scorecard.record_event(
                "CriteriaAgent",
                "custom_weights_applied",
                f"Custom criteria weights applied: {normalized_wts}",
            )

        if self.mandatory_documents:
            scorecard.criteria["mandatory_documents"] = list(self.mandatory_documents)
            await scorecard.record_event(
                "ComplianceAgent",
                "custom_mandatory_docs_applied",
                f"Custom mandatory compliance documents: {self.mandatory_documents}",
            )

        # Load bids to evaluate
        bids_raw = self.load_bids(selected_bids=selected_bids)
        if not bids_raw:
            await scorecard.record_event("Orchestrator", "pipeline_warning", "No bids found to evaluate.")
            return scorecard

        # Initialize bids in scorecard
        for bid_id, text in bids_raw.items():
            scorecard.init_bid(bid_id)

        # 2. Fan-Out: Run scorers concurrently per bid with asyncio.gather
        async def evaluate_single_bid(bid_id: str, bid_text: str):
            # Run compliance check
            comp_res = await self.compliance_agent.evaluate_bid(
                bid_id=bid_id, bid_text=bid_text, scorecard=scorecard
            )
            # Run technical scoring
            tech_res = await self.technical_scorer.score_bid(
                bid_id=bid_id, bid_text=bid_text, scorecard=scorecard
            )
            # Initial commercial scoring pass (extracts price and checks payment terms)
            comm_res = await self.commercial_scorer.score_bid(
                bid_id=bid_id, bid_text=bid_text, scorecard=scorecard
            )
            return bid_id, comp_res, tech_res, comm_res

        # Concurrently execute evaluation across all bids
        await asyncio.gather(*(evaluate_single_bid(b_id, text) for b_id, text in bids_raw.items()))

        # Normalize commercial scores across all compliant bids based on the lowest compliant price
        await self.commercial_scorer.update_all_commercial_scores(scorecard=scorecard)

        # 3. Fan-In: Award Manager aggregates scores, applies weights, and ranks
        await self.award_manager.aggregate_and_rank(scorecard=scorecard)

        # 4. Tie-Break Agent check and resolution
        await self.tiebreak_agent.evaluate_and_resolve(
            scorecard=scorecard,
            margin=self.tie_margin,
            secondary_criterion=self.secondary_criterion,
        )

        # 5. Award Manager generates winning recommendation and weighted justification
        await self.award_manager.generate_award_recommendation(scorecard=scorecard)

        await scorecard.record_event("Orchestrator", "pipeline_complete", f"Winner selected: {scorecard.winner}")

        # 6. Write final outputs
        self.generate_report(scorecard, output_path=REPORT_OUTPUT_PATH)
        scorecard.save_json(output_path=SCORECARD_OUTPUT_PATH)

        return scorecard

        return scorecard

    def generate_report(self, scorecard: Scorecard, output_path: Path = REPORT_OUTPUT_PATH) -> str:
        """Constructs an executive Markdown report and writes to output/report.md."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            f"# Tender Evaluation Report: {scorecard.tender_id}",
            f"**Run ID**: `{scorecard.run_id}`  ",
            f"**Evaluation Timestamp**: `{datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}`  ",
            f"**Framework**: Semantic Kernel Multi-Agent Pipeline (Fan-Out / Fan-In)  ",
            "",
            "## 1. Executive Summary & Award Recommendation",
            f"- **Recommended Winner**: **{scorecard.winner}**",
            f"- **Tie-Break Applied**: `{'Yes' if scorecard.tie_break_applied else 'No'}`",
            "",
            "### Award Justification",
            f"{scorecard.justification}",
            "",
            "## 2. Evaluation Criteria & Weights (RAG Extracted)",
            "| Criterion | Weight (%) | Kind | Cited Clauses |",
            "|---|---|---|---|",
        ]

        weights = scorecard.criteria.get("weights", {})
        cited = ", ".join(scorecard.criteria.get("cited_clauses", []))
        for crit, wt in weights.items():
            lines.append(f"| {crit.capitalize()} | {wt:.1f}% | Evaluated | {cited} |")

        lines.extend([
            "",
            f"**Mandatory Compliance Documents**: {', '.join(scorecard.criteria.get('mandatory_documents', []))}",
            "",
            "## 3. Scorecard & Comparative Vendor Ranking",
            "| Rank | Bid ID | Vendor Name | Technical (40) | Commercial (30) | Experience (20) | Delivery (10) | Total Score | Status |",
            "|---|---|---|---|---|---|---|---|---|",
        ])

        # Sort bids: ranked compliant first by rank, then disqualified
        compliant_bids = [b for b in scorecard.bids.values() if not b.get("disqualified", False)]
        compliant_bids.sort(key=lambda x: x.get("rank") or 999)

        disqualified_bids = [b for b in scorecard.bids.values() if b.get("disqualified", False)]

        for b in compliant_bids:
            scores = b.get("scores", {})
            lines.append(
                f"| {b.get('rank')} | `{b.get('bid_id')}` | {b.get('vendor_name')} | "
                f"{scores.get('technical', 0.0):.2f} | {scores.get('commercial', 0.0):.2f} | "
                f"{scores.get('experience', 0.0):.2f} | {scores.get('delivery', 0.0):.2f} | "
                f"**{b.get('total', 0.0):.2f}** | Compliant |"
            )

        for b in disqualified_bids:
            scores = b.get("scores", {})
            reason = b.get("disqualification_reason") or "Failed mandatory compliance"
            lines.append(
                f"| - | `{b.get('bid_id')}` | {b.get('vendor_name')} | "
                f"{scores.get('technical', 0.0):.2f} | - | "
                f"{scores.get('experience', 0.0):.2f} | {scores.get('delivery', 0.0):.2f} | "
                f"0.00 | **Disqualified**: {reason} |"
            )

        lines.extend([
            "",
            "## 4. Multi-Agent Audit Event Trace",
            "| Timestamp | Agent | Action | Detail |",
            "|---|---|---|---|",
        ])

        for evt in scorecard.events:
            lines.append(f"| `{evt['timestamp']}` | **{evt['agent']}** | `{evt['action']}` | {evt['detail']} |")

        report_content = "\n".join(lines) + "\n"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        return report_content


async def run_tender_evaluation(
    selected_bids: Optional[List[str]] = None,
    print_trace: bool = True,
    use_semantic_kernel: bool = False,
    custom_weights: Optional[Dict[str, float]] = None,
    mandatory_documents: Optional[List[str]] = None,
    tie_margin: Optional[float] = None,
    secondary_criterion: Optional[str] = None,
    custom_tender_text: Optional[str] = None,
    custom_bids: Optional[Dict[str, Any]] = None,
) -> Scorecard:
    """Convenience functional runner for external callers, tests, and CLI."""
    orchestrator = TenderOrchestrator(
        use_semantic_kernel=use_semantic_kernel,
        tie_margin=tie_margin if tie_margin is not None else TIE_MARGIN,
        custom_weights=custom_weights,
        mandatory_documents=mandatory_documents,
        secondary_criterion=secondary_criterion or "delivery_days",
        custom_tender_text=custom_tender_text,
        custom_bids=custom_bids,
    )
    scorecard = await orchestrator.run(selected_bids=selected_bids)

    if print_trace:
        print("\n" + "=" * 80)
        print("TENDER EVALUATION MULTI-AGENT EXECUTION TRACE")
        print("=" * 80)
        for evt in scorecard.events:
            print(f"[{evt['timestamp']}] [{evt['agent']}] {evt['action'].upper()}: {evt['detail']}")
        print("=" * 80)
        print(f"RECOMMENDED WINNER: {scorecard.winner}")
        print(f"TIE BREAK APPLIED: {scorecard.tie_break_applied}")
        print("-" * 80)
        print(scorecard.justification)
        print("=" * 80 + "\n")

    return scorecard


if __name__ == "__main__":
    asyncio.run(run_tender_evaluation())
