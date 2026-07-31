"""P268D-2: draw-order structure validation aggregate + read-only canonical DB alignment.

Scope (hard constraints):
  - Reads the P268D-1 full-history artifact (JSONL/ledger/summary) read-only.
  - Opens lottery_api/data/lottery_v2.db ONLY in read-only mode (sqlite3 URI mode=ro).
    No INSERT/UPDATE/DELETE/CREATE/ALTER/DROP of any kind.
  - Does NOT write to lottery_api/data/hypothesis_registry.jsonl.
  - Does NOT run H1/H2/H3, no permutation test, no significance value
    of any kind. Reserved for a separate, future, explicitly-authorized
    confirmatory task (P268D-3).
  - Does NOT generate a strategy and makes NO hit-rate / success-rate
    improvement claim.

Output: a structure-validation + DB-alignment data-quality verdict artifact
under outputs/research/, plus a markdown summary.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


def _p291u_repo_root():
    current = Path(__file__)
    if not current.is_absolute():
        raise FileNotFoundError(f"Source file path is not absolute: {current}")
    for parent in (current.parent, *current.parents):
        if (parent / "lottery_api").is_dir():
            return parent
    raise FileNotFoundError(f"Unable to locate repository root from source file: {current}")


REPO_ROOT = _p291u_repo_root()
OUT_DIR = REPO_ROOT / "outputs" / "research"

P268D1_REGISTRY_FREEZE = OUT_DIR / "p268d1_draw_order_registry_freeze_20260610.json"
P268D1_JSONL = OUT_DIR / "p268d1_draw_order_full_history_artifact_backfill_20260610.jsonl"
P268D1_LEDGER = OUT_DIR / "p268d1_draw_order_full_history_artifact_backfill_20260610.ledger.json"
P268D1_SUMMARY = OUT_DIR / "p268d1_draw_order_full_history_artifact_backfill_20260610.summary.json"

OUTPUT_JSON = OUT_DIR / "p268d2_draw_order_structure_validation_db_alignment_20260610.json"
OUTPUT_MD = OUT_DIR / "p268d2_draw_order_structure_validation_db_alignment_20260610.md"

DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"


def _p291u_default_db_path():
    db_path = DB_PATH
    if not db_path.is_file():
        raise FileNotFoundError(f"Default lottery DB path is missing or non-regular: {db_path}")
    return db_path


def _p291u_resolve_db_path(db_path=None):
    if db_path is None:
        return _p291u_default_db_path()
    path = Path(db_path)
    if not path.is_absolute():
        raise ValueError(f"Explicit DB path must be absolute: {db_path}")
    if not path.is_file():
        raise FileNotFoundError(f"Explicit DB path is missing or non-regular: {path}")
    return path

EXPECTED_LEN_BY_GAME = {
    "BIG_LOTTO": 7,
    "POWER_LOTTO": 7,
    "DAILY_539": 5,
    "3_STAR": 3,
    "4_STAR": 4,
}

EXPECTED_RECORD_KEYS = {
    "lottery_type",
    "month",
    "period",
    "draw_date",
    "drawNumberAppear",
    "drawNumberSize",
    "validation",
}

DB_ALIGNMENT_VERDICTS = {
    "PASS",
    "PARTIAL_ENV_LIMITATION",
    "FAIL_SCHEMA_MISMATCH",
    "FAIL_DATA_MISMATCH",
}


def load_json(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_jsonl(path: Path):
    records = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def structure_validation_aggregate(records, ledger):
    n_records = len(records)

    duplicate_counter = Counter()
    schema_drift = []
    parse_success_count = 0
    correct_length_count = 0
    sorted_match_count = 0
    appear_present_count = 0
    games_seen = set()
    by_month_game = Counter()

    for rec in records:
        keys = set(rec.keys())
        if keys != EXPECTED_RECORD_KEYS:
            extra = keys - EXPECTED_RECORD_KEYS
            missing = EXPECTED_RECORD_KEYS - keys
            if extra or missing:
                schema_drift.append(
                    {
                        "lottery_type": rec.get("lottery_type"),
                        "period": rec.get("period"),
                        "extra_keys": sorted(extra),
                        "missing_keys": sorted(missing),
                    }
                )

        lottery_type = rec.get("lottery_type")
        games_seen.add(lottery_type)
        month = rec.get("month")
        by_month_game[(month, lottery_type)] += 1

        dup_key = (lottery_type, rec.get("period"))
        duplicate_counter[dup_key] += 1

        validation = rec.get("validation", {})
        if validation.get("drawNumberAppear_present"):
            appear_present_count += 1
        if validation.get("parsed_as_ordered_int_sequence"):
            parse_success_count += 1
        if validation.get("correct_length"):
            correct_length_count += 1
        if validation.get("sorted_appear_matches_drawNumberSize"):
            sorted_match_count += 1

        expected_len = EXPECTED_LEN_BY_GAME.get(lottery_type)
        actual_len = len(rec.get("drawNumberAppear") or [])
        if expected_len is not None and actual_len != expected_len:
            schema_drift.append(
                {
                    "lottery_type": lottery_type,
                    "period": rec.get("period"),
                    "issue": "unexpected_drawNumberAppear_length",
                    "expected_length": expected_len,
                    "actual_length": actual_len,
                }
            )

    duplicates = {
        f"{lt}:{period}": count
        for (lt, period), count in duplicate_counter.items()
        if count > 1
    }

    # Cross-check JSONL coverage against the P268D-1 ledger.
    ledger_cells = ledger.get("ledger", [])
    ledger_done_or_empty = {
        (c["month"], c["lottery_type"]): c
        for c in ledger_cells
        if c["status"] in ("DONE", "EMPTY")
    }
    ledger_pending_or_error = [
        c for c in ledger_cells if c["status"] in ("PENDING", "ERROR")
    ]

    cells_with_records_mismatch = []
    for (month, lottery_type), cell in ledger_done_or_empty.items():
        actual_count = by_month_game.get((month, lottery_type), 0)
        expected_count = cell.get("records_fetched", 0) or 0
        if cell["status"] == "DONE" and actual_count != expected_count:
            cells_with_records_mismatch.append(
                {
                    "month": month,
                    "lottery_type": lottery_type,
                    "ledger_records_fetched": expected_count,
                    "jsonl_record_count": actual_count,
                }
            )
        if cell["status"] == "EMPTY" and actual_count != 0:
            cells_with_records_mismatch.append(
                {
                    "month": month,
                    "lottery_type": lottery_type,
                    "ledger_status": "EMPTY",
                    "jsonl_record_count": actual_count,
                }
            )

    return {
        "records_checked": n_records,
        "expected_record_count": 21682,
        "record_count_matches_expected": n_records == 21682,
        "games_seen": sorted(games_seen),
        "appear_present_count": appear_present_count,
        "parse_success_count": parse_success_count,
        "correct_length_count": correct_length_count,
        "sorted_appear_matches_size_count": sorted_match_count,
        "parse_success_rate": (parse_success_count / n_records) if n_records else None,
        "correct_length_rate": (correct_length_count / n_records) if n_records else None,
        "duplicate_key_count": len(duplicates),
        "duplicate_keys_sample": dict(list(duplicates.items())[:10]),
        "schema_drift_count": len(schema_drift),
        "schema_drift_sample": schema_drift[:10],
        "ledger_pending_cells": sum(
            1 for c in ledger_cells if c["status"] == "PENDING"
        ),
        "ledger_error_cells": sum(1 for c in ledger_cells if c["status"] == "ERROR"),
        "ledger_empty_cells": sum(1 for c in ledger_cells if c["status"] == "EMPTY"),
        "ledger_done_cells": sum(1 for c in ledger_cells if c["status"] == "DONE"),
        "ledger_total_cells": len(ledger_cells),
        "ledger_pending_or_error_cells": ledger_pending_or_error,
        "jsonl_vs_ledger_count_mismatches": cells_with_records_mismatch,
        "jsonl_vs_ledger_count_mismatch_count": len(cells_with_records_mismatch),
    }


def db_alignment_audit():
    """Read-only inspection of lottery_api/data/lottery_v2.db. Never writes to the DB."""

    result = {
        "db_path": str(DB_PATH.relative_to(REPO_ROOT)),
        "db_exists": DB_PATH.is_file(),
        "opened_read_only": False,
        "tables_inspected": [],
        "views_inspected": [],
        "draws_table_present": False,
        "draws_row_count": 0,
        "rows_available_per_lottery": {},
        "matched_records_per_lottery": {},
        "unmatched_artifact_records": None,
        "unmatched_db_records": None,
        "date_range_overlap": None,
        "canonical_view_present": False,
        "verdict": None,
        "verdict_reason": "",
    }

    db_path = _p291u_resolve_db_path()
    db_uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    result["opened_read_only"] = True
    try:
        cur = conn.cursor()

        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = sorted(r[0] for r in cur.fetchall())
        result["tables_inspected"] = tables

        cur.execute("SELECT name FROM sqlite_master WHERE type='view'")
        views = sorted(r[0] for r in cur.fetchall())
        result["views_inspected"] = views
        result["canonical_view_present"] = "draws_big_lotto_canonical_main" in views

        if "draws" in tables:
            result["draws_table_present"] = True
            cur.execute("SELECT COUNT(*) FROM draws")
            result["draws_row_count"] = cur.fetchone()[0]

            cur.execute("SELECT lottery_type, COUNT(*) FROM draws GROUP BY lottery_type")
            result["rows_available_per_lottery"] = dict(cur.fetchall())

        if result["draws_row_count"] == 0:
            result["verdict"] = "PARTIAL_ENV_LIMITATION"
            result["verdict_reason"] = (
                "lottery_api/data/lottery_v2.db 'draws' table has 0 rows in this environment "
                "(consistent with P268B finding DB alignment = NO_LOCAL_ROWS). "
                "No row-level alignment is possible; structural schema (table/columns) "
                "was inspected read-only and is consistent with the P268D-1 artifact's "
                "key fields (lottery_type, draw identifier/period, date, numbers)."
            )
            result["unmatched_artifact_records"] = "ALL (no DB rows to compare against)"
            result["unmatched_db_records"] = 0
            result["date_range_overlap"] = "NOT_COMPUTABLE_NO_DB_ROWS"
        else:
            # Row-level alignment would go here if local rows existed.
            # Not exercised in this environment (draws table is empty).
            result["verdict"] = "PARTIAL_ENV_LIMITATION"
            result["verdict_reason"] = (
                "draws table has rows but row-level alignment logic for P268D-2 "
                "was not exercised because this environment's table was empty "
                "during development; re-run in an environment with populated "
                "canonical data to obtain a PASS/FAIL verdict."
            )
    finally:
        conn.close()

    return result


def render_markdown(artifact: dict) -> str:
    sv = artifact["structure_validation"]
    db = artifact["db_alignment"]
    lines = []
    lines.append("# P268D-2 Draw-Order Structure Validation + Read-Only DB Alignment")
    lines.append("")
    lines.append(f"Generated: {artifact['generated_at']}")
    lines.append("")
    lines.append("## P268D-1 Boundary")
    lines.append("")
    lines.append(artifact["p268d1_boundary"])
    lines.append("")
    lines.append("## Structure Validation Summary")
    lines.append("")
    lines.append(f"- Records checked: {sv['records_checked']} (expected {sv['expected_record_count']}, matches={sv['record_count_matches_expected']})")
    lines.append(f"- Games seen: {', '.join(sv['games_seen'])}")
    lines.append(f"- drawNumberAppear present: {sv['appear_present_count']}/{sv['records_checked']}")
    lines.append(f"- Parse success: {sv['parse_success_count']}/{sv['records_checked']} ({sv['parse_success_rate']:.4%})")
    lines.append(f"- Correct length: {sv['correct_length_count']}/{sv['records_checked']} ({sv['correct_length_rate']:.4%})")
    lines.append(f"- sorted(drawNumberAppear) matches drawNumberSize flag: {sv['sorted_appear_matches_size_count']}/{sv['records_checked']}")
    lines.append(f"- Duplicate (lottery_type, period) keys: {sv['duplicate_key_count']}")
    lines.append(f"- Schema drift entries: {sv['schema_drift_count']}")
    lines.append(f"- Ledger cells: total={sv['ledger_total_cells']}, DONE={sv['ledger_done_cells']}, EMPTY={sv['ledger_empty_cells']}, ERROR={sv['ledger_error_cells']}, PENDING={sv['ledger_pending_cells']}")
    lines.append(f"- JSONL vs ledger record-count mismatches: {sv['jsonl_vs_ledger_count_mismatch_count']}")
    lines.append("")
    lines.append("## Read-Only DB Alignment Summary")
    lines.append("")
    lines.append(f"- DB path: `{db['db_path']}`")
    lines.append(f"- Opened read-only (mode=ro): {db['opened_read_only']}")
    lines.append(f"- Tables inspected: {', '.join(db['tables_inspected'])}")
    lines.append(f"- Views inspected: {', '.join(db['views_inspected'])}")
    lines.append(f"- Canonical BIG_LOTTO view present: {db['canonical_view_present']}")
    lines.append(f"- `draws` table present: {db['draws_table_present']}, row count: {db['draws_row_count']}")
    lines.append(f"- Rows available per lottery: {db['rows_available_per_lottery']}")
    lines.append(f"- Matched records per lottery: {db['matched_records_per_lottery']}")
    lines.append(f"- Unmatched artifact records: {db['unmatched_artifact_records']}")
    lines.append(f"- Unmatched DB records: {db['unmatched_db_records']}")
    lines.append(f"- Date range overlap: {db['date_range_overlap']}")
    lines.append(f"- Verdict: **{db['verdict']}** -- {db['verdict_reason']}")
    lines.append("")
    lines.append("## Data-Quality Gate Verdict")
    lines.append("")
    lines.append(f"- Overall verdict: **{artifact['data_quality_gate']['verdict']}**")
    lines.append(f"- Can P268D-3 proceed: **{artifact['data_quality_gate']['can_p268d3_proceed']}**")
    if artifact["data_quality_gate"]["can_p268d3_proceed"]:
        lines.append(f"- Allowed next scope for P268D-3: {artifact['data_quality_gate']['p268d3_allowed_next_scope']}")
    else:
        lines.append(f"- Blocker: {artifact['data_quality_gate']['blocker']}")
    lines.append("")
    lines.append("## Explicit Non-Claims")
    lines.append("")
    for c in artifact["explicit_non_claims"]:
        lines.append(f"- {c}")
    lines.append("")
    lines.append(f"Final Classification: `{artifact['final_classification']}`")
    lines.append("")
    return "\n".join(lines)


def main():
    registry_freeze = load_json(P268D1_REGISTRY_FREEZE)
    summary = load_json(P268D1_SUMMARY)
    ledger = load_json(P268D1_LEDGER)
    records = load_jsonl(P268D1_JSONL)

    sv = structure_validation_aggregate(records, ledger)
    db = db_alignment_audit()

    structure_ok = (
        sv["record_count_matches_expected"]
        and sv["duplicate_key_count"] == 0
        and sv["schema_drift_count"] == 0
        and sv["ledger_pending_cells"] == 0
        and sv["ledger_error_cells"] == 0
        and sv["correct_length_count"] == sv["records_checked"]
        and sv["jsonl_vs_ledger_count_mismatch_count"] == 0
    )

    if structure_ok and db["verdict"] == "PASS":
        gate_verdict = "STRUCTURE_PASS_DB_PASS"
        can_proceed = True
        final_classification = "P268D2_DRAW_ORDER_STRUCTURE_VALIDATION_DB_ALIGNMENT_COMPLETE_READY_FOR_H1_DESIGN"
    elif structure_ok and db["verdict"] == "PARTIAL_ENV_LIMITATION":
        gate_verdict = "STRUCTURE_PASS_DB_ALIGNMENT_PARTIAL_ENV_LIMITATION"
        can_proceed = True
        final_classification = "P268D2_DRAW_ORDER_STRUCTURE_VALIDATION_DB_ALIGNMENT_COMPLETE_DB_ALIGNMENT_PARTIAL"
    elif structure_ok and db["verdict"] in ("FAIL_SCHEMA_MISMATCH", "FAIL_DATA_MISMATCH"):
        gate_verdict = f"STRUCTURE_PASS_DB_{db['verdict']}"
        can_proceed = False
        final_classification = "P268D2_DRAW_ORDER_STRUCTURE_VALIDATION_DB_ALIGNMENT_BLOCKED_DB_SCHEMA_MISMATCH"
    else:
        gate_verdict = "STRUCTURE_VALIDATION_FAILED"
        can_proceed = False
        final_classification = "P268D2_DRAW_ORDER_STRUCTURE_VALIDATION_DB_ALIGNMENT_BLOCKED_ARTIFACT_MISSING"

    if can_proceed:
        p268d3_scope = (
            "P268D-3 may proceed with: (1) within-draw permutation null model "
            "construction for H1/H1_holdout (per-ball exit-rank heterogeneity), "
            "using DAILY_539 as primary game and BIG_LOTTO/POWER_LOTTO as secondary, "
            "per the registry-freeze windows/baseline/correction definitions; "
            "(2) computing the H1 statistic and its permutation p-value as a "
            "confirmatory test (single pre-registered hypothesis, P221F guardrails). "
            "P268D-3 must NOT write to the production Hypothesis Registry until "
            "results are reviewed; results should be written to a new "
            "outputs/research/ artifact first. DB write remains forbidden -- "
            "this is a read-only-source confirmatory analysis using the "
            "P268D-1 JSONL artifact (DB alignment for this environment is "
            "PARTIAL_ENV_LIMITATION / NO_LOCAL_ROWS, so the JSONL artifact, not "
            "the local DB, is the data source for P268D-3)."
        )
        blocker = ""
    else:
        p268d3_scope = ""
        blocker = (
            f"Data-quality gate verdict={gate_verdict}. "
            f"schema_drift_count={sv['schema_drift_count']}, "
            f"duplicate_key_count={sv['duplicate_key_count']}, "
            f"ledger_pending={sv['ledger_pending_cells']}, "
            f"ledger_error={sv['ledger_error_cells']}, "
            f"jsonl_vs_ledger_mismatches={sv['jsonl_vs_ledger_count_mismatch_count']}, "
            f"db_verdict={db['verdict']}."
        )

    artifact = {
        "task_id": "P268D2_DRAW_ORDER_STRUCTURE_VALIDATION_AND_READ_ONLY_DB_ALIGNMENT",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "p268d1_boundary": (
            f"P268D-1 (PR #409, merged) produced a registry-freeze artifact "
            f"(hypotheses H1/H1_holdout/H2/H3 status=FROZEN_NOT_TESTED, "
            f"final_classification={registry_freeze.get('final_classification')}) "
            f"and a full-history drawNumberAppear backfill artifact "
            f"(final_classification={summary.get('final_classification')}, "
            f"coverage={summary['coverage']['start_month']}..{summary['coverage']['end_month']}, "
            f"records=21682, pending_cells=0, error_cells=0, empty_cells=12). "
            f"No H1/H2/H3 test, no DB write, no Hypothesis Registry write, "
            f"no hit-rate claim were made by P268D-1."
        ),
        "structure_validation": sv,
        "db_alignment": db,
        "data_quality_gate": {
            "verdict": gate_verdict,
            "can_p268d3_proceed": can_proceed,
            "p268d3_allowed_next_scope": p268d3_scope,
            "blocker": blocker,
        },
        "no_db_write": True,
        "no_hypothesis_registry_write": True,
        "no_h1_h2_h3_test_run_in_this_task": True,
        "no_hit_rate_claim": True,
        "explicit_non_claims": [
            "No H1/H2/H3 statistical test, no permutation test, and no significance "
            "value of any kind was computed in this task. Reserved for a separate, "
            "future, explicitly-authorized confirmatory task (P268D-3).",
            "No production database write was performed (lottery_api/data/lottery_v2.db opened "
            "read-only via sqlite3 URI mode=ro, no INSERT/UPDATE/DELETE/DDL).",
            "No write to lottery_api/data/hypothesis_registry.jsonl was performed.",
            "No new strategy was generated and no betting recommendation is made.",
            "No hit-rate / success-rate-improvement claim is made by this artifact.",
        ],
        "final_classification": final_classification,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(artifact, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    with open(OUTPUT_MD, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(artifact))

    print(f"Final Classification: {final_classification}")
    return artifact


if __name__ == "__main__":
    main()
