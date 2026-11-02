"""Re-ask Test A baseline pairs that got no answer (API timeouts) and merge them in."""
import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from stowcheck.llm import baseline_pair  # noqa: E402

HERE = Path(__file__).parent
res_path = HERE / "results" / "test_a_baseline.json"
res = json.load(open(res_path))
pairs = {r["id"]: r for r in csv.DictReader(open(HERE / "test_a_pairs.csv"))}
missing = [r for r in res["rows"] if r["pred"] is None]


def ask(row):
    p = pairs[row["id"]]
    try:
        lv = baseline_pair(f"{p['un_a']} {p['name_a']}", f"{p['un_b']} {p['name_b']}").get("level")
        return row["id"], int(lv) if lv is not None else None
    except Exception as e:
        print(row["id"], "error", repr(e)[:120], flush=True)
        return row["id"], None


with ThreadPoolExecutor(3) as ex:
    got = dict(ex.map(ask, missing))
for r in res["rows"]:
    if r["id"] in got and got[r["id"]] is not None:
        r["pred"] = got[r["id"]]
        print(r["id"], r["gold"], r["pred"], flush=True)
rows = res["rows"]
s = res["summary"]
s["exact"] = round(sum(r["gold"] == r["pred"] for r in rows) / len(rows), 3)
s["under_segregated"] = round(sum(r["pred"] is not None and r["pred"] < r["gold"] for r in rows) / len(rows), 3)
s["no_answer"] = sum(r["pred"] is None for r in rows)
by = {}
for r in rows:
    by.setdefault(r["rule"], []).append(r["gold"] == r["pred"])
s["by_rule"] = {k: round(sum(v) / len(v), 3) for k, v in by.items()}
s["note"] = "no-answer pairs (API timeouts) re-asked once"
json.dump(res, open(res_path, "w"), indent=2)
print(json.dumps(s, indent=2))
