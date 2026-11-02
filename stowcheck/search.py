"""Candidate retrieval over 172.101 proper shipping names (BM25, stdlib only)."""
from __future__ import annotations

import math
import re
from collections import Counter

from .engine import Rules

# Spelling only (British -> US as used in 49 CFR). Trade-name mapping is the AI's job.
SYN = {"sulphur": "sulfur", "aluminium": "aluminum", "fertiliser": "fertilizer", "sulphuric": "sulfuric",
       "colour": "color", "vapour": "vapor"}
TOK = re.compile(r"[a-z0-9]+")


def toks(s: str) -> list[str]:
    out = []
    for t in TOK.findall(s.lower()):
        out.append(SYN.get(t, t))
    return out


class Index:
    def __init__(self, rules: Rules):
        self.docs = []
        for un, rows in rules.rows.items():
            for e in rows:
                self.docs.append((e, Counter(toks(e.name))))
        n = len(self.docs)
        df = Counter(t for _, c in self.docs for t in c)
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}
        self.avg = sum(sum(c.values()) for _, c in self.docs) / n

    def search(self, query: str, k: int = 8):
        q = toks(query)
        scored = []
        for e, c in self.docs:
            L = sum(c.values())
            s = sum(self.idf.get(t, 0) * c[t] * 2.2 / (c[t] + 1.2 * (0.25 + 0.75 * L / self.avg)) for t in set(q) if t in c)
            if s > 0:
                scored.append((s, e))
        scored.sort(key=lambda x: -x[0])
        seen, out = set(), []
        for s, e in scored:
            key = (e.un, e.name)
            if key not in seen:
                seen.add(key)
                out.append(e)
            if len(out) == k:
                break
        return out
