# Viva Preparation Notes: BidWise Multi-Agent Tender Evaluation

**Course**: CSE476 | **Task**: 2 | **Group**: 19  
**System**: BidWise Tender & Procurement Evaluation System  

---

## 1. Step-by-Step Data Flow Walkthrough

1. **Corpus & Bid Ingestion**: The orchestrator initializes the central `Scorecard` with tender reference `TDR-2026-CAMPUS-NET-019` and loads vendor submissions from `data/bids/`.
2. **Phase 1: Dynamic Criteria Extraction (RAG)**:
   - `CriteriaAgent` queries the in-memory `Retriever` for evaluation weights, rubric guidelines, and mandatory documents.
   - `parse_weights` parses and normalizes weights to sum to 100%. `parse_mandatory_docs` extracts required certificates.
   - Slices are saved into `scorecard.criteria`.
3. **Phase 2: Concurrent Fan-Out Bid Evaluation**:
   - For each bid, `asyncio.gather` invokes `ComplianceAgent`, `TechnicalScorer`, and `CommercialScorer` in parallel.
   - `ComplianceAgent` verifies mandatory documents and dates. If any mandatory document (e.g. EMD Receipt for Bid C) is absent, the bid is marked disqualified.
   - `TechnicalScorer` extracts features (certifications, team size, past projects, experience) and calculates scores against `data/rubric.json`.
   - `CommercialScorer` checks payment terms and records quoted prices.
   - Once all compliant prices are gathered, `CommercialScorer` executes cross-bid normalization: $\text{Score} = (\text{Lowest Compliant Price} / \text{Price}) \times 30$.
4. **Phase 3: Fan-In Aggregation & Ranking**:
   - `AwardManager` reads the scorecard, excludes disqualified bids, applies criteria weights to obtain totals, and ranks compliant bids.
5. **Phase 4: Margin Tie-Breaking**:
   - `TieBreakAgent` evaluates whether the score difference between Rank 1 and Rank 2 is $\le \text{TIE\_MARGIN}$ (2.0 points).
   - If a tie exists (e.g., Bid D: 92.09 vs. Bid A: 91.00, gap = 1.09), it applies the secondary criterion (Delivery Timeline: shorter delivery wins) and updates rankings.
6. **Phase 5: Award Recommendation & Reporting**:
   - `AwardManager` formulates the final award and justification citing per-criterion scores and weights.
   - Final outputs are saved to `output/report.md` and `output/scorecard.json`.

---

## 2. Key Architectural Decisions & Rationale

### Why is each agent in a separate module?
To enforce **Single Responsibility Principle (SRP)** and modularity. In procurement systems, legal compliance, technical evaluation, commercial auditing, and executive awards represent distinct administrative roles with separate validation boundaries. Decoupling them allows individual agents and tools to be tested, versioned, or replaced independently without side effects.

### Where is the LLM used and NOT used, and why?
- **NOT Used for Scoring/Math**: Scoring against rubrics, commercial inverse-price calculations, date checks, and tie-break margins use **deterministic Python functions**. This guarantees reproducibility, eliminates hallucinations, prevents prompt injection from malicious bids, and adheres to strict procurement compliance laws.
- **Used for Natural Language Synthesis**: The LLM is used in `AwardManager` for drafting formal, executive-ready award justifications powered by **Groq (`openai/gpt-oss-120b`)** through Semantic Kernel. When running offline (default), a deterministic template guarantees 100% test reliability.

### How is Groq integrated with Semantic Kernel?
Groq exposes an OpenAI-compatible REST API at `https://api.groq.com/openai/v1`. Semantic Kernel's `OpenAIChatCompletion` connector is initialized with an `openai.AsyncOpenAI` client pointing to Groq's base URL and credentials configured in `.env`. Both the Semantic Kernel service interface and direct `AsyncGroq` client are supported.

### How is the shared state protected during parallel writes?
`Scorecard` encapsulates an `asyncio.Lock`. When parallel tasks spawned by `asyncio.gather` write their respective criteria slices (`update_technical_slice`, `update_compliance_slice`, `update_commercial_slice`), the lock guarantees atomic, thread-safe updates to the dictionary and prevents race conditions.

### How does the tie-break work?
`TieBreakAgent` invokes `detect_ties` across the top two compliant bids. If $|\text{Total}_1 - \text{Total}_2| \le 2.0$, it applies `apply_secondary_criterion`, prioritizing the shorter delivery timeline. The tie-break flag `tie_break_applied = True` is permanently recorded in the scorecard and audit log.

---

## 3. Anticipated Viva Questions & Model Answers

### Q1: What makes your system an agentic architecture rather than a simple script?
> **Answer**: The system uses Semantic Kernel agents possessing dedicated roles, autonomous decision-making over tools, structured message passing, dynamic RAG memory rather than hardcoded logic, and an append-only audit trail logging tool interactions.

### Q2: What happens if a vendor bids the lowest price but fails compliance?
> **Answer**: In our test suite (Scenario 2), Bid C submitted a low price and high technical specs but lacked the mandatory EMD receipt. The `ComplianceAgent` immediately disqualified it. Disqualified bids are preserved in the scorecard with explicit failure reasons but are strictly excluded from financial normalization and ranking.

### Q3: How do you handle non-standard criteria weights in the tender?
> **Answer**: In Scenario 4, if criteria weights in the tender document sum to 80% or 125%, `parse_weights` detects the variance, normalizes all weights proportionally to 100.0, and writes an audit warning to `logs/run_log.jsonl`.

### Q4: How is your system guaranteed to run without an active OpenAI API key?
> **Answer**: All tools are pure Python functions. In-memory TF-IDF vectorization replaces external embedding APIs, and deterministic templating replaces LLM text generation. Tests and notebooks run entirely offline with zero external network calls.
