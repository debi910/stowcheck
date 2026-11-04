"""Re-ask rows that failed with an API error (429/400) one at a time, then rescore. Same prompts."""
import csv, json, os, sys, time
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent)); sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from pathlib import Path
from stowcheck import Rules, llm
from stowcheck.search import Index
import run_test_b
E = Path(__file__).resolve().parent; idx = Index(Rules())
def ask(text, mode):
    for t in range(6):
        try:
            if mode == "baseline":
                a = llm.identify(text); a["abstain"] = a.get("is_dangerous") is None or float(a.get("confidence") or 0) < 0.5
            else:
                a = llm.identify_grounded(text, idx)
            return a
        except Exception as e:
            err = str(e)[:200]; time.sleep(20 * (t + 1))
    return {"error": err, "abstain": True}
for s in ["d", "b", "c"]:
    for mode in ["baseline", "ours"]:
        p = E / "results" / f"groq_test_{s}_{mode}.json"; res = json.load(open(p))
        if s == "c":
            src = {r["id"]: r["declared_description"] for r in csv.DictReader(open(E / "test_c_incidents.csv"))}
            bad = [r for r in res["rows"] if r["verdict"] == "error"]
        else:
            src = {r["id"]: r["description"] for r in csv.DictReader(open(E / ("test_b_descriptions.csv" if s == "b" else "test_d_heldout.csv")))}
            bad = [r for r in res["rows"] if r.get("error")]
        ids = [r["id"] for r in bad]
        for r in bad:
            a = ask(src[r["id"]], mode); time.sleep(3)
            if s == "c":
                r.update(pred_un=a.get("un_number"), confidence=a.get("confidence"),
                         verdict=("error" if "error" in a else "flagged_dg" if a.get("is_dangerous") and not a.get("abstain")
                                  else "needs_human" if a.get("abstain") else "cleared"))
            else:
                un = (a.get("un_number") or "").upper().replace(" ", "") or None
                if un and not un.startswith(("UN", "NA")): un = "UN" + un
                r.pop("error", None)
                r.update(pred_dg=a.get("is_dangerous"), pred_un=un, abstain=bool(a.get("abstain")), confidence=a.get("confidence"))
                if "error" in a: r["error"] = a["error"]
            print(s, mode, r["id"], "error" if "error" in a else "ok", flush=True)
        if s == "c":
            rows = res["rows"]
            res["summary"].update(caught=sum(o["verdict"] in ("flagged_dg", "needs_human") for o in rows),
                                  cleared=sum(o["verdict"] == "cleared" for o in rows),
                                  errors=sum(o["verdict"] == "error" for o in rows))
        else:
            first = res["summary"]["errors"]
            res["summary"] = {**run_test_b.score(res["rows"], mode), "model": res["summary"]["model"],
                              "errors": sum(1 for o in res["rows"] if o.get("error"))}
            res["summary"]["errors_first_pass"] = first
        res["summary"]["errors_reasked"] = ids
        json.dump(res, open(p, "w"), indent=2); print(json.dumps(res["summary"]), flush=True)
