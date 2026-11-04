# Changelog

## 2026-11-04
- Added Groq gpt-oss-120b (the live demo's model) results for Tests B, C and D. Held-out UN exact: 9/24 alone vs 21/24 StowCheck; development set 35.9% vs 79.5%, confident DG misses 4 vs 0; incidents 5/7 vs 4/7. Page and README now show both models.

## 2026-11-03
- Added document upload: PDF (pdf.js), Excel (SheetJS) and CSV are read in the browser; the AI extracts cargo lines and container numbers for the person to review before checking. Tested on the sample packing list: 20 of 20 lines extracted.
- Added a printable stowage report with violations, items needing a human, identifications and a sign-off line.
- Added a 20-line sample packing list (PDF and CSV) with hidden hazards and one mismatched UN number.
- Raised the function time limit to 120 s for longer manifests.
- Added Test C: 7 real misdeclared cargo declarations from container-ship fire investigations, run once. Model alone and StowCheck both 4/7 flagged or sent to a human; 3 cleared by both (published as a limit).
- Added Test D: 30 held-out descriptions, written after prompts were frozen, run once. UN exact on 24 clear DG: 15 alone vs 21 StowCheck; 0 dangerous cargo called safe on either side. First attempt had 9 API timeouts; re-run at lower concurrency, both runs kept.
- Added misdeclaration check: a typed UN number not in 172.101 is rejected, and one whose description reads like a different class or ordinary goods is flagged.
- Redesigned the web page: light, neutral, monochrome with status colours only for meaning. Evaluation section leads with held-out and real-incident results, including failures.
- README and page numbers restated with sample sizes, development-set caveat, Test A answer-key caveat, and the demo-model difference.

## 2026-11-02
- Added 49 CFR 172.101 table (3,001 rows) and 176.83(b)/176.84 segregation data (public domain, see data/SOURCES.md).
- Added deterministic segregation engine: general table, subsidiary hazards, column 10B codes, same-container rule.
- Added hand-verified unit tests.
- Fixed chemical-group matching (whole phrase, not word stem).
- Added Test A: 100 stratified pairs of commonly shipped dangerous goods (Class 1 excluded), gold reviewed against 176.83(b)/176.84 text.
- Added free-model client (Groq or Gemini, OpenAI-compatible) and Test A runner. Table-only engine (no AI): 88% exact, 52% on pairs decided by chemical-group codes.
- Added Test B: 60 shipping descriptions (46 dangerous goods incl. 8 ambiguous, 14 non-DG or vague), gold UN numbers checked against 172.101.
- Added BM25 retrieval over 172.101 names and grounded identification (AI search terms -> table candidates -> AI picks -> abstain). Raw-description retrieval alone: recall@6 = 37/46.
- Added FastAPI web API and single-page demo (manifest in plain words -> identification -> segregation findings with citations); Vercel config.
- Free model default: gemini-3.5-flash via Gemini OpenAI-compatible API (gemini-2.5 is closed to new keys); longer timeout and retries.
- Evals now run in parallel; Gemma 4 26B (open model, free tier) used because Gemini flash free tier is 20 requests/day.
- First eval run (Gemma 4 26B, free tier, 2026-11-02): Test A baseline 48/100 exact (48/72 answered, 24 too lenient, 28 unparseable/no answer); ours 100/100. Test B UN exact on clear dangerous goods: baseline 66.7%, ours 84.6%; confident misses of dangerous goods: baseline 2, ours 0. Results in eval/results/.
- Test B scoring split into clear / hard-but-decidable / truly vague items. Gemma 4 run: UN exact on hard items baseline 1/7 vs ours 6/7; vague abstain 4/5 both.
- API identifies manifest lines in parallel.
- Re-asked the 28 Test A baseline no-answers: all timed out again (model still thinking after 150 s, 4 tries each, 2 rounds). Final baseline: 48/100 exact, 48/72 of answered, 24 too lenient.
- Auto-pick a live model when the provider has retired the configured one (Groq retired llama-3.3-70b-versatile).
- Demo: violations first, other keep-apart pairs collapsed; picker prompt prefers the product's own entry and does not map finished articles (clothing etc.) to raw-material entries. Test B to be re-run with this prompt.
- Test B re-run with final prompt (timeouts re-asked): ours UN exact on clear DG 87.2% (34/39), hard 6/7, 0 confident DG misses, 0 false alarms on ordinary goods.
- New UI: hero with animated ship, stats strip, manifest workbench, staged progress, verdict banner, container view with hazard diamonds, plain-English violation cards with citations, detail drawer, animated results bars; reduced-motion support.
