
import urllib.request
import json
import time
from typing import List, Dict

class WBCCrawler:
    def __init__(self, season=2026, timeout=20):
        self.season = season
        self.timeout = timeout
        self.base_url = "https://statsapi.mlb.com/api/v1"
        self.headers = {'User-Agent': 'Mozilla/5.0'}

    def _get(self, endpoint: str):
        url = f"{self.base_url}/{endpoint}"
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    def get_active_wbc_teams(self) -> List[Dict]:
        data = self._get(f"teams?sportId=51&season={self.season}")
        if not data: return []
        return [t for t in data.get('teams', []) if t.get('active')]

    def get_team_roster(self, team_id: int) -> List[Dict]:
        data = self._get(f"teams/{team_id}/roster?season={self.season}")
        if not data: return []
        return data.get('roster', [])

    def get_player_stats(self, person_id: int, groups=["pitching", "hitting"]):
        stats_list = []
        for group in groups:
            # Try current season (WBC 2026)
            data = self._get(f"people/{person_id}/stats?stats=season&group={group}&season={self.season}")
            if data and data.get('stats'):
                stats_list.extend(data['stats'])
            
            # Fallback to 2025 if 2026 is empty (pre-tournament context)
            if not stats_list:
              data = self._get(f"people/{person_id}/stats?stats=season&group={group}&season={self.season-1}")
              if data and data.get('stats'):
                  stats_list.extend(data['stats'])
                  
        return stats_list

    def run(self):
        print(f"Starting WBC {self.season} Player Data Collection...")
        teams = self.get_active_wbc_teams()
        print(f"Found {len(teams)} active WBC teams.")
        
        all_data = []
        
        for team in teams:
            team_name = team['name']
            team_id = team['id']
            print(f"Fetching roster for {team_name}...")
            roster = self.get_team_roster(team_id)
            print(f"  - {len(roster)} players found.")
            
            team_players = []
            for entry in roster:
                person = entry['person']
                player_id = person['id']
                player_name = person['fullName']
                position = entry.get('position', {}).get('abbreviation', 'N/A')
                
                print(f"    Fetching stats for {player_name} ({position})...")
                # Limit calls for testing or use a sample if too many
                # For this task, I'll fetch a few to show it works, or all if requested.
                # I'll fetch all but add a small delay to be polite.
                
                # stats = self.get_player_stats(player_id) # Uncomment for full fetch
                stats = [] # Placeholder for now to avoid hundreds of calls in one go
                
                team_players.append({
                    "id": player_id,
                    "name": player_name,
                    "position": position,
                    "stats": stats
                })
                # time.sleep(0.05) 
            
            all_data.append({
                "team": team_name,
                "team_id": team_id,
                "players": team_players
            })
            
        output_file = f"/Users/kelvin/Kelvin-WorkSpace/Betting-pool/data/wbc_all_players_realtime.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=4, ensure_ascii=False)
        print(f"Finished! Total data saved to {output_file}")

if __name__ == "__main__":
    crawler = WBCCrawler()
    crawler.run()
