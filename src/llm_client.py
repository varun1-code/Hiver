"""Minimal LLM REST client supporting two backends behind one interface
(generate / generate_json): Gemini and TheHive.ai. No SDK dependency -- keeps
the reproduction footprint to the standard library plus `requests`-free
urllib, which matters for the 15-minute repro promise. See config.LLM_PROVIDER
and the decision log for why both exist.
"""
import json
import os
import re
import time
import urllib.request
import urllib.error

from src.config import (
    LLM_PROVIDER, GEMINI_API_URL, GEMINI_MODEL, HIVE_API_URL, HIVE_MODEL,
)


class LLMError(RuntimeError):
    pass


# Proactive throttling: Gemini's free tier caps gemini-3.5-flash-lite at 15
# requests/minute; Hive showed no rate-limit issues at this project's volume
# but a small floor is kept anyway to be a well-behaved client.
_MIN_SECONDS_BETWEEN_CALLS = 4.3 if LLM_PROVIDER == "gemini" else 0.3
_last_call_time = [0.0]


def _throttle():
    elapsed = time.monotonic() - _last_call_time[0]
    if elapsed < _MIN_SECONDS_BETWEEN_CALLS:
        time.sleep(_MIN_SECONDS_BETWEEN_CALLS - elapsed)
    _last_call_time[0] = time.monotonic()


def _api_key(env_var: str) -> str:
    key = os.environ.get(env_var)
    if not key:
        raise LLMError(f"{env_var} not set. Copy .env.example to .env and fill it in.")
    return key


_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _extract_json_text(text: str) -> str:
    """Strip markdown code fences some models wrap JSON in."""
    return _JSON_FENCE_RE.sub("", text).strip()


def generate(
    prompt: str,
    system_instruction: str | None = None,
    json_schema: dict | None = None,
    temperature: float = 0.2,
    max_output_tokens: int = 512,
    max_retries: int = 7,
) -> str:
    """Call the configured LLM provider. Returns the raw text of the response.

    If json_schema is given: on Gemini this uses native structured-output
    constraints (responseSchema); on Hive (no native schema support) the
    schema's field names are appended to the prompt as an instruction and the
    response is parsed as JSON on the caller side (generate_json).
    """
    if LLM_PROVIDER == "gemini":
        return _generate_gemini(prompt, system_instruction, json_schema, temperature, max_output_tokens, max_retries)
    elif LLM_PROVIDER == "hive":
        return _generate_hive(prompt, system_instruction, json_schema, temperature, max_output_tokens, max_retries)
    raise LLMError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER}")


def _generate_hive(prompt, system_instruction, json_schema, temperature, max_output_tokens, max_retries):
    url = HIVE_API_URL
    key = _api_key("HIVE_API_KEY")

    if json_schema is not None:
        fields = ", ".join(json_schema.get("properties", {}).keys())
        prompt = (
            f"{prompt}\n\nRespond with ONLY a single valid JSON object with these "
            f"fields: {fields}. No markdown code fences, no extra text before or after."
        )

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": HIVE_MODEL,
        "max_tokens": max_output_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    )

    last_err = None
    for attempt in range(max_retries):
        try:
            _throttle()
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            choices = body.get("choices", [])
            if not choices:
                raise LLMError(f"No choices in response: {body}")
            text = choices[0].get("message", {}).get("content", "")
            if not text:
                raise LLMError(f"Empty text in response: {body}")
            return text
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")
            last_err = LLMError(f"HTTP {e.code}: {body_text[:500]}")
            if e.code == 429 or e.code >= 500:
                time.sleep(min(2 ** attempt, 30))
                continue
            raise last_err
        except urllib.error.URLError as e:
            last_err = LLMError(f"Network error: {e}")
            time.sleep(2 ** attempt)
            continue
    raise last_err


def _generate_gemini(prompt, system_instruction, json_schema, temperature, max_output_tokens, max_retries):
    url = GEMINI_API_URL.format(model=GEMINI_MODEL) + f"?key={_api_key('GEMINI_API_KEY')}"

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
    cleaned = _extract_json_text(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise LLMError(f"Model did not return valid JSON: {text[:300]}") from e
