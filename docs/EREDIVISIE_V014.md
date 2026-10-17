# Eredivisie Research v0.14 — betrouwbare eindstanden en lokale training

**Versie:** `feature/eredivisie-data-v0.14` (draft PR #14), nog **geen productie** of bewezen winstgevende voorspeller. Bestaande `main` en vorige onderzoeksbranches blijven ongewijzigd.

## Waarom opnieuw Nederlandse uitslagen ophalen?

De eerste CC0-training op 17 oktober 2026 bevatte 22.665 gespeelde wedstrijden uit 7 competities, maar de laatste algemeen ingelezen uitslag was **20 september 2026**. De Nederlandse dataset begon bovendien pas in **2018/19**, niet helemaal vanaf januari 2016. De officiële KNVB-kalender toont wie wanneer speelt, maar geen door ons geverifieerde complete dataset met alle nieuwe eindstanden. OpenFootball bevestigt zelf dat zijn onderliggende bronnen niet gegarandeerd dagelijks bijgewerkt worden.

Daarom heeft v0.14 **twee strikt gescheiden databronnen**:

### A. Automatische Eredivisie-update via football-data.org

De dienst heeft de officiële competitiecode **`DED`**, met onder meer `GET /v4/competitions/DED/matches?season=2026`. De app haalt de gehele lopende jaargang op (één extra verzoek in de zesuurs-monitor, plus de bestaande beperkte speelschema-aanvragen). Daardoor kan hij, als je abonnement toegang geeft, ook het gat van september naar oktober herstellen.

**Wat je doet:**

1. Maak een account aan bij <https://www.football-data.org/> en controleer of jouw toegang **Eredivisie / DED** bevat. Gratis 10 verzoeken/minuut is niet hetzelfde als gratis toegang tot iedere competitie; `403` betekent dat je abonnement de bron niet toestaat.
2. Gebruik **`configureer_speelschema_api.bat`**. Dit opent `.supahbetting/providers.json`.
3. Vul bij `providers` → `football-data` → `api_key` jouw **football-data.org-token** in en sla het bestand op. Het gaat **niet** om je GitHub-token of de API-sleutel van een bookmaker.
4. Start **`start_supahbetting.bat`**. De monitor leest de lokale 2016+-basis, probeert het lopende DED-seizoen te controleren, accepteert uitsluitend `FINISHED` plus een geldige eindstand minimaal 90 minuten na aftrap, en past daarna het lokale experimentele model aan als er echt nieuwe resultaten zijn.
5. Voor een gerichte controle zonder het volledige dashboard te hertrainen: **`controleer_eredivisie.bat`**. Bij succes verschijnt `status=loaded`, het aantal gecontroleerde resultaten, de echte nieuwste modeldatum en of hertraining nodig was.

Wanneer er geen token of geen toegang is, blijft de bestaande dataset intact en toont de software `no_api_key`, `subscription_required` of een HTTP-status. Niets wordt gefingeerd. Er wordt niet namens jou betaald of een account aangemaakt.

**Technisch:** het systeem herkent afwijkende teamnamen met expliciete aliassen, verwerpt vreemde competities en ongeldige standen, controleert bronconflicten, en bewaart de licentiegebonden API-resultaten uitsluitend lokaal in `data/research/provider_finals_local.json`. De herberekende staat heet `data/research/augmented_model_local.json`. Deze gegevens worden **niet** als publiek-domeinbron op GitHub gepubliceerd.

### B. Historische Nederlandse CSV’s vanaf januari 2016

Voor de ontbrekende jaren is een eenmalige lokale historische aanvulling mogelijk.

1. Bezoek <https://www.football-data.co.uk/netherlandsm.php>.
2. Download zelf, binnen de gepubliceerde voorwaarden, de `N1`-Eredivisie-CSV’s voor de relevante jaargangen **2015/16, 2016/17, 2017/18** en desgewenst andere ontbrekende seizoenen.
3. Dubbelklik **`importeer_eredivisie_csv.bat`**, zet de CSV-bestanden in de geopende lokale `data/research/nl_csv_inbox`-map en bevestig de import.
4. De import controleert competitiecode `N1`, datum, beide clubs, gehele eindstanden, `H/D/A`-uitslag, dubbele wedstrijden en onderlinge verschillen. Wedstrijden van **vandaag zonder onafhankelijk bewezen afloop** of uit de toekomst worden niet als trainingswaarheid overgenomen.
5. Bij voldoende controleerbare gegevens wordt het **lokale** model automatisch opnieuw berekend. De eerdere trainingen en voorspellingen blijven bestaan.

De bestanden blijven op je computer, inclusief de bestandsvingerafdruk (SHA-256) en bronclaims. Omdat een handmatig ingevoerd CSV-bestand niet automatisch aantoont waar het vandaan komt, staat dat expliciet bij de herkomst. Gebruik deze route uitsluitend met gegevens die je rechtmatig hebt verkregen.

**Gebruikslimiet:** de uitgever van Football-Data.co.uk staat bij gratis bestanden alleen persoonlijk/academisch en licht gebruik toe, met maximaal twee geautomatiseerde downloads per week. De website verbiedt zware geautomatiseerde scraping of commerciële data-trainingsprojecten. Daarom bevat SupahBetting hier **geen automatische CSV-downloader** en kopieert geen verkregen bestanden naar GitHub. Voor bedrijfsmatig/dataproductgebruik heb je een passende datalicentie nodig. Zie <https://www.football-data.co.uk/contact.php>.

## Starten zonder steeds ZIP-bestanden of modellen over te nemen

De code en de complete beschikbare openbare onderzoeksbaselines blijven op de aparte GitHub-branch. De lokale score- en API-bestanden blijven lokaal. De scripts:

| Bestand | Functie |
|---|---|
| `start_supahbetting.bat` | Snelle historische controle + monitor + overzicht bovenaan |
| `controleer_eredivisie.bat` | Alleen volledige Nederlandse seizoenresultaten ophalen/hertrainen, indien API-toegang |
| `ververs_speelschema.bat` | Geplande wedstrijden en 1X2-kaartjes lokaal actualiseren |
| `importeer_eredivisie_csv.bat` | Handmatig gedownloade historische Eredivisie-CSV’s importeren en lokaal hertrainen |
| `migreer_naar_git.bat` | Eenmalig naar Git-werkmap overstappen, oude researchdata bewaren |
| `update_supahbetting.bat` | Daarna deze **v0.14-experimentele** Git-branch veilig bijwerken |

Als je een nieuwe ZIP gebruikt, **sluit eerst beide CMD-vensters**, pak de ZIP in een **nieuwe map** uit en zet oude lokale `.supahbetting` en `data/research` over. Verwijder nooit `provider_forecast_log.json` of `shadow_predictions.json`: die bevatten de originele voorspellingen vóór aftrap, noodzakelijk voor eerlijke toekomsttests.

## Hoe bepalen we of dit zin heeft?

Een model kan met meer wedstrijden nauwkeuriger worden, maar kan ook verslechteren door veranderde competities, transfers of verouderde patronen. Daarom vergelijken we minstens:

- **Dekkingsgraad:** gespeelde Nederlandse wedstrijden vanaf 2016, ontbrekende speeldagen, datum laatste score en bronconflicten.
- **Chronologische toetsen:** log loss en Brier-score tegen de eerdere versie op exact dezelfde eerdere wedstrijden. Niet achteraf parameters kiezen op de gewenste testperiode.
- **Echte toekomsttests:** voorspellingen vóór aftrap onveranderlijk bewaren en later beoordelen. Het aantal eerdere succesvolle voorspellingen kan **niet** achteraf worden aangevuld.
- **Afzonderlijke marktvergelijking:** de hoogst voorspelde winstkans is geen bewijs van financieel voordeel; daarvoor zijn historische *vooraf bekende* bookmakerodds, bookmaker-marge en netto rendement nodig.

De gratis sport-API kan vertraagde uitslagen tonen en sommige abonnementen bevatten geen Nederlandse wedstrijden. Zonder geverifieerde data kan de app **niet** rechtmatig of betrouwbaar claimen dat de wedstrijden van 16–17 oktober allemaal zijn ingelezen. Deze status wordt zichtbaar getoond, in plaats van het model groen te kleuren terwijl er nog gaten zijn.

**Financiële waarschuwing:** als je geld voor rekeningen of levensonderhoud nodig hebt, gebruik dat niet om weddenschappen te plaatsen. SupahBetting is onderzoekssoftware, niet een manier om gegarandeerd inkomen te genereren.


## Hotfix 17 oktober 2026 — HTTP 429 / `Databronroute niet toegestaan` / thread-crash

De eerste Windows-praktijkrun met Python 3.14 meldde:

- `football-data HTTP 429` na meerdere aanvragen voor buitenlandse competities;
- `TheSportsDB HTTP 429` op de gedeelde gratis v1 API;
- `Databronroute niet toegestaan` bij de officiële full-season URL
  `/v4/competitions/DED/matches?season=2026`;
- daarna een traceback van `LiveDataUnavailable` in
  `research-first-schedule`.

**Dit was een echte fout in de v0.14-koppeling**, niet een probleem in je
CPU of de eerder getrainde basismodellen. De corrigende commitserie op
dezelfde `feature/eredivisie-data-v0.14`-branch omvat:

1. De vaste URL-allowlist accepteert nu de door football-data.org gedocumenteerde
   `?season=YYYY`-query, maar nog steeds geen willekeurige paden, hosts,
   redirects of API-sleutels in de URL.
2. Het Eredivisie-verzoek voor het **hele seizoen gaat vóór** eventuele
   aanvullende buitenlandse competitieaanvragen. Daardoor kan een
   latere buitenlandse HTTP 429 niet al het Nederlandse onderzoeksbudget
   opmaken voordat `DED` geprobeerd is. Een tweede dubbele
   `DED`-aanvraag voor alleen 18 kalenderdagen wordt overgeslagen.
3. Tussen opeenvolgende football-data.org-schema-aanvragen staat nu
   minstens **6,5 seconden**. In een oudere versie werkte het pauzeren niet,
   doordat een optie door een standaard-lambda niet meer `None` was.
4. Na een echte HTTP 429 blijft een provider tijdens dezelfde procesrun
   minstens vijf minuten in een netwerk-cooldown (of langer als
   `Retry-After` dit expliciet verlangt, maximaal een uur). Na HTTP
   401/403 wordt minstens dertig minuten gewacht. Het HTTP-nummer blijft
   behouden in de foutenafhandeling. Andere onafhankelijke bronnen blijven
   beschikbaar.
5. Zowel `research_nl_api.py`, `research_upcoming.py` als de monitor
   vangen providerstoringen en ongeldige API-verzoeken gecontroleerd af:
   **geen ongecontroleerde traceback** en geen wissen van eerdere resultaten.
6. Offline regressietests simuleren HTTP 429, blokkeren verdere
   daadwerkelijke netwerkverzoeken, testen de echte seizoenroute en
   controleren dat KNVB-wedstrijden en opgeslagen brongegevens behouden
   blijven. De Windows-Python-3.14-combinatie is toegevoegd aan GitHub Actions.

**Zo installeer je de hotfix:**

- Stop **eerst** de oude SupahBetting-monitor én dashboardserver met
  `Ctrl+C` in hun vensters. Sluit ook eventuele losse
  `controleer_eredivisie.bat`-vensters.
- Download de *nieuwste* v0.14-branch opnieuw en pak deze uit in een
  **nieuwe map**, of voer vanuit een echte Git-clone
  `update_supahbetting.bat` uit.
- Behoud je lokale `.supahbetting/` en `data/research/` en je
  originele vooraf opgeslagen prognoselogboeken; verwijder ze niet.
- Start `start_supahbetting.bat`. Voer niet tegelijkertijd
  `controleer_eredivisie.bat` uit terwijl de eerste controle nog loopt.
- Als er al HTTP 429 was: **laat de API minstens 5–10 minuten met rust**
  voordat je opnieuw controleert. Een dienst kan een eigen, langere
  limiet toepassen.
- De status van het Nederlandse onderzoeksmodel kan voorlopig nog
  `degraded` tonen zolang er **geen door de provider bevestigde
  eindstanden na 20 september 2026** zijn ingelezen. De codefix is
  niet hetzelfde als een succesvolle gegevensimport.

Let op: de officiële documentatie van football-data.org vermeldt
**10 requests/minuut voor gratis geregistreerde gebruikers**. Dit is
geen garantie dat je betaald/functiegebonden `DED`-toegang krijgt,
noch een reden om een API-limiet te proberen omzeilen. Zie
<https://docs.football-data.org/general/v4/policies.html>.
