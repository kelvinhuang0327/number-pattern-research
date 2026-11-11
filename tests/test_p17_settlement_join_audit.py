"""
tests/test_p17_settlement_join_audit.py

Unit tests for the P17 settlement join audit module.
"""
import pytest
import pandas as pd

from wbc_backend.recommendation.p17_paper_ledger_contract import (
    P16_6_ELIGIBLE_DECISION,
)
from wbc_backend.recommendation.p17_settlement_join_audit import (
    JOIN_METHOD_GAME_ID,
    JOIN_METHOD_NONE,
    audit_recommendation_to_p15_join,
    identify_duplicate_game_ids,
    identify_unmatched_recommendations,
    summarize_settlement_join_quality,
)

ELIGIBLE_GATE = P16_6_ELIGIBLE_DECISION
BLOCKED_GATE = "P16_6_BLOCKED_EDGE_BELOW_P18_THRESHOLD"


def make_rec_df(game_ids: list[str], y_trues: list | None = None) -> pd.DataFrame:
    rows = []
    for i, gid in enumerate(game_ids):
        row = {
            "recommendation_id": f"R-{i:03d}",
            "game_id": gid,
            "date": "2025-05-08",
            "side": "HOME",
            "gate_decision": ELIGIBLE_GATE,
        }
        if y_trues is not None:
            row["y_true"] = y_trues[i]
        rows.append(row)
    return pd.DataFrame(rows)


def make_p15_df(game_ids: list[str], y_trues: list[float]) -> pd.DataFrame:
    return pd.DataFrame({
        "game_id": game_ids,
        "y_true": y_trues,
        "fold_id": list(range(len(game_ids))),
        "row_idx": list(range(len(game_ids))),
    })


def make_p15_df_no_game_id(n: int) -> pd.DataFrame:
    """P15 ledger without game_id (simulates simulation_ledger.csv fragility)."""
    return pd.DataFrame({
        "row_idx": list(range(n)),
        "y_true": [float(i % 2) for i in range(n)],
        "fold_id": list(range(n)),
        "reason": ["BELOW_EDGE_THRESHOLD"] * n,
    })


class TestAuditRecommendationToP15Join:
    def test_high_coverage_when_all_match(self):
        game_ids = ["2025-05-08_A_B", "2025-05-08_C_D"]
        rec_df = make_rec_df(game_ids)
        p15_df = make_p15_df(game_ids, [1.0, 0.0])
        _, result = audit_recommendation_to_p15_join(rec_df, p15_df)
        assert result.join_method == JOIN_METHOD_GAME_ID
        assert result.join_coverage == 1.0
        assert result.join_quality == "HIGH"
        assert result.n_joined == 2
        assert result.n_unmatched == 0

    def test_zero_coverage_when_no_match(self):
        rec_df = make_rec_df(["2025-05-08_A_B"])
        p15_df = make_p15_df(["2025-05-09_C_D"], [1.0])
        _, result = audit_recommendation_to_p15_join(rec_df, p15_df)
        assert result.n_joined == 0
        assert result.join_coverage == 0.0
        assert result.join_quality == "NONE"

    def test_zero_coverage_surfaces_risk_note(self):
        rec_df = make_rec_df(["2025-05-08_A_B"])
        p15_df = make_p15_df(["2025-05-09_C_D"], [1.0])
        _, result = audit_recommendation_to_p15_join(rec_df, p15_df)
        assert any("fragility" in note.lower() or "0 match" in note.lower()
                   for note in result.risk_notes)

    def test_join_method_none_when_p15_lacks_game_id(self):
        rec_df = make_rec_df(["2025-05-08_A_B"])
        p15_df = make_p15_df_no_game_id(5)
        _, result = audit_recommendation_to_p15_join(rec_df, p15_df)
        assert result.join_method == JOIN_METHOD_NONE
        assert result.join_coverage == 0.0
        assert len(result.risk_notes) > 0

    def test_partial_match_medium_quality(self):
        rec_game_ids = [f"2025-05-0{i}_A_B" for i in range(10)]
        p15_game_ids = rec_game_ids[:6]  # only 6 of 10 match
        rec_df = make_rec_df(rec_game_ids)
        p15_df = make_p15_df(p15_game_ids, [float(i % 2) for i in range(6)])
        _, result = audit_recommendation_to_p15_join(rec_df, p15_df)
        assert result.join_quality in ("MEDIUM", "LOW")

    def test_duplicate_game_ids_in_p15_triggers_note(self):
        game_ids = ["2025-05-08_A_B"]
        rec_df = make_rec_df(game_ids)
        # P15 has duplicate game_id
        p15_df = make_p15_df(["2025-05-08_A_B", "2025-05-08_A_B"], [1.0, 0.0])
        _, result = audit_recommendation_to_p15_join(rec_df, p15_df)
        assert any("duplicate" in note.lower() for note in result.risk_notes)

    def test_joined_df_has_p15_y_true_when_matched(self):
        game_ids = ["2025-05-08_A_B"]
        rec_df = make_rec_df(game_ids)
        p15_df = make_p15_df(game_ids, [1.0])
        joined_df, _ = audit_recommendation_to_p15_join(rec_df, p15_df)
        assert "p15_y_true" in joined_df.columns
        assert joined_df.iloc[0]["p15_y_true"] == 1.0

    def test_unmatched_rows_have_nan_p15_y_true(self):
        rec_df = make_rec_df(["2025-05-08_A_B", "2025-05-08_C_D"])
        p15_df = make_p15_df(["2025-05-08_A_B"], [1.0])
        joined_df, _ = audit_recommendation_to_p15_join(rec_df, p15_df)
        unmatched = joined_df[joined_df["game_id"] == "2025-05-08_C_D"]
        assert unmatched.iloc[0]["p15_y_true"] != unmatched.iloc[0]["p15_y_true"]  # NaN check

    def test_duplicate_game_ids_in_rec_detected(self):
        # Two recommendation rows for same game (HOME + AWAY)
        rec_df = pd.DataFrame([
            {"recommendation_id": "R-001", "game_id": "2025-05-08_A_B",
             "date": "2025-05-08", "side": "HOME", "gate_decision": ELIGIBLE_GATE},
            {"recommendation_id": "R-002", "game_id": "2025-05-08_A_B",
             "date": "2025-05-08", "side": "AWAY", "gate_decision": ELIGIBLE_GATE},
        ])
        p15_df = make_p15_df(["2025-05-08_A_B"], [1.0])
        _, result = audit_recommendation_to_p15_join(rec_df, p15_df)
        assert result.n_duplicate_game_ids >= 1


class TestIdentifyUnmatchedRecommendations:
    def test_returns_unmatched_ids(self):
        joined_df = pd.DataFrame({
            "recommendation_id": ["R-001", "R-002"],
            "p15_y_true": [1.0, float("nan")],
        })
        unmatched = identify_unmatched_recommendations(joined_df)
        assert "R-002" in unmatched
        assert "R-001" not in unmatched

    def test_empty_when_all_matched(self):
        joined_df = pd.DataFrame({
            "recommendation_id": ["R-001"],
            "p15_y_true": [1.0],
        })
        unmatched = identify_unmatched_recommendations(joined_df)
        assert len(unmatched) == 0


class TestIdentifyDuplicateGameIds:
    def test_finds_duplicates(self):
        df = pd.DataFrame({"game_id": ["A", "A", "B"]})
        dups = identify_duplicate_game_ids(df)
        assert "A" in dups

    def test_empty_when_no_duplicates(self):
        df = pd.DataFrame({"game_id": ["A", "B", "C"]})
        dups = identify_duplicate_game_ids(df)
        assert len(dups) == 0


class TestSummarizeSettlementJoinQuality:
    def test_y_true_coverage_correct(self):
        joined_df = pd.DataFrame({
            "game_id": ["A", "B"],
            "y_true": [1.0, float("nan")],
        })
        summary = summarize_settlement_join_quality(joined_df)
        assert summary["n_with_y_true"] == 1
        assert summary["n_without_y_true"] == 1
        assert abs(summary["y_true_coverage"] - 0.5) < 1e-9

    def test_zero_coverage_when_no_y_true(self):
        joined_df = pd.DataFrame({"game_id": ["A"]})
        summary = summarize_settlement_join_quality(joined_df)
        assert summary["n_with_y_true"] == 0
        assert summary["y_true_coverage"] == 0.0
