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


# ---- grounded identification (ours) ------------------------------------------
TERMS_SYSTEM = """You help find a cargo's entry in the US 49 CFR 172.101 Hazardous Materials Table.
Given a cargo description, return JSON {"search_terms": ["...", "..."]} with 1-3 short phrases written
the way 49 CFR proper shipping names are written (e.g. "power bank" -> "lithium ion batteries";
"pool chlorine tablets" -> "calcium hypochlorite"). If the cargo is clearly not dangerous, return []."""

PICK_SYSTEM = f"""You classify a cargo for sea transport under US 49 CFR. You are given the cargo description
and candidate rows from the 172.101 table. Pick the single best candidate, or none if the cargo is not
dangerous or the description is too vague to decide. Return JSON:
{{"choice": <candidate number or null>, "is_dangerous": true|false|null, "confidence": 0.0-1.0,
  "groups": [subset of {GROUPS}], "evidence": "which words in the description support the choice"}}
Use is_dangerous null and confidence below 0.5 when the description could be several different things."""


def identify_grounded(description: str, index, k: int = 6, abstain_below: float = 0.5) -> dict:
    terms = parse_json(chat(TERMS_SYSTEM, description)).get("search_terms") or []
    cands, seen = [], set()
    for q in [description] + list(terms):
        for e in index.search(q, k):
            if (e.un, e.name) not in seen:
                seen.add((e.un, e.name))
                cands.append(e)
    cands = cands[: 3 * k]
    listing = "\n".join(f"{i+1}. {e.un} | {e.name} | class {e.hazard_class} | PG {e.packing_group or '-'}"
                        for i, e in enumerate(cands)) or "(no candidates)"
    ans = parse_json(chat(PICK_SYSTEM, f"Cargo: {description}\n\nCandidates:\n{listing}"))
    choice = ans.get("choice")
    entry = cands[int(choice) - 1] if isinstance(choice, int) and 1 <= choice <= len(cands) else None
    conf = float(ans.get("confidence") or 0)
    abstain = ans.get("is_dangerous") is None or conf < abstain_below
    return {"is_dangerous": ans.get("is_dangerous"), "un_number": entry.un if entry and not abstain else None,
            "packing_group": entry.packing_group if entry else "", "entry": entry.cite if entry else None,
            "groups": [g for g in ans.get("groups") or [] if g in GROUPS], "confidence": conf,
            "abstain": abstain, "evidence": ans.get("evidence", ""), "search_terms": terms}
