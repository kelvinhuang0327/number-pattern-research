"""
Phase 6R — Native Timestamp Integration Tests
===============================================
Tests that:
  1. ML-only adapter writes all 9 native timestamp fields
  2. timestamp_capture_version = "6R-1.0"
  3. prediction_time_source is validator-approved
  4. feature_cutoff_source is not "UNKNOWN"
  5. Timing order invariant holds for all rows
  6. Historical file is not mutated by Phase 6R adapter
  7. Validator M13 passes for all Phase 6R fixture rows
  8. NativeTimestampCapture helper stage lifecycle
  9. validate_chain() detects ordering violations
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(REPO_ROOT))

from native_timestamp_helper import (
    NativeTimestampCapture,
    TIMESTAMP_CAPTURE_VERSION,
    PREDICTION_TIME_SOURCE,
    FEATURE_CUTOFF_SOURCE_DEFAULT,
    _fmt_utc,
)
from build_ml_future_model_outputs import run_adapter, _ELO_RATINGS, _elo_win_prob

# Phase 6P validator constants (used for T3 assertion)
ALLOWED_PREDICTION_TIME_SOURCES = [
    "MODEL_INFERENCE_RUNTIME",
    "MODEL_OUTPUT_EMISSION_RUNTIME",
    "SCHEDULER_RUN_RUNTIME",
]

HISTORICAL_FILE = REPO_ROOT / "data" / "derived" / "model_outputs_2026-04-29.jsonl"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def adapter_output(tmp_path_factory):
    """
    Run the Phase 6R adapter once and return the emitted rows.
    Uses a temporary output path so the real file is not touched.
    """
    out = tmp_path_factory.mktemp("6r") / "model_outputs_6r_test.jsonl"
    result = run_adapter(output_path=str(out))
    assert "error" not in result, f"Adapter error: {result}"
    rows = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
    return rows


@pytest.fixture(scope="module")
def historical_mtime():
    """Record historical file mtime before any Phase 6R work."""
    if HISTORICAL_FILE.exists():
        return HISTORICAL_FILE.stat().st_mtime
    return None


# ── TASK 7.1 — All 9 native timestamp fields present ─────────────────────────

NATIVE_FIELDS = [
    "prediction_run_started_at_utc",
    "feature_cutoff_time_utc",
    "prediction_time_utc",
    "prediction_run_completed_at_utc",
    "model_output_written_at_utc",
    "prediction_time_source",
    "feature_cutoff_source",
    "timestamp_capture_version",
    "timestamp_quality_flags",
]


def test_all_native_fields_present(adapter_output):
    """All 9 required native timestamp fields must be present in every row."""
    for i, row in enumerate(adapter_output):
        for field in NATIVE_FIELDS:
            assert field in row, f"row {i}: missing field '{field}'"
            # Datetime fields must not be None
            if field.endswith("_utc") and field not in ("timestamp_quality_flags",):
                assert row[field] is not None, (
                    f"row {i}: '{field}' is None (must be set)"
                )


# ── TASK 7.2 — timestamp_capture_version = "6R-1.0" ─────────────────────────

def test_timestamp_capture_version(adapter_output):
    """Every row must declare timestamp_capture_version = '6R-1.0'."""
    for i, row in enumerate(adapter_output):
        assert row["timestamp_capture_version"] == "6R-1.0", (
            f"row {i}: timestamp_capture_version = '{row.get('timestamp_capture_version')}', "
            "expected '6R-1.0'"
        )


# ── TASK 7.3 — prediction_time_source is validator-approved ──────────────────

def test_prediction_time_source_allowed(adapter_output):
    """prediction_time_source must be in the Phase 6P approved set."""
    for i, row in enumerate(adapter_output):
        pts = row.get("prediction_time_source")
        assert pts in ALLOWED_PREDICTION_TIME_SOURCES, (
            f"row {i}: prediction_time_source='{pts}' not in allowed set "
            f"{ALLOWED_PREDICTION_TIME_SOURCES}"
        )


def test_prediction_time_source_is_model_inference_runtime(adapter_output):
    """Phase 6R must use MODEL_INFERENCE_RUNTIME (system-clock inference time)."""
    for i, row in enumerate(adapter_output):
        assert row["prediction_time_source"] == "MODEL_INFERENCE_RUNTIME", (
            f"row {i}: expected MODEL_INFERENCE_RUNTIME"
        )


# ── TASK 7.4 — feature_cutoff_source is not UNKNOWN ─────────────────────────

def test_feature_cutoff_source_not_unknown(adapter_output):
    """feature_cutoff_source must never be 'UNKNOWN'."""
    for i, row in enumerate(adapter_output):
        fcs = row.get("feature_cutoff_source", "")
        assert fcs != "UNKNOWN", f"row {i}: feature_cutoff_source=UNKNOWN is forbidden"
        assert fcs, f"row {i}: feature_cutoff_source is empty"


# ── TASK 7.5 — Timestamp order invariant holds ───────────────────────────────

def _parse_iso(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def test_timestamp_ordering_invariant(adapter_output):
    """
    Verify: started <= feature_cutoff <= prediction <= completed <= written
    AND prediction < match_time (pre-game invariant, M6 T1).
    """
    for i, row in enumerate(adapter_output):
        rs = _parse_iso(row["prediction_run_started_at_utc"])
        fc = _parse_iso(row["feature_cutoff_time_utc"])
        pt = _parse_iso(row["prediction_time_utc"])
        mt = _parse_iso(row["match_time_utc"])
        rc = _parse_iso(row["prediction_run_completed_at_utc"])
        ow = _parse_iso(row["model_output_written_at_utc"])

        assert rs <= fc, f"row {i}: started > feature_cutoff"
        assert fc <= pt, f"row {i}: feature_cutoff > prediction"
        assert pt < mt, f"row {i}: prediction >= match_time (look-ahead leakage!)"
        assert pt <= rc, f"row {i}: prediction > run_completed"
        assert rc <= ow, f"row {i}: run_completed > output_written"


# ── TASK 7.6 — Historical file not mutated ───────────────────────────────────

def test_historical_file_not_mutated(historical_mtime, adapter_output):
    """
    Calling run_adapter() must not modify the Phase 6L historical output file.
    """
    if not HISTORICAL_FILE.exists():
        pytest.skip("Historical file not present in this environment")
    current_mtime = HISTORICAL_FILE.stat().st_mtime
    assert current_mtime == historical_mtime, (
        f"Historical file was modified! "
        f"Before={historical_mtime}, After={current_mtime}"
    )


def test_historical_rows_unchanged_count():
    """Historical JSONL row count must remain 2986."""
    if not HISTORICAL_FILE.exists():
        pytest.skip("Historical file not present")
    count = sum(1 for l in HISTORICAL_FILE.read_text().splitlines() if l.strip())
    assert count == 2986, f"Historical row count changed to {count} (expected 2986)"


# ── TASK 7.7 — M13 passes for 6R fixture rows ────────────────────────────────

def test_m13_native_timestamp_contract(adapter_output):
    """
    Inline M13 check: all Phase 6O fields must be present, prediction_time_source
    must be allowed, feature_cutoff_source must not be UNKNOWN,
    timestamp_quality_flags must be empty or contain no hard-fail flags.
    """
    HARD_FAIL_FLAGS = {
        "TIMESTAMP_MISSING",
        "TIMESTAMP_SOURCE_LOW_CONFIDENCE",
        "PREDICTION_TIME_AFTER_MATCH",
        "FEATURE_CUTOFF_AFTER_PREDICTION",
        "FEATURE_CUTOFF_AFTER_MATCH",
        "TIMESTAMP_CLOCK_DRIFT",
        "HISTORICAL_TIMESTAMP_RECOVERY",
        "ODDS_SNAPSHOT_AFTER_MATCH",
    }
    DISALLOWED_SOURCES = {"REPORT_METADATA", "FILE_METADATA_LOW_CONFIDENCE", "UNKNOWN"}

    m13_datetime_fields = [
        "prediction_run_started_at_utc",
        "prediction_run_completed_at_utc",
        "model_output_written_at_utc",
    ]

    for i, row in enumerate(adapter_output):
        # Datetime fields present
        for f in m13_datetime_fields:
            assert f in row and row[f] is not None, f"row {i}: M13 fail — {f} absent/null"

        # prediction_time_source
        pts = row.get("prediction_time_source")
        assert pts not in DISALLOWED_SOURCES, (
            f"row {i}: M13 fail — prediction_time_source='{pts}' is disallowed"
        )
        assert pts in ALLOWED_PREDICTION_TIME_SOURCES, (
            f"row {i}: M13 fail — prediction_time_source='{pts}' not in allowed set"
        )

        # feature_cutoff_source
        fcs = row.get("feature_cutoff_source")
        assert fcs and fcs != "UNKNOWN", (
            f"row {i}: M13 fail — feature_cutoff_source='{fcs}'"
        )

        # timestamp_capture_version
        tcv = row.get("timestamp_capture_version")
        assert tcv and isinstance(tcv, str) and tcv.strip(), (
            f"row {i}: M13 fail — timestamp_capture_version absent/empty"
        )

        # timestamp_quality_flags — no hard-fail flags
        tqf = row.get("timestamp_quality_flags") or []
        bad = [f for f in tqf if f in HARD_FAIL_FLAGS]
        assert not bad, f"row {i}: M13 fail — hard-fail flags: {bad}"


# ── NativeTimestampCapture unit tests ─────────────────────────────────────────

class TestNativeTimestampCapture:
    """Unit tests for the helper class itself."""

    def test_full_lifecycle_no_violation(self):
        """Calling all 5 stages in order must produce zero chain violations."""
        cap = NativeTimestampCapture()
        cap.start()
        time.sleep(0.001)
        cap.feature_loaded()
        time.sleep(0.001)
        cap.prediction_made()
        time.sleep(0.001)
        cap.run_completed()
        time.sleep(0.001)
        cap.output_written()

        violations = cap.validate_chain()
        assert violations == [], f"Unexpected violations: {violations}"

    def test_to_fields_all_stages_complete(self):
        """to_fields() returns 9 keys when all stages are done."""
        cap = NativeTimestampCapture()
        cap.start()
        cap.feature_loaded()
        cap.prediction_made()
        cap.run_completed()
        cap.output_written()

        fields = cap.to_fields()
        assert set(fields.keys()) == set(NATIVE_FIELDS), (
            f"to_fields() returned unexpected keys: {set(fields.keys())}"
        )

    def test_to_fields_raises_before_complete(self):
        """to_fields() must raise ValueError if stages are missing."""
        cap = NativeTimestampCapture()
        cap.start()
        with pytest.raises(ValueError, match="stages not yet called"):
            cap.to_fields()

    def test_early_fields_stage4_5_none(self):
        """early_fields() has None for run_completed and output_written."""
        cap = NativeTimestampCapture()
        cap.start()
        cap.feature_loaded()
        cap.prediction_made()
        ef = cap.early_fields()
        assert ef["prediction_run_completed_at_utc"] is None
        assert ef["model_output_written_at_utc"] is None
        assert ef["prediction_run_started_at_utc"] is not None
        assert ef["prediction_time_utc"] is not None

    def test_chain_violation_detected(self):
        """validate_chain() catches a manually injected ordering violation."""
        from datetime import timedelta
        cap = NativeTimestampCapture()
        cap.start()
        cap.feature_loaded()
        cap.prediction_made()
        cap.run_completed()
        cap.output_written()

        # Manually inject a violation: move run_started_at to the future
        cap._run_started_at = cap._prediction_time + timedelta(seconds=5)
        violations = cap.validate_chain()
        assert any("started > " in v for v in violations), (
            f"Expected chain violation not found: {violations}"
        )

    def test_timestamp_quality_flags_default_empty(self):
        """timestamp_quality_flags must default to empty list."""
        cap = NativeTimestampCapture()
        cap.start()
        cap.feature_loaded()
        cap.prediction_made()
        cap.run_completed()
        cap.output_written()
        fields = cap.to_fields()
        assert fields["timestamp_quality_flags"] == []

    def test_feature_cutoff_source_custom(self):
        """Custom feature_cutoff_source is preserved in to_fields()."""
        cap = NativeTimestampCapture()
        cap.start()
        cap.feature_loaded(source="LIVE_ELO_CACHE_V2")
        cap.prediction_made()
        cap.run_completed()
        cap.output_written()
        fields = cap.to_fields()
        assert fields["feature_cutoff_source"] == "LIVE_ELO_CACHE_V2"

    def test_timestamp_capture_version_constant(self):
        """timestamp_capture_version must equal the module constant."""
        cap = NativeTimestampCapture()
        cap.start()
        cap.feature_loaded()
        cap.prediction_made()
        cap.run_completed()
        cap.output_written()
        fields = cap.to_fields()
        assert fields["timestamp_capture_version"] == TIMESTAMP_CAPTURE_VERSION


# ── Adapter-level contract tests ──────────────────────────────────────────────

def test_adapter_row_count(adapter_output):
    """Adapter must emit exactly 10 rows (5 games × 2 ML sides)."""
    assert len(adapter_output) == 10


def test_adapter_dry_run_false(adapter_output):
    """All Phase 6R rows must have dry_run=False (real output, not stub)."""
    for i, row in enumerate(adapter_output):
        assert row.get("dry_run") is False, f"row {i}: expected dry_run=False"


def test_adapter_predicted_probability_real(adapter_output):
    """predicted_probability must be a real float in [0, 1], not null."""
    for i, row in enumerate(adapter_output):
        pp = row.get("predicted_probability")
        assert pp is not None, f"row {i}: predicted_probability is null"
        assert isinstance(pp, float), f"row {i}: predicted_probability not float"
        assert 0.0 < pp < 1.0, f"row {i}: predicted_probability={pp} out of (0,1)"


def test_adapter_market_type_ml_only(adapter_output):
    """Phase 6R adapter emits only ML market rows."""
    for i, row in enumerate(adapter_output):
        assert row.get("market_type") == "ML", (
            f"row {i}: market_type={row.get('market_type')} (expected ML)"
        )


def test_adapter_schema_version_6j(adapter_output):
    """schema_version must remain '6j-1.0' (backward compatible)."""
    for i, row in enumerate(adapter_output):
        assert row.get("schema_version") == "6j-1.0", (
            f"row {i}: schema_version={row.get('schema_version')}"
        )


def test_adapter_clv_usable_false_phase6s_blocker(adapter_output):
    """clv_usable must be False — Phase 6S odds_snapshot_ref not yet aligned."""
    for i, row in enumerate(adapter_output):
        assert row.get("clv_usable") is False, (
            f"row {i}: clv_usable should be False pending Phase 6S"
        )


def test_elo_win_probability_bounds():
    """Elo win probability must be in (0, 1) for any Elo difference."""
    for h_elo in [1400, 1500, 1600]:
        for a_elo in [1400, 1500, 1600]:
            p = _elo_win_prob(h_elo, a_elo)
            assert 0.0 < p < 1.0, f"elo_win_prob({h_elo},{a_elo}) = {p} out of range"


def test_elo_home_advantage_positive():
    """Home-field advantage must always increase home-win probability."""
    p_no_adv = _elo_win_prob(1500, 1500, home_field_adv=0.0)
    p_with_adv = _elo_win_prob(1500, 1500, home_field_adv=35.0)
    assert p_with_adv > p_no_adv, "Home-field advantage must increase home-win probability"
