"""Local HTTP API and static dashboard. Default binding is strictly loopback only."""
from __future__ import annotations

import argparse
import json
import logging
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .domain import MARKETS, ValidationError, quote_slip
from .store import Store
from .live_scores import LiveScores, LiveDataUnavailable, InvalidLiveRequest
from .external_feeds import ProviderHub, FootballData
from .provider_config import make_local_config
from .fork_research import ResearchStore
from .fork_bridge import BridgeError
from .trained_model import (TrainingError, load_pretrained, predict_trained,
                            PROVIDER_LEAGUES)

ROOT = Path(__file__).parent / "static"
JSON_LIMIT = 24_576
MAX_PATH = 512
LOG = logging.getLogger("supahbetting")


def preview(store, payload):
    if not isinstance(payload, dict):
        raise ValidationError("Ongeldige aanvraag")
    choices = payload.get("legs")
    if not isinstance(choices, list) or not 1 <= len(choices) <= 8:
        raise ValidationError("Selecteer 1 tot 8 wedstrijden")
    legs = []
    for choice in choices:
        if not isinstance(choice, dict):
            raise ValidationError("Ongeldige selectie")
        match_id = choice.get("match_id")
        market = choice.get("market")
        if not isinstance(match_id, int) or isinstance(match_id, bool):
            raise ValidationError("Ongeldige wedstrijd-ID")
        if market not in MARKETS:
            raise ValidationError("Onbekende markt")
        match = store.get_match(match_id)
        if match["is_settled"]:
            raise ValidationError("Deze wedstrijd is al afgelopen en afgerekend")
        value = match["analysis"]["markets"][market]
        legs.append({
            "match_id": match_id, "market": market,
            "home_team": match["home_team"], "away_team": match["away_team"],
            "probability": value["probability"], "decimal_odds": value["decimal_odds"],
        })
    return {"quote": quote_slip(legs, payload.get("stake")), "legs": legs}


def make_handler(store, live_scores=None, provider_hub=None, research_hub=None, trained=None):
    """Create a request handler with isolated store, useful for integration tests."""
    live_scores = live_scores if live_scores is not None else LiveScores()
    provider_hub = provider_hub if provider_hub is not None else ProviderHub(openliga=live_scores)
    research_hub = research_hub if research_hub is not None else ResearchStore(store.path)
    if trained is None:
        try:
            trained = load_pretrained()
        except TrainingError:
            trained = None
    class Handler(BaseHTTPRequestHandler):
        server_version = "SupahBetting/0.7"

        def _headers(self, code, mimetype, length):
            self.send_response(code)
            self.send_header("Content-Type", mimetype)
            self.send_header("Content-Length", str(length))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; img-src 'self' data:; object-src 'none'; "
                "base-uri 'none'; frame-ancestors 'none'; "
                "frame-src https://www.youtube-nocookie.com",
            )
            self.end_headers()

        def reply(self, code, obj):
            payload = json.dumps(obj, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self._headers(code, "application/json; charset=utf-8", len(payload))
            self.wfile.write(payload)

        def _path(self):
            if len(self.path) > MAX_PATH:
                raise ValidationError("Aanvraagpad te lang")
            return urlsplit(self.path).path

        def _check_host(self):
            # Prevent an arbitrary Host header resolving into a trusted local listener.
            allowed = {f"127.0.0.1:{self.server.server_port}",
                       f"localhost:{self.server.server_port}"}
            if self.headers.get("Host", "") not in allowed:
                raise ValidationError("Ongeoorloofde Host-header")
            if self.command != "GET":
                origin = self.headers.get("Origin")
                if origin and origin not in {f"http://{host}" for host in allowed}:
                    raise ValidationError("Ongeoorloofde oorsprong")

        def _read_json(self):
            kind = self.headers.get("Content-Type", "").split(";")[0].lower().strip()
            if kind != "application/json":
                raise ValidationError("Verwacht application/json")
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise ValidationError("Ongeldige berichtlengte") from None
            if not 0 < size <= JSON_LIMIT:
                raise ValidationError("Bericht te groot of leeg")
            try:
                data = json.loads(self.rfile.read(size))
            except (ValueError, UnicodeDecodeError):
                raise ValidationError("Ongeldige JSON") from None
            if not isinstance(data, dict):
                raise ValidationError("JSON moet een object zijn")
            return data

        def do_GET(self):
            try:
                self._check_host()
                path = self._path()
                if path == "/api/health":
                    return self.reply(200, {"status": "ok", "version": "0.7.0",
                                            "mode": "paper_only", "live_odds": False})
                if path == "/api/live/providers":
                    return self.reply(200, provider_hub.catalog())
                if path == "/api/live/leagues":
                    return self.reply(200, {
                        "leagues": live_scores.leagues(),
                        "provider": "OpenLigaDB",
                        "score_feed_only": True,
                    })
                if path == "/api/live/matches":
                    params = parse_qs(urlsplit(self.path).query)
                    provider = params.get("provider", ["openliga"])[0]
                    league = params.get("league", ["all"])[0]
                    if not isinstance(provider, str) or len(provider) > 35:
                        raise InvalidLiveRequest("Ongeldige databron")
                    if not isinstance(league, str) or len(league) > 16:
                        raise InvalidLiveRequest("Ongeldige competitie")
                    return self.reply(200, provider_hub.list_matches(provider, league))
                live_match = re.fullmatch(r"/api/live/matches/([1-9][0-9]{0,9})", path)
                if live_match:
                    params = parse_qs(urlsplit(self.path).query)
                    provider = params.get("provider", ["openliga"])[0]
                    league = params.get("league", [""])[0]
                    if not isinstance(provider, str) or len(provider) > 35:
                        raise InvalidLiveRequest("Ongeldige databron")
                    if not isinstance(league, str) or len(league) > 16:
                        raise InvalidLiveRequest("Ongeldige competitie")
                    return self.reply(
                        200, provider_hub.match_detail(
                            provider, int(live_match.group(1)), league
                        )
                    )
                if path == "/api/matches":
                    return self.reply(200, {"matches": store.list_matches()})
                if path == "/api/slips":
                    return self.reply(200, {"slips": store.list_slips()})
                if path == "/api/stats":
                    return self.reply(200, store.stats())
                if path == "/api/model-metrics":
                    return self.reply(200, store.model_metrics())
                if path == "/api/trained/status":
                    if trained is None:
                        return self.reply(200, {
                            "available": False,
                            "message": "Geen getraind model gevonden; gebruik train_model.bat",
                            "source": "openfootball/football.json (CC0)"
                        })
                    return self.reply(200, {
                        "available": True,
                        "version": trained["version"],
                        "training_matches": trained["training_matches"],
                        "source": trained["source"],
                        "parameters": trained["parameters"],
                        "evaluation": trained["evaluation"],
                        "leagues": {
                            league: {
                                "teams": len(item["teams"]),
                                "trained_through": item["last_result_date"],
                                "training_matches": item["training_matches"]
                            }
                            for league, item in trained["leagues"].items()
                        },
                        "caution": (
                            "Model uit echte historische SCORES, geen schot-xG, "
                            "geen actuele bookmakerprijzen en geen bewijs van winst."
                        )
                    })
                if path == "/api/research/status":
                    return self.reply(200, research_hub.status())
                if path == "/api/research/opportunities":
                    return self.reply(200, research_hub.opportunities())
                assets = {
                    "/": ("index.html", "text/html; charset=utf-8"),
                    "/index.html": ("index.html", "text/html; charset=utf-8"),
                    "/style.css": ("style.css", "text/css; charset=utf-8"),
                    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                    "/live.js": ("live.js", "text/javascript; charset=utf-8"),
                    "/research.js": ("research.js", "text/javascript; charset=utf-8"),
                    "/trained.js": ("trained.js", "text/javascript; charset=utf-8"),
                    "/trained.js": ("trained.js", "text/javascript; charset=utf-8"),
                }
                if path in assets:
                    name, mimetype = assets[path]
                    data = (ROOT / name).read_bytes()
                    self._headers(200, mimetype, len(data))
                    return self.wfile.write(data)
                return self.reply(404, {"error": "Niet gevonden"})
            except (ValidationError, InvalidLiveRequest, BridgeError, TrainingError) as exc:
                return self.reply(400, {"error": str(exc)})
            except LiveDataUnavailable as exc:
                return self.reply(502, {"error": str(exc)})
            except Exception:
                LOG.exception("Unhandled GET failure")
                return self.reply(500, {"error": "Interne serverfout"})

        def do_POST(self):
            try:
                self._check_host()
                path = self._path()
                payload = self._read_json()
                if path == "/api/matches":
                    return self.reply(201, {"match": store.add_match(payload)})
                if path == "/api/slips/quote":
                    return self.reply(200, preview(store, payload))
                if path == "/api/slips":
                    # Always reprice and validate against the database inside the transaction.
                    result = store.create_slip(payload.get("legs"), payload.get("stake"))
                    return self.reply(201, {"slip": result})
                if path == "/api/demo":
                    return self.reply(201, store.seed_demo())
                if path == "/api/trained/predict":
                    if trained is None:
                        return self.reply(503, {
                            "error": "Basismodel ontbreekt; train opnieuw met train_model.bat"
                        })
                    provider = payload.get("provider")
                    league = payload.get("league")
                    if provider is not None:
                        if provider not in PROVIDER_LEAGUES:
                            raise TrainingError("Onbekende model-databron")
                        league = PROVIDER_LEAGUES[provider].get(league)
                    if not isinstance(league, str):
                        raise TrainingError("Geen getrainde competitie beschikbaar")
                    result = predict_trained(
                        trained, league, payload.get("home_team"), payload.get("away_team")
                    )
                    return self.reply(200, result)
                if path == "/api/research/imports/scan":
                    return self.reply(200, research_hub.scan_inbox())
                match = re.fullmatch(r"/api/matches/([1-9][0-9]*)/settle", path)
                if match:
                    result = store.settle_match(
                        int(match.group(1)), payload.get("home_goals"), payload.get("away_goals")
                    )
                    return self.reply(200, {"match": result})
                return self.reply(404, {"error": "Niet gevonden"})
            except (ValidationError, BridgeError, TrainingError) as exc:
                return self.reply(400, {"error": str(exc)})
            except (TypeError, ValueError) as exc:
                return self.reply(400, {"error": "Ongeldige aanvraag"})
            except Exception:
                LOG.exception("Unhandled POST failure")
                return self.reply(500, {"error": "Interne serverfout"})

        def do_OPTIONS(self):
            return self.reply(405, {"error": "CORS is uitgeschakeld"})

        def log_message(self, fmt, *args):
            LOG.info("%s - %s", self.client_address[0], fmt % args)

    return Handler


def main():
    parser = argparse.ArgumentParser(description="SupahBetting lokaal onderzoeksdashboard")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", type=Path, default=Path(".supahbetting") / "data.sqlite3")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Poort moet tussen 1 en 65535 zijn")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    store = Store(args.db)
    config_path = args.db.parent / "providers.json"
    try:
        created_config = make_local_config(config_path)
    except OSError:
        parser.error(
            "Kan lokaal providers.json niet maken. Controleer schrijfrechten "
            "in de datamap."
        )
    if created_config:
        print(
            "Nieuw lokaal API-bestand: " + str(config_path.resolve()) +
            "\nGebruik bewerk_api_config.bat om de football-data API-sleutel in te vullen."
        )
    # Keep one config location even when --db points to another data folder.
    provider_hub = ProviderHub(
        football_data=FootballData(config_path=config_path)
    )
    research_hub = ResearchStore(args.db)
    try:
        scan_result = research_hub.scan_inbox()
        print("Fork-export inbox: " + str(research_hub.inbox.resolve()))
        print(
            "Ingelezen bestanden bij opstarten: " +
            str(scan_result["files_imported"]) +
            ". Gebruik de knop 'Bronbestanden inlezen' om later opnieuw te scannen."
        )
    except OSError:
        LOG.warning("Kan lokale bronbestanden nu niet inlezen; dashboard start door")
    server = ThreadingHTTPServer(
        ("127.0.0.1", args.port), make_handler(
            store, provider_hub=provider_hub, research_hub=research_hub
        )
    )
    server.daemon_threads = True
    print(f"SupahBetting v0.7: http://127.0.0.1:{args.port}", flush=True)
    print("Alleen lokaal, fictieve inzetten. Druk Ctrl+C om te stoppen.", flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
