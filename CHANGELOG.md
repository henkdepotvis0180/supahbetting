# Changelog

## v0.3.0 — 2026-10-17
- Nieuw responsief Nederlandstalig dashboard met duidelijke wedstrijdkaarten en mobiele layout.
- Combinatie-betslip voor 1–8 verschillende wedstrijden, server-side prijs-/kansberekening.
- Verwerping van meerdere selecties uit dezelfde wedstrijd vanwege correlatierisico.
- SQLite-transacties, opgeslagen odds- en modelkans-snapshots, winst/verlies bij handmatig ingevoerde resultaten.
- Scheiding tussen theoretische EV en gerealiseerde fictieve ROI.
- Nieuwe gevalideerde JSON-API op localhost met securityheaders en afgeschermde origin/host.
- CSV/JSON-import met standaardkolommen en fictieve demo-data.
- Unit- en API-integratietests, Windows-startscript en CI-matrix.
- De drie forks gecontroleerd; code niet blind gemengd vanwege omgevings- en licentieverschillen.
- Beperkingen: geen live bookmakerkoppeling, geen gevalideerd model, geen echt-geld inzetten.

## v0.2.0 — 2026-10-17
- Eerste lokale dashboard voor handmatige xG en odds.
- Eenvoudige papieren inzetsimulatie in een JSONL-bestand.

## v0.1.0 — 2026-10-17
- Basis Poisson, implied odds en expected value.
- Eerste tests en Codex-instructies.
