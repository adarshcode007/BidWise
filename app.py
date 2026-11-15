"""FastAPI Web Application and REST API for BidWise Multi-Agent Tender Evaluation.

Includes full interactive visualizer for multi-agent data exchange.
Run via:
    uvicorn app:app --host 0.0.0.0 --port 6000 --reload
or:
    python app.py --port 6000
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from config import (
    GROQ_MODEL,
    OUTPUT_DIR,
    REPORT_OUTPUT_PATH,
    SCORECARD_OUTPUT_PATH,
    USE_LLM,
    has_groq_api_key,
)
from logs.logger import default_logger
from orchestrator import run_tender_evaluation

app = FastAPI(
    title="BidWise Multi-Agent Tender Evaluation API",
    description="Autonomous Fan-Out / Fan-In multi-agent tender evaluation system powered by Semantic Kernel and Groq.",
    version="1.0.0",
)


@app.get("/api/health")
async def health_check():
    """System health check and LLM configuration status."""
    return {
        "status": "healthy",
        "llm_provider": "Groq",
        "model": GROQ_MODEL,
        "has_api_key": has_groq_api_key(),
        "use_llm": USE_LLM,
    }


@app.post("/api/evaluate")
async def evaluate_tender(selected_bids: Optional[List[str]] = None):
    """Executes the full multi-agent tender evaluation pipeline."""
    try:
        scorecard = await run_tender_evaluation(
            selected_bids=selected_bids,
            print_trace=False,
            use_semantic_kernel=True,
        )
        return scorecard.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scorecard")
async def get_latest_scorecard():
    """Retrieves the latest persisted evaluation scorecard."""
    if not SCORECARD_OUTPUT_PATH.exists():
        raise HTTPException(status_code=404, detail="No evaluation scorecard found. Run /api/evaluate first.")
    with open(SCORECARD_OUTPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


@app.get("/api/report")
async def get_latest_report():
    """Retrieves the Markdown evaluation report."""
    if not REPORT_OUTPUT_PATH.exists():
        raise HTTPException(status_code=404, detail="No evaluation report found. Run /api/evaluate first.")
    with open(REPORT_OUTPUT_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    return {"report_markdown": content}


@app.get("/api/logs")
async def get_audit_logs(run_id: Optional[str] = None):
    """Fetches records from the append-only audit run log."""
    records = default_logger.get_records(run_id=run_id)
    return {"count": len(records), "records": records}


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serves an interactive web dashboard with animated multi-agent dataflow visualizer."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>BidWise | Multi-Agent Dataflow Visualizer</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    .badge-pass { background-color: #dcfce7; color: #166534; border: 1px solid #86efac; }
    .badge-fail { background-color: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }
    .badge-winner { background-color: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }
    
    /* Flow Animations */
    @keyframes pulse-node {
      0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(79, 70, 229, 0.4); }
      70% { transform: scale(1.03); box-shadow: 0 0 0 10px rgba(79, 70, 229, 0); }
      100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(79, 70, 229, 0); }
    }
    .node-active {
      animation: pulse-node 1.8s infinite;
      border-color: #4f46e5 !important;
      background-color: #eef2ff !important;
    }
    .node-disq-active {
      animation: pulse-node 1.8s infinite;
      border-color: #e11d48 !important;
      background-color: #fff1f2 !important;
    }
    .flow-line {
      stroke-dasharray: 6;
      animation: dash 1.2s linear infinite;
    }
    @keyframes dash {
      to { stroke-dashoffset: -12; }
    }
  </style>
</head>
<body class="bg-slate-50 text-slate-800 min-h-screen">
  <!-- Navbar -->
  <header class="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-indigo-500 flex items-center justify-center text-white font-black text-xl shadow-md">
          <i class="fa-solid fa-network-wired"></i>
        </div>
        <div>
          <div class="flex items-center space-x-2">
            <h1 class="text-lg font-bold text-slate-900 tracking-tight">BidWise</h1>
            <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">Multi-Agent System</span>
          </div>
          <p class="text-xs text-slate-500">Autonomous Procurement Evaluation with Fan-Out / Fan-In Parallelism</p>
        </div>
      </div>
      <div class="flex items-center space-x-4">
        <span class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
          <span class="w-2 h-2 mr-1.5 bg-emerald-500 rounded-full animate-pulse"></span> Pipeline Active
        </span>
        <a href="/docs" target="_blank" class="text-xs font-semibold text-slate-600 hover:text-indigo-600 flex items-center space-x-1 transition">
          <span>API Docs</span> <i class="fa-solid fa-arrow-up-right-from-square text-[10px]"></i>
        </a>
        <button id="runBtn" onclick="runRealEvaluation()" class="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs px-4 py-2 rounded-lg shadow-sm transition flex items-center space-x-2">
          <i class="fa-solid fa-bolt"></i>
          <span>Run Live Pipeline</span>
        </button>
      </div>
    </div>
  </header>

  <!-- Main Container -->
  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">

    <!-- Winner Hero Banner -->
    <div id="winnerBanner" class="bg-white border border-amber-200/80 rounded-2xl p-6 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-6 transition-all">
      <div class="flex items-center space-x-4">
        <div class="w-14 h-14 rounded-2xl bg-gradient-to-tr from-amber-400 to-amber-300 flex items-center justify-center text-amber-900 text-2xl shadow-md">
          <i class="fa-solid fa-trophy"></i>
        </div>
        <div>
          <div class="flex items-center space-x-2">
            <span class="text-[11px] font-extrabold uppercase tracking-wider text-amber-800">Recommended Winner</span>
            <span id="tieBreakBadge" class="hidden px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-100 text-indigo-800 border border-indigo-200">Tie-Break Applied</span>
          </div>
          <h2 id="winnerName" class="text-2xl font-black text-slate-900 mt-0.5">--</h2>
          <p id="winnerScore" class="text-xs text-slate-600 font-medium">Weighted Score: --</p>
        </div>
      </div>
      <div class="w-full md:w-auto bg-amber-50/70 rounded-xl p-4 border border-amber-200/60 max-w-xl text-xs text-slate-700 leading-relaxed font-sans" id="justificationSummary">
        Click <b>Run Live Pipeline</b> to evaluate vendor bids and watch the agents pass data.
      </div>
    </div>

    <!-- VISUAL AGENT DATAFLOW STAGE -->
    <div class="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
        <div>
          <h2 class="text-base font-bold text-slate-900 flex items-center space-x-2">
            <i class="fa-solid fa-diagram-project text-indigo-600"></i>
            <span>Interactive Multi-Agent Dataflow Architecture</span>
          </h2>
          <p class="text-xs text-slate-500">Watch data packets transfer between autonomous agents and the shared Scorecard memory.</p>
        </div>
        
        <!-- Simulation & Playback Controls -->
        <div class="flex items-center space-x-2 bg-slate-100 p-1 rounded-xl">
          <button onclick="prevFlowStep()" class="p-1.5 px-3 rounded-lg hover:bg-white text-slate-600 font-bold text-xs transition shadow-sm">
            <i class="fa-solid fa-backward-step mr-1"></i> Prev
          </button>
          <button id="autoPlayBtn" onclick="toggleAutoPlay()" class="p-1.5 px-3 rounded-lg bg-indigo-600 text-white font-bold text-xs transition shadow-sm flex items-center space-x-1.5">
            <i id="playIcon" class="fa-solid fa-play"></i> <span id="playText">Auto Flow</span>
          </button>
          <button onclick="nextFlowStep()" class="p-1.5 px-3 rounded-lg hover:bg-white text-slate-600 font-bold text-xs transition shadow-sm">
            Next <i class="fa-solid fa-forward-step ml-1"></i>
          </button>
          <button onclick="resetFlow()" class="p-1.5 px-2.5 rounded-lg hover:bg-white text-slate-400 hover:text-slate-700 text-xs transition" title="Reset Flow">
            <i class="fa-solid fa-rotate-right"></i>
          </button>
        </div>
      </div>

      <!-- Diagram Stage Grid -->
      <div class="relative bg-gradient-to-b from-slate-900 via-slate-900 to-slate-950 rounded-2xl p-6 text-white overflow-hidden shadow-inner min-h-[380px]">
        <!-- Top Row: Input Corpus -> Criteria Agent -> Scorecard -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 relative z-10">
          
          <!-- Node: Tender Corpus -->
          <div id="v-tender" onclick="inspectNode('tender')" class="cursor-pointer bg-slate-800/90 border border-slate-700 rounded-xl p-4 hover:border-indigo-400 transition flex flex-col justify-between shadow-lg">
            <div class="flex items-center justify-between">
              <span class="text-[10px] uppercase font-bold text-indigo-400 tracking-wider">Input Corpus</span>
              <i class="fa-solid fa-file-contract text-slate-400"></i>
            </div>
            <div class="my-2">
              <h4 class="font-bold text-sm text-white">data/tender.txt</h4>
              <p class="text-[11px] text-slate-400">Clauses 1–7 (Criteria, Weights, Rubric)</p>
            </div>
            <div class="text-[10px] text-slate-500 font-mono">TDR-2026-CAMPUS-NET-019</div>
          </div>

          <!-- Node: Criteria Agent -->
          <div id="v-crit" onclick="inspectNode('crit')" class="cursor-pointer bg-slate-800/90 border border-slate-700 rounded-xl p-4 hover:border-indigo-400 transition flex flex-col justify-between shadow-lg">
            <div class="flex items-center justify-between">
              <span class="text-[10px] uppercase font-bold text-sky-400 tracking-wider">Agent 1 (RAG)</span>
              <span class="w-2 h-2 rounded-full bg-sky-400 animate-ping"></span>
            </div>
            <div class="my-2">
              <h4 class="font-bold text-sm text-white">CriteriaAgent</h4>
              <p class="text-[11px] text-slate-400">TF-IDF Vectorization & Weights Parsing</p>
            </div>
            <div class="text-[10px] text-sky-400 font-mono">Tools: retrieve_clauses, parse_weights</div>
          </div>

          <!-- Central Node: Shared Scorecard -->
          <div id="v-scorecard" onclick="inspectNode('scorecard')" class="cursor-pointer bg-amber-950/40 border border-amber-600/50 rounded-xl p-4 hover:border-amber-400 transition flex flex-col justify-between shadow-lg">
            <div class="flex items-center justify-between">
              <span class="text-[10px] uppercase font-bold text-amber-400 tracking-wider">Central State</span>
              <i class="fa-solid fa-database text-amber-400"></i>
            </div>
            <div class="my-2">
              <h4 class="font-bold text-sm text-white">Shared Scorecard</h4>
              <p class="text-[11px] text-slate-300">Protected by <code class="text-amber-300 font-mono">asyncio.Lock</code></p>
            </div>
            <div class="text-[10px] text-amber-400 font-mono">Slice Writes & Audit Events</div>
          </div>
        </div>

        <!-- Middle Row: Parallel Fan-Out Bid Lanes -->
        <div class="mt-6">
          <div class="flex items-center justify-between mb-2">
            <span class="text-[11px] uppercase tracking-wider font-bold text-slate-400">
              <i class="fa-solid fa-arrows-split-up-and-left rotate-90 mr-1 text-indigo-400"></i> Parallel Fan-Out Scoring (asyncio.gather)
            </span>
            <span class="text-[10px] font-mono text-slate-500">Compliance &bull; Technical &bull; Commercial</span>
          </div>
          
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <!-- Bid A -->
            <div id="v-bidA" onclick="inspectNode('bidA')" class="cursor-pointer bg-slate-800/80 border border-slate-700 rounded-xl p-3 hover:border-emerald-400 transition">
              <div class="flex justify-between items-center text-[10px] text-slate-400">
                <span class="font-bold text-white font-mono">bid_A</span>
                <span class="text-emerald-400 font-bold">COMPLIANT</span>
              </div>
              <div class="text-[11px] text-slate-300 font-semibold mt-1">Alpha Networks</div>
              <div class="text-[10px] text-slate-400 mt-1 font-mono">$125,000 | 45 days</div>
              <div class="text-[11px] text-emerald-400 font-mono mt-1 font-bold">Total: 91.00</div>
            </div>

            <!-- Bid B -->
            <div id="v-bidB" onclick="inspectNode('bidB')" class="cursor-pointer bg-slate-800/80 border border-slate-700 rounded-xl p-3 hover:border-emerald-400 transition">
              <div class="flex justify-between items-center text-[10px] text-slate-400">
                <span class="font-bold text-white font-mono">bid_B</span>
                <span class="text-emerald-400 font-bold">LOWEST PRICE</span>
              </div>
              <div class="text-[11px] text-slate-300 font-semibold mt-1">Beta Infrastructure</div>
              <div class="text-[10px] text-slate-400 mt-1 font-mono">$100,000 | 60 days</div>
              <div class="text-[11px] text-emerald-400 font-mono mt-1 font-bold">Total: 72.50</div>
            </div>

            <!-- Bid C (Disqualified) -->
            <div id="v-bidC" onclick="inspectNode('bidC')" class="cursor-pointer bg-rose-950/40 border border-rose-700/60 rounded-xl p-3 hover:border-rose-400 transition">
              <div class="flex justify-between items-center text-[10px] text-slate-400">
                <span class="font-bold text-white font-mono">bid_C</span>
                <span class="text-rose-400 font-bold">DISQUALIFIED</span>
              </div>
              <div class="text-[11px] text-rose-200 font-semibold mt-1">Gamma Systems</div>
              <div class="text-[10px] text-rose-300 mt-1 font-mono">Missing EMD Receipt</div>
              <div class="text-[11px] text-rose-400 font-mono mt-1 font-bold">Excluded from Rank</div>
            </div>

            <!-- Bid D (Tie-Break Winner) -->
            <div id="v-bidD" onclick="inspectNode('bidD')" class="cursor-pointer bg-slate-800/80 border border-slate-700 rounded-xl p-3 hover:border-amber-400 transition">
              <div class="flex justify-between items-center text-[10px] text-slate-400">
                <span class="font-bold text-white font-mono">bid_D</span>
                <span class="text-amber-400 font-bold">WINNER</span>
              </div>
              <div class="text-[11px] text-slate-300 font-semibold mt-1">Delta Communications</div>
              <div class="text-[10px] text-slate-400 mt-1 font-mono">$115,000 | 20 days</div>
              <div class="text-[11px] text-amber-400 font-mono mt-1 font-bold">Total: 92.09</div>
            </div>
          </div>
        </div>

        <!-- Bottom Row: Fan-In Award Manager -> Tie-Break Agent -> Groq LLM -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mt-6">
          
          <!-- Node: Award Manager -->
          <div id="v-award" onclick="inspectNode('award')" class="cursor-pointer bg-slate-800/90 border border-slate-700 rounded-xl p-4 hover:border-indigo-400 transition flex flex-col justify-between shadow-lg">
            <div class="flex items-center justify-between">
              <span class="text-[10px] uppercase font-bold text-emerald-400 tracking-wider">Agent 5 (Fan-In)</span>
              <i class="fa-solid fa-scale-balanced text-emerald-400"></i>
            </div>
            <div class="my-2">
              <h4 class="font-bold text-sm text-white">AwardManager</h4>
              <p class="text-[11px] text-slate-400">Filters Bid C &bull; Applies Weights &bull; Initial Ranks</p>
            </div>
            <div class="text-[10px] text-emerald-400 font-mono">Tools: apply_weights, rank_bids</div>
          </div>

          <!-- Node: Tie-Break Agent -->
          <div id="v-tie" onclick="inspectNode('tie')" class="cursor-pointer bg-slate-800/90 border border-slate-700 rounded-xl p-4 hover:border-indigo-400 transition flex flex-col justify-between shadow-lg">
            <div class="flex items-center justify-between">
              <span class="text-[10px] uppercase font-bold text-indigo-400 tracking-wider">Agent 6 (Resolver)</span>
              <span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-900 text-indigo-300">&Delta; &le; 2.0</span>
            </div>
            <div class="my-2">
              <h4 class="font-bold text-sm text-white">TieBreakAgent</h4>
              <p class="text-[11px] text-slate-400">Secondary Rule: Delivery Timeline (20d vs 45d)</p>
            </div>
            <div class="text-[10px] text-indigo-400 font-mono">Tools: detect_ties, apply_secondary</div>
          </div>

          <!-- Node: Groq LLM / Decision -->
          <div id="v-llm" onclick="inspectNode('llm')" class="cursor-pointer bg-slate-800/90 border border-slate-700 rounded-xl p-4 hover:border-orange-400 transition flex flex-col justify-between shadow-lg">
            <div class="flex items-center justify-between">
              <span class="text-[10px] uppercase font-bold text-orange-400 tracking-wider">Inference & Justification</span>
              <i class="fa-solid fa-microchip text-orange-400"></i>
            </div>
            <div class="my-2">
              <h4 class="font-bold text-sm text-white">Groq LPU Engine</h4>
              <p class="text-[11px] text-slate-400">openai/gpt-oss-120b</p>
            </div>
            <div class="text-[10px] text-orange-400 font-mono">Synthesizes Audit Justification</div>
          </div>
        </div>

      </div>

      <!-- Live Packet Transmission Readout -->
      <div class="bg-slate-50 border border-slate-200 rounded-xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div class="flex items-start sm:items-center space-x-3">
          <div id="packetDot" class="w-3.5 h-3.5 rounded-full bg-indigo-600 animate-ping mt-1 sm:mt-0 flex-shrink-0"></div>
          <div>
            <div class="flex items-center space-x-2">
              <span id="packetStepBadge" class="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded bg-indigo-100 text-indigo-800">STEP 1</span>
              <span id="packetRoute" class="text-xs font-bold text-slate-800">Tender Document &rarr; CriteriaAgent</span>
            </div>
            <p id="packetDetail" class="text-xs text-slate-600 mt-1 leading-relaxed">
              CriteriaAgent queries the in-memory TF-IDF index for evaluation criteria and weights.
            </p>
          </div>
        </div>
        <div class="text-right flex-shrink-0">
          <span id="packetActionType" class="text-[10px] font-mono px-2 py-1 rounded bg-slate-200 text-slate-700 font-bold">RAG_RETRIEVAL</span>
        </div>
      </div>
    </div>

    <!-- Inspector Modal / Drawer -->
    <div id="nodeModal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div class="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4 border border-slate-200">
        <div class="flex justify-between items-center pb-3 border-b border-slate-100">
          <div class="flex items-center space-x-2">
            <span id="modalIcon" class="text-indigo-600 text-lg"></span>
            <h3 id="modalTitle" class="font-bold text-slate-900 text-base">Node Inspector</h3>
          </div>
          <button onclick="closeModal()" class="text-slate-400 hover:text-slate-700 text-lg">&times;</button>
        </div>
        <div class="space-y-3 text-xs">
          <div>
            <span class="font-bold text-slate-500 uppercase tracking-wider text-[10px]">Role & Purpose:</span>
            <p id="modalRole" class="text-slate-800 mt-0.5 leading-relaxed font-medium">--</p>
          </div>
          <div>
            <span class="font-bold text-slate-500 uppercase tracking-wider text-[10px]">Tools Executed:</span>
            <p id="modalTools" class="text-indigo-600 mt-0.5 font-mono">--</p>
          </div>
          <div>
            <span class="font-bold text-slate-500 uppercase tracking-wider text-[10px]">Input Data Received:</span>
            <div id="modalInput" class="p-2.5 rounded bg-slate-50 border border-slate-100 font-mono text-[11px] text-slate-700 mt-0.5">--</div>
          </div>
          <div>
            <span class="font-bold text-slate-500 uppercase tracking-wider text-[10px]">Output Data Passed to Scorecard:</span>
            <div id="modalOutput" class="p-2.5 rounded bg-slate-50 border border-slate-100 font-mono text-[11px] text-slate-700 mt-0.5">--</div>
          </div>
        </div>
        <div class="pt-3 border-t border-slate-100 flex justify-end">
          <button onclick="closeModal()" class="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs rounded-lg transition">Close</button>
        </div>
      </div>
    </div>

    <!-- Comparative Scorecard Table -->
    <div class="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
      <div class="p-5 border-b border-slate-200 flex justify-between items-center">
        <div>
          <h3 class="font-bold text-slate-900 text-base">Comparative Evaluation Scorecard</h3>
          <p class="text-xs text-slate-500">Live vendor scores evaluated across Technical, Commercial, Experience, and Delivery criteria.</p>
        </div>
        <div id="tableLoading" class="hidden text-xs text-indigo-600 font-semibold flex items-center space-x-1.5">
          <i class="fa-solid fa-spinner animate-spin"></i>
          <span>Evaluating bids...</span>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-slate-200 text-xs text-left">
          <thead class="bg-slate-50 text-slate-600 font-bold uppercase tracking-wider text-[11px]">
            <tr>
              <th class="py-3 px-4">Rank</th>
              <th class="py-3 px-4">Bid ID</th>
              <th class="py-3 px-4">Vendor</th>
              <th class="py-3 px-4">Price ($)</th>
              <th class="py-3 px-4">Delivery</th>
              <th class="py-3 px-4">Technical (40)</th>
              <th class="py-3 px-4">Commercial (30)</th>
              <th class="py-3 px-4">Experience (20)</th>
              <th class="py-3 px-4">Delivery (10)</th>
              <th class="py-3 px-4">Total (100)</th>
              <th class="py-3 px-4">Status</th>
            </tr>
          </thead>
          <tbody id="scorecardBody" class="divide-y divide-slate-100 font-medium text-slate-700">
            <tr>
              <td colspan="11" class="py-8 text-center text-slate-400">Loading scorecard...</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Audit Trace Log -->
    <div class="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
      <h3 class="font-bold text-slate-900 text-sm flex items-center space-x-2 mb-3">
        <i class="fa-solid fa-list-check text-indigo-500"></i>
        <span>Multi-Agent Audit Trail (<code class="font-mono text-xs">logs/run_log.jsonl</code>)</span>
      </h3>
      <div id="traceLog" class="bg-slate-950 text-slate-200 font-mono text-[11px] p-4 rounded-xl h-60 overflow-y-auto space-y-1.5 shadow-inner border border-slate-800">
        <p class="text-slate-500">// Waiting for pipeline execution...</p>
      </div>
    </div>

  </main>

  <script>
    // Visualizer Pipeline Flow Steps
    const flowSteps = [
      {
        step: 1,
        activeIds: ["v-tender", "v-crit"],
        sender: "data/tender.txt",
        receiver: "CriteriaAgent",
        type: "RAG_RETRIEVAL",
        route: "Tender Corpus &rarr; CriteriaAgent",
        detail: "CriteriaAgent queries in-memory TF-IDF index for evaluation criteria, weights, and mandatory compliance checklist."
      },
      {
        step: 2,
        activeIds: ["v-crit", "v-scorecard"],
        sender: "CriteriaAgent",
        receiver: "Scorecard (asyncio.Lock)",
        type: "MUTEX_WRITE",
        route: "CriteriaAgent &rarr; Scorecard",
        detail: "CriteriaAgent writes parsed weights (Tech: 40%, Comm: 30%, Exp: 20%, Delivery: 10%) into shared Scorecard with lock protection."
      },
      {
        step: 3,
        activeIds: ["v-scorecard", "v-bidA", "v-bidB", "v-bidC", "v-bidD"],
        sender: "Scorecard",
        receiver: "Fan-Out Bid Workers",
        type: "FAN_OUT_DISPATCH",
        route: "Scorecard &rarr; Parallel Bid Evaluators",
        detail: "Orchestrator dispatches bids A, B, C, D concurrently via asyncio.gather to ComplianceAgent, TechnicalScorer, and CommercialScorer."
      },
      {
        step: 4,
        activeIds: ["v-bidC"],
        disqIds: ["v-bidC"],
        sender: "ComplianceAgent",
        receiver: "Scorecard",
        type: "DISQUALIFICATION",
        route: "ComplianceAgent &rarr; Scorecard (Disqualification)",
        detail: "ComplianceAgent evaluates Bid C. Identifies missing mandatory 'EMD Receipt'. Immediately marks Bid C as DISQUALIFIED."
      },
      {
        step: 5,
        activeIds: ["v-bidA", "v-bidB", "v-bidD", "v-scorecard"],
        sender: "Technical & Commercial Scorers",
        receiver: "Scorecard",
        type: "SLICE_WRITES",
        route: "Scorers &rarr; Scorecard",
        detail: "Scorers record rubric points and prices. CommercialScorer applies inverse-price formula based on Bid B's $100k lowest compliant price."
      },
      {
        step: 6,
        activeIds: ["v-scorecard", "v-award"],
        sender: "Scorecard",
        receiver: "AwardManager",
        type: "FAN_IN_AGGREGATION",
        route: "Scorecard &rarr; AwardManager (Fan-In)",
        detail: "AwardManager reads all slices, excludes disqualified Bid C, applies weights, and computes initial ranks: Rank 1: Bid D (92.09), Rank 2: Bid A (91.00)."
      },
      {
        step: 7,
        activeIds: ["v-award", "v-tie"],
        sender: "AwardManager",
        receiver: "TieBreakAgent",
        type: "MARGIN_TIE_DETECTED",
        route: "AwardManager &rarr; TieBreakAgent",
        detail: "Score difference between top two bids is 1.09 <= 2.0 margin. TieBreakAgent is invoked to apply the secondary delivery timeline rule."
      },
      {
        step: 8,
        activeIds: ["v-tie", "v-bidD", "v-llm"],
        sender: "TieBreakAgent & Groq",
        receiver: "Final Winner",
        type: "AWARD_RECOMMENDATION",
        route: "TieBreakAgent & Groq &rarr; Winner Decision",
        detail: "Bid D wins with faster delivery of 20 days (vs Bid A's 45 days). Groq LLM (openai/gpt-oss-120b) drafts formal weighted procurement justification."
      }
    ];

    let currentFlowIdx = 0;
    let autoPlayInterval = null;

    function applyFlowStep(idx) {
      currentFlowIdx = idx;
      const data = flowSteps[idx];

      document.getElementById('packetStepBadge').textContent = `STEP ${data.step} OF ${flowSteps.length}`;
      document.getElementById('packetRoute').innerHTML = data.route;
      document.getElementById('packetDetail').textContent = data.detail;
      document.getElementById('packetActionType').textContent = data.type;

      // Reset all node highlights
      const allNodes = ["v-tender", "v-crit", "v-scorecard", "v-bidA", "v-bidB", "v-bidC", "v-bidD", "v-award", "v-tie", "v-llm"];
      allNodes.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.remove('node-active', 'node-disq-active');
      });

      // Highlight active nodes
      data.activeIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
          if (data.disqIds && data.disqIds.includes(id)) {
            el.classList.add('node-disq-active');
          } else {
            el.classList.add('node-active');
          }
        }
      });
    }

    function nextFlowStep() {
      if (currentFlowIdx < flowSteps.length - 1) {
        applyFlowStep(currentFlowIdx + 1);
      } else {
        applyFlowStep(0);
      }
    }

    function prevFlowStep() {
      if (currentFlowIdx > 0) {
        applyFlowStep(currentFlowIdx - 1);
      } else {
        applyFlowStep(flowSteps.length - 1);
      }
    }

    function toggleAutoPlay() {
      const icon = document.getElementById('playIcon');
      const text = document.getElementById('playText');
      if (autoPlayInterval) {
        clearInterval(autoPlayInterval);
        autoPlayInterval = null;
        icon.className = "fa-solid fa-play";
        text.textContent = "Auto Flow";
      } else {
        icon.className = "fa-solid fa-pause";
        text.textContent = "Pause Flow";
        autoPlayInterval = setInterval(nextFlowStep, 2500);
      }
    }

    function resetFlow() {
      if (autoPlayInterval) toggleAutoPlay();
      applyFlowStep(0);
    }

    // Node Inspector details
    const nodeDetails = {
      'tender': {
        icon: '<i class="fa-solid fa-file-contract text-indigo-500"></i>',
        title: "Tender Corpus (data/tender.txt)",
        role: "Authoritative procurement document specifying campus network infrastructure requirements.",
        tools: "Clause chunking parser (numbered clauses 1 through 7)",
        input: "Digital sealed tender specification",
        output: "Clause 4 (Criteria: Tech 40%, Comm 30%, Exp 20%, Delivery 10%), Clause 5 (Mandatory: Registration, Tax, EMD, Experience)"
      },
      'crit': {
        icon: '<i class="fa-solid fa-brain text-sky-500"></i>',
        title: "CriteriaAgent (RAG Agent)",
        role: "Autonomous agent retrieving criteria, weights, and compliance rules dynamically without hardcoding.",
        tools: "retrieve_clauses(query), parse_weights(text), parse_mandatory_docs(text)",
        input: "Tender text clauses via in-memory TF-IDF vectorizer",
        output: "Weights dictionary: {'technical': 40.0, 'commercial': 30.0, 'experience': 20.0, 'delivery': 10.0}, Mandatory checklist"
      },
      'scorecard': {
        icon: '<i class="fa-solid fa-database text-amber-500"></i>',
        title: "Shared Scorecard (Thread-Safe Central Memory)",
        role: "Central shared dataclass maintaining bid slices, compliance states, events, and final award under asyncio.Lock.",
        tools: "Scorecard.update_technical_slice, update_commercial_slice, update_compliance_slice, update_totals_and_ranks",
        input: "Parallel slice updates from all 6 agents",
        output: "Unified evaluation matrix & immutable append-only logs in logs/run_log.jsonl"
      },
      'bidA': {
        icon: '<i class="fa-solid fa-building text-emerald-500"></i>',
        title: "Bid A Evaluation Lane (Alpha Networks)",
        role: "Strong technical bidder with mid-tier commercial quotation.",
        tools: "check_required_docs, extract_bid_features, score_against_rubric",
        input: "bid_A.txt: $125,000, 45 days, 12 years exp, ISO 9001/27001, 25 engineers",
        output: "Compliant: True | Tech: 40/40, Exp: 20/20, Comm: 24.00, Deliv: 7.00 | Total: 91.00 (Rank 2)"
      },
      'bidB': {
        icon: '<i class="fa-solid fa-building text-emerald-500"></i>',
        title: "Bid B Evaluation Lane (Beta Infrastructure)",
        role: "Lowest cost bidder setting the commercial baseline for normalization.",
        tools: "normalize_price, check_payment_terms, score_against_rubric",
        input: "bid_B.txt: $100,000 (Lowest), 60 days, 6 years exp, ISO 9001, 15 engineers",
        output: "Compliant: True | Tech: 25.5/40, Exp: 12/20, Comm: 30.00, Deliv: 5.00 | Total: 72.50 (Rank 3)"
      },
      'bidC': {
        icon: '<i class="fa-solid fa-triangle-exclamation text-rose-500"></i>',
        title: "Bid C Evaluation Lane (Gamma Systems - DISQUALIFIED)",
        role: "High-spec bidder failing mandatory legal compliance (handled failure).",
        tools: "check_required_docs(bid_text, required_docs)",
        input: "bid_C.txt: Missing mandatory 'EMD Receipt' certificate",
        output: "Disqualified: True | Reason: 'Missing mandatory documents: EMD Receipt' | Total: 0.00 (Excluded from ranking)"
      },
      'bidD': {
        icon: '<i class="fa-solid fa-building text-amber-500"></i>',
        title: "Bid D Evaluation Lane (Delta Communications - WINNER)",
        role: "Fastest delivery bidder qualifying for margin tie-break victory.",
        tools: "score_against_rubric, apply_secondary_criterion",
        input: "bid_D.txt: $115,000, 20 days delivery, 8 years exp, ISO 9001/27001, 20 engineers",
        output: "Compliant: True | Tech: 40/40, Exp: 16/20, Comm: 26.09, Deliv: 10.00 | Total: 92.09 (Declared Winner)"
      },
      'award': {
        icon: '<i class="fa-solid fa-scale-balanced text-emerald-500"></i>',
        title: "AwardManager (Fan-In Aggregator)",
        role: "Fuses per-bid slices, applies criteria weights, filters disqualified bids, and ranks candidates.",
        tools: "apply_weights(scores, weights), rank_bids(totals)",
        input: "Aggregated bid slices from central Scorecard",
        output: "Initial ranked standings: [1: bid_D (92.09), 2: bid_A (91.00), 3: bid_B (72.50)]"
      },
      'tie': {
        icon: '<i class="fa-solid fa-handshake-angle text-indigo-500"></i>',
        title: "TieBreakAgent (Margin Resolver)",
        role: "Detects score differences <= 2.0 margin and resolves award via secondary tender criterion.",
        tools: "detect_ties(ranked, margin=2.0), apply_secondary_criterion(bids, 'delivery_days')",
        input: "Rank 1 (Bid D: 92.09) vs Rank 2 (Bid A: 91.00) -> Gap = 1.09 <= 2.0",
        output: "Winner: bid_D resolved based on superior 20-day delivery timeline (vs 45 days)"
      },
      'llm': {
        icon: '<i class="fa-solid fa-microchip text-orange-500"></i>',
        title: "Groq LPU Engine (openai/gpt-oss-120b)",
        role: "High-speed LLM inference synthesizing formal audit-compliant award justification.",
        tools: "OpenAIChatCompletion via Semantic Kernel over Groq OpenAI API",
        input: "Per-criterion scores, weights citation prompt, vendor comparison details",
        output: "Executive award justification citing Technical, Commercial, Experience, and Delivery weights"
      }
    };

    function inspectNode(key) {
      const data = nodeDetails[key];
      if (!data) return;
      document.getElementById('modalIcon').innerHTML = data.icon;
      document.getElementById('modalTitle').textContent = data.title;
      document.getElementById('modalRole').textContent = data.role;
      document.getElementById('modalTools').textContent = data.tools;
      document.getElementById('modalInput').textContent = data.input;
      document.getElementById('modalOutput').textContent = data.output;
      document.getElementById('nodeModal').classList.remove('hidden');
    }

    function closeModal() {
      document.getElementById('nodeModal').classList.add('hidden');
    }

    // Backend API execution
    async function loadScorecardData() {
      try {
        const res = await fetch('/api/scorecard');
        if (res.ok) {
          const data = await res.json();
          renderScorecard(data);
        }
      } catch (e) {
        console.log("No previous scorecard:", e);
      }
    }

    async function runRealEvaluation() {
      const btn = document.getElementById('runBtn');
      const loader = document.getElementById('tableLoading');
      btn.disabled = true;
      btn.classList.add('opacity-50', 'cursor-not-allowed');
      loader.classList.remove('hidden');

      // Start automatic step animation while API evaluates
      let stepCounter = 0;
      const animTimer = setInterval(() => {
        applyFlowStep(stepCounter % flowSteps.length);
        stepCounter++;
      }, 700);

      try {
        const res = await fetch('/api/evaluate', { method: 'POST' });
        if (!res.ok) throw new Error("Evaluation request failed");
        const data = await res.json();
        clearInterval(animTimer);
        applyFlowStep(flowSteps.length - 1);
        renderScorecard(data);
      } catch (err) {
        clearInterval(animTimer);
        alert("Evaluation error: " + err.message);
      } finally {
        btn.disabled = false;
        btn.classList.remove('opacity-50', 'cursor-not-allowed');
        loader.classList.add('hidden');
      }
    }

    function renderScorecard(data) {
      if (!data || !data.bids) return;

      // Render Winner
      const banner = document.getElementById('winnerBanner');
      banner.classList.remove('hidden');
      document.getElementById('winnerName').textContent = data.winner;
      const winnerBid = data.bids[data.winner] || {};
      document.getElementById('winnerScore').textContent = `Total Weighted Score: ${winnerBid.total ? winnerBid.total.toFixed(2) : '--'} / 100.00`;
      document.getElementById('justificationSummary').textContent = data.justification || "Evaluation finalized.";

      const tieBadge = document.getElementById('tieBreakBadge');
      if (data.tie_break_applied) {
        tieBadge.classList.remove('hidden');
      } else {
        tieBadge.classList.add('hidden');
      }

      // Render Table
      const tbody = document.getElementById('scorecardBody');
      tbody.innerHTML = '';

      const bidsList = Object.values(data.bids);
      bidsList.sort((a, b) => {
        if (a.disqualified && !b.disqualified) return 1;
        if (!a.disqualified && b.disqualified) return -1;
        return (a.rank || 999) - (b.rank || 999);
      });

      bidsList.forEach(b => {
        const tr = document.createElement('tr');
        const s = b.scores || {};
        const isWinner = b.bid_id === data.winner;
        if (isWinner) tr.classList.add('bg-amber-50/50');

        const priceStr = b.price ? '$' + Number(b.price).toLocaleString() : '-';
        const deliveryStr = b.delivery_days ? b.delivery_days + ' days' : '-';
        const rankStr = b.disqualified ? '<span class="text-rose-600 font-bold">-</span>' : `<b>${b.rank}</b>`;
        const totalStr = b.disqualified ? '0.00' : Number(b.total || 0).toFixed(2);
        
        const statusBadge = b.disqualified
          ? `<span class="badge-fail px-2 py-0.5 rounded text-[10px] font-bold">Disqualified (${b.disqualification_reason || 'Failed'})</span>`
          : (isWinner 
              ? `<span class="badge-winner px-2 py-0.5 rounded text-[10px] font-bold">Recommended Winner</span>`
              : `<span class="badge-pass px-2 py-0.5 rounded text-[10px] font-bold">Compliant</span>`);

        tr.innerHTML = `
          <td class="py-3 px-4">${rankStr}</td>
          <td class="py-3 px-4 font-mono font-bold ${isWinner ? 'text-amber-800' : 'text-slate-900'}">${b.bid_id}</td>
          <td class="py-3 px-4">${b.vendor_name || b.bid_id}</td>
          <td class="py-3 px-4 font-mono">${priceStr}</td>
          <td class="py-3 px-4">${deliveryStr}</td>
          <td class="py-3 px-4 font-mono">${s.technical !== undefined ? s.technical.toFixed(2) : '-'}</td>
          <td class="py-3 px-4 font-mono">${s.commercial !== undefined && !b.disqualified ? s.commercial.toFixed(2) : '-'}</td>
          <td class="py-3 px-4 font-mono">${s.experience !== undefined ? s.experience.toFixed(2) : '-'}</td>
          <td class="py-3 px-4 font-mono">${s.delivery !== undefined ? s.delivery.toFixed(2) : '-'}</td>
          <td class="py-3 px-4 font-black font-mono ${isWinner ? 'text-amber-700 text-sm' : 'text-slate-900'}">${totalStr}</td>
          <td class="py-3 px-4">${statusBadge}</td>
        `;
        tbody.appendChild(tr);
      });

      // Render Trace Log
      const traceBox = document.getElementById('traceLog');
      if (data.events && data.events.length) {
        traceBox.innerHTML = '';
        data.events.forEach(evt => {
          const div = document.createElement('div');
          div.innerHTML = `<span class="text-slate-500">[${evt.timestamp.substring(11, 19)}]</span> <span class="text-indigo-400 font-bold">[${evt.agent}]</span> <span class="text-amber-300 font-bold">${evt.action.toUpperCase()}</span>: <span class="text-slate-300">${evt.detail}</span>`;
          traceBox.appendChild(div);
        });
        traceBox.scrollTop = traceBox.scrollHeight;
      }
    }

    window.addEventListener('DOMContentLoaded', () => {
      applyFlowStep(0);
      loadScorecardData();
    });
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start BidWise Web Application")
    parser.add_argument("--port", type=int, default=8080, help="Port to run the application on (default: 8080)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address (default: 0.0.0.0)")
    parser.add_argument("--reload", action="store_true", help="Enable live reload")
    args = parser.parse_args()

    print(f"\n=======================================================")
    print(f" Starting BidWise Multi-Agent Visualizer on port {args.port}...")
    print(f" Dashboard URL : http://localhost:{args.port}")
    print(f" API Docs URL  : http://localhost:{args.port}/docs")
    print(f"=======================================================\n")

    uvicorn.run("app:app", host=args.host, port=args.port, reload=args.reload)
