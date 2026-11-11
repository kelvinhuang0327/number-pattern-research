"""
tests/test_p37_5_manual_approval_docs.py

P37.5 — Tests for manual odds approval package documentation files and examples.

Verifies:
  - All four documentation files exist at correct paths
  - Documentation files contain required content markers
  - Example JSON has all 17 required approval record fields
  - Example JSON enforces PAPER_ONLY=true and PRODUCTION_READY=false
  - Example CSV has all 11 required columns
  - Example CSV data row uses EXAMPLE_* placeholder values

PAPER_ONLY: True
PRODUCTION_READY: False
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import pytest

# ──────────────────────────────────────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────────────────────────────────────

DOCS_DIR = Path(__file__).parent.parent / "docs" / "betting" / "manual_odds_approval"

APPROVAL_PACKAGE_MD = DOCS_DIR / "P37_5_APPROVAL_PACKAGE.md"
OPERATOR_CHECKLIST_MD = DOCS_DIR / "P37_5_OPERATOR_CHECKLIST.md"
PROVIDER_TOS_MD = DOCS_DIR / "P37_5_PROVIDER_TOS_REVIEW_TEMPLATE.md"
MANUAL_IMPORT_RUNBOOK_MD = DOCS_DIR / "P37_5_MANUAL_IMPORT_RUNBOOK.md"

EXAMPLE_APPROVAL_JSON = DOCS_DIR / "odds_approval_record_EXAMPLE_PLACEHOLDER.json"
EXAMPLE_ODDS_CSV = DOCS_DIR / "odds_2024_approved_EXAMPLE_TEMPLATE.csv"

REQUIRED_JSON_FIELDS = [
    "provider_name",
    "source_name",
    "source_url_or_reference",
    "license_terms_summary",
    "allowed_use",
    "redistribution_allowed",
    "attribution_required",
    "internal_research_allowed",
    "commercial_use_allowed",
    "approved_by",
    "approved_at",
    "approval_scope",
    "source_file_expected_path",
    "checksum_required",
    "checksum_sha256",
    "paper_only",
    "production_ready",
]

REQUIRED_CSV_COLUMNS = [
    "game_id",
    "game_date",
    "home_team",
    "away_team",
    "p_market",
    "odds_decimal",
    "sportsbook",
    "market_type",
    "closing_timestamp",
    "source_odds_ref",
    "license_ref",
]


# ──────────────────────────────────────────────────────────────────────────────
# File existence tests
# ──────────────────────────────────────────────────────────────────────────────

class TestDocumentFilesExist:
    def test_approval_package_md_exists(self) -> None:
        assert APPROVAL_PACKAGE_MD.exists(), f"Missing: {APPROVAL_PACKAGE_MD}"

    def test_operator_checklist_md_exists(self) -> None:
        assert OPERATOR_CHECKLIST_MD.exists(), f"Missing: {OPERATOR_CHECKLIST_MD}"

    def test_provider_tos_review_template_md_exists(self) -> None:
        assert PROVIDER_TOS_MD.exists(), f"Missing: {PROVIDER_TOS_MD}"

    def test_manual_import_runbook_md_exists(self) -> None:
        assert MANUAL_IMPORT_RUNBOOK_MD.exists(), f"Missing: {MANUAL_IMPORT_RUNBOOK_MD}"

    def test_example_approval_json_exists(self) -> None:
        assert EXAMPLE_APPROVAL_JSON.exists(), f"Missing: {EXAMPLE_APPROVAL_JSON}"

    def test_example_odds_csv_exists(self) -> None:
        assert EXAMPLE_ODDS_CSV.exists(), f"Missing: {EXAMPLE_ODDS_CSV}"


# ──────────────────────────────────────────────────────────────────────────────
# Content marker tests — docs reference no-raw-commit
# ──────────────────────────────────────────────────────────────────────────────

class TestDocumentContent:
    def test_approval_package_mentions_no_raw_odds_commit(self) -> None:
        content = APPROVAL_PACKAGE_MD.read_text(encoding="utf-8")
        assert (
            "raw_odds_commit_allowed" in content or "raw odds" in content.lower()
        ), "P37_5_APPROVAL_PACKAGE.md must mention no raw odds commit policy"

    def test_approval_package_mentions_approval_record_required(self) -> None:
        content = APPROVAL_PACKAGE_MD.read_text(encoding="utf-8")
        assert "approval record" in content.lower(), (
            "P37_5_APPROVAL_PACKAGE.md must mention approval record requirement"
        )

    def test_operator_checklist_mentions_no_raw_odds_commit(self) -> None:
        content = OPERATOR_CHECKLIST_MD.read_text(encoding="utf-8")
        assert (
            "Do NOT commit" in content or "never" in content.lower()
        ), "Operator checklist must warn against committing manual_import files"

    def test_operator_checklist_mentions_approval_record(self) -> None:
        content = OPERATOR_CHECKLIST_MD.read_text(encoding="utf-8")
        assert "approval_record" in content or "approval record" in content.lower()

    def test_operator_checklist_mentions_paper_only(self) -> None:
        content = OPERATOR_CHECKLIST_MD.read_text(encoding="utf-8")
        assert "paper_only" in content or "PAPER_ONLY" in content

    def test_runbook_mentions_no_raw_odds_commit(self) -> None:
        content = MANUAL_IMPORT_RUNBOOK_MD.read_text(encoding="utf-8")
        assert (
            "commit" in content.lower() and "raw" in content.lower()
        ), "Runbook must warn against committing raw odds"

    def test_runbook_mentions_approval_record(self) -> None:
        content = MANUAL_IMPORT_RUNBOOK_MD.read_text(encoding="utf-8")
        assert "approval_record" in content or "approval record" in content.lower()

    def test_runbook_mentions_p37_gate(self) -> None:
        content = MANUAL_IMPORT_RUNBOOK_MD.read_text(encoding="utf-8")
        assert "p37" in content.lower() or "P37" in content

    def test_provider_tos_template_mentions_research_use(self) -> None:
        content = PROVIDER_TOS_MD.read_text(encoding="utf-8")
        assert "internal_research_allowed" in content or "research" in content.lower()

    def test_provider_tos_template_mentions_paper_only(self) -> None:
        content = PROVIDER_TOS_MD.read_text(encoding="utf-8")
        assert "paper_only" in content


# ──────────────────────────────────────────────────────────────────────────────
# Example JSON tests
# ──────────────────────────────────────────────────────────────────────────────

class TestExampleApprovalJson:
    @pytest.fixture(scope="class")
    def example_json(self) -> dict:
        with open(EXAMPLE_APPROVAL_JSON, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def test_example_json_is_dict(self, example_json: dict) -> None:
        assert isinstance(example_json, dict)

    @pytest.mark.parametrize("field", REQUIRED_JSON_FIELDS)
    def test_example_json_has_required_field(self, example_json: dict, field: str) -> None:
        assert field in example_json, f"Example JSON missing required field: {field}"

    def test_example_json_paper_only_is_true(self, example_json: dict) -> None:
        assert example_json["paper_only"] is True, "Example JSON must have paper_only=true"

    def test_example_json_production_ready_is_false(self, example_json: dict) -> None:
        assert example_json["production_ready"] is False, (
            "Example JSON must have production_ready=false"
        )

    def test_example_json_internal_research_allowed_is_true(self, example_json: dict) -> None:
        assert example_json["internal_research_allowed"] is True, (
            "Example JSON must have internal_research_allowed=true"
        )

    def test_example_json_commercial_use_allowed_is_false(self, example_json: dict) -> None:
        assert example_json["commercial_use_allowed"] is False

    def test_example_json_allowed_use_is_internal_research(self, example_json: dict) -> None:
        assert example_json["allowed_use"] == "internal_research"

    def test_example_json_has_17_required_fields(self, example_json: dict) -> None:
        present = [f for f in REQUIRED_JSON_FIELDS if f in example_json]
        assert len(present) == 17, f"Expected 17 required fields, found {len(present)}"

    def test_example_json_placeholder_values_present(self, example_json: dict) -> None:
        """Free-form fields must use PLACEHOLDER_ prefix; fixed-value fields are excluded."""
        # approval_scope and source_file_expected_path have well-known fixed values
        string_fields = [
            "provider_name", "source_name", "source_url_or_reference",
            "license_terms_summary", "approved_by", "approved_at",
            "checksum_sha256",
        ]
        for field in string_fields:
            value = example_json.get(field, "")
            assert "PLACEHOLDER" in str(value), (
                f"Example JSON field '{field}' should have a PLACEHOLDER value, got: {value!r}"
            )


# ──────────────────────────────────────────────────────────────────────────────
# Example CSV tests
# ──────────────────────────────────────────────────────────────────────────────

class TestExampleOddsCsv:
    @pytest.fixture(scope="class")
    def csv_rows(self) -> list:
        with open(EXAMPLE_ODDS_CSV, "r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            return list(reader)

    @pytest.fixture(scope="class")
    def csv_header(self) -> list:
        with open(EXAMPLE_ODDS_CSV, "r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            return reader.fieldnames or []

    @pytest.mark.parametrize("col", REQUIRED_CSV_COLUMNS)
    def test_example_csv_has_required_column(self, csv_header: list, col: str) -> None:
        assert col in csv_header, f"Example CSV missing required column: {col}"

    def test_example_csv_has_exactly_11_columns(self, csv_header: list) -> None:
        assert len(csv_header) == 11, (
            f"Expected 11 columns, found {len(csv_header)}: {csv_header}"
        )

    def test_example_csv_has_one_data_row(self, csv_rows: list) -> None:
        assert len(csv_rows) == 1, f"Expected 1 example row, found {len(csv_rows)}"

    def test_example_csv_row_values_are_example_prefix(self, csv_rows: list) -> None:
        """Free-form string columns use EXAMPLE_ prefix; market_type uses a valid constant."""
        row = csv_rows[0]
        # market_type is validated separately in test_example_csv_market_type_is_valid
        example_string_cols = [
            "game_id", "game_date", "home_team", "away_team",
            "sportsbook", "closing_timestamp",
            "source_odds_ref", "license_ref",
        ]
        for col in example_string_cols:
            val = row.get(col, "")
            assert "EXAMPLE" in str(val), (
                f"Example CSV column '{col}' should start with EXAMPLE_, got: {val!r}"
            )

    def test_example_csv_p_market_is_numeric(self, csv_rows: list) -> None:
        val = float(csv_rows[0]["p_market"])
        assert 0.0 < val < 1.0, f"p_market should be in (0,1), got {val}"

    def test_example_csv_odds_decimal_is_at_least_one(self, csv_rows: list) -> None:
        val = float(csv_rows[0]["odds_decimal"])
        assert val >= 1.0, f"odds_decimal should be >= 1.0, got {val}"

    def test_example_csv_market_type_is_valid(self, csv_rows: list) -> None:
        valid = {"moneyline", "ml", "money_line", "1x2", "h2h"}
        val = csv_rows[0]["market_type"]
        assert val in valid, f"market_type should be one of {valid}, got {val!r}"
