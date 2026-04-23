#!/usr/bin/env python3
"""
Backfill DAILY_539 pool-size data from official Taiwan Lottery API.
Fetches sell_amount and total_amount for all historical draws.
"""
import sqlite3
import logging
import time
from datetime import datetime, timedelta
import json

try:
    import requests
except ImportError:
    print("Error: requests library not installed. Run: pip install requests")
    exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = "lottery_api/data/lottery_v2.db"
API_BASE = "https://api.taiwanlottery.com/TLCAPIWeB"
FETCH_TIMEOUT = 15
RETRY_MAX = 3
RETRY_DELAY = 1.5
POLITE_DELAY = 0.8

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Origin": "https://www.taiwanlottery.com",
    "Referer": "https://www.taiwanlottery.com/",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8",
}


def fetch_daily539_month(start_month: str, end_month: str, page_size: int = 100) -> list:
    """
    Fetch DAILY_539 results for a given month range from official API.
    Returns list of draw dicts with pool-size fields.
    """
    url = API_BASE + "/Lottery/Daily539Result"
    params = {
        "pageNum": 1,
        "pageSize": page_size,
        "startMonth": start_month,
        "endMonth": end_month,
    }
    
    for attempt in range(1, RETRY_MAX + 1):
        try:
            logger.info(f"🌐 Fetching Daily539 {start_month}~{end_month} (attempt {attempt})")
            resp = requests.get(url, params=params, headers=HEADERS, timeout=FETCH_TIMEOUT)
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("rtCode") == 0:
                    rows = data.get("content", {}).get("daily539Res", [])
                    logger.info(f"✅ Fetched {len(rows)} draws for {start_month}~{end_month}")
                    
                    # Convert API rows to our schema
                    draws = []
                    for row in rows:
                        try:
                            period = str(row.get("period"))
                            date_raw = row.get("lotteryDate", "")[:10].replace("-", "/")
                            draw_nums = row.get("drawNumberSize", [])
                            
                            if len(draw_nums) >= 5:
                                numbers = sorted(draw_nums[:5])
                                draw_dict = {
                                    "draw": period,
                                    "date": date_raw,
                                    "lotteryType": "DAILY_539",
                                    "numbers": numbers,
                                    "special": 0,
                                    "sell_amount": row.get("sellAmount"),
                                    "total_amount": row.get("totalAmount"),
                                }
                                draws.append(draw_dict)
                        except Exception as e:
                            logger.warning(f"⚠️  Failed to parse row {row.get('period')}: {e}")
                    
                    return draws
                else:
                    logger.warning(f"⚠️  API error rtCode={data.get('rtCode')}: {data.get('rtMsg')}")
                    return []
            else:
                logger.warning(f"⚠️  HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"⚠️  Fetch error: {e}")
        
        if attempt < RETRY_MAX:
            time.sleep(RETRY_DELAY * attempt)
    
    logger.error(f"❌ Failed to fetch after {RETRY_MAX} attempts")
    return []


def backfill_all_daily539():
    """
    Fetch and backfill all DAILY_539 historical data from official API.
    DAILY_539 started in 2007.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get current data coverage
        cursor.execute("SELECT COUNT(*) FROM draws WHERE lottery_type='DAILY_539'")
        existing_count = cursor.fetchone()[0]
        logger.info(f"📊 Existing DAILY_539 draws: {existing_count}")
        
        # Fetch from 2007 to now, month by month
        start_date = datetime(2007, 1, 1)
        end_date = datetime.now()
        
        current = start_date
        total_fetched = 0
        total_updated = 0
        
        while current <= end_date:
            start_month = current.strftime("%Y-%m")
            
            # End month is the same for monthly fetch
            month_end = current + timedelta(days=32)
            month_end = month_end.replace(day=1) - timedelta(days=1)
            end_month = month_end.strftime("%Y-%m")
            
            # Fetch draws for this month
            draws = fetch_daily539_month(start_month, end_month)
            
            if draws:
                total_fetched += len(draws)
                
                # Update database with pool-size data
                for draw in draws:
                    cursor.execute("""
                        UPDATE draws 
                        SET sell_amount=?, total_amount=?
                        WHERE draw=? AND lottery_type='DAILY_539'
                    """, (draw.get('sell_amount'), draw.get('total_amount'), draw.get('draw')))
                    
                    if cursor.rowcount == 0:
                        # Insert if not exists
                        try:
                            cursor.execute("""
                                INSERT INTO draws 
                                (draw, date, lottery_type, numbers, special, sell_amount, total_amount)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (
                                draw['draw'],
                                draw['date'],
                                draw['lotteryType'],
                                json.dumps(draw['numbers']),
                                draw.get('special', 0),
                                draw.get('sell_amount'),
                                draw.get('total_amount'),
                            ))
                            total_updated += 1
                        except sqlite3.IntegrityError:
                            # Already exists, just update
                            pass
                
                conn.commit()
            
            # Polite delay between API calls
            time.sleep(POLITE_DELAY)
            
            # Move to next month
            current = month_end + timedelta(days=1)
        
        logger.info(f"✅ Backfill complete: {total_fetched} draws processed, {total_updated} new rows inserted")
        
        # Show coverage stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(sell_amount) as nonnull_sell,
                COUNT(total_amount) as nonnull_total,
                ROUND(100.0 * COUNT(sell_amount) / COUNT(*), 2) as pct_sell,
                ROUND(100.0 * COUNT(total_amount) / COUNT(*), 2) as pct_total
            FROM draws WHERE lottery_type='DAILY_539'
        """)
        stats = cursor.fetchone()
        logger.info(f"""
        📊 Pool-size coverage statistics:
           Total DAILY_539 draws: {stats[0]}
           Non-null sell_amount: {stats[1]} ({stats[3]}%)
           Non-null total_amount: {stats[2]} ({stats[4]}%)
        """)
        
    except Exception as e:
        logger.error(f"❌ Backfill failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    backfill_all_daily539()
