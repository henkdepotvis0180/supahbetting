# SupahBetting v0.8.1

**Lokaal Nederlandstalig voetbalanalyseplatform met een betrouwbare basis voor enkelvoudige én combinatie-betslips.**

SupahBetting is software voor onderzoek en **fictieve weddenschappen**. Vanaf v0.8 bevat het **twee daadwerkelijk getrainde, afzonderlijke voetbalmodellen**: een Elo-/vormmodel en een zeven-competities doelpunten-/Poisson-model. Nieuw in v0.5: **meerdere voetbalgegevensbronnen**, waaronder Nederlandse en Belgische competities; de bestaande OpenLigaDB-community-doelpuntenfeed blijft aanwezig. Er zijn **geen live bookmakerquoteringen**, geen directe bookmakeraccounts en geen functie voor echt geld. Het aparte getrainde basismodel heeft een chronologische historische toets gehad, maar is niet tegen actuele bookmakers geijkt. Het eerste Elo-/vormmodel gebruikt data tot 2024; het tweede model heeft nieuwe bronuitslagen uit 2025/26, maar per competitie zijn sommige bestanden onvolledig. Een positieve model-EV is **geen bewijs van winstgevendheid**.

## Extra training met seizoen 2026/27 (v0.8.1)

Het meegeleverde **Poisson/doelpuntenmodel** is verder getraind met **295 extra echte eindstanden** uit seizoen 2026/27. Het heeft nu **13.467 historische wedstrijden** verdeeld over zeven competities. De nieuwe wedstrijddata komen uit de openbare **CC0**-bron [OpenFootball](https://github.com/openfootball/football.json).

**Hoe betrouwbaar/actueel is dit?** De bronbestanden voor 2026/27 lopen op het moment van ophalen (17 oktober 2026) slechts tot **20 september 2026**. België heeft voor 2026/27 geen corresponderend bronbestand. Het model werkt dus **niet op uitslagen tot vandaag** en is ook niet gekoppeld aan blessures, opstellingen of bookmakerodds.

De trainingshyperparameters zijn uitsluitend gekozen op de historische validatieset **2024/25**. De wedstrijden uit 2025/26 (**2.037**) en vervolgens 2026/27 (**295**) zijn strikt chronologisch **vóór het verwerken van hun uitslag** voorspeld. De huidige 2026/27-score over 295 wedstrijden is Brier **0,57990** tegenover **0,64430** voor een simpele historische frequentie-referentie, en log loss **0,97842** tegenover **1,06398**. Dit zijn foutmaten; lager is beter. De steekproef is klein en onvolledig, **niet** onafhankelijk vergeleken met marktquoteringen en **geen** bewijs voor positieve betting-ROI.

Je hoeft je Windows-pc niet te gebruiken om het getrainde bestand aan te maken: de modeltraining is uitgevoerd in **GitHub Actions**, en de getrainde parameters staan in `supahbetting/models/baseline.json` (modelversie 0.9.0). Het bestaande Elo-/vormmodel `models/baseline_v1.json` is bewust ongewijzigd gebleven.

Voor een volgende update kun je via `train_model.bat` opnieuw trainen **nadat je nieuwe, geverifieerde eindstanden aan `data/historical/` hebt toegevoegd**. Zonder nieuwe informatie telkens opnieuw hetzelfde model trainen levert geen nieuwe kennis op. De trainingsworkflow is reproduceerbaar via `.github/workflows/rolling-season-training.yml`, en de originele dataset-versies staan in `data/historical/provenance_2026_27.json`.

## Wat is werkend?

- **Nieuw v0.8.1:** bijgewerkt Poisson-model met 295 extra echte wedstrijden uit 2026/27 en een onafhankelijke chronologische toekomstige-seizoenstoets (bron tot 20 september 2026).
- **v0.8:** twee naast elkaar werkende, voorgetrainde modellen. De bestaande Elo-/vormvoorspellingen blijven, plus een nieuw doelpunten-/Poisson-model met Eredivisie en Belgische competitie uit CC0-bronuitslagen t/m de geregistreerde 2025/26-wedstrijden.
- Tweede model direct in dashboard te raadplegen, met handmatige voorspelling en optionele invulling van doelpuntverwachting (NOOIT automatische bookmakerprijzen).

- **Nieuw v0.5:** kies een databron en competitie in één dashboard. TheSportsDB gratis toont beperkt de Eredivisie/Eerste Divisie, België en internationale competities; football-data.org voegt vertraagde scores toe met een optionele persoonlijke API-sleutel.
- **Nieuw v0.6:** native fork-exportadapters, onderzoeksranglijst voor modelkansen en bookmakerprijzen, deduplicatie en bron-/versheidscontrole.
- **v0.5.1:** lokaal centraal configuratiebestand voor API-sleutels.
- Backend-cache per vaste API-route, duidelijke foutafhandeling, bron- en vertragingslabels, geen live bookmakerodds.

- **Live**: acht OpenLigaDB-competities, klikbare wedstrijdkaarten, scorebord en doelpunten met minuten.
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

## Nederlandse, Belgische en internationale competities (v0.5)

Gebruik boven in het **Live wedstrijdcentrum** de twee dropdowns voor databron en competitie.

| Databron | Competerende dekking | Gratis gegevens | Sleutel |
|---|---|---|---|
| OpenLigaDB | Bundesliga 1/2/3, UCL, DFB-Pokal, vrouwen-Bundesliga, La Liga, Premier League (community) | Community-scores en doelpuntentijdlijn, mogelijk vertraagd | Niet nodig |
| TheSportsDB v1 | Eredivisie, Eerste Divisie, Belgische Pro League, Premier League, Championship, Scottish Premiership, Bundesliga, Serie A, Ligue 1, La Liga, MLS, Brazilië, Oostenrijk | **Beperkte selectie**: maximaal één volgende, één vorige en tot drie wedstrijden per dag (gisteren, vandaag en morgen). **Geen echte livescores of doelpuntenfeed** in gratis v1 | Ingebouwde openbare gedeelde sleutel 123 |
| football-data.org v4 | Eredivisie, Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Portugal, Champions League, Championship, Brazilië, WK, EK (afhankelijk van abonnement) | Gratis basisgegevens en **vertraagde** standen. Eventtijdlijnen kunnen ontbreken | Persoonlijke API-sleutel |

Beschikbare wedstrijden en abonnementsrechten worden bepaald door de aanbieders. De app verzint geen ontbrekende scores, doelpunten of livestreams. Bronstatus en vertragingsmeldingen staan zichtbaar in de interface.

### Gratis football-data.org instellen via een lokaal configuratiebestand (nieuw v0.5.1)

**Je hoeft geen Windows-omgevingsvariabele meer aan te maken.** Voor alle huidige en toekomstige API-koppelingen gebruikt SupahBetting één uitbreidbaar lokaal JSON-bestand.

1. Pak de nieuwste ZIP uit op je Windows-pc (of update je clone).
2. Dubbelklik op **bewerk_api_config.bat**. Dit maakt het bestand automatisch aan (als het nog niet bestaat) en opent het in Kladblok.
3. Zoek in het geopende bestand de sleutel `api_key` onder `providers` → `football-data`. Plak **uitsluitend op je eigen computer** je gratis football-data.org-token tussen de dubbele aanhalingstekens.
4. Sla op (Ctrl+S) en sluit Kladblok.
5. Start SupahBetting opnieuw met **start_dashboard.bat** en kies **football-data.org → Eredivisie**.

**Locatie:** `.supahbetting/providers.json` in je uitgepakte SupahBetting-map. Het dashboard maakt dit bestand ook zelf aan bij de eerste start. Als het bestand al bestaat, wordt het **nooit automatisch overschreven**.

De basisinhoud ziet er zo uit (met een lege, niet-werkende waarde):

```json
{
  "providers": {
    "football-data": {
      "api_key": ""
    }
  }
}
```

Je kunt later meerdere providers toevoegen, ieder met een eigen onderdeel:

```json
{
  "providers": {
    "football-data": { "api_key": "" },
    "nieuwe-provider": { "api_key": "" }
  }
}
```

**Belangrijk:** dat een provider in dit bestand staat betekent nog niet dat zijn API automatisch wordt ondersteund; daarvoor is een bijbehorende adapter in de backend nodig. Dit bestandsformaat is daar alvast op voorbereid. Het meegeleverde `config/providers.example.json` bevat bewust geen echte sleutels.

**Veiligheid:** `.supahbetting/` staat in `.gitignore`. Je token wordt lokaal als **gewone tekst** in JSON opgeslagen, niet versleuteld. Bescherm dus je Windows-account, deel het bestand niet en upload het niet naar GitHub, chats of een ZIP die je deelt. Bij het opstarten leest uitsluitend de backend de sleutel; deze wordt niet meegestuurd naar de browser. Op Windows zijn de map-/bestandsrechten gebaseerd op de rechten van jouw gebruikersaccount. Fouten in JSON leiden tot een melding zonder de sleutel te tonen; de andere providers blijven beschikbaar.

Heb je de oude Windows-variabele **FOOTBALL_DATA_API_KEY** al ingesteld? Die blijft als terugvaloptie werken wanneer het JSON-veld leeg is. Een ingevulde sleutel in het JSON-bestand krijgt voorrang.

De gratis [football-data.org](https://www.football-data.org/pricing)-bron levert **vertraagde scores**, geen echte gratis livescores. De bestaande servercache (10 minuten) blijft bestaan. Er worden geen bookmakerquoteringen of echte weddenschappen toegevoegd.

### API-config uitbreiden voor nieuwe aanbieders

De generieke module `supahbetting/provider_config.py` kan sleutels per provider ophalen zonder een nieuw bestandssysteem te introduceren. Nieuwe data-adapters kunnen dezelfde methode gebruiken, met de configuratieprovidernaam als sleutel. Een provider-specifieke toegestane HTTPS-host, routes, voorwaarden en rate limits moeten nog wel apart in de betreffende adapter worden ontwikkeld en getest.

### Klikbare wedstrijdpopup en eventueel officiële video

Alle bronnen gebruiken dezelfde popup met teamnamen, score, status, bronupdate en beschikbare doelpunten.

- **OpenLigaDB:** doelpuntenfeed wanneer de bron doelpunten registreert.
- **TheSportsDB gratis:** beperkt speelschema en recente uitslagen, geen volledige feed.
- **football-data.org gratis:** vertraagde resultaten. Gedetailleerde doelpuntengebeurtenissen zijn afhankelijk van een uitgebreider abonnement.

Volgens de [voorwaarden van TheSportsDB](https://www.thesportsdb.com/docs_terms_of_use.php) is de gratis API voor ontwikkelprojecten bedoeld en vereist het publiceren van een mobiele app in een appstore een betaald abonnement. De andere providers hebben eigen voorwaarden, waaronder verplichte bronvermelding.

De videospeler is optioneel: alleen een handmatig geverifieerde, officiële YouTube-nocookie-embed mag worden toegevoegd in het lokaal genegeerde bestand **.supahbetting/official_broadcasts.json**. De sleutels worden per provider verschillend opgebouwd:

- OpenLigaDB: bl1:123456
- TheSportsDB: tsdb-4337:123456
- football-data.org: fd-DED:123456

Gebruik de werkelijke wedstrijd-ID en een officiële video waarvoor insluiten is toegestaan. Het programma doorzoekt geen ongeautoriseerde streamsites.

## Live wedstrijdcentrum (v0.4.0)

Klik op een wedstrijdkaart om een klein scorebord, de huidige bronstatus en een **doelpuntenfeed** met minuten, doelpuntenmakers en eventuele penalty-/eigen-doelpuntmarkeringen te openen. De feed geeft geen doorlopende videocommentaar en geen actuele bookmakerprijzen.

Bron: [OpenLigaDB](https://www.openligadb.de/), openbare community-data onder [Open Database License (ODbL) 1.0](https://www.openligadb.de/lizenz). Lezen vereist geen account of API-key.

Gecontroleerde competities:
- Bundesliga (bl1), 2. Bundesliga (bl2), 3. Liga (bl3)
- Champions League (ucl)
- DFB-Pokal (dfb)
- Frauen-Bundesliga (ffb1)
- La Liga (la1; communitybron, mogelijk onvolledig)
- Premier League (pl; communitybron, mogelijk onvolledig)

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

## Nieuw v0.7: een echt getraind basismodel

SupahBetting bevat nu **models/baseline_v1.json**: een vooraf getraind 1X2-model met Elo en recente vorm. Het model is met 18.085 historische wedstrijden uit de Prediict-fork getraind en chronologisch beoordeeld op 3.143 latere wedstrijden. De testnauwkeurigheid bedroeg **53,33%**, versus **44,61%** bij een eenvoudige historische uitkomstfrequentie als referentie.

**Belangrijk:** de beschikbare bronhistorie eindigt op **2 juni 2024**. Dit model kent dus niet de actuele vorm, trainers, promoties of transfers in seizoen 2026/27 en is niet bewezen beter dan bookmakers of winstgevend.

Voor gebruik heb je geen extra ML-installatie nodig: start het dashboard, open een geplande wedstrijd en klik op **Bereken modelkansen**. De drie voorspellingen zijn uitsluitend voor onderzoek; ze beïnvloeden de bestaande paperbets niet.

Om later zelf een bijgewerkt basismodel te trainen, plaats je een **volledige, aangevulde historische CSV** in **.supahbetting/training_history.csv** en start je **train_baseline.bat**. Dit gebruikt een aparte Python-omgeving met scikit-learn, valideert chronologisch en vervangt het JSON-model alleen na geslaagde training. Herstart daarna het dashboard.

**Lees alle details:** [Trainingsmethode, resultaten, beperkingen en bijtrainen](docs/PRETRAINED_MODEL.md).

## Tweede voorgetrainde basismodel (v0.8): zeven competities

**Je hoeft niets zelf te trainen om SupahBetting te gebruiken.** In de volledige
ZIP staan nu **twee afzonderlijke getrainde JSON-modellen**:

| Model | Getrainde wedstrijden | Laatste historische brondata | Methode |
|---|---:|---|---|
| Elo-/vormmodel uit v0.7 | 18.085 | Juni 2024 | Elo, vorm, multinomiale logistische regressie |
| Nieuw doelpunten-/Poisson-model uit v0.8 | **13.172** | Geregistreerde eindstanden t/m 2025/26 (sommige competities incompleet) | Doelpuntenaanval/verdediging, thuisvoordeel, Poisson |

Het nieuwe model is een **onafhankelijk tweede onderzoeksmodel**, geen kopie
van de oorspronkelijke Prediict-/ProphitBet-netwerken en geen vervanging van
het oudere Elo-model. De oude koppelingen met live scores, native exports,
API-tokens, combinatiebets en SQLite blijven aanwezig.

### Test van het nieuwe doelpuntenmodel

De brondata zijn echte, volledig gespeelde voetbalwedstrijden uit
[OpenFootball](https://github.com/openfootball/football.json) onder
**CC0 1.0 Universal**. De zeven CSV-bestanden en herkomst staan in
\`data/historical/\`. Er zijn meer dan 13.000 echte uitslagen over zes seizoenen.
Het ontbrekende deel van bepaalde seizoenen is **niet aangevuld met verzonnen
uitslagen**.

De hyperparameters (aanval/verdedigingsfilter en krimp naar gemiddelde)
zijn gekozen op **2024/25**; de uitkomsten uit **2025/26** zijn
chronologisch op 2.037 geregistreerde wedstrijden getest. Pas na iedere
wedstrijddag worden eindstanden geleerd, zodat andere matches op die dag
geen verborgen voorkennis krijgen.

- **Brier-score 2025/26:** **0,58474** tegenover **0,63649** voor
  een eenvoudige frequentie-referentie.
- **Log loss 2025/26:** **0,98432** tegenover **1,05357** voor
  diezelfde referentie.
- In de Belgische bron ontbreken meerdere seizoenen en zijn slechts
  104 wedstrijden in 2025/26 geregistreerd; andere competities missen
  ook enkele uitslagen. Zie de waarschuwingen in
  \`supahbetting/models/baseline.json\`.

**Dit is geen bookmakersbenchmark.** Het model is niet onafhankelijk getest
op betwinst en gebruikt geen actuele opstellingen, blessures, odds of
schotgebaseerde xG. De modelwaarden zijn *verwachte doelpunten op basis van
historische scores*, niet officiële xG.

### Meteen voorspellingen bekijken

1. Start zoals gewoonlijk **start_dashboard.bat**. De twee getrainde
   modelbestanden worden **automatisch geladen**.
2. Het bestaande **Historische voorspellingen**-onderdeel houdt het
   Elo-/vormmodel beschikbaar.
3. Onder **Voorspellingen van ons basismodel** vind je het nieuwe
   **doelpunten-/Poisson-model**. Kies een van de zeven competities
   (Eredivisie, Belgische Pro League, Premier League, Bundesliga,
   La Liga, Serie A of Ligue 1).
4. Voer twee bekende teams in, bijvoorbeeld **Ajax** en **PSV** in
   de Eredivisie, en klik op **Bereken modelkansen**.
5. De drie 1X2-kansen worden getoond, samen met verwachte goals,
   betrouwbaarheid en de laatste historische uitslag.
6. Klik optioneel op **Gebruik modeldoelpunten in handmatige analyse**;
   er worden **geen bookmakerodds ingevuld**. Je kunt bij een geplande
   wedstrijd ook op **Gebruik wedstrijd + verwachte goals** klikken.

Onbekende teams worden niet automatisch aan een mogelijk verkeerde club
gekoppeld. Dan moet je handmatig analyseren of de brondata uitbreiden.

### Later modellen hertrainen of uitbreiden

Het **nieuwe Poisson-model** kan zonder installatie van extra Python-pakketten
op basis van de CSV's worden hertraind:

\`\`\`powershell
python -m supahbetting.trained_model
\`\`\`

Of dubbelklik **train_model.bat** en herstart na afloop het dashboard.
Dit schrijft \`supahbetting/models/baseline.json\` opnieuw. Het verandert
het oorspronkelijke \`models/baseline_v1.json\` **niet**.

Voor het oudere Elo-/vormmodel blijft de bestaande
**train_baseline.bat**-procedure beschikbaar. Die gebruikt zijn eigen
dataset en scikit-learn in een gescheiden omgeving.

In GitHub zijn beide trainingsworkflows apart ingericht. Nieuwe, rechtmatig
verkregen uitslagen kunnen later worden toegevoegd aan de
\`data/historical\`-CSV's in exact hetzelfde formaat, ook voor nieuwe seizoenen.
De testperiode van 2025/26 moet bij toekomstige modelwijzigingen als
historische test worden behandeld; claim niet dat de vernieuwde finale fit
op dezelfde periode opnieuw onafhankelijk getest is.

## Native integratie van de drie GitHub-forks (v0.6.0)

Deze release bevat **drie daadwerkelijke exportadapters** voor de oorspronkelijke bestandsformaten, een aparte SQLite-onderzoeksdatabase en een vergelijking van aangeleverde modelkansen met bookmakerquoteringen. Alle onderdelen van het bestaande dashboard blijven werken, inclusief live wedstrijdstanden en fictieve combinatiebets.

**Belangrijk onderscheid:** de adapters importeren de *echte native CSV/JSON-uitvoer* van de forks. Ze starten de zware, externe ProphitBet-/Prediict-ML-omgeving of de OddsHarvester-scraper **niet automatisch** op. Hiervoor zouden aparte Python-omgevingen, externe toegang en verdere juridische controles nodig zijn. Er zijn geen AI-modellen of externe broncodes naar SupahBetting gekopieerd.

### In de praktijk: zo koppel je een fork

1. Download of update SupahBetting en dubbelklik op **start_dashboard.bat**. Bij de eerste start maakt het programma de bronmappen automatisch aan.
2. De drie mappen staan onder `.supahbetting/imports/`:
   - `prophitbet/`
   - `oddsharvester/`
   - `prediict/`
3. Exporteer de voorspellingen/odds met één van de originele tools en plaats het CSV- of JSON-bestand in de juiste map.
4. Klik in het nieuwe dashboardgedeelte **Modelkansen en bookmakerprijzen vergelijken** op **Bronbestanden inlezen**. Bij herstart leest de backend ook automatisch nieuwe bestanden in.
5. Je ziet het aantal ingelezen voorspellingen/quoteringen, de berekende model-EV en het tijdstip (of de onbekende leeftijd) van de prijs.

**Voor Windows:** `bronbestanden_inlezen.bat` scant dezelfde mappen ook buiten het dashboard. Je hoeft de drie Python-projecten niet in één omgeving te installeren.

### Gecontroleerde upstream-bestandsindelingen

| Fork | Export die de adapter echt ondersteunt | Beperkingen |
|---|---|---|
| [ProphitBet](https://github.com/henkdepotvis0180/ProphitBet-Soccer-Bets-Predictor) | **Fixture Predictions → Export** (CSV) met `Home Team`, `Away Team`, `Prob(1)`, `Prob(X)`, `Prob(2)`, eventueel `1`, `X`, `2`. Ook CSV vanuit Manual Prediction met `Date`, `Home`, `Away`. | Geen `Prob(U)`/`Prob(O)`-markten in de huidige 1X2-researchscanner. Fixture-export bevat doorgaans géén datum; zulke rijen worden alleen met de odds in diezelfde bestandsrij vergeleken. |
| [OddsHarvester](https://github.com/henkdepotvis0180/OddsHarvester) | Native CSV/JSON-exports van voetbal `1x2` met `match_date`, `scraped_date`, `home_team`, `away_team`, `1x2_market`, per bookmaker de velden `1`, `X`, `2`. | Geen Python-import of automatische scraping; geblokkeerde odds en andere markten worden overgeslagen. `scraped_date` moet een expliciete tijdzone hebben voor een leeftijdsclaim. |
| [Prediict](https://github.com/henkdepotvis0180/prediict) | `data/value_bets_*.csv` met `home_team`, `away_team`, `date`, `outcome`, `model_probability`, `bookmaker_odds`. Eventueel volledige 1X2-probability-CSV met `home_win_prob`, `draw_prob`, `away_win_prob`. | Native voorbeeldbestanden bevatten **oude** weddenschappen en soms zeer extreme kansen. We lezen de gegevens, maar behandelen ze niet als bewezen voorspellingen of actuele odds. Licentie voor overname van de broncode is niet vastgesteld, dus die wordt niet gekopieerd. |

De parser accepteert CSV, JSON en NDJSON van maximaal 3 MB per bestand en maximaal 1000 wedstrijden. `.xlsx` importeren kan niet zonder extra afhankelijkheden; gebruik de CSV-export. Opnieuw inlezen van hetzelfde bestand veroorzaakt geen dubbele data dankzij een SHA-256-controle per bron. Bestanden mogen geen symlinks naar externe paden zijn.

**Voorbeeldbestanden:** `examples/native_prophitbet_fixtures.csv`, `examples/native_oddsharvester.json` en `examples/native_prediict_value_bets.csv`. Die bestanden zijn **volledig fictief en historisch**; zet ze zelf in een bronmap als je de import wilt testen.

### Onderzoeksranglijst: matchregels en beperkingen

Het systeem koppelt uitsluitend exacte, genormaliseerde teamnamen, hetzelfde **kalenderdatumveld** en dezelfde uitkomst (1/X/2). Verschillende wedstrijddatums of alleen gedeeltelijk overeenkomende teamnamen worden **niet** automatisch samengevoegd. Een export zonder datum wordt uitsluitend binnen dezelfde bronbestandsrij gekoppeld om verkeerde wedstrijden te voorkomen. Dat betekent dat sommige geldige combinaties vooralsnog **niet** gevonden zullen worden; foutief koppelen is erger dan iets overslaan.

De berekende EV is `modelkans × decimale odds - 1` en wordt getoond **als onderzoekswaarde**, niet als winstadvies. Naast iedere kans staan modelbron, bookmaker, bestandsnaam en prijsstatus. Gegevens van afgelopen wedstrijden zijn **historisch**. Een prijs zonder betrouwbare `scraped_date` krijgt **opnametijd onbekend**, ongeacht hoe recent je het bestand gekopieerd hebt. De filter **Alleen prijzen met gecontroleerde recente opnametijd** helpt oude odds uit de lijst te houden.

**ProphitBet-waarschuwing:** zijn modellen kunnen bookmakerodds als trainings-/voorspellingsinput gebruiken. Als je die kansen vervolgens met dezelfde odds vergelijkt, is de berekende EV **niet onafhankelijk** en dus zeker geen bewijs van een voordeel. Prediict-modellen zijn evenmin onafhankelijk gevalideerd. Dit programma doet **geen echte weddenschappen**, beveelt geen inzetbedragen aan en garandeert geen rendement.

Een losse odds-export (OddsHarvester) bevat nog geen voorspelling. Een losse model-export (ProphitBet/Prediict) bevat mogelijk geen recente bookmakerodds. Alleen bij een veilige overeenkomst tonen we een vergelijkingsresultaat.

### Handmatig/technisch inlezen

Via de terminal vanuit de uitgepakte SupahBetting-map:

```powershell
python -m supahbetting.research_cli scan
python -m supahbetting.research_cli status
python -m supahbetting.research_cli opportunities
python -m supahbetting.research_cli import prophitbet "C:\pad\naar\fixture_export.csv"
python -m supahbetting.research_cli import oddsharvester "C:\pad\naar\odds.json"
python -m supahbetting.research_cli import prediict "C:\pad\naar\value_bets.csv"
```

Alle importgegevens komen in dezelfde lokale SQLite-database als je onderzoeksapp, maar in **aparte onderzoekstabellen**, zodat ze geen al opgeslagen odds, afgewikkelde slips of bestaande gesimuleerde inzetten overschrijven. De web-API accepteert geen willekeurige bestandspaden: de browserknop scant alleen zijn vooraf ingestelde lokale importmappen.

De oorspronkelijke forks blijven afzonderlijk onderhoudbaar en houden hun eigen versies en installatievereisten. Respecteer de voorwaarden van de oorspronkelijke databronnen en OddsPortal bij het maken van exports.

## Eigen data importeren (CSV of JSON)

Naast de nieuwe **native exportadapters** blijft de oudere gestandaardiseerde CSV/JSON-invoer beschikbaar voor eigen modellen en zelf samengestelde bestanden. De oorspronkelijke tools draaien nog steeds zelfstandig; SupahBetting leest hun uitvoer in.

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

**Waarom niet alles met één `pip install` samenvoegen?** Verschillende omgevingen kunnen versieconflicten veroorzaken. De centrale applicatie is daarom bewust afhankelijkheidsarm, met een apart gestandaardiseerd importkanaal. De drie upstream-programma's zijn sinds v0.6 **via hun native CSV/JSON-uitvoer geïntegreerd**. De uitvoering van hun ML-modellen en scraper draait nog afzonderlijk, buiten de SupahBetting-backend.

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
- De drie forks zijn via hun native CSV/JSON-export gekoppeld, **niet** als automatisch uitgevoerde trainings-/scrapeprocessen.
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
