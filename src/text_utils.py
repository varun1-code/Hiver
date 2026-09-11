"""Shared text cleaning helpers."""
import re

MENTION_RE = re.compile(r"@\w+")
URL_RE = re.compile(r"https?://\S+")
WS_RE = re.compile(r"\s+")


def clean_for_matching(text: str) -> str:
    """Strip mentions/URLs and normalize whitespace for retrieval/keyword
    matching. Never use this for display -- keep the original text there."""
    text = MENTION_RE.sub(" ", text or "")
    text = URL_RE.sub(" ", text)
    text = WS_RE.sub(" ", text).strip()
    return text
