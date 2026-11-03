# Changelog

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
