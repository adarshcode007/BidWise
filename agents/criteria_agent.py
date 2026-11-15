"""Criteria Agent for BidWise tender evaluation system.

Extracts evaluation criteria, weights, and compliance rules from tender document via RAG.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import GROQ_API_KEY, GROQ_MODEL, USE_LLM, has_groq_api_key
from logs.logger import log_event
from rag.retriever import Retriever
from state.scorecard import Scorecard
from tools.rag_tools import RagTools, parse_mandatory_docs, parse_weights, retrieve_clauses


class CriteriaAgent:
    """Agent responsible for RAG retrieval of tender criteria and weights."""

    def __init__(self, retriever: Optional[Retriever] = None, kernel: Any = None):
        self.agent_name = "CriteriaAgent"
        self.retriever = retriever or Retriever()
        self.rag_tools = RagTools(self.retriever)
        self.kernel = kernel
        if self.kernel:
            self.kernel.add_plugin(self.rag_tools, plugin_name="RagPlugin")

    async def run(self, scorecard: Scorecard) -> Dict[str, Any]:
        """Executes RAG retrieval to extract criteria, weights, and mandatory documents."""
        run_id = scorecard.run_id
        log_event(
            run_id=run_id,
            agent=self.agent_name,
            tool="CriteriaAgent.run",
            input_summary="Querying tender corpus for criteria and weights",
            output_summary="Starting retrieval",
        )

        # 1. Retrieve criteria and weights clause
        clauses_weights = self.rag_tools.retrieve_clauses(query="evaluation criteria weights commercial technical", top_k=2)
        cited_clause_ids = [c["clause_id"] for c in clauses_weights]

        combined_text = "\n".join(c["full_text"] for c in clauses_weights)
        weights_parsed = self.rag_tools.parse_weights(combined_text)

        # 2. Retrieve mandatory compliance documents clause
        clauses_docs = self.rag_tools.retrieve_clauses(query="mandatory documents compliance requirements EMD receipt", top_k=1)
        cited_docs_clause_ids = [c["clause_id"] for c in clauses_docs]
        docs_text = "\n".join(c["full_text"] for c in clauses_docs)
        mandatory_docs = self.rag_tools.parse_mandatory_docs(docs_text)

        criteria_registry = {
            "tender_id": scorecard.tender_id,
            "weights": weights_parsed["weights"],
            "mandatory_documents": mandatory_docs,
            "cited_clauses": list(set(cited_clause_ids + cited_docs_clause_ids)),
            "weight_normalized": weights_parsed.get("normalized", False),
            "normalization_warning": weights_parsed.get("warning"),
        }

        # Update shared scorecard
        await scorecard.update_criteria(criteria_registry, agent=self.agent_name)

        log_event(
            run_id=run_id,
            agent=self.agent_name,
            tool="CriteriaAgent.run",
            input_summary=f"Extracted weights: {weights_parsed['weights']}",
            output_summary=f"Mandatory docs: {mandatory_docs}; Cited: {criteria_registry['cited_clauses']}",
        )

        return criteria_registry
