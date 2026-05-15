import json, os, sys

def evaluate_status(s):
    e150 = s.get('edge_150p') or 0
    e500 = s.get('edge_500p') or 0
    e1500 = s.get('edge_1500p') or 0
    perm_p = s.get('perm_p')
    mcnemar_p = s.get('mcnemar_p')
    sharpe = s.get('sharpe') or 0
    
    all_positive = e150 > 0 and e500 > 0 and e1500 > 0
    perm_ok = perm_p is not None and perm_p < 0.05
    mcn_ok = mcnemar_p is not None and mcnemar_p < 0.05
    
    if all_positive and perm_ok and mcn_ok and sharpe > 0:
        return 'VALIDATED'
    elif perm_ok and sharpe > 0:
        return 'WATCH'
    elif perm_p is not None and perm_p >= 0.05:
        return 'REJECT'
    else:
        return 'WATCH'

base = 'lottery_api/data'
for lt in ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO']:
    f = os.path.join(base, 'strategy_states_%s.json' % lt)
    d = json.load(open(f))
    print('=== %s ===' % lt)
    for name, s in sorted(d.items()):
        current = s.get('validated_status', '        current = s.get('validated_status', '        current = s.get('vali==        current = sMAT        current = s.ge.g        current = s.get('vas.get('m        current = s.get('validateur        current = s.get('validated_n=        current = s.get('va c        current = s.get('validate          current = s.get('vaone else -1,
            mcn if mcn is not None else -1))
