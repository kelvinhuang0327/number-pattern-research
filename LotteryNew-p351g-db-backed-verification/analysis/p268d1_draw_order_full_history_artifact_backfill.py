"""P268D-1: drawNumberAppear full-history artifact-store backfill (bounded-rate prototype).

This script implements step 2 of the P268C plan
(`outputs/research/p268c_draw_order_full_history_feasibility_and_hypothesis_design_20260610.json`,
`p268d_implementation_order` step 2: `bounded_rate_full_history_fetcher`).

Hard constraints (per task authorization):
  - NO production DB write. `data/lottery_v2.db` is never opened by this
    script.
  - NO Hypothesis Registry write. The companion registry-freeze artifact
    (`p268d1_draw_order_registry_freeze_20260610.json`) is a snapshot under
    `outputs/research/`, NOT a write to
    `lottery_api/data/hypothesis_registry.jsonl`.
  - NO H1/H2/H3 statistical test, NO permutation test, NO p-value, NO
    strategy generation, NO hit-rate / success-rate-improvement claim.
    Those are reserved for a separate, future, explicitly-authorized
    confirmatory task (P268D-3).
  - Bounded-rate, resumable: a per-run call cap (`MAX_CALLS_PER_RUN`) limits
    how many months are fetched in a single invocation. A checkpoint ledger
    (`p268d1_draw_order_full_history_artifact_backfill_20260610.ledger.json`)
    tracks (month, lottery_type) completion so subsequent runs resume rather
    than re-fetch.
  - On endpoint instability, a (month, lottery_type) cell is marked `ERROR`
    (not retried aggressively) and the overall run is reported `PARTIAL`. No
    fake/mock data is substituted.

Output artifact store (append-only JSONL, NOT the production DB):
  - `outputs/research/p268d1_draw_order_full_history_artifact_backfill_20260610.jsonl`
    one validated record per line.
  - `outputs/research/p268d1_draw_order_full_history_artifact_backfill_20260610.ledger.json`
    (month x lottery_type) completion ledger.
  - `outputs/research/p268d1_draw_order_full_history_artifact_backfill_20260610.summary.json`
    run summary (coverage, counts, schema drift, limitations, next step).
  - `outputs/research/p268d1_draw_order_full_history_artifact_backfill_20260610.md`
    human-readable rendering of the summary.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "outputs" / "research"

JSONL_PATH = OUT_DIR / "p268d1_draw_order_full_history_artifact_backfill_20260610.jsonl"
LEDGER_PATH = OUT_DIR / "p268d1_draw_order_full_history_artifact_backfill_20260610.ledger.json"
SUMMARY_PATH = OUT_DIR / "p268d1_draw_order_full_history_artifact_backfill_20260610.summary.json"
MD_PATH = OUT_DIR / "p268d1_draw_order_full_history_artifact_backfill_20260610.md"

API_BASE = "https://api.taiwanlottery.com/TLCAPIWeB/Lottery"
TIMEOUT_SECONDS = 20

# Bounded-rate: hard cap on the number of HTTP fetches performed in a single
# run. Sequential, single-in-flight (no concurrency). Chosen so one run
# completes within a normal tool-call timeout while still making forward
# progress on a full-history backfill across many runs.
MAX_CALLS_PER_RUN = 60

# Full-history target range. End month chosen to match the months already
# verified live in P268A/P268B; this script does not assume any month beyond
# what has been previously confirmed reachable.
START_MONTH = "2007-01"
END_MONTH = "2026-05"

# Game definitions, identical to P268B
# (analysis/p268b_official_draw_order_positional_bias_audit.py) for
# consistency of lottery_type / endpoint / array_key / pool definitions.
GAMES = {
    "BIG_LOTTO": {
        "endpoint": "Lotto649Result",
        "array_key": "lotto649Res",
        "expected_appear_len": 7,
        "main_count": 6,
        "has_size_field": True,
    },
    "POWER_LOTTO": {
        "endpoint": "SuperLotto638Result",
        "array_key": "superLotto638Res",
        "expected_appear_len": 7,
        "main_count": 6,
        "has_size_field": True,
    },
    "DAILY_539": {
        "endpoint": "Daily539Result",
        "array_key": "daily539Res",
        "expected_appear_len": 5,
        "main_count": 5,
        "has_size_field": True,
    },
    "3_STAR": {
        "endpoint": "3DResult",
        "array_key": "lotto3DRes",
        "expected_appear_len": 3,
        "main_count": 3,
        "has_size_field": False,
    },
    "4_STAR": {
        "endpoint": "4DResult",
        "array_key": "lotto4DRes",
        "expected_appear_len": 4,
        "main_count": 4,
        "has_size_field": False,
    },
}


def month_range(start: str, end: str) -> list[str]:
    """Inclusive list of "YYYY-MM" strings from start to end."""
    sy, sm = (int(x) for x in start.split("-"))
    ey, em = (int(x) for x in end.split("-"))
    months = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            m = 1
            y += 1
    return months


def fetch_month(endpoint: str, month: str, page_size: int = 31) -> dict:
    """Fetch one month of results from the official TLCAPIWeB endpoint.

    Uses `curl` rather than `urllib`, per the P268B precedent
    (analysis/p268b_official_draw_order_positional_bias_audit.py): this
    environment's Python/OpenSSL rejects the official cert chain with
    "[SSL: CERTIFICATE_VERIFY_FAILED] ... Missing Subject Key Identifier",
    while curl verifies it successfully via the system CA store. This is a
    real, verified-live, unauthenticated public endpoint, not mock data.
    """
    url = f"{API_BASE}/{endpoint}?period&month={month}&pageNum=1&pageSize={page_size}"
    result = subprocess.run(
        ["curl", "-s", "--max-time", str(TIMEOUT_SECONDS), "-A", "Mozilla/5.0", url],
        capture_output=True,
        timeout=TIMEOUT_SECONDS + 5,
        check=False,
    )
    if result.returncode != 0:
        raise OSError(f"curl exited {result.returncode}: {result.stderr.decode('utf-8', 'replace')}")
    if not result.stdout:
        raise OSError("curl returned empty response")
    return json.loads(result.stdout.decode("utf-8"))


def build_full_ledger() -> list[dict]:
    ledger = []
    for month in month_range(START_MONTH, END_MONTH):
        for lottery_type in GAMES:
            ledger.append(
                {
                    "month": month,
                    "lottery_type": lottery_type,
                    "status": "PENDING",
                    "records_fetched": None,
                    "error": None,
                }
            )
    return ledger


def load_ledger() -> tuple[list[dict], bool]:
    """Return (ledger, is_new). Loads existing ledger if present, else builds
    a fresh full-coverage ledger with all cells PENDING."""
    if LEDGER_PATH.exists():
        with open(LEDGER_PATH, encoding="utf-8") as fh:
            return json.load(fh)["ledger"], False
    return build_full_ledger(), True


def validate_record(rec: dict, lottery_type: str, cfg: dict, month: str) -> dict:
    expected_len = cfg["expected_appear_len"]
    main_count = cfg["main_count"]

    appear = rec.get("drawNumberAppear")
    appear_present = appear is not None
    appear_is_int_seq = appear_present and isinstance(appear, list) and all(isinstance(x, int) for x in appear)
    correct_length = appear_is_int_seq and len(appear) == expected_len

    sorted_matches_size = None
    size = rec.get("drawNumberSize")
    if cfg["has_size_field"] and size is not None and appear_is_int_seq:
        sorted_matches_size = (
            isinstance(size, list)
            and len(size) >= main_count
            and len(appear) >= main_count
            and sorted(appear[:main_count]) == sorted(size[:main_count])
        )

    return {
        "lottery_type": lottery_type,
        "month": month,
        "period": rec.get("period"),
        "draw_date": rec.get("lotteryDate") or rec.get("dDate") or rec.get("drawDate"),
        "drawNumberAppear": appear,
        "drawNumberSize": size,
        "validation": {
            "drawNumberAppear_present": appear_present,
            "parsed_as_ordered_int_sequence": appear_is_int_seq,
            "correct_length": correct_length,
            "expected_length": expected_len,
            "sorted_appear_matches_drawNumberSize": sorted_matches_size,
        },
    }


def main() -> dict:
    ledger, is_new_ledger = load_ledger()
    ledger_by_key = {(e["month"], e["lottery_type"]): e for e in ledger}

    # Resume order: chronological months (ascending), then GAMES dict order
    # within each month, restricted to PENDING cells.
    pending = [
        e
        for e in (
            ledger_by_key[(month, lt)]
            for month in month_range(START_MONTH, END_MONTH)
            for lt in GAMES
        )
        if e["status"] == "PENDING"
    ]

    new_records: list[dict] = []
    calls_made = 0
    months_attempted: set[str] = set()
    games_attempted: set[str] = set()
    schema_drift: list[dict] = []

    for entry in pending:
        if calls_made >= MAX_CALLS_PER_RUN:
            break

        month = entry["month"]
        lottery_type = entry["lottery_type"]
        cfg = GAMES[lottery_type]
        months_attempted.add(month)
        games_attempted.add(lottery_type)

        try:
            payload = fetch_month(cfg["endpoint"], month)
            calls_made += 1
        except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError) as exc:
            entry["status"] = "ERROR"
            entry["error"] = f"{type(exc).__name__}: {exc}"
            continue

        content = payload.get("content") or {}
        records = content.get(cfg["array_key"]) or []

        if not records:
            entry["status"] = "EMPTY"
            entry["records_fetched"] = 0
            entry["error"] = None
            continue

        validated_for_cell = []
        for rec in records:
            v = validate_record(rec, lottery_type, cfg, month)
            validated_for_cell.append(v)
            if not v["validation"]["drawNumberAppear_present"] or not v["validation"]["correct_length"]:
                schema_drift.append(
                    {
                        "lottery_type": lottery_type,
                        "month": month,
                        "period": v["period"],
                        "validation": v["validation"],
                    }
                )

        new_records.extend(validated_for_cell)
        entry["status"] = "DONE"
        entry["records_fetched"] = len(records)
        entry["error"] = None

    # Persist ledger
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(LEDGER_PATH, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "start_month": START_MONTH,
                "end_month": END_MONTH,
                "max_calls_per_run": MAX_CALLS_PER_RUN,
                "ledger": ledger,
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )

    # Append new records to JSONL artifact (resumable, append-only)
    with open(JSONL_PATH, "a", encoding="utf-8") as fh:
        for rec in new_records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # --- Summary ---
    total_cells = len(ledger)
    done_cells = sum(1 for e in ledger if e["status"] == "DONE")
    empty_cells = sum(1 for e in ledger if e["status"] == "EMPTY")
    error_cells = sum(1 for e in ledger if e["status"] == "ERROR")
    pending_cells = sum(1 for e in ledger if e["status"] == "PENDING")

    parsed_ok = sum(1 for r in new_records if r["validation"]["correct_length"])
    parse_fail = len(new_records) - parsed_ok

    missing_months_by_game: dict[str, list[str]] = {lt: [] for lt in GAMES}
    for e in ledger:
        if e["status"] in ("PENDING", "ERROR"):
            missing_months_by_game[e["lottery_type"]].append(e["month"])

    is_complete = pending_cells == 0 and error_cells == 0
    overall_status = "COMPLETE" if is_complete else "PARTIAL"

    summary = {
        "task_id": "P268D1_DRAW_ORDER_FULL_HISTORY_ARTIFACT_BACKFILL",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "p268c_design_artifact": (
            "outputs/research/p268c_draw_order_full_history_feasibility_and_hypothesis_design_20260610.json"
        ),
        "this_run": {
            "max_calls_per_run": MAX_CALLS_PER_RUN,
            "calls_made_this_run": calls_made,
            "months_attempted_this_run": sorted(months_attempted),
            "games_attempted_this_run": sorted(games_attempted),
            "new_records_written_this_run": len(new_records),
            "ledger_was_newly_created": is_new_ledger,
        },
        "coverage": {
            "start_month": START_MONTH,
            "end_month": END_MONTH,
            "games": list(GAMES.keys()),
            "total_ledger_cells": total_cells,
            "done_cells": done_cells,
            "empty_cells": empty_cells,
            "error_cells": error_cells,
            "pending_cells": pending_cells,
        },
        "request_counts": {
            "calls_made_this_run": calls_made,
        },
        "parse_results_this_run": {
            "records_written": len(new_records),
            "correct_length_count": parsed_ok,
            "incorrect_length_or_missing_field_count": parse_fail,
        },
        "schema_drift_this_run": schema_drift[:20],
        "schema_drift_count_this_run": len(schema_drift),
        "missing_months_by_game": missing_months_by_game,
        "limitations": [
            "Bounded-rate prototype: a single run fetches at most "
            f"{MAX_CALLS_PER_RUN} (month, lottery_type) cells; full-history "
            "coverage requires multiple resumed runs.",
            "No production DB write performed; artifacts are append-only "
            "files under outputs/research/.",
            "No Hypothesis Registry write performed; the companion "
            "registry-freeze artifact is a design-snapshot under "
            "outputs/research/, not a write to "
            "lottery_api/data/hypothesis_registry.jsonl.",
            "No H1/H2/H3 statistical test, no permutation test, and no "
            "significance value of any kind computed in this task. "
            "Reserved for a separate, future, explicitly-authorized "
            "confirmatory task (P268D-3).",
            "No success-rate / hit-rate-improvement claim is made by this "
            "artifact.",
            "On endpoint instability a (month, lottery_type) cell is marked "
            "ERROR (not aggressively retried); a future run may retry by "
            "resetting that cell's status to PENDING.",
        ],
        "is_complete": is_complete,
        "overall_status": overall_status,
        "next_step_recommendation": (
            "Re-run this script in additional bounded sessions (resumable "
            "via the ledger) until pending_cells == 0 and error_cells == 0, "
            "then proceed to P268D step 4 (structure_validation aggregate "
            "report) and step 6 (read-only canonical DB alignment), per "
            "p268c ... p268d_implementation_order."
            if not is_complete
            else "Full-history backfill ledger complete; proceed to P268D "
            "step 4 (structure_validation aggregate report) and step 6 "
            "(read-only canonical DB alignment)."
        ),
        "final_classification": (
            "P268D1_DRAW_ORDER_REGISTRY_FREEZE_AND_FULL_HISTORY_ARTIFACT_BACKFILL_COMPLETE"
            if is_complete
            else "P268D1_DRAW_ORDER_REGISTRY_FREEZE_AND_FULL_HISTORY_ARTIFACT_BACKFILL_PARTIAL_API_LIMIT"
        ),
    }

    with open(SUMMARY_PATH, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)

    MD_PATH.write_text(render_markdown(summary), encoding="utf-8")

    return summary


def render_markdown(summary: dict) -> str:
    lines = []
    lines.append("# P268D-1: drawNumberAppear Full-History Artifact Backfill (Bounded-Rate Prototype)")
    lines.append("")
    lines.append(f"Generated: {summary.get('generated_at')}")
    lines.append("")
    lines.append("## Scope & Constraints")
    lines.append("- NO production DB write (`data/lottery_v2.db` never opened by this script).")
    lines.append("- NO Hypothesis Registry write (registry-freeze artifact is a design snapshot under `outputs/research/`).")
    lines.append("- NO H1/H2/H3 statistical test, permutation test, or p-value (reserved for P268D-3).")
    lines.append("- NO hit-rate / success-rate-improvement claim.")
    lines.append("")
    lines.append("## This Run")
    for k, v in summary["this_run"].items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    lines.append("## Coverage")
    for k, v in summary["coverage"].items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    lines.append("## Parse Results (this run)")
    for k, v in summary["parse_results_this_run"].items():
        lines.append(f"- **{k}**: {v}")
    lines.append(f"- **schema_drift_count_this_run**: {summary['schema_drift_count_this_run']}")
    lines.append("")
    lines.append("## Missing Months By Game (PENDING or ERROR)")
    for lt, months in summary["missing_months_by_game"].items():
        n = len(months)
        head = months[:5]
        lines.append(f"- **{lt}**: {n} remaining (first 5: {head})")
    lines.append("")
    lines.append("## Limitations")
    for item in summary["limitations"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Next-Step Recommendation")
    lines.append(summary["next_step_recommendation"])
    lines.append("")
    lines.append("## Final Classification")
    lines.append(summary["final_classification"])
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    summary = main()
    print(f"Final Classification: {summary['final_classification']}")
    sys.exit(0)
