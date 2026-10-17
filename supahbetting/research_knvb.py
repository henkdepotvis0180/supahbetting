"""Eredivisie fixtures from the official KNVB programme.

TheSportsDB is NOT the sole Dutch fixture source anymore.  Use one bounded
official KNVB page read per refresh and, if it cannot be verified, a clearly
dated manually checked official fixture excerpt for up to seven days.
Never manufacture scores, kickoffs or claim an old snapshot is live data.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
import hashlib
import json
import logging
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

OFFICIAL_URL = "https://www.knvb.nl/competities/eredivisie/programma"
BACKUP = Path(__file__).parent / "data" / "knvb_eredivisie_2026_27.json"
MAX_HTML_BYTES = 1_800_000
LOG = logging.getLogger("supahbetting.knvb")
WEEKDAYS = ("maandag", "dinsdag", "woensdag", "donderdag", "vrijdag",
            "zaterdag", "zondag")
MONTHS = ("januari", "februari", "maart", "april", "mei", "juni",
          "juli", "augustus", "september", "oktober", "november", "december")
CLUBS = (
    "ADO Den Haag", "PSV", "Telstar", "Feyenoord", "Sparta Rotterdam",
    "Willem II", "PEC Zwolle", "Go Ahead Eagles", "SC Cambuur", "AZ",
    "FC Groningen", "Ajax", "N.E.C.", "NEC", "Fortuna Sittard",
    "FC Twente", "FC Utrecht", "sc Heerenveen", "SC Heerenveen",
    "Excelsior", "Excelsior Rotterdam"
)
DAY_RE = re.compile(
    r"\b(?:" + "|".join(WEEKDAYS) + r")\s+([0-3]?\d)\s+("
    + "|".join(MONTHS) + r")\s+(20\d{2})\b", re.I
)
TEAM_RE = re.compile(
    r"(?<![\w])(?:" + "|".join(re.escape(s) for s in
                               sorted(CLUBS, key=len, reverse=True))
    + r")(?![\w])", re.I
)
TIME_RE = re.compile(r"(?<![\d])(?:[01]?\d|2[0-3]):[0-5]\d(?![\d])")


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.suppressed = 0
        self.words = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "svg", "noscript"):
            self.suppressed += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "svg", "noscript"):
            self.suppressed = max(0, self.suppressed - 1)

    def handle_data(self, value):
        if not self.suppressed and value.strip():
            self.words.append(" ".join(value.split()))


def _last_sunday(year, month):
    following = date(year + (month == 12), (month % 12) + 1, 1)
    end = following - timedelta(days=1)
    return end - timedelta(days=(end.weekday()+1) % 7)


def kickoff_utc(day_text, local_clock):
    """KNVB publishes Amsterdam local times; handle CET/CEST without tzdata.

    The usual professional fixtures don't start at the ambiguous switch hour;
    refuse such times instead of guessing.
    """
    day = date.fromisoformat(day_text)
    if not TIME_RE.fullmatch(local_clock):
        raise ValueError("KNVB aftraptijd ontbreekt")
    hour, minute = map(int, local_clock.split(":"))
    march = _last_sunday(day.year, 3)
    october = _last_sunday(day.year, 10)
    if (day in (march, october)) and hour in (2,):
        raise ValueError("Dubbelzinnig tijdstip tijdens zomer-/wintertijdwissel")
    summer = (march < day < october or (day == march and hour >= 3))
    zone_offset = timedelta(hours=2 if summer else 1)
    clock = datetime(day.year, day.month, day.day, hour, minute,
                     tzinfo=timezone(zone_offset))
    return clock.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_knvb_schedule(html, *, today, days=15):
    """Parse bounded KNVB-visible fixture blocks: date, club, time, club.

    Completely rejects non-Eredivisie teams and incomplete/unmatched time
    records; only returns future-dated fixtures within the requested window.
    """
    if not isinstance(html, str) or len(html) > MAX_HTML_BYTES:
        raise ValueError("KNVB antwoord heeft ongeldige omvang")
    parser = _VisibleText()
    parser.feed(html)
    visible = " ".join(parser.words)
    matches = list(DAY_RE.finditer(visible))
    results = []
    seen = set()
    for index, day_match in enumerate(matches):
        try:
            day = date(int(day_match.group(3)),
                       MONTHS.index(day_match.group(2).casefold())+1,
                       int(day_match.group(1)))
        except (ValueError, TypeError):
            continue
        if day < today or day > today + timedelta(days=days):
            continue
        end = matches[index+1].start() if index+1<len(matches) else len(visible)
        section = visible[day_match.end():end]
        # In every fixture, only a known club/time/known club sequence is valid.
        found = [(m.start(), m.end(), "team", m.group()) for m in TEAM_RE.finditer(section)]
        found += [(m.start(), m.end(), "time", m.group()) for m in TIME_RE.finditer(section)]
        found.sort()
        for j in range(len(found)-2):
            first, clock, last = found[j:j+3]
            if (first[2], clock[2], last[2]) != ("team", "time", "team"):
                continue
            # The published schedule may contain a logo or 'Image' text.
            if clock[0]-first[1]>55 or last[0]-clock[1]>55:
                continue
            home, away = first[3], last[3]
            if home.casefold()==away.casefold():
                continue
            identifier=(day.isoformat(),clock[3],home.casefold(),away.casefold())
            if identifier in seen:
                continue
            seen.add(identifier)
            results.append({"day":day.isoformat(),"local_time":clock[3],
                            "home":home,"away":away})
    return results


def _verified_events(fixtures, *, now, confirmed, method):
    """Convert official schedule to the same normalized provider shape."""
    from .research_upcoming import _utc, WINDOW_DAYS
    events=[]
    for item in fixtures:
        try:
            iso=kickoff_utc(item["day"],item["local_time"])
            start=_utc(iso)
            if (start is None or start <= now or
                    start > now + timedelta(days=WINDOW_DAYS)):
                continue
            home, away=item["home"],item["away"]
            if home not in CLUBS or away not in CLUBS or home==away:
                continue
            # Internal stable ID derived ONLY from the actual published fixture,
            # NOT advertised as an official KNVB provider event identifier.
            fingerprint=hashlib.sha256(
                json.dumps([item["day"],home,away],ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            identifier=str(int(fingerprint[:13],16))
            events.append({
                "provider":"knvb","source_id":identifier,
                "league":"nl.1","league_name":"Eredivisie",
                "home":home,"away":away,"date":item["day"],
                "kickoff":iso,"source_confirmed":confirmed,
                "source_method":method,"status":"scheduled",
                "hg":None,"ag":None,"source_url":OFFICIAL_URL,
            })
        except (ValueError, KeyError, TypeError):
            continue
    return events


def _load_snapshot(*, now):
    try:
        payload=json.loads(BACKUP.read_text(encoding="utf-8"))
        if (payload["source_url"] != OFFICIAL_URL or
                payload["league"] != "nl.1" or
                payload["schema_version"] != 1):
            raise ValueError("KNVB snapshot met onjuiste herkomst")
        asof=date.fromisoformat(payload["snapshot_verified_on"])
        age=(now.date()-asof).days
        # A dated official document may be amended; never treat a week-old
        # extract as a recently checked current schedule.
        confirmed=0<=age<=7
        rows=_verified_events(payload["fixtures"],now=now,
                              confirmed=confirmed,method="dated_official_snapshot")
        return rows,asof,confirmed
    except (OSError, ValueError, KeyError, TypeError):
        return [],None,False


def _download_official(*,timeout=12):
    request=Request(OFFICIAL_URL,headers={
        "User-Agent":"SupahBettingResearch/0.13 (low-rate local KNVB schedule check)",
        "Accept":"text/html",
    })
    with urlopen(request,timeout=timeout) as res:
        if res.status!=200:
            raise ValueError("KNVB HTTP "+str(res.status))
        raw=res.read(MAX_HTML_BYTES+1)
        if len(raw)>MAX_HTML_BYTES:
            raise ValueError("KNVB pagina groter dan bronlimiet")
        return raw.decode("utf-8",errors="replace")


def get_eredivisie(*,now=None,fetch_html=None,network=True):
    """Return (fixtures, warnings), fail open to dated official snapshot.

    A failed live download must NOT wipe genuine KNVB fixtures from the local
    site. Never fabricate data or treat stale snapshots as fresh.
    """
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Eis tijdzone bij monitorcheck")
    results,snapshot_date,snapshot_fresh=_load_snapshot(now=now)
    warnings=[]
    if not network:
        if not results:
            warnings.append("KNVB: geen actuele officiële agendagegevens beschikbaar")
        elif not all(row["source_confirmed"] for row in results):
            warnings.append("KNVB: oudere agenda-snapshot, herbevestiging ontbreekt")
        return results,warnings
    try:
        markup=(fetch_html or _download_official)()
        future=parse_knvb_schedule(markup,today=now.date(),days=15)
        actual=_verified_events(future,now=now,confirmed=True,method="official_page_live")
        if len(actual)<2:
            raise ValueError("KNVB: minder dan twee herkenbare toekomstige duels")
        return actual,warnings
    except (HTTPError, URLError, TimeoutError, OSError,
            UnicodeError, ValueError, TypeError) as exc:
        warnings.append("KNVB online controle niet bevestigd ("+
                        type(exc).__name__+"); gecontroleerde agenda-snapshot"+
                        (" met geldige controletermijn" if results and
                         all(row["source_confirmed"] for row in results)
                         else " is verouderd of ontbreekt"))
        return results,warnings
