"""Tests for P35 import validator skeletons."""
import json
import os
import tempfile

import pytest

from wbc_backend.recommendation.p35_dual_source_import_validation_contract import (
    ODDS_REQUIRED_COLUMNS,
    PREDICTION_REQUIRED_COLUMNS,
)
from wbc_backend.recommendation.p35_import_validator_skeletons import (
    OUT_ODDS_VALIDATOR_SPEC,
    OUT_PREDICTION_VALIDATOR_SPEC,
    build_odds_import_validator_spec,
    build_prediction_import_validator_spec,
    validate_validator_specs,
    write_validator_specs,
)


# ---------------------------------------------------------------------------
# build_odds_import_validator_spec
# ---------------------------------------------------------------------------


def test_odds_spec_returns_dict():
    spec = build_odds_import_validator_spec()
    assert isinstance(spec, dict)


def test_odds_spec_has_all_required_columns():
    spec = build_odds_import_validator_spec()
    spec_cols = set(spec["required_columns"])
    required = set(ODDS_REQUIRED_COLUMNS)
    assert required == spec_cols, f"Missing: {required - spec_cols}"


def test_odds_spec_11_required_columns():
    spec = build_odds_import_validator_spec()
    assert len(spec["required_columns"]) == 11


def test_odds_spec_paper_only():
    spec = build_odds_import_validator_spec()
    assert spec["paper_only"] is True
    assert spec["production_ready"] is False


def test_odds_spec_has_field_rules():
    spec = build_odds_import_validator_spec()
    assert "field_rules" in spec
    assert isinstance(spec["field_rules"], dict)


def test_odds_spec_has_global_rules():
    spec = build_odds_import_validator_spec()
    assert "global_rules" in spec
    assert "no_outcome_derived_odds" in spec["global_rules"]


def test_odds_spec_field_rules_cover_all_required_columns():
    spec = build_odds_import_validator_spec()
    for col in ODDS_REQUIRED_COLUMNS:
        assert col in spec["field_rules"], f"Missing field rule for: {col}"


# ---------------------------------------------------------------------------
# build_prediction_import_validator_spec
# ---------------------------------------------------------------------------


def test_prediction_spec_returns_dict():
    spec = build_prediction_import_validator_spec()
    assert isinstance(spec, dict)


def test_prediction_spec_has_all_required_columns():
    spec = build_prediction_import_validator_spec()
    spec_cols = set(spec["required_columns"])
    required = set(PREDICTION_REQUIRED_COLUMNS)
    assert required == spec_cols, f"Missing: {required - spec_cols}"


def test_prediction_spec_9_required_columns():
    spec = build_prediction_import_validator_spec()
    assert len(spec["required_columns"]) == 9


def test_prediction_spec_paper_only():
    spec = build_prediction_import_validator_spec()
    assert spec["paper_only"] is True
    assert spec["production_ready"] is False


def test_prediction_spec_generated_without_y_true_must_be_true():
    spec = build_prediction_import_validator_spec()
    assert "generated_without_y_true" in spec["field_rules"]
    rule = spec["field_rules"]["generated_without_y_true"]
    assert rule.get("must_be_true") is True


def test_prediction_spec_has_no_y_true_derived_global_rule():
    spec = build_prediction_import_validator_spec()
    assert "no_y_true_derived_predictions" in spec["global_rules"]


def test_prediction_spec_field_rules_cover_all_required_columns():
    spec = build_prediction_import_validator_spec()
    for col in PREDICTION_REQUIRED_COLUMNS:
        assert col in spec["field_rules"], f"Missing field rule for: {col}"


# ---------------------------------------------------------------------------
# write_validator_specs
# ---------------------------------------------------------------------------


def test_write_validator_specs_writes_two_files():
    with tempfile.TemporaryDirectory() as tmp:
        written = write_validator_specs(tmp)
    assert len(written) == 2


def test_write_validator_specs_files_exist():
    with tempfile.TemporaryDirectory() as tmp:
        write_validator_specs(tmp)
        assert os.path.isfile(os.path.join(tmp, OUT_ODDS_VALIDATOR_SPEC))
        assert os.path.isfile(os.path.join(tmp, OUT_PREDICTION_VALIDATOR_SPEC))


def test_write_validator_specs_files_are_valid_json():
    with tempfile.TemporaryDirectory() as tmp:
        write_validator_specs(tmp)
        for fname in (OUT_ODDS_VALIDATOR_SPEC, OUT_PREDICTION_VALIDATOR_SPEC):
            path = os.path.join(tmp, fname)
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            assert isinstance(data, dict)


def test_write_validator_specs_files_nonempty():
    with tempfile.TemporaryDirectory() as tmp:
        write_validator_specs(tmp)
        for fname in (OUT_ODDS_VALIDATOR_SPEC, OUT_PREDICTION_VALIDATOR_SPEC):
            path = os.path.join(tmp, fname)
            assert os.path.getsize(path) > 0


def test_write_validator_specs_creates_output_dir():
    with tempfile.TemporaryDirectory() as tmp:
        sub = os.path.join(tmp, "new_output", "nested")
        write_validator_specs(sub)
        assert os.path.isdir(sub)


# ---------------------------------------------------------------------------
# validate_validator_specs
# ---------------------------------------------------------------------------


def test_validate_valid_after_write():
    with tempfile.TemporaryDirectory() as tmp:
        write_validator_specs(tmp)
        assert validate_validator_specs(tmp) is True


def test_validate_fails_if_file_missing():
    with tempfile.TemporaryDirectory() as tmp:
        # Only write odds spec
        spec = build_odds_import_validator_spec()
        spec["generated_at"] = "2026-01-01T00:00:00Z"
        with open(os.path.join(tmp, OUT_ODDS_VALIDATOR_SPEC), "w") as fh:
            json.dump(spec, fh)
        # prediction spec is missing
        assert validate_validator_specs(tmp) is False


def test_validate_fails_if_empty_dir():
    with tempfile.TemporaryDirectory() as tmp:
        assert validate_validator_specs(tmp) is False


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_write_validator_specs_deterministic_required_columns():
    """Two runs should produce specs with identical required_columns (excluding generated_at)."""
    with tempfile.TemporaryDirectory() as tmp1:
        write_validator_specs(tmp1)
        with open(os.path.join(tmp1, OUT_ODDS_VALIDATOR_SPEC), encoding="utf-8") as fh:
            spec1 = json.load(fh)

    with tempfile.TemporaryDirectory() as tmp2:
        write_validator_specs(tmp2)
        with open(os.path.join(tmp2, OUT_ODDS_VALIDATOR_SPEC), encoding="utf-8") as fh:
            spec2 = json.load(fh)

    assert sorted(spec1["required_columns"]) == sorted(spec2["required_columns"])
    assert spec1["field_rules"].keys() == spec2["field_rules"].keys()
    assert spec1["global_rules"].keys() == spec2["global_rules"].keys()
    assert spec1["paper_only"] == spec2["paper_only"]
    assert spec1["production_ready"] == spec2["production_ready"]
