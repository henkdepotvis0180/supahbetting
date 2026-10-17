"""Local-only latest FINISHED scores and safe incremental replay.

All non-CC0 provider results remain local. Provider score records, training
snapshots and identities are never sent to the public GitHub research sync.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

from .research_data import LOCAL, atomic_json
from .research_model import train_candidate, _history_digest
from .trained_model import LEAGUES, _lookup_team, norm, TrainingError, load_pretrained

LOCAL_FINALS = LOCAL / "provider_finals_local.json"
AUGMENTED_MODEL = LOCAL / "augmented_model_local.json"
AUGMENTED_STATE = LOCAL / "augmented_training_state.json"
MAX_LOCAL_FINALS = 12000


def _utc(iso):
    if not isinstance(iso, str):
        return None
    try:
        value = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return value.astimezone(timezone.utc) if value.tzinfo else None
    except ValueError:
        return None


def _approved_final(row, model, now, *, max_age_days=21):
    """A real finished match, at least 90 mins after claimed kickoff."""
    if (not isinstance(row, dict) or row.get("status") != "finished"
            or row.get("source_confirmed") is not True):
        # A stale cached source may contain plausible looking final scores.
        # Do not train from it until an active provider re-confirms the record.
        return None
    league = row.get("league")
    if league not in LEAGUES or league == "be.1":
        return None
    kickoff = _utc(row.get("kickoff"))
    if not kickoff or not (timedelta(hours=1,minutes=30) <= now-kickoff <= timedelta(days=max_age_days)):
        return None
    hg, ag = row.get("hg"), row.get("ag")
    if type(hg) is not int or type(ag) is not int or not (0 <= hg <= 20 and 0 <= ag <= 20):
        return None
    try:
        teams = model["leagues"][league]["teams"]
        from .research_upcoming import _team_name  # Avoid module-level import cycle.
        home = _lookup_team(league, _team_name(league, row.get("home")), teams)
        away = _lookup_team(league, _team_name(league, row.get("away")), teams)
    except (TrainingError, TypeError, KeyError, ValueError):
        return None
    if home == away:
        return None
    day = kickoff.date().isoformat()
    year = kickoff.year if kickoff.month >= 7 else kickoff.year - 1
    season = str(year) + "-" + str((year+1)%100).zfill(2)
    identity = json.dumps([league, day, norm(home), norm(away)], separators=(",", ":"))
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return {
        "id":key,"league":league,"season":season,"date":day,
        "home":home,"away":away,"hg":hg,"ag":ag,
        "source_provider":row["provider"],"source_event_id":row["source_id"],
        "confirmed_after_utc":now.isoformat(timespec="seconds"),
    }


def collect_verified_finals(fetched, model, *, now=None, path=LOCAL_FINALS, max_age_days=21):
    """Quarantine conflicting scores; never overwrite evidence silently."""
    now = now or datetime.now(timezone.utc)
    path = Path(path)
    original = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    rows = {r["id"]: r for r in original.get("finished", [])}
    conflicts = {r["id"]:r for r in original.get("conflicts", [])}
    new, rejected = 0, 0
    for raw in fetched:
        item = _approved_final(raw, model, now, max_age_days=max_age_days)
        if not item or item["id"] in conflicts:
            continue
        prior = rows.get(item["id"])
        if prior and (prior["hg"],prior["ag"]) != (item["hg"],item["ag"]):
            conflicts[item["id"]] = {
                "id": item["id"],"league":item["league"],"date":item["date"],
                "reason":"sources_disagree_on_final_score",
                "original_source":prior["source_provider"],
                "new_source":item["source_provider"],
            }
            rows.pop(item["id"],None)
            rejected += 1
        elif prior is None:
            rows[item["id"]] = item
            new += 1
    if len(rows) > MAX_LOCAL_FINALS:
        raise ValueError("Local result quota exceeded: review provider import")
    new_rows = sorted(rows.values(),key=lambda r:(r["date"],r["league"],r["home"]))
    atomic_json(path,{
        "schema_version":1,"source":"local_only_third_party_finals",
        "finished":new_rows,"conflicts":list(conflicts.values()),
        "updated_at_utc":now.isoformat(timespec="seconds"),
    })
    return {"new":new,"conflicted":rejected,"finished_count":len(new_rows),
            "conflict_count":len(conflicts)}


def merge_verified_locally(inventory, *, finals_path=LOCAL_FINALS, csv_path=None):
    """Reconcile base CC0 data, local API finals, and manual Eredivisie CSV.

    Every dated, named match is included at most once.  Never silently
    select between two different final scores.
    """
    original = inventory.get("matches", [])
    if not isinstance(original, list) or len(original) < 1000:
        raise ValueError("Historische echte wedstrijdbasis ontbreekt")
    finals_path = Path(finals_path)
    csv_path = Path(csv_path) if csv_path is not None else finals_path.with_name(
        "nl_csv_finals_local.json"
    )
    provider = json.loads(finals_path.read_text(encoding="utf-8")) if finals_path.exists() else {}
    manual = json.loads(csv_path.read_text(encoding="utf-8")) if csv_path.exists() else {}
    if not isinstance(provider.get("finished", []), list) or not isinstance(manual.get("matches", []), list):
        raise ValueError("Ongeldige lokale bronstructuur")

    def key(row):
        from .research_upcoming import _team_name
        league = row["league"]
        return (league, row["date"], norm(_team_name(league, row["home"])),
                norm(_team_name(league, row["away"])))

    base = {key(row): row for row in original}
    extras = {}
    rejected = set()
    conflicts = 0
    duplicates = 0
    csv_extras = set()
    for provider_name, items in (
        ("manual_csv", manual.get("matches", [])),
        ("football_api", provider.get("finished", [])),
    ):
        for row in items:
            try:
                if provider_name == "manual_csv" and row["league"] != "nl.1":
                    raise ValueError("CSV buiten Eredivisie")
                if type(row["hg"]) is not int or type(row["ag"]) is not int:
                    raise ValueError("Ongeldige score")
                if not (0 <= row["hg"] <= 20 and 0 <= row["ag"] <= 20):
                    raise ValueError("Onmogelijke eindstand")
                identity = key(row)
                if row["league"] not in LEAGUES or not (
                    "2016-01-01" <= row["date"] <= date.today().isoformat()
                ):
                    raise ValueError("Ongeldige speeldatum")
                if identity in rejected:
                    continue
                previous = base.get(identity)
                if previous is not None:
                    if (previous["hg"], previous["ag"]) != (row["hg"], row["ag"]):
                        conflicts += 1
                    else:
                        duplicates += 1
                    continue
                previous = extras.get(identity)
                if previous is not None:
                    if (previous["hg"], previous["ag"]) != (row["hg"], row["ag"]):
                        conflicts += 1
                        rejected.add(identity)
                        extras.pop(identity)
                        csv_extras.discard(identity)
                    else:
                        duplicates += 1
                    continue
                extra = {field: row[field] for field in (
                    "league", "season", "date", "home", "away", "hg", "ag", "id"
                )}
                extras[identity] = extra
                if provider_name == "manual_csv":
                    csv_extras.add(identity)
            except (ValueError, KeyError, TypeError):
                conflicts += 1
                continue
    merged = {**inventory, "matches": sorted(
        list(original) + list(extras.values()),
        key=lambda m: (m["date"], m["league"], m["home"], m["away"])
    )}
    return merged, {
        "provider_extra_matches": len(extras),
        "manual_csv_extra_matches": len(csv_extras),
        "provider_conflicts_with_cc0": conflicts,
        "duplicate_scores_skipped": duplicates,
        "provider_quarantined_matches": len(rejected),
        "manual_seasons": len({m["season"] for m in manual.get("matches", [])}),
    }

def rebuild_augmented_if_needed(inventory, *, folder=LOCAL):
    """Recompute all ratings only when audited local provider finals actually changed."""
    folder=Path(folder)
    merged, coverage=merge_verified_locally(
        inventory,finals_path=folder/"provider_finals_local.json")
    digest=_history_digest(merged["matches"])
    state_path=folder/"augmented_training_state.json"
    model_path=folder/"augmented_model_local.json"
    try:
        old=json.loads(state_path.read_text(encoding="utf-8"))
        if old.get("sha256")==digest and model_path.is_file():
            candidate=load_pretrained(model_path)
            if candidate.get("version")=="0.13.0-local-augmented":
                return candidate,{**coverage,"retrained":False}
    except (OSError, ValueError, TrainingError):
        pass
    trained, _=train_candidate(merged)
    trained["version"]="0.13.0-local-augmented"
    trained["experimental"]=True
    trained["research_provenance"]["local_only_provider_results"] = coverage["provider_extra_matches"]
    trained["research_provenance"]["provider_licence_warning"]=(
        "Additional supplier final scores stay local; this generated model is not "
        "automatically published to GitHub as CC0."
    )
    atomic_json(model_path,trained)
    atomic_json(state_path,{
        "sha256":digest,
        **coverage,
        "trained_at_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    return trained,{**coverage,"retrained":True}
