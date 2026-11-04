"""Thin client for free OpenAI-compatible endpoints (Groq or Gemini).

Set one of:
  GROQ_API_KEY    -> https://api.groq.com/openai/v1   (default model llama-3.3-70b-versatile)
  GEMINI_API_KEY  -> https://generativelanguage.googleapis.com/v1beta/openai  (gemini-3.5-flash)
Override the model with STOWCHECK_MODEL.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request

from .engine import GROUPS


def _endpoint():
    if os.getenv("GROQ_API_KEY"):
        return "https://api.groq.com/openai/v1", os.environ["GROQ_API_KEY"], "llama-3.3-70b-versatile"
    if os.getenv("GEMINI_API_KEY"):
        return ("https://generativelanguage.googleapis.com/v1beta/openai", os.environ["GEMINI_API_KEY"],
                "gemini-3.5-flash")
    raise RuntimeError("Set GROQ_API_KEY or GEMINI_API_KEY")


_PREFER = ["gpt-oss-120b", "llama-4-maverick", "llama-3.3-70b", "llama-4-scout", "qwen3", "kimi-k2", "gpt-oss-20b",
           "llama", "gemini-3.5-flash", "gemma-4-26b"]
_SKIP = ("whisper", "guard", "tts", "orpheus", "playai", "embed", "compound", "prompt-guard", "distil")
_resolved: dict[str, str] = {}
_exhausted: set[str] = set()  # models whose daily free quota is used up in this process


def _pick_model(base: str, key: str, exclude: set[str] = frozenset()) -> str | None:
    """Ask the provider which chat models exist and pick the best free one (Groq retires models often)."""
    req = urllib.request.Request(f"{base}/models", headers={"Authorization": f"Bearer {key}",
                                                           "User-Agent": "Mozilla/5.0 (compatible; stowcheck/0.1)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        ids = [m["id"].removeprefix("models/") for m in json.load(r).get("data", [])]
    ids = [i for i in ids if not any(x in i.lower() for x in _SKIP) and i not in exclude]
    for pref in _PREFER:
        for i in ids:
            if pref in i.lower():
                return i
    return ids[0] if ids else None


def chat(system: str, user: str, json_mode: bool = True, retries: int = 6) -> str:
    base, key, model = _endpoint()
    model = _resolved.get(base) or os.getenv("STOWCHECK_MODEL", model)
    body = {"model": model, "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if json_mode and not body["model"].startswith("gemma"):  # Gemma rejects JSON mode params
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(f"{base}/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                          "User-Agent": "Mozilla/5.0 (compatible; stowcheck/0.1)", "Accept": "application/json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=150) as r:
                return json.load(r)["choices"][0]["message"]["content"]
        except (TimeoutError, urllib.error.URLError) as e:  # rate limits / slow free tiers
            code = getattr(e, "code", None)
            if code == 429:
                try:
                    detail = e.read().decode(errors="ignore").lower()
                except Exception:
                    detail = ""
                if "per day" in detail:  # daily quota gone: each model has its own, so move to the next one
                    _exhausted.add(body["model"])
                    new = _pick_model(base, key, _exhausted)
                    if new:
                        _resolved[base] = new
                        body["model"] = new
                        if new.startswith("gemma"):
                            body.pop("response_format", None)
                        req.data = json.dumps(body).encode()
                        continue
            if code in (400, 404) and body["model"] not in _exhausted:  # model retired: discover a live one
                _exhausted.add(body["model"])
                new = _pick_model(base, key, _exhausted)
                if new and new != body["model"]:
                    _resolved[base] = new
                    body["model"] = new
                    if new.startswith("gemma"):
                        body.pop("response_format", None)
                    req.data = json.dumps(body).encode()
                    continue
            if (code in (429, 500, 503) or code is None) and attempt < retries - 1:
                wait = 2 ** (attempt + 2)
                try:  # honour the provider's Retry-After when it sends one
                    wait = max(1.0, min(30.0, float(e.headers.get("retry-after"))))
                except Exception:
                    pass
                time.sleep(wait)
                continue
            raise


def parse_json(text: str) -> dict:
    text = re.sub(r"<thought>.*?</thought>", "", text or "", flags=re.S)  # Gemma thinking block
    text = text.split("</thought>")[-1]
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


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
Rules: prefer the entry that names the product itself (e.g. a finished product's own entry) over an entry for
one of its ingredients. Finished manufactured articles such as clothing, textiles, furniture, tiles or utensils
are not raw bulk materials: do not match them to raw-material entries. Use is_dangerous null and confidence
below 0.5 when the description could be several different things."""


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


EXTRACT_SYSTEM = """You read shipping documents (packing lists, commercial invoices, manifests) that were converted to text.
List every cargo line item. For each, give the goods description exactly as written (keep UN numbers,
concentrations and packaging words) and the container number if the document links one to that line.
Container numbers look like four letters and seven digits, e.g. MSKU1234565. Skip totals, addresses, prices,
headers and terms. Do not judge whether goods are dangerous.
Reply with JSON only: {"lines": [{"description": "...", "container": "..."}]}"""


def extract_lines(document_text: str, limit: int = 25) -> list[dict]:
    """AI step 0: turn a messy document into cargo lines. The person reviews them before the check runs."""
    out = parse_json(chat(EXTRACT_SYSTEM, document_text[:12000]))
    lines = []
    for ln in out.get("lines", [])[:limit]:
        d = str(ln.get("description") or "").strip()
        if d:
            lines.append({"description": d[:200], "container": str(ln.get("container") or "").strip()[:20]})
    return lines
