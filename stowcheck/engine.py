"""Deterministic segregation engine for dangerous goods on ships.

Rules come from 49 CFR (public domain):
  * 172.101 Hazardous Materials Table (class, subsidiary labels, column 10A/10B)
  * 176.83(b) General Segregation Table, 176.83(a)(6) subsidiary hazards,
    176.83(d) no segregated pair inside one cargo transport unit
  * 176.84 stowage/segregation codes referenced by column 10B

The AI layer (see llm.py) only identifies *what* a cargo is (UN number,
packing group, chemical groups such as "acids"). Everything below is code.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

LEVEL_NAMES = {
    0: "No segregation required",
    1: "Away from",
    2: "Separated from",
    3: "Separated by a complete compartment or hold from",
    4: "Separated longitudinally by an intervening complete compartment or hold from",
}

# Words used in 176.84 code texts that name a whole hazard class.
CLASS_WORDS = [
    (r"flammable solids?", ["4.1"]),
    (r"flammable liquids?", ["3"]),
    (r"flammable gas(es)?", ["2.1"]),
    (r"dangerous when wet", ["4.3"]),
    (r"oxidi[sz]ers?", ["5.1"]),
    (r"organic peroxides", ["5.2"]),
    (r"infectious substances", ["6.2"]),
    (r"radioactive materials?", ["7"]),
    (r"corrosives?|corrosive materials", ["8"]),
    (r"explosives division 1\.3", ["1.3"]),
    (r"class 1 \(explosives\) except division 1\.4", ["1.1", "1.2", "1.3", "1.5", "1.6"]),
    (r"divisions? 1\.1, 1\.2,? and 1\.5", ["1.1", "1.2", "1.5"]),
    (r"explosives", ["1.1", "1.2", "1.3", "1.4", "1.5", "1.6"]),
]
# Chemical groups named in 176.84 codes. The AI tags each cargo with these.
GROUPS = [
    "acids", "alkaline compounds", "ammonium compounds", "animal or vegetable oils",
    "bromates", "chlorates", "chlorites", "combustible materials", "copper", "cyanides",
    "fluorides", "foodstuffs", "halides", "heavy metals", "hypochlorites", "lead",
    "liquid halogenated hydrocarbons", "mercury", "nitrites", "nitrogen compounds",
    "organic materials", "perchlorates", "permanganates", "peroxides", "powdered metals",
    "sodium compounds",
]
PHRASE_LEVEL = [
    (r"separated longitudinally", 4),
    (r"separated by a complete compartment", 3),
    (r"separated from", 2),
    (r"away from", 1),
]


def matrix_key(cls: str) -> str:
    """Map a class/division like '1.1D' or '5.1' to a 176.83(b) row/column."""
    c = cls.strip()
    if c.startswith("1"):
        div = c[:3]
        if div in ("1.1", "1.2", "1.5"):
            return "1.1, 1.2, 1.5"
        if div == "1.3":
            return "1.3"
        return "1.4, 1.6"
    return c


def base_division(cls: str) -> str:
    return cls[:3] if cls.startswith("1") else cls


@dataclass
class Entry:
    un: str
    name: str
    hazard_class: str
    packing_group: str
    labels: list[str]
    stowage_cat: str
    codes: list[str]

    @property
    def cite(self) -> str:
        pg = f", PG {self.packing_group}" if self.packing_group else ""
        return f"49 CFR 172.101: {self.un} {self.name} (class {self.hazard_class}{pg})"


@dataclass
class Cargo:
    """One consignment as identified by the AI layer (or typed by a user)."""
    label: str
    un: str
    packing_group: str = ""
    groups: list[str] = field(default_factory=list)  # e.g. ["acids"], from the AI
    container: str = ""


class Rules:
    def __init__(self, data_dir: Path = DATA):
        seg = json.loads((data_dir / "segregation_176_83.json").read_text())
        self.matrix = seg["matrix"]
        self.codes = seg["stowage_codes"]
        self.categories = seg["stowage_categories"]
        self.rows: dict[str, list[Entry]] = {}
        with open(data_dir / "hmt_172_101.csv", newline="") as fh:
            for r in csv.DictReader(fh):
                if not r["un_number"].startswith(("UN", "NA")):
                    continue
                e = Entry(
                    un=r["un_number"],
                    name=r["proper_shipping_name"],
                    hazard_class=r["hazard_class"],
                    packing_group=r["packing_group"],
                    labels=[x.strip() for x in r["label_codes"].split(",") if x.strip()],
                    stowage_cat=r["vessel_stowage_10a"],
                    codes=[x.strip().rstrip(".*") for x in r["vessel_other_10b"].split(",") if x.strip().rstrip(".*")],
                )
                self.rows.setdefault(e.un, []).append(e)

    # ---- lookup -----------------------------------------------------------
    def lookup(self, un: str, packing_group: str = "") -> Entry | None:
        un = un.upper().replace(" ", "")
        if re.fullmatch(r"\d{4}", un):
            un = "UN" + un
        rows = [r for r in self.rows.get(un, []) if r.hazard_class != "Forbidden"]
        if not rows:
            return None
        if packing_group:
            pg_rows = [r for r in rows if r.packing_group == packing_group.upper()]
            rows = pg_rows or rows
        return rows[0]

    # ---- hazards used for segregation --------------------------------------
    @staticmethod
    def hazards(e: Entry) -> list[str]:
        """Primary class plus subsidiary labels (176.83(a)(6))."""
        out = [e.hazard_class]
        for lab in e.labels:
            lab = lab.split()[0]
            if lab == e.hazard_class or not re.fullmatch(r"[1-9](\.\d)?[A-S]?", lab):
                continue
            if lab.startswith("1"):  # explosive subsidiary: treat as 1.4 (1.3 for 5.2)
                lab = "1.3" if e.hazard_class == "5.2" else "1.4"
            out.append(lab)
        return out

    def general_level(self, a: Entry, b: Entry) -> tuple[int, list[str]]:
        best, why = 0, []
        for ha in self.hazards(a):
            for hb in self.hazards(b):
                cell = self.matrix[matrix_key(ha)][matrix_key(hb)]
                if cell.isdigit() and int(cell) > best:
                    best = int(cell)
                    why = [f"176.83(b) table: class {ha} vs class {hb} = {cell} ({LEVEL_NAMES[int(cell)]})"]
                elif cell == "(*)" and best < 2:
                    why.append("Both Class 1: compatibility groups decide (176.144); not modelled")
        return best, why

    def code_level(self, src: Entry, other: Entry, other_groups: list[str]) -> tuple[int, list[str]]:
        """Column 10B codes of `src` that target the other cargo."""
        best, why = 0, []
        other_divs = {base_division(h) for h in self.hazards(other)}
        for code in src.codes:
            text = self.codes.get(code, "")
            low = text.lower().replace("“", "").replace("”", "").replace('"', "")
            level = next((lv for pat, lv in PHRASE_LEVEL if re.search(pat, low)), 0)
            if not level:
                continue
            hit = False
            for pat, classes in CLASS_WORDS:
                if re.search(pat, low) and other_divs & set(classes):
                    hit = True
                    break
            if not hit and other.un.lower() in low:
                hit = True
            if not hit:
                stem = other.name.split(",")[0].split("(")[0].strip().lower()
                if len(stem) > 3 and re.search(rf"\b{re.escape(stem)}\b", low):
                    hit = True
            if not hit:
                for g in other_groups:
                    if re.search(rf"\b{re.escape(g.lower())}\b", low):
                        hit = True
                        break
            if hit and level > best:
                best = level
                why = [f"176.84 code {code} on {src.un}: {text.strip()}"]
        return best, why

    # ---- public API ----------------------------------------------------------
    def pair(self, a: Cargo, b: Cargo) -> dict:
        ea, eb = self.lookup(a.un, a.packing_group), self.lookup(b.un, b.packing_group)
        if not ea or not eb:
            missing = [c.un for c, e in ((a, ea), (b, eb)) if not e]
            return {"level": None, "status": "unknown", "reasons": [f"Not in 172.101: {', '.join(missing)}"]}
        if ea.un == eb.un:
            return {"level": 0, "status": "ok", "reasons": ["Same UN number"], "a": ea.cite, "b": eb.cite}
        lv, why = self.general_level(ea, eb)
        for src, dst, grp in ((ea, eb, b.groups), (eb, ea, a.groups)):
            l2, w2 = self.code_level(src, dst, grp)
            if l2 > lv:
                lv, why = l2, w2
            elif l2 and l2 == lv:
                why += w2
        same_ctu = bool(a.container) and a.container == b.container
        status = "violation" if (same_ctu and lv > 0) else ("ok" if lv == 0 else "segregate")
        if same_ctu and lv > 0:
            why.append("176.83(d): materials needing any segregation may not share one cargo transport unit")
        return {
            "level": lv,
            "requirement": LEVEL_NAMES[lv],
            "status": status,
            "reasons": why or ["176.83(b) table: no segregation required"],
            "a": ea.cite,
            "b": eb.cite,
        }

    # ---- where a single cargo may go (column 10A, location codes) ----------------
    ON_DECK_ONLY = {"C", "D"}

    def stowage_notes(self, e: Entry) -> list[str]:
        """Column 10A category and 10B codes that restrict where this one cargo may be stowed."""
        notes = []
        if e.stowage_cat in self.ON_DECK_ONLY:
            notes.append(f"172.101 column 10A: stowage category {e.stowage_cat}, on deck only")
        for code in e.codes:
            text = self.codes.get(code, "").strip()
            if re.search(r"living quarters|sources of heat|shaded|cool|well ventilated", text, re.I):
                notes.append(f"176.84 code {code} on {e.un}: {text}")
        return notes

    COMBUSTIBLE_CODES = {"4": "may not share a cargo transport unit with combustible material",
                         "59": "must be separated from combustible materials"}

    def combustible_conflicts(self, cargos: list[Cargo], others: list[tuple[str, str]]) -> list[dict]:
        """Codes 4 and 59 against ordinary cargo in the same container. `others` = (label, container) of
        non-regulated lines that are combustible (textiles, plastics, paper, wood, food and similar)."""
        out = []
        for c in cargos:
            e = self.lookup(c.un, c.packing_group)
            if not e or not c.container:
                continue
            for code, rule in self.COMBUSTIBLE_CODES.items():
                if code not in e.codes:
                    continue
                for label, box in others:
                    if box == c.container:
                        out.append({"a": c.label, "b": label, "level": 2, "status": "violation",
                                    "requirement": "Separated from (combustible material)",
                                    "reasons": [f"176.84 code {code} on {e.un}: {self.codes[code].strip()}",
                                                "176.83(d): may not share one cargo transport unit"],
                                    "cite_a": e.cite, "cite_b": f"{label}: ordinary cargo, combustible"})
        return out

    def check_manifest(self, cargos: list[Cargo]) -> list[dict]:
        out = []
        for i in range(len(cargos)):
            for j in range(i + 1, len(cargos)):
                r = self.pair(cargos[i], cargos[j])
                if r["level"] != 0:
                    out.append({"a": cargos[i].label, "b": cargos[j].label, **{k: v for k, v in r.items() if k not in ("a", "b")},
                                "cite_a": r.get("a"), "cite_b": r.get("b")})
        return sorted(out, key=lambda r: (r["status"] != "violation", -(r["level"] or 0)))
