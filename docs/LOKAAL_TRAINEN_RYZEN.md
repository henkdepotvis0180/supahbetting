# SupahBetting lokale training — Ryzen 9 9900X

## Starten op Windows

1. Download de branch `feature/model-v0.11.0` als ZIP en pak die volledig uit.
2. Installeer Python 3.11 of 3.12 en zorg dat `py -3` of `python` beschikbaar is.
3. Dubbelklik op **train_en_test_ryzen.bat**.

De batch voert achtereenvolgens uit:
- de volledige Python-testset;
- een snelle proef met vier parametercombinaties en vier workers;
- een uitgebreide zoektocht met maximaal 16 CPU-processen en een **doelbudget** van vier uur.

Er worden 64 combinaties van `alpha` en `prior_matches` onderzocht. Selectie gebeurt uitsluitend op log loss van seizoen 2024/25; pas na een volledig afgeronde zoektocht worden 2025/26 en 2026/27 beoordeeld. Er is geen garantie dat de gekozen combinatie beter is op nieuwe wedstrijden.

## Bestanden en hervatten

- `training_reports/local_optimizer_checkpoint.json` — voortgang per combinatie, automatisch hergebruikt bij gelijke data.
- `training_reports/local_optimizer_report.json` — vergelijking, gekozen validatiekandidaat en eventuele holdouts.
- `supahbetting/models/baseline.json` wordt **niet** aangepast.

De optimizer controleert de SHA-256-vingerafdruk van de trainingsdata voordat checkpoints worden hergebruikt. Bij andere data begint de zoektocht opnieuw.

**Let op:** vier uur is een budget om nieuwe taken in te plannen, geen harde proces-kill. Een reeds lopende berekening kan de totale duur iets overschrijden. De snelle controle komt daar bovenop. Stoppen met Ctrl+C kan het lopende experiment afbreken; reeds opgeslagen checkpoints blijven bestaan.

## Handmatige opties

```powershell
py -3 -m supahbetting.local_optimizer --quick --workers 4 --hours 0.1
py -3 -m supahbetting.local_optimizer --workers 16 --hours 4
```

Het systeem gebruikt standaard geen GPU. GPU-ondersteuning voor de RX 9070 XT vereist aparte implementatie en benchmarks. De code maakt geen echte weddenschappen en gebruikt geen bookmakeraccounts.
