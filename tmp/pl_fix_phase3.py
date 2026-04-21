#!/usr/bin/env python3
"""
Fix Phase 3 (H-PL-02) stats with correct chi2_sf (Wilson-Hilferty approximation).
Re-runs phase3_hpl02 and updates h_pl_02_validation.json and integrated report.
Does NOT re-write lessons (already written as L109, L110).
"""
import sys, os, json, math
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew')

# Monkey-patch: import the fixed phase3 function
exec(open('/Users/kelvin/Kelvin-WorkSpace/LotteryNew/tmp/pl_deep_validation.py').read(), globals())

if __name__ == '__main__':
    # Load data
    draws = load_draws()
    bt_records = load_backtest()
    print(f'Loaded {len(draws)} draws, {len(bt_records)} backtest records')

    # Re-run Phase 3 only
    p3_new = phase3_hpl02(draws, bt_records)
    print(f'\n  CORRECTED h_pl_02_validation.json saved')
    print(f'  chi2={p3_new["chi2"]}, chi2_p={p3_new["chi2_p"]}')
    print(f'  ljung_box_q={p3_new["ljung_box_q"]}, ljung_box_p={p3_new["ljung_box_p"]}')
    print(f'  structural_bias={p3_new["structural_bias"]}, verdict={p3_new["verdict"]}')

    # Update integrated report with correct Phase 3 stats (keep Phase 2/4 as-is)
    rpt_path = os.path.join(DATA_DIR, 'power_lotto_deep_validation_2026_04_19.json')
    with open(rpt_path) as f:
        rpt = json.load(f)

    rpt['h_pl_02_mod7']['structural_bias'] = p3_new.get('structural_bias', False)
    rpt['h_pl_02_mod7']['chi2_p'] = p3_new.get('chi2_p')
    rpt['h_pl_02_mod7']['ljung_box_p'] = p3_new.get('ljung_box_p')
    rpt['h_pl_02_mod7']['perm_p'] = p3_new.get('perm_p')
    rpt['h_pl_02_mod7']['window_600p'] = p3_new.get('window_600p')
    rpt['h_pl_02_mod7']['verdict'] = p3_new.get('verdict')

    with open(rpt_path, 'w') as f:
        json.dump(rpt, f, indent=2, ensure_ascii=False)
    print(f'\n  Updated integrated report: {rpt_path}')

    # Also fix lessons.md L110 to show correct stats if needed
    # L110 notes "Ljung-Box p=0.0000" — check if it was already written
    lessons_path = os.path.join(MEM_DIR, 'lessons.md')
    with open(lessons_path) as f:
        content = f.read()

    if 'Ljung-Box p=0.0000' in content:
        correct = f'Ljung-Box p={p3_new["ljung_box_p"]:.4f}'
        content = content.replace('Ljung-Box p=0.0000', correct)
        with open(lessons_path, 'w') as f:
            f.write(content)
        print(f'  Fixed lessons.md: Ljung-Box p -> {correct}')
    else:
        print('  lessons.md already correct (no Ljung-Box p=0.0000 found)')
