"""Rule-based auto-handle / escalate decision.

Deliberately NOT delegated to the LLM: this is the one decision in the
pipeline with real downstream cost (a wrongly auto-handled account-security
or billing case), so it stays as auditable, testable if/else logic with a
human-readable reason attached to every decision. See decision log.
"""
import re

from src.config import ESCALATION_SIGNAL_KEYWORDS, ESCALATION_REQUEST_PHRASES

_RISK_RE = re.compile("|".join(re.escape(k) for k in ESCALATION_SIGNAL_KEYWORDS), re.I)
_REQUEST_RE = re.compile("|".join(re.escape(k) for k in ESCALATION_REQUEST_PHRASES), re.I)

CONFIDENCE_FLOOR = 0.55
SIMILARITY_FLOOR = 0.12

# Intents where even a confident, well-grounded reply still shouldn't be
# auto-sent, because the action needed requires authority the bot doesn't have.
NEVER_AUTO_INTENTS = {"billing_purchase", "account_access"}


def decide(
    customer_text: str,
    intent: str,
    intent_confidence: float,
    top_similarity: float,
) -> dict:
    """Returns {"auto_handle": bool, "reason": str}."""
    if _RISK_RE.search(customer_text):
        return {"auto_handle": False, "reason": "Message contains a high-risk keyword (safety/legal/fraud) requiring human review."}

    if _REQUEST_RE.search(customer_text):
        return {"auto_handle": False, "reason": "Customer explicitly asked for a human/manager."}

    if intent in NEVER_AUTO_INTENTS:
        return {"auto_handle": False, "reason": f"Intent '{intent}' involves account security or money and requires human authorization/identity verification."}

    if intent_confidence < CONFIDENCE_FLOOR:
        return {"auto_handle": False, "reason": f"Classifier confidence {intent_confidence:.2f} is below the {CONFIDENCE_FLOOR} floor; too uncertain to auto-handle."}

    if top_similarity < SIMILARITY_FLOOR:
        return {"auto_handle": False, "reason": f"No sufficiently similar historical resolution found (top similarity {top_similarity:.2f} < {SIMILARITY_FLOOR}); reply would not be grounded."}

    return {"auto_handle": True, "reason": f"High-confidence '{intent}' classification ({intent_confidence:.2f}) with a close historical precedent (similarity {top_similarity:.2f}) in a low-risk category."}
