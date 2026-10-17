"""Local native export import commands; no automatic scraping."""
import argparse
import json
from pathlib import Path
from .fork_bridge import BridgeError, PROVIDERS
from .fork_research import ResearchStore

def main():
    parser = argparse.ArgumentParser(description="SupahBetting fork exports")
    parser.add_argument("--db", type=Path, default=Path(".supahbetting/data.sqlite3"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("scan")
    imp = sub.add_parser("import")
    imp.add_argument("source", choices=PROVIDERS)
    imp.add_argument("file", type=Path)
    sub.add_parser("status")
    sub.add_parser("opportunities")
    args = parser.parse_args()
    store = ResearchStore(args.db)
    try:
        result = (
            store.scan_inbox() if args.command == "scan" else
            store.ingest(args.file, args.source) if args.command == "import" else
            store.status() if args.command == "status" else
            store.opportunities()
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except BridgeError as exc:
        parser.exit(1, "Import kon niet worden verwerkt: " + str(exc) + "\n")

if __name__ == "__main__":
    main()
