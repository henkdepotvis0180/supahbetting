"""Free community-maintained football scores from OpenLigaDB.

ODbL source attribution: https://www.openligadb.de/lizenz
This is a scores/goals timeline provider, not a video/odds/prediction provider.
No credential, open redirect, scraper or user-selected remote endpoint.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.parse import urlsplit

LOG = logging.getLogger("supahbetting.live")
LEAGUES = {
    "bl1": "Bundesliga",
    "bl2": "2. Bundesliga",
    "bl3": "3. Liga",
    "ucl": "Champions League",
    "dfb": "DFB-Pokal",
    "ffb1": "Frauen-Bundesliga",
    "la1": "La Liga (community)",
    "pl": "Premier League (community)",
}
BASE_URL = "https://api.openligadb.de"
ATTRIBUTION = {
    "name": "OpenLigaDB",
    "url": "https://www.openligadb.de/",
    "license": "ODbL 1.0",
    "license_url": "https://www.openligadb.de/lizenz",
}
USER_AGENT = "SupahBetting/0.4 (+https://github.com/henkdepotvis0180/supahbetting)"
YOUTUBE_EMBED = re.compile(r"^https://www\.youtube-nocookie\.com/embed/([A-Za-z0-9_-]{11})$")
BROADCAST_KEY = re.compile(r"^(" + "|".join(re.escape(slug) for slug in LEAGUES) + r"):([1-9][0-9]{0,9})$")

# Limit upstream bandwidth and avoid cascading failure on a slow/unavailable service.
MAX_UPSTREAM_BYTES = 850_000
LIST_TTL_SECONDS = 90
DETAIL_TTL_SECONDS = 45
RETRY_AFTER_ERROR_SECONDS = 120


class LiveDataUnavailable(Exception):
    pass


class InvalidLiveRequest(ValueError):
    pass


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise LiveDataUnavailable("De livebron heeft een onverwachte omleiding gestuurd")


def _request_json(path):
    # Never allow the user to supply the remote destination; no redirects.
    allowed_slug = "|".join(re.escape(slug) for slug in LEAGUES)
    if not re.fullmatch(r"/getmatchdata/(?:" + allowed_slug + r"|[1-9][0-9]{0,9})", path):
        raise InvalidLiveRequest("Ongeldige bronroute")
    req = Request(
        BASE_URL + path,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        method="GET",
    )
    opener = build_opener(_NoRedirects())
    try:
        with opener.open(req, timeout=7) as response:
            if response.status != 200:
                raise LiveDataUnavailable("Livebron geeft geen geldige status")
            content = response.read(MAX_UPSTREAM_BYTES + 1)
            if len(content) > MAX_UPSTREAM_BYTES:
                raise LiveDataUnavailable("Antwoord van livebron is te groot")
            data = json.loads(content.decode("utf-8-sig"))
            return data
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeError,
            json.JSONDecodeError) as exc:
        LOG.warning("OpenLigaDB request failed (%s): %s", path, exc)
        raise LiveDataUnavailable("Livebron tijdelijk niet bereikbaar") from exc


def _number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = int(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return number if 0 <= number <= 200 else None


def _identifier(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        identifier = int(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return identifier if 1 <= identifier <= 9999999999 else None


def _clean(value, max_length=100):
    if not isinstance(value, str):
        return ""
    return " ".join("".join(ch for ch in value if ch.isprintable()).split())[:max_length]


def _kickoff(raw):
    # OpenLigaDB's UTC field is preferred to its timezone-free local field.
    text = raw.get("matchDateTimeUTC")
    if not isinstance(text, str) or not text:
        return "", _clean(raw.get("matchDateTime"), 40)
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.isoformat(), ""
    except ValueError:
        return "", _clean(raw.get("matchDateTime"), 40)


def _get_league(raw, fallback=""):
    value = raw.get("leagueShortcut")
    if value in LEAGUES:
        return value
    return fallback if fallback in LEAGUES else ""


def _score(raw):
    results = raw.get("matchResults")
    if not isinstance(results, list):
        results = []
    is_finished = raw.get("matchIsFinished") is True
    # OpenLigaDB: type 2 = fulltime and type 1 = halftime;
    # never confuse halftime with final.
    typed = [
        record for record in results
        if isinstance(record, dict)
        and _number(record.get("pointsTeam1")) is not None
        and _number(record.get("pointsTeam2")) is not None
    ]
    if is_finished:
        final = next((x for x in typed if x.get("resultTypeID") == 2), None)
        if final:
            return (_number(final["pointsTeam1"]), _number(final["pointsTeam2"]))
    # The latest goal provides a better in-play score than a previous half-time result.
    goals = raw.get("goals") if isinstance(raw.get("goals"), list) else []
    for goal in reversed(goals):
        if isinstance(goal, dict):
            h, a = _number(goal.get("scoreTeam1")), _number(goal.get("scoreTeam2"))
            if h is not None and a is not None:
                return h, a
    halftime = next((x for x in typed if x.get("resultTypeID") == 1), None)
    if halftime:
        return _number(halftime["pointsTeam1"]), _number(halftime["pointsTeam2"])
    if is_finished and typed:
        best = max(typed, key=lambda x: _number(x.get("resultOrderID")) or 0)
        return _number(best["pointsTeam1"]), _number(best["pointsTeam2"])
    return None, None


def _status(raw, kickoff):
    if raw.get("matchIsFinished") is True:
        return "finished", "Afgelopen"
    if kickoff:
        try:
            delta = (datetime.now(timezone.utc) -
                     datetime.fromisoformat(kickoff).astimezone(timezone.utc)).total_seconds()
            if delta < -300:
                return "scheduled", "Gepland"
            if -300 <= delta <= 3 * 60 * 60:
                return "estimated_live", "Mogelijk bezig"
        except ValueError:
            pass
    return "unknown", "Status onbekend"


def normalize_match(raw, league=""):
    if not isinstance(raw, dict):
        raise InvalidLiveRequest("Ongeldig wedstrijdobject")
    identifier = _identifier(raw.get("matchID"))
    team1 = raw.get("team1") if isinstance(raw.get("team1"), dict) else {}
    team2 = raw.get("team2") if isinstance(raw.get("team2"), dict) else {}
    if identifier is None or identifier == 0:
        raise InvalidLiveRequest("Livebron leverde geen wedstrijd-ID")
    home = _clean(team1.get("teamName"), 110)
    away = _clean(team2.get("teamName"), 110)
    if not home or not away:
        raise InvalidLiveRequest("Livebron leverde geen teamnamen")
    kickoff, local_time = _kickoff(raw)
    status, status_label = _status(raw, kickoff)
    home_score, away_score = _score(raw)
    league_code = _get_league(raw, league)
    return {
        "id": identifier,
        "league": league_code,
        "league_name": LEAGUES.get(league_code, _clean(raw.get("leagueName"), 80)),
        "round": _clean((raw.get("group") or {}).get("groupName"), 55)
        if isinstance(raw.get("group"), dict) else "",
        "home_team": home,
        "away_team": away,
        "kickoff": kickoff,
        "kickoff_source_local": local_time,  # do not silently invent a timezone
        "score_home": home_score,
        "score_away": away_score,
        "status": status,
        "status_label": status_label,
        "goals_count": len(raw.get("goals")) if isinstance(raw.get("goals"), list) else 0,
        "source": ATTRIBUTION,
    }


def normalize_goal(raw):
    if not isinstance(raw, dict):
        return None
    minute = _number(raw.get("matchMinute"))
    getter = _clean(raw.get("goalGetterName"), 105) or "Onbekende doelpuntenmaker"
    h, a = _number(raw.get("scoreTeam1")), _number(raw.get("scoreTeam2"))
    return {
        "minute": minute,
        "player": getter,
        "is_penalty": raw.get("isPenalty") is True,
        "is_own_goal": raw.get("isOwnGoal") is True,
        "score_home": h,
        "score_away": a,
        "type": "goal",
    }


def normalize_detail(raw):
    item = normalize_match(raw)
    goals = raw.get("goals") if isinstance(raw.get("goals"), list) else []
    timeline = [goal for goal in (normalize_goal(g) for g in goals[:35]) if goal]
    timeline.sort(key=lambda g: (g["minute"] is None, g["minute"] or 0))
    item["timeline"] = timeline
    item["timeline_note"] = (
        "Doelpunten uit de openbare bron; geen volledige livecommentaar- of videostream."
        if timeline else
        "De bron heeft nog geen doelpuntengebeurtenissen voor deze wedstrijd."
    )
    item["video_embed_url"] = None
    return item


def approved_broadcast(config_path, league, match_id):
    """Opt-in: user-verified official embeddable YouTube video, never autodiscovered."""
    path = Path(config_path)
    if not path.is_file():
        return None
    try:
        if path.stat().st_size > 16_384:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        url = data.get(f"{league}:{match_id}")
        if isinstance(url, str) and YOUTUBE_EMBED.fullmatch(url):
            return url
    except (OSError, ValueError, TypeError):
        LOG.warning("Ongeldige officiële uitzendingen-configuratie; overgeslagen")
    return None


class LiveScores:
    """Process-local bounded cache prevents request storms and signals stale results."""

    def __init__(self, fetcher=None, clock=None, broadcasts_path=None):
        self._fetcher = fetcher or _request_json
        self._clock = clock or time.monotonic
        self._lock = threading.RLock()
        self._cache = {}
        self._broadcasts = broadcasts_path or (
            Path(".supahbetting") / "official_broadcasts.json"
        )

    def _cached(self, key, ttl):
        now = self._clock()
        with self._lock:
            cached = self._cache.get(key)
            if cached and now < cached["retry_at"]:
                if cached["payload"] is None:
                    raise LiveDataUnavailable("Livebron tijdelijk niet bereikbaar; probeer later opnieuw")
                return cached["payload"], cached["fetched_at"], True, cached["error"]
            if cached and now < cached["expires_at"]:
                return cached["payload"], cached["fetched_at"], False, None
            try:
                payload = self._fetcher(key)
                self._cache[key] = {
                    "payload": payload,
                    "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "expires_at": now + ttl,
                    "retry_at": 0,
                    "error": None,
                }
                # No indefinite process memory growth from random match IDs.
                if len(self._cache) > 160:
                    for old_key in list(self._cache)[:40]:
                        if old_key != key:
                            self._cache.pop(old_key, None)
                fresh = self._cache[key]
                return payload, fresh["fetched_at"], False, None
            except (LiveDataUnavailable, ValueError, TypeError) as exc:
                LOG.warning("Live scores refresh failed: %s", exc)
                old = cached if cached else {"payload": None, "fetched_at": None}
                code = getattr(exc, "status_code", None)
                holdoff = max(RETRY_AFTER_ERROR_SECONDS, 300 if code == 429 else 0)
                self._cache[key] = {
                    "payload": old["payload"],
                    "fetched_at": old["fetched_at"],
                    "expires_at": 0,
                    "retry_at": now + holdoff,
                    "error": "Bron tijdelijk niet bereikbaar",
                }
                if old["payload"] is None:
                    # Preserve the actionable 429/403 HTTP status for callers.
                    # A generic wrapper previously erased it and caused a
                    # second provider scan to repeat the failed request.
                    if isinstance(code, int):
                        raise
                    raise LiveDataUnavailable(
                        "Livebron tijdelijk niet bereikbaar; probeer later opnieuw"
                    ) from exc
                return old["payload"], old["fetched_at"], True, "Bron tijdelijk niet bereikbaar"

    def leagues(self):
        return [{"code": key, "name": name} for key, name in LEAGUES.items()]

    def list_matches(self, league):
        if league not in LEAGUES:
            raise InvalidLiveRequest("Deze competitie wordt nog niet ondersteund")
        data, fetched, stale, error = self._cached(f"/getmatchdata/{league}", LIST_TTL_SECONDS)
        if not isinstance(data, list):
            raise LiveDataUnavailable("Livebron gaf een onverwacht antwoord")
        matches = []
        for item in data[:80]:
            try:
                matches.append(normalize_match(item, league))
            except InvalidLiveRequest:
                LOG.warning("Ongeldige wedstrijd uit OpenLigaDB overgeslagen")
        matches.sort(key=lambda m: (m["kickoff"] or "9999", m["id"]))
        return {
            "league": league,
            "matches": matches,
            "fetched_at": fetched,
            "stale": stale,
            "warning": error,
            "refresh_seconds": LIST_TTL_SECONDS,
            "source": ATTRIBUTION,
        }

    def match_detail(self, match_id, league):
        if league not in LEAGUES:
            raise InvalidLiveRequest("Deze competitie wordt nog niet ondersteund")
        if isinstance(match_id, bool) or not isinstance(match_id, int) or not 1 <= match_id <= 9999999999:
            raise InvalidLiveRequest("Ongeldig wedstrijdnummer")
        data, fetched, stale, error = self._cached(
            f"/getmatchdata/{match_id}", DETAIL_TTL_SECONDS
        )
        if not isinstance(data, dict):
            raise LiveDataUnavailable("Livebron gaf een onverwacht antwoord")
        result = normalize_detail(data)
        if result["league"] and result["league"] != league:
            raise InvalidLiveRequest("Wedstrijd hoort niet bij de gekozen competitie")
        if not result["league"]:
            result["league"] = league
            result["league_name"] = LEAGUES[league]
        result["fetched_at"] = fetched
        result["stale"] = stale
        result["warning"] = error
        result["refresh_seconds"] = DETAIL_TTL_SECONDS
        result["video_embed_url"] = approved_broadcast(
            self._broadcasts, league, match_id
        )
        result["video_note"] = (
            "Handmatig geconfigureerde officiële YouTube-embed. "
            "Controleer zelf de uitzendrechten en toestemming van de aanbieder."
            if result["video_embed_url"] else
            "Geen bevestigde, openbaar insluitbare officiële video beschikbaar. "
            "De doelpuntenfeed blijft zichtbaar."
        )
        return result
