"""Helper script to construct demo.ipynb with comprehensive markdown and code cells."""

import nbformat as nbf

nb = nbf.v4.new_notebook()

cells = []

# Title & Overview
cells.append(nbf.v4.new_markdown_cell(
"""# BidWise: Multi-Agent Tender and Procurement Evaluation System
**Course**: CSE476 (Task 2, Group 19)  
**Framework**: Semantic Kernel (Python)  
**Architecture**: Fan-Out / Fan-In Parallel Bid Scoring  

This notebook demonstrates the complete end-to-end evaluation of vendor bids against a campus network infrastructure tender:
1. **Criteria Agent (RAG)**: Dynamically retrieves evaluation criteria, weights, and compliance rules from `data/tender.txt`.
2. **Fan-Out Scoring (Concurrent)**: Evaluates bids concurrently across Compliance, Technical, and Commercial agents.
3. **Fan-In Award Manager**: Normalizes commercial scores, aggregates weighted totals, and ranks compliant bids.
4. **Tie-Break Agent**: Automatically resolves near-ties (within 2.0 margin) using delivery timeline secondary criterion.
5. **Report & Audit Log**: Generates formal justification report and verifies append-only audit trail in `logs/run_log.jsonl`.
"""
))

# Setup and Imports
cells.append(nbf.v4.new_code_cell(
"""import asyncio
from IPython.display import display, Markdown

from config import GROQ_MODEL, USE_LLM, has_groq_api_key
from orchestrator import TenderOrchestrator, run_tender_evaluation
from logs.logger import default_logger

llm_status = f"Groq LPU Acceleration ({GROQ_MODEL})" if (USE_LLM and has_groq_api_key()) else "Offline Fallback Mode (Deterministic)"
print("Environment and dependencies initialized successfully.")
print(f"Active LLM Service: {llm_status}")
"""
))

# Section 1: Run Evaluation
cells.append(nbf.v4.new_markdown_cell(
"""## 1. Execute Multi-Agent Evaluation Pipeline
We invoke the orchestrator with Semantic Kernel plugin architecture. All agents coordinate over the shared thread-safe `Scorecard`.
"""
))

cells.append(nbf.v4.new_code_cell(
"""# Execute end-to-end evaluation
scorecard = await run_tender_evaluation(print_trace=False, use_semantic_kernel=True)

print(f"Run ID: {scorecard.run_id}")
print(f"Tender Reference: {scorecard.tender_id}")
print(f"Total Bids Processed: {len(scorecard.bids)}")
"""
))

# Section 2: Criteria Extraction
cells.append(nbf.v4.new_markdown_cell(
"""## 2. RAG Criteria & Weights Retrieval
The Criteria Agent queries the in-memory retriever against the tender document clauses.
"""
))

cells.append(nbf.v4.new_code_cell(
"""criteria_md = [
    "### RAG-Extracted Tender Specifications",
    f"- **Tender ID**: `{scorecard.tender_id}`",
    f"- **Cited Clauses**: {', '.join(scorecard.criteria.get('cited_clauses', []))}",
    f"- **Weights Normalized**: `{'Yes' if scorecard.criteria.get('weight_normalized') else 'No (Already 100%)'}`",
    "",
    "| Criterion | Weight (%) | Kind | Description |",
    "|---|---|---|---|",
]

weights = scorecard.criteria.get("weights", {})
for crit, wt in weights.items():
    criteria_md.append(f"| {crit.capitalize()} | **{wt:.1f}%** | Rubric / Formula | Assessed per bid |")

criteria_md.extend([
    "",
    f"**Mandatory Compliance Documents**: {', '.join(scorecard.criteria.get('mandatory_documents', []))}"
])

display(Markdown("\\n".join(criteria_md)))
"""
))

# Section 3: Comparative Scorecard Table
cells.append(nbf.v4.new_markdown_cell(
"""## 3. Comparative Scorecard & Vendor Rankings
The Award Manager filters disqualified bids (such as Bid C, which lacked the mandatory EMD receipt) and calculates weighted totals for all compliant vendors.
"""
))

cells.append(nbf.v4.new_code_cell(
"""table_md = [
    "### Multi-Criteria Bid Evaluation Scorecard",
    "| Rank | Bid ID | Vendor Name | Quoted Price | Delivery | Technical (40) | Commercial (30) | Experience (20) | Delivery (10) | Total Score | Status |",
    "|---|---|---|---|---|---|---|---|---|---|---|",
]

# Sort compliant bids by rank, followed by disqualified bids
compliant_bids = sorted(
    [b for b in scorecard.bids.values() if not b.get("disqualified", False)],
    key=lambda x: x.get("rank") or 999
)
disqualified_bids = [b for b in scorecard.bids.values() if b.get("disqualified", False)]

for b in compliant_bids:
    s = b.get("scores", {})
    price_str = f"${b.get('price'):,}" if b.get('price') else "N/A"
    table_md.append(
        f"| **{b.get('rank')}** | `{b['bid_id']}` | {b.get('vendor_name')} | {price_str} | {b.get('delivery_days')} days | "
        f"{s.get('technical', 0.0):.2f} | {s.get('commercial', 0.0):.2f} | {s.get('experience', 0.0):.2f} | "
        f"{s.get('delivery', 0.0):.2f} | **{b.get('total', 0.0):.2f}** | Compliant |"
    )

for b in disqualified_bids:
    s = b.get("scores", {})
    price_str = f"${b.get('price'):,}" if b.get('price') else "N/A"
    reason = b.get("disqualification_reason") or "Failed compliance"
    table_md.append(
        f"| - | `{b['bid_id']}` | {b.get('vendor_name')} | {price_str} | {b.get('delivery_days')} days | "
        f"{s.get('technical', 0.0):.2f} | - | {s.get('experience', 0.0):.2f} | {s.get('delivery', 0.0):.2f} | "
        f"0.00 | **Disqualified**: {reason} |"
    )

display(Markdown("\\n".join(table_md)))
"""
))

# Section 4: Award & Justification
cells.append(nbf.v4.new_markdown_cell(
"""## 4. Winning Award Recommendation & Justification
"""
))

cells.append(nbf.v4.new_code_cell(
"""award_md = f\"\"\"### Contract Award Decision
- **Winning Vendor**: **{scorecard.winner}**
- **Tie-Break Invoked**: `{'Yes (Secondary Criterion Applied)' if scorecard.tie_break_applied else 'No'}`

#### Official Recommendation Text
{scorecard.justification}
\"\"\"
display(Markdown(award_md))
"""
))

# Section 5: Multi-Agent Trace
cells.append(nbf.v4.new_markdown_cell(
"""## 5. Multi-Agent Execution Trace
Ordered sequence of actions taken by agents communicating through the shared `Scorecard`.
"""
))

cells.append(nbf.v4.new_code_cell(
"""trace_md = [
    "### Chronological Multi-Agent Trace",
    "| Timestamp | Agent | Action | Detail |",
    "|---|---|---|---|",
]

for evt in scorecard.events:
    trace_md.append(f"| `{evt['timestamp']}` | **{evt['agent']}** | `{evt['action']}` | {evt['detail']} |")

display(Markdown("\\n".join(trace_md)))
"""
))

# Section 6: Append-Only Audit Log
cells.append(nbf.v4.new_markdown_cell(
"""## 6. Immutable Append-Only Audit Log (`logs/run_log.jsonl`)
Verification of the append-only JSONL run log containing structured tool invocation summaries.
"""
))

cells.append(nbf.v4.new_code_cell(
"""records = default_logger.get_records(run_id=scorecard.run_id)
print(f"Total audit records logged for run {scorecard.run_id}: {len(records)}\\n")

log_md = [
    "| Timestamp | Agent | Tool | Input Summary | Output Summary |",
    "|---|---|---|---|---|",
]

for rec in records:
    log_md.append(f"| `{rec['ts']}` | **{rec['agent']}** | `{rec['tool']}` | {rec['input_summary']} | {rec['output_summary']} |")

display(Markdown("\\n".join(log_md)))
"""
))

nb.cells = cells

with open("demo.ipynb", "w", encoding="utf-8") as f:
    nbf.write(nb, f)

print("demo.ipynb created successfully.")
