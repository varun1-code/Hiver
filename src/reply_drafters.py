"""Two reply-drafting strategies:

1. template_reply -- simple baseline: copy the closest retrieved historical
   reply verbatim (only above a similarity floor), else a safe generic
   fallback. No LLM call, fully deterministic.
2. llm_rag_reply  -- main system: the configured LLM (see config.LLM_PROVIDER;
   Hive by default, Gemini optional) drafts a new reply grounded in the top
   retrieved historical resolutions, in the brand's voice.
"""
from src.llm_client import generate
from src.retrieval import RetrievedCase

SIMILARITY_FLOOR = 0.12
GENERIC_FALLBACK = (
    "Sorry for the trouble! To look into this properly, please send us a DM "
    "with your device model and OS version and we'll help from there."
)


def template_reply(retrieved: list[RetrievedCase]) -> dict:
    if not retrieved or retrieved[0].similarity < SIMILARITY_FLOOR:
        return {"reply": GENERIC_FALLBACK, "grounded": False, "source_case_id": None}
    top = retrieved[0]
    return {"reply": top.brand_reply, "grounded": True, "source_case_id": top.case_id}


def llm_rag_reply(customer_text: str, retrieved: list[RetrievedCase]) -> dict:
    if not retrieved:
        return {"reply": GENERIC_FALLBACK, "grounded": False, "source_case_ids": []}

    evidence_block = "\n\n".join(
        f"Similar past case (similarity {r.similarity:.2f}):\n"
        f"Customer: {r.customer_text}\n"
        f"AppleSupport replied: {r.brand_reply}"
        for r in retrieved
    )

    prompt = f"""You are @AppleSupport replying to a customer on Twitter. Draft a reply
grounded in how AppleSupport has actually resolved similar issues before,
shown below as evidence. Do not invent troubleshooting steps that are not
supported by the evidence or well-established Apple support practice for
the described issue.

{evidence_block}

New customer message:
\"\"\"{customer_text}\"\"\"

Write ONLY the reply text, under 280 characters, in AppleSupport's typical
tone (brief, helpful, asks to DM for account-specific details, no over-promising).
Do not include a signature or hashtags."""

    text = generate(prompt, temperature=0.4, max_output_tokens=220).strip()
    if len(text) < 15:
        # Rare short/truncated generation; one retry with a lower temperature
        # before falling back, rather than shipping a useless reply.
        text = generate(prompt, temperature=0.1, max_output_tokens=220).strip()
    if len(text) < 15:
        text = GENERIC_FALLBACK
    return {
        "reply": text,
        "grounded": bool(retrieved) and retrieved[0].similarity >= SIMILARITY_FLOOR,
        "source_case_ids": [r.case_id for r in retrieved],
    }
