# SupahBetting

**v0.1.0 — onderzoeksbasis, nog geen live odds of echte upstream-code-integratie.**

Één Python-programma met drie geplande modules:
- [ProphitBet](https://github.com/kochlisGit/ProphitBet-Soccer-Bets-Predictor): AI-voorspellingen
- [OddsHarvester](https://github.com/jordantete/OddsHarvester): odds-verzameling
- [Prediict](https://github.com/thedatadoktor/prediict): dagelijkse analyses

Deze upstream projecten zijn nog niet samengevoegd. Eerst controleren we licenties, dependencies, veiligheid en toegestane data-API's.

## Starten (Windows / Python 3.11+)

```powershell
python -m supahbetting.cli predict --home-xg 1.7 --away-xg 1.1
python -m supahbetting.cli odds --probability 0.60 --decimal-odds 2.00
python -m supahbetting.cli paper --event "Team A - Team B" --market home --probability 0.6 --decimal-odds 2.0 --stake 1
python -m unittest discover -s tests -v
```

De huidige Poisson-voorspellingen gebruiken handmatig opgegeven xG-cijfers. De paper bets worden lokaal opgeslagen in `paper_bets.jsonl`.

## Roadmap
1. Bron- en licentieaudit en modulaire adapters.
2. Historische data, kalibratie en chronologische backtesting.
3. Nederlandstalig webdashboard en scheduler.
4. Odds-integraties via toegestane providers, met optionele Toto/Unibet-dekking indien beschikbaar.

**Geen echt-geld inzetten. Geen gegarandeerde winst.** Zie `AGENTS.md` voor Codex-instructies en `CHANGELOG.md` voor wijzigingen.
