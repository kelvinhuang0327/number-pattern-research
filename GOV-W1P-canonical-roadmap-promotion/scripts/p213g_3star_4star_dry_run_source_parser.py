"""
P213G 3_STAR / 4_STAR Dry-run Source Parser Validation

Validates whether the Taiwan Lottery TXT source format for 3_STAR and 4_STAR
games includes original positional order (開出順序), and whether a parser can
extract both sorted canonical numbers and positional draw order.

Dry-run only — NO production DB write.
This script may read production DB for comparison queries only.

Source status: P213G_SOURCE_FORMAT_VALIDATED_WITH_MOCK_ONLY
Real historical source files are not present in this repo. The format is
validated using mock content from lottery_api/tools/debug_validator.py and
debug_comprehensive.py, which represent the Taiwan Lottery TXT format.

Usage:
    python3 scripts/p213g_3star_4star_dry_run_source_parser.py
    python3 scripts/p213g_3star_4star_dry_run_source_parser.py --db-compare

Output: prints dry-run results; does NOT write to production DB.
"""
import json
import os
import re
import sys
import sqlite3
from typing import Dict, List, Optional, Tuple

from pathlib import Path


def _p291u_repo_root():
    current = Path(__file__)
    if not current.is_absolute():
        raise FileNotFoundError(f"Source file path is not absolute: {current}")
    for parent in (current.parent, *current.parents):
        if (parent / "lottery_api").is_dir():
            return parent
    raise FileNotFoundError(f"Unable to locate repository root from source file: {current}")


def _p291u_default_db_path():
    db_path = _p291u_repo_root() / "lottery_api" / "data" / "lottery_v2.db"
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


def _p291u_connect_resolved(db_path, *, uri=False):
    if uri:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    return sqlite3.connect(str(db_path))


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCTION_DB = os.path.join(REPO_ROOT, "lottery_api", "data", "lottery_v2.db")

SOURCE_STATUS = "P213G_SOURCE_FORMAT_VALIDATED_WITH_MOCK_ONLY"
SOURCE_PROVENANCE = "Mock content from lottery_api/tools/debug_validator.py and debug_comprehensive.py; represents Taiwan Lottery TXT format; no real historical files present"

# ---------------------------------------------------------------------------
# Known source format fixtures (from debug_validator.py and debug_comprehensive.py)
# These represent the Taiwan Lottery TXT format for 3_STAR and 4_STAR games.
# ---------------------------------------------------------------------------

FIXTURE_3STAR = [
    {
        "source": "fixture:3star_reversed",
        "content": "112000001期\n開獎日期:112/01/01\n大小順序:1 2 3\n開出順序:3 2 1\n1 2 3",
        "lottery_type": "3_STAR",
        "expected_positional": [3, 2, 1],
        "expected_sorted": [1, 2, 3],
    },
    {
        "source": "fixture:3star_already_sorted",
        "content": "112000002期\n開獎日期:112/01/02\n大小順序:0 5 9\n開出順序:0 5 9\n0 5 9",
        "lottery_type": "3_STAR",
        "expected_positional": [0, 5, 9],
        "expected_sorted": [0, 5, 9],
    },
    {
        "source": "fixture:3star_all_different",
        "content": "112000003期\n開獎日期:112/01/03\n大小順序:1 4 7\n開出順序:7 1 4\n1 4 7",
        "lottery_type": "3_STAR",
        "expected_positional": [7, 1, 4],
        "expected_sorted": [1, 4, 7],
    },
]

FIXTURE_4STAR = [
    {
        "source": "fixture:4star_reversed_joined",
        "content": "112000001\n開獎日期:112/01/01\n大小順序:1234\n開出順序:4321\n1234",
        "lottery_type": "4_STAR",
        "expected_positional": [4, 3, 2, 1],
        "expected_sorted": [1, 2, 3, 4],
    },
    {
        "source": "fixture:4star_already_sorted",
        "content": "112000002\n開獎日期:112/01/02\n大小順序:0159\n開出順序:0159\n0159",
        "lottery_type": "4_STAR",
        "expected_positional": [0, 1, 5, 9],
        "expected_sorted": [0, 1, 5, 9],
    },
]


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _parse_draw_id(line: str) -> Optional[str]:
    """Extract draw number from lines like '112000001期' or '112000001'."""
    m = re.match(r'^(\d+)期?$', line.strip())
    return m.group(1) if m else None


def _parse_date(line: str) -> Optional[str]:
    """Extract date from lines like '開獎日期:112/01/01'."""
    m = re.match(r'^開獎日期[:：](.+)$', line.strip())
    return m.group(1).strip() if m else None


def _parse_draw_order(line: str, lottery_type: str) -> Optional[List[int]]:
    """
    Extract numbers from '開出順序' line.
    3_STAR: space-separated single digits → [3, 2, 1]
    4_STAR: joined digits → [4, 3, 2, 1]
    """
    m = re.match(r'^開出順序[:：](.+)$', line.strip())
    if not m:
        return None
    raw = m.group(1).strip()
    if lottery_type == '4_STAR':
        return [int(d) for d in raw if d.isdigit()]
    else:
        parts = raw.split()
        return [int(p) for p in parts if p.isdigit() or (len(p) <= 2 and p.isdigit())]


def parse_source_content(content: str, lottery_type: str) -> Dict:
    """
    Parse a single TXT source record.
    Returns a dict with: draw_id, date, positional, sorted_numbers, errors.
    Does not write to DB.
    """
    result = {
        "draw_id": None,
        "date": None,
        "lottery_type": lottery_type,
        "positional": None,
        "sorted_numbers": None,
        "source_has_draw_order": False,
        "errors": [],
    }

    lines = content.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue

        if result["draw_id"] is None:
            draw_id = _parse_draw_id(line)
            if draw_id:
                result["draw_id"] = draw_id
                continue

        if result["date"] is None:
            date = _parse_date(line)
            if date:
                result["date"] = date
                continue

        if result["positional"] is None and '開出順序' in line:
            positional = _parse_draw_order(line, lottery_type)
            if positional is not None:
                result["positional"] = positional
                result["sorted_numbers"] = sorted(positional)
                result["source_has_draw_order"] = True
                continue

    if result["positional"] is None:
        result["errors"].append("Missing 開出順序 field")
    if result["draw_id"] is None:
        result["errors"].append("Missing draw ID")

    return result


def run_dry_run(fixtures: List[Dict]) -> Dict:
    """
    Run parser over a list of fixture records.
    Returns summary dict with parse results. No DB write.
    """
    parsed = []
    invalid = 0
    for f in fixtures:
        r = parse_source_content(f["content"], f["lottery_type"])
        r["source"] = f["source"]
        r["expected_positional"] = f["expected_positional"]
        r["expected_sorted"] = f["expected_sorted"]
        r["positional_match"] = r["positional"] == f["expected_positional"]
        r["sorted_match"] = r["sorted_numbers"] == f["expected_sorted"]
        if r["errors"] or not r["positional_match"] or not r["sorted_match"]:
            invalid += 1
        parsed.append(r)
    return {
        "total": len(parsed),
        "valid": len(parsed) - invalid,
        "invalid": invalid,
        "rows": parsed,
    }


def compare_with_db(parsed_rows: List[Dict]) -> Dict:
    """
    Read-only comparison of parsed rows with production DB.
    Does not write to DB.
    """
    _p291u_db_path = _p291u_resolve_db_path()
    if not os.path.exists(PRODUCTION_DB):
        return {"db_available": False, "matched": 0, "mismatched": 0, "not_in_db": 0}

    conn = _p291u_connect_resolved(_p291u_db_path, uri=True)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    matched = mismatched = not_in_db = 0
    for row in parsed_rows:
        if not row["draw_id"] or not row["sorted_numbers"]:
            continue
        cursor.execute(
            "SELECT numbers FROM draws WHERE draw=? AND lottery_type=?",
            (row["draw_id"], row["lottery_type"])
        )
        db_row = cursor.fetchone()
        if db_row is None:
            not_in_db += 1
        else:
            db_sorted = json.loads(db_row["numbers"])
            if db_sorted == row["sorted_numbers"]:
                matched += 1
            else:
                mismatched += 1
    conn.close()
    return {"db_available": True, "matched": matched, "mismatched": mismatched, "not_in_db": not_in_db}


def main():
    print("=== P213G 3_STAR/4_STAR Dry-run Source Parser ===")
    print(f"Source status: {SOURCE_STATUS}")
    print(f"Provenance: {SOURCE_PROVENANCE}")
    print()

    all_fixtures = FIXTURE_3STAR + FIXTURE_4STAR
    result = run_dry_run(all_fixtures)

    print(f"Fixtures total: {result['total']}")
    print(f"  Valid parsed: {result['valid']}")
    print(f"  Invalid:      {result['invalid']}")
    print()

    for r in result["rows"]:
        status = "OK" if not r["errors"] and r["positional_match"] and r["sorted_match"] else "FAIL"
        print(f"  [{status}] {r['source']} ({r['lottery_type']})")
        print(f"    draw_id: {r['draw_id']}  date: {r['date']}")
        print(f"    positional: {r['positional']}  expected: {r['expected_positional']}  match={r['positional_match']}")
        print(f"    sorted:     {r['sorted_numbers']}  expected: {r['expected_sorted']}  match={r['sorted_match']}")
        if r["errors"]:
            print(f"    errors: {r['errors']}")

    db_cmp = compare_with_db(result["rows"])
    print()
    print(f"DB comparison (read-only): {db_cmp}")
    print()
    print("Production DB: NOT WRITTEN. Dry-run only.")


if __name__ == "__main__":
    main()
