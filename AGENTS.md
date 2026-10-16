# Codex development instructions — SupahBetting

Goal: one Dutch-language football prediction + bookmaker odds analysis + paper-trading platform.

Upstream inspirations (NOT yet vendored or integrated):
- ProphitBet: https://github.com/kochlisGit/ProphitBet-Soccer-Bets-Predictor
- OddsHarvester: https://github.com/jordantete/OddsHarvester
- Prediict: https://github.com/thedatadoktor/prediict

Before incorporating upstream code: inspect actual LICENSE, dependencies, last commits, data rights, and security. Do not copy incompatible or unlicensed code. Keep attribution and source provenance.

Architecture:
- supahbetting/core.py: probability, odds and value computations
- supahbetting/cli.py: unified entrypoint
- Future adapters/predictors/: model adapters (ProphitBet concepts)
- Future adapters/odds/: licensed odds providers (OddsHarvester concepts)
- Future jobs/: scheduled predictions and evaluation (Prediict concepts)
- Future web/: Dutch dashboard

Rules:
1. Never promise profit or claim verified predictive accuracy without out-of-sample evidence.
2. Paper trading only by default; never place real-money wagers.
3. No scraping that circumvents bookmaker authentication, rate limits or terms.
4. Use leakage-free chronological backtests, calibration, and actual quoted odds.
5. Add tests for every calculation and integration.
6. Maintain README and Dutch CHANGELOG.
7. Never commit secrets/API tokens or personal account data.
8. Keep the software runnable on Windows with Python 3.11+.
