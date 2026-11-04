"""StowCheck web API (FastAPI). Runs locally with `uvicorn api.index:app` and on Vercel as a Python function."""
import hashlib
import json
import re
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from stowcheck import Cargo, Rules  # noqa: E402
from stowcheck.search import Index  # noqa: E402

app = FastAPI(title="StowCheck")
RULES = Rules()
INDEX = Index(RULES)
UN_RE = re.compile(r"\b(UN|NA)\s?(\d{4})\b", re.I)

# Saved answers for the built-in examples, produced by this same pipeline (see eval/build_demo_cache.py).
# Free AI tiers allow only a few requests a minute, so the examples answer instantly; anything else calls the AI.
_CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "demo_cache.json"
DEMO_CACHE = json.load(open(_CACHE_PATH)) if _CACHE_PATH.exists() else {"identify": {}, "extract": {}}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _doc_key(text: str) -> str:
    return hashlib.sha256(_norm(text).encode()).hexdigest()[:16]


class Line(BaseModel):
    description: str
    container: str = ""


class Manifest(BaseModel):
    lines: list[Line] = []
    document_text: str = ""  # when set, the AI extracts cargo lines from a document instead of checking


def _identify(description: str) -> dict:
    hit = DEMO_CACHE["identify"].get(_norm(description))
    if hit:
        return {**hit, "cached": True}
    typed = UN_RE.search(description)
    if not typed:
        try:
            from stowcheck.llm import identify_grounded
            return identify_grounded(description, INDEX)
        except Exception as e:
            return {"un_number": None, "abstain": True, "error": str(e)[:200]}
    un = f"{typed.group(1).upper()}{typed.group(2)}"
    declared = RULES.lookup(un)
    if declared is None:  # a typed number that is not in the 172.101 table is not trusted
        return {"un_number": None, "abstain": True, "is_dangerous": None,
                "evidence": f"{un} is not in the 49 CFR 172.101 table. Check the number."}
    ident = {"un_number": un, "is_dangerous": True, "confidence": 1.0, "abstain": False, "groups": [],
             "evidence": "UN number typed in the description"}
    # Misdeclaration check: read the words without the number and see if they point somewhere else.
    words = UN_RE.sub(" ", description).strip(" ,;-")
    try:
        from stowcheck.llm import identify_grounded
        ai = identify_grounded(words or description, INDEX)
        ident["groups"] = ai.get("groups", [])
        ai_entry = RULES.lookup(ai["un_number"]) if ai.get("un_number") and not ai.get("abstain") else None
        if ai_entry and ai_entry.hazard_class != declared.hazard_class:
            ident["mismatch"] = (f"Declared {un} is Class {declared.hazard_class}, but the description reads like "
                                 f"{ai_entry.cite} (Class {ai_entry.hazard_class}). Check the declaration.")
        elif ai.get("is_dangerous") is False and not ai.get("abstain") and words:
            ident["mismatch"] = f"Declared {un}, but the description reads like ordinary goods. Check the declaration."
    except Exception:
        pass
    return ident


@app.get("/api/health")
@app.get("/api/index")  # Vercel rewrites every path to /api/index, so GET there is the health check
def health():
    import os
    out = {"groq_key_set": bool(os.getenv("GROQ_API_KEY")), "gemini_key_set": bool(os.getenv("GEMINI_API_KEY")),
           "model": os.getenv("STOWCHECK_MODEL", "default")}
    try:
        from stowcheck.llm import chat
        out["test_call"] = chat("Reply with JSON {\"ok\": true}", "ping")[:200]
        from stowcheck import llm
        out["resolved_model"] = llm._resolved
    except Exception as e:
        body = ""
        if hasattr(e, "read"):
            try:
                body = e.read().decode()[:300]
            except Exception:
                pass
        out["test_call_error"] = f"{e!r} {body}"[:500]
    return out


@app.get("/")
def home():
    return FileResponse(Path(__file__).resolve().parent.parent / "public" / "index.html")


@app.post("/api/check")
@app.post("/api/index")  # Vercel rewrites every path to the function at /api/index
@app.post("/")
def check(m: Manifest):
    if m.document_text.strip():
        try:
            from stowcheck.llm import extract_lines
            hit = DEMO_CACHE["extract"].get(_doc_key(m.document_text))
            if hit:
                return {"extracted": hit, "cached": True}
            return {"extracted": extract_lines(m.document_text)}
        except Exception as e:
            return {"extracted": [], "error": str(e)[:200]}
    from concurrent.futures import ThreadPoolExecutor
    lines = m.lines[:25]
    with ThreadPoolExecutor(3) as ex:  # free tiers rate-limit bursts
        idents = list(ex.map(_identify, [ln.description for ln in lines]))
    items, cargos = [], []
    for i, (ln, ident) in enumerate(zip(lines, idents)):
        label = f"#{i+1} {ln.description[:60]}"
        entry = RULES.lookup(ident["un_number"], ident.get("packing_group", "")) if ident.get("un_number") else None
        items.append({"line": i + 1, "description": ln.description, "container": ln.container,
                      "identified": entry.cite if entry else None, "un": ident.get("un_number"),
                      "class": entry.hazard_class if entry else None, "groups": ident.get("groups", []),
                      "confidence": ident.get("confidence"), "abstain": ident.get("abstain"),
                      "is_dangerous": ident.get("is_dangerous"), "evidence": ident.get("evidence", ""),
                      "error": ident.get("error"), "mismatch": ident.get("mismatch"),
                      "cached": ident.get("cached", False)})
        if entry:
            cargos.append(Cargo(label=label, un=entry.un, packing_group=entry.packing_group,
                                groups=ident.get("groups", []), container=ln.container))
    return {"items": items, "findings": RULES.check_manifest(cargos)}
