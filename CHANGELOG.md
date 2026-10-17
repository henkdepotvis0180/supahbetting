# Changelog

## v0.7.0 — 2026-10-17
- **Echt getraind 1X2-basismodel** met Elo-sterkte, recente vorm en logistieke regressie, modelparameters opgeslagen als veilig JSON zonder pickle/joblib.
- GitHub Actions traint op 18.085 historische wedstrijden uit jouw Prediict-fork; vijf grote Europese competities.
- Chronologische train/validatie/holdout-toetsing, 3.143 testwedstrijden: 53,33% nauwkeurigheid, 0,98164 log loss tegenover 44,61% en 1,06924 voor een eenvoudig constant referentiemodel.
- Definitieve JSON-parameters zijn ná die holdout opnieuw op de gehele bronhistorie getraind. De gerapporteerde testcijfers horen bij het eerdere pretest-model, niet bij een onafhankelijk geteste definitieve fit.
- Brongegevens lopen slechts tot **2024-06-02**; expliciete ouderdomswaarschuwing in de applicatie.
- Live wedstrijdpopup krijgt knop **Bereken modelkansen** met geschatte 1/X/2 en waarschuwing bij onbekende teams of oude historische informatie.
- Modellen worden los van de oddsvergelijking en paperbets gehouden; geen automatische koppeling met bookmakerprijzen.
- Apart lokaal Windows-script train_baseline.bat om met volledige, bijgewerkte historie opnieuw te trainen in eigen Python-venv.
- Extra API-endpoints voor status en modelanalyse, directe chronologische lekpreventietests, dataset-hash voor reproduceerbaarheid en Nederlandstalig trainingslogboek.
- Geen bewezen waarde boven bookmakerkansen, geen live odds en geen geldtransacties.


## v0.6.0 — 2026-10-17
- Drie echte native exportadapters toegevoegd voor ProphitBet-v2 (CSV), OddsHarvester (CSV/JSON/NDJSON) en Prediict (CSV/JSON).
- Alleen geverifieerde velden en 1X2-uitkomsten gekoppeld; geen code of modelbestanden van Prediict gekopieerd wegens ontbrekende licentie.
- ProphitBet Prob(1), Prob(X), Prob(2) en eigen ingevoerde odds; OddsHarvester 1x2_market per bookmaker, inclusief blokkadecheck; Prediict model_probability en bookmaker_odds.
- Aparte SQLite-onderzoekstabellen; SHA-256-importdeduplicatie; geen overschrijven van paperbets.
- Matches samenvoegen alleen bij dezelfde genormaliseerde teams, datum en markt; undated exports alleen binnen dezelfde bestandsrij.
- Nieuwe Nederlandstalige onderzoeksranglijst met model-EV, model-/odds-bron, historische/oude/onbekende prijstijd.
- Eén klik: Bronbestanden inlezen, opstartscan, bronbestanden_inlezen.bat en research_cli.
- Fictieve, historische voorbeeldbestanden voor alle drie de adapters.
- Extra veiligheidstests voor verdachte CSV/JSON, verkeerde wedstrijden, oude odds, symlinks en dubbele import.
- De originele ML/scraperprocessen worden bewust niet automatisch gestart; zware externe dependencies blijven geïsoleerd.
- Alle drie de oorspronkelijk geforkte projecten kunnen zelfstandig blijven updaten. Geen bewezen winstgevendheid.


## v0.5.1 — 2026-10-17
- Eén modulair, lokaal JSON-configuratiebestand voor API-sleutels: .supahbetting/providers.json.
- Automatisch een leeg bestand aanmaken bij eerste dashboardstart, bestaande sleutels nooit overschrijven.
- Windows-tool bewerk_api_config.bat: open het lokale bestand in Kladblok.
- football-data.org leest zijn API-token uit providers > football-data > api_key.
- De oude Windows-omgevingsvariabele FOOTBALL_DATA_API_KEY blijft bestaan als fallback.
- Nieuwe aanbieders kunnen dezelfde centrale configuratieparser gebruiken, maar hebben nog een eigen adapter nodig.
- JSON-validatie, 32 KB-limiet, credentials niet in UI/API-foutmeldingen en beperkt bestandsrecht op Unix.
- Malformed JSON schakelt alleen de betreffende geconfigureerde API-bron uit; de rest van het dashboard blijft bruikbaar.
- Tests toegevoegd voor eerste start, behoud van sleutels, provider-uitbreiding, foutafhandeling en privacy.


## v0.5.0 — 2026-10-17
- Multi-provider wedstrijdoverzicht: OpenLigaDB, gratis TheSportsDB v1 en optioneel football-data.org v4.
- Eredivisie, Eerste Divisie, Belgische Pro League en internationale competities.
- TheSportsDB: gratis beperkte wedstrijdgegevens voor gisteren/vandaag/morgen, geen echte live scores.
- football-data.org: persoonlijke API-sleutel in lokale omgevingsvariabele, vertraagde scores en 10-minuten-cache.
- Eén klikbare wedstrijdpopup, dynamisch bron-/competitiefilter en zichtbare bron-, vertragings- en licentievermeldingen.
- HTTPS-hostallowlists, timeouts, redirects blokkeren, caching en offline tests voor alle providers.
- Geen automatische bookmakerodds, geen bron-onafhankelijke winstgarantie en geen ongeautoriseerde video.


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
