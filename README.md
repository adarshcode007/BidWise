# BidWise: Multi-Agent Tender & Procurement Evaluation System

**Course**: CSE476 | **Task**: 2 | **Group**: 19  
**Framework**: Semantic Kernel (Python) | **Architecture**: Fan-Out / Fan-In Parallel Bid Scoring  

---

## 1. Overview & Goal

BidWise is an autonomous multi-agent procurement evaluation system built with **Semantic Kernel**. It ingests a tender specification document and multiple vendor proposals, dynamically extracts evaluation criteria using Retrieval-Augmented Generation (RAG), scores bids concurrently across specialized agents, resolves margin ties, and produces an auditable, ranked scorecard with winning award justifications.

The system runs **offline-first** by default (zero external API keys required), guaranteeing deterministic evaluation while supporting optional LLM generation via configuration.

---

## 2. Agent Roster & Tool Mapping

The system distributes responsibilities across 6 specialized agents. Every agent executes at least 2 real tools implemented as pure Python functions and decorated as Semantic Kernel `@kernel_function` plugins:

| # | Agent (`agents/`) | Role | Tools (`tools/`) |
|---|---|---|---|
| 1 | `criteria_agent.py` | Retrieves tender criteria, weights, and compliance checklists via RAG | `retrieve_clauses(query)`, `parse_weights(text)`, `parse_mandatory_docs(text)` |
| 2 | `compliance_agent.py` | Validates mandatory certificates and validity dates; flags disqualifications | `check_required_docs(bid_text, req)`, `check_validity_dates(bid_text, as_of)` |
| 3 | `technical_scorer.py` | Parses quantitative technical specifications and scores against the rubric | `extract_bid_features(bid_text)`, `score_against_rubric(features, rubric)` |
| 4 | `commercial_scorer.py` | Evaluates pricing against lowest compliant bid and validates payment terms | `normalize_price(prices, max_marks)`, `check_payment_terms(bid_text)` |
| 5 | `award_manager.py` | Aggregates weighted scores, filters disqualified bids, ranks, and justifies award | `apply_weights(scores, weights)`, `rank_bids(totals)` |
| 6 | `tiebreak_agent.py` | Identifies ties within margin ($\le 2.0$ pts) and resolves via secondary criterion | `detect_ties(ranked, margin)`, `apply_secondary_criterion(bids, criterion)` |

---

## 3. Architecture & Why Fan-Out / Fan-In Fits

```
   [Tender Document] ──> [Criteria Agent (RAG)] ──> [Shared Scorecard (asyncio.Lock)]
                                                              │
             ┌───────────────────────── Fan-Out ──────────────┴─────────────────────────┐
             ▼                                  ▼                                       ▼
    [Bid A: Comp/Tech/Comm]            [Bid B: Comp/Tech/Comm]                 [Bid D: Comp/Tech/Comm]
             │                                  │                                       │
             └───────────────────────── Fan-In ─┬───────────────────────────────────────┘
                                                ▼
                                      [Award Manager]
                                                │
                                    (Margin <= 2.0 pts?)
                                       ├── Yes ──> [Tie-Break Agent (Delivery)]
                                       └── No  ──> [Final Award & Justification]
```

### Why Fan-Out / Fan-In Fits
Vendor bids are strictly independent. Running compliance, technical rubric scoring, and commercial extraction concurrently per bid (**Fan-Out** via `asyncio.gather`) eliminates bottlenecks and maximizes throughput. Once per-bid slices are recorded in the central thread-safe `Scorecard`, the **Award Manager** performs the **Fan-In** phase to execute cross-bid commercial price normalization, filter disqualified entries, calculate weighted totals, and invoke tie-breaking.

---

## 4. Retrieval (RAG) & Shared State

- **Retrieval (`rag/retriever.py`)**: The tender corpus (`data/tender.txt`) is indexed into numbered clause chunks (`Clause 1` through `Clause 7`). In offline mode, an in-memory `TfidfVectorizer` computes cosine similarity over clause chunks to extract criteria, weights, and mandatory compliance lists dynamically without hardcoding.
- **Shared State (`state/scorecard.py`)**: A single, thread-safe `Scorecard` dataclass maintains bid slices, timestamps, compliance flags, totals, and winner state. Write access is protected by an `asyncio.Lock`.
- **Append-Only Run Log (`logs/run_log.jsonl`)**: Every agent start/finish and tool invocation appends an immutable JSON record (`mode="a"`).

---

## 5. Handled Failures & Edge Cases

1. **Mandatory Document Disqualification (Bid C)**: Bid C submitted strong technical credentials but omitted the mandatory *EMD Receipt*. The `ComplianceAgent` immediately disqualified Bid C, excluded it from financial ranking, and recorded the reason in the scorecard.
2. **Weight Normalization**: If tender criteria weights do not sum to 100%, `parse_weights` detects the mismatch, normalizes all weights proportionally to 100.0, and logs an audit warning.
3. **Margin Tie-Breaking (Bid A vs. Bid D)**: Bid D scored 92.09 and Bid A scored 91.00 ($\Delta = 1.09 \le 2.0$). The `TieBreakAgent` resolved the tie in favor of Bid D based on its superior delivery timeline (20 days vs. 45 days).

---

## 6. Groq API & LLM Integration

BidWise integrates **Groq's ultra-fast LPU inference engine** via Semantic Kernel's OpenAI connector (`OpenAIChatCompletion` targeting `https://api.groq.com/openai/v1`).

### Configuring `.env`:
Create or edit `.env` in the repository root:
```env
# Groq API Configuration
GROQ_API_KEY=gsk_your_actual_key_here
GROQ_MODEL=openai/gpt-oss-120b
GROQ_BASE_URL=https://api.groq.com/openai/v1

# Enable LLM generation (set to true to use Groq)
USE_LLM=true
OFFLINE_MODE=false
```

- When `GROQ_API_KEY` is configured, `AwardManager` synthesizes comprehensive, executive procurement justifications dynamically using `openai/gpt-oss-120b`.
- When offline or when no key is set, the system seamlessly uses deterministic, audit-compliant templating so tests and benchmarks never fail.

---

## 7. Quickstart & Verification

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure your Groq API key in .env (optional for tests)
# cp .env.example .env

# 3. Run automated test suite (all 12 unit and scenario tests pass offline)
pytest tests/ -v

# 4. Start the Web Dashboard and REST API on port 6000
python app.py --port 6000
# or with live reload:
uvicorn app:app --host 0.0.0.0 --port 6000 --reload

# 5. Execute the CLI pipeline
python orchestrator.py

# 6. Execute the interactive demonstration notebook
jupyter nbconvert --execute --to notebook --inplace demo.ipynb
```
