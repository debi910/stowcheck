"""Test B: identify dangerous goods hidden in ordinary shipping descriptions.

  baseline: free model alone (IDENTIFY prompt, no table).
  ours:     same model writes search terms -> table retrieval -> model picks a real row -> abstain if unsure.
Metrics: DG detection on clear items, UN exact on clear DG items, abstain rate on vague items,
and wrong-confident (a UN or "not dangerous" given with confidence on an item that is actually DG).
"""
import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from stowcheck import Rules  # noqa: E402
from stowcheck.search import Index  # noqa: E402

HERE = Path(__file__).parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["baseline", "ours"], required=True)
    args = ap.parse_args()
    rows = list(csv.DictReader(open(HERE / "test_b_descriptions.csv")))
    from stowcheck import llm
    index = Index(Rules()) if args.mode == "ours" else None
    def run(r):
        try:
            if args.mode == "baseline":
                a = llm.identify(r["description"])
                a["abstain"] = a.get("is_dangerous") is None or float(a.get("confidence") or 0) < 0.5
            else:
                a = llm.identify_grounded(r["description"], index)
        except Exception as e:
            a = {"error": str(e)[:200], "abstain": True}
        return a

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(int(__import__("os").getenv("STOWCHECK_WORKERS", "6"))) as ex:
        answers = list(ex.map(run, rows))
    out = []
    for r, a in zip(rows, answers):
        un = (a.get("un_number") or "").upper().replace(" ", "") or None
        if un and not un.startswith(("UN", "NA")):
            un = "UN" + un
        out.append({"id": r["id"], "gold_dg": r["gold_dg"], "gold_un": r["gold_un"] or None,
                    "ambiguous": r["ambiguous"] == "yes", "pred_dg": a.get("is_dangerous"), "pred_un": un,
                    "abstain": bool(a.get("abstain")), "confidence": a.get("confidence")})
        print(r["id"], r["gold_un"], un, a.get("is_dangerous"), "abstain" if a.get("abstain") else "", flush=True)
    clear = [o for o in out if not o["ambiguous"]]
    clear_dg = [o for o in clear if o["gold_dg"] == "yes"]
    vague = [o for o in out if o["ambiguous"]]
    summary = {
        "mode": args.mode, "n": len(out),
        "dg_detection_clear": round(sum((o["pred_dg"] is True) == (o["gold_dg"] == "yes") for o in clear) / len(clear), 3),
        "un_exact_clear_dg": round(sum(o["pred_un"] == o["gold_un"] for o in clear_dg) / len(clear_dg), 3),
        "abstain_on_vague": round(sum(o["abstain"] for o in vague) / len(vague), 3),
        "model": __import__("os").getenv("STOWCHECK_MODEL", "default"),
        "errors": sum("error" in a for a in answers),
        "missed_dg_confident": sum(o["gold_dg"] == "yes" and o["pred_dg"] is False and not o["abstain"] for o in out),
    }
    print(json.dumps(summary, indent=2))
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / f"test_b_{args.mode}.json").write_text(json.dumps({"summary": summary, "rows": out}, indent=2))


if __name__ == "__main__":
    main()
