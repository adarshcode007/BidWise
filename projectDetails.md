# PROJECT BRIEF: Tender and Procurement Evaluation System (CSE476, Task 2, Group 19)

You are a coding agent. Build the project described below end to end, in the order given in "Build order". Deadline is today, so favour a working, tested, simple system over a clever one. Do not ask questions; where something is unspecified, pick the simplest option and note it in the README.

## 1. Goal

A multi-agent system that evaluates several vendor bids against a tender's criteria and recommends a winning bid with a scorecard.

Coordination architecture: **fan-out / fan-in parallel bid scoring**. A Criteria Agent runs first, scorers run in parallel per bid (fan-out), and the Award Manager collects everything (fan-in).

Framework: **Semantic Kernel (Python, `semantic-kernel` package)**. Each agent is a separate module with one clear role. Tools are plain Python functions exposed to the kernel as plugins (`@kernel_function`), and also directly callable so tests run without an LLM.

## 2. Hard requirements (graded, do not skip)

1. At least 4 agents, each in its own module with one clear role (this project has 6 including the add-on).
2. Every working agent calls at least 2 real tools written as plain Python functions.
3. RAG: the Criteria Agent must take criteria and weights from the provided tender document via retrieval, not hardcoded.
4. Shared state: a single `Scorecard` object that every scorer reads and writes.
5. Built on Semantic Kernel.
6. Deliverables:
   - source code, one module per agent
   - `README.md` of at most 2 pages (agent roster, architecture and why it fits, tools per agent, what the retrieval/memory holds, one failure handled)
   - demo notebook `demo.ipynb` that runs end to end and prints the multi-agent trace
   - architecture diagram (`docs/architecture.png` plus its source)
   - append-only run log `logs/run_log.jsonl`
   - test file covering at least 3 scenarios
7. The system must output: a ranked scorecard across all bids and a recommended winner with a weighted justification.

## 3. Agents and tools

All tools are deterministic plain Python functions in `tools/`. The LLM is used only for natural-language steps (criteria extraction phrasing, justification text). Every agent must also work in **offline mode** (no API key) using a deterministic fallback, so tests and the demo never fail for lack of a key.

| # | Agent (module) | Role | Tools (min 2 each) |
|---|---|---|---|
| 1 | `criteria_agent.py` | Retrieves evaluation criteria and weights from the tender document (RAG) | `retrieve_clauses(query)`, `parse_weights(text)` |
| 2 | `technical_scorer.py` | Scores one bid on the technical criteria (one run per bid, in parallel) | `extract_bid_features(bid_text)`, `score_against_rubric(features, rubric)` |
| 3 | `commercial_scorer.py` | Scores price and commercial terms | `normalize_price(prices)`, `check_payment_terms(bid_text)` |
| 4 | `compliance_agent.py` | Checks mandatory documents and validity; can disqualify a bid | `check_required_docs(bid_text, required)`, `check_validity_dates(bid_text, as_of)` |
| 5 | `award_manager.py` | Fans in, applies weights, ranks, recommends the winner with justification | `apply_weights(scores, weights)`, `rank_bids(totals)` |
| 6 | `tiebreak_agent.py` | Add-on: resolves bids within the margin using a secondary criterion | `detect_ties(ranked, margin)`, `apply_secondary_criterion(bids, criterion)` |

Notes:
- Compliance runs before or alongside scoring; a disqualified bid is excluded from ranking but kept in the scorecard with the reason.
- Commercial scoring rule: lowest compliant price gets full marks, others get `lowest / price * max_marks`.
- Technical scoring: keyword and feature matching against a rubric defined in `data/rubric.json` (for example experience years, certifications, team size, similar projects). Document the rule.
- Tie-break: if the top bids are within `TIE_MARGIN = 2.0` points, apply the secondary criterion (shorter delivery time wins). Record that the tie-break fired.

## 4. Shared state

`state/scorecard.py` defines a dataclass `Scorecard` holding:
- `tender_id`, `criteria` (name, weight, kind: technical/commercial/compliance)
- `bids`: per-bid dict with `scores` (per criterion), `compliance` (pass/fail + reasons), `disqualified` (bool + reason), `total`, `rank`
- `events`: ordered list of `{timestamp, agent, action, detail}`
- `winner`, `justification`, `tie_break_applied`

Rules:
- Every agent receives the same `Scorecard` instance, reads from it, and writes its results into it.
- Scorers write only their own slice (their criteria) for each bid. Use a lock (`threading.Lock` or `asyncio.Lock`) so parallel writes are safe.
- Every write also appends to `logs/run_log.jsonl` (see Logging).

## 5. Orchestration (fan-out / fan-in)

`orchestrator.py`:
1. Load tender and bids. Run the Criteria Agent (RAG) and populate `scorecard.criteria`.
2. **Fan-out:** for each bid, run the Compliance Agent, Technical Scorer and Commercial Scorer concurrently with `asyncio.gather`.
3. **Fan-in:** the Award Manager reads the full Scorecard, excludes disqualified bids, applies weights, and ranks.
4. If the top bids are within the margin, call the Tie-Break Agent and re-rank.
5. The Award Manager writes the winner and a weighted justification (LLM-written when a key is present, a template when offline). The justification must cite the per-criterion scores and weights.
6. Print the trace and write the final report to `output/report.md` and `output/scorecard.json`.

## 6. Retrieval (RAG)

- Corpus: `data/tender.txt`, split into clause-sized chunks (by numbered clause).
- Use a simple in-memory retriever. Prefer embeddings if an API key is present; otherwise TF-IDF with scikit-learn. Both must sit behind one `Retriever` interface in `rag/retriever.py`.
- The Criteria Agent queries it for "evaluation criteria", "weights", and "mandatory documents", and returns the cited clause ids with the extracted values.
- Weights must sum to 100. If they do not, the Criteria Agent normalizes them and logs a warning (this is a handled failure).

## 7. Data to create (synthetic)

`data/tender.txt`: tender for "Supply and installation of a campus network". Include:
- Clause 4: Evaluation criteria and weights. Technical 40, Commercial/Price 30, Experience 20, Delivery 10.
- Clause 5: Mandatory documents: registration certificate, tax clearance, EMD receipt, experience certificate.
- Clause 6: Technical rubric expectations.
- Clause 7: Tie-break rule: delivery time (shorter wins) if score gap is under 2 points.

`data/bids/bid_A.txt` to `bid_D.txt`, each with price, delivery days, years of experience, certifications, team size, payment terms and a list of documents submitted.
- Bid A: strong technical, mid price, compliant.
- Bid B: lowest price, average technical, compliant.
- Bid C: **missing the EMD receipt, so it is disqualified** (this is the "one failure handled").
- Bid D: scores within 2 points of the leader, with a shorter delivery time, so the **tie-break fires**.

`data/rubric.json`: technical rubric with max marks per feature.

Tune the numbers so the three scenarios below hold deterministically.

## 8. Logging

`logs/run_log.jsonl` is **append-only**: open with mode `"a"`, never truncate or rewrite, one JSON object per line: `{ts, run_id, agent, tool, input_summary, output_summary}`. Log every agent start/finish and every tool call. Provide `logs/logger.py` and a test proving the file is only ever appended to.

## 9. Tests (`tests/test_scenarios.py`, pytest)

Tests run offline (no API key). Minimum scenarios:
1. **Clean winner:** with compliant bids only, the expected bid ranks first and the totals match hand-computed values.
2. **Disqualification:** Bid C is disqualified for the missing EMD receipt, is absent from the ranking, and the reason is in the scorecard.
3. **Tie-break:** a near-tie triggers the Tie-Break Agent, the shorter-delivery bid wins, and `tie_break_applied` is true.
4. Extra if time allows: weights not summing to 100 get normalized; run log is append-only; `parse_weights` and `normalize_price` unit tests.

## 10. Repository layout

```
tender-eval/
  README.md
  requirements.txt
  config.py                 # model lane, TIE_MARGIN, paths; reads env vars
  orchestrator.py
  agents/ criteria_agent.py technical_scorer.py commercial_scorer.py
          compliance_agent.py award_manager.py tiebreak_agent.py
  tools/  rag_tools.py scoring_tools.py compliance_tools.py ranking_tools.py
  rag/    retriever.py
  state/  scorecard.py
  logs/   logger.py  run_log.jsonl
  data/   tender.txt rubric.json bids/bid_A..D.txt
  docs/   architecture.mmd architecture.png
  output/ report.md scorecard.json
  tests/  test_scenarios.py
  demo.ipynb
```

## 11. Build order

1. Scaffold the repo, `requirements.txt` (semantic-kernel, scikit-learn, pytest, nbformat, jupyter), `config.py`.
2. Write synthetic data (section 7).
3. `Scorecard`, logger, retriever.
4. Tools (pure functions) plus unit tests for them.
5. Agents (offline-first), then the orchestrator.
6. Scenario tests (section 9). Make them pass.
7. Wire in the Semantic Kernel LLM path behind a config flag. The offline path must stay the default fallback.
8. `demo.ipynb`: runs the orchestrator, prints the agent-by-agent trace, the scorecard table, the winner and the justification.
9. Architecture diagram (Mermaid to PNG with `mmdc`): Criteria Agent, then fan-out to the three scorers per bid, then fan-in to the Award Manager, then the Tie-Break Agent, with the shared Scorecard and the run log shown.
10. README (at most 2 pages, about 600 words): agent roster, architecture and why fan-out/fan-in fits (bids are independent, so scoring parallelises, then one manager reconciles), tools per agent, what retrieval holds (tender clauses), the one failure handled (disqualified bid, plus weight normalization).
11. Final check: run `pytest`, run the notebook top to bottom with `jupyter nbconvert --execute`, confirm every deliverable in section 2 exists.

## 12. Viva support

Add `docs/VIVA_NOTES.md` (one page): data flow step by step, why each agent is separate, where the LLM is and is not used and why (determinism for scoring), how the shared state is protected during parallel writes, how the tie-break works, and likely questions with short answers.

## 13. Do not

- Do not build a single agent with many tools.
- Do not hardcode weights or criteria in agent code; they must come from the tender via RAG.
- Do not require an API key for tests or for the demo to run.
- Do not rewrite or truncate the run log.