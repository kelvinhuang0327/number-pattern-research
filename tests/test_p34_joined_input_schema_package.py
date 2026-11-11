"""Tests for p34_joined_input_schema_package.py"""

from __future__ import annotations

import csv
import json
import os
import tempfile

import pytest

from wbc_backend.recommendation.p34_dual_source_acquisition_contract import (
    ODDS_TEMPLATE_COLUMNS,
    PREDICTION_TEMPLATE_COLUMNS,
)
from wbc_backend.recommendation.p34_joined_input_schema_package import (
    OUT_ODDS_TEMPLATE,
    OUT_PREDICTION_TEMPLATE,
    OUT_VALIDATION_RULES,
    build_joined_input_validation_rules,
    build_odds_schema_template,
    build_prediction_schema_template,
    validate_schema_templates,
    write_schema_templates,
)


class TestBuildPredictionSchemaTemplate:
    def test_returns_schema_requirement(self):
        from wbc_backend.recommendation.p34_dual_source_acquisition_contract import P34SchemaRequirement
        schema = build_prediction_schema_template()
        assert isinstance(schema, P34SchemaRequirement)

    def test_prediction_columns_match(self):
        schema = build_prediction_schema_template()
        assert schema.prediction_columns == PREDICTION_TEMPLATE_COLUMNS

    def test_season_2024(self):
        schema = build_prediction_schema_template()
        assert schema.season == 2024

    def test_paper_only(self):
        schema = build_prediction_schema_template()
        assert schema.paper_only is True
        assert schema.production_ready is False


class TestBuildOddsSchemaTemplate:
    def test_returns_schema_requirement(self):
        from wbc_backend.recommendation.p34_dual_source_acquisition_contract import P34SchemaRequirement
        schema = build_odds_schema_template()
        assert isinstance(schema, P34SchemaRequirement)

    def test_odds_columns_match(self):
        schema = build_odds_schema_template()
        assert schema.odds_columns == ODDS_TEMPLATE_COLUMNS

    def test_season_2024(self):
        schema = build_odds_schema_template()
        assert schema.season == 2024

    def test_paper_only(self):
        schema = build_odds_schema_template()
        assert schema.paper_only is True


class TestBuildJoinedInputValidationRules:
    def test_returns_dict(self):
        rules = build_joined_input_validation_rules()
        assert isinstance(rules, dict)

    def test_paper_only_in_rules(self):
        rules = build_joined_input_validation_rules()
        assert rules["paper_only"] is True
        assert rules["production_ready"] is False

    def test_season_2024(self):
        rules = build_joined_input_validation_rules()
        assert rules["season"] == 2024

    def test_required_fields_present(self):
        rules = build_joined_input_validation_rules()
        assert "required_fields" in rules
        assert "prediction" in rules["required_fields"]
        assert "odds" in rules["required_fields"]

    def test_field_rules_present(self):
        rules = build_joined_input_validation_rules()
        assert "field_rules" in rules
        field_names = [r["field"] for r in rules["field_rules"]]
        assert "game_id" in field_names
        assert "p_oof" in field_names
        assert "p_market" in field_names
        assert "odds_decimal" in field_names
        assert "generated_without_y_true" in field_names
        assert "license_ref" in field_names

    def test_global_rules_present(self):
        rules = build_joined_input_validation_rules()
        assert "global_rules" in rules
        rule_names = [r["rule"] for r in rules["global_rules"]]
        assert "no_production_ready" in rule_names
        assert "no_outcome_derived_odds" in rule_names
        assert "no_y_true_derived_predictions" in rule_names
        assert "season_2024_only" in rule_names

    def test_p_oof_range_rule(self):
        rules = build_joined_input_validation_rules()
        oof_rule = next((r for r in rules["field_rules"] if r["field"] == "p_oof"), None)
        assert oof_rule is not None
        assert oof_rule.get("min") == 0.0
        assert oof_rule.get("max") == 1.0

    def test_odds_decimal_min_greater_than_1(self):
        rules = build_joined_input_validation_rules()
        dec_rule = next((r for r in rules["field_rules"] if r["field"] == "odds_decimal"), None)
        assert dec_rule is not None
        assert dec_rule.get("min") == 1.0

    def test_license_ref_required(self):
        rules = build_joined_input_validation_rules()
        lic_rule = next((r for r in rules["field_rules"] if r["field"] == "license_ref"), None)
        assert lic_rule is not None

    def test_generated_without_y_true_must_be_true(self):
        rules = build_joined_input_validation_rules()
        yt_rule = next(
            (r for r in rules["field_rules"] if r["field"] == "generated_without_y_true"), None
        )
        assert yt_rule is not None
        assert yt_rule.get("rule") == "must_be_true"


class TestWriteSchemaTemplates:
    def test_writes_three_files(self, tmp_path):
        written = write_schema_templates(str(tmp_path))
        assert len(written) == 3

    def test_all_files_exist(self, tmp_path):
        write_schema_templates(str(tmp_path))
        assert os.path.isfile(tmp_path / OUT_PREDICTION_TEMPLATE)
        assert os.path.isfile(tmp_path / OUT_ODDS_TEMPLATE)
        assert os.path.isfile(tmp_path / OUT_VALIDATION_RULES)

    def test_prediction_template_header(self, tmp_path):
        write_schema_templates(str(tmp_path))
        with open(tmp_path / OUT_PREDICTION_TEMPLATE, encoding="utf-8") as fh:
            reader = csv.reader(fh)
            header = next(reader)
        assert header == list(PREDICTION_TEMPLATE_COLUMNS)

    def test_odds_template_header(self, tmp_path):
        write_schema_templates(str(tmp_path))
        with open(tmp_path / OUT_ODDS_TEMPLATE, encoding="utf-8") as fh:
            reader = csv.reader(fh)
            header = next(reader)
        assert header == list(ODDS_TEMPLATE_COLUMNS)

    def test_validation_rules_json_valid(self, tmp_path):
        write_schema_templates(str(tmp_path))
        with open(tmp_path / OUT_VALIDATION_RULES, encoding="utf-8") as fh:
            data = json.load(fh)
        assert isinstance(data, dict)
        assert data["paper_only"] is True

    def test_prediction_template_has_no_data_rows(self, tmp_path):
        """Template must be header-only; no fabricated data."""
        write_schema_templates(str(tmp_path))
        with open(tmp_path / OUT_PREDICTION_TEMPLATE, encoding="utf-8") as fh:
            reader = csv.reader(fh)
            rows = list(reader)
        # Only header row
        assert len(rows) == 1

    def test_odds_template_has_no_data_rows(self, tmp_path):
        write_schema_templates(str(tmp_path))
        with open(tmp_path / OUT_ODDS_TEMPLATE, encoding="utf-8") as fh:
            reader = csv.reader(fh)
            rows = list(reader)
        assert len(rows) == 1

    def test_creates_output_dir_if_missing(self, tmp_path):
        new_dir = str(tmp_path / "nested" / "output")
        write_schema_templates(new_dir)
        assert os.path.isdir(new_dir)

    def test_deterministic_across_two_runs(self, tmp_path):
        """Two consecutive writes to different dirs must produce identical outputs."""
        dir1 = str(tmp_path / "run1")
        dir2 = str(tmp_path / "run2")
        write_schema_templates(dir1)
        write_schema_templates(dir2)
        for fname in (OUT_PREDICTION_TEMPLATE, OUT_ODDS_TEMPLATE):
            c1 = open(os.path.join(dir1, fname), encoding="utf-8").read()
            c2 = open(os.path.join(dir2, fname), encoding="utf-8").read()
            assert c1 == c2, f"Mismatch in {fname}"
        # Validation rules should also be deterministic
        r1 = json.loads(open(os.path.join(dir1, OUT_VALIDATION_RULES), encoding="utf-8").read())
        r2 = json.loads(open(os.path.join(dir2, OUT_VALIDATION_RULES), encoding="utf-8").read())
        assert r1 == r2


class TestValidateSchemaTemplates:
    def test_valid_after_write(self, tmp_path):
        write_schema_templates(str(tmp_path))
        assert validate_schema_templates(str(tmp_path)) is True

    def test_invalid_if_prediction_template_missing(self, tmp_path):
        write_schema_templates(str(tmp_path))
        os.remove(tmp_path / OUT_PREDICTION_TEMPLATE)
        assert validate_schema_templates(str(tmp_path)) is False

    def test_invalid_if_odds_template_missing(self, tmp_path):
        write_schema_templates(str(tmp_path))
        os.remove(tmp_path / OUT_ODDS_TEMPLATE)
        assert validate_schema_templates(str(tmp_path)) is False

    def test_invalid_if_validation_rules_missing(self, tmp_path):
        write_schema_templates(str(tmp_path))
        os.remove(tmp_path / OUT_VALIDATION_RULES)
        assert validate_schema_templates(str(tmp_path)) is False

    def test_invalid_if_prediction_template_empty(self, tmp_path):
        write_schema_templates(str(tmp_path))
        (tmp_path / OUT_PREDICTION_TEMPLATE).write_text("")
        assert validate_schema_templates(str(tmp_path)) is False

    def test_invalid_if_prediction_header_wrong(self, tmp_path):
        write_schema_templates(str(tmp_path))
        (tmp_path / OUT_PREDICTION_TEMPLATE).write_text("wrong,columns\n")
        assert validate_schema_templates(str(tmp_path)) is False
