# Changelog

## v0.4.0 — 2026-10-17
- Live OpenLigaDB-scores zonder API-key: Bundesliga 1/2/3, Champions League, DFB-Pokal, Frauen-Bundesliga, La Liga en Premier League (community).
- Klikbare wedstrijdkaarten, scorebord, doelpuntenfeed met minuten/spelers en zichtbare bronupdates.
- Automatische verversing (90 seconden wedstrijden / 45 seconden details) zolang het tabblad actief is.
- Server-side HTTPS-bronallowlist, time-outs, begrensde antwoorden, caching, 120 seconden retry-backoff en stale-melding.
- Optionele handmatig geverifieerde officiële YouTube-nocookie-embed met hostallowlist; geen ongeautoriseerde streams.
- Geplande wedstrijd kan worden overgenomen naar het handmatige analyseformulier; xG/odds blijven verplicht handmatig.
- OpenLigaDB ODbL-bronvermelding in interface en documentatie.
- Offline unit- en HTTP-integratietests voor de live-provider en aanvullende JavaScript-controle.
- Geen live bookmakerodds, geen automatische selectie van rechtenvrije uitzendingen en geen echte inzetten.


## v0.3.0 — 2026-10-17
- Nieuw responsief Nederlandstalig dashboard met duidelijke wedstrijdkaarten en mobiele layout.
- Combinatie-betslip voor 1–8 verschillende wedstrijden, server-side prijs-/kansberekening.
- Verwerping van meerdere selecties uit dezelfde wedstrijd vanwege correlatierisico.
- SQLite-transacties, opgeslagen odds- en modelkans-snapshots, winst/verlies bij handmatig ingevoerde resultaten.
- Scheiding tussen theoretische EV en gerealiseerde fictieve ROI.
- Modelkwaliteitscontrole met Brier-score en log-loss tegenover de bookmakerskansen zonder marge (sample-waarschuwing).
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
