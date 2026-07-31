"""
Phase 0 comprehensive analysis:
1. Check what market prob our bet selections were (underdogs vs favorites)
2. Check win rate by bet side  
3. Check if settlement matching logic correctly uses rec_side
"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

rows = [json.loads(l) for l in open('research/trade_ledger.jsonl') if l.strip()]
preds = {r["game_id"]: r for r in rows if r.get("event_type") == "prediction"}
setts = [r for r in rows if r.get("event_type") == "settlement"]

# Load postgame results for reference
postgame = {}
pg_path = "data/wbc_backend/reports/postgame_results.jsonl"
if os.path.exists(pg_path):
    for line in open(pg_path):
        try:
            r = json.loads(line)
            gid = r.get("game_id")
            ar = r.get("actual_result", {})
            if gid and ar and ar.get("home_score") is not None:
                postgame[gid] = ar
        except:
            pass

print("=" * 65)
print("SETTLEMENT WIN/LOSS BREAKDOWN")
print("=" * 65)
print(f"{'GID':5} {'pred_prob':10} {'rec_side':9} {'bet_odds':10} {'actual':8} {'correct_dir':11} {'result':6}")
print("-" * 65)

wins = 0
losses = 0
total_bet_market_prob = 0
bet_count = 0

home_wins = 0
home_losses = 0
away_wins = 0
away_losses = 0

for s in sorted(setts, key=lambda x: x.get('game_id', '')):
    gid = s.get('game_id', '')
    p = preds.get(gid, {})
    pg = postgame.get(gid, {})
    
    pred_prob = float(p.get('predicted_prob') or 0.5)
    smeta = s.get('metadata') or {}
    rec_side = (p.get('metadata') or {}).get('recommended_side', '?')
    
    odds = p.get('odds', {})
    home_ml = odds.get('home_ml', 0)
    away_ml = odds.get('away_ml', 0)
    
    # Market prob for bet selection
    def american_to_prob(ml):
        if not ml: return 0.5
        if ml > 0: return 100 / (ml + 100)
        return abs(ml) / (abs(ml) + 100)
    
    if rec_side == 'home':
        bet_market_prob = american_to_prob(home_ml)
        bet_odds_str = str(home_ml)
    elif rec_side == 'away':
        bet_market_prob = american_to_prob(away_ml)
        bet_odds_str = str(away_ml)
    else:
        bet_market_prob = 0.5
        bet_odds_str = "?"
    
    # Actual result
    actual_hw = bool(pg.get('home_win', False)) if pg else None
    correct_dir = None
    if actual_hw is not None:
        correct_dir = (pred_prob > 0.5) == actual_hw

    result = s.get('result', '?')
    win = result == 'win'
    
    if win: wins += 1
    else: losses += 1
    
    if rec_side == 'home':
        if win: home_wins += 1
        else: home_losses += 1
    elif rec_side == 'away':
        if win: away_wins += 1
        else: away_losses += 1
    
    total_bet_market_prob += bet_market_prob
    bet_count += 1
    
    print(f"{gid:5} {pred_prob:10.4f} {rec_side:9} {bet_odds_str:10} "
          f"{str(actual_hw):8} {str(correct_dir):11} {result:6}")

print("=" * 65)
print(f"Total: {wins}W / {losses}L = {wins/(wins+losses):.1%}")
print(f"HOME bets: {home_wins}W / {home_losses}L = {home_wins/(home_wins+home_losses):.1%}" if (home_wins+home_losses) > 0 else "HOME: n/a")
print(f"AWAY bets: {away_wins}W / {away_losses}L = {away_wins/(away_wins+away_losses):.1%}" if (away_wins+away_losses) > 0 else "AWAY: n/a")
avg_market_prob = total_bet_market_prob / bet_count if bet_count else 0
print(f"\nAvg market prob for our bet selections: {avg_market_prob:.1%}")
print(f"  (If ~50%, betting favorites. If ~20-30%, betting dogs)")
print(f"  Expected win rate given avg market prob: {avg_market_prob:.1%}")
print(f"  Actual win rate: {wins/(wins+losses):.1%}")

# Is it systematically below or above market expectations?
print("\n--- DIRECTION ACCURACY ---")
dir_correct = sum(1 for s in setts 
                  if postgame.get(s['game_id']) 
                  and (float(preds.get(s['game_id'],{}).get('predicted_prob',0.5)) > 0.5) 
                  == bool(postgame[s['game_id']].get('home_win')))
dir_total = sum(1 for s in setts if postgame.get(s['game_id']))
print(f"Model direction correct: {dir_correct}/{dir_total} = {dir_correct/dir_total:.1%}" if dir_total else "n/a")
