# SupahBetting Research v0.13 — serieuze lokale voetbalanalyse

**Status: experimentele onderzoeksbranch `feature/research-v0.13-serious-dashboard`.**
Dit is géén goedgekeurd productiemodel en de historische log-loss zegt
niets over bewezen rendement bij bookmakers. De bestaande `main` en
`supahbetting/models/baseline.json` blijven ongemoeid.

## 1. Eén keer installeren, daarna geen modellen meer kopiëren

**Bestaande ZIP-gebruiker:** Download deze v0.13-ZIP en pak hem in een nieuwe
map uit. Start **`migreer_naar_git.bat`**, voer eenmalig het volledige pad van je
oude SupahBetting-map in (bijvoorbeeld het pad met je oude
`data\research\inventory.json`). Het script maakt via Git een nieuwe map
`SupahBetting-Research-v013` en neemt jouw oude `.supahbetting` en
`data\research` mee, inclusief originele tijdstippen van voorspellingen. Het
kopieert **niet** oude Git-tracked CC0-bronbestanden over de nieuwste heen.

Alternatief: direct deze ZIP gebruiken met **`start_supahbetting.bat`**. De
ingepakte 2016–2026 modelbasis is dan meteen aanwezig. Nieuwe lokale gegevens
uit jouw vorige installatie worden daarbij echter niet automatisch
overgenomen.

**Vanaf dat moment:**
- Start `start_supahbetting.bat` voor dashboard en monitor.
- Start `update_supahbetting.bat` om de **experimentele Git-branch** via
  `git pull --ff-only` op te halen en de applicatie te starten.
- Gebruik `ververs_speelschema.bat` voor een handmatige nieuwe broncontrole
  zonder tien jaar opnieuw binnen te halen.
- Gebruik `vergelijk_modellen.bat` om de aparte Dixon-Coles-kandidaat tegen
  het oorspronkelijke Poisson-model te toetsen; dit past niets in productie aan.

### Automatisch bij website-opstart

1. **Binnen enkele seconden** controleert de lokale startscriptmodelchecker
   welke historische basis en modelversie aanwezig zijn, wat de datum van de
   laatste eindstand is en of de dataset-vingerafdruk overeenkomt.
2. De dashboardserver start direct op `http://127.0.0.1:8765/`.
3. In een tweede monitorvenster begint **zonder blokkeren van het dashboard**
   de beperkte actuele speelschema-API-controle. De eerste complete refresh
   duurt langer dan de lokale modelcheck omdat netwerkverzoeken verantwoord
   moeten worden gespreid.
4. Op basis van geverifieerde nieuwe eindstanden (niet van vermoede livescores)
   werkt v0.13 het **lokale** experimentele model bij. Als exact dezelfde
   uitslagen al verwerkt zijn, worden die niet opnieuw geteld.
5. Na de eerste controle werkt de monitor door, standaard eens per zes uur
   zolang het venster en de computer aan zijn. De browser leest uit een lokale
   cache en start **geen nieuwe API-calls bij iedere paginaverversing**.

**Belangrijk:** een geslaagde HTTP-download betekent niet dat het model van
vandaag is. Het modelwaarschuwingspaneel meldt ontbrekende laatste dagen, een
incomplete competitie, mislukte API-connecties en onvoldoende historiek.

## 2. Website — echte wedstrijden eerst, geen demo

Het dashboard begint nu met **‘Wedstrijden & modelvoorkeuren’** en toont
Nederland, Engeland, Duitsland, Spanje, Italië en Frankrijk. België komt
later terug als de recente uitslagen en competitiedekking bevestigd zijn.
Je kunt kiezen voor vandaag, de komende drie of vijftien dagen, met filters
voor competitie en beschikbare voorspellingen. Onder de lijst is een apart
uitklapbaar overzicht van recent bevestigde eindstanden van gisteren/vandaag.

Er verschijnen **geen demo-wedstrijden** en de oude
`POST /api/demo`-route is uitgeschakeld. Oudere demo-rijen blijven op de
computer staan, maar worden verborgen zodat geen echte opgeslagen informatie
stilzwijgend wordt verwijderd. Paperbetfuncties en het uitgebreide
trainingslaboratorium zijn verplaatst naar uitklapbare onderdelen.

### Waarom heeft een team volgens het model meer kans?

Voor iedere wedstrijd uit een actieve geverifieerde bron met een gekend team
berekent de onderzoeksversie:

- kansen voor **thuiswinst, gelijkspel en uitwinst**;
- doelpuntverwachtingen en gespeelde wedstrijden in het scoremodel;
- recente ouderdom van het model per competitie;
- onderbouwde argumenten uit berekende aanval-, verdediging- en
  thuis-/uitindicatoren.

Met **‘Waarom kiest het model hiervoor?’** lees je welke signalen uit de
werkelijke trainingsdata komen en welke onzekerheden ontbreken. Alleen een
duidelijke kansvoorsprong, voldoende historiek en recente uitslagen mogen als
*modelvoorkeur* opvallen. Geen voornaam of medische status wordt verzonnen.

**Een kansinschatting is geen weddenschap-advies.** Zonder controleerbare
bookmakerprijzen, marge en onafhankelijk getoetste winstverwachting kunnen we
niet vaststellen of een favoriet daadwerkelijk *betting value* heeft.

## 3. Tien jaar training, actualiteit en bronrechten

De CC0 OpenFootball-basis is samengesteld uit bestanden van seizoenen 2015/16
(vanaf **1 januari 2016**) t/m 2026/27. Bij de vorige echte import waren
**22.665** eindstanden beschikbaar. De algemene bron was toen bij
**20 september 2026** gestopt; dit is geen volledige of gegarandeerd actuele
tienjarige dekking. De Belgische Pro League was nog ouder.

- De openbare scorebasis en herkomstcontrole blijven van
  `openfootball/football.json` (CC0); de bijbehorende research-GitHub
  synchronisatie blijft intact.
- Bepaalde actuele uitslagen van TheSportsDB, OpenLigaDB of football-data.org
  zijn onder andere voorwaarden beschikbaar. Die eindstanden worden **alleen
  lokaal** geverifieerd, ontdubbeld, op bronconflicten gecontroleerd en daarna
  eventueel gebruikt om het **lokale** `augmented_model_local.json`
  opnieuw te berekenen. De ruwe externe bronbestanden en daaruit afgeleide
  lokale modellen worden **niet als CC0 naar GitHub gepubliceerd**.
- De lokale provider-uitkomsten staan in
  `data/research/provider_finals_local.json`, het extra experimentele model
  in `data/research/augmented_model_local.json` en de
  vingerafdruk in `data/research/augmented_training_state.json`.
  Deze bestanden en je originele prognoselogboeken vallen onder `.gitignore`.
- Bij uiteenlopende eindstanden uit verschillende bronnen wordt de match in
  quarantaine gezet in plaats van ongemerkt een score te kiezen.
- Het apparaat hoeft geen model van een website te downloaden of te plakken;
  de baseline zit al in GitHub en het lokale model wordt opnieuw opgebouwd
  zodra nieuwe betrouwbare resultaten beschikbaar zijn.

### Voor de recentste kalenderwedstrijden

`football-data.org` is optioneel, met een eigen lokaal API-token via
`configureer_speelschema_api.bat`. De gratis dienst biedt twaalf
competities, maximaal tien verzoeken per minuut en vertraagde uitslagen;
de beschikbaarheid per competitie hangt van je abonnement af. Voor
TheSportsDB is de gratis speelschemadekking beperkt. Als er niets kan worden
geverifieerd, toont de app expliciet ‘geen bevestigde wedstrijden’ in
plaats van testdata te genereren.

## 4. Extern model en eerlijk vergelijken

Het open-source project [The Open Model](https://github.com/Hicruben/theopenmodel)
gebruikt Elo, Dixon-Coles en Monte Carlo. Dat is een interessante externe
onderzoekskandidaat (MIT-code, voorspellingen onder CC BY 4.0), maar de
competities, tijdlijnen en afhankelijkheden verschillen van onze historische
data. Het zou misleidend zijn om diens claims, percentages of actuele uitkomsten
zomaar als beter model over te nemen.

Daarom heeft deze branch eerst
`python -m supahbetting.research_challengers` (of
`vergelijk_modellen.bat`). Het vergelijkt een vooraf vaste
Dixon-Coles-correctie (ρ = −0,13) met de onafhankelijke Poisson-kansen op
dezelfde chronologisch afgesplitste gespeelde wedstrijden. Het maakt een
rapport in `data/research/model_challengers.json`.

**Nog geen automatische fusie:** de echte toekomstige voorspellingen moeten
onafhankelijk vóór aftrap worden geregistreerd, en beide kandidaten moeten
over een voldoende grote steekproef via Brier, log loss, kalibratie en
data-/licentiedekking worden vergeleken. Pas daarna kunnen we een
modelvariant promoten, zonder terugkijkfouten.

## 5. Wat nog ontbreekt voor ‘super goed getraind’?

- Betrouwbare actuele resultaten voor **alle** zes competities, niet alleen
  de beperkte gratis API-dekking.
- Completere spelers- en teamstatistieken (geschoten/verdedigde kansen,
  keeperprestaties, opstellingen en speeltijd) met geldige bronlicentie.
- Verifieerbare en vóór de aftrap bekende gegevens over beschikbaarheid,
  vermoeidheid, weersverwachtingen en veldondergrond.
- Een grote, maandenlange **echt prospectieve** steekproef, ook bij negatieve
  uitkomsten. Historische scores zijn geen winstgarantie.
- Alleen met echte bookmakerprijzen is een vergelijking met break-even odds,
  netto verwachte waarde en bookmaker-marge zinvol.

**Deze v0.13-branch blijft onderzoekssoftware, zonder echte inzetten of
integratie met bookmakeraccounts.**


## 6. Herstel: TheSportsDB geeft herhaaldelijk HTTP-fouten

Als je in het monitorvenster voor meerdere competities dezelfde melding
`Request naar sportsdb mislukt ... HTTPError` ziet, betekent dat een
**externe bronfout** en niet een defecte CPU of mislukte lokale modeltraining.
De gratis TheSportsDB-v1-sleutel `123` wordt nog op de officiële site
gedocumenteerd; een HTTP-fout op je pc bewijst **niet** dat die sleutel
wereldwijd buiten werking is.

**Reparatie in deze researchbranch:**

- Het exacte HTTP-statusnummer (zoals 403, 404, 429 of 5xx) wordt nu gelogd.
  HTTP 403 betekent vaak dat toegang voor dit verzoek wordt geweigerd;
  HTTP 429 betekent dat er te veel verzoeken zijn gedaan. Zonder statuscode
  weten we niet welk probleem op jouw verbinding optreedt.
- Na **één** fout stopt TheSportsDB voor die controlecyclus; er volgen
  dus geen tientallen verzoeken naar andere datums en competities.
  OpenLigaDB en een eventueel geconfigureerde football-data.org API blijven
  afzonderlijk werken.
- Sommige echte voetbalmatches hebben een `strTimestamp` zonder
  tijdzone-aanduiding. Als TheSportsDB **uitdrukkelijk Soccer** aangeeft,
  met een overeenkomstige `dateEvent` en een volledige ISO-tijd, wordt
  die volgens de gepubliceerde API-conventie als UTC gelezen. Voor andere
  sporten of twijfelachtige datums blijft de tijd onbekend.
- De monitor houdt de bestaande lokale getrainde modellen intact;
  mislukte extra API-aanvragen overschrijven de historische data niet.

**Updateprocedure:** sluit de monitor- en dashboardvensters. Bij een Git-installatie
kun je `update_supahbetting.bat` gebruiken; bij een ZIP-installatie download
je de nieuwste ZIP van deze branch en behoud je `.supahbetting/` en
`data/research/`. Start opnieuw met `start_supahbetting.bat`. Voor een
onmiddellijke handmatige controle gebruik je `ververs_speelschema.bat`.
De eerste TheSportsDB-storing geeft nu één duidelijke melding met HTTP-code
in plaats van een lange foutlijst.

**Als je steeds HTTP 403/429 krijgt:** gebruik indien toegestaan de
<https://www.thesportsdb.com/docs/api> en controleer de HTTP-status
zonder de provider te belasten. Een officieel
<https://www.football-data.org/>-token (eigen, lokaal ingesteld via
`configureer_speelschema_api.bat`) biedt een onafhankelijke bron.
Een werkende provider is géén garantie op een compleet speelschema of
recente modeltrainingsdata.


## 7. Eredivisie weer zichtbaar bij TheSportsDB-storing (17 oktober 2026)

**Oorzaak:** de v0.13-website toont alleen geverifieerde wedstrijden uit
aangesloten speelschemabronnen, geen oude OpenFootball-archiefagenda. Toen
TheSportsDB herhaaldelijk HTTP-errors gaf, bleef voor `nl.1` zonder
football-data.org-token geen actuele speelschemaleverancier over.
**De Eredivisie en getrainde teamratings waren niet verdwenen.**

De experimentele branch heeft nu een **eigen KNVB-koppeling voor de
Eredivisie**, los van TheSportsDB:

- De monitor controleert de officiële pagina
  <https://www.knvb.nl/competities/eredivisie/programma> met één
  begrensd verzoek per refresh, en probeert uitsluitend echte in die
  pagina aangekondigde datum-thuisploeg-tijd-uitploeg-combinaties
  te parseren.
- Als dat netwerkverzoek mislukt of de parser geen voldoende herkenbaar
  programma vindt, gebruikt hij de beperkte, **handmatig op
  17 oktober 2026 gecontroleerde officiële KNVB-programmagegevens**
  in `supahbetting/data/knvb_eredivisie_2026_27.json` (26 echte
  wedstrijden van 17 oktober t/m 1 november). Dat is **geen livefeed**.
- Omdat het KNVB-programma kan worden gewijzigd, is deze reservekopie
  maximaal **zeven dagen** als recent gecontroleerd geclassificeerd.
  Daarna zijn de vermelde data nog informatief, maar nooit ongemerkt
  opnieuw als actueel bevestigd; de monitor moet de officiële
  agenda opnieuw ophalen of een andere geldige bron vinden.
- Alleen wedstrijden waarvan de aftrap nog niet heeft plaatsgevonden
  komen tussen de toekomstige wedstrijden. De tijden zijn op de
  KNVB-pagina in Amsterdamse lokale tijd opgegeven en worden zorgvuldig
  naar UTC omgerekend, óók over de wintertijdomschakeling op
  25 oktober 2026.
- De naamvarianten van **Telstar (Telstar 1963)** en
  **N.E.C. (NEC)** worden nu via expliciete aliassen aan het reeds
  getrainde scoremodel gekoppeld. Er worden geen teams verzonnen.
- KNVB krijgt een afzonderlijk bronlabel en bronverwijzing op de website.
  Een **actuele** KNVB-webcontrole heeft voorrang; bij een
  **gedateerde** KNVB-reservekopie krijgt een nieuwere
  football-data.org-koppeling voorrang.
- Geen KNVB-gegevens worden als OpenFootball-CC0-data naar GitHub
  gesynchroniseerd; officiële speelschema's en wedstrijdresultaten
  blijven gescheiden van de trainingsuitslagen.

**Concreet voorbeeld:** na 17 oktober 2026 omstreeks 17.41 uur
lokale tijd blijven de nog niet begonnen wedstrijden
**Telstar–Feyenoord (20.00 uur)** en
**Sparta Rotterdam–Willem II (21.00 uur)** zichtbaar. De reeds
begonnen ADO Den Haag–PSV-wedstrijd van 16.30 uur wordt niet als
toekomstig aangeduid. Op zondag 18 oktober vermeldt de KNVB o.a.
PEC Zwolle–Go Ahead Eagles en FC Groningen–Ajax.

**Update-instructie:** stop de oude monitor, gebruik
`update_supahbetting.bat` wanneer je een Git-checkout hebt (of
download de nieuwste ZIP van dezelfde experimentele branch met behoud
van `.supahbetting/` en `data/research/`), start
`start_supahbetting.bat`, en voer desgewenst
`ververs_speelschema.bat` uit. Kijk in het monitorvenster naar
bronwaarschuwingen en controleer in de website
`Wedstrijden & modelvoorkeuren` met filter **Eredivisie**.

De huidige modeluitslagen lopen op dit moment nog achter t/m
20 september 2026. KNVB zorgt voor de **wedstrijdkalender**, niet
voor geverifieerde dagelijkse **eindstanden**. De voorspellingen
blijven daarom experimenteel en vermelden hun oudere trainingsdatum.
