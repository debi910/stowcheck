# StowCheck

**Live demo:** https://stowcheck.vercel.app

You paste a container ship manifest in plain words, such as "pool chlorine tablets" or "car batteries". StowCheck works out which dangerous goods are hiding in it and checks which ones must be kept apart on the ship under US 49 CFR. Each finding cites the regulation row it comes from. When the tool isn't sure, it says so and hands the item to a human.

## The problem

- A container ship fire breaks out about every 17 days, and misdeclared or undeclared dangerous goods are a leading cause (Allianz *Safety & Shipping Review 2026*, cited by the [World Shipping Council](https://www.worldshipping.org/news/misdeclared-dangerous-goods-remain-a-persistent-threat-to-shipping-and-supply-chains) and [gCaptain](https://gcaptain.com/containership-fire-breaks-out-every-17-days-as-misdeclared-cargo-remains-major-threat/)).
- The [DGEval benchmark](https://arxiv.org/abs/2608.21036) (Aug 2026, NCB Hazcheck and Durham University) tested 13 frontier models on the dangerous goods code. Even the best scored only about 50% on stowage and segregation ([natcargo](https://natcargo.org/dgeval/)).

## What you can do with it

- **Upload the document you already have.** Drop a packing list, commercial invoice or manifest (PDF, Excel or CSV). The file is read in your browser, the AI pulls out the cargo lines and container numbers, and you review them before anything is checked. A sample 20-line packing list is in `public/samples/`.
- **Get a stowage report.** One printable page (save as PDF) with the violations, the lines that need a human, what each line was identified as, and a sign-off line for the dangerous-goods officer.
- **Catch some misdeclarations.** A UN number that is not in the 172.101 table is rejected. A typed UN number whose description reads like a different hazard class, or like ordinary goods, is flagged.

## How it works

The AI does the language work and the code applies the rules.

1. **AI reads the description** and writes search terms in regulatory language ("power bank" becomes "lithium ion batteries").
2. **Code retrieves candidate rows** from the 49 CFR 172.101 Hazardous Materials Table (3,001 rows), using BM25 search.
3. **AI picks a real row** or says "not sure". It also tags chemical families such as "acids" or "cyanides". It cannot invent a UN number, because it can only choose from rows the code retrieved.
4. **Code checks every pair** against the 176.83(b) segregation table, including subsidiary hazards, and against the 176.84 codes in column 10B, which is where the chemical families matter. It also applies the 176.83(d) rule that segregated goods may not share a container.
5. **Every finding cites its rule.** If any cargo is unidentified, the result is marked *incomplete* rather than "safe".

## Results

All results use the same free model in both arms: Gemma 4 26B through the Gemini API free tier. The live demo runs a different free model (Groq, currently openai/gpt-oss-120b), so the demo's answers can differ from these numbers. Data, scripts and every answer are in `eval/`.

**Held-out test (Test D): 30 new descriptions, written after the prompts were frozen and run once.** 24 clear dangerous goods, 3 ordinary goods, 3 vague or undecidable.

| | UN number right (clear DG) | Dangerous cargo called safe |
|---|---|---|
| Model alone | 15 / 24 (62.5%) | 0 |
| **StowCheck** | **21 / 24 (87.5%)** | **0** |

The first attempt hit 9 API timeouts on the StowCheck side, so the whole set was re-run at lower concurrency. Both runs are published (`test_d_*_run1.json`: 13 vs 16 of 24). StowCheck's misses: sodium hypochlorite and ammonia solution (said dangerous but picked no row), carbon dioxide (API error, counted wrong). It also called the vague "Car parts (used)" not dangerous, where the model alone said "not sure".

**Real incidents (Test C): 7 declarations taken from container-ship fire investigations.** The real cargo was dangerous every time (Yantian Express 2019, KMTC Hong Kong 2019, Gard case files on calcium hypochlorite). Sources are in `eval/test_c_incidents.csv`.

| | Flagged or sent to a human | Cleared as safe |
|---|---|---|
| Model alone | 4 / 7 | 3 |
| StowCheck | 4 / 7 | 3 |

StowCheck is no better here. "Coconut pellets", "Dolls" and "Calcium chloride" describe harmless goods, so no reader of the words alone could catch them. This is why StowCheck also checks a typed UN number against its description, rejects UN numbers that are not in the table, and never reports "safe" while a line is unsure.

**Development set (Test B): 60 invoice-style descriptions.** The prompts were written while looking at this set, so treat it as a development score.

| | UN number right (39 clear DG) | Hard items (7) | Dangerous cargo called safe |
|---|---|---|---|
| Model alone | 66.7% | 1 / 7 | 2 |
| **StowCheck** | **87.2%** | **6 / 7** | **0** |

**Segregation pairs (Test A): 100 pairs of common dangerous goods. Task: name the required segregation level.**

| | Exact | Too lenient (unsafe) | No answer |
|---|---|---|---|
| Model alone | 48 / 100 (48 of 72 answered) | 24 | 28 (timed out twice) |
| Rule table only, no AI | 88 / 100 | 12 | 0 |
| **StowCheck (AI + rules)** | **100 / 100** | **0** | **0** |

The answer key comes from the regulation text, which is the same table the engine encodes, so 100 shows the engine is wired right. What Test A really shows is that the free model cannot apply the rules reliably on its own, and that the AI's job (tagging chemical families) closes the 12-pair gap the table leaves.

For context only: the external [DGEval benchmark](https://arxiv.org/abs/2608.21036) found the best of 13 frontier models scored about 50% on stowage questions. It is a different task and data set from ours.

## Limits

- The rules are US 49 CFR only. The IMDG Code is copyrighted, so it is not included.
- Class 1 (explosives) compatibility groups, the 176.83(a) exceptions, and container-ship spacing distances (table 176.83(f)) are not modelled.
- The test sets are small (100 pairs, 60, 30 and 7 descriptions) and hand-built by the team, except the 7 incident declarations, which come from published investigations.
- Words alone cannot expose a deliberately false declaration (see Test C).
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
- Models: Gemma 4 and Gemini via the Google AI free tier; gpt-oss-120b via the Groq free tier for the live demo.
