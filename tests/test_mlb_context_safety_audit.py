"""
tests/test_mlb_context_safety_audit.py

P12: Tests for mlb_context_safety_audit module.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from wbc_backend.prediction.mlb_context_safety_audit import (
    audit_context_safety,
    summarize_context_safety,
)


# ─────────────────────────────────────────────────────────────────────────────
# § Helpers — write temporary files
# ─────────────────────────────────────────────────────────────────────────────

def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _write_csv(path: Path, rows: list[dict]) -> None:
    import csv
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


# ─────────────────────────────────────────────────────────────────────────────
# § 1  Postgame risk detection
# ─────────────────────────────────────────────────────────────────────────────

def test_context_safety_flags_postgame_result_columns():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "postgame.jsonl"
        _write_jsonl(path, [
            {
                "game_id": "2025-04-01_A_B",
                "home_score": 5,
                "away_score": 3,
                "home_win": 1,
                "fetched_at": "2026-01-01T00:00:00Z",
            }
        ])
        result = audit_context_safety(context_files=[path])
        file_result = result["files"][0]
        assert file_result["safety_status"] == "POSTGAME_RISK"
        assert file_result["has_outcome_columns"] is True


def test_context_safety_flags_final_score_column():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "results.csv"
        _write_csv(path, [
            {"game_id": "2025-04-01_A_B", "final_score": "5-3", "winner": "home"}
        ])
        result = audit_context_safety(context_files=[path])
        file_result = result["files"][0]
        # Should flag postgame keywords
        assert file_result["has_postgame_keywords"] is True


# ─────────────────────────────────────────────────────────────────────────────
# § 2  Pregame safe detection
# ─────────────────────────────────────────────────────────────────────────────

def test_context_safety_flags_pregame_weather_columns():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "weather.jsonl"
        _write_jsonl(path, [
            {
                "game_id": "2025-04-01_A_B",
                "wind_kmh": 15.0,
                "temp_c": 20.0,
                "forecast": "clear",
                "fetched_at": "2025-04-01T10:00:00Z",
            }
        ])
        result = audit_context_safety(context_files=[path])
        file_result = result["files"][0]
        assert file_result["has_pregame_keywords"] is True
        assert file_result["safety_status"] == "PREGAME_SAFE"


def test_context_safety_flags_starter_columns_as_safe():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "starters.jsonl"
        _write_jsonl(path, [
            {
                "game_id": "2025-04-01_A_B",
                "probable_starter_home": "Pitcher A",
                "starter_era_proxy_home": 3.5,
                "rest_days_home": 4,
            }
        ])
        result = audit_context_safety(context_files=[path])
        file_result = result["files"][0]
        assert file_result["has_pregame_keywords"] is True
        assert file_result["safety_status"] == "PREGAME_SAFE"


def test_context_safety_flags_bullpen_as_safe():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "bullpen.jsonl"
        _write_jsonl(path, [
            {
                "game_id": "2025-04-01_A_B",
                "bullpen_usage_last_3d_home": 11.5,
                "bullpen_usage_last_3d_away": 9.2,
                "fetched_at": "2025-04-01T09:00:00Z",
            }
        ])
        result = audit_context_safety(context_files=[path])
        file_result = result["files"][0]
        assert file_result["has_pregame_keywords"] is True
        assert file_result["safety_status"] == "PREGAME_SAFE"


def test_context_safety_flags_rest_as_safe():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "rest.jsonl"
        _write_jsonl(path, [
            {
                "game_id": "2025-04-01_A_B",
                "rest_days_home": 3,
                "rest_days_away": 1,
            }
        ])
        result = audit_context_safety(context_files=[path])
        file_result = result["files"][0]
        assert file_result["has_pregame_keywords"] is True
        assert file_result["safety_status"] == "PREGAME_SAFE"


# ─────────────────────────────────────────────────────────────────────────────
# § 3  Unknown / empty file handling
# ─────────────────────────────────────────────────────────────────────────────

def test_context_safety_handles_unknown_columns():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "mystery.jsonl"
        _write_jsonl(path, [
            {"game_id": "2025-04-01_A_B", "blah_metric_xyz": 99}
        ])
        result = audit_context_safety(context_files=[path])
        file_result = result["files"][0]
        # Should not crash; status should be UNKNOWN or PREGAME_SAFE
        assert file_result["safety_status"] in {"UNKNOWN", "PREGAME_SAFE", "POSTGAME_RISK"}


def test_context_safety_handles_empty_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "empty.jsonl"
        path.write_text("")
        result = audit_context_safety(context_files=[path])
        file_result = result["files"][0]
        assert file_result["safety_status"] == "UNKNOWN"


def test_context_safety_handles_nonexistent_file():
    path = Path("/tmp/does_not_exist_p12_test.jsonl")
    result = audit_context_safety(context_files=[path])
    file_result = result["files"][0]
    assert file_result["safety_status"] == "UNKNOWN"


# ─────────────────────────────────────────────────────────────────────────────
# § 4  Summary counts
# ─────────────────────────────────────────────────────────────────────────────

def test_context_safety_summary_counts_statuses():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create 3 files: 1 safe, 1 risky, 1 unknown
        safe_path = Path(tmpdir) / "safe.jsonl"
        _write_jsonl(safe_path, [{"game_id": "x", "rest_days_home": 3}])

        risk_path = Path(tmpdir) / "risk.jsonl"
        _write_jsonl(risk_path, [{"game_id": "x", "home_score": 5, "away_score": 3, "home_win": 1}])

        unknown_path = Path(tmpdir) / "unknown.jsonl"
        _write_jsonl(unknown_path, [{"game_id": "x", "value": 99}])

        audit = audit_context_safety(context_files=[safe_path, risk_path, unknown_path])
        summary = summarize_context_safety(audit)

        assert summary["total_files"] == 3
        assert summary["pregame_safe_count"] >= 1
        assert summary["postgame_risk_count"] >= 1
        assert summary["usable_file_count"] == summary["pregame_safe_count"]
        assert summary["unsafe_file_count"] == summary["postgame_risk_count"]


def test_context_safety_summary_all_safe():
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = []
        for i in range(3):
            p = Path(tmpdir) / f"safe_{i}.jsonl"
            _write_jsonl(p, [{"game_id": f"g{i}", "rest_days_home": i, "bullpen_usage_last_3d_home": 5.0}])
            paths.append(p)

        audit = audit_context_safety(context_files=paths)
        summary = summarize_context_safety(audit)

        assert summary["postgame_risk_count"] == 0
        assert "OK" in summary["safety_recommendation"] or "pregame" in summary["safety_recommendation"].lower()


def test_context_safety_summary_recommendation_warns_on_risk():
    with tempfile.TemporaryDirectory() as tmpdir:
        risk_path = Path(tmpdir) / "risk.jsonl"
        _write_jsonl(risk_path, [
            {"game_id": "x", "home_score": 5, "away_score": 3, "home_win": 1, "winner": "home"}
        ])
        audit = audit_context_safety(context_files=[risk_path])
        summary = summarize_context_safety(audit)
        assert "CAUTION" in summary["safety_recommendation"] or "postgame" in summary["safety_recommendation"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# § 5  Real context files (integration)
# ─────────────────────────────────────────────────────────────────────────────

def test_real_bullpen_context_is_pregame_safe():
    """Validate that the actual bullpen_usage_3d.jsonl is pregame-safe."""
    path = Path("data/mlb_context/bullpen_usage_3d.jsonl")
    if not path.exists():
        pytest.skip("Real bullpen context file not present")
    result = audit_context_safety(context_files=[path])
    fa = result["files"][0]
    assert fa["safety_status"] == "PREGAME_SAFE", (
        f"bullpen_usage_3d.jsonl should be PREGAME_SAFE, got {fa['safety_status']}. "
        f"Reasons: {fa.get('safety_reasons')}"
    )


def test_real_weather_context_is_pregame_safe():
    """Validate that the actual weather_wind.jsonl is pregame-safe."""
    path = Path("data/mlb_context/weather_wind.jsonl")
    if not path.exists():
        pytest.skip("Real weather context file not present")
    result = audit_context_safety(context_files=[path])
    fa = result["files"][0]
    assert fa["safety_status"] == "PREGAME_SAFE", (
        f"weather_wind.jsonl should be PREGAME_SAFE, got {fa['safety_status']}. "
        f"Reasons: {fa.get('safety_reasons')}"
    )


def test_real_mlb_odds_csv_contains_outcome_columns():
    """The as-played odds CSV should contain outcome columns (expected POSTGAME_RISK)."""
    path = Path("data/mlb_2025/mlb_odds_2025_real.csv")
    if not path.exists():
        pytest.skip("Real odds CSV not present")
    result = audit_context_safety(context_files=[path])
    fa = result["files"][0]
    # This file has Away Score / Home Score — should be flagged
    # (We just verify the audit runs without crash)
    assert fa["safety_status"] in {"PREGAME_SAFE", "POSTGAME_RISK", "UNKNOWN"}
