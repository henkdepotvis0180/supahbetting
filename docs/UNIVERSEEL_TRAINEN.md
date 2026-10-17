# Universele Windows-training en automatische GitHub-upload

## Download en trainen
1. Download de ZIP van branch `feature/model-v0.11.0` en pak hem volledig uit.
2. Installeer Python 3.11+ en (eenmalig) [GitHub CLI](https://cli.github.com/).
3. Open PowerShell of CMD en voer eenmalig `gh auth login` uit. Log in bij **github.com** met een GitHub-account dat mag schrijven naar `henkdepotvis0180/supahbetting`.
4. Dubbelklik op `train_en_test_auto.bat`.

De Windows-launcher controleert CPU, logisch aantal processors, RAM en GPU; hij kiest conservatief maximaal 16 CPU-processen. De GPU wordt *alleen herkend*: het huidige model gebruikt CPU. Het hardwareprofiel blijft op de pc in `training_reports/hardware_profile.json`.

Vervolgens voert de launcher uit: alle Python-tests, een korte proef, de uitgebreide parameterzoektocht (richtbudget vier uur), en **alleen na een volledig afgeronde run** de automatische GitHub-upload. Het budget is geen harde process-stop; lopend werk kan langer duren.

## Wat gaat wel/niet naar GitHub?
De synchronisatie gebruikt rechtstreeks GitHubs HTTPS API, dus hij werkt ook als je de code via **Download ZIP** hebt ontvangen en geen `.git`-map hebt.

- Doelbranch: `feature/model-v0.11.0` (niet `main`).
- Doelbestand: `training_reports/local_runs/latest_complete.json`.
- Geüpload: de geselecteerde experimentele parametercombinatie, de validatie-/testmetingen, alle 64 kandidaatmetingen, datasetvingerafdruk en laatste uitslagdatum.
- **Niet** geüpload: API-sleutels/tokens, `.env`, persoonlijke instellingen, hardwaredetails, lokale database, ruwe wedstrijdbestanden, of het productie-Poisson-model.
- Het gedeelde JSON-bestand wordt bij een volgende succesvolle complete run vernieuwd; vorige versies blijven in de Git-commithistorie. Meerdere pc's schrijven naar dezelfde laatste versie: de laatst succesvol gepubliceerde run is zichtbaar.

Een onvolledige run of alleen de snelle proef wordt nooit gepubliceerd. De lokale voortgang blijft in `training_reports/local_optimizer_checkpoint.json`; de lokale metingen in `training_reports/local_optimizer_report.json`.

## Als GitHub-upload niet werkt
De trainer bewaart de lokale rapporten ook zonder GitHub-toegang. Controleer de inlogstatus met `gh auth status` en voer indien nodig `gh auth login` opnieuw uit. Probeer de upload daarna zonder hertraining:

```powershell
py -3 -m supahbetting.github_training_sync
```

Droogtesten zonder internet of GitHub-toegang:

```powershell
py -3 -m supahbetting.github_training_sync --dry-run
```

Alternatief voor GitHub CLI: stel de omgevingsvariabele `SUPAHBETTING_GITHUB_TOKEN` lokaal in op een **GitHub** fine-grained personal access token met **Contents: Read and write**, uitsluitend voor deze repository. Gebruik daarvoor **niet** je bookmaker-/dataprovider-API-token. Plaats het token **nooit** in een BAT-bestand, configbestand in de repository of chat.

## Modelkwaliteit en actualiteit
De upload publiceert alleen **onderzoeksresultaten**. Hij promoveert een kandidaat niet automatisch naar `supahbetting/models/baseline.json` of `main`. Dit voorkomt dat een experimenteel model zonder review het dashboard beïnvloedt.

Herhaald trainen op precies dezelfde historische data maakt de brondata niet actueler. Nieuwe uitslagen moeten eerst gecontroleerd in `data/historical/` terechtkomen. Een lagere historische log loss geeft bovendien geen garantie op succesvolle weddenschappen.
