import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MD_PATH = REPO_ROOT / "outputs/research/p213k_missing_source_row_ingestion_feasibility_design_20260605.md"
JSON_PATH = REPO_ROOT / "outputs/research/p213k_missing_source_row_ingestion_feasibility_design_20260605.json"


def _json():
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def _md():
    return MD_PATH.read_text(encoding="utf-8")


class P213KArtifactTest(unittest.TestCase):
    def test_markdown_artifact_exists(self):
        self.assertTrue(MD_PATH.exists())

    def test_json_artifact_parses(self):
        self.assertTrue(JSON_PATH.exists())
        self.assertEqual(_json()["task_id"], "P213K")

    def test_classification_is_approved(self):
        self.assertEqual(
            _json()["classification"],
            "P213K_MISSING_SOURCE_ROW_INGESTION_FEASIBILITY_DESIGN_COMPLETE",
        )

    def test_source_and_missing_counts(self):
        data = _json()
        self.assertEqual(data["source_rows_total"], 11700)
        self.assertEqual(data["existing_db_matched_rows"], 7101)
        self.assertEqual(data["missing_source_rows_total"], 4599)
        self.assertEqual(data["missing_source_rows_by_lottery"], {"3_STAR": 1671, "4_STAR": 2928})

    def test_no_db_write_or_ingestion(self):
        data = _json()
        self.assertIs(data["production_db_write"], False)
        self.assertIs(data["ingestion_performed"], False)
        self.assertIs(data["final_state"]["missing_source_rows_inserted"], False)

    def test_no_forbidden_strategy_or_betting_claims(self):
        data = _json()
        text = (_md() + JSON_PATH.read_text(encoding="utf-8")).lower()
        self.assertIs(data["no_registry_mutation"], True)
        self.assertIs(data["no_production_recommendation_change"], True)
        self.assertIs(data["no_monitoring_change"], True)
        self.assertIs(data["no_strategy_authorization"], True)
        self.assertIs(data["no_betting_advice"], True)
        forbidden = [
            "recommended numbers:",
            "bet now",
            "guaranteed",
            "improves win rate",
            "production recommendation authorized",
            "strategy promotion authorized",
        ]
        for phrase in forbidden:
            self.assertNotIn(phrase, text)

    def test_exact_authorization_phrase_present(self):
        phrase = (
            "Authorize P213L controlled missing source-row ingestion gate for 3_STAR/4_STAR "
            "(Type D DB write, backup required, insert source-only rows only, no strategy scan, "
            "no recommendation change)"
        )
        self.assertEqual(_json()["exact_authorization_phrase_for_next_direction"], phrase)
        self.assertIn(phrase, _md())

    def test_type_d_required_for_future_ingestion(self):
        text = _md()
        self.assertIn("Any future insertion is Type D", text)
        self.assertEqual(
            _json()["insertion_feasibility"],
            "FEASIBLE_ONLY_UNDER_FUTURE_TYPE_D_GATE",
        )

    def test_no_scan_or_production_recommendation_authorized(self):
        data = _json()
        self.assertIs(data["straight_play_dependency"]["scan_authorized"], False)
        self.assertIn("No straight-play scan is authorized by P213K.", _md())
        self.assertIs(data["no_production_recommendation_change"], True)

    def test_backup_and_rollback_gates_present(self):
        data = _json()
        self.assertIs(data["required_backup_plan"]["required"], True)
        self.assertIs(data["required_rollback_plan"]["required"], True)
        text = _md().lower()
        self.assertIn("backup integrity check", text)
        self.assertIn("rollback plan", text)

    def test_db_row_count_preservation_and_expected_change_discussed(self):
        data = _json()
        self.assertEqual(data["final_state"]["production_db_rows_before"], 94924)
        self.assertEqual(data["final_state"]["production_db_rows_after"], 94924)
        text = _md()
        self.assertIn("draws` increases from 59,762 to 64,361", text)
        self.assertIn("replay rows would remain 94,924", text)

    def test_schema_unique_key_documented(self):
        data = _json()
        self.assertIn("UNIQUE(draw, lottery_type)", data["db_schema_summary"]["unique_constraints"])
        self.assertIn("(draw, lottery_type)", data["unique_key_assumption"])

    def test_p238b_observation_only_retained(self):
        self.assertIn("RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY", _json()["p238b_interpretation"])
        self.assertIn("P238B remains `RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY`", _md())


if __name__ == "__main__":
    unittest.main()
