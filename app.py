"""FastAPI Web Application and REST API for BidWise Multi-Agent Tender Evaluation.

Includes full interactive visualizer for multi-agent data exchange in Dark Mode,
with customizable system parameters (defaulting to baseline hardcoded values).

Run via:
    python app.py --port 8080
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
from pydantic import BaseModel, Field

from config import (
    GROQ_MODEL,
    OUTPUT_DIR,
    REPORT_OUTPUT_PATH,
    SCORECARD_OUTPUT_PATH,
    TENDER_PATH,
    USE_LLM,
    has_groq_api_key,
)
from logs.logger import default_logger
from orchestrator import run_tender_evaluation

app = FastAPI(
    title="BidWise Multi-Agent Tender Evaluation API",
    description="Autonomous Fan-Out / Fan-In multi-agent tender evaluation system powered by Semantic Kernel and Groq.",
    version="1.1.0",
)


class EvaluationConfig(BaseModel):
    selected_bids: Optional[List[str]] = Field(default=None, description="List of bid IDs to evaluate")
    custom_weights: Optional[Dict[str, float]] = Field(default=None, description="Custom criteria weights")
    tie_margin: Optional[float] = Field(default=None, description="Tie break margin threshold")
    secondary_criterion: Optional[str] = Field(default=None, description="Secondary tiebreak criterion")
    mandatory_documents: Optional[List[str]] = Field(default=None, description="Mandatory compliance checklist")
    custom_bids: Optional[Dict[str, Any]] = Field(default=None, description="Per-bid property overrides")
    custom_tender_text: Optional[str] = Field(default=None, description="Custom tender document text")


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


@app.get("/api/defaults")
async def get_system_defaults():
    """Returns baseline hardcoded defaults for criteria, tie-break, compliance, and bids."""
    tender_text = ""
    if Path(TENDER_PATH).exists():
        with open(TENDER_PATH, "r", encoding="utf-8") as f:
            tender_text = f.read()

    return {
        "weights": {
            "technical": 40.0,
            "commercial": 30.0,
            "experience": 20.0,
            "delivery": 10.0,
        },
        "tie_margin": 2.0,
        "secondary_criterion": "delivery_days",
        "mandatory_documents": [
            "Registration Certificate",
            "Tax Clearance",
            "EMD Receipt",
            "Experience Certificate",
        ],
        "tender_text": tender_text,
        "bids": {
            "bid_A": {
                "vendor_name": "Alpha Networks Ltd",
                "price": 125000,
                "delivery_days": 45,
                "years_of_experience": 12,
                "team_size": 25,
                "similar_projects": 8,
                "certifications": ["ISO 9001", "ISO 27001"],
                "submitted_docs": ["Registration Certificate", "Tax Clearance", "EMD Receipt", "Experience Certificate"],
                "enabled": True,
            },
            "bid_B": {
                "vendor_name": "Beta Infrastructure Ltd",
                "price": 100000,
                "delivery_days": 60,
                "years_of_experience": 6,
                "team_size": 15,
                "similar_projects": 4,
                "certifications": ["ISO 9001"],
                "submitted_docs": ["Registration Certificate", "Tax Clearance", "EMD Receipt", "Experience Certificate"],
                "enabled": True,
            },
            "bid_C": {
                "vendor_name": "Gamma Systems Pvt Ltd",
                "price": 110000,
                "delivery_days": 30,
                "years_of_experience": 10,
                "team_size": 22,
                "similar_projects": 6,
                "certifications": ["ISO 9001", "ISO 27001"],
                "submitted_docs": ["Registration Certificate", "Tax Clearance", "Experience Certificate"],
                "enabled": True,
            },
            "bid_D": {
                "vendor_name": "Delta Communications Inc",
                "price": 115000,
                "delivery_days": 20,
                "years_of_experience": 8,
                "team_size": 20,
                "similar_projects": 5,
                "certifications": ["ISO 9001", "ISO 27001"],
                "submitted_docs": ["Registration Certificate", "Tax Clearance", "EMD Receipt", "Experience Certificate"],
                "enabled": True,
            },
        },
    }


@app.post("/api/evaluate")
async def evaluate_tender(config: Optional[EvaluationConfig] = None):
    """Executes the full multi-agent tender evaluation pipeline with optional custom overrides."""
    try:
        cfg = config or EvaluationConfig()
        scorecard = await run_tender_evaluation(
            selected_bids=cfg.selected_bids,
            print_trace=False,
            use_semantic_kernel=True,
            custom_weights=cfg.custom_weights,
            mandatory_documents=cfg.mandatory_documents,
            tie_margin=cfg.tie_margin,
            secondary_criterion=cfg.secondary_criterion,
            custom_tender_text=cfg.custom_tender_text,
            custom_bids=cfg.custom_bids,
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
    """Serves an interactive Dark Mode web dashboard with multi-agent dataflow visualizer and parameter customizer."""
    html_content = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>BidWise | Multi-Agent Tender Evaluation (Dark Mode)</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            brand: {
              50: '#eef2ff',
              500: '#6366f1',
              600: '#4f46e5',
              700: '#4338ca',
            }
          }
        }
      }
    }
  </script>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: #0b0f19;
      color: #f1f5f9;
    }
    .badge-pass { background-color: rgba(6, 78, 59, 0.4); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
    .badge-fail { background-color: rgba(136, 19, 55, 0.4); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.4); }
    .badge-winner { background-color: rgba(120, 53, 15, 0.4); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.5); }
    
    /* Flow Animations */
    @keyframes pulse-node-dark {
      0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(99, 102, 241, 0.7); }
      70% { transform: scale(1.03); box-shadow: 0 0 0 12px rgba(99, 102, 241, 0); }
      100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(99, 102, 241, 0); }
    }
    @keyframes pulse-disq-dark {
      0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(244, 63, 94, 0.7); }
      70% { transform: scale(1.03); box-shadow: 0 0 0 12px rgba(244, 63, 94, 0); }
      100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(244, 63, 94, 0); }
    }
    .node-active {
      animation: pulse-node-dark 1.8s infinite;
      border-color: #818cf8 !important;
      background-color: #1e1b4b !important;
    }
    .node-disq-active {
      animation: pulse-disq-dark 1.8s infinite;
      border-color: #fb7185 !important;
      background-color: #4c0519 !important;
    }
    .custom-scroll::-webkit-scrollbar { width: 6px; height: 6px; }
    .custom-scroll::-webkit-scrollbar-track { background: #0b0f19; }
    .custom-scroll::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
    .custom-scroll::-webkit-scrollbar-thumb:hover { background: #475569; }
  </style>
</head>
<body class="min-h-screen bg-[#0b0f19] text-slate-100 flex flex-col justify-between">

  <!-- Navbar -->
  <header class="bg-slate-900/90 backdrop-blur border-b border-slate-800 sticky top-0 z-50 shadow-md">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-indigo-500 flex items-center justify-center text-white font-black text-xl shadow-lg shadow-indigo-500/20">
          <i class="fa-solid fa-network-wired"></i>
        </div>
        <div>
          <div class="flex items-center space-x-2">
            <h1 class="text-lg font-bold text-white tracking-tight">BidWise</h1>
            <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-400 border border-indigo-800">Multi-Agent System</span>
            <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">Dark Mode</span>
          </div>
          <p class="text-xs text-slate-400">Autonomous Tender Evaluation &bull; Parallel Fan-Out / Fan-In</p>
        </div>
      </div>
      
      <div class="flex items-center space-x-3">
        <!-- Parameters Drawer Button -->
        <button onclick="toggleConfigPanel()" class="bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-semibold text-xs px-3 py-2 rounded-lg transition flex items-center space-x-1.5 shadow-sm">
          <i class="fa-solid fa-sliders text-indigo-400"></i>
          <span>Configure Parameters</span>
        </button>

        <!-- Reset Defaults Button -->
        <button onclick="resetToDefaults()" class="bg-slate-800/80 hover:bg-slate-700 text-amber-400 border border-amber-900/60 font-semibold text-xs px-3 py-2 rounded-lg transition flex items-center space-x-1.5 shadow-sm" title="Restore hardcoded baseline values">
          <i class="fa-solid fa-rotate-left"></i>
          <span class="hidden sm:inline">Reset Defaults</span>
        </button>

        <a href="/docs" target="_blank" class="hidden sm:flex text-xs font-semibold text-slate-400 hover:text-indigo-400 items-center space-x-1 transition px-2 py-1">
          <span>API Docs</span> <i class="fa-solid fa-arrow-up-right-from-square text-[10px]"></i>
        </a>

        <!-- Run Live Pipeline Button -->
        <button id="runBtn" onclick="runRealEvaluation()" class="bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white font-bold text-xs px-4 py-2 rounded-lg shadow-lg shadow-indigo-600/30 transition flex items-center space-x-2">
          <i class="fa-solid fa-bolt"></i>
          <span>Run Live Pipeline</span>
        </button>
      </div>
    </div>
  </header>

  <!-- Main Container -->
  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6 flex-grow w-full">

    <!-- COLLAPSIBLE CUSTOM PARAMETERS PANEL -->
    <div id="configPanel" class="hidden bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5 transition-all">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-800">
        <div>
          <div class="flex items-center space-x-2">
            <h2 class="text-base font-bold text-white flex items-center space-x-2">
              <i class="fa-solid fa-gear text-indigo-400"></i>
              <span>System Parameters & Custom Inputs</span>
            </h2>
            <span id="configModeBadge" class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">Default Baseline Active</span>
          </div>
          <p class="text-xs text-slate-400 mt-0.5">All default hardcoded values are pre-filled. Customize weights, tie-break margins, compliance rules, or vendor bids.</p>
        </div>
        <div class="flex items-center space-x-2">
          <button onclick="resetToDefaults()" class="text-xs text-amber-400 hover:text-amber-300 font-semibold px-2.5 py-1 rounded bg-amber-950/40 border border-amber-800/60 transition flex items-center space-x-1">
            <i class="fa-solid fa-rotate-left text-[10px]"></i> <span>Reset All to Defaults</span>
          </button>
          <button onclick="toggleConfigPanel()" class="text-slate-400 hover:text-slate-200 text-sm px-2 py-1 rounded hover:bg-slate-800 transition">
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>
      </div>

      <!-- Config Tabs -->
      <div class="flex space-x-2 border-b border-slate-800 pb-2 text-xs font-bold overflow-x-auto">
        <button id="tabBtn-weights" onclick="switchConfigTab('weights')" class="px-3 py-1.5 rounded-lg bg-indigo-600 text-white transition">1. Criteria Weights</button>
        <button id="tabBtn-tiebreak" onclick="switchConfigTab('tiebreak')" class="px-3 py-1.5 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white transition">2. Tie-Break Rules</button>
        <button id="tabBtn-compliance" onclick="switchConfigTab('compliance')" class="px-3 py-1.5 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white transition">3. Compliance Checklist</button>
        <button id="tabBtn-bids" onclick="switchConfigTab('bids')" class="px-3 py-1.5 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white transition">4. Vendor Bids Customizer</button>
        <button id="tabBtn-tender" onclick="switchConfigTab('tender')" class="px-3 py-1.5 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white transition">5. Tender Document Text</button>
      </div>

      <!-- TAB 1: Criteria & Weights -->
      <div id="tabContent-weights" class="space-y-4">
        <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          <!-- Technical Weight -->
          <div class="bg-slate-950/70 p-4 rounded-xl border border-slate-800 space-y-2">
            <div class="flex justify-between items-center text-xs">
              <span class="font-bold text-slate-300">Technical Capability</span>
              <span id="display-wt-tech" class="font-mono text-indigo-400 font-bold">40%</span>
            </div>
            <input type="range" id="input-wt-tech" min="5" max="80" step="5" value="40" oninput="updateWeightsFromSliders()" class="w-full accent-indigo-500 cursor-pointer">
            <p class="text-[11px] text-slate-500">Architecture, certifications, team & experience</p>
          </div>

          <!-- Commercial Weight -->
          <div class="bg-slate-950/70 p-4 rounded-xl border border-slate-800 space-y-2">
            <div class="flex justify-between items-center text-xs">
              <span class="font-bold text-slate-300">Commercial & Price</span>
              <span id="display-wt-comm" class="font-mono text-indigo-400 font-bold">30%</span>
            </div>
            <input type="range" id="input-wt-comm" min="5" max="80" step="5" value="30" oninput="updateWeightsFromSliders()" class="w-full accent-indigo-500 cursor-pointer">
            <p class="text-[11px] text-slate-500">Price competitiveness & payment terms</p>
          </div>

          <!-- Experience Weight -->
          <div class="bg-slate-950/70 p-4 rounded-xl border border-slate-800 space-y-2">
            <div class="flex justify-between items-center text-xs">
              <span class="font-bold text-slate-300">Past Experience</span>
              <span id="display-wt-exp" class="font-mono text-indigo-400 font-bold">20%</span>
            </div>
            <input type="range" id="input-wt-exp" min="5" max="80" step="5" value="20" oninput="updateWeightsFromSliders()" class="w-full accent-indigo-500 cursor-pointer">
            <p class="text-[11px] text-slate-500">Years in business and enterprise projects</p>
          </div>

          <!-- Delivery Timeline Weight -->
          <div class="bg-slate-950/70 p-4 rounded-xl border border-slate-800 space-y-2">
            <div class="flex justify-between items-center text-xs">
              <span class="font-bold text-slate-300">Delivery Timeline</span>
              <span id="display-wt-deliv" class="font-mono text-indigo-400 font-bold">10%</span>
            </div>
            <input type="range" id="input-wt-deliv" min="5" max="80" step="5" value="10" oninput="updateWeightsFromSliders()" class="w-full accent-indigo-500 cursor-pointer">
            <p class="text-[11px] text-slate-500">Committed project rollout speed</p>
          </div>
        </div>

        <div class="flex items-center justify-between text-xs px-2 pt-2">
          <span class="text-slate-400">Total Weight Sum: <b id="totalWeightSum" class="font-mono text-emerald-400">100%</b> (Automatically normalized if != 100%)</span>
          <button onclick="normalizeSlidersTo100()" class="text-xs text-indigo-400 hover:text-indigo-300 font-semibold underline">Auto-Normalize to 100%</button>
        </div>
      </div>

      <!-- TAB 2: Tie-Break Rules -->
      <div id="tabContent-tiebreak" class="hidden space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="bg-slate-950/70 p-4 rounded-xl border border-slate-800 space-y-2">
            <label class="block text-xs font-bold text-slate-300">Tie Margin Threshold (&Delta; Points)</label>
            <input type="number" id="input-tie-margin" step="0.5" min="0" max="10" value="2.0" class="bg-slate-900 border border-slate-700 text-slate-100 rounded-lg px-3 py-2 text-xs w-full focus:outline-none focus:border-indigo-500 font-mono">
            <p class="text-[11px] text-slate-500">If top 2 candidate total scores differ by &le; this margin, secondary rule triggers (Default: 2.0).</p>
          </div>

          <div class="bg-slate-950/70 p-4 rounded-xl border border-slate-800 space-y-2">
            <label class="block text-xs font-bold text-slate-300">Secondary Tie-Break Rule</label>
            <select id="input-secondary-rule" class="bg-slate-900 border border-slate-700 text-slate-100 rounded-lg px-3 py-2 text-xs w-full focus:outline-none focus:border-indigo-500 font-medium">
              <option value="delivery_days" selected>Delivery Timeline (Shorter delivery days wins - Baseline)</option>
              <option value="technical">Technical Capability (Higher technical score wins)</option>
              <option value="price">Quoted Price (Lower commercial price wins)</option>
              <option value="experience">Experience Track Record (More years wins)</option>
            </select>
            <p class="text-[11px] text-slate-500">Deterministic decider applied when top bidders are tied.</p>
          </div>
        </div>
      </div>

      <!-- TAB 3: Compliance Checklist -->
      <div id="tabContent-compliance" class="hidden space-y-4">
        <div class="bg-slate-950/70 p-4 rounded-xl border border-slate-800 space-y-3">
          <h3 class="text-xs font-bold text-slate-300">Mandatory Compliance Documents</h3>
          <p class="text-[11px] text-slate-500">Bidders missing any of these documents will be immediately flagged as <b class="text-rose-400">DISQUALIFIED</b> by ComplianceAgent.</p>
          
          <div id="mandatoryDocsContainer" class="flex flex-wrap gap-2 pt-1">
            <!-- Dynamically populated tags -->
          </div>

          <div class="flex items-center space-x-2 pt-2 border-t border-slate-800 text-xs">
            <input type="text" id="newDocInput" placeholder="Add custom mandatory doc name..." class="bg-slate-900 border border-slate-700 text-slate-100 rounded-lg px-3 py-1.5 text-xs flex-grow focus:outline-none focus:border-indigo-500">
            <button onclick="addMandatoryDoc()" class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs px-3 py-1.5 rounded-lg transition">Add Document</button>
          </div>
        </div>
      </div>

      <!-- TAB 4: Bids Customizer -->
      <div id="tabContent-bids" class="hidden space-y-4">
        <div class="flex items-center justify-between">
          <p class="text-xs text-slate-400">Select which bids to include in the evaluation, or customize their quoted prices, delivery days, and compliance documents.</p>
          <button onclick="addCustomBid()" class="bg-slate-800 hover:bg-slate-700 text-indigo-400 border border-slate-700 text-xs font-bold px-3 py-1.5 rounded-lg transition flex items-center space-x-1">
            <i class="fa-solid fa-plus text-[10px]"></i> <span>Add New Bidder</span>
          </button>
        </div>

        <div id="bidsGrid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <!-- Dynamically populated bid cards -->
        </div>
      </div>

      <!-- TAB 5: Tender Corpus -->
      <div id="tabContent-tender" class="hidden space-y-3">
        <div class="bg-slate-950/70 p-4 rounded-xl border border-slate-800 space-y-2">
          <div class="flex justify-between items-center">
            <h3 class="text-xs font-bold text-slate-300">Authoritative Tender Specifications (Clauses 1–7)</h3>
            <button onclick="reloadDefaultTenderText()" class="text-[11px] text-indigo-400 hover:underline">Reload Original Text</button>
          </div>
          <textarea id="tenderTextArea" rows="8" class="w-full bg-slate-900 border border-slate-700 text-slate-200 font-mono text-[11px] p-3 rounded-lg focus:outline-none focus:border-indigo-500 custom-scroll leading-relaxed"></textarea>
          <p class="text-[11px] text-slate-500">The CriteriaAgent uses TF-IDF over this text to extract evaluation criteria and weights via RAG.</p>
        </div>
      </div>

    </div>

    <!-- WINNER HERO BANNER (Dark Mode) -->
    <div id="winnerBanner" class="bg-gradient-to-r from-amber-950/30 via-slate-900 to-slate-900 border border-amber-600/40 rounded-2xl p-6 shadow-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-6 transition-all">
      <div class="flex items-center space-x-4">
        <div class="w-14 h-14 rounded-2xl bg-gradient-to-tr from-amber-500 to-amber-400 flex items-center justify-center text-slate-950 text-2xl shadow-lg shadow-amber-500/20">
          <i class="fa-solid fa-trophy"></i>
        </div>
        <div>
          <div class="flex items-center space-x-2">
            <span class="text-[11px] font-extrabold uppercase tracking-wider text-amber-400">Recommended Winner</span>
            <span id="tieBreakBadge" class="hidden px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-950 text-indigo-300 border border-indigo-700">Tie-Break Applied</span>
          </div>
          <h2 id="winnerName" class="text-2xl font-black text-amber-300 mt-0.5">--</h2>
          <p id="winnerScore" class="text-xs text-slate-400 font-medium font-mono">Weighted Score: --</p>
        </div>
      </div>
      <div class="w-full md:w-auto bg-slate-950/80 rounded-xl p-4 border border-amber-600/30 max-w-xl text-xs text-slate-300 leading-relaxed font-sans" id="justificationSummary">
        Click <b class="text-indigo-400">Run Live Pipeline</b> to evaluate vendor bids and watch the agents pass data.
      </div>
    </div>

    <!-- VISUAL AGENT DATAFLOW STAGE (Dark Mode) -->
    <div class="bg-slate-900 rounded-2xl border border-slate-800 p-6 shadow-xl space-y-4">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800">
        <div>
          <h2 class="text-base font-bold text-white flex items-center space-x-2">
            <i class="fa-solid fa-diagram-project text-indigo-400"></i>
            <span>Interactive Multi-Agent Dataflow Architecture</span>
          </h2>
          <p class="text-xs text-slate-400">Watch data packets transfer between autonomous agents and the shared Scorecard memory.</p>
        </div>
        
        <!-- Simulation & Playback Controls -->
        <div class="flex flex-wrap items-center gap-2 bg-slate-950 p-1.5 rounded-xl border border-slate-800">
          <div class="flex items-center space-x-1">
            <button onclick="prevFlowStep()" class="p-1.5 px-3 rounded-lg hover:bg-slate-800 text-slate-300 font-bold text-xs transition" title="Previous Step">
              <i class="fa-solid fa-backward-step mr-1"></i> Prev
            </button>
            <button id="autoPlayBtn" onclick="toggleAutoPlay()" class="p-1.5 px-3 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs transition shadow-sm flex items-center space-x-1.5">
              <i id="playIcon" class="fa-solid fa-play"></i> <span id="playText">Auto Flow</span>
            </button>
            <button onclick="nextFlowStep()" class="p-1.5 px-3 rounded-lg hover:bg-slate-800 text-slate-300 font-bold text-xs transition" title="Next Step">
              Next <i class="fa-solid fa-forward-step ml-1"></i>
            </button>
            <button onclick="resetFlow()" class="p-1.5 px-2.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 text-xs transition" title="Reset Flow">
              <i class="fa-solid fa-rotate-right"></i>
            </button>
          </div>

          <div class="flex items-center space-x-1.5 pl-2 border-l border-slate-800 text-xs">
            <label for="flowSpeedSelect" class="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Speed:</label>
            <select id="flowSpeedSelect" onchange="updateFlowSpeed()" class="text-xs bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 font-bold text-slate-200 focus:outline-none cursor-pointer">
              <option value="2200" selected>2.2s (Viva Demo - Recommended)</option>
              <option value="1500">1.5s (Normal)</option>
              <option value="800">0.8s (Fast)</option>
            </select>
          </div>
        </div>
      </div>

      <!-- Flow Progress Bar -->
      <div class="w-full bg-slate-950 rounded-full h-2 overflow-hidden border border-slate-800 shadow-inner">
        <div id="flowProgressBar" class="bg-gradient-to-r from-indigo-500 via-indigo-400 to-cyan-400 h-2 rounded-full transition-all duration-500" style="width: 12.5%;"></div>
      </div>

      <!-- Diagram Stage Grid -->
      <div class="relative bg-gradient-to-b from-slate-950 via-slate-950 to-slate-900 rounded-2xl p-6 text-white overflow-hidden shadow-2xl border border-slate-800/80 min-h-[380px]">
        
        <!-- Top Row: Input Corpus -> Criteria Agent -> Scorecard -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 relative z-10">
          
          <!-- Node: Tender Corpus -->
          <div id="v-tender" onclick="inspectNode('tender')" class="cursor-pointer bg-slate-900/90 border border-slate-800 rounded-xl p-4 hover:border-indigo-400 transition flex flex-col justify-between shadow-lg">
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
          <div id="v-crit" onclick="inspectNode('crit')" class="cursor-pointer bg-slate-900/90 border border-slate-800 rounded-xl p-4 hover:border-indigo-400 transition flex flex-col justify-between shadow-lg">
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
          <div id="v-scorecard" onclick="inspectNode('scorecard')" class="cursor-pointer bg-amber-950/30 border border-amber-600/40 rounded-xl p-4 hover:border-amber-400 transition flex flex-col justify-between shadow-lg">
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
            <div id="v-bidA" onclick="inspectNode('bidA')" class="cursor-pointer bg-slate-900/90 border border-slate-800 rounded-xl p-3 hover:border-emerald-400 transition">
              <div class="flex justify-between items-center text-[10px] text-slate-400">
                <span class="font-bold text-white font-mono">bid_A</span>
                <span class="text-emerald-400 font-bold">COMPLIANT</span>
              </div>
              <div class="text-[11px] text-slate-200 font-semibold mt-1">Alpha Networks</div>
              <div class="text-[10px] text-slate-400 mt-1 font-mono">$125,000 | 45 days</div>
              <div class="text-[11px] text-emerald-400 font-mono mt-1 font-bold">Total: 91.00</div>
            </div>

            <!-- Bid B -->
            <div id="v-bidB" onclick="inspectNode('bidB')" class="cursor-pointer bg-slate-900/90 border border-slate-800 rounded-xl p-3 hover:border-emerald-400 transition">
              <div class="flex justify-between items-center text-[10px] text-slate-400">
                <span class="font-bold text-white font-mono">bid_B</span>
                <span class="text-emerald-400 font-bold">LOWEST PRICE</span>
              </div>
              <div class="text-[11px] text-slate-200 font-semibold mt-1">Beta Infrastructure</div>
              <div class="text-[10px] text-slate-400 mt-1 font-mono">$100,000 | 60 days</div>
              <div class="text-[11px] text-emerald-400 font-mono mt-1 font-bold">Total: 72.50</div>
            </div>

            <!-- Bid C (Disqualified) -->
            <div id="v-bidC" onclick="inspectNode('bidC')" class="cursor-pointer bg-rose-950/30 border border-rose-800/50 rounded-xl p-3 hover:border-rose-400 transition">
              <div class="flex justify-between items-center text-[10px] text-slate-400">
                <span class="font-bold text-white font-mono">bid_C</span>
                <span id="v-bidC-status" class="text-rose-400 font-bold">DISQUALIFIED</span>
              </div>
              <div class="text-[11px] text-rose-200 font-semibold mt-1">Gamma Systems</div>
              <div id="v-bidC-note" class="text-[10px] text-rose-300 mt-1 font-mono">Missing EMD Receipt</div>
              <div id="v-bidC-total" class="text-[11px] text-rose-400 font-mono mt-1 font-bold">Excluded from Rank</div>
            </div>

            <!-- Bid D (Tie-Break Winner) -->
            <div id="v-bidD" onclick="inspectNode('bidD')" class="cursor-pointer bg-slate-900/90 border border-slate-800 rounded-xl p-3 hover:border-amber-400 transition">
              <div class="flex justify-between items-center text-[10px] text-slate-400">
                <span class="font-bold text-white font-mono">bid_D</span>
                <span class="text-amber-400 font-bold">WINNER</span>
              </div>
              <div class="text-[11px] text-slate-200 font-semibold mt-1">Delta Communications</div>
              <div class="text-[10px] text-slate-400 mt-1 font-mono">$115,000 | 20 days</div>
              <div class="text-[11px] text-amber-400 font-mono mt-1 font-bold">Total: 92.09</div>
            </div>
          </div>
        </div>

        <!-- Bottom Row: Fan-In Award Manager -> Tie-Break Agent -> Groq LLM -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mt-6">
          
          <!-- Node: Award Manager -->
          <div id="v-award" onclick="inspectNode('award')" class="cursor-pointer bg-slate-900/90 border border-slate-800 rounded-xl p-4 hover:border-indigo-400 transition flex flex-col justify-between shadow-lg">
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
          <div id="v-tie" onclick="inspectNode('tie')" class="cursor-pointer bg-slate-900/90 border border-slate-800 rounded-xl p-4 hover:border-indigo-400 transition flex flex-col justify-between shadow-lg">
            <div class="flex items-center justify-between">
              <span class="text-[10px] uppercase font-bold text-indigo-400 tracking-wider">Agent 6 (Resolver)</span>
              <span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">&Delta; &le; 2.0</span>
            </div>
            <div class="my-2">
              <h4 class="font-bold text-sm text-white">TieBreakAgent</h4>
              <p class="text-[11px] text-slate-400">Secondary Rule: Delivery Timeline (20d vs 45d)</p>
            </div>
            <div class="text-[10px] text-indigo-400 font-mono">Tools: detect_ties, apply_secondary</div>
          </div>

          <!-- Node: Groq LLM / Decision -->
          <div id="v-llm" onclick="inspectNode('llm')" class="cursor-pointer bg-slate-900/90 border border-slate-800 rounded-xl p-4 hover:border-orange-400 transition flex flex-col justify-between shadow-lg">
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

      <!-- Live Packet Transmission Readout (Dark Mode) -->
      <div class="bg-slate-950 border border-slate-800 rounded-xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div class="flex items-start sm:items-center space-x-3">
          <div id="packetDot" class="w-3.5 h-3.5 rounded-full bg-indigo-500 animate-ping mt-1 sm:mt-0 flex-shrink-0"></div>
          <div>
            <div class="flex items-center space-x-2">
              <span id="packetStepBadge" class="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">STEP 1</span>
              <span id="packetRoute" class="text-xs font-bold text-slate-200">Tender Document &rarr; CriteriaAgent</span>
            </div>
            <p id="packetDetail" class="text-xs text-slate-400 mt-1 leading-relaxed">
              CriteriaAgent queries the in-memory TF-IDF index for evaluation criteria and weights.
            </p>
          </div>
        </div>
        <div class="text-right flex-shrink-0">
          <span id="packetActionType" class="text-[10px] font-mono px-2.5 py-1 rounded bg-slate-800 text-indigo-300 border border-slate-700 font-bold">RAG_RETRIEVAL</span>
        </div>
      </div>
    </div>

    <!-- Inspector Modal / Drawer (Dark Mode) -->
    <div id="nodeModal" class="hidden fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div class="bg-slate-900 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4 border border-slate-800">
        <div class="flex justify-between items-center pb-3 border-b border-slate-800">
          <div class="flex items-center space-x-2">
            <span id="modalIcon" class="text-indigo-400 text-lg"></span>
            <h3 id="modalTitle" class="font-bold text-white text-base">Node Inspector</h3>
          </div>
          <button onclick="closeModal()" class="text-slate-400 hover:text-slate-200 text-lg">&times;</button>
        </div>
        <div class="space-y-3 text-xs">
          <div>
            <span class="font-bold text-slate-400 uppercase tracking-wider text-[10px]">Role & Purpose:</span>
            <p id="modalRole" class="text-slate-200 mt-0.5 leading-relaxed font-medium">--</p>
          </div>
          <div>
            <span class="font-bold text-slate-400 uppercase tracking-wider text-[10px]">Tools Executed:</span>
            <p id="modalTools" class="text-indigo-400 mt-0.5 font-mono">--</p>
          </div>
          <div>
            <span class="font-bold text-slate-400 uppercase tracking-wider text-[10px]">Input Data Received:</span>
            <div id="modalInput" class="p-2.5 rounded bg-slate-950 border border-slate-800 font-mono text-[11px] text-slate-300 mt-0.5">--</div>
          </div>
          <div>
            <span class="font-bold text-slate-400 uppercase tracking-wider text-[10px]">Output Data Passed to Scorecard:</span>
            <div id="modalOutput" class="p-2.5 rounded bg-slate-950 border border-slate-800 font-mono text-[11px] text-slate-300 mt-0.5">--</div>
          </div>
        </div>
        <div class="pt-3 border-t border-slate-800 flex justify-end">
          <button onclick="closeModal()" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs rounded-lg transition">Close</button>
        </div>
      </div>
    </div>

    <!-- Comparative Scorecard Table (Dark Mode) -->
    <div class="bg-slate-900 rounded-2xl border border-slate-800 overflow-hidden shadow-xl">
      <div class="p-5 border-b border-slate-800 flex justify-between items-center">
        <div>
          <h3 class="font-bold text-white text-base">Comparative Evaluation Scorecard</h3>
          <p class="text-xs text-slate-400">Live vendor scores evaluated across Technical, Commercial, Experience, and Delivery criteria.</p>
        </div>
        <div id="tableLoading" class="hidden text-xs text-indigo-400 font-semibold flex items-center space-x-1.5">
          <i class="fa-solid fa-spinner animate-spin"></i>
          <span>Evaluating bids across agents...</span>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-slate-800 text-xs text-left">
          <thead class="bg-slate-950/80 text-slate-400 font-bold uppercase tracking-wider text-[11px]">
            <tr>
              <th class="py-3 px-4">Rank</th>
              <th class="py-3 px-4">Bid ID</th>
              <th class="py-3 px-4">Vendor</th>
              <th class="py-3 px-4">Price ($)</th>
              <th class="py-3 px-4">Delivery</th>
              <th id="th-tech" class="py-3 px-4">Technical (40)</th>
              <th id="th-comm" class="py-3 px-4">Commercial (30)</th>
              <th id="th-exp" class="py-3 px-4">Experience (20)</th>
              <th id="th-deliv" class="py-3 px-4">Delivery (10)</th>
              <th class="py-3 px-4">Total (100)</th>
              <th class="py-3 px-4">Status</th>
            </tr>
          </thead>
          <tbody id="scorecardBody" class="divide-y divide-slate-800/60 font-medium text-slate-200">
            <tr>
              <td colspan="11" class="py-8 text-center text-slate-500">Loading scorecard...</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Multi-Agent Audit Trace Log (Dark Mode) -->
    <div class="bg-slate-900 rounded-2xl border border-slate-800 p-5 shadow-xl">
      <h3 class="font-bold text-white text-sm flex items-center space-x-2 mb-3">
        <i class="fa-solid fa-list-check text-indigo-400"></i>
        <span>Multi-Agent Audit Trail (<code class="font-mono text-xs text-indigo-300">logs/run_log.jsonl</code>)</span>
      </h3>
      <div id="traceLog" class="bg-black/95 text-slate-200 font-mono text-[11px] p-4 rounded-xl h-60 overflow-y-auto space-y-1.5 shadow-inner border border-slate-800 custom-scroll">
        <p class="text-slate-500">// Waiting for pipeline execution...</p>
      </div>
    </div>

  </main>

  <footer class="border-t border-slate-800 py-4 text-center text-xs text-slate-500">
    BidWise &bull; Multi-Agent Autonomous Tender Evaluation System &bull; Semantic Kernel & Groq LPU
  </footer>

  <script>
    // State for default baseline and active user configuration
    let systemDefaults = null;
    let activeConfig = {
      weights: { technical: 40.0, commercial: 30.0, experience: 20.0, delivery: 10.0 },
      tie_margin: 2.0,
      secondary_criterion: "delivery_days",
      mandatory_documents: ["Registration Certificate", "Tax Clearance", "EMD Receipt", "Past Experience Certificate"],
      bids: {},
      custom_tender_text: ""
    };

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
        detail: "CriteriaAgent writes parsed/customized weights into shared Scorecard with mutex lock protection."
      },
      {
        step: 3,
        activeIds: ["v-scorecard", "v-bidA", "v-bidB", "v-bidC", "v-bidD"],
        sender: "Scorecard",
        receiver: "Fan-Out Bid Workers",
        type: "FAN_OUT_DISPATCH",
        route: "Scorecard &rarr; Parallel Bid Evaluators",
        detail: "Orchestrator dispatches eligible bids concurrently via asyncio.gather to ComplianceAgent, TechnicalScorer, and CommercialScorer."
      },
      {
        step: 4,
        activeIds: ["v-bidC"],
        disqIds: ["v-bidC"],
        sender: "ComplianceAgent",
        receiver: "Scorecard",
        type: "COMPLIANCE_CHECK",
        route: "ComplianceAgent &rarr; Scorecard (Gatekeeper)",
        detail: "ComplianceAgent verifies mandatory documents against the checklist. Non-compliant proposals are marked DISQUALIFIED."
      },
      {
        step: 5,
        activeIds: ["v-bidA", "v-bidB", "v-bidD", "v-scorecard"],
        sender: "Technical & Commercial Scorers",
        receiver: "Scorecard",
        type: "SLICE_WRITES",
        route: "Scorers &rarr; Scorecard",
        detail: "Scorers record technical rubric points and prices. CommercialScorer calculates normalized score against the lowest compliant quotation."
      },
      {
        step: 6,
        activeIds: ["v-scorecard", "v-award"],
        sender: "Scorecard",
        receiver: "AwardManager",
        type: "FAN_IN_AGGREGATION",
        route: "Scorecard &rarr; AwardManager (Fan-In)",
        detail: "AwardManager reads all slices, filters disqualified bids, applies criteria weights, and computes initial standings."
      },
      {
        step: 7,
        activeIds: ["v-award", "v-tie"],
        sender: "AwardManager",
        receiver: "TieBreakAgent",
        type: "MARGIN_TIE_DETECTED",
        route: "AwardManager &rarr; TieBreakAgent",
        detail: "Score difference evaluated against the tie margin. Secondary criterion (e.g. Delivery Timeline) resolves close standings."
      },
      {
        step: 8,
        activeIds: ["v-tie", "v-bidD", "v-llm"],
        sender: "TieBreakAgent & Groq",
        receiver: "Final Winner",
        type: "AWARD_RECOMMENDATION",
        route: "TieBreakAgent & Groq &rarr; Winner Decision",
        detail: "Winning vendor confirmed. Groq LLM (openai/gpt-oss-120b) synthesizes formal audit-ready procurement justification."
      }
    ];

    let currentFlowIdx = 0;
    let autoPlayInterval = null;

    function updateProgressBar(step, total) {
      const bar = document.getElementById('flowProgressBar');
      if (bar) {
        const pct = Math.min(100, Math.round((step / total) * 100));
        bar.style.width = pct + '%';
      }
    }

    function getSelectedDelay() {
      const select = document.getElementById('flowSpeedSelect');
      return select ? (parseInt(select.value) || 2000) : 2000;
    }

    function updateFlowSpeed() {
      if (autoPlayInterval) {
        clearInterval(autoPlayInterval);
        autoPlayInterval = setInterval(nextFlowStep, getSelectedDelay());
      }
    }

    function applyFlowStep(idx) {
      currentFlowIdx = idx;
      const data = flowSteps[idx];

      document.getElementById('packetStepBadge').textContent = `STEP ${data.step} OF ${flowSteps.length}`;
      document.getElementById('packetRoute').innerHTML = data.route;
      document.getElementById('packetDetail').textContent = data.detail;
      document.getElementById('packetActionType').textContent = data.type;

      updateProgressBar(data.step, flowSteps.length);

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
        autoPlayInterval = setInterval(nextFlowStep, getSelectedDelay());
      }
    }

    function resetFlow() {
      if (autoPlayInterval) toggleAutoPlay();
      applyFlowStep(0);
    }

    // Node Inspector details
    const nodeDetails = {
      'tender': {
        icon: '<i class="fa-solid fa-file-contract text-indigo-400"></i>',
        title: "Tender Corpus (data/tender.txt)",
        role: "Authoritative procurement document specifying campus network infrastructure requirements.",
        tools: "Clause chunking parser (numbered clauses 1 through 7)",
        input: "Digital sealed tender specification",
        output: "Clause 4 (Criteria: Tech 40%, Comm 30%, Exp 20%, Delivery 10%), Clause 5 (Mandatory Documents)"
      },
      'crit': {
        icon: '<i class="fa-solid fa-brain text-sky-400"></i>',
        title: "CriteriaAgent (RAG Agent)",
        role: "Autonomous agent retrieving criteria, weights, and compliance rules dynamically without hardcoding.",
        tools: "retrieve_clauses(query), parse_weights(text), parse_mandatory_docs(text)",
        input: "Tender text clauses via in-memory TF-IDF vectorizer",
        output: "Weights dictionary & Mandatory checklist"
      },
      'scorecard': {
        icon: '<i class="fa-solid fa-database text-amber-400"></i>',
        title: "Shared Scorecard (Thread-Safe Central Memory)",
        role: "Central shared dataclass maintaining bid slices, compliance states, events, and final award under asyncio.Lock.",
        tools: "Scorecard.update_technical_slice, update_commercial_slice, update_compliance_slice, update_totals_and_ranks",
        input: "Parallel slice updates from all 6 agents",
        output: "Unified evaluation matrix & immutable append-only logs in logs/run_log.jsonl"
      },
      'bidA': {
        icon: '<i class="fa-solid fa-building text-emerald-400"></i>',
        title: "Bid A Evaluation Lane (Alpha Networks)",
        role: "Strong technical bidder with mid-tier commercial quotation.",
        tools: "check_required_docs, extract_bid_features, score_against_rubric",
        input: "bid_A: $125,000, 45 days, 12 years exp, ISO 9001/27001, 25 engineers",
        output: "Compliant: True | Tech: 40/40, Exp: 20/20, Comm: 24.00, Deliv: 7.00 | Total: 91.00"
      },
      'bidB': {
        icon: '<i class="fa-solid fa-building text-emerald-400"></i>',
        title: "Bid B Evaluation Lane (Beta Infrastructure)",
        role: "Lowest cost bidder setting the commercial baseline for normalization.",
        tools: "normalize_price, check_payment_terms, score_against_rubric",
        input: "bid_B: $100,000 (Lowest), 60 days, 6 years exp, ISO 9001, 15 engineers",
        output: "Compliant: True | Tech: 25.5/40, Exp: 12/20, Comm: 30.00, Deliv: 5.00 | Total: 72.50"
      },
      'bidC': {
        icon: '<i class="fa-solid fa-triangle-exclamation text-rose-400"></i>',
        title: "Bid C Evaluation Lane (Gamma Systems)",
        role: "High-spec bidder evaluated against mandatory compliance rules.",
        tools: "check_required_docs(bid_text, required_docs)",
        input: "bid_C: Checks for EMD Receipt, Registration, Tax, Experience",
        output: "Subject to compliance gatekeeper (disqualified if EMD missing)"
      },
      'bidD': {
        icon: '<i class="fa-solid fa-building text-amber-400"></i>',
        title: "Bid D Evaluation Lane (Delta Communications)",
        role: "Fastest delivery bidder qualifying for margin tie-break victory.",
        tools: "score_against_rubric, apply_secondary_criterion",
        input: "bid_D: $115,000, 20 days delivery, 8 years exp, ISO 9001/27001, 20 engineers",
        output: "Compliant: True | Tech: 40/40, Exp: 16/20, Comm: 26.09, Deliv: 10.00 | Total: 92.09"
      },
      'award': {
        icon: '<i class="fa-solid fa-scale-balanced text-emerald-400"></i>',
        title: "AwardManager (Fan-In Aggregator)",
        role: "Fuses per-bid slices, applies criteria weights, filters disqualified bids, and ranks candidates.",
        tools: "apply_weights(scores, weights), rank_bids(totals)",
        input: "Aggregated bid slices from central Scorecard",
        output: "Ranked standings and margin checks"
      },
      'tie': {
        icon: '<i class="fa-solid fa-handshake-angle text-indigo-400"></i>',
        title: "TieBreakAgent (Margin Resolver)",
        role: "Detects score differences <= tie margin and resolves award via secondary tender criterion.",
        tools: "detect_ties(ranked, margin), apply_secondary_criterion(bids, rule)",
        input: "Top 2 candidate score differential",
        output: "Tie-break resolution based on selected secondary rule"
      },
      'llm': {
        icon: '<i class="fa-solid fa-microchip text-orange-400"></i>',
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

    // Toggle Config Drawer
    function toggleConfigPanel() {
      const p = document.getElementById('configPanel');
      p.classList.toggle('hidden');
    }

    function switchConfigTab(tabName) {
      const tabs = ['weights', 'tiebreak', 'compliance', 'bids', 'tender'];
      tabs.forEach(t => {
        const btn = document.getElementById('tabBtn-' + t);
        const content = document.getElementById('tabContent-' + t);
        if (t === tabName) {
          btn.className = "px-3 py-1.5 rounded-lg bg-indigo-600 text-white transition";
          content.classList.remove('hidden');
        } else {
          btn.className = "px-3 py-1.5 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white transition";
          content.classList.add('hidden');
        }
      });
    }

    // Sliders & Weights Handling
    function updateWeightsFromSliders() {
      const tech = parseFloat(document.getElementById('input-wt-tech').value) || 0;
      const comm = parseFloat(document.getElementById('input-wt-comm').value) || 0;
      const exp = parseFloat(document.getElementById('input-wt-exp').value) || 0;
      const deliv = parseFloat(document.getElementById('input-wt-deliv').value) || 0;

      document.getElementById('display-wt-tech').textContent = tech + '%';
      document.getElementById('display-wt-comm').textContent = comm + '%';
      document.getElementById('display-wt-exp').textContent = exp + '%';
      document.getElementById('display-wt-deliv').textContent = deliv + '%';

      const sum = tech + comm + exp + deliv;
      const sumEl = document.getElementById('totalWeightSum');
      sumEl.textContent = sum + '%';
      if (Math.abs(sum - 100) > 0.01) {
        sumEl.className = "font-mono text-amber-400 font-bold";
      } else {
        sumEl.className = "font-mono text-emerald-400 font-bold";
      }

      activeConfig.weights = { technical: tech, commercial: comm, experience: exp, delivery: deliv };
      markConfigCustom();
    }

    function normalizeSlidersTo100() {
      const tech = parseFloat(document.getElementById('input-wt-tech').value) || 0;
      const comm = parseFloat(document.getElementById('input-wt-comm').value) || 0;
      const exp = parseFloat(document.getElementById('input-wt-exp').value) || 0;
      const deliv = parseFloat(document.getElementById('input-wt-deliv').value) || 0;
      const sum = tech + comm + exp + deliv;
      if (sum <= 0) return;

      const nTech = Math.round((tech / sum) * 100);
      const nComm = Math.round((comm / sum) * 100);
      const nExp = Math.round((exp / sum) * 100);
      const nDeliv = 100 - (nTech + nComm + nExp);

      document.getElementById('input-wt-tech').value = nTech;
      document.getElementById('input-wt-comm').value = nComm;
      document.getElementById('input-wt-exp').value = nExp;
      document.getElementById('input-wt-deliv').value = nDeliv;

      updateWeightsFromSliders();
    }

    function markConfigCustom() {
      const badge = document.getElementById('configModeBadge');
      if (badge) {
        badge.className = "text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800";
        badge.textContent = "Custom Overrides Active";
      }
    }

    // Mandatory Compliance Documents Handling
    function renderMandatoryDocs() {
      const container = document.getElementById('mandatoryDocsContainer');
      container.innerHTML = '';
      activeConfig.mandatory_documents.forEach((doc, idx) => {
        const span = document.createElement('span');
        span.className = "inline-flex items-center space-x-1.5 px-3 py-1 rounded-lg bg-slate-900 border border-slate-700 text-xs text-slate-200";
        span.innerHTML = `
          <i class="fa-solid fa-file-shield text-indigo-400 text-[10px]"></i>
          <span>${doc}</span>
          <button onclick="removeMandatoryDoc(${idx})" class="text-slate-400 hover:text-rose-400 ml-1">&times;</button>
        `;
        container.appendChild(span);
      });
    }

    function addMandatoryDoc() {
      const input = document.getElementById('newDocInput');
      const val = input.value.trim();
      if (val && !activeConfig.mandatory_documents.includes(val)) {
        activeConfig.mandatory_documents.push(val);
        input.value = '';
        renderMandatoryDocs();
        markConfigCustom();
      }
    }

    function removeMandatoryDoc(idx) {
      activeConfig.mandatory_documents.splice(idx, 1);
      renderMandatoryDocs();
      markConfigCustom();
    }

    // Vendor Bids Handling
    function renderBidsGrid() {
      const grid = document.getElementById('bidsGrid');
      grid.innerHTML = '';

      Object.keys(activeConfig.bids).forEach(bidId => {
        const b = activeConfig.bids[bidId];
        const card = document.createElement('div');
        card.className = "bg-slate-950/70 p-4 rounded-xl border border-slate-800 space-y-3";
        
        const docsList = ["Registration Certificate", "Tax Clearance", "EMD Receipt", "Experience Certificate"];
        let docCheckboxes = docsList.map(d => {
          const isChecked = b.submitted_docs && b.submitted_docs.some(sd => sd.toLowerCase().includes(d.toLowerCase().split(' ')[0]));
          return `
            <label class="flex items-center space-x-1.5 text-[11px] text-slate-400 cursor-pointer">
              <input type="checkbox" ${isChecked ? 'checked' : ''} onchange="toggleBidDoc('${bidId}', '${d}', this.checked)" class="rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-0">
              <span>${d.replace(' Certificate', '')}</span>
            </label>
          `;
        }).join('');

        card.innerHTML = `
          <div class="flex items-center justify-between pb-2 border-b border-slate-800">
            <div class="flex items-center space-x-2">
              <input type="checkbox" id="check-${bidId}" ${b.enabled ? 'checked' : ''} onchange="activeConfig.bids['${bidId}'].enabled = this.checked; markConfigCustom();" class="rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-0">
              <span class="font-mono font-bold text-white text-xs">${bidId}</span>
            </div>
            <span class="text-[10px] text-slate-500 font-mono">${bidId === 'bid_C' ? 'Default Disqualified' : 'Compliant'}</span>
          </div>

          <div class="space-y-2 text-xs">
            <div>
              <label class="text-[10px] uppercase font-bold text-slate-500">Vendor Name</label>
              <input type="text" value="${b.vendor_name || ''}" onchange="activeConfig.bids['${bidId}'].vendor_name = this.value; markConfigCustom();" class="w-full bg-slate-900 border border-slate-700 text-slate-200 rounded px-2 py-1 text-xs focus:outline-none focus:border-indigo-500">
            </div>

            <div class="grid grid-cols-2 gap-2">
              <div>
                <label class="text-[10px] uppercase font-bold text-slate-500">Price ($)</label>
                <input type="number" value="${b.price || 0}" step="1000" onchange="activeConfig.bids['${bidId}'].price = parseFloat(this.value); markConfigCustom();" class="w-full bg-slate-900 border border-slate-700 text-slate-200 font-mono rounded px-2 py-1 text-xs focus:outline-none focus:border-indigo-500">
              </div>
              <div>
                <label class="text-[10px] uppercase font-bold text-slate-500">Delivery (Days)</label>
                <input type="number" value="${b.delivery_days || 0}" onchange="activeConfig.bids['${bidId}'].delivery_days = parseInt(this.value); markConfigCustom();" class="w-full bg-slate-900 border border-slate-700 text-slate-200 font-mono rounded px-2 py-1 text-xs focus:outline-none focus:border-indigo-500">
              </div>
            </div>

            <div class="grid grid-cols-2 gap-2">
              <div>
                <label class="text-[10px] uppercase font-bold text-slate-500">Exp (Years)</label>
                <input type="number" value="${b.years_of_experience || 0}" onchange="activeConfig.bids['${bidId}'].years_of_experience = parseInt(this.value); markConfigCustom();" class="w-full bg-slate-900 border border-slate-700 text-slate-200 font-mono rounded px-2 py-1 text-xs focus:outline-none focus:border-indigo-500">
              </div>
              <div>
                <label class="text-[10px] uppercase font-bold text-slate-500">Team Size</label>
                <input type="number" value="${b.team_size || 0}" onchange="activeConfig.bids['${bidId}'].team_size = parseInt(this.value); markConfigCustom();" class="w-full bg-slate-900 border border-slate-700 text-slate-200 font-mono rounded px-2 py-1 text-xs focus:outline-none focus:border-indigo-500">
              </div>
            </div>

            <div class="pt-2 border-t border-slate-800 space-y-1">
              <label class="text-[10px] uppercase font-bold text-slate-500 block">Submitted Docs</label>
              ${docCheckboxes}
            </div>
          </div>
        `;
        grid.appendChild(card);
      });
    }

    function toggleBidDoc(bidId, docName, isChecked) {
      const bid = activeConfig.bids[bidId];
      if (!bid.submitted_docs) bid.submitted_docs = [];
      if (isChecked) {
        if (!bid.submitted_docs.includes(docName)) bid.submitted_docs.push(docName);
      } else {
        bid.submitted_docs = bid.submitted_docs.filter(d => !d.toLowerCase().includes(docName.toLowerCase().split(' ')[0]));
      }
      markConfigCustom();
    }

    function addCustomBid() {
      const newId = 'bid_' + String.fromCharCode(65 + Object.keys(activeConfig.bids).length);
      activeConfig.bids[newId] = {
        vendor_name: "Custom Enterprise Ltd",
        price: 105000,
        delivery_days: 28,
        years_of_experience: 9,
        team_size: 18,
        similar_projects: 5,
        certifications: ["ISO 9001", "ISO 27001"],
        submitted_docs: ["Registration Certificate", "Tax Clearance", "EMD Receipt", "Experience Certificate"],
        enabled: true
      };
      renderBidsGrid();
      markConfigCustom();
    }

    function reloadDefaultTenderText() {
      if (systemDefaults && systemDefaults.tender_text) {
        document.getElementById('tenderTextArea').value = systemDefaults.tender_text;
        activeConfig.custom_tender_text = "";
      }
    }

    // Reset to defaults
    async function resetToDefaults() {
      try {
        if (!systemDefaults) {
          const res = await fetch('/api/defaults');
          systemDefaults = await res.json();
        }
        
        // Deep copy defaults
        activeConfig.weights = JSON.parse(JSON.stringify(systemDefaults.weights));
        activeConfig.tie_margin = systemDefaults.tie_margin;
        activeConfig.secondary_criterion = systemDefaults.secondary_criterion;
        activeConfig.mandatory_documents = JSON.parse(JSON.stringify(systemDefaults.mandatory_documents));
        activeConfig.bids = JSON.parse(JSON.stringify(systemDefaults.bids));
        activeConfig.custom_tender_text = "";

        // Update inputs
        document.getElementById('input-wt-tech').value = activeConfig.weights.technical;
        document.getElementById('input-wt-comm').value = activeConfig.weights.commercial;
        document.getElementById('input-wt-exp').value = activeConfig.weights.experience;
        document.getElementById('input-wt-deliv').value = activeConfig.weights.delivery;
        document.getElementById('input-tie-margin').value = activeConfig.tie_margin;
        document.getElementById('input-secondary-rule').value = activeConfig.secondary_criterion;
        document.getElementById('tenderTextArea').value = systemDefaults.tender_text || '';

        updateWeightsFromSliders();
        renderMandatoryDocs();
        renderBidsGrid();

        const badge = document.getElementById('configModeBadge');
        if (badge) {
          badge.className = "text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700";
          badge.textContent = "Default Baseline Active";
        }
      } catch (err) {
        console.error("Failed to reset defaults:", err);
      }
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

      // Sync active parameters from inputs
      activeConfig.tie_margin = parseFloat(document.getElementById('input-tie-margin').value) || 2.0;
      activeConfig.secondary_criterion = document.getElementById('input-secondary-rule').value || 'delivery_days';
      const tenderText = document.getElementById('tenderTextArea').value.trim();
      if (systemDefaults && tenderText !== systemDefaults.tender_text) {
        activeConfig.custom_tender_text = tenderText;
      }

      const selected_bids = Object.keys(activeConfig.bids).filter(k => activeConfig.bids[k].enabled);

      const requestPayload = {
        selected_bids: selected_bids.length ? selected_bids : null,
        custom_weights: activeConfig.weights,
        tie_margin: activeConfig.tie_margin,
        secondary_criterion: activeConfig.secondary_criterion,
        mandatory_documents: activeConfig.mandatory_documents,
        custom_bids: activeConfig.bids,
        custom_tender_text: activeConfig.custom_tender_text || null
      };

      // 1. Kick off real backend evaluation in the background
      const evalPromise = fetch('/api/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestPayload)
      }).then(async res => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: "Evaluation failed" }));
          throw new Error(err.detail || "Evaluation request failed");
        }
        return res.json();
      });

      try {
        const stepDelay = getSelectedDelay();

        // 2. Visibly step through all 8 multi-agent pipeline stages sequentially
        for (let i = 0; i < flowSteps.length; i++) {
          applyFlowStep(i);
          await new Promise(resolve => setTimeout(resolve, stepDelay));
        }

        // 3. Await final data and render scorecard table & winner decision
        const data = await evalPromise;
        renderScorecard(data);
      } catch (err) {
        alert("Evaluation error: " + err.message);
      } finally {
        btn.disabled = false;
        btn.classList.remove('opacity-50', 'cursor-not-allowed');
        loader.classList.add('hidden');
      }
    }

    function renderScorecard(data) {
      if (!data || !data.bids) return;

      // Update table headers to match criteria weights
      const w = (data.criteria && data.criteria.weights) ? data.criteria.weights : activeConfig.weights;
      if (w) {
        if (w.technical !== undefined) document.getElementById('th-tech').textContent = `Technical (${Math.round(w.technical)})`;
        if (w.commercial !== undefined) document.getElementById('th-comm').textContent = `Commercial (${Math.round(w.commercial)})`;
        if (w.experience !== undefined) document.getElementById('th-exp').textContent = `Experience (${Math.round(w.experience)})`;
        if (w.delivery !== undefined) document.getElementById('th-deliv').textContent = `Delivery (${Math.round(w.delivery)})`;
      }

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
        if (isWinner) tr.classList.add('bg-amber-950/20', 'border-l-4', 'border-amber-500');

        const priceStr = b.price ? '$' + Number(b.price).toLocaleString() : '-';
        const deliveryStr = b.delivery_days ? b.delivery_days + ' days' : '-';
        const rankStr = b.disqualified ? '<span class="text-rose-500 font-bold">-</span>' : `<b class="text-slate-100">${b.rank}</b>`;
        const totalStr = b.disqualified ? '0.00' : Number(b.total || 0).toFixed(2);
        
        const statusBadge = b.disqualified
          ? `<span class="badge-fail px-2 py-0.5 rounded text-[10px] font-bold">Disqualified (${b.disqualification_reason || 'Failed'})</span>`
          : (isWinner 
              ? `<span class="badge-winner px-2 py-0.5 rounded text-[10px] font-bold">Recommended Winner</span>`
              : `<span class="badge-pass px-2 py-0.5 rounded text-[10px] font-bold">Compliant</span>`);

        tr.innerHTML = `
          <td class="py-3 px-4">${rankStr}</td>
          <td class="py-3 px-4 font-mono font-bold ${isWinner ? 'text-amber-400' : 'text-slate-200'}">${b.bid_id}</td>
          <td class="py-3 px-4 text-slate-300">${b.vendor_name || b.bid_id}</td>
          <td class="py-3 px-4 font-mono text-slate-300">${priceStr}</td>
          <td class="py-3 px-4 text-slate-300">${deliveryStr}</td>
          <td class="py-3 px-4 font-mono text-slate-300">${s.technical !== undefined ? s.technical.toFixed(2) : '-'}</td>
          <td class="py-3 px-4 font-mono text-slate-300">${s.commercial !== undefined && !b.disqualified ? s.commercial.toFixed(2) : '-'}</td>
          <td class="py-3 px-4 font-mono text-slate-300">${s.experience !== undefined ? s.experience.toFixed(2) : '-'}</td>
          <td class="py-3 px-4 font-mono text-slate-300">${s.delivery !== undefined ? s.delivery.toFixed(2) : '-'}</td>
          <td class="py-3 px-4 font-black font-mono ${isWinner ? 'text-amber-400 text-sm' : 'text-slate-100'}">${totalStr}</td>
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
          div.innerHTML = `<span class="text-slate-500">[${evt.timestamp.substring(11, 19)}]</span> <span class="text-indigo-400 font-bold">[${evt.agent}]</span> <span class="text-amber-400 font-bold">${evt.action.toUpperCase()}</span>: <span class="text-slate-300">${evt.detail}</span>`;
          traceBox.appendChild(div);
        });
        traceBox.scrollTop = traceBox.scrollHeight;
      }
    }

    window.addEventListener('DOMContentLoaded', async () => {
      applyFlowStep(0);
      await resetToDefaults();
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
    print(f" Starting BidWise Multi-Agent Visualizer (Dark Mode) on port {args.port}...")
    print(f" Dashboard URL : http://localhost:{args.port}")
    print(f" API Docs URL  : http://localhost:{args.port}/docs")
    print(f"=======================================================\n")

    uvicorn.run("app:app", host=args.host, port=args.port, reload=args.reload)
