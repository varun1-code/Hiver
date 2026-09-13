"""Three end-to-end system tiers, run over the same case schema so their
outputs are directly comparable in evaluate.py.

- trivial: majority-class intent, constant canned reply, always auto-handle.
  This is the "what if we shipped nothing" floor -- it exists specifically
  to make the escalation logic's value legible (see decision log / report).
- simple:  keyword classifier + retrieval-copy reply + rule-based escalation.
- llm:     LLM classifier + retrieval-grounded LLM reply (Hive by default,
  Gemini optional -- see config.LLM_PROVIDER) + the same rule-based
  escalation (escalation logic is shared on purpose -- it is the one
  component we do NOT want to vary by system tier, see escalation.py).
"""
from src.classifiers import majority_classifier, keyword_classifier, llm_classifier
from src.escalation import decide
from src.reply_drafters import template_reply, llm_rag_reply, GENERIC_FALLBACK
from src.retrieval import CaseRetriever
from src.text_utils import clean_for_matching

# Fixed confidence used for the simple baseline. It has no real notion of
# confidence, so we assign a constant value (documented as such) purely so it
# can flow through the same escalation.decide() used by every tier.
SIMPLE_BASELINE_CONFIDENCE = 0.70


def run_trivial(customer_text: str, majority_label: str) -> dict:
    intent = majority_classifier(customer_text, majority_label)
    esc = {"auto_handle": True, "reason": "Trivial baseline: no escalation logic, everything is auto-handled."}
    return {
        "system": "trivial",
        "intent": intent,
        "intent_confidence": None,
        "reply": GENERIC_FALLBACK,
        "grounded": False,
        "auto_handle": esc["auto_handle"],
        "escalation_reason": esc["reason"],
        "top_similarity": None,
    }


def run_simple(customer_text: str, retriever: CaseRetriever) -> dict:
    clean = clean_for_matching(customer_text)
    intent = keyword_classifier(customer_text)
    retrieved = retriever.retrieve(clean, k=3)
    top_sim = retrieved[0].similarity if retrieved else 0.0
    esc = decide(customer_text, intent, SIMPLE_BASELINE_CONFIDENCE, top_sim)
    drafted = template_reply(retrieved)
    return {
        "system": "simple",
        "intent": intent,
        "intent_confidence": SIMPLE_BASELINE_CONFIDENCE,
        "reply": drafted["reply"],
        "grounded": drafted["grounded"],
        "auto_handle": esc["auto_handle"],
        "escalation_reason": esc["reason"],
        "top_similarity": top_sim,
        "evidence_case_ids": [drafted["source_case_id"]] if drafted.get("source_case_id") else [],
    }


def run_llm(customer_text: str, retriever: CaseRetriever) -> dict:
    clean = clean_for_matching(customer_text)
    cls = llm_classifier(customer_text)
    intent, confidence = cls["intent"], float(cls.get("confidence", 0.5))
    retrieved = retriever.retrieve(clean, k=3)
    top_sim = retrieved[0].similarity if retrieved else 0.0
    esc = decide(customer_text, intent, confidence, top_sim)
    drafted = llm_rag_reply(customer_text, retrieved)
    return {
        "system": "llm",
        "intent": intent,
        "intent_confidence": confidence,
        "intent_rationale": cls.get("rationale"),
        "reply": drafted["reply"],
        "grounded": drafted["grounded"],
        "auto_handle": esc["auto_handle"],
        "escalation_reason": esc["reason"],
        "top_similarity": top_sim,
        "evidence_case_ids": drafted.get("source_case_ids", []),
    }
