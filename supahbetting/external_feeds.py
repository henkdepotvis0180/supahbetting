"""Additional *documented* football data providers for SupahBetting.

TheSportsDB free v1: extremely limited fixtures/results, NOT live scores.
football-data.org free plan: delayed results and schedules; requires a token.

No provider returns betting odds or stream URLs here. Upstream requests use a
fixed hostname, known routes, bounded replies, no redirects and a shared TTL
cache. All external payloads are untrusted and normalized before returning.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from datetime import date, datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from .live_scores import (
    LiveDataUnavailable, InvalidLiveRequest, LiveScores, _NoRedirects,
    _clean, _identifier, _number, approved_broadcast,
)
from .provider_config import (
    DEFAULT_CONFIG, ProviderConfigError, get_api_key,
)

LOG = logging.getLogger("supahbetting.providers")


class ProviderHTTPFailure(LiveDataUnavailable):
    """HTTP status only; never include credentials or raw remote error bodies."""

    def __init__(self, provider, status_code):
        self.provider = provider
        self.status_code = int(status_code)
        super().__init__(provider + " gaf HTTP " + str(self.status_code))

# Shared process-wide HTTP-429 circuit breaker. No response bodies or secrets
# are persisted. A temporarily blocked provider never gets request storms.
_PROVIDER_COOLDOWN = {}
_PROVIDER_COOLDOWN_LOCK = threading.Lock()


def provider_cooldown_seconds(provider):
    with _PROVIDER_COOLDOWN_LOCK:
        state = _PROVIDER_COOLDOWN.get(provider)
        return max(0, int(state[0] - time.monotonic())) if state else 0


def provider_cooldown_status(provider):
    with _PROVIDER_COOLDOWN_LOCK:
        state = _PROVIDER_COOLDOWN.get(provider)
        return state[1] if state and state[0] > time.monotonic() else None


def _suspend_provider(provider, http_error):
    # Observe numeric Retry-After headers only; bounded to an hour.
    headers = getattr(http_error, "headers", None)
    raw = headers.get("Retry-After") if headers else None
    try:
        retry_after = max(0, min(3600, int(raw)))
    except (TypeError, ValueError):
        retry_after = 0
    # 429: back off at least 5min, 401/403: no rapid unauthorized retries.
    base = 300 if http_error.code == 429 else 1800 if http_error.code in (401, 403) else 0
    if base:
        with _PROVIDER_COOLDOWN_LOCK:
            existing = _PROVIDER_COOLDOWN.get(provider)
            until = time.monotonic() + max(base, retry_after)
            if existing is None or until >= existing[0]:
                _PROVIDER_COOLDOWN[provider] = (until, http_error.code)


MAX_RESPONSE = 1_100_000

SPORTSDB_LEAGUES = {
    "4337": "Eredivisie",
    "4641": "Eerste Divisie",
    "4338": "Belgische Pro League",
    "4328": "Premier League",
    "4329": "Championship",
    "4330": "Scottish Premiership",
    "4331": "Bundesliga",
    "4332": "Serie A",
    "4334": "Ligue 1",
    "4335": "La Liga",
    "4346": "MLS",
    "4351": "Braziliaanse Série A",
    "4621": "Oostenrijkse Bundesliga",
}
FOOTBALL_DATA_LEAGUES = {
    "DED": "Eredivisie",
    "PL": "Premier League",
    "PD": "La Liga",
    "BL1": "Bundesliga",
    "SA": "Serie A",
    "FL1": "Ligue 1",
    "PPL": "Primeira Liga",
    "CL": "Champions League",
    "ELC": "Championship",
    "BSA": "Braziliaanse Série A",
    "WC": "WK",
    "EC": "EK",
}
SPORTSDB_SOURCE = {
    "name": "TheSportsDB (gratis v1 — beperkte uitslagen)",
    "url": "https://www.thesportsdb.com/",
    "license": "Controleer de voorwaarden van TheSportsDB",
    "license_url": "https://www.thesportsdb.com/docs/api",
}
FOOTBALL_DATA_SOURCE = {
    "name": "football-data.org (vertraagde scores)",
    "url": "https://www.football-data.org/",
    "license": "API-gebruiksvoorwaarden football-data.org",
    "license_url": "https://www.football-data.org/pricing",
}


def fetch_bounded_json(path, provider, token=""):
    """Fetch from fixed provider base URLs; token goes into a header, never URL."""
    if provider == "sportsdb":
        valid = re.fullmatch(
            r"/api/v1/json/123/(?:(?:eventsnextleague|eventspastleague)\.php\?id=[0-9]{4,7}"
            r"|eventsday\.php\?d=[0-9]{4}-[0-9]{2}-[0-9]{2}&l=[0-9]{4,7}"
            r"|lookupevent\.php\?id=[0-9]{1,12})", path
        )
        host = "https://www.thesportsdb.com"
        headers = {"Accept": "application/json", "User-Agent": "SupahBetting/0.5 (local research)"}
    elif provider == "football-data":
        valid = re.fullmatch(
            r"/v4/(?:matches/[0-9]{1,12}"
            r"|competitions/[A-Z0-9]{2,4}/matches"
            r"\?(?:dateFrom=[0-9]{4}-[0-9]{2}-[0-9]{2}&dateTo=[0-9]{4}-[0-9]{2}-[0-9]{2}"
            r"|season=20[0-9]{2}))",
            path,
        )
        host = "https://api.football-data.org"
        if not token:
            raise LiveDataUnavailable("FOOTBALL_DATA_API_KEY ontbreekt: gratis registratie vereist")
        headers = {
            "Accept": "application/json",
            "User-Agent": "SupahBetting/0.5 (local research)",
            "X-Auth-Token": token,
        }
    else:
        raise InvalidLiveRequest("Databron onbekend")
    if not valid:
        raise InvalidLiveRequest("Databronroute niet toegestaan")
    remaining = provider_cooldown_seconds(provider)
    if remaining:
        # A local cooldown has the same status as the throttling event that
        # caused it. It is not an additional HTTP call to the provider.
        raise ProviderHTTPFailure(provider, provider_cooldown_status(provider) or 429)
    request = Request(host + path, headers=headers, method="GET")
    try:
        with build_opener(_NoRedirects()).open(request, timeout=8) as response:
            if response.status != 200:
                raise LiveDataUnavailable("Databron gaf geen geldige status")
            raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise LiveDataUnavailable("Antwoord van databron overschrijdt de limiet")
            return json.loads(raw.decode("utf-8-sig"))
    except HTTPError as exc:
        _suspend_provider(provider, exc)
        LOG.warning("Request naar %s geweigerd: HTTP %d (route %s)",
                    provider, exc.code, path)
        raise ProviderHTTPFailure(provider, exc.code) from exc
    except (URLError, TimeoutError, OSError, UnicodeError, ValueError) as exc:
        LOG.warning("Request naar %s mislukt (route %s): %s",
                    provider, path, type(exc).__name__)
        raise LiveDataUnavailable(
            "Databron tijdelijk onbereikbaar; check netwerk, DNS of TLS"
        ) from exc


def parse_utc(value):
    if not isinstance(value, str) or not value:
        return ""
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is not None and stamp.utcoffset() is not None:
            return stamp.astimezone(timezone.utc).isoformat()
    except ValueError:
        pass
    return ""


def safe_team(value):
    if isinstance(value, dict):
        return _clean(value.get("name") or value.get("shortName"), 90)
    return _clean(value, 90)


def _goal_lineup(goal):
    scorer = goal.get("scorer")
    if isinstance(scorer, dict):
        player = _clean(scorer.get("name"), 90)
    else:
        player = ""
    score = goal.get("score") or {}
    if not isinstance(score, dict):
        score = {}
    kind = str(goal.get("type") or "").upper()
    return {
        "minute": _number(goal.get("minute")),
        "player": player or "Onbekende doelpuntenmaker",
        "is_penalty": kind == "PENALTY",
        "is_own_goal": kind == "OWN_GOAL",
        "score_home": _number(score.get("home")),
        "score_away": _number(score.get("away")),
        "type": "goal",
    }


def normalize_football_data(raw, league):
    if not isinstance(raw, dict):
        raise InvalidLiveRequest("Ongeldig wedstrijdrecord")
    identifier = _identifier(raw.get("id"))
    home = safe_team(raw.get("homeTeam"))
    away = safe_team(raw.get("awayTeam"))
    if not identifier or not home or not away:
        raise InvalidLiveRequest("Wedstrijdgegevens onvolledig")
    score = raw.get("score")
    if not isinstance(score, dict):
        score = {}
    final = score.get("fullTime")
    if not isinstance(final, dict):
        final = {}
    code = str(raw.get("status", "")).upper()
    if code == "FINISHED":
        status, label = "finished", "Afgelopen · kan vertraagd zijn"
    elif code in ("SCHEDULED", "TIMED"):
        status, label = "scheduled", "Gepland · kan vertraagd zijn"
    elif code in ("IN_PLAY", "PAUSED"):
        status, label = "unknown", "Volgens bron bezig · gegevens vertraagd"
    elif code in ("POSTPONED", "CANCELLED", "SUSPENDED", "AWARDED"):
        status, label = "unknown", "Status: " + _clean(code, 18)
    else:
        status, label = "unknown", "Status onbekend · gegevens vertraagd"
    raw_goals = raw.get("goals")
    if not isinstance(raw_goals, list):
        raw_goals = []
    timeline = sorted(
        [_goal_lineup(g) for g in raw_goals[:50] if isinstance(g, dict)],
        key=lambda g: (g["minute"] is None, g["minute"] or 0),
    )
    return {
        "id": identifier,
        "league": league,
        "league_name": FOOTBALL_DATA_LEAGUES[league],
        "home_team": home,
        "away_team": away,
        "kickoff": parse_utc(raw.get("utcDate")),
        "kickoff_source_local": "",
        "round": ("Speelronde " + str(raw["matchday"])) if raw.get("matchday") else "",
        "status": status,
        "status_label": label,
        "score_home": _number(final.get("home")),
        "score_away": _number(final.get("away")),
        "goals_count": len(timeline),
        "timeline": timeline,
        "source": FOOTBALL_DATA_SOURCE,
        "provider": "football-data",
        "feed_kind": "delayed",
    }


def normalize_sportsdb(raw, league):
    if not isinstance(raw, dict):
        raise InvalidLiveRequest("Ongeldig wedstrijdrecord")
    identifier = _identifier(raw.get("idEvent"))
    home = _clean(raw.get("strHomeTeam"), 90)
    away = _clean(raw.get("strAwayTeam"), 90)
    if not identifier or not home or not away:
        raise InvalidLiveRequest("Wedstrijdgegevens onvolledig")
    reported_league = _identifier(raw.get("idLeague"))
    if reported_league and str(reported_league) != league:
        raise InvalidLiveRequest("Wedstrijd behoort tot een andere competitie")
    text = _clean(raw.get("strStatus"), 40).lower()
    if text in ("match finished", "finished", "ft", "full time", "after extra time", "aet"):
        status, label = "finished", "Eindstand (gratis bron)"
    elif text in ("not started", "scheduled", "ns"):
        status, label = "scheduled", "Gepland · geen livescore"
    else:
        status, label = "unknown", "Gratis wedstrijdgegevens · niet live"
    stamp = parse_utc(raw.get("strTimestamp"))
    # TheSportsDB v1 returns UTC soccer event timestamps without a "Z" suffix
    # in some responses. Its other sports can use local time, so never apply
    # this interpretation outside explicitly declared Soccer matches.
    if not stamp and _clean(raw.get("strSport"), 20).casefold() == "soccer":
        source_stamp = raw.get("strTimestamp")
        source_day = raw.get("dateEvent")
        if (isinstance(source_stamp, str)
                and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}", source_stamp)
                and source_day == source_stamp[:10]):
            try:
                stamp = (datetime.fromisoformat(source_stamp)
                         .replace(tzinfo=timezone.utc).isoformat())
            except ValueError:
                pass
    if not stamp:
        fallback = _clean(raw.get("dateEvent"), 12)
        clock = _clean(raw.get("strTime"), 12)
        fallback = (fallback + " " + clock).strip()
    else:
        fallback = ""
    return {
        "id": identifier,
        "league": league,
        "league_name": SPORTSDB_LEAGUES[league],
        "home_team": home,
        "away_team": away,
        "kickoff": stamp,
        "kickoff_source_local": fallback,
        "round": _clean(raw.get("intRound"), 12) and "Speelronde " + _clean(raw.get("intRound"), 12) or "",
        "status": status,
        "status_label": label,
        "score_home": _number(raw.get("intHomeScore")),
        "score_away": _number(raw.get("intAwayScore")),
        "goals_count": 0,
        "timeline": [],
        "source": SPORTSDB_SOURCE,
        "provider": "sportsdb",
        "feed_kind": "schedule_only",
    }


class SportsDB(LiveScores):
    """Free key 123, only 1 next/previous + up to 3 events/day; not live."""

    def __init__(self, fetcher=None, clock=None, broadcasts_path=None, today=None):
        super().__init__(
            fetcher=fetcher or (lambda path: fetch_bounded_json(path, "sportsdb")),
            clock=clock, broadcasts_path=broadcasts_path
        )
        self.today = today or (lambda: datetime.now(timezone.utc).date())

    def list_matches(self, league):
        if league not in SPORTSDB_LEAGUES:
            raise InvalidLiveRequest("Competitie niet beschikbaar bij TheSportsDB")
        current_day = self.today()
        paths = [
            ("/api/v1/json/123/eventsnextleague.php?id=" + league, "events"),
            ("/api/v1/json/123/eventspastleague.php?id=" + league, "events"),
        ]
        for shift in (-1, 0, 1):
            day = (current_day + timedelta(days=shift)).isoformat()
            paths.append((
                "/api/v1/json/123/eventsday.php?d=" + day + "&l=" + league,
                "events",
            ))
        by_id = {}
        errors = []
        timestamps = []
        for path, result_key in paths:
            try:
                raw, fetched, stale, error = self._cached(path, 600)
                if not isinstance(raw, dict):
                    raise LiveDataUnavailable("Onverwachte TheSportsDB-respons")
                events = raw.get(result_key) or []
                if not isinstance(events, list):
                    raise LiveDataUnavailable("Ongeldig wedstrijdformaat")
                for event in events[:25]:
                    try:
                        normalized = normalize_sportsdb(event, league)
                        by_id[normalized["id"]] = normalized
                    except InvalidLiveRequest:
                        LOG.info("Onvolledig sportevent overgeslagen")
                timestamps.append(fetched)
                if stale or error:
                    errors.append("Een TheSportsDB-resultaat is verouderd")
            except LiveDataUnavailable:
                errors.append("Niet alle gratis uitslagen beschikbaar")
        if not timestamps:
            raise LiveDataUnavailable("TheSportsDB is tijdelijk onbereikbaar")
        return {
            "matches": sorted(
                by_id.values(), key=lambda x: (x["kickoff"] or "9999", x["id"])
            ),
            "league": league,
            "fetched_at": max(x for x in timestamps if x),
            "stale": bool(errors),
            "warnings": list(dict.fromkeys(errors)),
            "coverage_note": (
                "TheSportsDB gratis: maximaal één volgende, één vorige en "
                "hooguit drie wedstrijden per dag (gisteren/vandaag/morgen). GEEN live scores of doelpuntenfeed."
            ),
            "refresh_seconds": 600,
            "source": SPORTSDB_SOURCE,
            "provider": "sportsdb",
            "feed_kind": "schedule_only",
        }

    def match_detail(self, match_id, league):
        if league not in SPORTSDB_LEAGUES:
            raise InvalidLiveRequest("Competitie niet beschikbaar")
        if isinstance(match_id, bool) or not isinstance(match_id, int) or not 1 <= match_id <= 9999999999:
            raise InvalidLiveRequest("Ongeldig wedstrijdnummer")
        raw, fetched, stale, error = self._cached(
            "/api/v1/json/123/lookupevent.php?id=" + str(match_id), 600
        )
        if not isinstance(raw, dict) or not isinstance(raw.get("events"), list) or not raw["events"]:
            raise LiveDataUnavailable("Geen wedstrijddetails beschikbaar via gratis bron")
        result = normalize_sportsdb(raw["events"][0], league)
        if result["id"] != match_id:
            raise InvalidLiveRequest("Bron gaf verkeerd wedstrijdnummer terug")
        result.update({
            "fetched_at": fetched, "stale": stale,
            "warning": error, "refresh_seconds": 600,
            "video_embed_url": approved_broadcast(self._broadcasts, "tsdb-" + league, match_id),
            "timeline_note": "TheSportsDB gratis v1 levert geen doelpuntenfeed; alleen beperkt speelschema/uitslagen.",
        })
        result["video_note"] = (
            "Door gebruiker handmatig gekoppelde officiële YouTube-embed (toestemming controleren)."
            if result["video_embed_url"] else "Geen geverifieerde officiële openbare video beschikbaar."
        )
        return result


class FootballData(LiveScores):
    """API token stays server-side; free scores are delayed and capped at 10/min."""

    def __init__(
        self, token=None, fetcher=None, clock=None, broadcasts_path=None,
        today=None, config_path=DEFAULT_CONFIG,
    ):
        # Explicit token injection is only used for tests/integrations.
        # In production, read the local JSON first; legacy env is a fallback.
        self.config_error = None
        if token is not None:
            self.token = token
        else:
            try:
                self.token = get_api_key(
                    "football-data",
                    config_path=config_path,
                    env_var="FOOTBALL_DATA_API_KEY",
                )
            except ProviderConfigError as exc:
                # Keep the rest of the dashboard working if JSON is malformed.
                self.config_error = str(exc)
                self.token = ""
        super().__init__(
            fetcher=fetcher or (lambda path: fetch_bounded_json(path, "football-data", self.token)),
            clock=clock, broadcasts_path=broadcasts_path,
        )
        self.today = today or (lambda: datetime.now(timezone.utc).date())

    @property
    def enabled(self):
        return bool(self.token)

    def _check(self, league):
        if league not in FOOTBALL_DATA_LEAGUES:
            raise InvalidLiveRequest("Competitie niet beschikbaar bij football-data.org")
        if self.config_error:
            raise LiveDataUnavailable(self.config_error)
        if not self.enabled:
            raise LiveDataUnavailable(
                "football-data.org heeft een API-sleutel nodig. Open "
                ".supahbetting/providers.json met bewerk_api_config.bat "
                "en vul providers > football-data > api_key in; herstart daarna. "
                "(Oude FOOTBALL_DATA_API_KEY-omgevingsvariabele werkt ook.)"
            )

    def list_matches(self, league):
        self._check(league)
        today = self.today()
        from_date = (today - timedelta(days=3)).isoformat()
        to_date = (today + timedelta(days=15)).isoformat()
        path = (
            "/v4/competitions/" + league +
            "/matches?dateFrom=" + from_date + "&dateTo=" + to_date
        )
        raw, fetched, stale, error = self._cached(path, 600)
        if not isinstance(raw, dict) or not isinstance(raw.get("matches"), list):
            raise LiveDataUnavailable("football-data.org gaf een onverwacht antwoord")
        matches = []
        for record in raw["matches"][:100]:
            try:
                matches.append(normalize_football_data(record, league))
            except InvalidLiveRequest:
                LOG.info("Onvolledig voetbalrecord overgeslagen")
        return {
            "matches": sorted(matches, key=lambda x: (x["kickoff"] or "9999", x["id"])),
            "league": league,
            "fetched_at": fetched, "stale": stale,
            "warnings": [error] if error else [],
            "coverage_note": (
                "football-data.org gratis: VERTRAAGDE scores, geen echte live feed; "
                "toegang en competities afhankelijk van API-abonnement."
            ),
            "refresh_seconds": 600,
            "source": FOOTBALL_DATA_SOURCE,
            "provider": "football-data",
            "feed_kind": "delayed",
        }

    def match_detail(self, match_id, league):
        self._check(league)
        if isinstance(match_id, bool) or not isinstance(match_id, int) or not 1 <= match_id <= 9999999999:
            raise InvalidLiveRequest("Ongeldig wedstrijdnummer")
        raw, fetched, stale, error = self._cached(
            "/v4/matches/" + str(match_id), 600
        )
        if not isinstance(raw, dict):
            raise LiveDataUnavailable("Onverwachte wedstrijddetails")
        comp = raw.get("competition")
        if isinstance(comp, dict) and comp.get("code") not in (None, league):
            raise InvalidLiveRequest("Wedstrijd hoort bij een andere competitie")
        result = normalize_football_data(raw, league)
        if result["id"] != match_id:
            raise InvalidLiveRequest("Bron gaf ander wedstrijdnummer terug")
        result.update({
            "fetched_at": fetched, "stale": stale,
            "warning": error, "refresh_seconds": 600,
            "video_embed_url": approved_broadcast(self._broadcasts, "fd-" + league, match_id),
            "timeline_note": (
                "Doelpunten staan alleen in het detail wanneer jouw football-data.org "
                "abonnement deze uitgebreide velden beschikbaar stelt."
            ) if result["timeline"] else (
                "Geen doelpuntenfeed in dit abonnement; gratis scores zijn vertraagd."
            ),
        })
        result["video_note"] = (
            "Door gebruiker handmatig gekoppelde officiële YouTube-embed (toestemming controleren)."
            if result["video_embed_url"] else "Geen geverifieerde officiële openbare video beschikbaar."
        )
        return result


class ProviderHub:
    """Access a catalog of data sources with separate provider identifiers."""

    def __init__(self, openliga=None, sportsdb=None, football_data=None):
        self.openliga = openliga or LiveScores()
        self.sportsdb = sportsdb or SportsDB()
        self.football_data = football_data or FootballData()

    def catalog(self):
        from .live_scores import LEAGUES as OPENLEAGUES
        return {
            "providers": [
                {
                    "id": "openliga", "label": "OpenLigaDB · doelpuntenfeed",
                    "enabled": True, "kind": "scores",
                    "note": "Gratis communitystanden en doelpunten. Mogelijke vertraging.",
                    "leagues": [{"code": k, "name": v} for k, v in OPENLEAGUES.items()],
                },
                {
                    "id": "sportsdb", "label": "TheSportsDB · gratis speelschema",
                    "enabled": True, "kind": "schedule_only",
                    "note": "Zeer beperkte wedstrijden, geen echte livescore, geen API-sleutel nodig.",
                    "leagues": [{"code": k, "name": v} for k, v in SPORTSDB_LEAGUES.items()],
                },
                {
                    "id": "football-data", "label": "football-data.org · vertraagde scores",
                    "enabled": self.football_data.enabled, "kind": "delayed",
                    "note": (
                        self.football_data.config_error
                        if self.football_data.config_error else
                        "API-sleutel beschikbaar; gratis scores blijven vertraagd."
                        if self.football_data.enabled else
                        "Vul je token in .supahbetting/providers.json in via "
                        "bewerk_api_config.bat (dan herstarten). Gratis scores vertraagd."
                    ),
                    "leagues": [{"code": k, "name": v} for k, v in FOOTBALL_DATA_LEAGUES.items()],
                },
            ]
        }

    def _select(self, name):
        if name == "openliga":
            return self.openliga
        if name == "sportsdb":
            return self.sportsdb
        if name == "football-data":
            return self.football_data
        raise InvalidLiveRequest("Databron niet ondersteund")

    def list_matches(self, provider, league):
        if provider == "openliga" and league == "all":
            from .live_scores import ATTRIBUTION, LEAGUES
            results, warnings, stamps = [], [], []
            for code in LEAGUES:
                try:
                    data = self.openliga.list_matches(code)
                    results.extend(data["matches"])
                    stamps.append(data["fetched_at"])
                    if data.get("stale") or data.get("warning"):
                        warnings.append(LEAGUES[code] + ": verouderde bron")
                except LiveDataUnavailable:
                    warnings.append(LEAGUES[code] + ": tijdelijk onbereikbaar")
            if not stamps:
                raise LiveDataUnavailable("OpenLigaDB is tijdelijk niet bereikbaar")
            return {
                "matches": sorted(results, key=lambda m: (m["kickoff"] or "9999", m["id"])),
                "league": "all",
                "fetched_at": min(stamps),
                "stale": bool(warnings), "warnings": warnings,
                "refresh_seconds": 90, "source": ATTRIBUTION,
                "provider": "openliga", "feed_kind": "scores",
                "coverage_note": "OpenLigaDB communitydoelpuntenfeed; kan vertraagd zijn.",
            }
        if league == "all":
            raise InvalidLiveRequest(
                "Kies een competitie voor deze bron om het gratis API-limiet te respecteren"
            )
        feed = self._select(provider)
        result = feed.list_matches(league)
        result.setdefault("warnings", [result["warning"]] if result.get("warning") else [])
        result.setdefault("coverage_note", "OpenLigaDB communitydoelpuntenfeed.")
        result.setdefault("provider", provider)
        result.setdefault("feed_kind", "scores")
        return result

    def match_detail(self, provider, match_id, league):
        if league == "all":
            raise InvalidLiveRequest("Kies een competitie bij wedstrijddetails")
        feed = self._select(provider)
        result = feed.match_detail(match_id, league)
        result.setdefault("provider", provider)
        result.setdefault("feed_kind", "scores")
        return result
