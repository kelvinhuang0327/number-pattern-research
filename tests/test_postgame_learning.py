from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.config.settings import AppConfig, DataSourceConfig
from wbc_backend.reporting.postgame_learning import (
    build_market_support_decision_note,
    extract_sub_model_predictions,
    load_latest_prediction_record,
    record_postgame_outcome,
    summarize_market_support_performance,
    update_review_report_with_market_support_summary,
    write_market_support_performance_summary,
)
from wbc_backend.strategy import live_retrainer


def _make_prediction_record(game_id: str, home: str, away: str, home_prob: float) -> dict:
    return {
        "recorded_at_utc": "2026-03-09T07:08:58.203790+00:00",
        "game_id": game_id,
        "teams": {"home": home, "away": away},
        "verification": {
            "status": "VERIFIED_WITH_FALLBACK",
            "used_fallback_lineup": True,
        },
        "game_output": {
            "predicted_home_score": 2.41,
            "predicted_away_score": 6.72,
            "confidence_index": 0.542045,
        },
        "prediction": {
            "home_win_prob": home_prob,
            "away_win_prob": 1.0 - home_prob,
            "sub_model_results": [
                {"model_name": "elo", "home_win_prob": 0.3733},
                {"model_name": "bayesian", "home_win_prob": 0.2437},
                {"model_name": "neural_net", "home_win_prob": 0.2419},
            ],
        },
        "decision_report": {
            "decision": "NO_BET",
            "reasoning": ["Edge score below threshold"],
        },
        "market_support": {
            "primary": "tsl_direct",
            "breakdown": {"tsl_direct": 2, "intl_only": 1},
            "tilt": "direct_favored",
            "best_bet_state": "tsl_direct",
        },
    }


class TestPostgameLearning(unittest.TestCase):
    def test_load_latest_prediction_record_returns_last_match(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry_path = root / "prediction_registry.jsonl"
            registry_path.write_text(
                "\n".join(
                    [
                        json.dumps(_make_prediction_record("C09", "AUS", "KOR", 0.30)),
                        json.dumps(_make_prediction_record("C09", "AUS", "KOR", 0.26)),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            config = AppConfig(
                sources=DataSourceConfig(
                    prediction_registry_jsonl=str(registry_path),
                    postgame_results_jsonl=str(root / "postgame_results.jsonl"),
                )
            )

            record = load_latest_prediction_record(config=config, game_id="C09")
            self.assertIsNotNone(record)
            self.assertAlmostEqual(record["prediction"]["home_win_prob"], 0.26)

    def test_record_postgame_outcome_appends_result_and_updates_retrainer(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry_path = root / "prediction_registry.jsonl"
            postgame_path = root / "postgame_results.jsonl"
            state_path = root / "retrainer_state.json"

            registry_path.write_text(
                json.dumps(_make_prediction_record("C09", "AUS", "KOR", 0.2635)) + "\n",
                encoding="utf-8",
            )

            config = AppConfig(
                sources=DataSourceConfig(
                    prediction_registry_jsonl=str(registry_path),
                    postgame_results_jsonl=str(postgame_path),
                )
            )

            original_state_file = live_retrainer.STATE_FILE
            live_retrainer.STATE_FILE = state_path
            try:
                payload = record_postgame_outcome(
                    config=config,
                    game_id="C09",
                    home_team="AUS",
                    away_team="KOR",
                    home_score=2,
                    away_score=7,
                    source_urls=["https://www.yonhapnewstv.co.kr/news/MYH20260309208700641"],
                    notes=["KOR won after Moon Bo-gyeong homered twice."],
                )
            finally:
                live_retrainer.STATE_FILE = original_state_file

            self.assertTrue(postgame_path.exists())
            lines = postgame_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            stored = json.loads(lines[0])
            self.assertEqual(stored["game_id"], "C09")
            self.assertTrue(stored["evaluation"]["winner_correct"])
            self.assertTrue(stored["learning"]["applied"])
            self.assertIn("updated_weights", stored["learning"])
            self.assertTrue(state_path.exists())

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertIn("elo", state["performances"])
            self.assertEqual(payload["prediction_summary"]["decision"], "NO_BET")
            self.assertEqual(payload["prediction_summary"]["market_support_primary"], "tsl_direct")
            self.assertEqual(payload["prediction_summary"]["best_bet_support_state"], "tsl_direct")
            self.assertEqual(payload["evaluation"]["market_support_primary"], "tsl_direct")

    def test_extract_sub_model_predictions_ignores_invalid_rows(self):
        record = {
            "prediction": {
                "sub_model_results": [
                    {"model_name": "elo", "home_win_prob": 0.52},
                    {"model_name": "", "home_win_prob": 0.50},
                    {"model_name": "bad", "home_win_prob": "oops"},
                ]
            }
        }

        preds = extract_sub_model_predictions(record)
        self.assertEqual(preds, {"elo": 0.52})

    def test_summarize_market_support_performance_groups_results(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            postgame_path = root / "postgame_results.jsonl"
            rows = [
                {
                    "game_id": "G1",
                    "evaluation": {
                        "winner_correct": True,
                        "home_win_brier": 0.11,
                        "home_win_log_loss": 0.31,
                        "score_error_total_abs": 1.0,
                        "market_support_primary": "tsl_direct",
                        "best_bet_support_state": "tsl_direct",
                    },
                },
                {
                    "game_id": "G2",
                    "evaluation": {
                        "winner_correct": False,
                        "home_win_brier": 0.29,
                        "home_win_log_loss": 0.72,
                        "score_error_total_abs": 3.0,
                        "market_support_primary": "intl_only",
                        "best_bet_support_state": "intl_only",
                    },
                },
                {
                    "game_id": "G3",
                    "evaluation": {
                        "winner_correct": True,
                        "home_win_brier": 0.09,
                        "home_win_log_loss": 0.28,
                        "score_error_total_abs": 2.0,
                        "market_support_primary": "tsl_direct",
                        "best_bet_support_state": "tsl_direct",
                    },
                },
            ]
            postgame_path.write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )
            config = AppConfig(
                sources=DataSourceConfig(
                    prediction_registry_jsonl=str(root / "prediction_registry.jsonl"),
                    postgame_results_jsonl=str(postgame_path),
                )
            )

            summary = summarize_market_support_performance(config=config)

            self.assertEqual(summary["group_by"], "market_support_primary")
            self.assertEqual(summary["n_games"], 3)
            self.assertEqual(summary["groups"]["tsl_direct"]["games"], 2)
            self.assertEqual(summary["groups"]["tsl_direct"]["winner_accuracy"], 1.0)
            self.assertEqual(summary["groups"]["intl_only"]["games"], 1)
            self.assertEqual(summary["groups"]["intl_only"]["winner_accuracy"], 0.0)
            self.assertIn("sample remains thin", summary["decision_note"])

    def test_summarize_market_support_performance_supports_alternate_group(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            postgame_path = root / "postgame_results.jsonl"
            row = {
                "game_id": "G1",
                "evaluation": {
                    "winner_correct": True,
                    "home_win_brier": 0.11,
                    "home_win_log_loss": 0.31,
                    "score_error_total_abs": 1.0,
                    "market_support_primary": "tsl_direct",
                    "best_bet_support_state": "intl_only",
                },
            }
            postgame_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            config = AppConfig(
                sources=DataSourceConfig(
                    prediction_registry_jsonl=str(root / "prediction_registry.jsonl"),
                    postgame_results_jsonl=str(postgame_path),
                )
            )

            summary = summarize_market_support_performance(
                config=config,
                group_by="best_bet_support_state",
            )

            self.assertEqual(summary["group_by"], "best_bet_support_state")
            self.assertIn("intl_only", summary["groups"])

    def test_build_market_support_decision_note_prefers_tsl_direct_when_strong(self):
        note = build_market_support_decision_note(
            {
                "groups": {
                    "tsl_direct": {"games": 6, "winner_accuracy": 0.67, "avg_brier": 0.14},
                    "intl_only": {"games": 4, "winner_accuracy": 0.50, "avg_brier": 0.22},
                }
            }
        )
        self.assertIn("favor TSL direct support", note)

    def test_write_market_support_performance_summary_persists_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            reports_dir = root / "reports"
            postgame_path = root / "postgame_results.jsonl"
            row = {
                "game_id": "G1",
                "evaluation": {
                    "winner_correct": True,
                    "home_win_brier": 0.11,
                    "home_win_log_loss": 0.31,
                    "score_error_total_abs": 1.0,
                    "market_support_primary": "tsl_direct",
                    "best_bet_support_state": "tsl_direct",
                },
            }
            postgame_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            config = AppConfig(
                sources=DataSourceConfig(
                    prediction_registry_jsonl=str(root / "prediction_registry.jsonl"),
                    postgame_results_jsonl=str(postgame_path),
                    reports_dir=str(reports_dir),
                )
            )

            target = write_market_support_performance_summary(config=config)

            self.assertTrue(target.exists())
            payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(payload["n_games"], 1)
            self.assertIn("tsl_direct", payload["groups"])

    def test_update_review_report_with_market_support_summary_appends_section(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            review_path = root / "WBC_Review_Meeting_Latest.md"
            review_path.write_text("# Review\n\nExisting content.\n", encoding="utf-8")
            config = AppConfig(
                sources=DataSourceConfig(
                    prediction_registry_jsonl=str(root / "prediction_registry.jsonl"),
                    postgame_results_jsonl=str(root / "postgame_results.jsonl"),
                    review_report_latest_md=str(review_path),
                )
            )

            target = update_review_report_with_market_support_summary(
                config=config,
                summary={
                    "group_by": "market_support_primary",
                    "n_games": 3,
                    "groups": {
                        "tsl_direct": {
                            "games": 2,
                            "winner_accuracy": 1.0,
                            "avg_brier": 0.1,
                            "avg_log_loss": 0.3,
                        }
                    },
                },
            )

            text = target.read_text(encoding="utf-8")
            self.assertIn("## Market Support Trend", text)
            self.assertIn("`tsl_direct`: games=2, acc=100.0%, brier=0.1000, logloss=0.3000", text)
            self.assertIn("Decision Note:", text)

    def test_update_review_report_replaces_existing_market_support_section(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            review_path = root / "WBC_Review_Meeting_Latest.md"
            review_path.write_text(
                "# Review\n\n## Market Support Trend\n\n- old line\n",
                encoding="utf-8",
            )
            config = AppConfig(
                sources=DataSourceConfig(
                    prediction_registry_jsonl=str(root / "prediction_registry.jsonl"),
                    postgame_results_jsonl=str(root / "postgame_results.jsonl"),
                    review_report_latest_md=str(review_path),
                )
            )

            update_review_report_with_market_support_summary(
                config=config,
                summary={
                    "group_by": "best_bet_support_state",
                    "n_games": 1,
                    "groups": {},
                },
            )

            text = review_path.read_text(encoding="utf-8")
            self.assertEqual(text.count("## Market Support Trend"), 1)
            self.assertNotIn("old line", text)

    def test_record_postgame_outcome_refreshes_review_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry_path = root / "prediction_registry.jsonl"
            postgame_path = root / "postgame_results.jsonl"
            review_path = root / "WBC_Review_Meeting_Latest.md"
            state_path = root / "retrainer_state.json"

            registry_path.write_text(
                json.dumps(_make_prediction_record("C09", "AUS", "KOR", 0.2635)) + "\n",
                encoding="utf-8",
            )
            config = AppConfig(
                sources=DataSourceConfig(
                    prediction_registry_jsonl=str(registry_path),
                    postgame_results_jsonl=str(postgame_path),
                    review_report_latest_md=str(review_path),
                    reports_dir=str(root / "reports"),
                )
            )

            original_state_file = live_retrainer.STATE_FILE
            live_retrainer.STATE_FILE = state_path
            try:
                record_postgame_outcome(
                    config=config,
                    game_id="C09",
                    home_team="AUS",
                    away_team="KOR",
                    home_score=2,
                    away_score=7,
                )
            finally:
                live_retrainer.STATE_FILE = original_state_file

            text = review_path.read_text(encoding="utf-8")
            self.assertIn("## Market Support Trend", text)
            self.assertIn("累積樣本: `1` 場", text)


if __name__ == "__main__":
    unittest.main()
