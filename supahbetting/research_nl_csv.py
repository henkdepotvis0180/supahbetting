"""Private Eredivisie CSV backfill: manually downloaded source files only.

No scraping, no automatic CSV requests, no bookmaker secret, no public GitHub
republication. Validates N1 complete scores, dates and provenance before use.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re

from .research_data import LOCAL, atomic_json
from .research_upcoming import _team_name
from .trained_model import norm

CSV_FOLDER=LOCAL/"nl_csv_inbox"
CSV_IMPORTED=LOCAL/"nl_csv_finals_local.json"
MAX_CSV_BYTES=2_000_000
MIN_DATE=date(2016,1,1)
DATE_FORMATS=("%d/%m/%Y","%d/%m/%y","%Y-%m-%d")
FIELD_LIMIT=130


def _date(value):
    if not isinstance(value,str) or len(value)>15:
        return None
    for pattern in DATE_FORMATS:
        try:
            parsed=datetime.strptime(value.strip(),pattern).date()
            # Reject platform 'strptime' 2-digit-year crossing into 2069.
            if pattern=="%d/%m/%y" and parsed.year>=2069:
                return None
            return parsed
        except ValueError:
            pass
    return None


def _club(value):
    if not isinstance(value,str) or len(value)>FIELD_LIMIT or not value.strip():
        return None
    if not re.fullmatch(r"[\w \-\.'éèëêáàâäüöï/]+",value.strip(),re.UNICODE):
        return None
    try:
        return _team_name("nl.1",value.strip())
    except ValueError:
        return None


def _score(raw):
    if not isinstance(raw,str) or not re.fullmatch(r"\d{1,2}",raw.strip()):
        return None
    n=int(raw)
    return n if 0<=n<=20 else None


def _key(m):
    return (m["date"],norm(m["home"]),norm(m["away"]))


def parse_csv(raw, *, now=None, filename="source.csv"):
    now=now or datetime.now(timezone.utc)
    if len(raw)>MAX_CSV_BYTES:
        raise ValueError("CSV groter dan 2 MB")
    if b"\0" in raw:
        raise ValueError("CSV met onjuist binair bestand")
    try:
        decoded=raw.decode("utf-8-sig")
    except UnicodeError:
        decoded=raw.decode("cp1252")
    rows=csv.DictReader(io.StringIO(decoded,newline=""))
    required={"Div","Date","HomeTeam","AwayTeam","FTHG","FTAG","FTR"}
    if rows.fieldnames is None or not required.issubset(set(rows.fieldnames)):
        raise ValueError("CSV heeft geen voetbalresultaten-schema (N1)")
    imported={}
    declined={"other_league":0,"not_finished":0,"outside_date":0,
              "not_full_time":0,"malformed":0}
    for source in rows:
        if len(imported)>420:
            raise ValueError("Onverwacht veel Eredivisie-wedstrijden in een seizoen CSV")
        if not isinstance(source,dict) or None in source:
            declined["malformed"]+=1
            continue
        if (source.get("Div") or "").strip()!="N1":
            declined["other_league"]+=1
            continue
        played=_date(source.get("Date"))
        if played is None or played<MIN_DATE or played>=now.date():
            declined["outside_date"]+=1
            continue
        home=_club(source.get("HomeTeam"))
        away=_club(source.get("AwayTeam"))
        hg=_score(source.get("FTHG"))
        ag=_score(source.get("FTAG"))
        actual=(source.get("FTR") or "").strip().upper()
        if not home or not away or norm(home)==norm(away) or hg is None or ag is None:
            declined["malformed"]+=1
            continue
        truth="H" if hg>ag else "A" if hg<ag else "D"
        if actual not in ("H","D","A") or actual!=truth:
            declined["not_full_time"]+=1
            continue
        year=played.year if played.month>=7 else played.year-1
        season=f"{year}-{(year+1)%100:02d}"
        identity=[played.isoformat(),norm(home),norm(away)]
        key=hashlib.sha256(json.dumps(identity).encode("utf-8")).hexdigest()[:24]
        entry={
            "id":key,"league":"nl.1","season":season,
            "date":played.isoformat(),"home":home,"away":away,
            "hg":hg,"ag":ag,"source_provider":"manual_eredivisie_csv",
            "source_file":filename,
        }
        match_key=_key(entry)
        prior=imported.get(match_key)
        if prior is not None:
            if (prior["hg"],prior["ag"])!=(hg,ag):
                raise ValueError("Tegenstrijdige eindstanden in hetzelfde CSV-bestand")
            continue
        imported[match_key]=entry
    return list(imported.values()),declined


def import_local_csv(*,folder=CSV_FOLDER,output=CSV_IMPORTED,now=None):
    """Only local inbox files; no URL download, no automated remote polling."""
    folder=Path(folder)
    files=sorted(folder.glob("*.csv")) if folder.is_dir() else []
    if not files:
        return {
            "status":"no_files","folder":str(folder),
            "imported_matches":0,
            "message":"Plaats handmatig gedownloade N1 Eredivisie-CSV's in de lokale map.",
        }
    now=now or datetime.now(timezone.utc)
    original=json.loads(Path(output).read_text(encoding="utf-8")) if Path(output).is_file() else {}
    old=original.get("matches",[])
    merged={_key(m):m for m in old}
    sources={r["file"]:r for r in original.get("sources",[])}
    collisions=[]
    new_count=0
    unreadable=[]
    for path in files[:20]:
        if path.stat().st_size>MAX_CSV_BYTES:
            unreadable.append({"file":path.name,"reason":"too_big"})
            continue
        data=path.read_bytes()
        try:
            matches,skipped=parse_csv(data,now=now,filename=path.name)
        except (ValueError,UnicodeError,csv.Error):
            unreadable.append({"file":path.name,"reason":"invalid_schema_or_scores"})
            continue
        if not matches:
            unreadable.append({"file":path.name,"reason":"no_finished_matches"})
            continue
        # Avoid ambiguous arbitrary filenames; all local files remain untrusted
        # if they cannot be independently sourced. Clearly label this.
        for item in matches:
            key=_key(item)
            if key in merged:
                previous=merged[key]
                if (previous["hg"],previous["ag"])!=(item["hg"],item["ag"]):
                    collisions.append({
                        "date":item["date"],"home":item["home"],"away":item["away"],
                        "existing_file":previous.get("source_file"),
                        "new_file":path.name,
                        "reason":"conflicting_finished_scores",
                    })
                    merged.pop(key)
                continue
            if any(x["date"]==item["date"] and x["home"]==item["home"]
                   and x["away"]==item["away"] for x in collisions):
                continue
            merged[key]=item
            new_count+=1
        sources[path.name]={
            "file":path.name,
            "sha256":hashlib.sha256(data).hexdigest(),
            "parsed_count":len(matches),
            "date_first":min(m["date"] for m in matches),
            "date_last":max(m["date"] for m in matches),
            "source_claim":"user_supplied_csv; origin not independently proven",
            "last_imported_at_utc":now.isoformat(timespec="seconds"),
        }
    if not merged:
        return {"status":"no_valid_matches","imported_matches":0,
                "invalid_files":unreadable}
    all_rows=sorted(merged.values(),key=lambda r:(r["date"],r["home"],r["away"]))
    payload={
        "schema_version":1,"league":"nl.1",
        "source_type":"manually_supplied_football_data_co_uk_style_csv",
        "licensing":"Local personal research only; never publish upstream CSV or rows to GitHub.",
        "matches":all_rows,
        "sources":list(sources.values()),
        "conflicts":list(original.get("conflicts",[]))+collisions,
        "updated_at_utc":now.isoformat(timespec="seconds"),
    }
    atomic_json(output,payload)
    return {
        "status":"imported","imported_matches":len(all_rows),
        "new_matches":new_count,
        "first_match":all_rows[0]["date"],"last_match":all_rows[-1]["date"],
        "seasons":len({m["season"] for m in all_rows}),
        "source_files":len(sources),
        "conflicts":len(payload["conflicts"]),"invalid_files":unreadable,
        "warning":"Brongegevens handmatig aangeleverd; datakwaliteit en rechten blijven belangrijk.",
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--folder",type=Path,default=CSV_FOLDER)
    args=parser.parse_args()
    args.folder.mkdir(parents=True,exist_ok=True)
    state=import_local_csv(folder=args.folder)
    print(json.dumps(state,indent=2,ensure_ascii=False))
    return 0 if state["status"] in ("imported","no_files") else 1


if __name__=="__main__":
    raise SystemExit(main())
