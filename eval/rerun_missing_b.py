"""Re-ask Test B 'ours' items that failed with an API error (timeouts) and rescore."""
import csv
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from stowcheck import Rules, llm  # noqa: E402
from stowcheck.search import Index  # noqa: E402

HERE = Path(__file__).parent
path = HERE / "results" / "test_b_ours.json"
res = json.load(open(path))
desc = {r["id"]: r["description"] for r in csv.DictReader(open(HERE / "test_b_descriptions.csv"))}
idx = Index(Rules())
ids = sys.argv[1:]
for r in res["rows"]:
    if r["id"] in ids:
        a = llm.identify_grounded(desc[r["id"]], idx)
        r.update(pred_dg=a.get("is_dangerous"), pred_un=a.get("un_number"), abstain=bool(a.get("abstain")),
                 confidence=a.get("confidence"))
        print(r["id"], r["gold_un"], r["pred_un"], flush=True)
res["summary"]["errors_reasked"] = ids
json.dump(res, open(path, "w"), indent=2)
subprocess.run([sys.executable, str(HERE / "run_test_b.py"), "--mode", "ours", "--rescore"])
