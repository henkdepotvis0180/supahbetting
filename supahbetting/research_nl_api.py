"""Eredivisie-first latest results from an authorized football-data.org API.

One season request (DED), not a scraper; no fabricated results.  Raw supplier
responses and derived supplier updates are local only, never published as CC0.
Manual historical CSV backfill is a separate opt-in import path.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from .external_feeds import FootballData, ProviderHTTPFailure
from .research_data import LOCAL, atomic_json
from .research_daily_results import (
    collect_verified_finals, rebuild_augmented_if_needed,
)
from .trained_model import TrainingError, load_pretrained
from .research_upcoming import _load_model

STATUS_FILE = LOCAL / "nl_update_status.json"
PROVIDER_CODE = "DED"
SUPPORTED_SOURCE = "https://www.football-data.org/"
MAX_MATCHES_PER_SEASON = 450


def season_year(now):
    if now.tzinfo is None:
        raise ValueError("UTC tijdstip vereist")
    return now.year if now.month >= 7 else now.year - 1


def validate_eredivisie_payload(raw, *, season):
    """Stop wrong competition / season responses before ingesting any scores."""
    if not isinstance(raw, dict) or not isinstance(raw.get("matches"), list):
        raise ValueError("Geen wedstrijdenlijst in Eredivisie API")
    comp = raw.get("competition")
    if not isinstance(comp, dict) or comp.get("code") != PROVIDER_CODE:
        raise ValueError("API antwoord is niet van de Eredivisie (DED)")
    matches=raw["matches"]
    if len(matches)>MAX_MATCHES_PER_SEASON:
        raise ValueError("Onverwacht grote Eredivisie lijst")
    allowed={season,season+1}
    for item in matches:
        if not isinstance(item,dict):
            raise ValueError("Ongeldig wedstrijdobject")
        declared=item.get("competition")
        if isinstance(declared,dict) and declared.get("code") not in (None,PROVIDER_CODE):
            raise ValueError("Wedstrijd uit andere competitie in DED-lijst")
        stamp=item.get("utcDate")
        if not isinstance(stamp,str) or len(stamp)<10:
            continue
        try:
            year=int(stamp[:4])
        except ValueError:
            continue
        if year not in allowed:
            raise ValueError("Competitiedata buiten aangevraagd seizoen")
    return matches


def _utc(value):
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError,TypeError,AttributeError):
        return None


def confirmed_results(raw, *, now, season):
    """Only FULL TIME, with declared integer home/away score after kickoff."""
    rows=validate_eredivisie_payload(raw,season=season)
    output=[]
    for row in rows:
        if row.get("status")!="FINISHED":
            continue
        comp=row.get("competition")
        stamp=_utc(row.get("utcDate"))
        if stamp is None or stamp>now-timedelta(minutes=90):
            continue
        goals=row.get("score")
        full=goals.get("fullTime") if isinstance(goals,dict) else None
        if not isinstance(full,dict):
            continue
        home,away=full.get("home"),full.get("away")
        if type(home) is not int or type(away) is not int or not (
            0<=home<=20 and 0<=away<=20
        ):
            continue
        event_id=row.get("id")
        home_team=row.get("homeTeam")
        away_team=row.get("awayTeam")
        if type(event_id) is not int or not 0<event_id<=9999999999:
            continue
        if not isinstance(home_team,dict) or not isinstance(away_team,dict):
            continue
        name_home=home_team.get("name")
        name_away=away_team.get("name")
        if not all(isinstance(n,str) and n.strip() and len(n)<120
                   for n in (name_home,name_away)):
            continue
        if name_home.strip().casefold()==name_away.strip().casefold():
            continue
        output.append({
            "provider":"football-data","source_id":str(event_id),
            "league":"nl.1","league_name":"Eredivisie",
            "home":name_home.strip(),"away":name_away.strip(),
            "date":stamp.date().isoformat(),
            "kickoff":stamp.isoformat(timespec="seconds"),
            "status":"finished","source_confirmed":True,
            "hg":home,"ag":away,"source_url":SUPPORTED_SOURCE,
        })
    return output


def _write_status(path, payload):
    atomic_json(path,{"schema_version":1,"league":"nl.1",**payload})


def refresh_nl_api(*, now=None, data_dir=LOCAL, provider=None, model=None,
                   inventory=None):
    """Refresh one DED season at responsible low frequency; never require token.

    Distinguish token missing, access denied and apparently successful but
    incomplete historical refresh.  A failed API never deletes old records.
    """
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Timezone required")
    directory=Path(data_dir)
    status_path=directory/"nl_update_status.json"
    result={
        "source":"football-data.org","code":"DED",
        "checked_at_utc":now.isoformat(timespec="seconds"),
        "status":"not_started","access":"unknown",
        "season":str(season_year(now)),"source_matches":0,
        "full_time_rows":0,"new_confirmed":0,
        "conflicted":0,"model_retrained":False,
        "model_last_score_date":None,
        "note":"Gratis toegang kan per competitie verschillen en score-updates vertragen.",
    }
    provider=provider if provider is not None else FootballData()
    if not provider.enabled:
        result.update(status="no_api_key",access="requires_football_data_org_token",
                      note=("Vul je football-data.org sleutel lokaal in. "
                            "Zonder abonnement is actuele Eredivisie-dekking niet gegarandeerd."))
        _write_status(status_path,result)
        return result
    path="/v4/competitions/DED/matches?season="+str(season_year(now))
    try:
        raw,fetched,stale,error=provider._cached(path, 1800)
        if stale or error:
            result.update(status="stale_api_cache",access="available_but_stale",
                          note="API-cache is verouderd; geen nieuwe uitslagen geïmporteerd.")
            _write_status(status_path,result)
            return result
        entries=confirmed_results(raw,now=now,season=season_year(now))
        latest_api_score=max((m["date"] for m in entries),default=None)
        days_behind=((now.date()-datetime.fromisoformat(latest_api_score).date()).days
                     if latest_api_score else None)
        result.update(
            source_matches=len(raw["matches"]),full_time_rows=len(entries),
            latest_api_score_date=latest_api_score,
            days_since_latest_api_score=days_behind,
            status=("loaded_but_lagging" if days_behind is None or days_behind>=3
                    else "loaded"),access="granted",
            note=("API gaf wel toegang, maar de nieuwste vastgelegde uitslag is "
                  +str(days_behind)+" dagen oud; controleer competitiestatus.")
                  if days_behind is not None and days_behind>=3 else
                  "API heeft eindstanden bevestigd, niet automatisch een compleet seizoen."
        )
        if model is None:
            model=_load_model()
        if model is None:
            result.update(status="no_model",
                          note="Model ontbreekt; geen gegevens in training opgenomen.")
        elif inventory is None or len(inventory.get("matches",[]))<1000:
            result.update(status="no_inventory",
                          note="Lokale 2016+ basis ontbreekt; oude gegevens niet vervangen.")
        else:
            report=collect_verified_finals(
                entries,model,now=now,path=directory/"provider_finals_local.json",
                max_age_days=380
            )
            candidate,train_state=rebuild_augmented_if_needed(inventory,folder=directory)
            result.update(new_confirmed=report["new"],
                          conflicted=report["conflicted"]+
                          train_state["provider_conflicts_with_cc0"],
                          model_retrained=train_state["retrained"],
                          model_last_score_date=candidate["leagues"]["nl.1"]["last_result_date"],
                          local_training_matches=candidate["training_matches"])
        _write_status(status_path,result)
        return result
    except ProviderHTTPFailure as exc:
        state=("subscription_required" if exc.status_code in (401,403) else
               "rate_limited" if exc.status_code==429 else "api_http_error")
        result.update(status=state,access="denied",http_status=exc.status_code,
                      note="API-toegang geweigerd of tijdelijk beperkt; bestaande lokale modellen blijven intact.")
    except (OSError,ValueError,RuntimeError,TrainingError,KeyError,TypeError) as exc:
        result.update(status="error",access="unknown",
                      error_type=type(exc).__name__,
                      note="API of dataset kon niet worden gevalideerd; niets overschreven.")
    _write_status(status_path,result)
    return result


def main():
    from .research_nl_bootstrap import bootstrap
    bootstrap()
    inventory_path=LOCAL/"inventory.json"
    inventory=json.loads(inventory_path.read_text(encoding="utf-8")) if inventory_path.is_file() else {}
    state=refresh_nl_api(inventory=inventory)
    print(json.dumps(state,ensure_ascii=False,indent=2))
    print("Ruwe API-resultaten worden NIET naar de openbare GitHub-branch geüpload.")
    if state["status"]=="no_api_key":
        print("API-sleutel optioneel: configureer_speelschema_api.bat")
    if state["status"]=="subscription_required":
        print("Eredivisie-toegang is beperkt bij dit API-abonnement; geen omzeiling.")
    return 0 if state["status"] in ("loaded","loaded_but_lagging",
                                   "no_api_key","subscription_required",
                                   "rate_limited","stale_api_cache") else 1


if __name__=="__main__":
    raise SystemExit(main())
