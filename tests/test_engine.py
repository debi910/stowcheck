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


def test_on_deck_only_category():
    r = Rules()
    notes = r.stowage_notes(r.lookup("UN1748"))
    assert any("on deck only" in n for n in notes)  # calcium hypochlorite is category D
    assert not any("on deck only" in n for n in r.stowage_notes(r.lookup("UN1090")))  # acetone is category B


def test_combustible_code_4_same_container():
    r = Rules()
    hypo = Cargo(label="#1 pool chlorine", un="UN1748", container="C1")
    out = r.combustible_conflicts([hypo], [("#2 plastic chairs", "C1"), ("#3 rice", "C2")])
    assert len(out) == 1 and out[0]["b"] == "#2 plastic chairs" and "code 4" in out[0]["reasons"][0]


def test_codes_with_trailing_punctuation_are_read():
    r = Rules()
    assert "52" in r.lookup("UN1823").codes  # 10B lists it as "52." in the source table
