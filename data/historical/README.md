# Historical football results — source and completeness

These CSV files contain **real completed football match scores**, not fictitious
data, inferred predictions, betting prices, or proprietary shot-level xG.

Original upstream: [openfootball/football.json](https://github.com/openfootball/football.json) (data released as **CC0 1.0 Universal**).
Files are snapshots of the upstream `<season>/<league>.json` data as fetched
2026-10-17. Only rows with a valid ISO match date, team names, and integer
full-time results `score.ft` were retained. CSV field names: league, season,
date, home, away, home_goals, away_goals. All 7 league CSVs are committed to
allow offline and reproducible training.

| Competition | ID | Retained completed games (2020-21 through 2025-26) | Important warnings |
|---|---|---:|---|
| Eredivisie | nl.1 | 1,825 | 2025-26 has 295 of 306 recorded matches |
| Belgian Pro League | be.1 | 747 | No files for 2021-22, 2022-23 and 2023-24; 2025-26 has only 104 completed matches in upstream snapshot |
| Premier League | en.1 | 2,253 | 2025-26 records 353/380 results |
| Bundesliga | de.1 | 1,824 | 2025-26 records 294/306 |
| La Liga | es.1 | 2,255 | Both 2024-25 and 2025-26 have missing results in upstream snapshot |
| Serie A | it.1 | 2,234 | Both 2024-25 and 2025-26 have missing results in upstream snapshot |
| Ligue 1 | fr.1 | 2,034 | 2025-26 records 282/306 |

**Total: 13,172 completed historical results.**

Why include incomplete seasons? Only *actually recorded final scores* are
used. The report flags coverage gaps and does not pretend absent games were
played, nor that holdout periods represent a full season.

Data provenance is maintained through upstream repository URLs and snapshot
file hashes in the data-import commit history. For changed/expanded datasets:
verify the upstream CC0 license and attribution, ensure that records are
historical **as of prediction time**, preserve date/season/league IDs, and
rerun `python -m supahbetting.trained_model`.

The trainer will never scrape an API, read any personal credentials, or
generate scores for unplayed matches.
