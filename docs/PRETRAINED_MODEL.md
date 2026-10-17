# SupahBetting v0.7 — voorgetraind basismodel

## Dit model is echt getraind

Het meegeleverde modelbestand is **models/baseline_v1.json**. Dit is een JSON-bestand met geleerde parameters en de historische teamsterkte, geen voorbeeldmodel en geen onveilig pickle- of joblib-bestand.

De eerste training is uitgevoerd met de reeds aanwezige historische wedstrijd-CSV uit jouw Prediict-fork. Er is géén Prediict-broncode of dataset naar SupahBetting gekopieerd.

| Kenmerk | Resultaat |
|---|---|
| Model | Historische Elo, recente vorm en multinomiale logistische regressie |
| Wedstrijden | **18.085** |
| Leagues | Premier League, Bundesliga, La Liga, Serie A, Ligue 1 |
| Meest recente historische wedstrijd | **2 juni 2024** |
| Chronologische testset | 3.143 wedstrijden, 10 oktober 2022 tot 2 juni 2024 |
| Testnauwkeurigheid | **53,33%** |
| Eenvoudige referentie: vaste H/D/A-kansen | 44,61% |
| Test log loss | **0,98164** |
| Referentie log loss | 1,06924 |
| Brier multiclass | 0,58499 |
| Referentie Brier | 0,64648 |

De chronologische test is gedaan met een model dat het testinterval bij training nog niet zag. Na die test is het **gepubliceerde JSON-model opnieuw op de volledige historische dataset gefit**. De gemelde testresultaten zijn dus NIET rechtstreeks afkomstig van een onafhankelijke evaluatie van die latere definitieve fit. Het model is ook niet vergeleken met bookmakerquoteringen. De test bewijst geen winstgevendheid.

**Belangrijk: de dataset stopt op 2 juni 2024.** Daardoor zijn transferbewegingen, promoties, blessuregegevens en teamvorm in 2025–2026 niet meegenomen. De app moet dit als verouderde modeldata tonen. Gebruik het model voorlopig voor onderzoek en fictieve tests, niet als grondslag voor echte inzetten.

## Zo gebruik je het model

1. Download de nieuwste SupahBetting-ZIP en start **start_dashboard.bat**.
2. De sectie **Historische voorspellingen** toont de trainingsdatum en de testresultaten.
3. Open een **geplande** voetbalwedstrijd, klik op **Bereken modelkansen**.
4. Je ziet kansen voor thuiswinst, gelijkspel en uitwinst plus waarschuwingen over ontbrekende teamhistorie en oude trainingsdata.

Voor het *gebruiken* van de meegeleverde parameters zijn geen NumPy of scikit-learn nodig. De kansen worden niet in jouw papieren betslip gezet en er worden geen bookmakerprijzen verzonnen.

## Later een beter model trainen

1. Haal de volledige oorspronkelijke historische CSV uit [jouw Prediict-fork](https://github.com/henkdepotvis0180/prediict/blob/main/data/football_matches_historical.csv).
2. Bewaar die lokaal als **.supahbetting/training_history.csv** en voeg in hetzelfde kolomformaat nieuwere, werkelijk gespeelde en afgelopen wedstrijden toe.
3. De kolommen **date, home_team, away_team, home_score, away_score, competition_code** worden ondersteund, naast enkele veelgebruikte alternatieve kolomnamen. Wedstrijdodds, kaarten en eindstanden worden NIET als directe voorspelfeatures ingelezen; eerdere uitslagen dienen uitsluitend voor historische vorm en Elo.
4. Klik op **train_baseline.bat**. Dit maakt een aparte Python-trainingsomgeving aan en installeert daarin de benodigde ML-pakketten. De standaardapp blijft zonder zware ML-dependencies werken.
5. Training gebeurt in volgorde van speeldatum: eerst trainperiode, dan validatie, dan een ongeziene testperiode, daarna een finale fit. Pas bij succesvolle afronding wordt het JSON-model vervangen.
6. Herstart het dashboard om de nieuwe parameters te gebruiken.

Handmatig vanuit een terminal:

    python -m pip install -r requirements-training.txt
    python -m supahbetting.train_baseline --input .supahbetting/training_history.csv --output models/baseline_v1.json

Je kunt ook de GitHub Actions-workflow **Train historical baseline** starten. Die haalt opnieuw de bestaande CSV uit jouw Prediict-fork op. De workflow haalt geen nieuwe speelschema's of uitslagen op en kan dus alleen recenter trainen als jij eerst die historie bijwerkt.

Er worden geen datasetbestanden, API-tokens of accountgegevens meegestuurd in het model. Het JSON-artifact bevat wel een SHA-256 van de gebruikte trainingsdataset en het onafhankelijke testverslag. Houd rekening met de gebruiksvoorwaarden van databronnen, ook wanneer je later andere competities toevoegt.
