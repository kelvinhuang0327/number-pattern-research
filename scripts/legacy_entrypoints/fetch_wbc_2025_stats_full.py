
import urllib.request
import json
import time
import os
from typing import List, Dict

class Stats2025Fetcher_All:
    def __init__(self):
        # Major WBC Teams from the roster
        self.target_teams = [
            "United States", "Japan", "Dominican Republic", "Chinese Taipei", 
            "Venezuela", "Puerto Rico", "Mexico", "Korea", "Kingdom of the Netherlands",
            "Canada", "Australia", "Cuba", "Panama", "Colombia", "Israel", "Italy",
            "Great Britain", "Czechia", "Nicaragua", "Brazil"
        ]
        self.roster_file = "/Users/kelvin/Kelvin-WorkSpace/Betting-pool/data/wbc_all_players_realtime.json"
        self.output_file = "/Users/kelvin/Kelvin-WorkSpace/Betting-pool/data/wbc_players_2025_stats.json"
        self.base_url = "https://statsapi.mlb.com/api/v1"
        self.headers = {'User-Agent': 'Mozilla/5.0'}

    def _get(self, endpoint: str):
        url = f"{self.base_url}/{endpoint}"
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception:
            return None

    def fetch_player_2025_stats(self, person_id: int, position: str):
        groups = ["pitching", "hitting"]
        result = {}
        for group in groups:
          data = self._get(f"people/{person_id}/stats?stats=season&group={group}&season=2025")
          if data and data.get('stats'):
            for stat_entry in data['stats']:
                splits = stat_entry.get('splits', [])
                if splits:
                    result[group] = splits[0].get('stat')
        return result if result else None

    def run(self):
        with open(self.roster_file, 'r', encoding='utf-8') as f:
            roster_data = json.load(f)

        # Load existing results to support incremental updates
        existing = {}
        if os.path.exists(self.output_file):
            try:
                with open(self.output_file, 'r', encoding='utf-8') as f:
                    for t in json.load(f):
                        if len(t.get("players_with_stats", [])) > 0:
                            existing[t["team"]] = t
            except Exception:
                pass

        results = []
        print(f"Starting 2025 stats extraction for ALL major teams...")

        for team_entry in roster_data:
            team_name = team_entry['team']
            if team_name not in self.target_teams: continue

            # Skip teams already fetched with reasonable data
            if team_name in existing and len(existing[team_name]["players_with_stats"]) >= 1:
                print(f"Skipping {team_name} (already have {len(existing[team_name]['players_with_stats'])} players)")
                results.append(existing[team_name])
                continue

            print(f"Processing {team_name}...")
            team_results = {"team": team_name, "players_with_stats": []}

            for player in team_entry['players']:
                p_id, name, pos = player['id'], player['name'], player['position']
                stats = self.fetch_player_2025_stats(p_id, pos)
                
                if stats:
                    team_results["players_with_stats"].append({
                        "id": p_id, "name": name, "position": pos, "stats_2025": stats
                    })
                time.sleep(0.05) 

            results.append(team_results)

            # Save incrementally after each team
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=4, ensure_ascii=False)
            print(f"  -> Saved {len(team_results['players_with_stats'])} players for {team_name}")

        count = sum(len(t["players_with_stats"]) for t in results)
        print(f"\nCompleted! Saved 2025 stats for {count} players to {self.output_file}")

if __name__ == "__main__":
    Stats2025Fetcher_All().run()
