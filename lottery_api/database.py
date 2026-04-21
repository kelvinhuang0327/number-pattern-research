"""
SQLite 數據庫管理模組
負責所有彩票數據的持久化存儲
"""
import sqlite3
import json
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import os

logger = logging.getLogger(__name__)

# 不含特別號的彩種。DB 內可能用 0 當佔位值，但 API 輸出應正規化成 None。
_NO_SPECIAL_TYPES = {
    "DAILY_539",
    "BIG_LOTTO_BONUS",
    "3_STAR",
    "4_STAR",
    "39_LOTTO",
    "38_LOTTO",
    "49_LOTTO",
    "BINGO_BINGO",
    "DOUBLE_WIN",
    "LOTTO_6_38",
}


def _normalize_special_for_output(lottery_type: Optional[str], special):
    """對外輸出時統一沒有特別號的彩種回傳 None。"""
    if lottery_type in _NO_SPECIAL_TYPES:
        return None
    return special


class DatabaseManager:
    """SQLite 數據庫管理器"""
    
    def __init__(self, db_path: str = "data/lottery_v2.db"):
        """
        初始化數據庫管理器
        
        Args:
            db_path: 數據庫文件路徑
        """
        self.db_path = db_path
        
        # 確保數據目錄存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # 初始化數據庫
        self._init_database()
        
        logger.info(f"✅ Database initialized at {db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """獲取數據庫連接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 使用字典式訪問
        return conn
    
    def _init_database(self):
        """初始化數據庫表結構"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # 創建開獎記錄表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS draws (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    draw TEXT NOT NULL,
                    date TEXT NOT NULL,
                    lottery_type TEXT NOT NULL,
                    numbers TEXT NOT NULL,
                    special INTEGER DEFAULT 0,
                    jackpot_amount REAL DEFAULT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(draw, lottery_type)
                )
            """)
            try:
                cursor.execute("ALTER TABLE draws ADD COLUMN jackpot_amount REAL DEFAULT NULL")
                conn.commit()
            except Exception:
                pass
            
            # 創建索引以提升查詢性能
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_lottery_type 
                ON draws(lottery_type)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_date 
                ON draws(date DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_draw
                ON draws(draw)
            """)

            # 預測追蹤：預測批次（每次預測為一個 run）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prediction_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lottery_type TEXT NOT NULL,
                    latest_known_draw TEXT NOT NULL,
                    latest_known_date TEXT,
                    strategy_name TEXT NOT NULL,
                    snapshot_source TEXT DEFAULT 'VALID',
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Migration: add snapshot_source to existing tables (safe no-op if column exists)
            try:
                cursor.execute("ALTER TABLE prediction_runs ADD COLUMN snapshot_source TEXT DEFAULT 'VALID'")
                conn.commit()
            except Exception:
                pass
            # Migration: add analyzed field (run-level analysis status)
            try:
                cursor.execute("ALTER TABLE prediction_runs ADD COLUMN analyzed TEXT DEFAULT '未研究'")
                conn.commit()
            except Exception:
                pass
            # Migration: add analysis_note field (user-submitted analysis text)
            try:
                cursor.execute("ALTER TABLE prediction_runs ADD COLUMN analysis_note TEXT")
                conn.commit()
            except Exception:
                pass
            # Migration: add review_json field (structured review data from LLM Research Board)
            try:
                cursor.execute("ALTER TABLE prediction_runs ADD COLUMN review_json TEXT")
                conn.commit()
            except Exception:
                pass

            # 預測追蹤：每注預測
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prediction_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    bet_index INTEGER NOT NULL,
                    numbers TEXT NOT NULL,
                    special INTEGER,
                    status TEXT DEFAULT 'PENDING',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES prediction_runs(id)
                )
            """)

            # 預測追蹤：比對結果
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prediction_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER NOT NULL UNIQUE,
                    actual_draw TEXT NOT NULL,
                    actual_date TEXT,
                    actual_numbers TEXT NOT NULL,
                    actual_special INTEGER,
                    hit_count INTEGER NOT NULL,
                    matched_numbers TEXT NOT NULL,
                    special_hit INTEGER DEFAULT 0,
                    researched TEXT DEFAULT '無',
                    resolved_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (item_id) REFERENCES prediction_items(id)
                )
            """)
            # Migration: add researched column to existing tables (safe no-op if column exists)
            try:
                cursor.execute("ALTER TABLE prediction_results ADD COLUMN researched TEXT DEFAULT '無'")
                conn.commit()
            except Exception:
                pass
            # Migration: Winning Quality fields (P1-1)
            try:
                cursor.execute("ALTER TABLE prediction_results ADD COLUMN wq_score INTEGER DEFAULT NULL")
                conn.commit()
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE prediction_results ADD COLUMN split_risk TEXT DEFAULT NULL")
                conn.commit()
            except Exception:
                pass
            # Migration: zone_coverage for prediction_items (P1-3)
            try:
                cursor.execute("ALTER TABLE prediction_items ADD COLUMN zone_coverage TEXT DEFAULT NULL")
                conn.commit()
            except Exception:
                pass
            # Migration: add strategy_name and num_bets to prediction_items (multi-strategy per run)
            try:
                cursor.execute("ALTER TABLE prediction_items ADD COLUMN strategy_name TEXT")
                conn.commit()
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE prediction_items ADD COLUMN num_bets INTEGER")
                conn.commit()
            except Exception:
                pass

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pred_runs_lottery
                ON prediction_runs(lottery_type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pred_items_run
                ON prediction_items(run_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pred_items_status
                ON prediction_items(status)
            """)

            # ── Snapshot Schedule Table ─────────────────────────────────────
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS snapshot_schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lottery_type TEXT NOT NULL,
                    target_draw TEXT NOT NULL,
                    target_date TEXT,
                    scheduled_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'SCHEDULED',
                    run_id INTEGER,
                    notes TEXT,
                    UNIQUE(lottery_type, target_draw),
                    FOREIGN KEY (run_id) REFERENCES prediction_runs(id)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_schedule_lottery
                ON snapshot_schedule(lottery_type, status)
            """)

            # ── Research Review System Tables ──────────────────────────────

            # review_sessions: 每次檢討會議
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS review_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game TEXT NOT NULL,
                    draw TEXT,
                    draw_date TEXT,
                    session_type TEXT NOT NULL DEFAULT 'daily_review',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    summary TEXT,
                    final_decision TEXT DEFAULT 'NO_ACTION',
                    confidence_level TEXT DEFAULT 'LOW',
                    raw_report_text TEXT,
                    parsed_successfully INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'OPEN'
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_sessions_game ON review_sessions(game)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_sessions_draw ON review_sessions(draw)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_sessions_status ON review_sessions(status)")

            # review_findings: 檢討發現
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS review_findings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    section_type TEXT NOT NULL,
                    title TEXT,
                    content TEXT,
                    evidence_type TEXT DEFAULT 'UNSURE',
                    sort_order INTEGER DEFAULT 0,
                    FOREIGN KEY (session_id) REFERENCES review_sessions(id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_findings_session ON review_findings(session_id)")

            # review_hypotheses: 假說記錄
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS review_hypotheses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    hypothesis_type TEXT DEFAULT 'other',
                    description TEXT,
                    expected_impact TEXT,
                    validation_method TEXT,
                    kill_condition TEXT,
                    status TEXT DEFAULT 'PENDING',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES review_sessions(id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_hypotheses_session ON review_hypotheses(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_hypotheses_status ON review_hypotheses(status)")

            # review_actions: 行動項目
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS review_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    priority TEXT DEFAULT 'P2',
                    action_title TEXT,
                    action_description TEXT,
                    expected_gain TEXT,
                    cost_level TEXT,
                    risk_level TEXT,
                    validation_method TEXT,
                    stop_condition TEXT,
                    status TEXT DEFAULT 'OPEN',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES review_sessions(id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_actions_session ON review_actions(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_actions_status ON review_actions(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_actions_priority ON review_actions(priority)")

            # shadow_experiments: 影子實驗
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS shadow_experiments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    game TEXT NOT NULL,
                    experiment_name TEXT NOT NULL,
                    base_strategy TEXT,
                    experiment_strategy TEXT,
                    experiment_config_json TEXT,
                    status TEXT DEFAULT 'DRAFT',
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES review_sessions(id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_shadow_experiments_session ON shadow_experiments(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_shadow_experiments_game ON shadow_experiments(game)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_shadow_experiments_status ON shadow_experiments(status)")

            # prediction_review_status: 預測與檢討的關聯
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prediction_review_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prediction_run_id INTEGER,
                    review_session_id INTEGER,
                    review_status TEXT DEFAULT 'UNREVIEWED',
                    resolved_at TEXT,
                    notes TEXT,
                    FOREIGN KEY (prediction_run_id) REFERENCES prediction_runs(id),
                    FOREIGN KEY (review_session_id) REFERENCES review_sessions(id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pred_review_run ON prediction_review_status(prediction_run_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pred_review_session ON prediction_review_status(review_session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pred_review_status ON prediction_review_status(review_status)")

            conn.commit()
            logger.info("✅ Database tables and indexes created")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Database initialization failed: {e}")
            raise
        finally:
            conn.close()
    
    def insert_draws(self, draws: List[Dict]) -> Tuple[int, int]:
        """
        批量插入開獎記錄（優化版 - 使用 executemany）
        
        Args:
            draws: 開獎記錄列表
            
        Returns:
            (inserted_count, duplicate_count) 元組
        """
        if not draws:
            return (0, 0)
            
        conn = self._get_connection()
        cursor = conn.cursor()
        
        inserted = 0
        duplicates = 0
        
        try:
            # 準備批次插入的數據
            batch_data = []
            
            # Debug: Log first item to check structure
            if len(draws) > 0:
                logger.info(f"🔍 First draw data sample: {draws[0]}")
            
            for draw in draws:
                # 處理 numbers 字段，防止雙重序列化
                numbers = draw.get('numbers', [])
                if isinstance(numbers, str):
                    try:
                        parsed = json.loads(numbers)
                        if isinstance(parsed, list):
                            numbers = parsed
                    except (json.JSONDecodeError, TypeError):
                        pass
                        
                numbers_json = json.dumps(sorted(numbers))
                jackpot_amount = draw.get('jackpot_amount', draw.get('jackpot'))
                if jackpot_amount in (None, ""):
                    jackpot_amount = None
                else:
                    try:
                        jackpot_amount = float(jackpot_amount)
                    except Exception:
                        jackpot_amount = None
                
                batch_data.append((
                    draw.get('draw'),
                    draw.get('date'),
                    draw.get('lotteryType'),
                    numbers_json,
                    draw.get('special', 0),
                    jackpot_amount,
                ))
            
            # 使用 executemany 批次插入（大幅提升性能）
            # 注意：SQLite 的 executemany 在遇到 UNIQUE 約束時會全部失敗
            # 所以我們需要先檢查哪些是重複的
            
            # 方法1：使用 INSERT OR IGNORE（快速但無法統計重複數）
            # 方法2：分批處理並捕獲錯誤（準確統計）
            
            # 這裡使用方法1（優先性能）+ 後續統計
            cursor.executemany("""
                INSERT OR IGNORE INTO draws (draw, date, lottery_type, numbers, special, jackpot_amount)
                VALUES (?, ?, ?, ?, ?, ?)
            """, batch_data)
            
            inserted = cursor.rowcount
            duplicates = len(draws) - inserted
            
            conn.commit()
            logger.info(f"✅ Batch inserted {inserted} draws, {duplicates} duplicates skipped")
            
            return (inserted, duplicates)
            
        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Insert failed: {e}")
            raise
        finally:
            conn.close()
    
    def get_draws(
        self,
        lottery_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict:
        """
        分頁查詢開獎記錄
        
        Args:
            lottery_type: 彩券類型篩選
            page: 頁碼（從 1 開始）
            page_size: 每頁數量
            start_date: 開始日期
            end_date: 結束日期
            
        Returns:
            包含 draws, total, page, page_size, total_pages 的字典
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # 構建查詢條件
            conditions = []
            params = []

            if lottery_type:
                # ✅ 使用相關類型查詢
                from .common import get_related_lottery_types
                related_types = get_related_lottery_types(lottery_type)

                # 使用 IN 子句支持多個類型
                placeholders = ','.join('?' * len(related_types))
                conditions.append(f"lottery_type IN ({placeholders})")
                params.extend(related_types)

            if start_date:
                conditions.append("date >= ?")
                params.append(start_date)

            if end_date:
                conditions.append("date <= ?")
                params.append(end_date)

            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            # 查詢總數
            count_query = f"SELECT COUNT(*) FROM draws WHERE {where_clause}"
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]
            
            # 計算分頁
            offset = (page - 1) * page_size
            total_pages = (total + page_size - 1) // page_size
            
            # 查詢數據
            data_query = f"""
                SELECT id, draw, date, lottery_type, numbers, special, jackpot_amount, created_at
                FROM draws
                WHERE {where_clause}
                ORDER BY CAST(draw AS INTEGER) DESC
                LIMIT ? OFFSET ?
            """
            cursor.execute(data_query, params + [page_size, offset])
            
            rows = cursor.fetchall()
            draws = []
            
            for row in rows:
                draws.append({
                    'id': row['id'],
                    'draw': row['draw'],
                    'date': row['date'],
                    'lotteryType': row['lottery_type'],
                    'numbers': json.loads(row['numbers']),
                    'special': _normalize_special_for_output(row['lottery_type'], row['special']),
                    'jackpot_amount': row['jackpot_amount'],
                    'created_at': row['created_at']
                })
            
            return {
                'draws': draws,
                'total': total,
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages
            }
            
        except Exception as e:
            logger.error(f"❌ Query failed: {e}")
            raise
        finally:
            conn.close()
    
    def get_all_draws(self, lottery_type: Optional[str] = None) -> List[Dict]:
        """
        獲取所有開獎記錄（不分頁）- 支持相關類型查詢

        Args:
            lottery_type: 可選的彩券類型篩選（會自動包含相關類型）

        Returns:
            開獎記錄列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            logger.info(f"🔍 [get_all_draws] Using database: {self.db_path}")

            if lottery_type:
                # ✅ 導入並使用 get_related_lottery_types（支援直接執行和模組導入）
                try:
                    from .common import get_related_lottery_types
                except ImportError:
                    from common import get_related_lottery_types

                # 獲取相關類型（例如：BIG_LOTTO -> [BIG_LOTTO, BIG_LOTTO_BONUS]）
                related_types = get_related_lottery_types(lottery_type)
                logger.info(f"🔍 [get_all_draws] Related types: {related_types}")

                # 使用 IN 查詢支持多個相關類型
                placeholders = ','.join('?' * len(related_types))
                query = f"""
                    SELECT id, draw, date, lottery_type, numbers, special, jackpot_amount
                    FROM draws
                    WHERE lottery_type IN ({placeholders})
                    ORDER BY CAST(draw AS INTEGER) DESC
                """
                logger.info(f"🔍 [get_all_draws] Query: {query}")
                logger.info(f"🔍 [get_all_draws] Params: {related_types}")
                cursor.execute(query, related_types)
            else:
                query = """
                    SELECT id, draw, date, lottery_type, numbers, special, jackpot_amount
                    FROM draws
                    ORDER BY CAST(draw AS INTEGER) DESC
                """
                cursor.execute(query)

            rows = cursor.fetchall()
            logger.info(f"🔍 [get_all_draws] SQL fetchall() returned {len(rows)} rows")

            draws = []

            for row in rows:
                draws.append({
                    'draw': row['draw'],
                    'date': row['date'],
                    'lotteryType': row['lottery_type'],
                    'numbers': json.loads(row['numbers']),
                    'special': _normalize_special_for_output(row['lottery_type'], row['special']),
                    'jackpot_amount': row['jackpot_amount'],
                })

            logger.info(f"🔍 [get_all_draws] Parsed {len(draws)} draws, returning...")
            return draws

        except Exception as e:
            logger.error(f"❌ Get all draws failed: {e}")
            raise
        finally:
            conn.close()
    
    def get_stats(self, lottery_type: Optional[str] = None) -> Dict:
        """
        獲取統計信息
        
        Args:
            lottery_type: 可選的彩券類型篩選
            
        Returns:
            統計信息字典
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # 按類型統計（若指定 lottery_type 則只回傳該類型）
            if lottery_type:
                cursor.execute("""
                    SELECT lottery_type, COUNT(*) as count
                    FROM draws
                    WHERE lottery_type = ?
                    GROUP BY lottery_type
                """, (lottery_type,))
            else:
                cursor.execute("""
                    SELECT lottery_type, COUNT(*) as count
                    FROM draws
                    GROUP BY lottery_type
                """)

            by_type = {}
            total = 0

            for row in cursor.fetchall():
                by_type[row['lottery_type']] = row['count']
                total += row['count']

            # 日期範圍
            if lottery_type:
                cursor.execute("""
                    SELECT MIN(date) as earliest, MAX(date) as latest
                    FROM draws
                    WHERE lottery_type = ?
                """, (lottery_type,))
            else:
                cursor.execute("""
                    SELECT MIN(date) as earliest, MAX(date) as latest
                    FROM draws
                """)
            
            date_row = cursor.fetchone()
            
            return {
                'total': total,
                'by_type': by_type,
                'date_range': {
                    'earliest': date_row['earliest'],
                    'latest': date_row['latest']
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Get stats failed: {e}")
            raise
        finally:
            conn.close()
    
    def delete_draw(self, draw_id: int) -> bool:
        """
        刪除指定的開獎記錄
        
        Args:
            draw_id: 記錄 ID
            
        Returns:
            是否刪除成功
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM draws WHERE id = ?", (draw_id,))
            conn.commit()
            
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"✅ Deleted draw {draw_id}")
            
            return deleted
            
        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Delete failed: {e}")
            raise
        finally:
            conn.close()
    
    def clear_all_data(self) -> int:
        """
        清空所有數據
        
        Returns:
            刪除的記錄數
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) FROM draws")
            count = cursor.fetchone()[0]

            # 清除所有業務表（依外鍵順序：子表先刪）
            for table in (
                "prediction_results",
                "prediction_items",
                "snapshot_schedule",
                "prediction_runs",
                "draws",
            ):
                cursor.execute(f"DELETE FROM {table}")

            conn.commit()

            logger.info(f"✅ Cleared {count} draws and all prediction data from database")
            return count
            
        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Clear failed: {e}")
            raise
        finally:
            conn.close()
    
    def vacuum(self):
        """優化數據庫（回收空間）"""
        conn = self._get_connection()
        try:
            conn.execute("VACUUM")
            logger.info("✅ Database vacuumed")
        except Exception as e:
            logger.error(f"❌ Vacuum failed: {e}")
            raise
        finally:
            conn.close()

    def get_draw(self, lottery_type: str, draw_number: str) -> Optional[Dict]:
        """
        根據期號獲取開獎記錄
        
        Args:
            lottery_type: 彩券類型
            draw_number: 期號
            
        Returns:
            開獎記錄字典或 None
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, draw, date, lottery_type, numbers, special, jackpot_amount
                FROM draws
                WHERE lottery_type = ? AND draw = ?
            """, (lottery_type, draw_number))
            
            row = cursor.fetchone()
            if not row:
                return None
                
            return {
                'id': row['id'],
                'draw': row['draw'],
                'date': row['date'],
                'lotteryType': row['lottery_type'],
                'numbers': json.loads(row['numbers']),
                'special': _normalize_special_for_output(row['lottery_type'], row['special']),
                'jackpot_amount': row['jackpot_amount'],
            }
            
        except Exception as e:
            logger.error(f"❌ Get draw failed: {e}")
            raise
        finally:
            conn.close()

    def get_draws_by_range(
        self,
        lottery_type: str,
        start_draw: Optional[str] = None,
        end_draw: Optional[str] = None
    ) -> List[Dict]:
        """
        根據期數範圍查詢開獎記錄 - 支持相關類型

        Args:
            lottery_type: 彩券類型（會自動包含相關類型）
            start_draw: 起始期數（包含），None 表示從最早開始
            end_draw: 結束期數（包含），None 表示到最新為止

        Returns:
            開獎記錄列表（按日期和期數升序排序）
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # ✅ 使用相關類型查詢
            from .common import get_related_lottery_types
            related_types = get_related_lottery_types(lottery_type)

            # 構建查詢條件
            placeholders = ','.join('?' * len(related_types))
            conditions = [f"lottery_type IN ({placeholders})"]
            params = list(related_types)

            if start_draw:
                # 使用 CAST 將 draw 轉為整數進行比較
                conditions.append("CAST(draw AS INTEGER) >= ?")
                params.append(int(start_draw))

            if end_draw:
                # 使用 CAST 將 draw 轉為整數進行比較
                conditions.append("CAST(draw AS INTEGER) <= ?")
                params.append(int(end_draw))

            where_clause = " AND ".join(conditions)

            # 查詢數據（按期號整數升序排列）
            query = f"""
                SELECT draw, date, lottery_type, numbers, special
                FROM draws
                WHERE {where_clause}
                ORDER BY CAST(draw AS INTEGER) ASC
            """

            logger.info(f"🔍 SQL Query: {query}")
            logger.info(f"🔍 Params: {params}")

            cursor.execute(query, params)

            rows = cursor.fetchall()
            draws = []

            for row in rows:
                draws.append({
                    'draw': row['draw'],
                    'date': row['date'],
                    'lotteryType': row['lottery_type'],
                    'numbers': json.loads(row['numbers']),
                    'special': _normalize_special_for_output(row['lottery_type'], row['special'])
                })

            logger.info(f"✅ 查詢範圍預測數據: {lottery_type} {start_draw or '最早'} - {end_draw or '最新'}, 共 {len(draws)} 期")

            return draws

        except Exception as e:
            logger.error(f"❌ Range query failed: {e}")
            raise
        finally:
            conn.close()


# 全局數據庫實例
db_manager = DatabaseManager()
