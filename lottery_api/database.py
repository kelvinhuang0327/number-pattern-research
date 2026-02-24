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
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(draw, lottery_type)
                )
            """)
            
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
                        
                numbers_json = json.dumps(numbers)
                
                batch_data.append((
                    draw.get('draw'),
                    draw.get('date'),
                    draw.get('lotteryType'),
                    numbers_json,
                    draw.get('special', 0)
                ))
            
            # 使用 executemany 批次插入（大幅提升性能）
            # 注意：SQLite 的 executemany 在遇到 UNIQUE 約束時會全部失敗
            # 所以我們需要先檢查哪些是重複的
            
            # 方法1：使用 INSERT OR IGNORE（快速但無法統計重複數）
            # 方法2：分批處理並捕獲錯誤（準確統計）
            
            # 這裡使用方法1（優先性能）+ 後續統計
            cursor.executemany("""
                INSERT OR IGNORE INTO draws (draw, date, lottery_type, numbers, special)
                VALUES (?, ?, ?, ?, ?)
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
                SELECT id, draw, date, lottery_type, numbers, special, created_at
                FROM draws
                WHERE {where_clause}
                ORDER BY date DESC, draw DESC
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
                    'special': row['special'],
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
                    SELECT id, draw, date, lottery_type, numbers, special
                    FROM draws
                    WHERE lottery_type IN ({placeholders})
                    ORDER BY date DESC, draw DESC
                """
                logger.info(f"🔍 [get_all_draws] Query: {query}")
                logger.info(f"🔍 [get_all_draws] Params: {related_types}")
                cursor.execute(query, related_types)
            else:
                query = """
                    SELECT id, draw, date, lottery_type, numbers, special
                    FROM draws
                    ORDER BY date DESC, draw DESC
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
                    'special': row['special']
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
            # 按類型統計
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
            
            cursor.execute("DELETE FROM draws")
            conn.commit()
            
            logger.info(f"✅ Cleared {count} draws from database")
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
                SELECT id, draw, date, lottery_type, numbers, special
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
                'special': row['special']
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
                    'special': row['special']
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
