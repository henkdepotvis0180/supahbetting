"""Foreground Windows/Linux research monitor with safe 6-hour refreshes.

No external scheduler required. Stops on Ctrl+C or machine shutdown. Publishes
only after changed verified FINISHED results and successful local replay.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from .research_data import LOCAL, atomic_json, refresh
from .research_model import (
    CANDIDATE_PATH, REPORT_PATH, SHADOW_PATH, _history_digest, run,
)
from .research_sync import publish
from .research_features import coverage_report

STATUS = LOCAL / "monitor_status.json"
STATE = LOCAL / "monitor_state.json"
LOCK = LOCAL / "monitor.lock"


@contextmanager
def single_instance(path=LOCK):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    file = path.open("a+b")
    try:
        if __import__("os").name == "nt":
            import msvcrt
            file.seek(0)
            if not file.read(1):
                file.write(b"X")
                file.flush()
            file.seek(0)
            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        file.close()
        raise RuntimeError("Onderzoeksmonitor draait al; start niet tweemaal") from None
    try:
        yield
    finally:
        if __import__("os").name == "nt":
            import msvcrt
            file.seek(0)
            msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(file.fileno(), fcntl.LOCK_UN)
        file.close()


def update_status(**updates):
    old = json.loads(STATUS.read_text(encoding="utf-8")) if STATUS.exists() else {}
    old.update(updates)
    old["last_status_at_utc"] = datetime.now(timezone.utc).isoformat()
    atomic_json(STATUS, old)
    return old


def cycle(*, upload=True, full=None, delay=1.0,
          data_dir=LOCAL, publish_fn=None, refresh_fn=None, research_fn=None):
    """Testable cycle; no upload of failed/incomplete calculations."""
    data_dir = Path(data_dir)
    state_path = data_dir / "monitor_state.json"
    inventory = (refresh_fn or refresh)(
        directory=data_dir, full=full, delay=delay
    )
    matches = inventory["matches"]
    digest = _history_digest(matches)
    old_state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    changed = digest != old_state.get("last_successful_upload_digest")
    research_fn = research_fn or run
    report = research_fn(
        inventory,
        candidate_path=data_dir / "candidate_model.json",
        report_path=data_dir / "research_report.json",
        shadow_path=data_dir / "shadow_predictions.json",
    )
    report["context_coverage"] = coverage_report(data_dir / "verified_context.json")
    atomic_json(data_dir / "research_report.json", report)
    sync_state = "disabled" if not upload else "not_required"
    if upload and changed:
        model = json.loads((data_dir / "candidate_model.json").read_text(encoding="utf-8"))
        try:
            (publish_fn or publish)(inventory, report, model)
            sync_state = "published"
            atomic_json(state_path, {
                "last_successful_upload_digest": digest,
                "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            })
        except (OSError, ValueError, RuntimeError) as exc:
            # Auth/network failure must never discard a completed local training.
            sync_state = "failed:" + type(exc).__name__
    status = {
        "state": "idle", "sync_state": sync_state,
        "historical_matches": len(matches),
        "new_final_matches": len(inventory["new_final_match_ids"]),
        "latest_result_date": inventory["latest_result_date"],
        "model_version": "0.12.0-research-experimental",
        "gaps": len([s for s in inventory["coverage"] if s["state"] == "not_published"]),
        "failed_sources": len(inventory["failed_sources"]),
        "genuine_graded_forecasts": report["shadow_forecast_evaluation"]["graded_predictions"],
    }
    return status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Single scan and training")
    parser.add_argument("--full", action="store_true", help="Refresh every season 2016-present")
    parser.add_argument("--interval-hours", type=float, default=6)
    parser.add_argument("--no-upload", action="store_true")
    args = parser.parse_args()
    if not (1 <= args.interval_hours <= 168):
        parser.error("Interval moet tussen 1 en 168 uur zijn")
    with single_instance():
        print("SupahBetting research v0.12 draait op deze pc. Ctrl+C stopt.")
        while True:
            update_status(state="refreshing", sync_state="pending", last_error=None)
            try:
                result = cycle(upload=not args.no_upload,
                               full=True if args.full else None)
                update_status(**result, last_error=None)
                print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
            except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
                # Don't leak source bodies/API credentials into shared status.
                update_status(state="error", last_error=type(exc).__name__)
                print("Onderzoeksrun mislukt:", type(exc).__name__, flush=True)
                if args.once:
                    return 1
            if args.once:
                return 0
            time.sleep(args.interval_hours * 3600)


if __name__ == "__main__":
    raise SystemExit(main())
