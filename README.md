# StowCheck

Paste a cargo manifest and get a container-ship segregation check for dangerous goods. Every finding cites the exact 49 CFR row it comes from, and the tool says "not sure" instead of guessing.

**Why:** a container ship fire breaks out about every 17 days, driven largely by misdeclared dangerous goods (Allianz Safety & Shipping Review 2026, via [gCaptain](https://gcaptain.com/containership-fire-breaks-out-every-17-days-as-misdeclared-cargo-remains-major-threat/)). The [DGEval benchmark](https://arxiv.org/abs/2608.21036) tested 13 frontier models, and they scored about 50% on stowage and segregation questions.

**How:** AI identifies what each cargo is (UN number, packing group, chemical groups such as "acids"). Code applies the regulation (49 CFR 172.101, 176.83, 176.84).

Work in progress. Scope: US 49 CFR only, not the IMDG Code. Not for operational use.
