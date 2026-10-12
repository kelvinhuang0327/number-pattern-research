"""
Taiwan Sports Lottery (TSL) V3 Crawler.
Fetches real-time odds for Baseball matches.
"""
import requests
import json
import time
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class TSLOdds:
    match_id: str
    home_team: str
    away_team: str
    game_time: str
    markets: Dict[str, Dict]

class TSLCrawler:
    def __init__(self, use_mock: bool = False):
        self.base_url = "https://www.sportslottery.com.tw/api/v1"
        self.use_mock = use_mock
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.sportslottery.com.tw",
            "Referer": "https://www.sportslottery.com.tw/zh-tw/game/pre-match?sportId=1"
        }

    def fetch_baseball_games(self) -> List[Dict]:
        """Fetch list of all baseball games and their odds."""
        if self.use_mock:
            return self._get_mock_data()

        endpoint = f"{self.base_url}/game/list"
        # sportId 1 = Baseball (MLB/WBC/NPB/CPBL)
        payload = {
            "sportId": "1",
            "marketGroupId": "0", # 0 for all basic markets
            "lan": "zh-TW"
        }
        
        try:
            # We use verify=False to bypass SSL issues in limited environments
            # In a real production environment, this should be True if certs are correctly managed.
            response = requests.post(endpoint, json=payload, headers=self.headers, timeout=10, verify=False)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except Exception as e:
            print(f"Error fetching TSL data: {e}")
            return []

    def parse_wbc_match(self, home_team: str, away_team: str) -> Optional[TSLOdds]:
        """Find a specific match and parse its odds."""
        games = self.fetch_baseball_games()
        for game in games:
            # Simple name matching logic (TSL uses Chinese names)
            g_home = game.get("homeTeamName", "")
            g_away = game.get("awayTeamName", "")
            
            # Check if names match (could be partial or mapping)
            if (home_team in g_home and away_team in g_away) or \
               (away_team in g_home and home_team in g_away):
                return self._process_game_odds(game)
        return None

    def _process_game_odds(self, game: Dict) -> TSLOdds:
        """Extract ML, RL, OU, OE, F5, TT odds from game data structure."""
        markets = {}
        # TSL V3 structure: markets are in game['markets'] list
        for m in game.get("markets", []):
            code = m.get("marketCode") # e.g., 'MNL' for ML, 'HDC' for RL, 'OU' for OU
            market_type = self._map_market_type(code)
            if not market_type:
                continue
                
            outcomes = {}
            for o in m.get("outcomes", []):
                side = o.get("outcomeName")
                price = o.get("odds")
                line = o.get("specialBetValue") # for RL/OU
                outcomes[side] = {
                    "price": float(price) if price else 1.0,
                    "line": float(line) if line else None
                }
            markets[market_type] = outcomes

        return TSLOdds(
            match_id=str(game.get("gameId")),
            home_team=game.get("homeTeamName"),
            away_team=game.get("awayTeamName"),
            game_time=game.get("gameTime"),
            markets=markets
        )

    def _map_market_type(self, code: str) -> Optional[str]:
        mapping = {
            "MNL": "ML", # 不讓分
            "HDC": "RL", # 讓分
            "OU":  "OU", # 大小
            "OE":  "OE", # 單雙
            "FMNL": "F5", # 前五局不讓分
            "TTO": "TT", # 隊伍總分
        }
        return mapping.get(code)

    def _get_mock_data(self) -> List[Dict]:
        """Provide mock data for testing."""
        return [
            {
                "gameId": 12345,
                "homeTeamName": "日本",
                "awayTeamName": "中華台北",
                "gameTime": "2026-03-07T19:00:00",
                "markets": [
                    {
                        "marketCode": "MNL",
                        "outcomes": [
                            {"outcomeName": "日本", "odds": "1.42"},
                            {"outcomeName": "中華台北", "odds": "3.10"}
                        ]
                    },
                    {
                        "marketCode": "OU",
                        "outcomes": [
                            {"outcomeName": "大", "odds": "1.85", "specialBetValue": "7.5"},
                            {"outcomeName": "小", "odds": "1.95", "specialBetValue": "7.5"}
                        ]
                    }
                ]
            }
        ]

if __name__ == "__main__":
    crawler = TSLCrawler(use_mock=True)
    games = crawler.fetch_baseball_games()
    print(f"Fetched {len(games)} games (Mock).")
    match = crawler.parse_wbc_match("日本", "中華台北")
    if match:
        print(f"Match found: {match.home_team} vs {match.away_team}")
        print(f"Odds: {json.dumps(match.markets, indent=2, ensure_ascii=False)}")
