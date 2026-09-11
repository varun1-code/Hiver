"""Central configuration: paths, brand, model names, taxonomy."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_CSV = ROOT / "reports" / "twcs" / "twcs.csv"
CASES_PATH = ROOT / "data" / "cases.jsonl"
REFERENCE_POOL_PATH = ROOT / "data" / "reference_pool.jsonl"
EVAL_POOL_PATH = ROOT / "data" / "eval_pool.jsonl"
GOLDEN_TEMPLATE_PATH = ROOT / "data" / "golden_template.jsonl"
GOLDEN_PATH = ROOT / "data" / "golden.jsonl"
REPORTS_DIR = ROOT / "reports"

BRAND = "AppleSupport"

# Model used for every LLM call in the pipeline (classification, generation, judging).
# Kept to a single cheap/fast model so the whole eval run is inexpensive and reproducible.
# NOTE: "gemini-flash-latest" (-> gemini-3.8-flash on this key) has only a
# 20-REQUESTS-PER-DAY free quota, exhausted almost immediately during
# development. "gemini-flash-lite-latest" (-> gemini-3.5-flash-lite) has a
# separate, much more usable 15-REQUESTS-PER-MINUTE quota. See README.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

# How many historical cases to build from the raw dump, and how the reference/eval
# split is drawn. Grouped by thread root so no thread crosses the split (leakage guard).
N_CASES_TARGET = 8000
EVAL_POOL_FRACTION = 0.25  # fraction of cases held out from retrieval for evaluation/golden sampling
RANDOM_SEED = 42

# ---- Intent taxonomy -------------------------------------------------------
# Derived empirically from ~50k AppleSupport-directed first-turn tweets (see
# scripts/exploration/00_explore_full.py). Kept small and mutually exclusive by
# design -- see decision log for what was deliberately left out (no 77-way
# Banking77-style taxonomy; no separate "spam/unrelated" class beyond OTHER).
INTENTS = {
    "software_bug_after_update": (
        "Device or OS behaves incorrectly (freezing, crashing, kernel panics, "
        "battery drain, features broken) especially after an iOS/macOS update."
    ),
    "update_install_issue": (
        "Problem with the update/upgrade process itself: stuck, slow, failing to "
        "download or install, or asking how to update."
    ),
    "hardware_malfunction": (
        "Physical device fault: screen, keyboard, touchpad, button, camera, "
        "speaker, or battery/charging hardware not working."
    ),
    "connectivity_issue": (
        "Bluetooth, WiFi, cellular, or pairing problems."
    ),
    "account_access": (
        "Apple ID, iCloud, two-factor auth, password reset, or being locked out "
        "of an account/service."
    ),
    "billing_purchase": (
        "App Store or subscription charges, refunds, failed purchases, or "
        "billing disputes."
    ),
    "how_to_question": (
        "Customer is asking how to use a feature (Siri, Settings, backups, "
        "transfers, etc.) without reporting something broken."
    ),
    "complaint_feedback": (
        "General venting, sarcasm, or negative/positive feedback about Apple "
        "with no specific actionable technical request."
    ),
}

INTENT_NAMES = list(INTENTS.keys())

# Keywords/phrases that push a case toward escalation regardless of intent
# confidence. Kept explicit and auditable rather than learned.
ESCALATION_SIGNAL_KEYWORDS = [
    "lawyer", "legal action", "sue", "class action", "fraud", "stolen",
    "hacked", "unauthorized charge", "safety", "fire", "smoke", "explod",
    "injur", "refund now", "cancel my account", "delete my account",
    "discriminat", "threat", "self harm", "suicide",
]

ESCALATION_REQUEST_PHRASES = [
    "speak to a human", "talk to a person", "call me", "phone call",
    "real person", "manager", "supervisor", "escalate",
]
