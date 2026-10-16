# SupahBetting v0.4.0

**Lokaal Nederlandstalig voetbalanalyseplatform met een betrouwbare basis voor enkelvoudige én combinatie-betslips.**

SupahBetting is software voor onderzoek en **fictieve weddenschappen**. Nieuw in v0.4: openbare live **scoredata en doelpunten**. Er zijn **geen live bookmakerquoteringen**, geen directe bookmakeraccounts en geen functie voor echt geld. De modelkansen zijn nog niet gekalibreerd of onafhankelijk gevalideerd. Een positieve model-EV is **geen bewijs van winstgevendheid**.

## Wat is werkend?

- **Live**: zeven OpenLigaDB-competities, klikbare wedstrijdkaarten, scorebord en doelpunten met minuten.
- Automatische verversing: lijst ongeveer 90 seconden, geopende wedstrijd ongeveer 45 seconden.
- Optioneel alleen handmatig geverifieerde officiële openbare YouTube-embed; geen automatisch gevonden videostreams.
- Geplande wedstrijden overnemen naar analyse: teamnamen en aftrap, maar nooit fictieve xG/odds invullen.

- Een overzichtelijke responsieve (ook mobiel bruikbare) webinterface, volledig in het Nederlands.
- Wedstrijden invoeren: teamnamen, optionele aftraptijd, verwachte doelpunten (xG), bron en 1X2-quoteringen.
- Berekeningen: onafhankelijke Poisson-baseline, 1/X/2-kansen, fair odds, bookmakersmarge, theoretische expected value.
- Een **enkelvoudige of combinatie-betslip** van maximaal 8 verschillende wedstrijden.
- Server-side berekende gecombineerde odds, kans op alle goede selecties, potentiële bruto-uitbetaling en fictieve nettowinst.
- Meerdere selecties uit dezelfde wedstrijd worden geweigerd: kansen kunnen sterk van elkaar afhangen.
- Gesimuleerde inzetten in **SQLite** met oorspronkelijke quoteringen vastgelegd op het tijdstip van opslaan.
- Handmatig uitslagen invoeren en automatisch combinatietickets afrekenen. Reeds afgerekende resultaten zijn onwijzigbaar.
- Dashboard met openstaande inzet, gerealiseerd fictief resultaat en gerealiseerde ROI (afzonderlijk van theoretische EV).
- **Modelkwaliteit** op afgehandelde wedstrijden: multiclass Brier-score en log-loss ten opzichte van odds zonder bookmaker-marge. Dit is nog geen out-of-sample-backtest.
- CSV/JSON-import via een gedocumenteerd tussenschema; fictieve voorbeeldwedstrijden met één klik.
- API-inputvalidatie, SQLite-transacties, alleen localhost, strikte HTTP-headers en regressietests.

## Starten op Windows

Vereist **Python 3.11+**. Alleen de standaardbibliotheek is nodig voor het dashboard.

1. Open de [hoofdbranch](https://github.com/henkdepotvis0180/supahbetting) of haal hem binnen via Git.
2. Kies **Code → Download ZIP** en pak de ZIP volledig uit, of gebruik:

   ```powershell
   git clone https://github.com/henkdepotvis0180/supahbetting.git
   cd supahbetting
   ```

3. Dubbelklik op **start_dashboard.bat**.
4. Open **http://127.0.0.1:8765/** op dezelfde computer.

Alternatief:

```powershell
python -m supahbetting
```

De lokale database wordt aangemaakt in `.supahbetting/data.sqlite3`. Maak hiervan zelf regelmatig een back-up (bij voorkeur wanneer de server niet draait). Deze database wordt niet naar GitHub geüpload.

## Eerste gebruik

1. Kies **Voorbeeldwedstrijden laden** voor vier volledig verzonnen testwedstrijden.
2. Klik bij twee verschillende wedstrijden op een quotering **1, X of 2**.
3. Bekijk rechts de combinatiekans, totale odds en mogelijke fictieve uitbetaling.
4. Kies een fictieve inzet en klik op **Fictieve betslip bewaren**.
5. Vul onder **Wedstrijduitslagen invoeren** een uitslag in; de status en winst/verlies worden automatisch bijgewerkt.

Klik op een andere markt binnen dezelfde wedstrijd om die selectie te vervangen. Niet mogelijk: twee markten van dezelfde wedstrijd op één combinatie.

## Live wedstrijdcentrum (v0.4.0)

Klik op een wedstrijdkaart om een klein scorebord, de huidige bronstatus en een **doelpuntenfeed** met minuten, doelpuntenmakers en eventuele penalty-/eigen-doelpuntmarkeringen te openen. De feed geeft geen doorlopende videocommentaar en geen actuele bookmakerprijzen.

Bron: [OpenLigaDB](https://www.openligadb.de/), openbare community-data onder [Open Database License (ODbL) 1.0](https://www.openligadb.de/lizenz). Lezen vereist geen account of API-key.

Gecontroleerde competities:
- Bundesliga (bl1), 2. Bundesliga (bl2), 3. Liga (bl3)
- Champions League (ucl)
- DFB-Pokal (dfb)
- Frauen-Bundesliga (ffb1)
- La Liga (la1; communitybron, mogelijk onvolledig)

De shortcuts zijn bevestigd aan de hand van de [competitie-index 2026](https://beta.openligadb.de/Leagues?season=2026). De Nederlandse Eredivisie is via deze bron nog niet bevestigd. Dit is geen compleet overzicht van alle competities ter wereld.

**Verversing:** de browser haalt wedstrijdlijsten op met een interval van 90 seconden en een geopend wedstrijddetail om de 45 seconden. De Python-server heeft een eigen TTL-cache, een beperkte wachttijd en 120 seconden terughoudende retry na een fout. Als de bron niet bereikbaar is, kan een eerder opgehaald resultaat blijven staan, duidelijk gemarkeerd als verouderd. "Mogelijk bezig" is een **inschatting** op basis van de aftraptijd en géén officieel bevestigde wedstrijdstatus. OpenLigaDB wordt door vrijwilligers bijgehouden, waardoor standen en goals vertraagd of onjuist kunnen zijn.

### Eventuele officiële openbare livestream bekijken

OpenLigaDB levert geen videocontent. SupahBetting gaat niet naar ongeautoriseerde voetbalstreams zoeken.

Wanneer een **officiële rechthebbende** een openbare YouTube-video beschikbaar stelt die in een andere website mag worden ingesloten, kun je die per wedstrijd handmatig toevoegen:

1. Zoek het numerieke OpenLigaDB-wedstrijdnummer op.
2. Maak een lokaal bestand: .supahbetting/official_broadcasts.json (de map bestaat na de eerste start).
3. Gebruik het onderstaande JSON-formaat (het voorbeeld-ID is een placeholder):

    {
      "bl1:123456": "https://www.youtube-nocookie.com/embed/AAAAAAAAAAA"
    }

4. Vervang het wedstrijdnummer en de YouTube-video-ID door gecontroleerde echte waarden.
5. Open de betreffende wedstrijd en klik zelf op "Officiële video tonen".

De server accepteert uitsluitend de vaste HTTPS-YouTube-nocookie-embedvorm. De instelling is optioneel en wordt niet naar GitHub gepusht. **SupahBetting kan de uitzendrechten of beschikbaarheid niet automatisch beoordelen.** Een openbaar linkje betekent niet automatisch dat insluiten is toegestaan; YouTube kan embeds bovendien uitschakelen. Zorg dat je toestemming hebt.

### Veiligheid en datakwaliteit

- Vastgelegde bronhost (api.openligadb.de), HTTPS, geen redirects, maximumantwoordgrootte, time-out, cache en zichtbare fouten.
- De live-feed en je **fictieve weddenschappen zijn gescheiden**. Live scores worden nooit gepresenteerd als bookmakerquoteringen of winstgevende voorspellingen.
- Een wedstrijd uit de feed kan als uitgangspunt voor een **nieuwe analyse** worden gekozen; het formulier vereist daarna eigen xG/odds.
- De ODbL-datalicentie kan extra eisen stellen bij herpublicatie of het opbouwen en verspreiden van afgeleide databases; raadpleeg de licentietekst.
- Alleen lokaal beschikbaar op 127.0.0.1, geen accountbeveiliging of publieke hosting.

## Eigen data importeren (CSV of JSON)

De ingang naar ProphitBet, OddsHarvester en een eigen analyser is een **genormaliseerd gegevensformaat**. Exporteer de voorspellingen en odds, voeg die buiten het programma samen, en importeer ze. De oorspronkelijke tools worden **nog niet automatisch aangestuurd**.

Vereiste kolommen:

```text
home_team,away_team,kickoff,home_xg,away_xg,odds_home,odds_draw,odds_away,source
```

- `kickoff`: leeg, of een ISO 8601-tijdstip **met tijdzone**, bijvoorbeeld `2026-10-18T18:00:00+02:00`.
- `home_xg`, `away_xg`: verwachte doelpunten van een transparant model of handmatige invoer; 0–8.
- `odds_home`, `odds_draw`, `odds_away`: decimale quoteringen, groter dan 1.
- `source`: naam en herkomst van de gegevens.
- JSON mag een lijst van objecten met dezelfde sleutelvelden bevatten.

Importeer met:

```powershell
python -m supahbetting.importers examples/normalized_matches.csv
```

De CSV is **uitsluitend fictief**, geen actuele bookmakersdata. Onjuiste rijen worden gerapporteerd en geweigerd. Herhaald importeren maakt nieuwe wedstrijden; gebruik een gecontroleerde export.

## Over de drie forks

| Fork in het GitHub-account | Rol | Juridische en technische status |
|---|---|---|
| [ProphitBet-Soccer-Bets-Predictor](https://github.com/henkdepotvis0180/ProphitBet-Soccer-Bets-Predictor) | Voorspellingsmodellen en xG-bronnen | MIT (`LICENSE.txt`); zware TensorFlow/PyQt6-dependencies |
| [OddsHarvester](https://github.com/henkdepotvis0180/OddsHarvester) | Odds uit toegestane exports | MIT (`LICENSE.txt`); Python 3.12+, Playwright |
| [prediict](https://github.com/henkdepotvis0180/prediict) | Analyse-inspiratie en onafhankelijke model-export | Geen licentie bevestigd; broncode niet overnemen zonder toestemming |

**Waarom niet alles met één `pip install` samenvoegen?** Verschillende omgevingen kunnen versieconflicten veroorzaken. De centrale applicatie is daarom bewust afhankelijkheidsarm, met een apart gestandaardiseerd importkanaal. De drie upstream-programma's zijn nog niet rechtstreeks geïntegreerd.

Controleer bij dataverzameling altijd de voorwaarden, robots-regels, rate limits en toepasselijke wetgeving van de betrokken aanbieder.

## Tests

```powershell
python -m unittest discover -s tests -v
python -m compileall -q supahbetting
```

GitHub Actions draait de tests onder Python 3.11 en 3.12 en controleert JavaScript-syntax.

## Huidige beperkingen

- Alleen **1X2**-selecties, maximaal één markt per wedstrijd per ticket.
- Geen live **odds-feed** van Toto, Unibet of andere bookmakers. Er is nu wel een afzonderlijke openbare score- en doelpuntenfeed.
- Geen direct gekoppeld ProphitBet-/OddsHarvester-/Prediict-proces.
- De kans op een combinatie wordt vermenigvuldigd onder de **aanname van onafhankelijke wedstrijden**. Dit is ook bij verschillende wedstrijden niet altijd juist.
- Geen kalibratie of chronologische out-of-sample-backtest; de EV-waarden zijn onderzoeksindicaties.
- Alleen lokaal toegankelijk via **127.0.0.1**; geen gebruikersaccounts, HTTPS, LAN of internetpublicatie.
- Handmatige uitslagen worden vertrouwd en zijn daarna niet te wijzigen; ze zijn geen geverifieerde livescores.
- Bestaande `paper_bets.jsonl`-bestanden van v0.1/v0.2 worden niet automatisch gemigreerd.

## Volgende stappen

1. Bronspecifieke adapters voor gecontroleerde model- en odds-exports.
2. Chronologische backtesting, modelkalibratie, odds-timestamps en bronkwaliteit.
3. Optioneel extra markten (BTTS, over/under), met correcte afhankelijkheidsbehandeling.
4. Bookmakerdata via expliciet geautoriseerde API's waar beschikbaar.

Bekijk `CHANGELOG.md` en `AGENTS.md`.
