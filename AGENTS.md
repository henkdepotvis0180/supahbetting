# SupahBetting — instructies voor Codex

Projectdoel: één overzichtelijke Nederlandstalige voetbalanalyse-app met afzonderlijke dataverzameling, voorspellingsmodellen en paper trading. Geen gegarandeerde inkomsten.

## Architectuur
- `supahbetting/domain.py`: inputvalidatie, onafhankelijk Poisson-model, EV en combinatiekansen.
- `supahbetting/store.py`: lokale SQLite, odds-/kanssnapshots en settlements.
- `supahbetting/evaluation.py`: Brier- en log-loss-benchmark op geregistreerde uitslagen.
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


## Live-feed instructies v0.4
- supahbetting/live_scores.py levert een streng begrensde, gecachte OpenLigaDB scorefeed.
- supahbetting/static/live.js is de aparte interface voor live wedstrijden en doelpuntentijdlijn.
- API-routes: GET /api/live/leagues, GET /api/live/matches?league=all|bl1|bl2|bl3|ucl|dfb|ffb1|la1|pl en GET /api/live/matches/<id>?league=<shortcut>.
- OpenLigaDB-data vallen onder Open Database License (ODbL) 1.0: behoud bronvermelding en controleer eisen voor databases.
- Status estimated_live betekent alleen **mogelijk bezig**, afgeleid van aftraptijd; nooit presenteren als officieel bevestigd.
- Geen live score omzetten naar bookmakerodds, model-xG, uitslagen-afhandeling of echte inzet zonder gescheiden verificatie.
- Nooit lokale URL-input of redirects naar onbeperkte hosts introduceren.
- Videoframes zijn uitsluitend opt-in voor handmatig geverifieerde officiële YouTube-nocookie-embeds.
- Geen video van illegale streamsites, geen inlog- of toegangsrestricties omzeilen.
- Offline tests voor bronvelden, foutcondities en API-routes verplicht.

## Aanvullende providers (v0.5)
- supahbetting/external_feeds.py bevat veilige, gecachte adapters voor TheSportsDB v1 en football-data.org v4.
- OpenLigaDB heeft een community-doelpuntenfeed; TheSportsDB gratis levert hoogstens beperkt schema; football-data.org gratis is vertraagd.
- Gebruik alleen vastgelegde competities en HTTPS-hosts. Geen willekeurige doel-URL's of API-sleutels via de browser.
- football-data.org token alleen via lokale environment FOOTBALL_DATA_API_KEY en server-side X-Auth-Token header, nooit in logs, code of GitHub.
- TheSportsDB gratis niet publiceren als mobiele appstore-app zonder betaald abonnement. Controleer bronvermelding en gebruiksvoorwaarden.
- Houd de live-scores gescheiden van modelkansen en boekmakerquoteringen; geen verzonnen live odds.
- Voeg voor elke integratie tests toe met fake providers die offline draaien.

## Modulaire lokale API-config (v0.5.1)
- Gebruik altijd supahbetting/provider_config.py voor lokale API-credentials. Het echte bestand staat in .supahbetting/providers.json en wordt door supahbetting.server.main bij de eerste start aangemaakt.
- config/providers.example.json bevat nooit echte credentials en mag worden gecommit.
- bewerk_api_config.bat opent op Windows veilig alleen het lokale JSON-bestand in Kladblok.
- Per provider: providers > provider-id > api_key. De parser werkt met meerdere providers maar het toevoegen van JSON alleen activeert geen nieuwe API; implementeer per bron een afzonderlijke veilige adapter.
- De ingevulde config-API-sleutel heeft voorrang op de legacy FOOTBALL_DATA_API_KEY Windows-variable. Een leeg veld valt terug op de variabele.
- Geen sleutels in UI, API-antwoorden, foutdetails of logregels. Nooit credentials, debug dumps of echte ingevulde JSON in commits, tests, issues of screenshots.
- Respecteer providervoorwaarden, vaste HTTPS-host allowlists, de status van gratis vs betaald en rate limits.
- Na configbewerkingen moet de server opnieuw worden gestart. Geen browser-endpoint schrijven dat credentials kan aanpassen of uitlezen.
- Test in CI offline en met fictieve sleutels via tempfile; controleer dat de andere providers beschikbaar blijven bij ongeldig JSON.

## v0.6 Native fork export bridge
- **supahbetting/fork_bridge.py** herkent native dataformaten: ProphitBet GUI fixture Prediction CSV, OddsHarvester voetbal 1x2_market JSON/CSV, Prediict value_bets CSV en 1X2-probability CSV.
- **supahbetting/fork_research.py** bevat aparte onderzoekstabellen, dedup, strikte event- en marktmatches, stale pricing flags en theoretical EV. De bestaande Store/slips zijn onaangetast.
- **supahbetting/research_cli.py** en browserknop importeren lokale exports. Bestanden staan in .supahbetting/imports/{prophitbet,oddsharvester,prediict}. Geen onbegrensde bestandspaden via HTTP.
- **supahbetting/static/research.js** presenteert onderzoeksresultaten en bronvermelding, geen real-money transactie.
- De originele ML-componenten zijn **niet uitgevoerd of gebundeld**: ProphitBet Qt/TensorFlow/scikit-learn, OddsHarvester Playwright en Prediict joblib hebben eigen uitvoeromgeving.
- Prediict heeft geen aangetoonde licentie voor herdistributie: neem geen broncode of modelbestanden over en laad geen ongecontroleerde pickle/joblib.
- OddsHarvester-exportdata alleen importeren na wettige, toegestane verzameling; geen automatische omzeiling van oddsprovider-inlog, CAPTCHA, rate limiting of voorwaarden.
- Alleen volledig expliciete wedstrijd/marktmatching; géén fuzzy auto-team matching, geen eerdere kalenderdatum samenvoegen, geen ongedateerde cross-file matching.
- Toon nooit oude of ongedateerde boekmakerquotes als live prijzen. Positive EV van niet onafhankelijk gekalibreerde modellen is geen bewezen voordeel.
- Tests: python -m unittest discover -s tests -v; Python 3.11+; node --check supahbetting/static/research.js.
- Bij uitbreiding ondersteunt het systeem nieuwe adapters via native exports, bronregistratie en expliciete geïsoleerde tests.

## v0.7 Historisch getraind model
- Databron: openfootball/football.json (CC0 1.0 Universal), snapshots in data/historical/{nl.1,be.1,en.1,de.1,es.1,it.1,fr.1}.csv; herkomst data/historical/README.md.
- Reproduceerbare training: python -m supahbetting.trained_model; gegenereerd artefact supahbetting/models/baseline.json; optionele Windows-knop train_model.bat.
- Gebruik geen shot-xG-claim: output is empirische verwachte goals geleerd op basis van eindstanden, niet echte xG-gebeurtenissen.
- Hyperparameterkeuze strikt uit 2024/25 (validatie), 2025/26 is chronologisch gehouden test. Eerder-die-dag resultaten mogen nooit in voorspellingen van dezelfde speeldag lekken.
- Modelkwaliteit altijd vergelijken met referentie door Brier en log loss. Per-league incomplete brondata tonen; Belgisch seizoen heeft grote gaten.
- Modelbestand mee publiceren zodat gebruiker niet zelf hoeft te trainen. Geen automatische trainingsrun bij opstarten nodig.
- API /api/trained/status en POST /api/trained/predict. Alleen bekende provider/league/teams en bewuste aliasregels; geen onzekere fuzzy matching.
- Live geplande wedstrijden mogen uitsluitend getrainde doelpuntverwachting invullen; bookmakerodds blijven leeg en moeten onafhankelijk worden ingevoerd.
- Hertraining op nieuwe wedstrijden mag eerdere 2024/25-val/hyperparameters en 2025/26-testgrens nooit retrospectief lekken.
- De originele ProphitBet-, OddsHarvester- en Prediict-programma's worden niet in-process getraind of gekopieerd. Native CSV/JSON-exportadapters blijven.
- Niet claimen dat een betere Brier-score tegen een gemiddelde referentie bewijst dat bookmakerprijzen te verslaan zijn.
