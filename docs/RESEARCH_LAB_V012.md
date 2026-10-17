# SupahBetting Research Lab v0.12 — gecontroleerd onderzoek vanaf 2016

**Status: concept/testbranch.** Onderdeel van `feature/research-data-v0.12.0`, naast v0.10 en v0.11. Geen automatische wijzigingen in `main` of het standaardmodel.

## Starten op Windows

1. Download de ZIP van [de research-branch](https://github.com/henkdepotvis0180/supahbetting/archive/refs/heads/feature/research-data-v0.12.0.zip), pak volledig uit en zorg dat **Python 3.11+** beschikbaar is.
2. Je eerdere `gh auth login` volstaat als je het rapport en model naar GitHub wilt uploaden en de account schrijfrechten heeft. Gebruik géén bookmaker-API-token als GitHub-token.
3. Start `start_research_dashboard.bat`. Dat opent de monitor in een **apart zichtbaar venster** en start het bestaande dashboard. Het dashboard blijft uitsluitend lokaal via `http://127.0.0.1:8765/` bereikbaar. Scroll naar **Live trainingslaboratorium**.
4. Houd het monitorvenster geopend; de broncontrole draait iedere **6 uur**. Ctrl+C of de machine uitschakelen stopt de monitor. Er draait géén verborgen taak in de cloud.
5. Liever één controle? Gebruik `research_refresh_once.bat`. Alleen lokaal zonder upload? `python -m supahbetting.research_monitor --once --no-upload`.

Voor de complete kalenderperiode vanaf januari 2016 wordt ook de tweede helft van seizoen 2015/16 meegenomen. De eerste start vraagt tot **12 seizoenen × 7 competities** op (maximaal 84 seizoensbestanden, inclusief 2015/16 voor januari–juni 2016). Er is een vertraging tussen verzoeken om de open bron niet onnodig te belasten. Daarna worden normaal alleen het huidige en vorige seizoen gecontroleerd; **minimaal wekelijks** worden alle seizoenen opnieuw bekeken om eerder ontbrekende bestanden te vinden. Handmatige hercontrole van alle seizoenen kan met `python -m supahbetting.research_monitor --once --full`.

## Wedstrijden van vandaag en toekomstige voorspellingen

Deze researchbranch heeft nu een **tweede dashboardsectie ‘Wedstrijden vandaag & binnenkort’** naast ‘Live trainingslaboratorium’. Daar kun je filteren op competitie, vandaag, drie of vijftien dagen, en alleen beschikbare 1X2-voorspellingen. Elk kaartje vermeldt aftraptijd, bron, kansen voor thuis/gelijk/uit, verwachte doelpunten, de laatste uitslag in het model en zo nodig een waarschuwing.

### Zo krijg je de lijst te zien

1. Download de nieuwste ZIP van de researchbranch en **bewaar vóór vervanging** de originele `.supahbetting/` en `data/research/` uit je vorige map. De eerste bevat je lokale configuratie, de tweede je datasets en onveranderlijke voorspelsnapshots.
2. Open `start_research_dashboard.bat` voor de gewone server plus de periodieke monitor. De monitor werkt het speelschema in zijn controlecyclus bij.
3. Wil je **direct** het speelschema opnieuw ophalen zonder volledig te trainen? Open `ververs_speelschema.bat`. Ga terug naar de browser en klik **‘Dashboard bijwerken’** (dit laadt alleen de lokale cache opnieuw).
4. Voor uitgebreidere dekking kun je **optioneel** `configureer_speelschema_api.bat` starten en het eigen **football-data.org**-token invullen bij `providers > football-data > api_key`. Dat token staat uitsluitend in `.supahbetting/providers.json` op je computer en wordt niet naar GitHub geüpload. Het is **geen** GitHub-token of bookmaker-API-token.

Zonder token werkt het systeem via TheSportsDB en voor enkele competities OpenLigaDB. De gratis versie van **TheSportsDB** biedt maximaal *drie wedstrijden per geselecteerde dag en één volgend/vorig duel per competitie*; de lijst kan dus **onvolledig** zijn. Met een geldige football-data.org API-sleutel zijn (binnen toegestane competities en het abonnement) toekomstige wedstrijden over de periode van vijftien dagen beter gedekt. Gratis football-data.org staat **maximaal tien requests per minuut** toe. De onderzoeksmonitor respecteert deze begrenzingen en voert geen API-aanvraag uit zodra een bezoeker de pagina opent.

Voor de Belgische Pro League levert football-data.org in onze huidige mapping geen algemene competitiecode, zodat het gratis TheSportsDB-speelschema een belangrijke — maar beperkte — bron blijft. Andere rechten/licenties moeten apart bevestigd worden voordat we die koppelen.

### Wanneer is er een voorspelling?

- De wedstrijd is door een actieve speelschemabron als **gepland** gemeld, met een tijdstip **na het ophalen**.
- Beide clubs zijn exact of via een expliciet gecontroleerd alias bekend in het onderzoeksmodel.
- De gespeelde trainingsuitslagen van die competitie zijn **niet meer dan 89 dagen oud**. Een model dat ernstig achterloopt, krijgt geen automatisch percentage.
- De aftraptijd is aanwezig en betrouwbaar; anders staat duidelijk ‘geen geverifieerde aftraptijd’.
- We tonen een waarschuwing als de laatste trainingsuitslag **14 dagen of langer** geleden is. De kansen gebruiken nog geen schot-xG, tactische eventdata, blessures of verwachte opstellingen.

OpenFootball-archiefwedstrijden mogen als *voorlopig* in de kalender worden getoond als een actieve bron ze niet bevestigt, maar krijgen **geen** modelvoorspelling. Zo suggereren we niet dat een oud schema actueel is. Live/afgelopen/geannuleerde wedstrijden worden evenmin voorgesteld als toekomstige voorspellingen.

### Echte prospectieve tests en privacy

Het lokale bestand `data/research/provider_forecast_log.json` bewaart de oorspronkelijke kansen en tijdstippen bij de **eerste voorspelling vóór aftrap**. Wanneer exact hetzelfde providerwedstrijdnummer later als afgelopen wordt gerapporteerd, worden Brier en log loss toegevoegd. Een verplaatste wedstrijd kan niet onopgemerkt met een oude voorspelling beoordeeld worden. Dit bestand blijft **lokaal**: het wordt nooit vervangen tijdens een nieuwe ZIP-installatie en nooit als providergegevens naar de openbare onderzoeksbranch geüpload.

De actuele API-speelschema's staan uitsluitend lokaal in `data/research/upcoming_predictions.json`: ze kunnen andere licenties hebben dan de publieke CC0-wedstrijdresultaten. **Alleen** de gecontroleerde CC0-historiek, het afzonderlijke experimentele model en het bijbehorende onderzoeksrapport blijven automatisch naar GitHub gaan als die resultaten wijzigen. Een werkende speelschema-koppeling betekent dus niet dat de historische wedstrijddata al volledig tot vandaag zijn bijgewerkt.

### Opgeslagen bestanden

- `data/research/inventory.json`: lokaal volledig wedstrijd- en fixture-overzicht, met hiaten.
- `data/research/raw/`: lokale CC0-broncaches en SHA-256-herkomst.
- `data/research/candidate_model.json`: experimenteel model, opnieuw opgebouwd met de ingelezen resultaten.
- `data/research/shadow_predictions.json`: onveranderlijke prognoses die **vóór de speeldag** zijn vastgelegd; worden later met de eindstand beoordeeld.
- `data/research/research_report.json`: lokaal dashboardrapport.
- `data/research/monitor_status.json`: laatste controle-/uploadstatus.
- `data/research/verified_context.json`: optionele, gecontroleerde extra bronrecords.

Deze lokale bestanden en tokens worden door `.gitignore` beschermd. Bij veranderde eindstanden gaan alleen toegestane **publieke** CC0-data per competitie naar `data/research/verified/<competitie>.json`, plus een afzonderlijk experimenteel model en `training_reports/research_live/latest.json` naar GitHub, **uitsluitend op deze testbranch**. De samenvatting wordt als laatste geschreven, zodat een mislukte tussentijdse upload opnieuw geprobeerd kan worden. Check `monitor_status.json` bij netwerk- of authenticatiefouten.

De monitor bewaart data ook als GitHub tijdelijk niet bereikbaar is. Bij de volgende cyclus wordt een nog niet gepubliceerde dataset opnieuw geprobeerd. Bronfouten mogen bestaande scores niet ongemerkt verwijderen.

**Dataverversing ≠ data-actualiteit.** [OpenFootball football.json](https://github.com/openfootball/football.json) genereert in 2026 wel dagelijks bronkopieën, maar schrijft expliciet dat onderliggende bronnen niet gegarandeerd dagelijks bijgewerkt worden. Het dashboard toont daarom de **daadwerkelijke nieuwste eindstand**, ontbrekende competitie-/seizoensbestanden en laatst gecontroleerde datum. De tool verzint geen ontbrekende uitslagen. Ook betekent 2016–heden de kalenderperiode die we proberen op te halen; het betekent niet 'alle wedstrijden ter wereld'. De eerste scope is zeven grote competities.

## v0.12 gegevenskwaliteit — reparatie van de eerste dashboardcontrole

De eerste onderzoeksrun op **17 oktober 2026** laadde 22.665 OpenFootball-wedstrijden, maar de laatste wedstrijd in die publieke bron bleek van **20 september 2026**. De Belgische Pro League liep zelfs maar tot **2 november 2025**, en **10 competitie-/seizoensbestanden** ontbraken. Dit zijn bronhiaten: er was **geen reden om de download geslaagd maar actueel te noemen**.

De monitor en het dashboard onderscheiden voortaan:
- **Eerste historische import** (bij deze run 22.665) van **nieuwe wedstrijden na de vorige broncontrole** (bij de eerste run per definitie 0);
- het werkelijke datumverschil tussen de computerklok en de laatst ingelezen eindstand;
- waarschuwingen per competitie, bij 14+ dagen vertraging en bij 90+ dagen ernstig verouderd;
- het aantal voorspellingen dat vóór een speeldag is vastgelegd versus het aantal voorspellingen waarvoor later al een uitslag kon worden beoordeeld.

Ook als de leverancier een bestand vandaag opnieuw genereert, blijft het dashboard een waarschuwing tonen als de inhoud alleen oudere scores bevat. De vertraging wordt **niet** opgelost door het model harder of langer te trainen.

### Andere bronnen en voorwaarden

[OpenFootball](https://github.com/openfootball/football.json) is CC0 en mag veilig op de experimentele branch worden gepubliceerd, maar meldt dat zijn onderliggende data niet gegarandeerd dagelijks worden bijgewerkt.

[Football-Data.co.uk](https://www.football-data.co.uk/belgiumm.php) publiceert actuele en historische Belgische wedstrijden in CSV. De [fair-usagevoorwaarden](https://www.football-data.co.uk/contact.php) staan echter uitsluitend licht gebruik door particulieren of academisch onderzoek toe, met **maximaal twee geautomatiseerde downloads per week** en zonder zware commerciële scrape- of trainingsprojecten. Daarom wordt deze dataset niet ongemerkt opgehaald, met CC0-resultaten vermengd of integraal naar GitHub gepusht. Een losse, expliciet ingeschakelde lokale import moet deze voorwaarden en de herkomst respecteren.

De reeds ondersteunde [football-data.org API](https://www.football-data.org/documentation/api) kan later als aanvullend controlepunt dienen als er een geldige API-sleutel en passende competitietoegang is. Toegang tot de Belgische competitie is daarmee niet automatisch gegarandeerd.

### Oude ZIP bijwerken zonder gegevens te verliezen

Omdat je de repository als ZIP hebt uitgepakt, wordt die **niet automatisch door GitHub vervangen**. Gebruik de nieuwste ZIP van de **researchbranch**, sluit beide CMD-vensters, en bewaar bij vervanging van je map zeker de lokale mappen **`.supahbetting/`** en **`data/research/`**. Hierin staan respectievelijk de instellingen en de historische voorraad, eerdere rapporten en de vooraf geregistreerde voorspellingen. Die prognoses mogen niet worden verwijderd of achteraf opnieuw aangemaakt omdat hun tijdstip nodig is voor eerlijke toekomsttests.

De nieuwe dashboardwaarschuwingen verschijnen na het openen van het dashboard uit de nieuwe ZIP en een daaropvolgende gegevenscontrole. Alleen de broncode aanpassen maakt de oude bronnen niet recenter.

## Speleranalyse en veldinvloeden: wat kan wel?

| Factor | Technisch zinvol? | Wat is daarvoor nodig? |
|---|---|---|
| Aanval | Ja | Schoten, kwaliteit van kansen/xG, loopacties, kansen creëren, voorzetten, counters, bezetting penaltygebied; rechtmatig verkregen event-/trackingdata |
| Verdediging | Ja | Geïncasseerde xG, drukacties, duels, onderscheppingen, blokken, defensieve omschakeling, standaardsituaties |
| Keeper | Ja | Schoten op doel, expected goals on target en schotstopprestaties, geen afzonderlijke zekerheid op basis van klein aantal reddingen |
| Speleropstelling | Ja | Officieel aangekondigde opstellingen met tijdstip van publicatie; zeker bij 'in het uur voor aftrap'-modellen |
| Beschikbaarheid | Beperkt | Alleen publieke, officieel bevestigde **speelbaarheid** (beschikbaar, twijfel, afwezig); geen diagnose, medische dossiers of privé-geruchten |
| Vermoeidheid | Ja | Historisch speelminuten, rustdagen, reisafstand, interlands, rouleren; nog te koppelen |
| Trainer/tactiek | Ja | Officiële trainerswissels, formatie, pressing, wedstrijdplan zoals tactisch meetbaar |
| Weer | Ja | Een **vóór de aftrap bekende voorspelling** of historische forecast-snapshot; achteraf gemeten weer als pre-matchvariabele gebruiken is datalek |
| Gras/kunstgras | Ja | Geverifieerd veldtype en stadionmetadata; veldkwaliteit alleen met officiële **pre-match** inspectie, niet via vermoedens |
| Transfers | Ja | Officiële bekendmaking en registratie-/beschikbaarheidstermijn; geen onbevestigde contractgeruchten |
| Omkoping, eten en privésituatie | Nee | Niet speculeren of personen beschuldigen; geen basis in betrouwbaar gepubliceerde prestatiemetingen |

Een groot gegevensbestand zonder onafhankelijke bronkwaliteit maakt voorspellingen niet vanzelf beter. Het huidige v0.12-model **gebruikt alleen uitslagen en daaruit geleerde teamratings**. De andere kenmerken zijn voorbereid voor bron-geattribueerde registratie, maar krijgen `training_enabled: false` totdat ze in een echte experimentenset waarde bewijzen.

### Volgende datakoppelingen (nog NIET ingebouwd)

- [StatsBomb Open Data](https://github.com/statsbomb/open-data): publiek gedeelde **selectie** van match-event- en opstellingsdata, inclusief defensieve/aanvallende gebeurtenissen, voor onderzoek; beschikbaarheid en publicatievoorwaarden per competitie controleren. Niet bruikbaar als volledige wereldwijde 2016–2026-dekking.
- [football-data.org](https://www.football-data.org/documentation/api): actuele/voorbije wedstrijdstatussen waar jouw abonnement toegang toe heeft; houdt rekening met de gratis limiet van **10 API-verzoeken per minuut** en seizoen-/competitieabonnementen.
- [Open-Meteo](https://open-meteo.com/en/docs/historical-weather-api): heranalyse en historisch weer voor verkennende plots; voor **voorspellen vóór de wedstrijd** zijn archived forecasts met oorspronkelijke uitgiftetijd nodig. Gratis API is **niet-commercieel**, dus eerst gebruiksdoel en licentie controleren; geen stilzwijgende bulk-import of automatisch doorpubliceren.

### Onderzoeksmethode

1. **Bronintegriteit:** match-ID, eindstand, competitie, speeldatum, oorspronkelijke bron-URL, timestamp en bronhiaten. Geen verzonnen ingevulde waarden. Verouderde resultaten tonen als verouderd.
2. **Tijdlijn:** alle features moeten voor de aftrap beschikbaar zijn geweest. Zelfde-dag-gepubliceerde features tellen niet mee zolang een betrouwbare aftraptijd ontbreekt.
3. **Modellen:** score-baseline, Dixon-Coles/correlated Poisson, Elo, team form, regularisatie, kalibratie en pas later eventfeatures; vergelijk per competitie.
4. **Validatie:** chronologische rolling-origin backtests (meerdere jaren), onafhankelijke toekomstige wedstrijdresultaten, Brier/log loss, kalibratie, onzekerheid en competitie-dekking. **Geen** promotie op basis van alleen teruggekeken holdout-scores.
5. **Praktische keuze:** neem alleen features op die aantoonbaar verbeteren op eerder ongeziene data. Als marktprijzen ooit worden gebruikt, bewaar echte historische odds en vergelijk eveneens zonder hindsight, inclusief marge en kosten.

## GitHub / privacy / rechten

Experimentele data- en modelbestanden kunnen zichtbaar zijn voor anderen als de repository openbaar is. Synchronisatie laat daarom alleen onpersoonlijke, publiek gelicentieerde voetbalresultaten en geaggregeerde modelbeoordelingen door. Tokens, logs met credentials, spelersgezondheidsdossiers en privégewoonten mogen nooit worden gepusht. De huidige marktvergelijker en het productie-Poisson-model blijven ongewijzigd.

**Geen garantie op betere voorspellingen of weddenschapswinst.** De tool meet verbeteringen in voorspelfouten en toont wat hij wel/niet weet; het kan geen onzichtbare tactische, medische of psychologische informatie achterhalen.
