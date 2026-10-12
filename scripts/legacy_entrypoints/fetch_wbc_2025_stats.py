
import urllib.request
import json
import time
import os
from typing import List, Dict

class Stats2025Fetcher:
    def __init__(self, target_teams=["Japan", "USA", "Chinese Taipei", "Dominican Republic"]):
        self.target_teams = target_teams
        self.roster_file = "/Users/kelvin/Kelvin-WorkSpace/Betting-pool/data/wbc_all_players_realtime.json"
        self.output_file = "/Users/kelvin/Kelvin-WorkSpace/Betting-pool/data/wbc_players_2025_stats.json"
        self.base_url = "https://statsapi.mlb.com/api/v1"
        self.headers = {'User-Agent': 'Mozilla/5.0'}

    def _get(self, endpoint: str):
        url = f"{self.base_url}/{endpoint}"
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            # Silently fail for 404s/empty stats
            return None

    def fetch_player_2025_stats(self, person_id: int, position: str):
        group = "pitching" if position == "P" else "hitting"
        # We try to get stats from MLB (sportId=1) first as it's the most likely source for 2025
        # The endpoint /people/{id}/stats?stats=season&group={group}&season=2025
        data = self._get(f"people/{person_id}/stats?stats=season&group={group}&season=2025")
        
        if data and data.get('stats'):
            for stat_entry in data['stats']:
                splits = stat_entry.get('splits', [])
                if splits:
                    return splits[0].get('stat')
        return None

    def run(self):
        if not os.path.exists(self.roster_file):
            print("Roster file not found. Please run the roster crawler first.")
            return

        with open(self.roster_file, 'r', encoding='utf-8') as f:
            roster_data = json.load(f)

        results = []
        print(f"Starting 2025 stats extraction for: {', '.join(self.target_teams)}")

        for team_entry in roster_data:
            team_name = team_entry['team']
            if team_name not in self.target_teams:
                continue

            print(f"Processing {team_name}...")
            team_results = {
                "team": team_name,
                "players_with_stats": []
            }

            for player in team_entry['players']:
                p_id = player['id']
                name = player['name']
                pos = player['position']
                
                print(f"  - Fetching 2025 stats for {name} ({pos})...", end="", flush=True)
                stats = self.fetch_player_2025_stats(p_id, pos)
                
                if stats:
                    print(" [FOUND]")
                    team_results["players_with_stats"].append({
                        "id": p_id,
                        "name": name,
                        "position": pos,
                        "stats_2025": stats
                    })
                else:
                    print(" [X]")
                
                # Small delay to avoid rate limiting
                time.sleep(0.1)

            results.append(team_results)

        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=4, ensure_ascii=False)
        
        count = sum(len(t["players_with_stats"]) for t in results)
        print(f"\nCompleted! Saved 2025 stats for {count} players to {self.output_file}")

if __name__ == "__main__":
    fetcher = Stats2025Fetcher()
    fetcher.run()
