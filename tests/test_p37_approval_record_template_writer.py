"""
Tests for p37_approval_record_template_writer.py
"""
import json
import os
import tempfile

import pytest

from wbc_backend.recommendation.p37_approval_record_template_writer import (
    build_approval_record_template,
    validate_approval_record_template,
    write_approval_record_template,
    write_approval_record_instructions,
)
from wbc_backend.recommendation.p37_manual_odds_provisioning_contract import (
    APPROVAL_RECORD_TEMPLATE_FIELDS,
    PAPER_ONLY,
    PRODUCTION_READY,
)


class TestBuildApprovalRecordTemplate:
    def test_returns_dict(self):
        t = build_approval_record_template()
        assert isinstance(t, dict)

    def test_contains_all_required_fields(self):
        t = build_approval_record_template()
        for f in APPROVAL_RECORD_TEMPLATE_FIELDS:
            assert f in t, f"Missing field: {f}"

    def test_paper_only_true(self):
        t = build_approval_record_template()
        assert t["paper_only"] is True

    def test_production_ready_false(self):
        t = build_approval_record_template()
        assert t["production_ready"] is False

    def test_internal_research_allowed_true(self):
        t = build_approval_record_template()
        assert t["internal_research_allowed"] is True

    def test_allowed_use_is_internal_research(self):
        t = build_approval_record_template()
        assert t["allowed_use"] == "internal_research"

    def test_redistribution_allowed_false(self):
        t = build_approval_record_template()
        assert t["redistribution_allowed"] is False

    def test_commercial_use_false(self):
        t = build_approval_record_template()
        assert t["commercial_use_allowed"] is False

    def test_placeholder_values_present(self):
        t = build_approval_record_template()
        assert "PLACEHOLDER" in str(t["provider_name"])
        assert "PLACEHOLDER" in str(t["source_name"])

    def test_source_file_expected_path_non_empty(self):
        t = build_approval_record_template()
        assert t["source_file_expected_path"] != ""


class TestValidateApprovalRecordTemplate:
    def test_valid_template_passes(self):
        t = build_approval_record_template()
        assert validate_approval_record_template(t) is True

    def test_missing_one_field_fails(self):
        t = build_approval_record_template()
        del t["provider_name"]
        assert validate_approval_record_template(t) is False

    def test_missing_paper_only_fails(self):
        t = build_approval_record_template()
        del t["paper_only"]
        assert validate_approval_record_template(t) is False

    def test_empty_dict_fails(self):
        assert validate_approval_record_template({}) is False


class TestWriteApprovalRecordTemplate:
    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_approval_record_template(tmp)
            assert os.path.exists(path)
            assert os.path.basename(path) == "odds_approval_record_TEMPLATE.json"

    def test_file_is_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_approval_record_template(tmp)
            with open(path) as f:
                data = json.load(f)
            assert isinstance(data, dict)

    def test_file_contains_all_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_approval_record_template(tmp)
            with open(path) as f:
                data = json.load(f)
            for field in APPROVAL_RECORD_TEMPLATE_FIELDS:
                assert field in data

    def test_deterministic_output(self):
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            p1 = write_approval_record_template(tmp1)
            p2 = write_approval_record_template(tmp2)
            with open(p1) as f1, open(p2) as f2:
                d1 = json.load(f1)
                d2 = json.load(f2)
            assert d1 == d2


class TestWriteApprovalRecordInstructions:
    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_approval_record_instructions(tmp)
            assert os.path.exists(path)
            assert os.path.basename(path) == "odds_approval_record_INSTRUCTIONS.md"

    def test_file_is_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_approval_record_instructions(tmp)
            with open(path) as f:
                content = f.read()
            assert content.startswith("#")

    def test_mentions_paper_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_approval_record_instructions(tmp)
            with open(path) as f:
                content = f.read()
            assert "PAPER_ONLY" in content or "paper_only" in content

    def test_mentions_internal_research(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_approval_record_instructions(tmp)
            with open(path) as f:
                content = f.read()
            assert "internal_research" in content

    def test_deterministic_content(self):
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            p1 = write_approval_record_instructions(tmp1)
            p2 = write_approval_record_instructions(tmp2)
            with open(p1) as f1, open(p2) as f2:
                c1 = f1.read()
                c2 = f2.read()
            assert c1 == c2
