"""Constants and configuration for Provenance Guard.

Mirrors the role of `config.py` in the RepairSafe Lab 4 starter: a single place for
the API key, model name, log path, scoring thresholds, and valid attribution labels.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# --- Groq (Signal 1) ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

# --- Audit log ---
LOG_PATH = os.path.join(os.path.dirname(__file__), "logs", "audit.jsonl")

# --- Confidence-score thresholds (see planning.md §2) ---
# p_ai = estimated probability the text is AI-generated, in [0, 1].
# Asymmetric on purpose: asserting "AI" requires strong evidence (>= 0.80) so that
# borderline cases degrade to "uncertain" rather than falsely accusing a human writer.
AI_THRESHOLD = 0.80      # p_ai >= this  -> likely_ai
HUMAN_THRESHOLD = 0.30   # p_ai <= this  -> likely_human
# between the two -> uncertain

VALID_ATTRIBUTIONS = ["likely_ai", "uncertain", "likely_human"]

# --- Signal combination weights (used in Milestone 4) ---
LLM_WEIGHT = 0.6
STYLE_WEIGHT = 0.4

# --- Rate limiting (Milestone 5; see README for reasoning) ---
# A real creator submits their own work a handful of times; these limits absorb editing
# bursts while blocking a script that tries to flood the endpoint.
SUBMIT_RATE_LIMIT = "10 per minute;100 per day"
