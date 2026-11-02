# StowCheck

**Live demo:** https://stowcheck.vercel.app

You paste a container ship manifest in plain words, such as "pool chlorine tablets" or "car batteries". StowCheck works out which dangerous goods are hiding in it and checks which ones must be kept apart on the ship under US 49 CFR. Each finding cites the regulation row it comes from. When the tool isn't sure, it says so and hands the item to a human.

## The problem

- A container ship fire breaks out about every 17 days, and misdeclared or undeclared dangerous goods are a leading cause (Allianz *Safety & Shipping Review 2026*, cited by the [World Shipping Council](https://www.worldshipping.org/news/misdeclared-dangerous-goods-remain-a-persistent-threat-to-shipping-and-supply-chains) and [gCaptain](https://gcaptain.com/containership-fire-breaks-out-every-17-days-as-misdeclared-cargo-remains-major-threat/)).
- The [DGEval benchmark](https://arxiv.org/abs/2608.21036) (Aug 2026, NCB Hazcheck and Durham University) tested 13 frontier models on the dangerous goods code. Even the best scored only about 50% on stowage and segregation ([natcargo](https://natcargo.org/dgeval/)).

## How it works

The AI does the language work and the code applies the rules.

1. **AI reads the description** and writes search terms in regulatory language ("power bank" becomes "lithium ion batteries").
2. **Code retrieves candidate rows** from the 49 CFR 172.101 Hazardous Materials Table (3,001 rows), using BM25 search.
3. **AI picks a real row** or says "not sure". It also tags chemical families such as "acids" or "cyanides". It cannot invent a UN number, because it can only choose from rows the code retrieved.
4. **Code checks every pair** against the 176.83(b) segregation table, including subsidiary hazards, and against the 176.84 codes in column 10B, which is where the chemical families matter. It also applies the 176.83(d) rule that segregated goods may not share a container.
5. **Every finding cites its rule.** If any cargo is unidentified, the result is marked *incomplete* rather than "safe".

## Results

All results use the same free model in both arms: Gemma 4 26B through the Gemini API free tier. The data, scripts and raw outputs are in `eval/`.

**Test A: 100 real pairs of commonly shipped dangerous goods. Task: name the required segregation level.**

| | Exact | Too lenient (unsafe) | No answer |
|---|---|---|---|
| Model alone | 48 / 100 | 24 | 28 (timed out twice) |
| Rule table only, no AI | 88 / 100 | 12 | 0 |
| **StowCheck (AI + rules)** | **100 / 100** | **0** | **0** |

The answer key comes from the regulation text applied by hand, and that text is the same table the engine encodes. So Test A mainly shows that the free model cannot apply the rules reliably on its own, and that the AI's real job here (tagging chemical families) closes the 12-pair gap the table leaves.

**Test B: 60 shipping descriptions written like real invoices.** These include 39 clear dangerous goods, 7 that are hard but decidable, 5 that are vague, and 9 that are not dangerous.

| | UN number right (clear DG) | UN number right (hard items) | Dangerous cargo called safe |
|---|---|---|---|
| Model alone | 66.7% | 1 / 7 | 2 |
| **StowCheck** | **87.2%** | **6 / 7** | **0** |

Both arms said "not sure" on 4 of the 5 vague items, and neither flagged any of the 9 ordinary goods as dangerous. StowCheck numbers use the final prompt; items that hit API timeouts were re-asked once.

## Limits

- The rules are US 49 CFR only. The IMDG Code is copyrighted, so it is not included.
- Class 1 (explosives) compatibility groups, the 176.83(a) exceptions, and container-ship spacing distances (table 176.83(f)) are not modelled.
- The test sets are small (100 and 60 items) and hand-built.
- This is a research demo. It is not for operational use.

## Run it

```bash
pip install -r requirements.txt
export GROQ_API_KEY=...        # or GEMINI_API_KEY; STOWCHECK_MODEL to override
uvicorn api.index:app --reload
python3 -m pytest tests
python3 eval/run_test_a.py --mode table      # no key needed
```

## Data and credits

- The 49 CFR 172.101, 176.83 and 176.84 data is a US Government work in the public domain. It was copied from [TurpoFIN/huolitsija-submission](https://github.com/TurpoFIN/huolitsija-submission), which parsed it from eCFR as of 2026-10-22; see `data/SOURCES.md`.
- Models: Gemma 4 and Gemini via the Google AI free tier; Llama 3.3 via the Groq free tier.
