# Data sources

- hmt_172_101.csv: 49 CFR 172.101 Hazardous Materials Table (3,001 rows). Copied from github.com/TurpoFIN/huolitsija-submission (commit fe5b9b8, backend/data/dg/hmt_172_101.csv), which built it from eCFR point-in-time 2026-10-22. US Government work, public domain (17 U.S.C. 105).
- segregation_176_83.json: 49 CFR 176.83(b) general segregation matrix + legend, 172.101(k) stowage categories, 176.84 codes. Same repo and commit (backend/data/dg/segregation.json).
- To do: spot-check both against eCFR text; transcribe table 176.83(f) (container vessels).
