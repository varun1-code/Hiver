"""Three intent classifiers, in increasing sophistication:

1. majority   -- trivial baseline, always predicts one constant label.
2. keyword    -- simple baseline, deterministic keyword/regex rules.
3. llm        -- the "real" system, the configured LLM (see config.LLM_PROVIDER;
   Hive by default, Gemini optional) with the taxonomy in-context.

See config.INTENTS for the taxonomy and its rationale.
"""
import json
import re

from src.config import INTENT_NAMES, INTENTS
from src.llm_client import generate_json

# ---- 1. Trivial baseline ---------------------------------------------------

def majority_classifier(_text: str, majority_label: str) -> str:
    return majority_label


# ---- 2. Simple keyword baseline -------------------------------------------
# Ordered rules: first matching rule wins. Order encodes priority (e.g. a
# safety/billing complaint should not be masked by a generic "how do I" hit).

_KEYWORD_RULES = [
    ("account_access", re.compile(
        r"\b(apple ?id|icloud|2fa|two.factor|locked out|can'?t (log|sign) ?in|"
        r"password reset|forgot my password)\b", re.I)),
    ("billing_purchase", re.compile(
        r"\b(refund|charged|charge|billing|subscription|app store purchase|"
        r"payment|receipt|cancel my (subscription|order))\b", re.I)),
    ("hardware_malfunction", re.compile(
        r"\b(screen (crack|broken|black)|keyboard|touchpad|touch ?screen|"
        r"battery (drain|swell|die)|won'?t charge|speaker|camera|button)\b", re.I)),
    ("connectivity_issue", re.compile(
        r"\b(bluetooth|wi.?fi|wifi|cellular|no signal|can'?t connect|pairing|"
        r"disconnect)\b", re.I)),
    ("update_install_issue", re.compile(
        r"\b(update (stuck|fail|won'?t|slow)|updating|upgrade|install(ing)? "
        r"(ios|update)|stuck on (the )?apple logo)\b", re.I)),
    ("software_bug_after_update", re.compile(
        r"\b(crash|freeze|freezing|kernel panic|bug|glitch|broke(n)? after|"
        r"since (the )?(ios|update)|random(ly)? (restart|shut ?down))\b", re.I)),
    ("how_to_question", re.compile(
        r"\b(how do i|how to|is there a way|can i|where is)\b", re.I)),
]


def keyword_classifier(text: str) -> str:
    for label, pattern in _KEYWORD_RULES:
        if pattern.search(text):
            return label
    return "complaint_feedback"


# ---- 3. LLM classifier ------------------------------------------------------

_CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": INTENT_NAMES},
        "confidence": {"type": "number"},
        "rationale": {"type": "string"},
    },
    "required": ["intent", "confidence", "rationale"],
}


def _build_taxonomy_block() -> str:
    return "\n".join(f"- {name}: {desc}" for name, desc in INTENTS.items())


def llm_classifier(text: str) -> dict:
    """Returns {"intent", "confidence", "rationale"}."""
    prompt = f"""You are classifying an inbound customer support tweet directed at
@AppleSupport into exactly one intent category.

Categories:
{_build_taxonomy_block()}

Tweet:
\"\"\"{text}\"\"\"

Pick the single best-fitting category. If multiple apply, pick the most
specific/actionable one over "complaint_feedback". Return confidence as your
genuine estimate of correctness in [0,1], calibrated -- do not default to a
round number like 0.9 unless you are actually that certain."""
    result = generate_json(prompt, json_schema=_CLASSIFY_SCHEMA, temperature=0.0, max_output_tokens=256)
    if result.get("intent") not in INTENT_NAMES:
        result["intent"] = "complaint_feedback"
    return result
