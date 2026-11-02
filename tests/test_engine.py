"""Spot checks hand-verified against 49 CFR 176.83(b) and 176.84 text."""
from stowcheck import Cargo, Rules

R = Rules()


def lv(a, b, ga=(), gb=()):
    return R.pair(Cargo("a", a, groups=list(ga)), Cargo("b", b, groups=list(gb)))["level"]


def test_flammable_liquid_vs_oxidizer():  # 3 vs 5.1 -> 2
    assert lv("UN1090", "UN2014") == 2


def test_toxic_gas_vs_flammable_liquid():  # 2.3 vs 3 -> 2
    assert lv("UN1017", "UN1203") == 2


def test_subsidiary_hazard_counts():  # nitric acid 8 (sub 5.1) vs ammonia 2.3 (sub 8)
    assert lv("UN2031", "UN1005") == 2


def test_code_targets_class():  # ammonium nitrate code 66 "separated from flammable solids"
    assert lv("UN1942", "UN1325") == 2


def test_code_needs_ai_group():  # ammonia code 52 "separated from acids"
    assert lv("UN1005", "UN1789") == 0  # table alone misses it
    assert lv("UN1005", "UN1789", gb=["acids"]) == 2


def test_code_names_substance():  # ammonia code 57 "separated from chlorine"
    assert lv("UN1005", "UN1017") >= 2


def test_same_container_violation():
    r = R.pair(Cargo("a", "UN1090", container="C1"), Cargo("b", "UN2014", container="C1"))
    assert r["status"] == "violation"


def test_unknown_un():
    assert R.pair(Cargo("a", "UN0000"), Cargo("b", "UN1090"))["status"] == "unknown"
