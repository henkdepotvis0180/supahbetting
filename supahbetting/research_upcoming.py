"""Offline-generated upcoming match predictions from separately licensed schedules.

Provider schedules stay LOCAL: football-data.org, TheSportsDB and OpenLigaDB
do NOT get republished into public CC0/GitHub files. Only known future kickoffs
are presented as confirmed; old OpenFootball fixtures are labelled provisional.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import time

from .external_feeds import (
    FootballData, ProviderHTTPFailure, fetch_bounded_json, normalize_sportsdb,
)
from .github_training_sync import SyncError
from .live_scores import LiveScores, LiveDataUnavailable
from .research_data import LOCAL, atomic_json
from .trained_model import (
    LEAGUES, PROVIDER_LEAGUES, TrainingError, load_pretrained, norm,
    predict_trained,
)

UPCOMING_FILE = LOCAL / "upcoming_predictions.json"
FORECAST_LOG = LOCAL / "provider_forecast_log.json"
FIXTURE_LOCK = LOCAL / "upcoming.lock"
RESEARCH_MODEL = LOCAL / "candidate_model.json"
PUBLISHED_MODEL = Path(__file__).parent / "models" / "research_v0.12.0_experimental.json"
AUGMENTED_MODEL = LOCAL / "augmented_model_local.json"
WINDOW_DAYS = 15
SOURCE_PRIORITY = {"football-data": 4, "openliga": 3, "knvb": 2,
                   "sportsdb": 1, "openfootball-archive": 0}
# Stable exact-name aliases for independent fixture providers. No fuzzy guesses.
TEAM_NAMES = {
    "nl.1": {
        "ajax": "AFC Ajax", "feyenoord": "Feyenoord Rotterdam",
        "psv eindhoven": "PSV", "az alkmaar": "AZ",
        "nec nijmegen": "NEC",
        "nec": "NEC", "n e c": "NEC",
        "twente": "FC Twente '65",
        "fc twente": "FC Twente '65",
        "utrecht": "FC Utrecht",
        "zwolle": "PEC Zwolle",
        "groningen": "FC Groningen",
        "den haag": "ADO Den Haag",
        "heracles": "Heracles Almelo",
        "cambuur": "SC Cambuur-Leeuwarden",
        "rkc": "RKC Waalwijk",
        "rkc waalwijk": "RKC Waalwijk",
        "heerenveen": "SC Heerenveen",
        "sparta": "Sparta Rotterdam",
        "roda": "Roda JC Kerkrade",
        "vvv venlo": "VVV-Venlo",
        "graafschap": "De Graafschap",
        "volendam": "FC Volendam",
        "almere city": "Almere City FC",
        "emmen": "FC Emmen",
        "nac": "NAC Breda",
        "az alkmaar": "AZ",
        "psv eindhoven": "PSV",
        "feyenoord": "Feyenoord Rotterdam",
        "excelsior": "SBV Excelsior",
        "ado": "ADO Den Haag", "excelsior": "SBV Excelsior",
        "heerenveen": "SC Heerenveen",
        "telstar": "Telstar 1963",
        "n e c": "NEC",
        "nec nijmegen": "NEC",
    },
    "be.1": {
        "club brugge": "Club Brugge KV",
        "anderlecht": "RSC Anderlecht", "antwerp": "Royal Antwerp FC",
        "royal antwerp": "Royal Antwerp FC",
        "gent": "KAA Gent", "genk": "KRC Genk",
        "standard liege": "Standard Liège",
        "union saint gilloise": "Union Saint-Gilloise",
        "charleroi": "Sporting Charleroi",
        "mechelen": "KV Mechelen", "westerlo": "KVC Westerlo",
    },
    "en.1": {"man city": "Manchester City FC", "man utd": "Manchester United FC",
             "spurs": "Tottenham Hotspur FC", "wolves": "Wolverhampton Wanderers FC",
             "west ham": "West Ham United FC", "brighton": "Brighton & Hove Albion FC"},
    "de.1": {"bayern munich": "FC Bayern München", "bayern": "FC Bayern München",
             "hoffenheim": "TSG 1899 Hoffenheim", "leverkusen": "Bayer 04 Leverkusen"},
    "es.1": {"barcelona": "FC Barcelona", "atletico madrid": "Club Atlético de Madrid",
             "real madrid": "Real Madrid CF", "espanyol": "RCD Espanyol de Barcelona"},
    "it.1": {"inter milan": "FC Internazionale Milano",
             "napoli": "SSC Napoli", "fiorentina": "ACF Fiorentina",
             "lazio": "SS Lazio"},
    "fr.1": {"psg": "Paris Saint-Germain FC",
             "paris saint germain": "Paris Saint-Germain FC",
             "marseille": "Olympique de Marseille",
             "lyon": "Olympique Lyonnais"},
}


def _utc(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo is not None else None
    except (ValueError, TypeError):
        return None


def _team_name(league, value):
    if not isinstance(value, str) or not 1 <= len(value) <= 120:
        raise ValueError("Teamnaam ontbreekt")
    return TEAM_NAMES.get(league, {}).get(norm(value), value.strip())


def _normalize(event, provider, league, now, window_days=WINDOW_DAYS):
    """Use only provider-declared status and kick-off time; no guessed dates."""
    if not isinstance(event, dict) or league not in LEAGUES:
        return None
    if event.get("status") not in ("scheduled", "finished"):
        return None
    home, away = event.get("home_team"), event.get("away_team")
    if not all(isinstance(x, str) and 1 <= len(x.strip()) <= 120 for x in (home, away)):
        return None
    if norm(home) == norm(away):
        return None
    kickoff = _utc(event.get("kickoff"))
    if kickoff is None:
        # No reliable time means today's games cannot be classified as pre-match.
        # Next-day games without a timestamp may be retained as date-only.
        fallback = event.get("kickoff_source_local")
        if not isinstance(fallback, str) or len(fallback) < 10:
            return None
        try:
            scheduled_day = date.fromisoformat(fallback[:10])
        except ValueError:
            return None
        if scheduled_day <= now.date():
            return None
        date_value = scheduled_day.isoformat()
        kickoff_iso = None
    else:
        date_value = kickoff.date().isoformat()
        kickoff_iso = kickoff.isoformat(timespec="seconds")
    if event["status"] == "scheduled":
        if kickoff is not None and kickoff <= now:
            return None
        if (date.fromisoformat(date_value) - now.date()).days > window_days:
            return None
    else:
        if kickoff is None or kickoff > now or kickoff < now - timedelta(days=4):
            return None
        if type(event.get("score_home")) is not int or type(event.get("score_away")) is not int:
            return None
        if not (0 <= event["score_home"] <= 20 and 0 <= event["score_away"] <= 20):
            return None
    source_id = event.get("id")
    if type(source_id) is not int and not (isinstance(source_id, str) and source_id.isdigit()):
        return None
    return {
        "provider": provider, "source_id": str(source_id), "league": league,
        "league_name": LEAGUES[league],
        "home": home.strip(), "away": away.strip(),
        "date": date_value, "kickoff": kickoff_iso,
        "source_confirmed": True,
        "status": event["status"],
        "hg": event.get("score_home") if event["status"] == "finished" else None,
        "ag": event.get("score_away") if event["status"] == "finished" else None,
        "source_url": {
            "football-data": "https://www.football-data.org/",
            "sportsdb": "https://www.thesportsdb.com/",
            "openliga": "https://www.openligadb.de/",
        }[provider],
    }


def _source_rank(fixture):
    # Official KNVB live HTML beats API sources, while a verified-but-dated
    # schedule loses to a fresh licensed football-data.org fixture.
    if fixture.get("provider") == "knvb":
        return 5 if fixture.get("source_method") == "official_page_live" else 2
    return SOURCE_PRIORITY.get(fixture.get("provider"), 0)


def _merge_key(fixture):
    # Cross-source comparison by *verified league, date and both team names*.
    # Unknown aliases don't risk merging distinct clubs.
    league = fixture["league"]
    return (
        league, fixture["date"],
        norm(_team_name(league, fixture["home"])),
        norm(_team_name(league, fixture["away"])),
    )


def _from_archived_fixture(fixture, now, days):
    """Tentative archive schedules are not claimed independently verified."""
    try:
        league = fixture["league"]
        date_value = date.fromisoformat(fixture["date"])
        if league not in LEAGUES or not (now.date() < date_value <= now.date() + timedelta(days=days)):
            return None
        home, away = fixture["home"], fixture["away"]
        if not all(isinstance(x, str) and x.strip() for x in (home, away)):
            return None
        return {
            "provider": "openfootball-archive",
            "source_id": str(fixture["id"]), "league": league,
            "league_name": LEAGUES[league],
            "home": home, "away": away, "date": date_value.isoformat(),
            "kickoff": None, "source_confirmed": False,
            "status": "scheduled", "hg": None, "ag": None,
            "source_url": "https://github.com/openfootball/football.json",
        }
    except (ValueError, KeyError, TypeError):
        return None


def _load_model(path=RESEARCH_MODEL):
    candidates = (AUGMENTED_MODEL, Path(path), PUBLISHED_MODEL)
    for candidate in candidates:
        try:
            model = load_pretrained(candidate)
            if model.get("version") in (
                "0.13.0-local-augmented", "0.12.0-research-experimental"
            ):
                return model
        except (TrainingError, OSError):
            pass
    return None


def _evaluate(fixture, model, now):
    """Safely provide forecasts only when team ratings and a valid match exist."""
    if model is None:
        return None, "Onderzoeksmodel niet beschikbaar"
    if fixture["status"] != "scheduled":
        return None, "Wedstrijd is niet meer gepland"
    if not fixture["source_confirmed"]:
        if fixture["provider"] == "openfootball-archive":
            return None, "Voorlopig archiefschema: aftrap niet recent bevestigd"
        return None, "Schema uit verouderde of onbetrouwbare broncache; eerst opnieuw verifiëren"
    if not fixture["kickoff"]:
        return None, "Geen geverifieerd tijdstip vóór aftrap"
    kickoff = _utc(fixture["kickoff"])
    if kickoff is None or kickoff <= now:
        return None, "Wedstrijd is gestart of aftraptijd onbekend"
    league = fixture["league"]
    try:
        result = predict_trained(
            model, league,
            _team_name(league, fixture["home"]),
            _team_name(league, fixture["away"]),
        )
    except (TrainingError, TypeError, ValueError, KeyError):
        return None, "Een of beide clubs niet betrouwbaar gekoppeld aan modeldata"
    model_last_date = result["data_through"]
    try:
        age = (now.date() - date.fromisoformat(model_last_date)).days
    except (ValueError, TypeError):
        return None, "Trainingsdatum is niet betrouwbaar"
    if age >= 90:
        return None, "Model voor deze competitie is ernstig verouderd (" + str(age) + " dagen)"
    result["model_age_days"] = max(0, age)
    result["schedule_confidence"] = "confirmed_from_provider"
    result["data_warning"] = (
        "Model mist de recentste uitslagen (" + str(age) + " dagen achterstand)"
        if age >= 14 else
        "Experimentele schatting; geen blessure-, opstellings- of oddsgegevens"
    )
    return result, None


def _frozen_pre_match(entries, completed, log_path, now):
    """Keep immutable pre-match snapshots and grade only the same source ID."""
    from .trained_model import score
    path = Path(log_path)
    prior = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    forecasts = prior.get("forecasts", {})
    added, graded, voided = 0, 0, 0
    finals = {(row["provider"], row["source_id"]): row for row in completed}
    for key, record in forecasts.items():
        if record.get("result") or record.get("void_reason"):
            continue
        finished = finals.get((record["provider"], record["source_id"]))
        if not finished:
            continue
        kicked_off = _utc(record.get("kickoff"))
        created = _utc(record.get("created_at_utc"))
        if (kicked_off is None or created is None or created >= kicked_off
                or finished["kickoff"] != record["kickoff"]
                or finished["home"] != record["home"]
                or finished["away"] != record["away"]):
            record["void_reason"] = "rescheduled_or_invalid_snapshot"
            voided += 1
            continue
        brier, logloss = score(record["prediction"]["probabilities"], finished)
        record["result"] = {
            "date": finished["date"], "hg": finished["hg"], "ag": finished["ag"],
            "brier": round(brier, 7), "logloss": round(logloss, 7),
        }
        graded += 1
    for row in entries:
        pred = row.get("prediction")
        if (not pred or not row["source_confirmed"] or not row["kickoff"]
                or not _utc(row["kickoff"]) or _utc(row["kickoff"]) <= now):
            continue
        key = row["provider"] + "/" + row["source_id"]
        if key not in forecasts:
            forecasts[key] = {
                "provider": row["provider"], "source_id": row["source_id"],
                "home": row["home"], "away": row["away"],
                "league": row["league"], "kickoff": row["kickoff"],
                "created_at_utc": now.isoformat(timespec="seconds"),
                "prediction": pred, "result": None,
            }
            added += 1
    if added or graded or voided or not path.exists():
        atomic_json(path, {"schema_version": 1, "forecasts": forecasts})
    evaluated = [r["result"] for r in forecasts.values() if r.get("result")]
    n = len(evaluated)
    return {
        "total_pre_match_snapshots": len(forecasts), "new_snapshots": added,
        "graded_total": n, "new_graded": graded, "new_void": voided,
        "prospective_logloss": round(sum(r["logloss"] for r in evaluated)/n, 6) if n else None,
        "prospective_brier": round(sum(r["brier"] for r in evaluated)/n, 6) if n else None,
    }


def build_upcoming(*, model=None, inventory=None, fetched=None, now=None,
                   forecast_log=FORECAST_LOG, output=UPCOMING_FILE):
    """Pure transform except intentional local prediction snapshot writes."""
    now = now or datetime.now(timezone.utc)
    model = model if model is not None else _load_model()
    fetched = fetched or []
    recent_finals = [row for row in fetched if row["status"] == "finished"]
    scheduled = {}
    for fixture in fetched:
        if fixture.get("league") == "be.1":
            continue  # Belgium follows after data reliability catches up.
        if fixture["status"] != "scheduled":
            continue
        key = _merge_key(fixture)
        if key not in scheduled or _source_rank(fixture) > _source_rank(scheduled[key]):
            scheduled[key] = fixture
    # Never place stale archive fixtures in the serious upcoming dashboard.
    # They remain in the separate research archive for auditing only.
    rows = []
    from .research_rationale import reasoning
    for row in sorted(scheduled.values(), key=lambda m:(m["date"], m["kickoff"] or "", m["league"], m["home"])):
        prediction, warning = _evaluate(row, model, now)
        argument = reasoning(model, prediction, now=now) if prediction else None
        rows.append({**row, "prediction": prediction,
                     "model_preference": argument,
                     "prediction_unavailable_reason": warning})
    rows.sort(key=lambda item: (
        0 if (item.get("model_preference") or {}).get("eligible_for_highlight") else 1
        if item.get("model_preference") else 2,
        -(item.get("model_preference") or {}).get("margin", 0),
        item["date"], item["home"],
    ))
    freeze = _frozen_pre_match(rows, recent_finals, forecast_log, now)
    confirmed = sum(row["source_confirmed"] for row in rows)
    # Yesterday and today (plus a short rolling recovery window) are shown as
    # verified provider results, never as demo or 2016 archive placeholders.
    local_day = now.astimezone().date()
    recent_results = sorted([
        {k: final.get(k) for k in (
            "provider", "source_id", "league", "league_name", "home", "away",
            "date", "kickoff", "hg", "ag", "source_url"
        )}
        for final in recent_finals
        if final.get("league") != "be.1"
        and final.get("date", "") >= (local_day-timedelta(days=2)).isoformat()
        and final.get("date", "") <= local_day.isoformat()
    ], key=lambda row:(row["date"],row["league"],row["home"]),reverse=True)
    completed_seen=set()
    unique_results=[]
    for final in recent_results:
        identity=_merge_key(final)
        if identity not in completed_seen:
            completed_seen.add(identity)
            unique_results.append(final)
    result = {
        "schema_version": 1,
        "updated_at_utc": now.isoformat(timespec="seconds"),
        "window_days": WINDOW_DAYS,
        "schedule_count": len(rows),
        "confirmed_schedule_count": confirmed,
        "provisional_schedule_count": len(rows) - confirmed,
        "predicted_count": sum(row["prediction"] is not None for row in rows),
        "model_version": model.get("version") if model else None,
        "model_last_data": model.get("last_observed_result_date") if model else None,
        "fixtures": rows[:150],
        "recent_results": unique_results[:100],
        "recent_results_count": len(unique_results),
        "model_comparisons": {"external_models_tested": 0,
            "automatically_fused": False,
            "note": "Externe modelcombinaties vereisen eerlijke chronologische vergelijking."},
        "prospective_evaluation": freeze,
        "disclaimer": (
            "Provider schedules are displayed locally under their individual licenses. "
            "Only confirmed kickoffs with known teams receive model probabilities. "
            "Older OpenFootball schedules are provisional and not forecasted. "
            "No evidence of betting profit."
        ),
    }
    atomic_json(output, result)
    return result


def fetch_provider_schedules(*, now=None, football_data=None,
                             sports_fetcher=None, openliga=None, pause=2.2,
                             knvb_fetcher=None):
    """Bounded provider discovery with free-tier pacing and 429 fast-stop.

    SportsDB free v1 is partial by design. Schedules are never exhaustive.
    """
    now = now or datetime.now(timezone.utc)
    fetched, warnings = [], []
    sports_fetcher = sports_fetcher or (
        lambda url: fetch_bounded_json(url, "sportsdb")
    )
    football_data = football_data if football_data is not None else FootballData()
    if football_data.enabled:
        for provider_code, league in PROVIDER_LEAGUES["football-data"].items():
            try:
                result = football_data.list_matches(provider_code)
                for event in result.get("matches", []):
                    row = _normalize(event, "football-data", league, now)
                    if row:
                        if result.get("stale") or result.get("warnings"):
                            row["source_confirmed"] = False
                        fetched.append(row)
                if result.get("stale") or result.get("warnings"):
                    warnings.append("football-data " + provider_code + ": bron mogelijk vertraagd")
            except ProviderHTTPFailure as exc:
                warnings.append(
                    "football-data HTTP " + str(exc.status_code) +
                    " bij " + provider_code +
                    "; overige football-data-verzoeken zijn in deze ronde gestopt"
                )
                break
            except (OSError, ValueError, RuntimeError, LiveDataUnavailable) as exc:
                warnings.append("football-data " + provider_code + ": " + type(exc).__name__)
                # An unavailable service must not trigger the next five
                # network requests within a few seconds.
                break
            # The free football-data.org tier permits at most 10/min.
            # Previous code accidentally bypassed ALL pacing by testing
            # 'sports_fetcher is None' after assigning a default lambda.
            # Fake-provider tests pass pause=0 and never sleep.
            if pause:
                time.sleep(max(6.5, pause))
    else:
        warnings.append("football-data.org API-token ontbreekt: beperkt gratis TheSportsDB-schema")
    # Critical Eredivisie fallback: do not depend exclusively on TheSportsDB.
    # Live official source is checked once; if blocked, use the explicitly
    # dated official KNVB schedule snapshot, never fake/demo fixtures.
    from .research_knvb import get_eredivisie
    try:
        official, official_warnings = (
            knvb_fetcher(now=now) if knvb_fetcher is not None
            else get_eredivisie(now=now)
        )
        fetched.extend(official)
        warnings.extend(official_warnings)
    except (OSError, ValueError, RuntimeError) as exc:
        warnings.append("KNVB schema tijdelijk niet leesbaar: " + type(exc).__name__)
    sports_days = [
        (now.astimezone() + timedelta(days=offset)).date().isoformat()
        for offset in (-1, 0, 1)
    ]
    # A single denied request is enough to suspend TheSportsDB for this
    # refresh: 30 near-identical calls would only increase throttling and hide
    # the useful HTTP status from the user. Independent providers still run.
    sportsdb_failure = None
    for provider_code, league in PROVIDER_LEAGUES["sportsdb"].items():
        if league == "be.1":
            continue
        paths = [
            "/api/v1/json/123/eventsday.php?d=" + day + "&l=" + provider_code
            for day in sports_days
        ]
        paths.append("/api/v1/json/123/eventsnextleague.php?id=" + provider_code)
        paths.append("/api/v1/json/123/eventspastleague.php?id=" + provider_code)
        for path in paths:
            try:
                raw = sports_fetcher(path)
                events = raw.get("events") if isinstance(raw, dict) else None
                for raw_event in (events or [])[:4]:
                    try:
                        normalized = normalize_sportsdb(raw_event, provider_code)
                        row = _normalize(normalized, "sportsdb", league, now)
                        if row:
                            fetched.append(row)
                    except (ValueError, KeyError, TypeError):
                        pass
            except ProviderHTTPFailure as exc:
                sportsdb_failure = (
                    "TheSportsDB: HTTP " + str(exc.status_code) +
                    (" (rate limit; wacht op herstel)" if exc.status_code == 429 else
                     " (toegang geweigerd; API of netwerk controleren)"
                     if exc.status_code in (401, 403) else
                     " (provider tijdelijk onbereikbaar)"
                     if exc.status_code >= 500 else
                     " (verzoek niet toegestaan of bronroute gewijzigd)")
                )
                break
            except (OSError, ValueError, RuntimeError, LiveDataUnavailable) as exc:
                sportsdb_failure = (
                    "TheSportsDB: " + type(exc).__name__ +
                    " (tijdelijk uitgeschakeld voor deze ronde)"
                )
                break
            # Five requests x six active leagues = at most 30 when healthy.
            if pause:
                time.sleep(max(0.0, pause))
        if sportsdb_failure:
            warnings.append(sportsdb_failure +
                            "; volgende ronde herprobeert, andere bronnen blijven actief")
            break
    openliga = openliga if openliga is not None else LiveScores()
    for provider_code, league in PROVIDER_LEAGUES["openliga"].items():
        try:
            result = openliga.list_matches(provider_code)
            for event in result.get("matches", []):
                row = _normalize(event, "openliga", league, now)
                if row:
                    if result.get("stale") or result.get("warning"):
                        row["source_confirmed"] = False
                    fetched.append(row)
        except (OSError, ValueError, RuntimeError, LiveDataUnavailable) as exc:
            warnings.append("OpenLigaDB " + provider_code + ": " + type(exc).__name__)
    return fetched, sorted(set(warnings))


@contextmanager
def _single_fixture_refresh(directory):
    """Keep manual BAT and the six-hour monitor from hitting APIs together."""
    path = Path(directory) / "upcoming.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+b")
    try:
        try:
            if __import__("os").name == "nt":
                import msvcrt
                stream.seek(0)
                if not stream.read(1):
                    stream.write(b"X")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError("Speelschemacontrole loopt al; probeer later opnieuw") from None
        yield
    finally:
        try:
            if __import__("os").name == "nt":
                import msvcrt
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        stream.close()


def refresh_upcoming(*, inventory=None, data_dir=LOCAL, now=None,
                     provider_fetcher=None, model=None):
    now = now or datetime.now(timezone.utc)
    data_dir = Path(data_dir)
    with _single_fixture_refresh(data_dir):
        if inventory is None:
            path = data_dir / "inventory.json"
            inventory = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        if provider_fetcher is None:
            fetched, errors = fetch_provider_schedules(now=now)
        else:
            fetched, errors = provider_fetcher(now=now)
        base_model = model if model is not None else _load_model()
        # v0.14: a separately authorized DED full-season results API can
        # repair weeks of missing scores, not just the last 3 matchdays.
        # Test-injected provider data must NEVER trigger real remote requests.
        nl_status = {"status":"not_checked","league":"nl.1"}
        if provider_fetcher is None:
            from .research_nl_api import refresh_nl_api
            try:
                nl_status = refresh_nl_api(
                    now=now,data_dir=data_dir,model=base_model,inventory=inventory
                )
                if nl_status.get("status") in (
                    "subscription_required", "rate_limited", "api_http_error",
                    "stale_api_cache", "provider_unavailable", "invalid_api_route",
                    "error"
                ):
                    errors.append(
                        "Eredivisie uitslagen: "+nl_status["status"]+
                        " (bestaande gegevens blijven behouden)"
                    )
                if nl_status.get("model_retrained"):
                    base_model = _load_model()
            except (OSError, ValueError, RuntimeError, LiveDataUnavailable,
                    KeyError, TypeError) as exc:
                # Even a broken local status file or an unexpected provider
                # wrapper must not kill the background fixture worker.
                nl_status = {"status":"error", "error_type":type(exc).__name__,
                             "league":"nl.1"}
                errors.append(
                    "Nederlandse uitslagencontrole mislukt ("+
                    type(exc).__name__+"); oude modelgegevens behouden"
                )
        refresh_state = {"updated": False, "added": 0,
                         "conflicts": 0, "local_retrained": False}
        if isinstance(inventory, dict) and len(inventory.get("matches", [])) >= 1000 and base_model:
            # Always update from strictly verified finished events, without
            # committing third-party records/models to the public CC0 branch.
            try:
                from .research_daily_results import (
                    collect_verified_finals, rebuild_augmented_if_needed
                )
                newly = collect_verified_finals(
                    fetched, base_model, now=now,
                    path=data_dir / "provider_finals_local.json",
                )
                current_model, coverage = rebuild_augmented_if_needed(
                    inventory, folder=data_dir
                )
                base_model = current_model
                refresh_state = {
                    "updated": newly["new"] > 0 or coverage["retrained"],
                    "added": newly["new"],
                    "conflicts": newly["conflicted"] + coverage["provider_conflicts_with_cc0"],
                    "local_retrained": coverage["retrained"],
                    "extra_games": coverage["provider_extra_matches"],
                }
            except (ValueError, OSError, RuntimeError, KeyError, TrainingError) as exc:
                errors.append("Lokale modelaanvulling: " + type(exc).__name__)
        result = build_upcoming(
            model=base_model, inventory=inventory, fetched=fetched, now=now,
            forecast_log=data_dir / "provider_forecast_log.json",
            output=data_dir / "upcoming_predictions.json",
        )
        result["nl_result_source"] = nl_status
        # Summaries only: never put licensed CSV rows or personal filenames
        # in the public browser response or on GitHub.
        csv_file=data_dir/"nl_csv_finals_local.json"
        if csv_file.is_file():
            try:
                csv_local=json.loads(csv_file.read_text(encoding="utf-8"))
                imported=csv_local.get("matches",[])
                result["nl_manual_history"]={
                    "matches":len(imported),
                    "seasons":len({m["season"] for m in imported}),
                    "latest_result_date":max((m["date"] for m in imported),default=None),
                    "source":"manually_supplied_csv_on_this_pc",
                }
            except (ValueError,OSError,KeyError,TypeError):
                result["nl_manual_history"]={"error":"invalid_local_csv"}
        result["local_data_update"] = {
            **refresh_state,
            "nl_api_added": nl_status.get("new_confirmed",0),
            "nl_api_retrained": nl_status.get("model_retrained",False),
        }
        result["provider_warnings"] = errors
        atomic_json(data_dir / "upcoming_predictions.json", result)
        return result


def main():
    print("Actuele geplande wedstrijden ophalen voor Research Lab (lokaal).")
    result = refresh_upcoming()
    print(json.dumps({
        key: result[key] for key in (
            "schedule_count", "confirmed_schedule_count", "provisional_schedule_count",
            "predicted_count", "model_version", "model_last_data",
            "provider_warnings", "prospective_evaluation"
        )
    }, indent=2, ensure_ascii=False))
    print("Dashboardbestand:", UPCOMING_FILE)


if __name__ == "__main__":
    main()
