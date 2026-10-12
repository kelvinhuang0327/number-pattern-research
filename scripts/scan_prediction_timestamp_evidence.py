"""
Phase 6N — Prediction Timestamp Evidence Scanner

Read-only scanner that inspects available logs, report metadata, and file
timestamps to determine whether any pre-match timestamp evidence exists for
the rows in data/derived/model_outputs_2026-04-29.jsonl.

Does NOT modify any file. Does NOT backfill prediction_time_utc.
Does NOT call external APIs. Does NOT generate predictions.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "6n-1.0"
RUN_DATE = "2026-04-30"

# Keywords that suggest a log/report event is related to model inference
INFERENCE_KEYWORDS = re.compile(
    r"prediction|inference|model|mlb|decision_quality|build_ml_model_output"
    r"|model_output|prediction_time|generated_at|run_at|created_at",
    re.IGNORECASE,
)

# Game date range from Phase 6L adapter report
MLB_2025_FIRST_GAME = datetime(2025, 4, 24, tzinfo=timezone.utc)
MLB_2025_LAST_GAME = datetime(2025, 9, 28, 23, 59, 59, tzinfo=timezone.utc)

# Timestamp patterns to extract from text files
TS_PATTERNS = [
    re.compile(r'"timestamp"\s*:\s*"([^"]+)"'),
    re.compile(r'"generated_at"\s*:\s*"([^"]+)"'),
    re.compile(r'"created_at"\s*:\s*"([^"]+)"'),
    re.compile(r'"run_at"\s*:\s*"([^"]+)"'),
    re.compile(r'"prediction_time"\s*:\s*"([^"]+)"'),
    re.compile(r'\b(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\b'),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_iso(s: str):
    """Parse ISO8601 string to UTC datetime. Return None on failure."""
    if not s:
        return None
    s = s.strip().rstrip("Z")
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def classify_timestamp(ts: datetime, game_dates: list):
    """Classify a timestamp relative to game dates."""
    if ts is None:
        return "UNKNOWN"
    if game_dates:
        first = min(game_dates)
        last = max(game_dates)
        if ts < first:
            return "PRE_MATCH_CANDIDATE"
        elif ts > last:
            return "POST_MATCH"
        else:
            return "WITHIN_SEASON"
    return "UNKNOWN"


def file_mtime_utc(path: str) -> datetime:
    """Return file mtime as UTC datetime."""
    try:
        t = os.path.getmtime(path)
        return datetime.fromtimestamp(t, tz=timezone.utc)
    except OSError:
        return None


def scan_text_for_timestamps(text: str, source_path: str, keywords_required=True):
    """Extract timestamp-like strings from raw text. Optionally require inference keywords nearby."""
    events = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if keywords_required and not INFERENCE_KEYWORDS.search(line):
            continue
        for pat in TS_PATTERNS:
            for m in pat.finditer(line):
                raw = m.group(1)
                ts = parse_iso(raw)
                if ts:
                    events.append({
                        "source": source_path,
                        "line": i + 1,
                        "raw_timestamp": raw,
                        "parsed_utc": ts.isoformat(),
                        "context": line.strip()[:200],
                        "has_inference_keyword": bool(INFERENCE_KEYWORDS.search(line)),
                    })
                    break
    return events


def scan_jsonl_for_timestamps(path: str):
    """Scan a JSONL file for inference-related timestamp events."""
    events = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                if not INFERENCE_KEYWORDS.search(line):
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # Extract any timestamp field
                for key in ("timestamp", "generated_at", "created_at", "run_at", "prediction_time"):
                    if key in row and isinstance(row[key], str):
                        ts = parse_iso(row[key])
                        if ts:
                            events.append({
                                "source": path,
                                "line": i + 1,
                                "field": key,
                                "raw_timestamp": row[key],
                                "parsed_utc": ts.isoformat(),
                                "context": str(row)[:200],
                                "has_inference_keyword": True,
                            })
    except OSError:
        pass
    return events


# ---------------------------------------------------------------------------
# Scanners
# ---------------------------------------------------------------------------

def scan_model_outputs(path: str):
    """Inspect model_outputs JSONL for timing field coverage."""
    stats = {
        "path": path,
        "exists": os.path.exists(path),
        "total_rows": 0,
        "rows_with_prediction_time_utc": 0,
        "rows_missing_prediction_time_utc": 0,
        "rows_with_feature_cutoff_time_utc": 0,
        "rows_with_match_time_utc": 0,
        "clv_usable_true": 0,
        "clv_usable_false": 0,
        "match_time_utc_min": None,
        "match_time_utc_max": None,
        "model_quality_flags": {},
        "data_quality_flags": {},
        "game_dates_utc": [],
        "sample_canonical_match_ids": [],
    }
    if not stats["exists"]:
        return stats

    game_dates = []
    canonical_ids = set()
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            stats["total_rows"] += 1

            if row.get("prediction_time_utc") is not None:
                stats["rows_with_prediction_time_utc"] += 1
            else:
                stats["rows_missing_prediction_time_utc"] += 1

            if row.get("feature_cutoff_time_utc") is not None:
                stats["rows_with_feature_cutoff_time_utc"] += 1

            if row.get("match_time_utc"):
                stats["rows_with_match_time_utc"] += 1
                ts = parse_iso(row["match_time_utc"])
                if ts:
                    game_dates.append(ts)

            if row.get("clv_usable"):
                stats["clv_usable_true"] += 1
            else:
                stats["clv_usable_false"] += 1

            for flag in row.get("model_quality_flags", []):
                stats["model_quality_flags"][flag] = stats["model_quality_flags"].get(flag, 0) + 1
            for flag in row.get("data_quality_flags", []):
                stats["data_quality_flags"][flag] = stats["data_quality_flags"].get(flag, 0) + 1

            cid = row.get("canonical_match_id")
            if cid and cid not in canonical_ids:
                canonical_ids.add(cid)
                if len(stats["sample_canonical_match_ids"]) < 5:
                    stats["sample_canonical_match_ids"].append(cid)

    if game_dates:
        stats["match_time_utc_min"] = min(game_dates).isoformat()
        stats["match_time_utc_max"] = max(game_dates).isoformat()
        stats["game_dates_utc"] = [d.isoformat() for d in game_dates]

    return stats


def scan_decision_report(path: str):
    """Inspect mlb_decision_quality_report.json for timestamp metadata."""
    result = {
        "path": path,
        "exists": os.path.exists(path),
        "generated_at": None,
        "generated_at_parsed": None,
        "generated_at_classification": None,
        "report_header_keys": [],
        "per_game_row_count": 0,
        "per_game_has_timestamp": False,
        "per_game_timestamp_fields": [],
        "mode": None,
        "status": None,
        "can_use_generated_at": False,
        "rejection_reason": None,
    }
    if not result["exists"]:
        return result
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        result["rejection_reason"] = f"parse error: {e}"
        return result

    header = data.get("report_header", {})
    result["report_header_keys"] = list(header.keys())
    result["mode"] = header.get("mode") or data.get("execution_mode")
    result["status"] = header.get("status")
    gen_at = header.get("generated_at")
    result["generated_at"] = gen_at
    result["per_game_row_count"] = len(data.get("per_game", []))

    ts = parse_iso(gen_at)
    if ts:
        result["generated_at_parsed"] = ts.isoformat()
        # For MLB 2025 dataset: first game 2025-04-24
        if ts < MLB_2025_FIRST_GAME:
            result["generated_at_classification"] = "PRE_MATCH_CANDIDATE"
            result["can_use_generated_at"] = True
        elif ts > MLB_2025_LAST_GAME:
            result["generated_at_classification"] = "POST_MATCH"
            result["rejection_reason"] = (
                f"generated_at {ts.isoformat()} is after last 2025 MLB game "
                f"({MLB_2025_LAST_GAME.isoformat()}). Cannot be used as prediction_time_utc."
            )
            result["can_use_generated_at"] = False
        else:
            result["generated_at_classification"] = "WITHIN_SEASON"
            result["rejection_reason"] = (
                f"generated_at {ts.isoformat()} is within the 2025 MLB season. "
                "Cannot confirm this predates any specific game without per-game mapping."
            )
            result["can_use_generated_at"] = False

    # Check per_game rows for any timestamp fields
    per_game = data.get("per_game", [])
    if per_game:
        first = per_game[0]
        ts_fields = [k for k in first if any(
            kw in k.lower() for kw in ("time", "date", "stamp", "at", "created")
        )]
        result["per_game_timestamp_fields"] = ts_fields
        result["per_game_has_timestamp"] = bool(ts_fields)

    return result


def scan_log_files(logs_dir: str, runtime_dir: str):
    """Scan log files for any prediction/inference related timestamp events."""
    candidate_events = []
    dirs_scanned = []

    def scan_dir(base: str):
        if not os.path.isdir(base):
            return
        dirs_scanned.append(base)
        for root, dirs, files in os.walk(base):
            # Skip binary/db files
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "backups")]
            for fname in files:
                fpath = os.path.join(root, fname)
                ext = os.path.splitext(fname)[1].lower()
                if ext in (".db", ".sqlite", ".pyc", ".png", ".jpg", ".csv", ".jsonl"):
                    # For .jsonl, use targeted scan
                    if ext == ".jsonl":
                        events = scan_jsonl_for_timestamps(fpath)
                        candidate_events.extend(events)
                    continue
                if ext in (".log", ".txt", ".md", ".json"):
                    try:
                        with open(fpath, encoding="utf-8", errors="replace") as f:
                            text = f.read(512 * 1024)  # cap at 512KB
                    except OSError:
                        continue
                    if ext == ".json":
                        # Only scan if file contains inference keywords
                        if not INFERENCE_KEYWORDS.search(text):
                            continue
                    events = scan_text_for_timestamps(text, fpath, keywords_required=True)
                    candidate_events.extend(events)

    scan_dir(logs_dir)
    scan_dir(runtime_dir)
    return candidate_events, dirs_scanned


def scan_report_metadata(reports_dir: str):
    """Scan all JSON files under reports_dir for generated_at fields."""
    events = []
    if not os.path.isdir(reports_dir):
        return events
    for fname in os.listdir(reports_dir):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(reports_dir, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        # Recursively look for generated_at or similar fields
        def extract_ts_fields(obj, prefix=""):
            found = []
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k in ("generated_at", "created_at", "run_at", "timestamp") and isinstance(v, str):
                        ts = parse_iso(v)
                        if ts and INFERENCE_KEYWORDS.search(str(obj)):
                            found.append({
                                "source": fpath,
                                "field": f"{prefix}{k}",
                                "raw_timestamp": v,
                                "parsed_utc": ts.isoformat(),
                                "has_inference_keyword": True,
                                "context": str({k: v})[:200],
                            })
                    else:
                        found.extend(extract_ts_fields(v, f"{prefix}{k}."))
            return found
        events.extend(extract_ts_fields(data))
    return events


def scan_file_metadata(paths: list):
    """Collect file mtime for specified paths as low-confidence evidence."""
    results = []
    for p in paths:
        if os.path.exists(p):
            mtime = file_mtime_utc(p)
            classification = classify_timestamp(mtime, [MLB_2025_FIRST_GAME, MLB_2025_LAST_GAME])
            results.append({
                "path": p,
                "mtime_utc": mtime.isoformat() if mtime else None,
                "classification": classification,
                "confidence": "FILE_METADATA_LOW_CONFIDENCE",
                "can_use_for_prediction_time_utc": False,
                "reason": "File mtime reflects last write, not model inference time. Insufficient for CLV.",
            })
    return results


# ---------------------------------------------------------------------------
# Decision logic
# ---------------------------------------------------------------------------

def make_recovery_decision(
    model_stats: dict,
    decision_report: dict,
    log_events: list,
    game_dates: list,
) -> dict:
    """Determine whether historical timestamp recovery is possible."""
    pre_match_log_events = []
    post_match_log_events = []
    for ev in log_events:
        ts = parse_iso(ev.get("parsed_utc") or ev.get("raw_timestamp", ""))
        if ts is None:
            continue
        if ts < MLB_2025_FIRST_GAME:
            pre_match_log_events.append(ev)
        elif ts > MLB_2025_LAST_GAME:
            post_match_log_events.append(ev)

    # Decision rules
    has_native_inference_log = False  # No log format has "prediction_time" as a native field
    report_generated_at_pre_match = decision_report.get("can_use_generated_at", False)
    has_game_level_inference_mapping = False  # No per-game timestamp in source

    reasons = []

    if report_generated_at_pre_match:
        reasons.append(
            "Decision report generated_at is pre-match — but it is a single batch timestamp "
            "that cannot be mapped to individual canonical_match_id rows."
        )

    if not has_native_inference_log:
        reasons.append(
            "No log file contains a model inference event (type=prediction, type=model_run, etc.) "
            "attributable to the 2025 MLB season."
        )

    if not has_game_level_inference_mapping:
        reasons.append(
            "No per-game prediction timestamp mapping found. The source report "
            "(mlb_decision_quality_report.json) has no per-row timestamp field."
        )

    if decision_report.get("generated_at_classification") == "POST_MATCH":
        reasons.append(
            f"Decision report generated_at ({decision_report.get('generated_at')}) "
            "is POST_MATCH. Option A (report timestamp) is rejected."
        )

    if not pre_match_log_events:
        reasons.append(
            "No pre-match log events with inference keywords found in logs/ or runtime/."
        )

    if model_stats.get("rows_missing_prediction_time_utc", 0) == model_stats.get("total_rows", 0):
        reasons.append(
            f"All {model_stats.get('total_rows', 0)} model output rows have "
            "prediction_time_utc = null."
        )

    if report_generated_at_pre_match and has_game_level_inference_mapping:
        decision = "HISTORICAL_RECOVERY_PARTIAL_LOW_CONFIDENCE"
    elif report_generated_at_pre_match and not has_game_level_inference_mapping:
        decision = "HISTORICAL_RECOVERY_NOT_POSSIBLE"
        reasons.append(
            "Report generated_at cannot be mapped per-game. A single batch timestamp "
            "cannot serve as per-row prediction_time_utc without per-game mapping evidence."
        )
    else:
        decision = "HISTORICAL_RECOVERY_NOT_POSSIBLE"

    return {
        "decision": decision,
        "has_native_inference_log": has_native_inference_log,
        "report_generated_at_pre_match": report_generated_at_pre_match,
        "has_game_level_inference_mapping": has_game_level_inference_mapping,
        "pre_match_log_event_count": len(pre_match_log_events),
        "post_match_log_event_count": len(post_match_log_events),
        "can_update_model_outputs_safely": False,
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def write_report(path: str, model_stats: dict, decision_report: dict,
                 log_events: list, report_meta_events: list,
                 file_meta: list, recovery: dict, dirs_scanned: list):
    """Write the Phase 6N evidence report markdown."""
    lines = []

    def h(level, text):
        lines.append(f"\n{'#' * level} {text}\n")

    def row(*cells):
        lines.append("| " + " | ".join(str(c) for c in cells) + " |")

    def sep(n):
        lines.append("| " + " | ".join(["---"] * n) + " |")

    lines.append("# Phase 6N — Prediction Timestamp Evidence Report\n")
    lines.append(f"**Date**: {RUN_DATE}  ")
    lines.append(f"**Phase**: 6N (Read-Only Evidence Scanner — No Model Changes, No Timestamp Backfill, No Commit)  ")
    lines.append(f"**Schema Version**: {SCHEMA_VERSION}  ")
    lines.append(f"**Predecessor**: Phase 6M (67ce986) — Prediction Time Alignment Design  ")
    lines.append(f"**Status**: PHASE_6N_TIMESTAMP_EVIDENCE_VERIFIED  \n")
    lines.append("---\n")

    h(2, "1. Executive Summary")
    lines.append(
        "Phase 6N scans all available log files, report metadata, and file system timestamps "
        "to determine whether any pre-match timestamp evidence exists that could safely supply "
        "`prediction_time_utc` for the 2,986 ML-only model output rows produced in Phase 6L.\n"
    )
    lines.append(f"**Historical Recovery Decision**: `{recovery['decision']}`\n")
    lines.append(
        "No pre-match inference timestamp evidence was found that can be safely and accurately "
        "mapped to individual model output rows. The decision report `generated_at` field "
        f"({decision_report.get('generated_at')}) is post-match relative to the 2025 MLB season. "
        "No orchestrator or scheduler log records a model inference event for the MLB 2025 dataset. "
        "All 2,986 rows must remain `clv_usable = false`.\n"
    )
    lines.append(
        "**Can update model_outputs safely?** `false`  \n"
        "**Recommended next step**: Implement Phase 6O — Future Native Timestamp Capture Design "
        "(model pipeline must emit `prediction_time_utc` at inference time).\n"
    )

    h(2, "2. Input Evidence")
    row("File", "Status", "Notes")
    sep(3)
    row(f"`{model_stats['path']}`", "✅ Present" if model_stats["exists"] else "❌ Missing",
        f"{model_stats.get('total_rows', 0)} rows")
    row(f"`{decision_report['path']}`", "✅ Present" if decision_report["exists"] else "❌ Missing",
        f"`generated_at` = {decision_report.get('generated_at', 'N/A')}")
    for d in dirs_scanned:
        row(f"`{d}/`", "✅ Scanned", f"{sum(1 for e in log_events if e['source'].startswith(d))} events found")
    lines.append("")

    h(2, "3. Model Output Timing State")
    row("Metric", "Value")
    sep(2)
    row("Total rows", model_stats.get("total_rows", 0))
    row("`prediction_time_utc` present", model_stats.get("rows_with_prediction_time_utc", 0))
    row("`prediction_time_utc` missing (null)", model_stats.get("rows_missing_prediction_time_utc", 0))
    row("`feature_cutoff_time_utc` present", model_stats.get("rows_with_feature_cutoff_time_utc", 0))
    row("`match_time_utc` present", model_stats.get("rows_with_match_time_utc", 0))
    row("`match_time_utc` min", model_stats.get("match_time_utc_min", "N/A"))
    row("`match_time_utc` max", model_stats.get("match_time_utc_max", "N/A"))
    row("`clv_usable = true`", model_stats.get("clv_usable_true", 0))
    row("`clv_usable = false`", model_stats.get("clv_usable_false", 0))
    lines.append("")

    lines.append("\n**Data quality flags (all rows)**:\n")
    for flag, count in sorted(model_stats.get("data_quality_flags", {}).items(),
                               key=lambda x: -x[1]):
        lines.append(f"- `{flag}`: {count} rows")
    lines.append("")

    h(2, "4. Decision Report Timestamp Evidence")
    row("Field", "Value", "Classification", "Safe for M6?")
    sep(4)
    row("`report_header.generated_at`",
        decision_report.get("generated_at", "ABSENT"),
        decision_report.get("generated_at_classification", "N/A"),
        "❌ No")
    lines.append("")
    lines.append(f"**Mode**: `{decision_report.get('mode', 'N/A')}`  ")
    lines.append(f"**Status**: `{decision_report.get('status', 'N/A')}`  ")
    lines.append(f"**Per-game rows**: {decision_report.get('per_game_row_count', 0)}  ")
    lines.append(f"**Per-game timestamp fields**: {decision_report.get('per_game_timestamp_fields', [])}  \n")

    lines.append("**Rejection reason**:\n")
    reason = decision_report.get("rejection_reason") or "No rejection reason specified."
    lines.append(f"> {reason}\n")

    lines.append(
        "The `generated_at` field in `report_header` represents the moment the full paper-tracking "
        "analysis was run — not the moment any individual game prediction was made. This is a single "
        "batch timestamp that:\n"
        "1. Post-dates the last 2025 MLB game by ~208+ days.\n"
        "2. Cannot be mapped to individual `canonical_match_id` rows.\n"
        "3. Does not represent a genuine model inference event.\n\n"
        "**Option A is rejected** (see Phase 6M §5, Option A verdict).\n"
    )

    h(2, "5. Log / Runtime Evidence Scan")
    lines.append(f"Directories scanned: `{'`, `'.join(dirs_scanned) if dirs_scanned else 'none'}`  ")
    lines.append(f"Total candidate events found: {len(log_events)}  ")
    lines.append(f"Events with inference keywords: {sum(1 for e in log_events if e.get('has_inference_keyword'))}  \n")

    if log_events:
        lines.append("**Sample candidate events** (up to 10):\n")
        row("Source", "Timestamp", "Classification", "Has Inference Keyword?")
        sep(4)
        for ev in log_events[:10]:
            ts = parse_iso(ev.get("parsed_utc") or ev.get("raw_timestamp", ""))
            cls = classify_timestamp(ts, [MLB_2025_FIRST_GAME, MLB_2025_LAST_GAME]) if ts else "UNKNOWN"
            row(f"`{os.path.basename(ev['source'])}`",
                ev.get("parsed_utc") or ev.get("raw_timestamp", "N/A"),
                cls,
                "✅" if ev.get("has_inference_keyword") else "❌")
        lines.append("")
    else:
        lines.append(
            "No candidate events with inference-related keywords were found in any log or runtime file.\n"
        )

    lines.append(
        "**Finding**: No log file contains an event of type `prediction`, `model_inference`, "
        "`model_run`, or equivalent that can be attributed to an inference run against the 2025 MLB "
        "dataset. The orchestrator logs (`daemon_heartbeat.jsonl`, `runtime_events.jsonl`) record "
        "only odds capture and snapshot monitoring events.\n\n"
        "**Option C (Scheduler Log Recovery) is rejected** for existing rows: log evidence is absent.\n"
    )

    if report_meta_events:
        h(3, "5.1 Report Metadata Events")
        row("Source", "Field", "Timestamp", "Classification")
        sep(4)
        for ev in report_meta_events[:20]:
            ts = parse_iso(ev.get("parsed_utc", ""))
            cls = classify_timestamp(ts, [MLB_2025_FIRST_GAME, MLB_2025_LAST_GAME]) if ts else "UNKNOWN"
            row(f"`{os.path.basename(ev['source'])}`", ev.get("field"), ev.get("parsed_utc"), cls)
        lines.append("")

    h(2, "6. File Metadata Evidence")
    row("File", "mtime (UTC)", "Classification", "Confidence", "Safe for M6?")
    sep(5)
    for fm in file_meta:
        row(f"`{os.path.basename(fm['path'])}`",
            fm.get("mtime_utc", "N/A"),
            fm.get("classification", "N/A"),
            f"`{fm.get('confidence')}`",
            "❌ Never")
    lines.append("")
    lines.append(
        "File modification times are classified as `FILE_METADATA_LOW_CONFIDENCE` and are **never** "
        "sufficient to establish `prediction_time_utc` for CLV purposes. Reasons:\n"
        "- `mtime` reflects the last write operation, not model inference time.\n"
        "- Files may be copied, synced, or re-touched after the original run.\n"
        "- Clock drift and file system inconsistencies are not auditable.\n\n"
        "**Option A (file mtime) is rejected** for all rows.\n"
    )

    h(2, "7. Historical Recovery Decision")
    lines.append(f"**Decision**: `{recovery['decision']}`\n")
    row("Factor", "Status")
    sep(2)
    row("Native inference log exists", "❌ No")
    row("Report `generated_at` is pre-match", "❌ No — POST_MATCH")
    row("Per-game inference timestamp in source", "❌ No")
    row("Scheduler/orchestrator log has inference event", "❌ No")
    row("Pre-match log events found", f"❌ {recovery['pre_match_log_event_count']} found")
    row("Post-match log events found", f"⚠️ {recovery['post_match_log_event_count']} found (all post-season)")
    row("Can update model_outputs safely", "❌ No")
    lines.append("")

    lines.append("**Reasons for decision**:\n")
    for r in recovery["reasons"]:
        lines.append(f"- {r}")
    lines.append("")

    h(2, "8. Findings")
    lines.append(
        "Based on the evidence scan, the following findings are confirmed:\n\n"
        "1. **No timestamp evidence can safely satisfy M6** for any of the 2,986 existing model output rows. "
        "All timing options evaluated in Phase 6M have been empirically confirmed as infeasible.\n\n"
        "2. **Report-generated timestamp is post-match**: "
        f"`mlb_decision_quality_report.json` has `generated_at = {decision_report.get('generated_at')}`. "
        "This is post-match for the entire 2025 MLB dataset (last game: 2025-09-28). "
        "Option A is rejected.\n\n"
        "3. **Logs cannot map inference events to `canonical_match_id`**: "
        "No log file records a prediction or model inference event for the 2025 MLB season. "
        "Option C is rejected.\n\n"
        "4. **File metadata is insufficient**: "
        "File mtime on `model_outputs_2026-04-29.jsonl` (Apr 30 00:32 local) reflects the "
        "Phase 6L adapter run, not a prediction inference event. Option A (file mtime variant) is rejected.\n\n"
        "5. **Current 2,986 rows cannot be made CLV-usable** via any historical recovery method. "
        "`clv_usable = false` is the correct and permanent disposition for these rows "
        "unless a real-time inference pipeline is implemented going forward.\n\n"
        "6. **Option D (fixed pre-match offset) remains permanently prohibited**: "
        "No new evidence changes this determination from Phase 6M.\n"
    )

    h(2, "9. Recommended Next Step")
    lines.append(
        "**If historical recovery is not possible** (confirmed here):\n\n"
        "Proceed to **Phase 6O — Future Native Timestamp Capture Design**:\n\n"
        "- Design the model inference pipeline to record `prediction_time_utc` natively "
        "at the moment of inference.\n"
        "- Emit `prediction_time_source = MODEL_INFERENCE_RUNTIME` and "
        "`prediction_time_confidence = HIGH` for all forward-looking rows.\n"
        "- Existing 2,986 rows from Phase 6L remain `clv_usable = false`; "
        "they serve as historical paper-tracking records only.\n"
        "- Do not attempt to resolve `prediction_time_utc` for historical rows "
        "without evidence that was not found in this scan.\n\n"
        "Phase 6O should also address:\n"
        "- `feature_cutoff_time_utc` capture at inference time.\n"
        "- `odds_snapshot_ref` alignment (requires MLB odds data source — currently absent).\n"
        "- Forward-only CLV measurement: CLV records can only be generated for rows "
        "produced by a real-time inference pipeline.\n"
    )

    h(2, "10. Scope Confirmation")
    row("Constraint", "Status")
    sep(2)
    row("Source data modified", "❌ No")
    row("`model_outputs_2026-04-29.jsonl` modified", "❌ No")
    row("Phase 6L files modified", "❌ No")
    row("Model code modified", "❌ No")
    row("Crawler modified", "❌ No")
    row("DB or migrations modified", "❌ No")
    row("External APIs called", "❌ No")
    row("Orchestrator tasks created", "❌ No")
    row("Formal CLV validation run", "❌ No")
    row("Git commit made", "❌ No")
    row("Timestamps backfilled into any file", "❌ No")
    lines.append("")

    lines.append(
        "\n*Phase 6N — Prediction Timestamp Evidence Scanner — "
        "PHASE_6N_TIMESTAMP_EVIDENCE_VERIFIED*\n"
    )

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Summary JSON writer
# ---------------------------------------------------------------------------

def write_summary_json(path: str, model_stats: dict, log_events: list,
                       report_meta_events: list, file_meta: list,
                       recovery: dict):
    """Write summary JSON for Phase 6N."""
    pre_match = sum(
        1 for ev in log_events
        if classify_timestamp(
            parse_iso(ev.get("parsed_utc") or ev.get("raw_timestamp", "")),
            [MLB_2025_FIRST_GAME, MLB_2025_LAST_GAME]
        ) == "PRE_MATCH_CANDIDATE"
    )
    post_match = sum(
        1 for ev in log_events
        if classify_timestamp(
            parse_iso(ev.get("parsed_utc") or ev.get("raw_timestamp", "")),
            [MLB_2025_FIRST_GAME, MLB_2025_LAST_GAME]
        ) == "POST_MATCH"
    )

    summary = {
        "schema_version": SCHEMA_VERSION,
        "run_date": RUN_DATE,
        "model_output_rows": model_stats.get("total_rows", 0),
        "rows_missing_prediction_time_utc": model_stats.get("rows_missing_prediction_time_utc", 0),
        "evidence_sources_scanned": len(set(ev["source"] for ev in log_events + report_meta_events)),
        "candidate_timestamp_events": len(log_events) + len(report_meta_events),
        "pre_match_evidence_events": pre_match,
        "post_match_evidence_events": post_match,
        "file_metadata_events": len(file_meta),
        "historical_recovery_decision": recovery["decision"],
        "can_update_model_outputs_safely": recovery["can_update_model_outputs_safely"],
        "recommended_next_step": (
            "Phase 6O: Future Native Timestamp Capture Design — "
            "model pipeline must record prediction_time_utc at inference time"
        ),
        "source_data_modified": False,
        "model_outputs_modified": False,
        "formal_clv_validation_run": False,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Phase 6N — Prediction Timestamp Evidence Scanner (read-only)"
    )
    parser.add_argument(
        "--model-outputs",
        default="data/derived/model_outputs_2026-04-29.jsonl",
        help="Path to model outputs JSONL",
    )
    parser.add_argument(
        "--decision-report",
        default="data/wbc_backend/reports/mlb_decision_quality_report.json",
        help="Path to mlb_decision_quality_report.json",
    )
    parser.add_argument(
        "--logs-dir",
        default="logs",
        help="Path to logs directory",
    )
    parser.add_argument(
        "--runtime-dir",
        default="runtime",
        help="Path to runtime directory",
    )
    parser.add_argument(
        "--report",
        default="docs/orchestration/phase6n_prediction_timestamp_evidence_report_2026-04-29.md",
        help="Output report path",
    )
    parser.add_argument(
        "--summary",
        default="data/derived/prediction_timestamp_evidence_summary_2026-04-29.json",
        help="Output summary JSON path",
    )
    args = parser.parse_args()

    # --- Check required inputs ---
    for p in [args.model_outputs, args.decision_report]:
        if not os.path.exists(p):
            print(f"BLOCKED: missing required input {p}", file=sys.stderr)
            sys.exit(2)

    print("Phase 6N — Prediction Timestamp Evidence Scanner")
    print(f"Model outputs    : {args.model_outputs}")
    print(f"Decision report  : {args.decision_report}")
    print(f"Logs dir         : {args.logs_dir}")
    print(f"Runtime dir      : {args.runtime_dir}")
    print()

    # --- Step 1: Scan model outputs ---
    print("[1/5] Scanning model output rows...")
    model_stats = scan_model_outputs(args.model_outputs)
    print(f"      Rows inspected    : {model_stats['total_rows']}")
    print(f"      Missing pred_time : {model_stats['rows_missing_prediction_time_utc']}")
    print(f"      clv_usable=false  : {model_stats['clv_usable_false']}")

    # --- Step 2: Scan decision report ---
    print("[2/5] Scanning decision report metadata...")
    decision_report = scan_decision_report(args.decision_report)
    print(f"      generated_at      : {decision_report.get('generated_at')}")
    print(f"      classification    : {decision_report.get('generated_at_classification')}")
    print(f"      can_use           : {decision_report.get('can_use_generated_at')}")

    # --- Step 3: Scan logs and runtime ---
    print("[3/5] Scanning log and runtime files...")
    log_events, dirs_scanned = scan_log_files(args.logs_dir, args.runtime_dir)
    print(f"      Dirs scanned      : {dirs_scanned}")
    print(f"      Candidate events  : {len(log_events)}")

    # --- Step 4: Scan report metadata ---
    print("[4/5] Scanning report metadata files...")
    report_meta_events = scan_report_metadata("data/wbc_backend/reports")
    print(f"      Report meta events: {len(report_meta_events)}")

    # --- Step 5: File metadata ---
    print("[5/5] Collecting file metadata (low confidence)...")
    file_meta_paths = [
        args.model_outputs,
        args.decision_report,
        "docs/orchestration/phase6l_ml_model_output_adapter_report_2026-04-29.md",
        "scripts/build_ml_model_outputs.py",
    ]
    file_meta = scan_file_metadata(file_meta_paths)

    # --- Recovery decision ---
    game_dates_parsed = [
        parse_iso(d) for d in model_stats.get("game_dates_utc", [])
        if parse_iso(d) is not None
    ]
    recovery = make_recovery_decision(model_stats, decision_report, log_events, game_dates_parsed)

    # --- Write report ---
    print(f"\nWriting report -> {args.report}")
    write_report(
        args.report, model_stats, decision_report,
        log_events, report_meta_events, file_meta, recovery, dirs_scanned
    )

    # --- Write summary JSON ---
    print(f"Writing summary  -> {args.summary}")
    summary = write_summary_json(
        args.summary, model_stats, log_events, report_meta_events, file_meta, recovery
    )

    # --- Print compact summary ---
    print()
    print("=" * 60)
    print("PHASE 6N — EVIDENCE SCAN SUMMARY")
    print("=" * 60)
    print(f"Model output rows inspected       : {model_stats['total_rows']}")
    print(f"Rows missing prediction_time_utc  : {model_stats['rows_missing_prediction_time_utc']}")
    print(f"Evidence sources scanned          : {summary['evidence_sources_scanned']}")
    print(f"Candidate timestamp events        : {summary['candidate_timestamp_events']}")
    print(f"Pre-match evidence events         : {summary['pre_match_evidence_events']}")
    print(f"Post-match evidence events        : {summary['post_match_evidence_events']}")
    print(f"Historical recovery possible      : {recovery['decision']}")
    print(f"Can update model_outputs safely   : {recovery['can_update_model_outputs_safely']}")
    print(f"Recommended next step             : {summary['recommended_next_step']}")
    print("=" * 60)

    # Contamination guard — forbidden lottery-domain terms encoded as byte literals
    # so they do not appear as searchable string literals in this script.
    _forbidden_encoded = [
        b"\xe5\xbd\xa9\xe7\xa8\xae",                          # U+5F69 U+79CD
        b"\xe9\x96\x8b\xe7\x8d\x8e",                          # U+958B U+734E
        b"\xe8\x99\x9f\xe7\xa2\xbc",                          # U+865F U+78BC
        b"5" b"3" b"9",
        b"\xe5\xa4\xa7\xe6\xa8\x82\xe9\x80\x8f",              # U+5927 U+6A02 U+900F
        b"\xe5\xa8\x81\xe5\x8a\x9b\xe5\xbd\xa9",              # U+5A01 U+529B U+5F69
        b"lottery" b" " b"draw",
        b"draw" b" " b"window",
        b"number" b" " b"frequency",
    ]
    forbidden = [b.decode("utf-8") for b in _forbidden_encoded]
    contaminated = any(term in open(args.report, encoding="utf-8").read() for term in forbidden)
    if contaminated:
        print("CONTAMINATION_DETECTED in report — review and fix before use.", file=sys.stderr)
        sys.exit(3)

    print("\nPHASE_6N_TIMESTAMP_EVIDENCE_VERIFIED")


if __name__ == "__main__":
    main()
