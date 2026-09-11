"""Minimal Gemini REST client. No SDK dependency -- keeps the reproduction
footprint to `requests` only, which matters for the 15-minute repro promise.
"""
import json
import os
import time
import urllib.request
import urllib.error

from src.config import GEMINI_API_URL, GEMINI_MODEL


class LLMError(RuntimeError):
    pass


# Gemini free tier caps gemini-3.5-flash-lite at 15 requests/minute. We
# throttle proactively (rather than only reacting to 429s) so a full run's
# wall-clock time is predictable instead of dominated by retry backoff. See
# README for how this shapes the "quick demo" vs "full golden-set run" split.
_MIN_SECONDS_BETWEEN_CALLS = 4.3
_last_call_time = [0.0]


def _throttle():
    elapsed = time.monotonic() - _last_call_time[0]
    if elapsed < _MIN_SECONDS_BETWEEN_CALLS:
        time.sleep(_MIN_SECONDS_BETWEEN_CALLS - elapsed)
    _last_call_time[0] = time.monotonic()


def _api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise LLMError(
            "GEMINI_API_KEY not set. Copy .env.example to .env and fill it in."
        )
    return key


def generate(
    prompt: str,
    system_instruction: str | None = None,
    json_schema: dict | None = None,
    temperature: float = 0.2,
    max_output_tokens: int = 512,
    max_retries: int = 7,
) -> str:
    """Call Gemini generateContent. Returns the raw text of the first candidate.

    If json_schema is given, requests structured JSON output constrained to
    that schema (Gemini's `responseSchema` field) and returns the JSON text.
    """
    url = GEMINI_API_URL.format(model=GEMINI_MODEL) + f"?key={_api_key()}"

    generation_config = {
        "temperature": temperature,
        "maxOutputTokens": max_output_tokens,
        # Disable extended "thinking" tokens: on 2.5+/3.x Gemini models these
        # are drawn from the same maxOutputTokens budget, which was silently
        # truncating short structured-output responses to empty/partial text.
        "thinkingConfig": {"thinkingBudget": 0},
    }
    if json_schema is not None:
        generation_config["responseMimeType"] = "application/json"
        generation_config["responseSchema"] = json_schema

    def build_request(cfg):
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": cfg,
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        data = json.dumps(payload).encode("utf-8")
        return urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    thinking_config_supported = True
    last_err = None
    for attempt in range(max_retries):
        cfg = dict(generation_config)
        if not thinking_config_supported:
            cfg.pop("thinkingConfig", None)
        req = build_request(cfg)
        try:
            _throttle()
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            candidates = body.get("candidates", [])
            if not candidates:
                raise LLMError(f"No candidates in response: {body}")
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
            if not text:
                raise LLMError(f"Empty text in response: {body}")
            return text
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")
            last_err = LLMError(f"HTTP {e.code}: {body_text[:500]}")
            if e.code == 400 and thinking_config_supported and "thinkingConfig" in cfg:
                # Some models (e.g. gemini-3.5-flash-lite) reject thinkingConfig
                # outright. Retry immediately without it, no backoff needed.
                thinking_config_supported = False
                continue
            if e.code == 429 or e.code >= 500:
                time.sleep(min(2 ** attempt, 30))
                continue
            raise last_err
        except urllib.error.URLError as e:
            last_err = LLMError(f"Network error: {e}")
            time.sleep(2 ** attempt)
            continue
    raise last_err


def generate_json(prompt: str, json_schema: dict, **kwargs) -> dict:
    text = generate(prompt, json_schema=json_schema, **kwargs)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMError(f"Model did not return valid JSON: {text[:300]}") from e
