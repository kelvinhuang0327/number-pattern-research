"""
Taiwan Lottery JSON API fetcher.
Fetches draw results from api.taiwanlottery.com for:
  BIG_LOTTO (大樂透), POWER_LOTTO (威力彩), DAILY_539 (今彩539)

API base: https://api.taiwanlottery.com/TLCAPIWeB
Endpoints:
  /Lottery/Daily539Result       → DAILY_539
  /Lottery/Lotto649Result       → BIG_LOTTO
  /Lottery/SuperLotto638Result  → POWER_LOTTO

Query params: pageNum, pageSize, startMonth (YYYY-MM), endMonth (YYYY-MM)

All returned dicts conform to internal DB schema:
  { lotteryType, draw, date, numbers, special }
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE      = "https://api.taiwanlottery.com/TLCAPIWeB"
FETCH_TIMEOUT = 15
RETRY_MAX     = 3
RETRY_DELAY   = 1.5
POLITE_DELAY  = 0.8

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json",
    "Origin":          "https://www.taiwanlottery.com",
    "Referer":         "https://www.taiwanlottery.com/",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8",
}

SOURCE_CONFIG: Dict[str, Dict[str, Any]] = {
    "BIG_LOTTO": {
        "endpoint":      "/Lottery/Lotto649Result",
        "result_key":    "lotto649Res",
        "numbers_count": 6,
        "has_special":   True,
        "label":         "大樂透",
    },
    "POWER_LOTTO": {
        "endpoint":      "/Lottery/SuperLotto638Result",
        "result_key":    "superLotto638Res",
        "numbers_count": 6,
        "has_special":   True,
        "label":         "威力彩",
    },
    "DAILY_539": {
        "endpoint":      "/Lottery/Daily539Result",
        "result_key":    "daily539Res",
        "numbers_count": 5,
        "has_special":   False,
        "label":         "今彩539",
    },
}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _call_api(endpoint: str, params: Dict) -> Optional[Dict]:
    """Call API endpoint with retry logic. Returns parsed JSON content or None."""
    try:
        import requests
    except ImportError:
        logger.error("❌ 'requests' library not installed.")
        return None

    url = API_BASE + endpoint
    for attempt in range(1, RETRY_MAX + 1):
        try:
            resp = requests.get(url, params=params, headers=HEADERS,
                                timeout=FETCH_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("rtCode") == 0:
                    return data.get("content", {})
                else:
                    logger.warning(f"⚠️  API error rtCode={data.get('rtCode')}: {data.get('rtMsg')}")
                    return None
            else:
                logger.warning(f"⚠️  HTTP {resp.status_code} (attempt {attempt})")
        except Exception as e:
            logger.warning(f"⚠️  Fetch error attempt {attempt}: {e}")

        if attempt < RETRY_MAX:
            time.sleep(RETRY_DELAY * attempt)

    logger.error(f"❌ Failed to call {url} after {RETRY_MAX} attempts")
    return None


def _month_range_for_recent(months_back: int = 2) -> tuple:
    """Return (startMonth, endMonth) strings covering the last N months."""
    now = datetime.now()
    start = now - timedelta(days=30 * months_back)
    return start.strftime("%Y-%m"), now.strftime("%Y-%m")


def _parse_row(lottery_type: str, config: Dict, row: Dict) -> Optional[Dict]:
    """Parse one API result row into internal DB schema dict."""
    try:
        period      = str(row["period"])
        date_raw    = row["lotteryDate"][:10].replace("-", "/")   # "2026-03-23" → "2026/03/23"
        draw_nums   = row.get("drawNumberSize", [])

        if config["has_special"]:
            # Last element is special number
            numbers = sorted(draw_nums[:config["numbers_count"]])
            special = int(draw_nums[config["numbers_count"]]) if len(draw_nums) > config["numbers_count"] else 0
        else:
            numbers = sorted(draw_nums[:config["numbers_count"]])
            special = 0

        if len(numbers) < config["numbers_count"]:
            logger.debug(f"Skip row {period}: insufficient numbers ({len(numbers)})")
            return None

        return {
            "lotteryType": lottery_type,
            "draw":        period,
            "date":        date_raw,
            "numbers":     numbers,
            "special":     special,
        }
    except Exception as e:
        logger.warning(f"⚠️  Failed to parse row: {e} — {row}")
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class TaiwanLotteryFetcher:
    """
    Fetches official draw data from Taiwan Lottery JSON API.

    Usage:
        fetcher = TaiwanLotteryFetcher()
        latest = fetcher.fetch_latest("BIG_LOTTO")
        draws  = fetcher.fetch_recent("DAILY_539", max_draws=10)
    """

    def fetch_latest(self, lottery_type: str) -> Optional[Dict]:
        """Fetch the single latest draw for the given lottery type."""
        draws = self.fetch_recent(lottery_type, max_draws=1)
        return draws[0] if draws else None

    def fetch_recent(self, lottery_type: str, max_draws: int = 30) -> List[Dict]:
        """
        Fetch the most recent N draws.
        Returns list of normalized draw dicts, newest first.
        """
        config = SOURCE_CONFIG.get(lottery_type)
        if not config:
            logger.error(f"Unknown lottery type: {lottery_type}")
            return []

        # Try current month first; extend back if needed
        months_back = 1
        results = []
        while len(results) < max_draws and months_back <= 6:
            start_m, end_m = _month_range_for_recent(months_back)
            params = {
                "pageNum":    1,
                "pageSize":   max(max_draws, 50),
                "startMonth": start_m,
                "endMonth":   end_m,
            }
            logger.info(f"🌐 Fetching {config['label']} {start_m}~{end_m} "
                        f"(max={params['pageSize']})")

            content = _call_api(config["endpoint"], params)
            if not content:
                break

            rows = content.get(config["result_key"]) or []
            parsed = []
            for row in rows:
                d = _parse_row(lottery_type, config, row)
                if d:
                    parsed.append(d)

            results = parsed  # already newest-first from API
            if len(results) >= max_draws:
                break
            months_back += 1

        results = results[:max_draws]
        logger.info(f"✅ Fetched {len(results)} {config['label']} draws")
        return results

    def fetch_all_supported(self) -> Dict[str, Optional[Dict]]:
        """Fetch the latest draw for all 3 supported lottery types."""
        out = {}
        for lt in ["BIG_LOTTO", "POWER_LOTTO", "DAILY_539"]:
            out[lt] = self.fetch_latest(lt)
            time.sleep(POLITE_DELAY)
        return out

    def check_source(self, lottery_type: str) -> Dict:
        """Test connectivity and parse for a given lottery type."""
        config = SOURCE_CONFIG.get(lottery_type)
        if not config:
            return {"ok": False, "error": f"Unknown type: {lottery_type}"}

        draws = self.fetch_recent(lottery_type, max_draws=5)
        if not draws:
            return {
                "ok":    False,
                "error": "API returned no draws. Check network or API endpoint.",
            }

        return {
            "ok":           True,
            "parsed_count": len(draws),
            "latest_draw":  draws[0],
        }


# Module-level singleton
fetcher = TaiwanLotteryFetcher()
