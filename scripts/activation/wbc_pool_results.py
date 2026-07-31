#!/usr/bin/env python3
"""
WBC Pool Results Builder
Matches wbc_2026_authoritative_snapshot.json to wbc_2026_live_scores.json
and produces a settlement records dict for use by phase2_wbc_batch_settle.py.
"""
import json
from pathlib import Path
from datetime import date, timedelta
from typing import Dict, Optional, List


CODE_TO_NAME: Dict[str, str] = {
    'AUS': 'Australia',
    'BRA': 'Brazil',
    'CAN': 'Canada',
    'COL': 'Colombia',
    'CUB': 'Cuba',
    'CZE': 'Czechia',
    'DOM': 'Dominican Republic',
    'GBR': 'Great Britain',
    'ISR': 'Israel',
    'ITA': 'Italy',
    'JPN': 'Japan',
    'KOR': 'Korea',
    'MEX': 'Mexico',
    'NED': 'Kingdom of the Netherlands',
    'NIC': 'Nicaragua',
    'PAN': 'Panama',
    'PUR': 'Puerto Rico',
    'TPE': 'Chinese Taipei',
    'USA': 'United States',
    'VEN': 'Venezuela',
}


def _build_live_lookup(live_games: List[dict]) -> Dict:
    """
    Build lookup keyed by (date_str, home_name, away_name) with ±1 day tolerance.
    Also indexes by (date, away_name, home_name) to handle orientation mismatches.
    """
    lookup = {}
    for g in live_games:
        d_obj = date.fromisoformat(g['date'])
        for delta in [-1, 0, 1]:
            dd = (d_obj + timedelta(days=delta)).isoformat()
            # Standard orientation
            k1 = (dd, g['home'], g['away'])
            if k1 not in lookup:
                lookup[k1] = g
            # Swapped orientation
            k2 = (dd, g['away'], g['home'])
            if k2 not in lookup:
                lookup[k2] = g
    return lookup


def _determine_result(snap_home_code: str, snap_away_code: str, live_game: dict) -> dict:
    """
    Determine canonical winner from the perspective of snap home/away assignment.
    Returns: {home_score, away_score, home_win, result_desc}
    """
    snap_home_name = CODE_TO_NAME.get(snap_home_code, snap_home_code)
    snap_away_name = CODE_TO_NAME.get(snap_away_code, snap_away_code)

    live_home = live_game['home']
    live_home_score = live_game['home_score']
    live_away_score = live_game['away_score']

    # Is the snap home team the same as the live home team?
    if live_home == snap_home_name:
        home_score = live_home_score
        away_score = live_away_score
    else:
        # Orientations are swapped — flip scores
        home_score = live_away_score
        away_score = live_home_score

    home_win = 1 if home_score > away_score else 0
    return {
        "home_score": home_score,
        "away_score": away_score,
        "home_win": home_win,
        "result_desc": (
            f"{snap_home_code} {home_score}-{away_score} {snap_away_code}"
        ),
        "status": live_game['status'],
    }


def build_settlement_records() -> Dict[str, dict]:
    """
    Returns dict: canonical_game_id → settlement_data
    Only includes games with status 'Final' or 'Completed Early'.
    """
    snap = json.loads(Path('data/wbc_2026_authoritative_snapshot.json').read_text())
    live_data = json.loads(Path('data/wbc_2026_live_scores.json').read_text())

    live_lookup = _build_live_lookup(live_data['games'])

    records = {}
    for g in snap['games']:
        gid = g['canonical_game_id']
        snap_date = g['date']
        home_code = g['home']
        away_code = g['away']
        hname = CODE_TO_NAME.get(home_code, home_code)
        aname = CODE_TO_NAME.get(away_code, away_code)

        d_obj = date.fromisoformat(snap_date)
        live_game = None
        for delta in [-1, 0, 1]:
            dd = (d_obj + timedelta(days=delta)).isoformat()
            k1 = (dd, hname, aname)
            k2 = (dd, aname, hname)
            if k1 in live_lookup:
                live_game = live_lookup[k1]
                break
            if k2 in live_lookup:
                live_game = live_lookup[k2]
                break

        if live_game is None:
            continue

        status = live_game.get('status', '')
        if status not in ('Final', 'Completed Early'):
            continue

        result = _determine_result(home_code, away_code, live_game)
        records[gid] = {
            "game_id": gid,
            "home_code": home_code,
            "away_code": away_code,
            "home_score": result["home_score"],
            "away_score": result["away_score"],
            "home_win": result["home_win"],
            "result_desc": result["result_desc"],
            "status": result["status"],
            "game_date": snap_date,
        }

    return records


if __name__ == "__main__":
    records = build_settlement_records()
    print(f"Settlement records built: {len(records)}/40")
    for gid in sorted(records.keys()):
        r = records[gid]
        print(f"  {gid}: {r['result_desc']}  home_win={r['home_win']}  [{r['status']}]")
