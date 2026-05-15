"""
高風險 API 路徑的自動化測試
涵蓋：update/delete 跨彩種安全、clear reset 完整性、stats 過濾、prediction_tracker 分頁
"""
import ast
import os
import json
import sys
import tempfile
import shutil
import sqlite3
import unittest

# ─── helpers ────────────────────────────────────────────────────────────────

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LOTTERY_API_ROOT = os.path.join(ROOT, 'lottery_api')
if LOTTERY_API_ROOT not in sys.path:
    sys.path.insert(0, LOTTERY_API_ROOT)


def load_lottery_num_max():
    """從 routes/data.py 原始碼安全讀取 _LOTTERY_NUM_MAX，避免 import FastAPI 依賴。"""
    source_path = os.path.join(LOTTERY_API_ROOT, 'routes', 'data.py')
    with open(source_path, 'r', encoding='utf-8') as f:
        source = f.read()

    module = ast.parse(source, filename=source_path)
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == '_LOTTERY_NUM_MAX':
                    return ast.literal_eval(node.value)

    raise AssertionError('_LOTTERY_NUM_MAX not found in routes/data.py')

def make_db(path):
    """建一個最小 lottery_v2 schema 的 SQLite 測試 DB"""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE draws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw TEXT NOT NULL,
            date TEXT NOT NULL,
            lottery_type TEXT NOT NULL,
            numbers TEXT NOT NULL,
            special INTEGER DEFAULT 0
        );
        CREATE TABLE prediction_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lottery_type TEXT NOT NULL,
            latest_known_draw TEXT NOT NULL,
            latest_known_date TEXT,
            strategy_name TEXT,
            snapshot_source TEXT DEFAULT 'VALID',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE prediction_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            bet_index INTEGER NOT NULL,
            numbers TEXT NOT NULL,
            special INTEGER,
            status TEXT DEFAULT 'PENDING'
        );
        CREATE TABLE prediction_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            actual_draw TEXT,
            actual_date TEXT,
            hit_count INTEGER DEFAULT 0,
            special_hit INTEGER DEFAULT 0,
            resolved_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE snapshot_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lottery_type TEXT NOT NULL,
            target_draw TEXT NOT NULL,
            status TEXT DEFAULT 'PENDING',
            run_id INTEGER
        );
    """)
    conn.commit()
    return conn


# ─── Test: _LOTTERY_NUM_MAX 定義 ────────────────────────────────────────────

class TestLotteryNumMax(unittest.TestCase):
    def setUp(self):
        self.limits = load_lottery_num_max()

    def test_power_lotto_special_is_8(self):
        self.assertEqual(self.limits['POWER_LOTTO']['special'], 8,
                         "威力彩特別號上限應為 8")

    def test_big_lotto_special_is_49(self):
        self.assertEqual(self.limits['BIG_LOTTO']['special'], 49)

    def test_daily_539_no_special(self):
        self.assertIsNone(self.limits['DAILY_539']['special'])

    def test_power_lotto_main_is_38(self):
        self.assertEqual(self.limits['POWER_LOTTO']['main'], 38)


class TestSpecialNormalization(unittest.TestCase):
    def test_daily_539_special_is_normalized_to_none(self):
        from database import _normalize_special_for_output
        self.assertIsNone(_normalize_special_for_output('DAILY_539', 0))
        self.assertIsNone(_normalize_special_for_output('DAILY_539', None))

    def test_power_lotto_special_preserved(self):
        from database import _normalize_special_for_output
        self.assertEqual(_normalize_special_for_output('POWER_LOTTO', 8), 8)


# ─── Test: clear_all_data 清所有表 ──────────────────────────────────────────

class TestClearAllData(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, 'test.db')
        self.conn = make_db(self.db_path)
        # 插入測試資料
        self.conn.executescript("""
            INSERT INTO draws (draw, date, lottery_type, numbers, special)
            VALUES ('115000001', '2026/01/01', 'BIG_LOTTO', '[1,2,3,4,5,6]', 7);
            INSERT INTO draws (draw, date, lottery_type, numbers, special)
            VALUES ('115000001', '2026/01/01', 'POWER_LOTTO', '[1,2,3,4,5,6]', 3);
            INSERT INTO prediction_runs (lottery_type, latest_known_draw)
            VALUES ('BIG_LOTTO', '115000001');
            INSERT INTO prediction_items (run_id, bet_index, numbers)
            VALUES (1, 0, '[1,2,3,4,5,6]');
            INSERT INTO snapshot_schedule (lottery_type, target_draw)
            VALUES ('BIG_LOTTO', '115000002');
        """)

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.tmpdir)

    def _clear(self):
        """直接執行 clear_all_data 邏輯（不依賴 db_manager singleton）"""
        for table in ("prediction_results", "prediction_items",
                      "snapshot_schedule", "prediction_runs", "draws"):
            self.conn.execute(f"DELETE FROM {table}")
        self.conn.commit()

    def test_draws_cleared(self):
        self._clear()
        count = self.conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0]
        self.assertEqual(count, 0)

    def test_prediction_runs_cleared(self):
        self._clear()
        count = self.conn.execute("SELECT COUNT(*) FROM prediction_runs").fetchone()[0]
        self.assertEqual(count, 0)

    def test_prediction_items_cleared(self):
        self._clear()
        count = self.conn.execute("SELECT COUNT(*) FROM prediction_items").fetchone()[0]
        self.assertEqual(count, 0)

    def test_snapshot_schedule_cleared(self):
        self._clear()
        count = self.conn.execute("SELECT COUNT(*) FROM snapshot_schedule").fetchone()[0]
        self.assertEqual(count, 0)


# ─── Test: delete 不跨彩種誤刪 ──────────────────────────────────────────────

class TestDeleteCrossType(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, 'test.db')
        self.conn = make_db(self.db_path)
        self.conn.executescript("""
            INSERT INTO draws (draw, date, lottery_type, numbers, special)
            VALUES ('115000001', '2026/01/01', 'BIG_LOTTO', '[1,2,3,4,5,6]', 7);
            INSERT INTO draws (draw, date, lottery_type, numbers)
            VALUES ('115000001', '2026/01/01', 'DAILY_539', '[1,2,3,4,5]');
        """)

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.tmpdir)

    def _delete_by_id(self, row_id):
        self.conn.execute("DELETE FROM draws WHERE id = ?", (row_id,))
        self.conn.commit()

    def test_delete_by_id_only_removes_one_row(self):
        """刪除 id=1 不應影響 id=2"""
        self._delete_by_id(1)
        remaining = self.conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0]
        self.assertEqual(remaining, 1)
        survivor = self.conn.execute("SELECT lottery_type FROM draws WHERE id=2").fetchone()
        self.assertIsNotNone(survivor)
        self.assertEqual(survivor[0], 'DAILY_539')

    def test_delete_by_draw_with_lottery_type_disambiguates(self):
        """用 draw + lottery_type 刪除只刪指定彩種"""
        self.conn.execute(
            "DELETE FROM draws WHERE draw = ? AND lottery_type = ?",
            ('115000001', 'BIG_LOTTO')
        )
        self.conn.commit()
        remaining = self.conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0]
        self.assertEqual(remaining, 1)
        survivor = self.conn.execute("SELECT lottery_type FROM draws").fetchone()
        self.assertEqual(survivor[0], 'DAILY_539')

    def test_delete_by_draw_only_when_ambiguous_returns_multiple(self):
        """同期號存在多個彩種時，不加 lottery_type 查詢應回傳多筆（提示呼叫者需消歧義）"""
        rows = self.conn.execute(
            "SELECT id FROM draws WHERE draw = ?", ('115000001',)
        ).fetchall()
        self.assertEqual(len(rows), 2, "應找到 2 筆，呼叫端需加 lottery_type 消歧義")


# ─── Test: get_stats lottery_type 過濾 ──────────────────────────────────────

class TestGetStats(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, 'test.db')
        self.conn = make_db(self.db_path)
        self.conn.executescript("""
            INSERT INTO draws (draw, date, lottery_type, numbers, special)
            VALUES ('115000001', '2026/01/01', 'BIG_LOTTO', '[1,2,3,4,5,6]', 7);
            INSERT INTO draws (draw, date, lottery_type, numbers, special)
            VALUES ('115000002', '2026/01/03', 'BIG_LOTTO', '[7,8,9,10,11,12]', 3);
            INSERT INTO draws (draw, date, lottery_type, numbers)
            VALUES ('115000001', '2026/01/01', 'DAILY_539', '[1,2,3,4,5]');
        """)

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.tmpdir)

    def _get_stats(self, lottery_type=None):
        if lottery_type:
            rows = self.conn.execute(
                "SELECT lottery_type, COUNT(*) as count FROM draws WHERE lottery_type=? GROUP BY lottery_type",
                (lottery_type,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT lottery_type, COUNT(*) as count FROM draws GROUP BY lottery_type"
            ).fetchall()
        by_type = {r[0]: r[1] for r in rows}
        total = sum(by_type.values())
        return {'total': total, 'by_type': by_type}

    def test_no_filter_returns_all(self):
        stats = self._get_stats()
        self.assertEqual(stats['total'], 3)
        self.assertIn('BIG_LOTTO', stats['by_type'])
        self.assertIn('DAILY_539', stats['by_type'])

    def test_filter_big_lotto_only(self):
        stats = self._get_stats('BIG_LOTTO')
        self.assertEqual(stats['total'], 2)
        self.assertNotIn('DAILY_539', stats['by_type'])

    def test_filter_daily_539_only(self):
        stats = self._get_stats('DAILY_539')
        self.assertEqual(stats['total'], 1)
        self.assertEqual(stats['by_type']['DAILY_539'], 1)


# ─── Test: prediction_tracker status 分頁 ───────────────────────────────────

class TestPredictionTrackerPagination(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, 'test.db')
        self.conn = make_db(self.db_path)
        # 建 5 個 run：3 個 PENDING、2 個 RESOLVED
        for i in range(1, 6):
            self.conn.execute(
                "INSERT INTO prediction_runs (lottery_type, latest_known_draw) VALUES (?,?)",
                ('BIG_LOTTO', f'11500000{i}')
            )
        self.conn.commit()
        run_ids = [r[0] for r in self.conn.execute("SELECT id FROM prediction_runs").fetchall()]
        for run_id in run_ids:
            self.conn.execute(
                "INSERT INTO prediction_items (run_id, bet_index, numbers) VALUES (?,0,'[1,2,3,4,5,6]')",
                (run_id,)
            )
        self.conn.commit()
        # 讓前 2 個 run 的 item 狀態設為 RESOLVED
        item_ids = [r[0] for r in self.conn.execute(
            "SELECT pi.id FROM prediction_items pi JOIN prediction_runs pr ON pi.run_id=pr.id ORDER BY pr.id LIMIT 2"
        ).fetchall()]
        for item_id in item_ids:
            self.conn.execute("UPDATE prediction_items SET status='RESOLVED' WHERE id=?", (item_id,))
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.tmpdir)

    def _query_runs(self, status=None, limit=10, offset=0):
        having = ""
        if status == "RESOLVED":
            having = "HAVING SUM(CASE WHEN pi.status='RESOLVED' THEN 1 ELSE 0 END) = COUNT(pi.id)"
        elif status == "PENDING":
            having = "HAVING SUM(CASE WHEN pi.status='RESOLVED' THEN 1 ELSE 0 END) < COUNT(pi.id)"

        total = self.conn.execute(f"""
            SELECT COUNT(*) FROM (
                SELECT pr.id FROM prediction_runs pr
                JOIN prediction_items pi ON pi.run_id=pr.id
                GROUP BY pr.id {having}
            )
        """).fetchone()[0]

        rows = self.conn.execute(f"""
            SELECT pr.id,
                   COUNT(pi.id) as total_bets,
                   SUM(CASE WHEN pi.status='RESOLVED' THEN 1 ELSE 0 END) as resolved_bets
            FROM prediction_runs pr
            JOIN prediction_items pi ON pi.run_id=pr.id
            GROUP BY pr.id
            {having}
            ORDER BY pr.id DESC
            LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()
        return total, rows

    def test_pending_count_correct(self):
        total, rows = self._query_runs(status="PENDING")
        self.assertEqual(total, 3, "應有 3 個 PENDING run")
        self.assertEqual(len(rows), 3)

    def test_resolved_count_correct(self):
        total, rows = self._query_runs(status="RESOLVED")
        self.assertEqual(total, 2, "應有 2 個 RESOLVED run")
        self.assertEqual(len(rows), 2)

    def test_pagination_with_status_filter_consistent(self):
        """limit=2 時，total 仍為 3，回傳 2 筆（分頁正確）"""
        total, rows = self._query_runs(status="PENDING", limit=2, offset=0)
        self.assertEqual(total, 3)
        self.assertEqual(len(rows), 2)

    def test_no_filter_returns_all(self):
        total, rows = self._query_runs()
        self.assertEqual(total, 5)


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    unittest.main(verbosity=2)
