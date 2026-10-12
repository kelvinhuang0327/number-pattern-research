import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts/p213l_3star_4star_controlled_missing_row_ingestion.py"


def load_module():
    spec = importlib.util.spec_from_file_location("p213l", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_db(path: Path):
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE draws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw TEXT NOT NULL,
            date TEXT NOT NULL,
            lottery_type TEXT NOT NULL,
            numbers TEXT NOT NULL,
            special INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            jackpot_amount REAL DEFAULT NULL,
            sell_amount REAL DEFAULT NULL,
            total_amount REAL DEFAULT NULL,
            numbers_positional TEXT DEFAULT NULL,
            UNIQUE(draw, lottery_type)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE strategy_prediction_replays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lottery_type TEXT NOT NULL,
            target_draw TEXT NOT NULL,
            strategy_id TEXT NOT NULL,
            bet_index INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    conn.commit()
    conn.close()


def write_json(path: Path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def source_row(lottery_type="3_STAR", draw="96000001", date="2007/01/01", positional=None, status="MISSING_IN_DB"):
    if positional is None:
        positional = [3, 5, 3] if lottery_type == "3_STAR" else [8, 8, 9, 4]
    return {
        "source_file": "source.csv",
        "line_no": 2,
        "lottery_type": lottery_type,
        "draw": draw,
        "source_date_raw": date,
        "source_date_normalized": date,
        "positional_numbers": positional,
        "canonical_numbers": sorted(positional),
        "db_date": None,
        "db_numbers": None,
        "db_numbers_positional": None,
        "status": status,
        "reason": "No matching DB row",
    }


def make_artifacts(tmp: Path, rows):
    rows_path = tmp / "rows.json"
    summary_path = tmp / "summary.json"
    p213k_path = tmp / "p213k.json"
    write_json(rows_path, rows)
    write_json(summary_path, {
        "total_rows": 11700,
        "total_matched": 7101,
        "total_missing": 4599,
        "total_mismatched": 0,
    })
    write_json(p213k_path, {"missing_source_rows_total": 4599})
    return rows_path, summary_path, p213k_path


class P213LTest(unittest.TestCase):
    def run_script(self, rows, apply=False):
        module = load_module()
        tmpdir = tempfile.TemporaryDirectory()
        tmp = Path(tmpdir.name)
        db_path = tmp / "test.db"
        make_db(db_path)
        rows_path, summary_path, p213k_path = make_artifacts(tmp, rows)
        result = module.run_ingestion(
            db_path=db_path,
            rows_path=rows_path,
            summary_path=summary_path,
            p213k_path=p213k_path,
            apply=apply,
            backup_path=None,
            backup_sha256_path=None,
            write_artifacts_flag=False,
            enforce_production_counts=False,
        )
        return tmpdir, db_path, result

    def test_script_imports(self):
        self.assertEqual(load_module().FINAL_CLASSIFICATION, "P213L_3STAR_4STAR_CONTROLLED_MISSING_SOURCE_ROW_INGESTION_COMPLETE")

    def test_dry_run_makes_no_db_changes(self):
        tmpdir, db_path, result = self.run_script([source_row()], apply=False)
        self.assertEqual(result["rows_insert_candidates"], 1)
        conn = sqlite3.connect(db_path)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0], 0)
        conn.close()
        tmpdir.cleanup()

    def test_apply_inserts_missing_3star_row(self):
        tmpdir, db_path, _ = self.run_script([source_row()], apply=False)
        module = load_module()
        rows_path, summary_path, p213k_path = make_artifacts(Path(tmpdir.name), [source_row()])
        conn = sqlite3.connect(db_path)
        action, _counts = module.build_actions(conn, json.loads(rows_path.read_text()))
        inserted = module.apply_actions(conn, action)
        conn.commit()
        self.assertEqual(inserted, 1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM draws WHERE lottery_type='3_STAR'").fetchone()[0], 1)
        conn.close()
        tmpdir.cleanup()

    def test_apply_inserts_missing_4star_row(self):
        row = source_row("4_STAR", "96000001", positional=[8, 8, 9, 4])
        tmpdir, db_path, _ = self.run_script([row], apply=False)
        module = load_module()
        rows_path, _summary_path, _p213k_path = make_artifacts(Path(tmpdir.name), [row])
        conn = sqlite3.connect(db_path)
        actions, _counts = module.build_actions(conn, json.loads(rows_path.read_text()))
        self.assertEqual(module.apply_actions(conn, actions), 1)
        conn.commit()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM draws WHERE lottery_type='4_STAR'").fetchone()[0], 1)
        conn.close()
        tmpdir.cleanup()

    def test_apply_does_not_update_existing_rows(self):
        module = load_module()
        tmpdir = tempfile.TemporaryDirectory()
        tmp = Path(tmpdir.name)
        db_path = tmp / "test.db"
        make_db(db_path)
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO draws(draw,date,lottery_type,numbers,numbers_positional) VALUES (?,?,?,?,?)",
            ("96000001", "2007/01/01", "3_STAR", "[0, 0, 0]", "[0, 0, 0]"),
        )
        conn.commit()
        row = source_row()
        actions, counts = module.build_actions(conn, [row])
        self.assertEqual(counts["rows_skipped_existing"], 1)
        module.apply_actions(conn, actions)
        conn.commit()
        self.assertEqual(conn.execute("SELECT numbers FROM draws WHERE draw='96000001'").fetchone()[0], "[0, 0, 0]")
        conn.close()
        tmpdir.cleanup()

    def test_apply_does_not_insert_duplicate_on_rerun(self):
        module = load_module()
        tmpdir, db_path, _ = self.run_script([source_row()], apply=False)
        conn = sqlite3.connect(db_path)
        row = source_row()
        actions, _counts = module.build_actions(conn, [row])
        module.apply_actions(conn, actions)
        conn.commit()
        actions2, counts2 = module.build_actions(conn, [row])
        module.apply_actions(conn, actions2)
        conn.commit()
        self.assertEqual(counts2["rows_skipped_existing"], 1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0], 1)
        conn.close()
        tmpdir.cleanup()

    def test_non_star_rows_are_ignored(self):
        tmpdir, _db_path, result = self.run_script([source_row("DAILY_539", "1", positional=[1, 2, 3, 4, 5])], apply=False)
        self.assertEqual(result["rows_skipped_non_star"], 1)
        tmpdir.cleanup()

    def test_mismatched_canonical_source_rows_are_skipped(self):
        row = source_row()
        row["canonical_numbers"] = [9, 9, 9]
        tmpdir, _db_path, result = self.run_script([row], apply=False)
        self.assertEqual(result["rows_skipped_mismatch"], 1)
        tmpdir.cleanup()

    def test_numbers_sorted_canonical_is_stored(self):
        tmpdir, db_path, _ = self.run_script([source_row()], apply=False)
        module = load_module()
        conn = sqlite3.connect(db_path)
        actions, _counts = module.build_actions(conn, [source_row()])
        module.apply_actions(conn, actions)
        conn.commit()
        self.assertEqual(json.loads(conn.execute("SELECT numbers FROM draws").fetchone()[0]), [3, 3, 5])
        conn.close()
        tmpdir.cleanup()

    def test_numbers_positional_stores_original_order(self):
        tmpdir, db_path, _ = self.run_script([source_row()], apply=False)
        module = load_module()
        conn = sqlite3.connect(db_path)
        actions, _counts = module.build_actions(conn, [source_row()])
        module.apply_actions(conn, actions)
        conn.commit()
        self.assertEqual(json.loads(conn.execute("SELECT numbers_positional FROM draws").fetchone()[0]), [3, 5, 3])
        conn.close()
        tmpdir.cleanup()

    def test_audit_counts_are_correct(self):
        tmpdir, _db_path, result = self.run_script([source_row(), source_row("4_STAR", "96000002", positional=[8, 8, 9, 4])], apply=False)
        self.assertEqual(result["rows_insert_candidates"], 2)
        self.assertEqual(result["rows_skipped_existing"], 0)
        self.assertEqual(result["rows_skipped_mismatch"], 0)
        tmpdir.cleanup()

    def test_result_artifact_payload_is_json_parseable(self):
        tmpdir, _db_path, result = self.run_script([source_row()], apply=False)
        parsed = json.loads(json.dumps(result))
        self.assertEqual(parsed["classification"], "P213L_3STAR_4STAR_CONTROLLED_MISSING_SOURCE_ROW_INGESTION_COMPLETE")
        tmpdir.cleanup()

    def test_script_has_no_forbidden_logic_tokens(self):
        text = SCRIPT_PATH.read_text(encoding="utf-8")
        for token in ["controlled_apply", "strategy_registry", "predict_next_numbers", "recommendation_engine"]:
            self.assertNotIn(token, text)

    def test_safety_booleans_are_conservative(self):
        tmpdir, _db_path, result = self.run_script([source_row()], apply=False)
        self.assertTrue(result["no_registry_mutation"])
        self.assertTrue(result["no_production_recommendation_change"])
        self.assertTrue(result["no_monitoring_change"])
        self.assertTrue(result["no_strategy_authorization"])
        self.assertTrue(result["no_betting_advice"])
        tmpdir.cleanup()


if __name__ == "__main__":
    unittest.main()
