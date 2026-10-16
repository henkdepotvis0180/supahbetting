"""Single CLI for prediction, odds analysis and paper bet tracking."""
import argparse
import json
from pathlib import Path
from .core import match_probabilities, expected_value, no_vig_probabilities


def main():
    parser = argparse.ArgumentParser(prog="supahbetting")
    sub = parser.add_subparsers(dest="command", required=True)
    pred = sub.add_parser("predict", help="Poisson match probabilities")
    pred.add_argument("--home-xg", type=float, required=True)
    pred.add_argument("--away-xg", type=float, required=True)
    odds = sub.add_parser("odds", help="Analyze decimal odds")
    odds.add_argument("--probability", type=float, required=True)
    odds.add_argument("--decimal-odds", type=float, required=True)
    paper = sub.add_parser("paper", help="Log a simulated bet")
    paper.add_argument("--event", required=True)
    paper.add_argument("--market", required=True)
    paper.add_argument("--probability", type=float, required=True)
    paper.add_argument("--decimal-odds", type=float, required=True)
    paper.add_argument("--stake", type=float, default=1.0)
    paper.add_argument("--file", default="paper_bets.jsonl")
    args = parser.parse_args()
    if args.command == "predict":
        result = match_probabilities(args.home_xg, args.away_xg)
    elif args.command == "odds":
        result = {"implied_probability": 1 / args.decimal_odds,
                  "expected_roi": expected_value(args.probability, args.decimal_odds)}
    else:
        if args.stake <= 0:
            parser.error("--stake must be positive")
        edge = expected_value(args.probability, args.decimal_odds)
        result = {"event": args.event, "market": args.market, "probability": args.probability,
                  "decimal_odds": args.decimal_odds, "stake": args.stake, "expected_roi": edge,
                  "status": "unsettled", "mode": "paper"}
        with Path(args.file).open("a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
