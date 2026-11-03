"""Test C: replay real misdeclared cargo descriptions from container-ship fire investigations.

Each row is the text a shipper actually declared; the real cargo was dangerous.
We record what each system says. "caught" = flagged as dangerous OR sent to a human (abstain).
"cleared" = confidently called not dangerous, which is the failure that let these boxes on board.
Run once; failures are published, not tuned away.
"""
import argparse, csv, json, os, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from stowcheck import Rules  # noqa: E402
from stowcheck.search import Index  # noqa: E402

HERE = Path(__file__).parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["baseline", "ours"], required=True)
    args = ap.parse_args()
    rows = list(csv.DictReader(open(HERE / "test_c_incidents.csv")))
    from stowcheck import llm
    index = Index(Rules()) if args.mode == "ours" else None

    def run(r):
        try:
            if args.mode == "baseline":
                a = llm.identify(r["declared_description"])
                a["abstain"] = a.get("is_dangerous") is None or float(a.get("confidence") or 0) < 0.5
            else:
                a = llm.identify_grounded(r["declared_description"], index)
        except Exception as e:
            a = {"error": str(e)[:200], "abstain": True}
        return a

    with ThreadPoolExecutor(int(os.getenv("STOWCHECK_WORKERS", "6"))) as ex:
        answers = list(ex.map(run, rows))
    out = []
    for r, a in zip(rows, answers):
        verdict = ("error" if "error" in a else "flagged_dg" if a.get("is_dangerous") and not a.get("abstain")
                   else "needs_human" if a.get("abstain") else "cleared")
        out.append({"id": r["id"], "declared": r["declared_description"], "actual": r["actual_cargo"],
                    "actual_un": r["actual_un"], "pred_un": a.get("un_number"), "verdict": verdict,
                    "confidence": a.get("confidence")})
        print(r["id"], r["declared_description"][:40], "->", verdict, a.get("un_number"), flush=True)
    summary = {"mode": args.mode, "n": len(out), "model": os.getenv("STOWCHECK_MODEL", "default"),
               "caught": sum(o["verdict"] in ("flagged_dg", "needs_human") for o in out),
               "cleared": sum(o["verdict"] == "cleared" for o in out),
               "errors": sum(o["verdict"] == "error" for o in out)}
    print(json.dumps(summary, indent=2))
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / f"test_c_{args.mode}.json").write_text(json.dumps({"summary": summary, "rows": out}, indent=2))


if __name__ == "__main__":
    main()
