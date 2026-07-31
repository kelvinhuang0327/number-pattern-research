"""
wbc_backend/recommendation/p24_source_integrity_auditor.py

P24 — Source Integrity Auditor.

For each replay date, inspects the materialized P15 input CSV to detect:
- Identical content hash across dates (duplicate source replay)
- Identical game_id sets across dates
- game_date values not matching run_date (temporal mismatch)
- All dates sharing same source origin

Does NOT modify any files.

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

import hashlib
import io
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from wbc_backend.recommendation.p24_backfill_stability_contract import (
    STABILITY_ACCEPTABLE,
    STABILITY_DUPLICATE_SOURCE_SUSPECTED,
    STABILITY_SOURCE_INTEGRITY_BLOCKED,
    P24DatePerformanceProfile,
    P24DuplicateSourceFinding,
    P24SourceIntegrityProfile,
)

# Path pattern for materialized P15 input CSV
_MATERIALIZED_CSV_RELATIVE = (
    "p23_historical_replay/p15_materialized/joined_oof_with_odds.csv"
)


def compute_file_hash(path: Path) -> str:
    """Compute sha256 of the raw file bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _compute_content_hash_excl_run_date(df: pd.DataFrame) -> str:
    """Compute sha256 of CSV content excluding the run_date column.

    This detects duplicate source regardless of run_date stamp.
    """
    cols = [c for c in df.columns if c != "run_date"]
    buf = io.StringIO()
    df[cols].to_csv(buf, index=False)
    return hashlib.sha256(buf.getvalue().encode()).hexdigest()


def _compute_game_id_set_hash(df: pd.DataFrame) -> str:
    """Compute sha256 of sorted game_id list."""
    if "game_id" not in df.columns:
        return "NO_GAME_ID_COLUMN"
    game_ids = sorted(df["game_id"].dropna().unique().tolist())
    payload = "\n".join(game_ids)
    return hashlib.sha256(payload.encode()).hexdigest()


def _get_game_date_range(df: pd.DataFrame) -> str:
    """Return 'min_game_date:max_game_date' or 'UNKNOWN'."""
    if "game_date" not in df.columns:
        return "UNKNOWN"
    dates = df["game_date"].dropna().unique().tolist()
    if not dates:
        return "UNKNOWN"
    return f"{min(dates)}:{max(dates)}"


def _check_run_date_matches_game_date(df: pd.DataFrame, run_date: str) -> bool:
    """True if all game_date values equal run_date."""
    if "game_date" not in df.columns:
        return False
    # game_date must contain the run_date (same day)
    return bool((df["game_date"] == run_date).all())


def audit_materialized_source_hashes(
    date_range: List[str],
    paper_base_dir: str,
) -> List[Dict]:
    """Inspect materialized P15 input for each date.

    Returns list of per-date audit dicts with:
    - run_date
    - file_found (bool)
    - file_hash (full file sha256)
    - content_hash (sha256 excl. run_date col)
    - game_id_set_hash
    - row_count
    - game_id_count
    - game_date_range_str
    - run_date_matches_game_date
    - error (str or None)
    """
    base = Path(paper_base_dir)
    results = []

    for run_date in date_range:
        csv_path = base / run_date / _MATERIALIZED_CSV_RELATIVE
        rec: Dict = {
            "run_date": run_date,
            "file_found": False,
            "file_hash": "",
            "content_hash": "",
            "game_id_set_hash": "",
            "row_count": 0,
            "game_id_count": 0,
            "game_date_range_str": "UNKNOWN",
            "run_date_matches_game_date": False,
            "error": None,
        }
        if not csv_path.exists():
            rec["error"] = f"file not found: {csv_path}"
            results.append(rec)
            continue

        try:
            rec["file_found"] = True
            rec["file_hash"] = compute_file_hash(csv_path)
            df = pd.read_csv(csv_path)
            rec["row_count"] = len(df)
            rec["content_hash"] = _compute_content_hash_excl_run_date(df)
            rec["game_id_set_hash"] = _compute_game_id_set_hash(df)
            rec["game_id_count"] = (
                df["game_id"].nunique() if "game_id" in df.columns else 0
            )
            rec["game_date_range_str"] = _get_game_date_range(df)
            rec["run_date_matches_game_date"] = _check_run_date_matches_game_date(
                df, run_date
            )
        except Exception as exc:  # noqa: BLE001
            rec["error"] = str(exc)

        results.append(rec)

    return results


def compare_materialized_inputs(
    date_results: List[Dict],
) -> Dict:
    """Compute summary statistics on materialized source comparison."""
    found = [r for r in date_results if r["file_found"]]
    content_hashes = [r["content_hash"] for r in found if r["content_hash"]]
    game_id_hashes = [r["game_id_set_hash"] for r in found if r["game_id_set_hash"]]

    unique_content = set(content_hashes)
    unique_game_id = set(game_id_hashes)
    date_mismatches = [r for r in found if not r["run_date_matches_game_date"]]

    return {
        "n_dates_found": len(found),
        "n_dates_missing": len(date_results) - len(found),
        "source_hash_unique_count": len(unique_content),
        "source_hash_duplicate_count": len(content_hashes) - len(unique_content),
        "game_id_set_unique_count": len(unique_game_id),
        "n_date_mismatches": len(date_mismatches),
        "all_dates_date_mismatch": len(date_mismatches) == len(found) and len(found) > 0,
        "any_date_date_mismatch": len(date_mismatches) > 0,
    }


def detect_duplicate_source_groups(
    date_results: List[Dict],
) -> List[P24DuplicateSourceFinding]:
    """Group dates by identical content hash. Returns list of findings for
    groups with >1 date (i.e., actual duplicates)."""
    groups: Dict[str, List[Dict]] = defaultdict(list)
    for r in date_results:
        if r["file_found"] and r["content_hash"]:
            groups[r["content_hash"]].append(r)

    findings = []
    group_id = 0
    for content_hash, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        dates = tuple(sorted(m["run_date"] for m in members))
        game_id_set_hash = members[0]["game_id_set_hash"]
        game_date_range = members[0]["game_date_range_str"]
        # Date mismatch: game_date does not match any run_date in the group
        all_mismatch = all(not m["run_date_matches_game_date"] for m in members)
        findings.append(
            P24DuplicateSourceFinding(
                group_id=group_id,
                content_hash=content_hash,
                game_id_set_hash=game_id_set_hash,
                dates_in_group=dates,
                n_dates=len(dates),
                representative_game_date_range=game_date_range,
                is_date_mismatch=all_mismatch,
            )
        )
        group_id += 1

    return findings


def summarize_source_integrity(
    date_results: List[Dict],
    duplicate_findings: List[P24DuplicateSourceFinding],
    n_dates_requested: int,
) -> P24SourceIntegrityProfile:
    """Build a P24SourceIntegrityProfile from audit results."""
    comparison = compare_materialized_inputs(date_results)
    n_found = comparison["n_dates_found"]

    # Count independent dates: dates NOT in any duplicate group
    dates_in_duplicate_groups: set = set()
    for f in duplicate_findings:
        for d in f.dates_in_group:
            dates_in_duplicate_groups.add(d)

    n_independent = n_found - len(dates_in_duplicate_groups)

    # Determine audit status
    total_in_dup_groups = sum(f.n_dates for f in duplicate_findings)
    majority_duplicated = (
        n_found > 0 and total_in_dup_groups / n_found > 0.5
    )

    if majority_duplicated:
        audit_status = STABILITY_SOURCE_INTEGRITY_BLOCKED
        blocker = (
            f"{total_in_dup_groups}/{n_found} dates share identical source content "
            f"({len(duplicate_findings)} duplicate group(s)). "
            "This is duplicate source replay, not independent evidence."
        )
    elif comparison["any_date_date_mismatch"]:
        audit_status = STABILITY_DUPLICATE_SOURCE_SUSPECTED
        blocker = (
            f"{comparison['n_date_mismatches']} date(s) have game_date not matching "
            "run_date — temporal mismatch detected."
        )
    else:
        audit_status = STABILITY_ACCEPTABLE
        blocker = ""

    return P24SourceIntegrityProfile(
        n_dates_audited=n_dates_requested,
        n_independent_source_dates=max(0, n_independent),
        n_duplicate_source_groups=len(duplicate_findings),
        source_hash_unique_count=comparison["source_hash_unique_count"],
        source_hash_duplicate_count=comparison["source_hash_duplicate_count"],
        game_id_set_unique_count=comparison["game_id_set_unique_count"],
        all_dates_date_mismatch=comparison["all_dates_date_mismatch"],
        any_date_date_mismatch=comparison["any_date_date_mismatch"],
        duplicate_findings=tuple(duplicate_findings),
        audit_status=audit_status,
        blocker_reason=blocker,
    )
