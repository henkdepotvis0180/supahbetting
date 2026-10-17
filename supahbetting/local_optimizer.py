"""Windows-friendly CPU-only model search with resumable checkpoints.

Candidate selection uses ONLY 2024/25 validation. 2025/26 and 2026/27
are evaluated once after selecting the best validation candidate.
Never writes to production model files.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import itertools
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from supahbetting.trained_model import (
    CURRENT_SEASON, TEST_SEASON, VALIDATION_SEASON,
    load_matches, run_sequential, summarize,
)

CHECKPOINT = Path("training_reports/local_optimizer_checkpoint.json")
REPORT = Path("training_reports/local_optimizer_report.json")
ALPHAS = (0.04, 0.07, 0.10, 0.12, 0.15, 0.19, 0.24, 0.30)
PRIORS = (3, 4, 6, 9, 12, 16, 24, 32)


def save_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def fingerprint(matches):
    digest = hashlib.sha256()
    for match in matches:
        digest.update(json.dumps(match, sort_keys=True).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def candidate_grid():
    return list(itertools.product(ALPHAS, PRIORS))


def evaluate_candidate(args):
    matches, alpha, prior = args
    development = [m for m in matches if m["season"] <= VALIDATION_SEASON]
    _, metrics, _ = run_sequential(development, alpha, prior, {VALIDATION_SEASON})
    summary = summarize(metrics[VALIDATION_SEASON])
    if not summary["matches"]:
        raise ValueError("No validation matches")
    return {"alpha": alpha, "prior_matches": prior,
            "validation": summary}


def choose_best(results):
    return min(results, key=lambda r: (
        r["validation"]["model_logloss"],
        r["validation"]["model_brier"],
        r["alpha"], r["prior_matches"],
    ))


def optimize(matches, checkpoint=CHECKPOINT, report=REPORT,
             hours=4.0, workers=16, quick=False):
    if not (0 < hours <= 4):
        raise ValueError("hours must be within (0, 4]")
    if not (1 <= workers <= 16):
        raise ValueError("workers must be within [1, 16]")
    if not matches:
        raise ValueError("historical matches required")
    started = time.monotonic()
    deadline = started + hours * 3600
    identity = fingerprint(matches)
    candidates = candidate_grid()[:4] if quick else candidate_grid()
    checkpoint = Path(checkpoint)
    report = Path(report)
    existing = {}
    if checkpoint.exists():
        saved = json.loads(checkpoint.read_text(encoding="utf-8"))
        if saved.get("dataset_sha256") == identity and saved.get("search_version") == 1:
            existing = { (r["alpha"], r["prior_matches"]): r
                         for r in saved.get("completed", []) }
    def persist():
        save_json(checkpoint, {
            "search_version": 1, "dataset_sha256": identity,
            "completed": list(existing.values()),
            "candidate_count": len(candidate_grid()),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
    pending = [(a, p) for a, p in candidates if (a, p) not in existing]
    # Bound outstanding work to workers, so timeout stops new submissions.
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        iterator = iter(pending)
        futures = {}
        def submit_one():
            if time.monotonic() >= deadline:
                return False
            try:
                a, p = next(iterator)
            except StopIteration:
                return False
            futures[pool.submit(evaluate_candidate, (matches, a, p))] = (a, p)
            return True
        for _ in range(workers):
            if not submit_one():
                break
        while futures:
            done, _ = concurrent.futures.wait(
                futures, timeout=max(0, min(5, deadline - time.monotonic())),
                return_when=concurrent.futures.FIRST_COMPLETED,
            )
            if not done and time.monotonic() >= deadline:
                for future in futures:
                    future.cancel()
                break
            for future in done:
                futures.pop(future)
                row = future.result()
                existing[(row["alpha"], row["prior_matches"])] = row
                persist()
                submit_one()
    completed = [existing[k] for k in candidates if k in existing]
    if not completed:
        raise RuntimeError("No candidate finished")
    best = choose_best(completed)
    # Holdouts are only scored if the FULL search completed. No holdout tuning.
    complete = len(completed) == len(candidates)
    result = {
        "experiment": "cpu_poisson_hyperparameter_search",
        "production_model_modified": False,
        "dataset_sha256": identity,
        "last_result_date": max(m["date"] for m in matches),
        "workers": workers, "time_budget_hours": hours,
        "quick": quick, "completed": len(completed),
        "requested": len(candidates), "complete": complete,
        "selection_season": VALIDATION_SEASON,
        "best_validation_candidate": best,
        "candidate_results": completed,
        "holdouts": {},
    }
    if complete:
        _, metrics, _ = run_sequential(
            matches, best["alpha"], best["prior_matches"],
            {TEST_SEASON, CURRENT_SEASON},
        )
        result["holdouts"] = {
            season: summarize(metrics[season])
            for season in (TEST_SEASON, CURRENT_SEASON)
        }
    save_json(report, result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=float, default=4)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--data-dir", default="data/historical")
    args = parser.parse_args()
    matches = load_matches(args.data_dir)
    result = optimize(matches, hours=args.hours, workers=args.workers, quick=args.quick)
    print(json.dumps({
        k: result[k] for k in ("completed", "requested", "complete",
                              "best_validation_candidate", "holdouts")
    }, indent=2))
    print("Rapport:", REPORT, "| Checkpoint:", CHECKPOINT)


if __name__ == "__main__":
    main()
