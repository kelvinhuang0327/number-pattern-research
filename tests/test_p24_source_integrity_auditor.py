"""
tests/test_p24_source_integrity_auditor.py

Unit tests for p24_source_integrity_auditor.py.
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pandas as pd
import pytest

from wbc_backend.recommendation.p24_backfill_stability_contract import (
    STABILITY_ACCEPTABLE,
    STABILITY_DUPLICATE_SOURCE_SUSPECTED,
    STABILITY_SOURCE_INTEGRITY_BLOCKED,
)
from wbc_backend.recommendation.p24_source_integrity_auditor import (
    _compute_content_hash_excl_run_date,
    _compute_game_id_set_hash,
    _get_game_date_range,
    audit_materialized_source_hashes,
    compare_materialized_inputs,
    detect_duplicate_source_groups,
    summarize_source_integrity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_csv(tmp_path: Path, run_date: str, game_ids: list, game_date: str) -> Path:
    """Write a minimal materialized P15 CSV to the expected path."""
    out_dir = (
        tmp_path
        / run_date
        / "p23_historical_replay"
        / "p15_materialized"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "joined_oof_with_odds.csv"
    df = pd.DataFrame(
        {
            "run_date": [run_date] * len(game_ids),
            "game_id": game_ids,
            "game_date": [game_date] * len(game_ids),
            "y_true": [1] * len(game_ids),
            "p_oof": [0.55] * len(game_ids),
            "edge": [0.05] * len(game_ids),
        }
    )
    df.to_csv(csv_path, index=False)
    return csv_path


# ---------------------------------------------------------------------------
# _compute_content_hash_excl_run_date
# ---------------------------------------------------------------------------


def test_content_hash_excludes_run_date():
    df1 = pd.DataFrame({"run_date": ["2026-05-01"], "game_id": ["g1"], "edge": [0.1]})
    df2 = pd.DataFrame({"run_date": ["2026-05-09"], "game_id": ["g1"], "edge": [0.1]})
    assert _compute_content_hash_excl_run_date(df1) == _compute_content_hash_excl_run_date(
        df2
    )


def test_content_hash_differs_on_different_data():
    df1 = pd.DataFrame({"run_date": ["2026-05-01"], "game_id": ["g1"], "edge": [0.1]})
    df2 = pd.DataFrame({"run_date": ["2026-05-01"], "game_id": ["g2"], "edge": [0.2]})
    assert _compute_content_hash_excl_run_date(df1) != _compute_content_hash_excl_run_date(
        df2
    )


# ---------------------------------------------------------------------------
# _compute_game_id_set_hash
# ---------------------------------------------------------------------------


def test_game_id_set_hash_order_insensitive():
    df1 = pd.DataFrame({"game_id": ["g1", "g2", "g3"]})
    df2 = pd.DataFrame({"game_id": ["g3", "g1", "g2"]})
    assert _compute_game_id_set_hash(df1) == _compute_game_id_set_hash(df2)


def test_game_id_set_hash_differs_on_different_ids():
    df1 = pd.DataFrame({"game_id": ["g1", "g2"]})
    df2 = pd.DataFrame({"game_id": ["g1", "g3"]})
    assert _compute_game_id_set_hash(df1) != _compute_game_id_set_hash(df2)


def test_game_id_set_hash_no_column():
    df = pd.DataFrame({"other": [1, 2]})
    assert _compute_game_id_set_hash(df) == "NO_GAME_ID_COLUMN"


# ---------------------------------------------------------------------------
# _get_game_date_range
# ---------------------------------------------------------------------------


def test_game_date_range():
    df = pd.DataFrame({"game_date": ["2026-05-01", "2026-05-03", "2026-05-02"]})
    assert _get_game_date_range(df) == "2026-05-01:2026-05-03"


def test_game_date_range_no_column():
    df = pd.DataFrame({"other": [1]})
    assert _get_game_date_range(df) == "UNKNOWN"


# ---------------------------------------------------------------------------
# audit_materialized_source_hashes — file-based tests
# ---------------------------------------------------------------------------


def test_audit_detects_missing_file(tmp_path):
    results = audit_materialized_source_hashes(["2026-05-01"], str(tmp_path))
    assert len(results) == 1
    r = results[0]
    assert r["file_found"] is False
    assert r["error"] is not None


def test_audit_reads_existing_file(tmp_path):
    game_ids = [f"2026-05-01_T{i:03d}" for i in range(10)]
    _make_csv(tmp_path, "2026-05-01", game_ids, "2026-05-01")
    results = audit_materialized_source_hashes(["2026-05-01"], str(tmp_path))
    assert len(results) == 1
    r = results[0]
    assert r["file_found"] is True
    assert r["row_count"] == 10
    assert r["game_id_count"] == 10
    assert r["content_hash"] != ""
    assert r["error"] is None


def test_audit_detects_date_mismatch(tmp_path):
    """File has run_date=2026-05-01 but game_date=2025-05-08."""
    game_ids = [f"2025-05-08_T{i:03d}" for i in range(5)]
    _make_csv(tmp_path, "2026-05-01", game_ids, "2025-05-08")
    results = audit_materialized_source_hashes(["2026-05-01"], str(tmp_path))
    r = results[0]
    assert r["run_date_matches_game_date"] is False
    assert "2025-05-08" in r["game_date_range_str"]


def test_audit_detects_identical_hashes_across_dates(tmp_path):
    """Two dates using the same game_ids should have identical content hashes."""
    game_ids = [f"2025-05-08_T{i:03d}" for i in range(20)]
    _make_csv(tmp_path, "2026-05-01", game_ids, "2025-05-08")
    _make_csv(tmp_path, "2026-05-02", game_ids, "2025-05-08")
    results = audit_materialized_source_hashes(
        ["2026-05-01", "2026-05-02"], str(tmp_path)
    )
    assert results[0]["content_hash"] == results[1]["content_hash"]
    assert results[0]["game_id_set_hash"] == results[1]["game_id_set_hash"]


# ---------------------------------------------------------------------------
# compare_materialized_inputs
# ---------------------------------------------------------------------------


def test_compare_identifies_duplicates(tmp_path):
    game_ids = [f"2025-05-08_T{i:03d}" for i in range(20)]
    _make_csv(tmp_path, "2026-05-01", game_ids, "2025-05-08")
    _make_csv(tmp_path, "2026-05-02", game_ids, "2025-05-08")
    results = audit_materialized_source_hashes(
        ["2026-05-01", "2026-05-02"], str(tmp_path)
    )
    comparison = compare_materialized_inputs(results)
    assert comparison["source_hash_unique_count"] == 1
    assert comparison["source_hash_duplicate_count"] == 1  # 2 total - 1 unique
    assert comparison["n_date_mismatches"] == 2
    assert comparison["all_dates_date_mismatch"] is True


def test_compare_independent_dates(tmp_path):
    game_ids_a = [f"2026-05-01_T{i:03d}" for i in range(5)]
    game_ids_b = [f"2026-05-02_T{i:03d}" for i in range(5)]
    _make_csv(tmp_path, "2026-05-01", game_ids_a, "2026-05-01")
    _make_csv(tmp_path, "2026-05-02", game_ids_b, "2026-05-02")
    results = audit_materialized_source_hashes(
        ["2026-05-01", "2026-05-02"], str(tmp_path)
    )
    comparison = compare_materialized_inputs(results)
    assert comparison["source_hash_unique_count"] == 2
    assert comparison["source_hash_duplicate_count"] == 0
    assert comparison["all_dates_date_mismatch"] is False


# ---------------------------------------------------------------------------
# detect_duplicate_source_groups
# ---------------------------------------------------------------------------


def test_detect_groups_finds_duplicates(tmp_path):
    game_ids = [f"2025-05-08_T{i:03d}" for i in range(20)]
    for d in ["2026-05-01", "2026-05-02", "2026-05-03"]:
        _make_csv(tmp_path, d, game_ids, "2025-05-08")
    results = audit_materialized_source_hashes(
        ["2026-05-01", "2026-05-02", "2026-05-03"], str(tmp_path)
    )
    findings = detect_duplicate_source_groups(results)
    assert len(findings) == 1
    assert findings[0].n_dates == 3
    assert set(findings[0].dates_in_group) == {"2026-05-01", "2026-05-02", "2026-05-03"}
    assert findings[0].is_date_mismatch is True


def test_detect_groups_no_duplicates(tmp_path):
    for i, d in enumerate(["2026-05-01", "2026-05-02"]):
        game_ids = [f"{d}_T{j:03d}" for j in range(5 + i)]
        _make_csv(tmp_path, d, game_ids, d)
    results = audit_materialized_source_hashes(
        ["2026-05-01", "2026-05-02"], str(tmp_path)
    )
    findings = detect_duplicate_source_groups(results)
    assert len(findings) == 0


# ---------------------------------------------------------------------------
# summarize_source_integrity — gate outcomes
# ---------------------------------------------------------------------------


def test_summarize_blocks_on_majority_duplicate(tmp_path):
    game_ids = [f"2025-05-08_T{i:03d}" for i in range(20)]
    dates = [f"2026-05-{d:02d}" for d in range(1, 13)]
    for d in dates:
        _make_csv(tmp_path, d, game_ids, "2025-05-08")
    results = audit_materialized_source_hashes(dates, str(tmp_path))
    findings = detect_duplicate_source_groups(results)
    profile = summarize_source_integrity(results, findings, len(dates))
    assert profile.audit_status == STABILITY_SOURCE_INTEGRITY_BLOCKED
    assert profile.n_duplicate_source_groups == 1
    assert profile.n_independent_source_dates == 0


def test_summarize_acceptable_on_independent_dates(tmp_path):
    dates = [f"2026-05-{d:02d}" for d in range(1, 4)]
    for d in dates:
        game_ids = [f"{d}_T{i:03d}" for i in range(10)]
        _make_csv(tmp_path, d, game_ids, d)
    results = audit_materialized_source_hashes(dates, str(tmp_path))
    findings = detect_duplicate_source_groups(results)
    profile = summarize_source_integrity(results, findings, len(dates))
    assert profile.n_duplicate_source_groups == 0
    assert profile.audit_status == STABILITY_ACCEPTABLE
    assert profile.n_independent_source_dates == 3
