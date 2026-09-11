"""LLM-as-judge for drafted-reply quality.

Scores a drafted reply 1-5 on four dimensions plus an overall score. The
judge only ever sees the customer message and the drafted reply (and, when
available, the retrieved evidence used to ground it) -- never the historical
"real" Apple reply, so it can't just reward replies that copy the answer key.

Calibration: scripts/05_judge_calibration.py compares this judge's overall
score against a human's manual 1-5 score on a subset, reporting agreement
(exact + within-1 + Spearman correlation). See report for results and caveats.
"""
from src.llm_client import generate_json

_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "relevance": {"type": "integer"},
        "faithfulness": {"type": "integer"},
        "tone": {"type": "integer"},
        "actionability": {"type": "integer"},
        "overall": {"type": "integer"},
        "rationale": {"type": "string"},
    },
    "required": ["relevance", "faithfulness", "tone", "actionability", "overall", "rationale"],
}


def judge_reply(customer_text: str, drafted_reply: str, evidence_text: str = "") -> dict:
    evidence_block = f"\nEvidence the reply was grounded in (if any):\n{evidence_text}\n" if evidence_text else ""
    prompt = f"""Rate the quality of a customer-support reply on a 1-5 scale (5=best) across
four dimensions, as a strict but fair support-quality reviewer would.

Customer message:
\"\"\"{customer_text}\"\"\"

Drafted reply:
\"\"\"{drafted_reply}\"\"\"
{evidence_block}
Dimensions (integer 1-5 each):
- relevance: does the reply actually address what the customer asked/reported?
- faithfulness: does it avoid inventing specific steps/facts not supported by
  the evidence or well-known Apple support practice? (5 = fully faithful,
  1 = confidently makes something up)
- tone: is it brief, polite, on-brand for a support tweet (not robotic, not
  dismissive)?
- actionability: does the customer know what to do next (e.g. DM sent, clear
  step, or clear reason nothing more can be done here)?
- overall: your holistic 1-5 judgment, not simply the average of the above.

Also give a one-sentence rationale for the overall score."""
    return generate_json(prompt, json_schema=_JUDGE_SCHEMA, temperature=0.0, max_output_tokens=300)
