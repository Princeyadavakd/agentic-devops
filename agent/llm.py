"""LLM access with two providers (Gemini cloud / Ollama local) and retry."""
import json
import time

import requests

from . import config


def _gemini(prompt):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    resp = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),
    )
    return resp.text


def _ollama(prompt):
    r = requests.post(
        f"{config.OLLAMA_URL}/api/generate",
        json={"model": config.OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json"},
        timeout=300,
    )
    r.raise_for_status()
    return r.json()["response"]


def _ask(prompt):
    last = None
    for i in range(3):
        try:
            return _gemini(prompt) if config.LLM_PROVIDER == "gemini" else _ollama(prompt)
        except Exception as e:  # rate limit, network, bad key ...
            last = e
            time.sleep(4 * (i + 1))
    raise RuntimeError(f"LLM failed after retries: {last}")


def ask_json(prompt):
    text = _ask(prompt)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("LLM did not return JSON")
    return json.loads(text[start:end + 1])
