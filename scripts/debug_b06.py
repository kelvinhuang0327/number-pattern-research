import json

rows = [json.loads(l) for l in open('research/trade_ledger.jsonl') if l.strip()]

for gid in ('B06', 'C09'):
    preds = [r for r in rows if r.get('game_id') == gid and r.get('event_type') == 'prediction']
    setts = [r for r in rows if r.get('game_id') == gid and r.get('event_type') == 'settlement']
    print("=== " + gid + " PREDICTION ===")
    for p in preds:
        print("  predicted_prob  :", p.get('predicted_prob'))
        print("  decision        :", p.get('decision'))
        print("  odds            :", p.get('odds'))
        meta = p.get('metadata') or {}
        print("  meta.rec_side   :", meta.get('recommended_side'))
        print("  meta.home_win_p :", meta.get('home_win_prob'))
        print("  meta.kelly      :", meta.get('recommended_kelly_fraction'))
        print("  meta.edge       :", meta.get('edge_vs_market'))
    print("=== " + gid + " SETTLEMENT ===")
    for s in setts:
        print("  result          :", s.get('result'))
        print("  pnl             :", s.get('pnl'))
        print("  decision        :", s.get('decision'))
        smeta = s.get('metadata') or {}
        print("  meta.bet_side   :", smeta.get('recommended_side'))
        print("  settlement_result:", smeta.get('result'))
    print()
