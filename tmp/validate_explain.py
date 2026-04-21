import sys, json, os
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')
os.chdir('/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')
from database import DatabaseManager
from engine.strategy_coordinator import coordinator_predict, get_last_explanation
db = DatabaseManager(db_path='data/lottery_v2.db')
samples = {}
for lt in ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO']:
    history = sorted(db.get_all_draws(lt), key=lambda x: (x.get('date',''), x.get('draw','')))
    bets, desc = coordinator_predict(lt, history, n_bets=3, mode='direct')
    exp = get_last_explanation()
    samples[lt] = exp
    lr = exp.get('learning', {})
    qr = exp.get('quality', {})
    base = exp.get('base', {})
    print('%s strat=%s vs=%s gate=%s lr_rank=%s qlabel=%s cs=%s fr=%s' % (
        lt, exp.get('selected_strategy','?'), exp.get('validated_status','?'),
        lr.get('gate','?'), lr.get('ranking_changed','?'),
        qr.get('quality_label','?'), base.get('composite_score','N/A'),
        bool(exp.get('final_reason'))))
os.chdir('/Users/kelvin/Kelvin-WorkSpace/LotteryNew')
os.makedirs('docs', exist_ok=True)
with open('docs/sample_explanations.json', 'w', encoding='utf-8') as f:
    json.dump(samples, f, indent=2, ensure_ascii=False, default=str)
print('DONE: saved docs/sample_explanations.json')
