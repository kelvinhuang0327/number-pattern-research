import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import p213h_3star_4star_controlled_positional_backfill as module


class P213HControlledBackfillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.db_path = self.tmp_path / "test.db"
        self.rows_path = self.tmp_path / "rows.json"
        self.summary_path = self.tmp_path / "summary.json"
        self._create_db()
        self._create_artifacts()

    def tearDown(self):
        self.tmp.cleanup()

    def _create_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            CREATE TABLE draws (
                id INTEGER PRIMARY KEY,
                draw TEXT NOT NULL,
                date TEXT NOT NULL,
                lottery_type TEXT NOT NULL,
                numbers TEXT NOT NULL,
                numbers_positional TEXT DEFAULT NULL
            )
            """
        )
        conn.execute("CREATE TABLE strategy_prediction_replays (id INTEGER PRIMARY KEY)")
        conn.executemany(
            "INSERT INTO strategy_prediction_replays(id) VALUES (?)",
            [(1,), (2,)],
        )
        rows = [
            ("001", "2024/01/01", "3_STAR", json.dumps([1, 2, 3]), None),
            ("002", "2024/01/02", "4_STAR", json.dumps([0, 4, 9, 9]), None),
            ("003", "2024/01/03", "BIG_LOTTO", json.dumps([1, 2, 3, 4, 5, 6]), None),
            ("004", "2024/01/04", "3_STAR", json.dumps([1, 1, 9]), json.dumps([9, 1, 1])),
            ("005", "2024/01/05", "3_STAR", json.dumps([0, 0, 1]), None),
        ]
        conn.executemany(
            "INSERT INTO draws(draw,date,lottery_type,numbers,numbers_positional) VALUES (?,?,?,?,?)",
            rows,
        )
        conn.commit()
        conn.close()

    def _create_artifacts(self):
        rows = [
            {
                "lottery_type": "3_STAR",
                "draw": "001",
                "status": "MATCH",
                "reason": "Canonical numbers and normalized dates match",
                "canonical_numbers": [1, 2, 3],
                "positional_numbers": [3, 1, 2],
            },
            {
                "lottery_type": "4_STAR",
                "draw": "002",
                "status": "MATCH",
                "reason": "Canonical numbers and normalized dates match",
                "canonical_numbers": [0, 4, 9, 9],
                "positional_numbers": [9, 0, 4, 9],
            },
            {
                "lottery_type": "3_STAR",
                "draw": "004",
                "status": "MATCH",
                "reason": "Canonical numbers and normalized dates match",
                "canonical_numbers": [1, 1, 9],
                "positional_numbers": [9, 1, 1],
            },
            {
                "lottery_type": "3_STAR",
                "draw": "005",
                "status": "MATCH",
                "reason": "Canonical numbers and normalized dates match",
                "canonical_numbers": [9, 9, 9],
                "positional_numbers": [9, 9, 9],
            },
            {
                "lottery_type": "3_STAR",
                "draw": "999",
                "status": "MISSING_IN_DB",
                "reason": "No matching DB row",
                "canonical_numbers": [1, 2, 3],
                "positional_numbers": [1, 2, 3],
            },
        ]
        summary = {
            "total_rows": 5,
            "total_matched": 4,
            "total_missing": 1,
            "total_mismatched": 0,
        }
        self.rows_path.write_text(json.dumps(rows), encoding="utf-8")
        self.summary_path.write_text(json.dumps(summary), encoding="utf-8")

    def _read_draws(self):
        conn = sqlite3.connect(self.db_path)
        rows = list(conn.execute("SELECT draw, lottery_type, numbers, numbers_positional FROM draws"))
        conn.close()
        return rows

    def test_script_imports(self):
        self.assertEqual(module.FINAL_CLASSIFICATION, "P213H_3STAR_4STAR_CONTROLLED_POSITIONAL_BACKFILL_COMPLETE")

    def test_dry_run_makes_no_db_changes(self):
        before = self._read_draws()
        result = module.run_backfill(
            db_path=self.db_path,
            rows_path=self.rows_path,
            summary_path=self.summary_path,
            apply=False,
        )
        after = self._read_draws()
        self.assertEqual(before, after)
        self.assertEqual(result["audit"]["rows_would_update"], 2)

    def test_apply_backfills_3_star_and_4_star_matches(self):
        result = module.run_backfill(
            db_path=self.db_path,
            rows_path=self.rows_path,
            summary_path=self.summary_path,
            apply=True,
        )
        self.assertEqual(result["audit"]["rows_updated"], 2)
        conn = sqlite3.connect(self.db_path)
        self.assertEqual(
            json.loads(conn.execute("SELECT numbers_positional FROM draws WHERE draw='001'").fetchone()[0]),
            [3, 1, 2],
        )
        self.assertEqual(
            json.loads(conn.execute("SELECT numbers_positional FROM draws WHERE draw='002'").fetchone()[0]),
            [9, 0, 4, 9],
        )
        conn.close()

    def test_non_permutation_rows_remain_unchanged(self):
        module.run_backfill(
            db_path=self.db_path,
            rows_path=self.rows_path,
            summary_path=self.summary_path,
            apply=True,
        )
        conn = sqlite3.connect(self.db_path)
        self.assertIsNone(conn.execute("SELECT numbers_positional FROM draws WHERE draw='003'").fetchone()[0])
        conn.close()

    def test_mismatched_canonical_numbers_are_not_updated(self):
        module.run_backfill(
            db_path=self.db_path,
            rows_path=self.rows_path,
            summary_path=self.summary_path,
            apply=True,
        )
        conn = sqlite3.connect(self.db_path)
        self.assertIsNone(conn.execute("SELECT numbers_positional FROM draws WHERE draw='005'").fetchone()[0])
        conn.close()

    def test_missing_source_rows_are_not_inserted(self):
        module.run_backfill(
            db_path=self.db_path,
            rows_path=self.rows_path,
            summary_path=self.summary_path,
            apply=True,
        )
        conn = sqlite3.connect(self.db_path)
        count = conn.execute("SELECT COUNT(*) FROM draws WHERE draw='999'").fetchone()[0]
        conn.close()
        self.assertEqual(count, 0)

    def test_idempotent(self):
        first = module.run_backfill(
            db_path=self.db_path,
            rows_path=self.rows_path,
            summary_path=self.summary_path,
            apply=True,
        )
        second = module.run_backfill(
            db_path=self.db_path,
            rows_path=self.rows_path,
            summary_path=self.summary_path,
            apply=True,
        )
        self.assertEqual(first["audit"]["rows_updated"], 2)
        self.assertEqual(second["audit"]["rows_updated"], 0)
        self.assertEqual(second["audit"]["rows_already_populated"], 3)

    def test_existing_numbers_column_is_unchanged(self):
        before = [row[2] for row in self._read_draws()]
        result = module.run_backfill(
            db_path=self.db_path,
            rows_path=self.rows_path,
            summary_path=self.summary_path,
            apply=True,
        )
        after = [row[2] for row in self._read_draws()]
        self.assertEqual(before, after)
        self.assertFalse(result["audit"]["numbers_column_changed"])

    def test_schema_add_is_additive_nullable(self):
        db_without_column = self.tmp_path / "without_column.db"
        conn = sqlite3.connect(db_without_column)
        conn.execute(
            """
            CREATE TABLE draws (
                id INTEGER PRIMARY KEY,
                draw TEXT NOT NULL,
                date TEXT NOT NULL,
                lottery_type TEXT NOT NULL,
                numbers TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE TABLE strategy_prediction_replays (id INTEGER PRIMARY KEY)")
        conn.execute(
            "INSERT INTO draws(draw,date,lottery_type,numbers) VALUES ('001','2024/01/01','3_STAR','[1, 2, 3]')"
        )
        conn.commit()
        conn.close()
        result = module.run_backfill(
            db_path=db_without_column,
            rows_path=self.rows_path,
            summary_path=self.summary_path,
            apply=True,
        )
        self.assertTrue(result["audit"]["schema_column_added"])

    def test_audit_counts_are_correct(self):
        result = module.run_backfill(
            db_path=self.db_path,
            rows_path=self.rows_path,
            summary_path=self.summary_path,
            apply=True,
        )
        audit = result["audit"]
        self.assertEqual(audit["rows_updated"], 2)
        self.assertEqual(audit["rows_already_populated"], 1)
        self.assertEqual(audit["rows_skipped_missing_in_db"], 1)
        self.assertEqual(audit["rows_skipped_mismatch"], 1)

    def test_source_has_no_forbidden_logic(self):
        text = Path(module.__file__).read_text(encoding="utf-8")
        forbidden = ["controlled_apply", "strategy_registry", "predict_next_numbers"]
        self.assertFalse(any(token in text for token in forbidden))

    def test_safety_booleans_are_conservative(self):
        result = module.run_backfill(
            db_path=self.db_path,
            rows_path=self.rows_path,
            summary_path=self.summary_path,
            apply=True,
        )
        audit = result["audit"]
        self.assertTrue(audit["no_registry_mutation"])
        self.assertTrue(audit["no_production_recommendation_change"])
        self.assertTrue(audit["no_monitoring_change"])
        self.assertTrue(audit["no_strategy_authorization"])
        self.assertTrue(audit["no_betting_advice"])


if __name__ == "__main__":
    unittest.main()
