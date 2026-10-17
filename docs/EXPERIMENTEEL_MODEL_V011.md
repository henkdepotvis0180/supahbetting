# SupahBetting — v0.11.0 experimenteel model

## Wat is daadwerkelijk geproduceerd?

Op basis van het geüploade rapport `training_reports/local_runs/latest_complete.json`
heeft GitHub Actions het Poisson-model **opnieuw opgebouwd vanuit de echte historische
wedstrijduitslagen** met `alpha=0.04` en `prior_matches=3`.

- **Bestaande productie:** `supahbetting/models/baseline.json` (v0.10.0)
- **Nieuw experimenteel model:** `supahbetting/models/baseline_v0.11.0_experimental.json`
- **Databasis:** 19.884 wedstrijden uit 7 competities, meest recente geregistreerde uitslag 20 september 2026
- **Modelselectie:** 64 parametercombinaties; de beste werd gekozen op de validatieset 2024/25
- **Vervolgens afzonderlijk geëvalueerd:** 2025/26 en onvolledig seizoen 2026/27

### Scores

| Periode | v0.10 log loss | v0.11 experimenteel log loss | Lagere waarde beter |
|---|---:|---:|---|
| Validatie 2024/25 | 1.00103 | 0.99779 | v0.11 |
| Retrospectieve toets 2025/26 | 0.98370 | 0.97725 | v0.11 |
| Retrospectieve toets 2026/27 (295 wedstrijden) | 0.98071 | 0.97760 | v0.11 |

**Waarschuwing:** alle perioden zijn inmiddels in het ontwikkelproces bekeken.
Deze verschillen zijn niet hetzelfde als onafhankelijke toekomstige prestaties,
noch bewijs van winst tegenover bookmakerprijzen. Het experiment gebruikt
dezelfde onderliggende historische data als v0.10.

## Naast elkaar vergelijken

Download de nieuwste ZIP van `feature/model-v0.11.0`, pak uit en start
`start_dashboard.bat`. Onder het Poisson-model verschijnt het v0.11-testelement
als het aparte modelbestand aanwezig is. Bereken een wedstrijd en kies daarna
**'Vergelijk v0.10.0 met v0.11.0 (experimenteel)'**.

De bestaande voorspelling en de handmatige-analyseknop blijven standaard v0.10.0
gebruiken. Een experiment wordt **niet automatisch actief**.

De read-only API-routes voor vergelijking zijn:

- `GET /api/trained/experimental/status`
- `POST /api/trained/compare` met JSON `{"league":"nl.1","home_team":"Ajax","away_team":"PSV"}`

De normale `POST /api/trained/predict` blijft v0.10.0 gebruiken.

## Wat gebeurt er bij de volgende training?

- `train_model.bat` traint het **bestaande basismodel lokaal opnieuw** met de
  ingepakte wedstrijddataset. Als er geen nieuwe wedstrijduitslagen zijn toegevoegd,
  is dit doorgaans hetzelfde model en **geen nieuwe kennis**. Deze oudere batch
  schrijft wel opnieuw naar het lokale `baseline.json` en synchroniseert niets.
- `train_en_test_auto.bat` detecteert hardware, voert modeltests en de lokale
  optimalisatie uit en publiceert na succes de **volledige onderzoeksresultaten** op
  `feature/model-v0.11.0`. Wanneer dat rapport wijzigt, bouwt de GitHub-workflow
  `.github/workflows/build-experimental-model.yml` automatisch het experimentele
  model opnieuw op **mits** de historische wedstrijddatasets in GitHub met die
  in het rapport overeenkomen. Anders wordt de build uit veiligheid geweigerd.
- Meerdere runs met ongewijzigde data leveren doorgaans dezelfde best passende
  instellingen; langer draaien maakt niet vanzelf nieuwe wedstrijden beschikbaar.

Een nieuw gepubliceerd model staat na de workflow op GitHub. Een eerder
gedownloade ZIP wordt niet automatisch bijgewerkt: download de bijgewerkte
branch of gebruik `git pull` als je een lokale Git-checkout gebruikt.

## Verificatie en veiligheid

`python -m supahbetting.experimental_model` controleert de SHA-256-vingerafdruk
van alle wedstrijden tegen het lokaal gepubliceerde rapport, rekent de
sequentiële doelpuntmodellen opnieuw uit en controleert log loss, Brier en
wedstrijdtellingen. Pas dan schrijft het een *apart* experimenteel modelbestand.

De workflow controleert dat `baseline.json` niet is veranderd en commit
uitsluitend `baseline_v0.11.0_experimental.json` naar de experimentele branch.
GitHub Actions-tests controleren bovendien de afzonderlijke API en het behoud
van het standaardmodel.
