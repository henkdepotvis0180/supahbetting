# SupahBetting Research Lab v0.12 — gecontroleerd onderzoek vanaf 2016

**Status: concept/testbranch.** Onderdeel van `feature/research-data-v0.12.0`, naast v0.10 en v0.11. Geen automatische wijzigingen in `main` of het standaardmodel.

## Starten op Windows

1. Download de ZIP van [de research-branch](https://github.com/henkdepotvis0180/supahbetting/archive/refs/heads/feature/research-data-v0.12.0.zip), pak volledig uit en zorg dat **Python 3.11+** beschikbaar is.
2. Je eerdere `gh auth login` volstaat als je het rapport en model naar GitHub wilt uploaden en de account schrijfrechten heeft. Gebruik géén bookmaker-API-token als GitHub-token.
3. Start `start_research_dashboard.bat`. Dat opent de monitor in een **apart zichtbaar venster** en start het bestaande dashboard. Het dashboard blijft uitsluitend lokaal via `http://127.0.0.1:8765/` bereikbaar. Scroll naar **Live trainingslaboratorium**.
4. Houd het monitorvenster geopend; de broncontrole draait iedere **6 uur**. Ctrl+C of de machine uitschakelen stopt de monitor. Er draait géén verborgen taak in de cloud.
5. Liever één controle? Gebruik `research_refresh_once.bat`. Alleen lokaal zonder upload? `python -m supahbetting.research_monitor --once --no-upload`.

Voor de complete kalenderperiode vanaf januari 2016 wordt ook de tweede helft van seizoen 2015/16 meegenomen. De eerste start vraagt tot **12 seizoenen × 7 competities** op (maximaal 84 seizoensbestanden, inclusief 2015/16 voor januari–juni 2016). Er is een vertraging tussen verzoeken om de open bron niet onnodig te belasten. Daarna worden normaal alleen het huidige en vorige seizoen gecontroleerd; **minimaal wekelijks** worden alle seizoenen opnieuw bekeken om eerder ontbrekende bestanden te vinden. Handmatige hercontrole van alle seizoenen kan met `python -m supahbetting.research_monitor --once --full`.

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
