"""StowCheck web API (FastAPI). Runs locally with `uvicorn api.index:app` and on Vercel as a Python function."""
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


class Line(BaseModel):
    description: str
    container: str = ""


class Manifest(BaseModel):
    lines: list[Line]


def _identify(description: str) -> dict:
    typed = UN_RE.search(description)
    if typed:
        un = f"{typed.group(1).upper()}{typed.group(2)}"
        ident = {"un_number": un, "is_dangerous": True, "confidence": 1.0, "abstain": False, "groups": [],
                 "evidence": "UN number typed in the description"}
        try:  # still ask the AI for chemical groups; the engine works without them
            from stowcheck.llm import identify_grounded
            ident["groups"] = identify_grounded(description, INDEX).get("groups", [])
        except Exception:
            pass
        return ident
    try:
        from stowcheck.llm import identify_grounded
        return identify_grounded(description, INDEX)
    except Exception as e:
        return {"un_number": None, "abstain": True, "error": str(e)[:200]}


@app.get("/")
def home():
    return FileResponse(Path(__file__).resolve().parent.parent / "public" / "index.html")


@app.post("/api/check")
@app.post("/api/index")  # Vercel rewrites every path to the function at /api/index
@app.post("/")
def check(m: Manifest):
    from concurrent.futures import ThreadPoolExecutor
    lines = m.lines[:25]
    with ThreadPoolExecutor(8) as ex:
        idents = list(ex.map(_identify, [ln.description for ln in lines]))
    items, cargos = [], []
    for i, (ln, ident) in enumerate(zip(lines, idents)):
        label = f"#{i+1} {ln.description[:40]}"
        entry = RULES.lookup(ident["un_number"], ident.get("packing_group", "")) if ident.get("un_number") else None
        items.append({"line": i + 1, "description": ln.description, "container": ln.container,
                      "identified": entry.cite if entry else None, "un": ident.get("un_number"),
                      "class": entry.hazard_class if entry else None, "groups": ident.get("groups", []),
                      "confidence": ident.get("confidence"), "abstain": ident.get("abstain"),
                      "is_dangerous": ident.get("is_dangerous"), "evidence": ident.get("evidence", "")})
        if entry:
            cargos.append(Cargo(label=label, un=entry.un, packing_group=entry.packing_group,
                                groups=ident.get("groups", []), container=ln.container))
    return {"items": items, "findings": RULES.check_manifest(cargos)}
