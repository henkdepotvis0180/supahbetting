"""Bootstrap local 2016+ CC0 history from checked-in verified match records.

Instant startup without the old ZIP's research folder, internet downloads or
API keys. Never replaces an existing inventory, model or user's forecast logs.
"""
from __future__ import annotations

from datetime import datetime,timezone
import json
from pathlib import Path

from .research_data import LOCAL,atomic_json,seasons
from .trained_model import LEAGUES

PUBLISHED=Path("data/research/verified")


def bootstrap(*, directory=LOCAL, published=PUBLISHED):
    directory=Path(directory)
    target=directory/"inventory.json"
    if target.is_file():
        return {"state":"existing","matches":None}
    stored={}
    coverage=[]
    first=None
    latest=None
    for league in LEAGUES:
        path=Path(published)/(league+".json")
        if not path.is_file():
            return {"state":"missing_verified_files","missing":league}
        try:
            data=json.loads(path.read_text(encoding="utf-8"))
            if (data["league"]!=league or data.get("license")!="CC0-1.0"
                    or data.get("source")!="openfootball/football.json"):
                return {"state":"unverified_source","league":league}
            records=data["matches"]
            if not isinstance(records,list) or len(records)>7000:
                return {"state":"invalid_coverage","league":league}
            season_counts={}
            for m in records:
                if (type(m.get("hg")) is not int or type(m.get("ag")) is not int
                        or not 0<=m["hg"]<=20 or not 0<=m["ag"]<=20
                        or not isinstance(m.get("id"),str)
                        or not isinstance(m.get("home"),str)
                        or not isinstance(m.get("away"),str)
                        or not isinstance(m.get("date"),str)
                        or not isinstance(m.get("season"),str)):
                    return {"state":"invalid_score","league":league}
                if not "2016-01-01" <= m["date"] <= datetime.now(timezone.utc).date().isoformat():
                    return {"state":"unexpected_date","league":league}
                if m["id"] in stored:
                    return {"state":"duplicate_id","league":league}
                stored[m["id"]]={**m,"league":league}
                season_counts[m["season"]]=season_counts.get(m["season"],0)+1
                first=min(first or m["date"],m["date"])
                latest=max(latest or m["date"],m["date"])
            for season,count in season_counts.items():
                coverage.append({
                    "key":season+"/"+league,
                    "state":"bundled_cc0_snapshot",
                    "finished":count,
                    "fixtures":0,
                    "url":"https://github.com/openfootball/football.json",
                })
        except (OSError,ValueError,KeyError,TypeError):
            return {"state":"invalid_source_file","league":league}
    if len(stored)<12000:
        return {"state":"too_few_results","matches":len(stored)}
    records=sorted(stored.values(),key=lambda m:(m["date"],m["league"],m["home"]))
    payload={
        "schema_version":1,
        "source":"openfootball/football.json",
        "license":"CC0-1.0",
        "fetched_at_utc":datetime.now(timezone.utc).isoformat(),
        "latest_result_date":latest,
        "season_range":["2015-16",seasons(datetime.now(timezone.utc).date())[-1]],
        "last_full_check_at_utc":None,
        "matches":records,"fixtures":[],
        "coverage":coverage,"failed_sources":[],
        "new_final_match_ids":[],
        "initial_backfill_matches":len(records),
        "is_initial_import":True,
        "first_import_at_utc":datetime.now(timezone.utc).isoformat(),
        "warning":"Gebundelde CC0 historische basis, niet een recente livecontrole.",
    }
    if not target.exists():
        atomic_json(target,payload)
    return {"state":"created","matches":len(records),
            "first":first,"last":latest}


def main():
    print(json.dumps(bootstrap(),ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
