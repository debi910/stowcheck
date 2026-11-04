"""Build data/demo_cache.json: saved pipeline answers for the page's built-in examples.

Free AI tiers allow only a few requests a minute, so the live demo answers its own examples from this file.
Every entry is produced by the same code path the API uses (_identify / extract_lines). Typed or uploaded
manifests that differ in any way still go to the AI.
"""
import csv
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import api.index as api  # noqa: E402

api.DEMO_CACHE = {"identify": {}, "extract": {}}  # build from scratch, never from old answers
EXAMPLE = []  # the page's default manifest is the sample packing list below
rows = list(csv.DictReader(open(ROOT / "public/samples/sample_manifest.csv")))
sample = [{"description": r["Description of goods"], "container": r["Container"]} for r in rows]
descs = EXAMPLE + [s["description"] for s in sample]
# Optional: reuse a saved check() run on the sample manifest (same pipeline) to save free-tier quota.
reuse = {}
if len(sys.argv) > 1:
    for it in json.load(open(sys.argv[1]))["items"]:
        reuse[it["description"]] = {k: it.get(k) for k in ("groups", "confidence", "abstain", "is_dangerous",
                                                           "evidence", "mismatch")} | {"un_number": it.get("un")}
todo = [d for d in descs if d not in reuse]
with ThreadPoolExecutor(int(os.getenv("STOWCHECK_WORKERS", "4"))) as ex:
    done = dict(zip(todo, ex.map(api._identify, todo)))
idents = [reuse.get(d) or done[d] for d in descs]
for _ in range(3):  # re-ask lines that hit API errors, one at a time
    for k, (d, i) in enumerate(zip(descs, idents)):
        if i.get("error"):
            idents[k] = api._identify(d)
bad = [d for d, i in zip(descs, idents) if i.get("error")]
if bad:
    sys.exit(f"AI errors, not saving: {bad}")
cache = {"model": os.getenv("STOWCHECK_MODEL", "default"),
         "identify": {api._norm(d): i for d, i in zip(descs, idents)},
         "extract": {api._doc_key(open(ROOT / "public/samples/sample_manifest.csv").read()): sample,
                     api._doc_key(open(ROOT / "eval/sample_pdf_text.txt").read()): sample}}
(ROOT / "data/demo_cache.json").write_text(json.dumps(cache, indent=1))
for d, i in zip(descs, idents):
    print(i.get("un_number"), "|", d, "|", i.get("mismatch") or "")
