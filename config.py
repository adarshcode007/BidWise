"""Configuration for Tender and Procurement Evaluation System (CSE476, Task 2, Group 19).

Reads environment variables and .env file for Groq API keys, model lanes, thresholds, and paths.
"""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Base directories
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
BIDS_DIR = DATA_DIR / "bids"
LOGS_DIR = BASE_DIR / "logs"
OUTPUT_DIR = BASE_DIR / "output"
DOCS_DIR = BASE_DIR / "docs"

# Load environment variables from .env file
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH, override=True)
else:
    load_dotenv()

# Ensure runtime directories exist
LOGS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(parents=True, exist_ok=True)

# File paths
TENDER_PATH = DATA_DIR / "tender.txt"
RUBRIC_PATH = DATA_DIR / "rubric.json"
RUN_LOG_PATH = LOGS_DIR / "run_log.jsonl"
REPORT_OUTPUT_PATH = OUTPUT_DIR / "report.md"
SCORECARD_OUTPUT_PATH = OUTPUT_DIR / "scorecard.json"

# Evaluation Thresholds & Policies
TIE_MARGIN = float(os.getenv("TIE_MARGIN", "2.0"))

# Groq API Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip()

# Compatibility alias
OPENAI_API_KEY = GROQ_API_KEY

def has_groq_api_key() -> bool:
    """Returns True if a valid non-placeholder Groq API key is configured."""
    return bool(GROQ_API_KEY) and not GROQ_API_KEY.startswith("your_groq_api_key")

# LLM & Operational Flags
# If a valid Groq API key is detected, default to USE_LLM=True unless explicitly overridden
_env_use_llm = os.getenv("USE_LLM")
if _env_use_llm is not None:
    USE_LLM = _env_use_llm.lower() in ("true", "1", "yes")
else:
    USE_LLM = has_groq_api_key()

_env_offline = os.getenv("OFFLINE_MODE")
if _env_offline is not None:
    OFFLINE_MODE = _env_offline.lower() in ("true", "1", "yes")
else:
    OFFLINE_MODE = not has_groq_api_key()
