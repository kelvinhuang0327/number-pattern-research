import sys
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')
from engine.actionable_intelligence import get_actionable_summary

summary = get_actionable_summary()
for lt, entry in summary.items():
    sig = entry.get('signals_summary', {}) or {}
    conf = entry.get('confidence', {}) or {}
    print(f'=== {lt} ===')
    print(f'  best={sig.get("best_strategy")}  validated_status={sig.get("best_validated_status")}')
    score = sig.get("best_confidence_score")
    adj = sig.get("best_adjusted_mcnemar")
    print(f'  best_tier={sig.get("best_confidence_tier")}  '
          f'score={score and round(score,3)}  '
          f'adj_mc={adj and round(adj,3)}')
    print(f'  promotable_count={sig.get("promotable_count")}')
    for p in (conf.get('promotable') or [])[:3]:
        print(f'    PROMO: {p["name"]} score={p["confidence_score"]:.3f} '
              f'tier={p["confidence_tier"]} adj_mc={p["adjusted_mcnemar_p"]:.3f}')
    r11 = [ins for ins in entry.get('insights', []) if ins.get('code') == 'R11_PROMOTABLE']
    for ins in r11:
        print(f'    R11: {ins["message"]}')
print('=== OK ===')
