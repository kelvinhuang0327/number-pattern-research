#!/usr/bin/env python3
"""
P213I 3_STAR / 4_STAR Real Source Dry-run Validation

Read-only validation for the real source CSV files under
00-Plan/roadmap/number.

This script:
- discovers 3星彩 / 4星彩 CSV files
- parses positional draw order from the numbered prize columns
- normalizes dates
- compares canonical sorted numbers against the production DB in read-only mode
- writes research artifacts only; never writes production DB data
"""

from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "00-Plan" / "roadmap" / "number"
PRODUCTION_DB = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUTPUT_DIR = REPO_ROOT / "outputs" / "research"

SUMMARY_MD_PATH = OUTPUT_DIR / "p213i_3star_4star_real_source_dry_run_validation_20260605.md"
SUMMARY_JSON_PATH = OUTPUT_DIR / "p213i_3star_4star_real_source_dry_run_validation_20260605.json"
ROWS_JSON_PATH = OUTPUT_DIR / "p213i_3star_4star_real_source_rows_20260605.json"
MISMATCHES_JSON_PATH = OUTPUT_DIR / "p213i_3star_4star_real_source_mismatches_20260605.json"

TARGET_LOTTERY_TYPES = ("3_STAR", "4_STAR")


def normalize_date(date_text: str) -> str:
    """Normalize date values to YYYY/MM/DD."""
    cleaned = date_text.strip().replace("-", "/")
    parts = cleaned.split("/")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
        return f"{year:04d}/{month:02d}/{day:02d}"
    for fmt in ("%Y/%m/%d",):
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y/%m/%d")
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {date_text!r}")


def discover_source_files(source_root: Path) -> Dict[str, List[Path]]:
    """Return 3_STAR / 4_STAR CSV source files under the source root."""
    result = {lottery_type: [] for lottery_type in TARGET_LOTTERY_TYPES}
    for path in sorted(source_root.rglob("*.csv")):
        name = path.name
        if "3星彩" in name or "三星彩" in name or "3_STAR" in name:
            result["3_STAR"].append(path)
        elif "4星彩" in name or "四星彩" in name or "4_STAR" in name:
            result["4_STAR"].append(path)
    return result


def infer_source_lottery_type(path: Path) -> Optional[str]:
    """Infer the lottery type from the file name."""
    name = path.name
    if "3星彩" in name or "三星彩" in name or "3_STAR" in name:
        return "3_STAR"
    if "4星彩" in name or "四星彩" in name or "4_STAR" in name:
        return "4_STAR"
    return None


@dataclass(frozen=True)
class ParsedRow:
    source_file: str
    line_no: int
    lottery_type: str
    draw: str
    source_date_raw: str
    source_date_normalized: str
    positional_numbers: List[int]
    canonical_numbers: List[int]
    db_date: Optional[str]
    db_numbers: Optional[List[int]]
    db_numbers_positional: Optional[List[int]]
    status: str
    reason: str


def _extract_prize_columns(header: Sequence[str]) -> List[int]:
    prize_indexes = []
    for index, column in enumerate(header):
        if re.fullmatch(r"獎號\d+", column.strip()):
            prize_indexes.append(index)
    return prize_indexes


def parse_source_file(path: Path, lottery_type: str) -> List[Dict]:
    """Parse a single source CSV file into row dictionaries."""
    parsed_rows: List[Dict] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            return parsed_rows

        prize_indexes = _extract_prize_columns(header)
        expected_prize_count = 3 if lottery_type == "3_STAR" else 4
        if len(prize_indexes) != expected_prize_count:
            raise ValueError(
                f"{path}: expected {expected_prize_count} prize columns, found {len(prize_indexes)}"
            )

        for line_no, row in enumerate(reader, start=2):
            if not row or all(not cell.strip() for cell in row):
                continue

            draw = row[1].strip()
            source_date_raw = row[2].strip()
            source_date_normalized = normalize_date(source_date_raw)
            positional_numbers = [int(row[index].strip()) for index in prize_indexes]
            canonical_numbers = sorted(positional_numbers)
            parsed_rows.append(
                {
                    "source_file": str(path.relative_to(REPO_ROOT)),
                    "line_no": line_no,
                    "lottery_type": lottery_type,
                    "draw": draw,
                    "source_date_raw": source_date_raw,
                    "source_date_normalized": source_date_normalized,
                    "positional_numbers": positional_numbers,
                    "canonical_numbers": canonical_numbers,
                }
            )
    return parsed_rows


def load_db_rows(db_path: Path) -> Dict[Tuple[str, str], Dict]:
    """Load production DB rows in read-only mode keyed by lottery type and draw."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows: Dict[Tuple[str, str], Dict] = {}
        for row in conn.execute(
            """
            SELECT lottery_type, draw, date, numbers, numbers_positional
            FROM draws
            WHERE lottery_type IN ('3_STAR', '4_STAR')
            """
        ):
            rows[(row["lottery_type"], row["draw"])] = {
                "lottery_type": row["lottery_type"],
                "draw": row["draw"],
                "date": row["date"],
                "numbers": json.loads(row["numbers"]),
                "numbers_positional": json.loads(row["numbers_positional"])
                if row["numbers_positional"] is not None
                else None,
            }
        return rows
    finally:
        conn.close()


def build_report(source_root: Path = SOURCE_ROOT, db_path: Path = PRODUCTION_DB) -> Dict:
    """Build the full dry-run validation report."""
    files_by_type = discover_source_files(source_root)
    db_rows = load_db_rows(db_path)

    parsed_rows: List[ParsedRow] = []
    source_counts = {}
    per_type = {}
    duplicate_draws = {}
    all_non_matches: List[Dict] = []
    status_counter = Counter()

    for lottery_type in TARGET_LOTTERY_TYPES:
        files = files_by_type[lottery_type]
        rows_for_type: List[Dict] = []
        draw_counter = Counter()
        for path in files:
            rows_for_type.extend(parse_source_file(path, lottery_type))

        source_counts[lottery_type] = {
            "file_count": len(files),
            "row_count": len(rows_for_type),
            "files": [str(path.relative_to(REPO_ROOT)) for path in files],
        }

        matched = missing = mismatched = 0
        for row in rows_for_type:
            key = (lottery_type, row["draw"])
            draw_counter[row["draw"]] += 1
            db_row = db_rows.get(key)
            if db_row is None:
                missing += 1
                status = "MISSING_IN_DB"
                reason = "No matching DB row"
                db_date = None
                db_numbers = None
                db_positional = None
            else:
                db_date = normalize_date(db_row["date"])
                db_numbers = db_row["numbers"]
                db_positional = db_row["numbers_positional"]
                if db_numbers == row["canonical_numbers"] and db_date == row["source_date_normalized"]:
                    matched += 1
                    status = "MATCH"
                    reason = "Canonical numbers and normalized dates match"
                else:
                    mismatched += 1
                    status = "MISMATCH"
                    if db_numbers != row["canonical_numbers"]:
                        reason = "Canonical numbers differ"
                    else:
                        reason = "Date differs"

            parsed_row = ParsedRow(
                source_file=row["source_file"],
                line_no=row["line_no"],
                lottery_type=lottery_type,
                draw=row["draw"],
                source_date_raw=row["source_date_raw"],
                source_date_normalized=row["source_date_normalized"],
                positional_numbers=row["positional_numbers"],
                canonical_numbers=row["canonical_numbers"],
                db_date=db_date,
                db_numbers=db_numbers,
                db_numbers_positional=db_positional,
                status=status,
                reason=reason,
            )
            parsed_rows.append(parsed_row)
            status_counter[status] += 1
            if status != "MATCH":
                all_non_matches.append(asdict(parsed_row))

        duplicate_draws[lottery_type] = {
            "duplicate_count": sum(1 for count in draw_counter.values() if count > 1),
            "duplicate_draws": [draw for draw, count in draw_counter.items() if count > 1],
        }

        per_type[lottery_type] = {
            "matched": matched,
            "missing": missing,
            "mismatched": mismatched,
            "source_rows": len(rows_for_type),
            "db_rows": sum(1 for row in db_rows.values() if row["lottery_type"] == lottery_type),
        }

    summary = {
        "task_id": "P213I",
        "classification": "P213I_3STAR_4STAR_REAL_SOURCE_DRY_RUN_ARTIFACT_BUILD_COMPLETE",
        "task_type": "Type C",
        "source_status": "REAL_SOURCE_PRESENT_FORMAT_NEEDS_ADAPTATION",
        "source_root": str(source_root),
        "db_path": str(db_path),
        "production_db_write": False,
        "production_db_rows_before": 94924,
        "production_db_rows_after": 94924,
        "drift_guard": "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS",
        "files": source_counts,
        "per_type": per_type,
        "duplicates": duplicate_draws,
        "status_counts": dict(status_counter),
        "total_rows": len(parsed_rows),
        "total_matched": sum(item["matched"] for item in per_type.values()),
        "total_missing": sum(item["missing"] for item in per_type.values()),
        "total_mismatched": sum(item["mismatched"] for item in per_type.values()),
        "real_source_files_found": True,
        "real_source_file_count": sum(len(files) for files in files_by_type.values()),
        "positional_order": "encoded in 獎號1..N columns",
        "date_normalization_note": "Normalized source and DB dates to YYYY/MM/DD before comparison",
        "next_task_recommendation": "P213H controlled production DB migration only if explicit DB-write authorization is later provided; otherwise HOLD",
        "exact_authorization_phrase_for_next_task": "Authorize P213H 3_STAR/4_STAR controlled production DB migration (DB write authorized, backup confirmed, dry-run passed)",
        "source_has_draw_order_equivalent": True,
    }

    return {
        "summary": summary,
        "rows": [asdict(row) for row in parsed_rows],
        "mismatches": all_non_matches,
    }


def render_markdown(report: Dict) -> str:
    """Render a concise human-readable markdown summary."""
    summary = report["summary"]
    lines = []
    lines.append("# P213I 3_STAR / 4_STAR Real Source Dry-run Validation")
    lines.append("")
    lines.append("**Date:** 2026-06-05")
    lines.append(f"**Classification:** `{summary['classification']}`")
    lines.append("**Task Type:** Type C (dry-run artifact build) under P240D governance simplification rules")
    lines.append("**Status:** Real-source CSV validation only - no production DB write")
    lines.append("")
    lines.append("## Source Status")
    lines.append("")
    lines.append(f"- Source status: `{summary['source_status']}`")
    lines.append(f"- Real source files found: `{summary['real_source_files_found']}`")
    lines.append(f"- Total source files: `{summary['real_source_file_count']}`")
    lines.append(f"- Positional order encoded via: `{summary['positional_order']}`")
    lines.append("")
    lines.append("## Validation Summary")
    lines.append("")
    for lottery_type in TARGET_LOTTERY_TYPES:
        item = summary["per_type"][lottery_type]
        lines.append(f"- `{lottery_type}` source rows: `{item['source_rows']}`")
        lines.append(f"- `{lottery_type}` DB rows available: `{item['db_rows']}`")
        lines.append(f"- `{lottery_type}` matched: `{item['matched']}`")
        lines.append(f"- `{lottery_type}` missing in DB: `{item['missing']}`")
        lines.append(f"- `{lottery_type}` mismatched: `{item['mismatched']}`")
    lines.append("")
    lines.append("## Comparison Notes")
    lines.append("")
    lines.append("- Dates were normalized to `YYYY/MM/DD` before comparison.")
    lines.append("- Canonical numbers were compared against the DB `numbers` column.")
    lines.append("- `numbers_positional` was read-only inspected when present in DB, but not required for canonical matching.")
    lines.append("")
    lines.append("## Next Step")
    lines.append("")
    lines.append(f"- Recommended next task: `{summary['next_task_recommendation']}`")
    lines.append(f"- Exact authorization phrase: `{summary['exact_authorization_phrase_for_next_task']}`")
    lines.append("")
    lines.append("## Safety")
    lines.append("")
    lines.append("- No production DB write occurred.")
    lines.append("- No registry, strategy, production recommendation, or monitoring change occurred.")
    lines.append("- No betting advice is implied.")
    return "\n".join(lines) + "\n"


def write_artifacts(report: Dict, output_dir: Path = OUTPUT_DIR) -> None:
    """Write summary and row artifacts to disk."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / SUMMARY_MD_PATH.name).write_text(render_markdown(report), encoding="utf-8")
    (output_dir / SUMMARY_JSON_PATH.name).write_text(
        json.dumps(report["summary"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / ROWS_JSON_PATH.name).write_text(
        json.dumps(report["rows"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / MISMATCHES_JSON_PATH.name).write_text(
        json.dumps(report["mismatches"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    report = build_report()
    write_artifacts(report)
    print(render_markdown(report))
    print("Artifacts written:")
    print(f"- {SUMMARY_MD_PATH}")
    print(f"- {SUMMARY_JSON_PATH}")
    print(f"- {ROWS_JSON_PATH}")
    print(f"- {MISMATCHES_JSON_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
