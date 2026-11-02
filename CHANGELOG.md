# Changelog

## 2026-11-02
- Added 49 CFR 172.101 table (3,001 rows) and 176.83(b)/176.84 segregation data (public domain, see data/SOURCES.md).
- Added deterministic segregation engine: general table, subsidiary hazards, column 10B codes, same-container rule.
- Added hand-verified unit tests.
- Fixed chemical-group matching (whole phrase, not word stem).
- Added Test A: 100 stratified pairs of commonly shipped dangerous goods (Class 1 excluded), gold reviewed against 176.83(b)/176.84 text.
- Added free-model client (Groq or Gemini, OpenAI-compatible) and Test A runner. Table-only engine (no AI): 88% exact, 52% on pairs decided by chemical-group codes.
