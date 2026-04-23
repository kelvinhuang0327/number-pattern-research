#!/usr/bin/env python3
"""
Migrate database to add sell_amount and total_amount columns for pool-size research.
This is a one-time migration to support H013 validation.
"""
import sqlite3
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = "lottery_api/data/lottery_v2.db"

def migrate():
    """Add sell_amount and total_amount columns to draws table if they don't exist."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(draws)")
        columns = {row[1] for row in cursor.fetchall()}
        
        if 'sell_amount' in columns and 'total_amount' in columns:
            logger.info("✅ Columns already exist. Migration skipped.")
            return True
        
        # Add columns if missing
        if 'sell_amount' not in columns:
            logger.info("Adding sell_amount column...")
            cursor.execute("ALTER TABLE draws ADD COLUMN sell_amount REAL DEFAULT NULL")
        
        if 'total_amount' not in columns:
            logger.info("Adding total_amount column...")
            cursor.execute("ALTER TABLE draws ADD COLUMN total_amount REAL DEFAULT NULL")
        
        conn.commit()
        logger.info("✅ Migration completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
