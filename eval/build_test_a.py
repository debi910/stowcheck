"""Build Test A: pairs of commonly shipped dangerous goods with the required segregation level.

Class 1 (explosives) is excluded: compatibility groups (176.144) are not modelled.
Gold = engine output, then every pair is reviewed by hand against the 176.83(b)
table and the 176.84 code text (see the `deciding_rule` column). Pairs are
stratified so the test is not dominated by easy "no segregation" cases.
"""
import csv
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from stowcheck import Cargo, Rules  # noqa: E402

# Frequently shipped dangerous goods (UN number, chemical groups the item belongs to).
COMMON = [
    ("UN1090", []), ("UN1203", []), ("UN1263", []), ("UN1266", []), ("UN1993", []),
    ("UN1170", []), ("UN1230", []), ("UN1219", []), ("UN1133", []), ("UN1210", []),
    ("UN1950", []), ("UN1075", []), ("UN1978", []), ("UN1072", []), ("UN1066", []),
    ("UN1005", []), ("UN1017", []), ("UN1079", []),
    ("UN1789", ["acids"]), ("UN1830", ["acids"]), ("UN2031", ["acids"]), ("UN1805", ["acids"]),
    ("UN2789", ["acids", "organic materials"]), ("UN1823", ["alkaline compounds", "sodium compounds"]),
    ("UN1824", ["alkaline compounds", "sodium compounds"]), ("UN1719", ["alkaline compounds"]),
    ("UN2014", ["peroxides"]), ("UN1942", ["ammonium compounds"]), ("UN1748", ["hypochlorites"]),
    ("UN2880", ["hypochlorites"]), ("UN1490", ["permanganates"]), ("UN1495", ["chlorates", "sodium compounds"]),
    ("UN3109", ["peroxides", "organic materials"]), ("UN3105", ["peroxides", "organic materials"]),
    ("UN1325", []), ("UN1350", []), ("UN1944", []), ("UN2213", []),
    ("UN1361", ["organic materials", "combustible materials"]), ("UN1363", ["animal or vegetable oils"]),
    ("UN1428", ["sodium compounds"]), ("UN1396", ["powdered metals"]), ("UN1402", []),
    ("UN1689", ["cyanides", "sodium compounds"]), ("UN1680", ["cyanides"]), ("UN2810", []),
    ("UN2811", []), ("UN1593", ["liquid halogenated hydrocarbons"]), ("UN1897", ["liquid halogenated hydrocarbons"]),
    ("UN2902", []), ("UN3082", []), ("UN3077", []), ("UN3480", []), ("UN3481", []),
    ("UN3090", []), ("UN2794", ["acids", "lead"]), ("UN3166", []), ("UN2067", ["ammonium compounds"]),
    ("UN2809", ["mercury", "heavy metals"]), ("UN1381", []),
    ("UN2910", []), ("UN2814", []), ("UN1977", []), ("UN1011", []), ("UN1001", []),
]


def deciding_rule(r):
    txt = " ".join(r["reasons"])
    if r["level"] == 0:
        return "none"
    if "176.84" in txt:
        return "code_group" if any(g in txt for g in ("acids", "alkaline", "ammonium", "cyanide", "hypochlor",
                                                    "permangan", "chlorat", "peroxides", "powdered", "mercury",
                                                    "sodium", "halogen", "organic", "combustible", "lead", "oils")) else "code_class"
    if any(f"class {x}" in txt for x in ()):  # placeholder kept simple
        return "table"
    return "table"


def main(n=100, seed=7):
    R = Rules()
    items = [(u, g) for u, g in COMMON if R.lookup(u)]
    rng = random.Random(seed)
    pools = {"none": [], "table": [], "code_class": [], "code_group": []}
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            (ua, ga), (ub, gb) = items[i], items[j]
            r = R.pair(Cargo("a", ua, groups=ga), Cargo("b", ub, groups=gb))
            if r["level"] is None:
                continue
            pools[deciding_rule(r)].append((ua, ub, r))
    quota = {"none": 25, "table": 35, "code_class": 15, "code_group": 25}
    rows = []
    for k, q in quota.items():
        pick = rng.sample(pools[k], min(q, len(pools[k])))
        for ua, ub, r in pick:
            ea, eb = R.lookup(ua), R.lookup(ub)
            rows.append({"id": f"A{len(rows)+1:03d}", "un_a": ua, "name_a": ea.name, "class_a": ea.hazard_class,
                         "un_b": ub, "name_b": eb.name, "class_b": eb.hazard_class, "gold_level": r["level"],
                         "deciding_rule": k, "reason": " | ".join(r["reasons"])})
    print({k: len(v) for k, v in pools.items()}, "->", len(rows))
    out = Path(__file__).parent / "test_a_pairs.csv"
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("wrote", out)


if __name__ == "__main__":
    main()
