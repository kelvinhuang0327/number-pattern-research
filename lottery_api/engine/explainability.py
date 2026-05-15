"""
Explainability Engine — Phase P
================================
Persistence and retrieval for prediction decision traces.

Provides:
  - save_explanation()   — persist an explanation snapshot per prediction run
  - get_explanation()    — retrieve by run_id
  - get_latest()         — retrieve latest by lottery_type
  - get_summary()        — aggregated statistics

DB Table: prediction_explanations (auto-created)

2026-04-16 Created — Phase P
"""
import os
import json
import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'lottery_v2.db'
)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS prediction_explanations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_run_id INTEGER,
    lottery_type TEXT NOT NULL,
    profile TEXT NOT NULL DEFAULT 'balanced',
    explanation_json TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(prediction_run_id)
);
"""


def _ensure_table():
    """Create table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(_CREATE_TABLE_SQL)
        conn.commit()
    finally:
        conn.close()


def save_explanation(
    lottery_type: str,
    explanation: Dict,
    prediction_run_id: Optional[int] = None,
    profile: str = 'balanced',
) -> int:
    """
    Persist an explanation snapshot. Returns the row id.

    If prediction_run_id is provided, upserts (replace on conflict).
    """
    _ensure_table()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        explanation_json = json.dumps(explanation, ensure_ascii=False, default=str)
        if prediction_run_id is not None:
            cur.execute("""
                INSERT INTO prediction_explanations
                  (prediction_run_id, lottery_type, profile, explanation_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(prediction_run_id) DO UPDATE SET
                  explanation_json = excluded.explanation_json,
                  created_at = excluded.created_at
            """, (prediction_run_id, lottery_type, profile, explanation_json,
                  datetime.now().isoformat()))
        else:
            cur.execute("""
                INSERT INTO prediction_explanations
                  (lottery_type, profile, explanation_json, created_at)
                VALUES (?, ?, ?, ?)
            """, (lottery_type, profile, explanation_json,
                  datetime.now().isoformat()))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_explanation_by_run(prediction_run_id: int) -> Optional[Dict]:
    """Retrieve explanation for a specific prediction run."""
    _ensure_table()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, prediction_run_id, lottery_type, profile,
                   explanation_json, created_at
            FROM prediction_explanations
            WHERE prediction_run_id = ?
        """, (prediction_run_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            'id': row[0],
            'prediction_run_id': row[1],
            'lottery_type': row[2],
            'profile': row[3],
            'explanation': json.loads(row[4]),
            'created_at': row[5],
        }
    finally:
        conn.close()


def get_latest_explanation(lottery_type: str) -> Optional[Dict]:
    """Retrieve the most recent explanation for a lottery type."""
    _ensure_table()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, prediction_run_id, lottery_type, profile,
                   explanation_json, created_at
            FROM prediction_explanations
            WHERE lottery_type = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (lottery_type,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            'id': row[0],
            'prediction_run_id': row[1],
            'lottery_type': row[2],
            'profile': row[3],
            'explanation': json.loads(row[4]),
            'created_at': row[5],
        }
    finally:
        conn.close()


def get_summary() -> Dict:
    """
    Aggregated statistics across all stored explanations.

    Returns counts of learning enabled/disabled/weak, ranking changes, etc.
    """
    _ensure_table()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT lottery_type, explanation_json
            FROM prediction_explanations
            ORDER BY created_at DESC
            LIMIT 200
        """)
        rows = cur.fetchall()

        summary = {
            'total_explanations': len(rows),
            'by_lottery_type': {},
        }

        for lt, ej in rows:
            if lt not in summary['by_lottery_type']:
                summary['by_lottery_type'][lt] = {
                    'count': 0,
                    'learning_enabled': 0,
                    'learning_weak': 0,
                    'learning_disabled': 0,
                    'ranking_changed': 0,
                    'quality_applied': 0,
                }
            entry = summary['by_lottery_type'][lt]
            entry['count'] += 1

            try:
                exp = json.loads(ej)
                gate = exp.get('learning', {}).get('gate', 'DISABLED')
                if gate == 'ENABLED':
                    entry['learning_enabled'] += 1
                elif gate == 'WEAK':
                    entry['learning_weak'] += 1
                else:
                    entry['learning_disabled'] += 1

                if exp.get('selection', {}).get('ranking_changed'):
                    entry['ranking_changed'] += 1

                if exp.get('quality', {}).get('enabled'):
                    entry['quality_applied'] += 1
            except Exception:
                pass

        return summary
    finally:
        conn.close()
