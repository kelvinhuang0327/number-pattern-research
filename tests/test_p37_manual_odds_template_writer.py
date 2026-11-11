"""
Tests for p37_manual_odds_template_writer.py
"""
import os
import tempfile

import pandas as pd
import pytest

from wbc_backend.recommendation.p37_manual_odds_template_writer import (
    build_manual_odds_csv_template,
    validate_manual_odds_template,
    write_manual_odds_template,
    write_manual_odds_column_guide,
)
from wbc_backend.recommendation.p37_manual_odds_provisioning_contract import (
    MANUAL_ODDS_TEMPLATE_COLUMNS,
)


class TestBuildManualOddsCsvTemplate:
    def test_returns_dataframe(self):
        df = build_manual_odds_csv_template()
        assert isinstance(df, pd.DataFrame)

    def test_has_all_required_columns(self):
        df = build_manual_odds_csv_template()
        for col in MANUAL_ODDS_TEMPLATE_COLUMNS:
            assert col in df.columns, f"Missing column: {col}"

    def test_has_one_example_row(self):
        df = build_manual_odds_csv_template()
        assert len(df) == 1

    def test_example_row_game_id_is_placeholder(self):
        df = build_manual_odds_csv_template()
        assert "EXAMPLE" in str(df.iloc[0]["game_id"])

    def test_example_row_market_type_is_moneyline(self):
        df = build_manual_odds_csv_template()
        assert df.iloc[0]["market_type"] == "moneyline"

    def test_p_market_in_valid_range(self):
        df = build_manual_odds_csv_template()
        p = df.iloc[0]["p_market"]
        assert 0.0 < float(p) < 1.0

    def test_odds_decimal_above_one(self):
        df = build_manual_odds_csv_template()
        odds = df.iloc[0]["odds_decimal"]
        assert float(odds) >= 1.0

    def test_no_forbidden_columns(self):
        df = build_manual_odds_csv_template()
        forbidden = {
            "y_true", "final_score", "home_score", "away_score", "winner",
            "outcome", "result", "run_diff", "total_runs", "game_result",
        }
        for col in forbidden:
            assert col not in df.columns


class TestValidateManualOddsTemplate:
    def test_valid_template_passes(self):
        df = build_manual_odds_csv_template()
        ok, msg, missing = validate_manual_odds_template(df)
        assert ok is True
        assert missing == []

    def test_missing_column_fails(self):
        df = build_manual_odds_csv_template().drop(columns=["game_id"])
        ok, msg, missing = validate_manual_odds_template(df)
        assert ok is False
        assert "game_id" in missing

    def test_non_dataframe_fails(self):
        ok, msg, missing = validate_manual_odds_template(None)
        assert ok is False

    def test_empty_dataframe_with_correct_columns_passes(self):
        df = pd.DataFrame(columns=list(MANUAL_ODDS_TEMPLATE_COLUMNS))
        ok, msg, missing = validate_manual_odds_template(df)
        assert ok is True


class TestWriteManualOddsTemplate:
    def test_writes_csv_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_manual_odds_template(tmp)
            assert os.path.exists(path)
            assert path.endswith("odds_2024_approved_TEMPLATE.csv")

    def test_csv_is_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_manual_odds_template(tmp)
            df = pd.read_csv(path)
            assert isinstance(df, pd.DataFrame)

    def test_csv_has_all_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_manual_odds_template(tmp)
            df = pd.read_csv(path)
            for col in MANUAL_ODDS_TEMPLATE_COLUMNS:
                assert col in df.columns

    def test_deterministic_output(self):
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            p1 = write_manual_odds_template(tmp1)
            p2 = write_manual_odds_template(tmp2)
            with open(p1) as f1, open(p2) as f2:
                c1 = f1.read()
                c2 = f2.read()
            assert c1 == c2


class TestWriteManualOddsColumnGuide:
    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_manual_odds_column_guide(tmp)
            assert os.path.exists(path)
            assert path.endswith("odds_2024_approved_COLUMN_GUIDE.md")

    def test_file_is_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_manual_odds_column_guide(tmp)
            with open(path) as f:
                content = f.read()
            assert "#" in content

    def test_mentions_all_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_manual_odds_column_guide(tmp)
            with open(path) as f:
                content = f.read()
            for col in MANUAL_ODDS_TEMPLATE_COLUMNS:
                assert col in content, f"Column {col} not mentioned in guide"

    def test_mentions_forbidden_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_manual_odds_column_guide(tmp)
            with open(path) as f:
                content = f.read()
            assert "y_true" in content
            assert "final_score" in content

    def test_deterministic_content(self):
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            p1 = write_manual_odds_column_guide(tmp1)
            p2 = write_manual_odds_column_guide(tmp2)
            with open(p1) as f1, open(p2) as f2:
                assert f1.read() == f2.read()
