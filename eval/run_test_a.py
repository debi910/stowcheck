"""Test A: required segregation level for 100 real UN-number pairs.

  baseline: the free model answers directly from the UN numbers and names.
  ours:     the same model only tags chemical groups; the engine computes the level.
  table:    engine with no AI groups at all (shows what the AI adds).
"""
import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from stowcheck import Cargo, Rules  # noqa: E402

HERE = Path(__file__).parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["baseline", "ours", "table"], required=True)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    rows = list(csv.DictReader(open(HERE / "test_a_pairs.csv")))
    if args.limit:
        rows = rows[: args.limit]
    ap_workers = int(__import__("os").getenv("STOWCHECK_WORKERS", "6"))
    R = Rules()
    groups_cache = {}
    if args.mode == "ours":  # tag each distinct cargo once, in parallel
        from concurrent.futures import ThreadPoolExecutor
        from stowcheck.llm import identify
        uniq = {}
        for r in rows:
            uniq[r["un_a"]] = r["name_a"]
            uniq[r["un_b"]] = r["name_b"]
        with ThreadPoolExecutor(ap_workers) as ex:
            res = ex.map(lambda kv: (kv[0], identify(f"{kv[0]} {kv[1]}").get("groups", [])), uniq.items())
            groups_cache = dict(res)
        print("groups", groups_cache, flush=True)
    base_answers = {}
    if args.mode == "baseline":
        from concurrent.futures import ThreadPoolExecutor
        from stowcheck.llm import baseline_pair

        def ask(r):
            try:
                return r["id"], baseline_pair(f"{r['un_a']} {r['name_a']}", f"{r['un_b']} {r['name_b']}")
            except Exception as e:  # count as no answer, keep going
                return r["id"], {"level": None, "error": str(e)[:200]}
        with ThreadPoolExecutor(ap_workers) as ex:
            base_answers = dict(ex.map(ask, rows))
    out = []
    for r in rows:
        gold = int(r["gold_level"])
        if args.mode == "baseline":
            pred = base_answers[r["id"]].get("level")
        else:
            ga = gb = []
            if args.mode == "ours":
                ga, gb = groups_cache[r["un_a"]], groups_cache[r["un_b"]]
            pred = R.pair(Cargo("a", r["un_a"], groups=ga), Cargo("b", r["un_b"], groups=gb))["level"]
        try:
            pred = int(pred)
        except (TypeError, ValueError):
            pred = None
        out.append({"id": r["id"], "rule": r["deciding_rule"], "gold": gold, "pred": pred})
        print(r["id"], gold, pred, flush=True)
    acc = sum(o["gold"] == o["pred"] for o in out) / len(out)
    under = sum(o["pred"] is not None and o["pred"] < o["gold"] for o in out) / len(out)
    by_rule = {}
    for o in out:
        by_rule.setdefault(o["rule"], []).append(o["gold"] == o["pred"])
    summary = {"mode": args.mode, "n": len(out), "exact": round(acc, 3), "under_segregated": round(under, 3),
               "by_rule": {k: round(sum(v) / len(v), 3) for k, v in by_rule.items()},
               "model": __import__("os").getenv("STOWCHECK_MODEL", "default"), "no_answer": sum(o["pred"] is None for o in out)}
    print(json.dumps(summary, indent=2))
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / f"test_a_{args.mode}.json").write_text(json.dumps({"summary": summary, "rows": out}, indent=2))


if __name__ == "__main__":
    main()
