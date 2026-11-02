"""Thin client for free OpenAI-compatible endpoints (Groq or Gemini).

Set one of:
  GROQ_API_KEY    -> https://api.groq.com/openai/v1   (default model llama-3.3-70b-versatile)
  GEMINI_API_KEY  -> https://generativelanguage.googleapis.com/v1beta/openai  (gemini-2.5-flash)
Override the model with STOWCHECK_MODEL.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request

from .engine import GROUPS


def _endpoint():
    if os.getenv("GROQ_API_KEY"):
        return "https://api.groq.com/openai/v1", os.environ["GROQ_API_KEY"], "llama-3.3-70b-versatile"
    if os.getenv("GEMINI_API_KEY"):
        return ("https://generativelanguage.googleapis.com/v1beta/openai", os.environ["GEMINI_API_KEY"],
                "gemini-2.5-flash")
    raise RuntimeError("Set GROQ_API_KEY or GEMINI_API_KEY")


def chat(system: str, user: str, json_mode: bool = True, retries: int = 4) -> str:
    base, key, model = _endpoint()
    body = {"model": os.getenv("STOWCHECK_MODEL", model), "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(f"{base}/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                          "User-Agent": "stowcheck/0.1"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:  # rate limits on free tiers
            if e.code in (429, 500, 503) and attempt < retries - 1:
                time.sleep(2 ** (attempt + 2))
                continue
            raise


def parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else {}


IDENTIFY_SYSTEM = f"""You identify dangerous goods for sea transport under US 49 CFR.
Given a cargo description (trade name, invoice line, or safety data sheet text), return JSON:
{{"is_dangerous": true|false|null, "un_number": "UN####" or null, "packing_group": "I"|"II"|"III"|"",
  "groups": [subset of {GROUPS}], "confidence": 0.0-1.0, "evidence": "short quote or reason"}}
"groups" are the chemical families used by 49 CFR 176.84 segregation codes; include every family the
substance belongs to (e.g. hydrochloric acid -> ["acids"]; sodium hydroxide -> ["alkaline compounds",
"sodium compounds"]). Use null and low confidence when the description is not enough to decide."""


def identify(description: str) -> dict:
    out = parse_json(chat(IDENTIFY_SYSTEM, description))
    out["groups"] = [g for g in out.get("groups") or [] if g in GROUPS]
    return out


BASELINE_SYSTEM = """You are a dangerous goods expert. Answer using US 49 CFR 176.83 and the 172.101 table,
including subsidiary hazards and column 10B segregation codes. Return JSON:
{"level": 0|1|2|3|4, "reason": "..."}  where 0 = no segregation required, 1 = "away from",
2 = "separated from", 3 = "separated by a complete compartment or hold from",
4 = "separated longitudinally by an intervening complete compartment or hold from"."""


def baseline_pair(a: str, b: str) -> dict:
    q = f"Cargo 1: {a}\nCargo 2: {b}\nWhat segregation does 49 CFR require between them on a ship?"
    return parse_json(chat(BASELINE_SYSTEM, q))
