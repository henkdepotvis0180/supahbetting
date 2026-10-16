# SupahBetting — instructies voor Codex

Projectdoel: één overzichtelijke Nederlandstalige voetbalanalyse-app met afzonderlijke dataverzameling, voorspellingsmodellen en paper trading. Geen gegarandeerde inkomsten.

## Architectuur
- `supahbetting/domain.py`: inputvalidatie, onafhankelijk Poisson-model, EV en combinatiekansen.
- `supahbetting/store.py`: lokale SQLite, odds-/kanssnapshots en settlements.
- `supahbetting/server.py`: localhost HTTP API en statische assets.
- `supahbetting/static/`: Nederlandstalige responsieve browserinterface.
- `supahbetting/importers.py`: veilige CSV/JSON import uit externe pipelines.
- `supahbetting/core.py`, `cli.py`, `web.py`: legacy v0.1/v0.2-tools; niet blind verwijderen zonder migratie.
- `tests/`: unit- en integratietests.

## Originele tools en forks
1. ProphitBet: `henkdepotvis0180/ProphitBet-Soccer-Bets-Predictor`; MIT LICENSE.txt. Scheid ML-dependencies.
2. OddsHarvester: `henkdepotvis0180/OddsHarvester`; MIT LICENSE.txt, Python 3.12+, Playwright. Geen ongeoorloofde scraping.
3. Prediict: `henkdepotvis0180/prediict`; licentie niet vastgesteld. Geen broncode kopiëren totdat toestemming/licentie is bevestigd.

De tools zijn *nog niet* direct aan elkaar gekoppeld. Het importformaat in README is de eerste interoperabele grens.

## Vereisten bij elke ontwikkeling
1. Paper-only is de standaard. Geen real-money orders of bookmaker-logins.
2. Behoud de onafhankelijke-vestigingsrestrictie: niet meerdere legs per wedstrijd combineren zonder aantoonbaar gezamenlijk kansmodel.
3. Prijzen en modelkansen **altijd server-side herleiden**, nooit inzetten op door browser aangeleverde odds.
4. Houd SQLite transactiegrenzen, inputvalidatie, local-only en CSP intact.
5. Differentieer bij analyses **theoretische** winstverwachting versus **gerealiseerd fictief** resultaat.
6. Voer na wijzigingen `python -m unittest discover -s tests -v` uit en herstel falende CI.
7. Gebruik chronologische en lekvrije validatie voordat een model betrouwbaar wordt genoemd.
8. Geen secrets, API keys, echte persoonlijke gegevens of wedstrijd-accounts committen.
9. Onderhoud Nederlandse README, CHANGELOG en testdekking.
10. Bewaar de integratiebranche totdat code review en tests zijn voltooid.
