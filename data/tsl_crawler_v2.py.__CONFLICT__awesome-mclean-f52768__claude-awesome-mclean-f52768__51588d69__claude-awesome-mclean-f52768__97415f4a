import urllib.request
import json
import ssl
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class TSLOdds:
    match_id: str
    home_team: str
    away_team: str
    game_time: str
    markets: Dict[str, Dict]

class TSLCrawlerV2:
    def __init__(self, use_mock: bool = False):
        self.base_url = "https://www.sportslottery.com.tw/api/v1"
        self.use_mock = use_mock
        # Using a more robust User-Agent and headers to bypass simple WAF
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://www.sportslottery.com.tw",
            "Referer": "https://www.sportslottery.com.tw/zh-tw/game/pre-match?sportId=1",
            "Sec-Ch-Ua": "\"Not_A Brand\";v=\"8\", \"Chromium\";v=\"120\", \"Google Chrome\";v=\"120\"",
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": "\"Windows\"",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin"
        }
        
    def fetch_baseball_games(self) -> List[Dict]:
        if self.use_mock:
            return self._get_mock_data()

        endpoint = f"{self.base_url}/game/list"
        payload = {
            "sportId": "1",
            "marketGroupId": "0",
            "lan": "zh-TW"
        }
        
        data = json.dumps(payload).encode('utf-8')
        
        # Create unverified context to match requests behavior but with urllib
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(
            endpoint, 
            data=data, 
            headers=self.headers, 
            method='POST'
        )
        
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result.get("data", [])
        except Exception as e:
            print(f"Error fetching TSL data: {e}")
            return []
            
    def _get_mock_data(self) -> List[Dict]:
        return []

if __name__ == "__main__":
    crawler = TSLCrawlerV2(use_mock=False)
    games = crawler.fetch_baseball_games()
    print(f"Fetched {len(games)} games.")
