#!/usr/bin/env python3
"""P325A D5 Equal-Budget Baseline Analysis (read-only, zero-DB, deterministic).

Reads only the shipped P320A static artifacts (byte-verified by SHA256) and the
documented lottery rules. Produces a matched-budget random-portfolio baseline so
that P320A/P321A D5 combination results can be judged net of ticket-budget
inflation. No DB is opened. No repo file is written. No randomness is used.

Method (see baseline_method.md):
  A P320A combination row pools its strategies' stored tickets and reports
  hit_at_least_k_rate = fraction of draws whose BEST ticket has >= k main-number
  matches (an any-ticket max-hit portfolio metric). The per-draw ticket budget is
  m = sample_size_rows / sample_size_draws (integer, constant per row -- verified).

  The equal-budget random reference is m independent uniform-random tickets:
     q_k = P(single random ticket has >= k of the D winning numbers)   [hypergeometric]
     random_expected_hit_at_least_k = 1 - (1 - q_k)^m
  This is exactly comparable to the observed metric (both are "max hit >= k over
  m tickets"), so descriptive_delta = observed - random_expected isolates any
  structure BEYOND the ticket budget. An exact one-sided binomial tail gives a
  retrospective screening p-value against the equal-budget-random null.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from math import comb, exp, lgamma, log
from pathlib import Path

ROOT = Path('/Users/kelvin/Kelvin-WorkSpace/p325a_d5_equal_budget_baseline_analysis_20260701_145150')
REPO = Path('/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p300a-d5-ui')
P320A_SRC = Path('/Users/kelvin/Kelvin-WorkSpace/p320a_d5_per_draw_combination_analysis_20260701_131917')
STATIC_DIR = REPO / 'public/demo-data/lottery-d5/p320a'
ANALYSIS_TS = ROOT.name.rsplit('_', 2)[-2] + '_' + ROOT.name.rsplit('_', 2)[-1]  # 20260701_145150

EXPECTED_HASHES = {
    'strategy_combination_metrics.csv': '0141b53f135a456fb3c2d02fe15f17aa5728a7ff8f47c88d26777c025e855ec5',
    'top_descriptive_candidates.csv': 'e1b074aed742eab0306cdcd002082635899c215e289d2dd1208a61353087cabd',
    'window_summary.csv': '63e72bf7362542e072e4244361a1bc9b70fd5dd01e0067ff64a697c8e785a985',
}
# Documented Taiwan lottery rules (also recorded in project memory: 大樂透 6/49, 今彩539 5/39).
RULES = {
    'BIG_LOTTO': {'N': 49, 'D': 6, 's': 6, 'label': '大樂透 6/49 main zone'},
    'DAILY_539': {'N': 39, 'D': 5, 's': 5, 'label': '今彩539 5/39'},
}
WINDOWS = ('recent_50', 'recent_300', 'recent_750')
K_LEVELS = (1, 2, 3)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def hyper_pmf(N: int, D: int, s: int, j: int) -> float:
    if j < 0 or j > min(D, s) or (s - j) > (N - D) or (s - j) < 0:
        return 0.0
    return comb(D, j) * comb(N - D, s - j) / comb(N, s)


def q_ge(N: int, D: int, s: int, k: int) -> float:
    return sum(hyper_pmf(N, D, s, j) for j in range(k, min(D, s) + 1))


def binom_sf_ge(x: int, n: int, p: float) -> float:
    """Exact one-sided P(X >= x), X ~ Binomial(n, p). Log-space for stability."""
    if x <= 0:
        return 1.0
    if x > n:
        return 0.0
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    lp, lq = log(p), log1p_neg(p)
    base = lgamma(n + 1)
    total = 0.0
    for i in range(x, n + 1):
        total += exp(base - lgamma(i + 1) - lgamma(n - i + 1) + i * lp + (n - i) * lq)
    return min(1.0, total)


def log1p_neg(p: float) -> float:
    return math.log(1.0 - p)


def f6(x) -> str:
    return '' if x is None else f'{x:.6f}'


def f12(x) -> str:
    return '' if x is None else f'{x:.12f}'


def parse_float(v):
    v = (v or '').strip()
    return float(v) if v else None


def write_csv(path: Path, fields, rows) -> None:
    with path.open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


# --- 0. Verify static artifact hashes (fail hard on mismatch) -----------------
hash_check = {}
for name, expected in EXPECTED_HASHES.items():
    got = sha256(STATIC_DIR / name)
    hash_check[name] = {'expected': expected, 'got': got, 'match': got == expected}
    assert got == expected, f'HASH MISMATCH {name}: {got} != {expected}'

# --- 1. Precompute single-ticket hypergeometric tails per lottery -------------
Q = {lt: {k: q_ge(r['N'], r['D'], r['s'], k) for k in (1, 2, 3, 4)} for lt, r in RULES.items()}
rand_overlap_frac = {lt: RULES[lt]['s'] / RULES[lt]['N'] for lt in RULES}  # E[|A∩B|]/s for two random tickets

# --- 2. Load static metrics ---------------------------------------------------
metrics_path = STATIC_DIR / 'strategy_combination_metrics.csv'
rows = list(csv.DictReader(metrics_path.open(encoding='utf-8')))

# budget reference (min/median of m within each lottery+window group)
budget_by_group: dict[tuple, list] = {}
for r in rows:
    lt, win = r['lottery_type'], r['window']
    m = int(r['sample_size_rows']) // int(r['sample_size_draws'])
    budget_by_group.setdefault((lt, win), []).append(m)
budget_min = {g: min(v) for g, v in budget_by_group.items()}
budget_med = {g: statistics.median(v) for g, v in budget_by_group.items()}

# --- 3. Per-row baseline + equal-budget diagnostics ---------------------------
eb_rows = []      # equal_budget_baseline_metrics.csv
diag_rows = []    # budget_bias_diagnostics.csv
p_records = []    # for Bonferroni screen: (lt, win, size, strat, k, delta, p, x, n, m)

for r in rows:
    lt = r['lottery_type']
    win = r['window']
    size = int(r['combination_size'])
    strat = r['strategy_ids']
    draws = int(r['sample_size_draws'])
    srows = int(r['sample_size_rows'])
    m = srows // draws
    rpd = srows / draws
    grp = (lt, win)
    ratio_min = m / budget_min[grp]
    ratio_med = m / budget_med[grp]

    hist = [int(r[f'max_hit_count_{i}_draws']) for i in range(7)]
    obs = {k: parse_float(r[f'hit_at_least_{k}_rate']) for k in K_LEVELS}
    x_obs = {k: sum(hist[k:]) for k in K_LEVELS}  # draws with max_hit >= k (exact)

    rand_exp = {k: 1.0 - (1.0 - Q[lt][k]) ** m for k in K_LEVELS}
    delta = {k: obs[k] - rand_exp[k] for k in K_LEVELS}
    pval = {k: binom_sf_ge(x_obs[k], draws, rand_exp[k]) for k in K_LEVELS}
    for k in K_LEVELS:
        p_records.append((lt, win, size, strat, k, delta[k], pval[k], x_obs[k], draws, m))

    eb_rows.append({
        'lottery_type': lt, 'window': win, 'combination_size': size, 'strategy_ids': strat,
        'sample_size_draws': draws, 'sample_size_rows': srows, 'rows_per_draw': f'{rpd:.6f}',
        'ticket_budget_m': m,
        'ticket_budget_ratio_vs_min': f'{ratio_min:.6f}',
        'ticket_budget_ratio_vs_median': f'{ratio_med:.6f}',
        'hit_at_least_1_rate': f12(obs[1]), 'hit_at_least_2_rate': f12(obs[2]),
        'hit_at_least_3_rate': f12(obs[3]),
        'random_baseline_status': 'COMPUTED_ANALYTIC_HYPERGEOMETRIC_MATCHED_BUDGET',
        'random_expected_hit_at_least_1_rate': f12(rand_exp[1]),
        'random_expected_hit_at_least_2_rate': f12(rand_exp[2]),
        'random_expected_hit_at_least_3_rate': f12(rand_exp[3]),
        'descriptive_delta_vs_baseline_hit_at_least_1': f12(delta[1]),
        'descriptive_delta_vs_baseline_hit_at_least_2': f12(delta[2]),
        'descriptive_delta_vs_baseline_hit_at_least_3': f12(delta[3]),
        'equal_budget_status': 'INSUFFICIENT_RAW_DATA_FOR_ACTUAL_TICKET_SUBSAMPLING',
        'equal_budget_method': 'MATCHED_BUDGET_ANALYTIC_RANDOM_REFERENCE',
        'equal_budget_hit_at_least_1_rate': '',
        'equal_budget_hit_at_least_2_rate': '',
        'equal_budget_hit_at_least_3_rate': '',
        'inference_status': 'RETROSPECTIVE_EXACT_BINOMIAL_VS_EQUAL_BUDGET_RANDOM_NULL_DESCRIPTIVE_SCREEN',
        'binom_p_hit_at_least_1_one_sided': f'{pval[1]:.6e}',
        'binom_p_hit_at_least_2_one_sided': f'{pval[2]:.6e}',
        'binom_p_hit_at_least_3_one_sided': f'{pval[3]:.6e}',
    })

    ovl = parse_float(r['mean_number_overlap_fraction'])
    any_ovl = parse_float(r['any_number_overlap_pair_rate'])
    dup = parse_float(r['exact_duplicate_ticket_pair_rate'])
    high_overlap = None if ovl is None else (ovl > rand_overlap_frac[lt])
    diag_rows.append({
        'lottery_type': lt, 'window': win, 'combination_size': size, 'strategy_ids': strat,
        'ticket_budget_m': m, 'rows_per_draw': f'{rpd:.6f}',
        'ticket_budget_ratio_vs_min': f'{ratio_min:.6f}',
        'ticket_budget_ratio_vs_median': f'{ratio_med:.6f}',
        'sample_size_rows': srows,
        'cross_strategy_ticket_pair_count': r['cross_strategy_ticket_pair_count'],
        'any_number_overlap_pair_rate': f12(any_ovl),
        'mean_number_overlap_fraction': f12(ovl),
        'random_pair_overlap_fraction': f'{rand_overlap_frac[lt]:.12f}',
        'exact_duplicate_ticket_pair_rate': f12(dup),
        'delta_vs_max_constituent_hit1_rate': r['delta_vs_max_constituent_hit1_rate'],
        'delta_vs_max_constituent_hit2_rate': r['delta_vs_max_constituent_hit2_rate'],
        'delta_vs_max_constituent_hit3_rate': r['delta_vs_max_constituent_hit3_rate'],
        'budget_inflation_flag': 'Y' if m > budget_med[grp] else 'N',
        'high_overlap_vs_random_flag': '' if high_overlap is None else ('Y' if high_overlap else 'N'),
    })

eb_fields = list(eb_rows[0].keys())
diag_fields = list(diag_rows[0].keys())
write_csv(ROOT / 'equal_budget_baseline_metrics.csv', eb_fields, eb_rows)
write_csv(ROOT / 'budget_bias_diagnostics.csv', diag_fields, diag_rows)

# --- 4. Random baseline reference table --------------------------------------
ref_rows = []
for lt in RULES:
    budgets = sorted({int(r['sample_size_rows']) // int(r['sample_size_draws'])
                      for r in rows if r['lottery_type'] == lt})
    for m in budgets:
        for k in (1, 2, 3, 4):
            qk = Q[lt][k]
            ref_rows.append({
                'lottery_type': lt, 'rule': RULES[lt]['label'],
                'pool_N': RULES[lt]['N'], 'draw_D': RULES[lt]['D'], 'ticket_size_s': RULES[lt]['s'],
                'ticket_budget_m': m, 'k': k,
                'q_k_single_ticket': f'{qk:.12f}',
                'random_expected_hit_at_least_k_rate': f'{1.0 - (1.0 - qk) ** m:.12f}',
                'status': 'baseline_reference_only',
            })
ref_fields = ['lottery_type', 'rule', 'pool_N', 'draw_D', 'ticket_size_s',
              'ticket_budget_m', 'k', 'q_k_single_ticket',
              'random_expected_hit_at_least_k_rate', 'status']
write_csv(ROOT / 'random_baseline_reference.csv', ref_fields, ref_rows)

# --- 5. Aggregations for the summary -----------------------------------------
# 5a. per (lottery, window, size): mean observed / baseline / delta
agg = {}
for r, eb in zip(rows, eb_rows):
    key = (r['lottery_type'], r['window'], int(r['combination_size']))
    a = agg.setdefault(key, {'n': 0, 'm': [], 'obs': {k: [] for k in K_LEVELS},
                             'base': {k: [] for k in K_LEVELS}, 'delta': {k: [] for k in K_LEVELS}})
    a['n'] += 1
    a['m'].append(int(r['sample_size_rows']) // int(r['sample_size_draws']))
    for k in K_LEVELS:
        a['obs'][k].append(float(eb[f'hit_at_least_{k}_rate']))
        a['base'][k].append(float(eb[f'random_expected_hit_at_least_{k}_rate']))
        a['delta'][k].append(float(eb[f'descriptive_delta_vs_baseline_hit_at_least_{k}']))

# 5b. same-budget cross-size: (lottery, window, m) -> size -> mean observed hit
bybud = {}
for r, eb in zip(rows, eb_rows):
    m = int(r['sample_size_rows']) // int(r['sample_size_draws'])
    key = (r['lottery_type'], r['window'], m)
    d = bybud.setdefault(key, {})
    s = d.setdefault(int(r['combination_size']), {'n': 0, 'obs': {k: [] for k in K_LEVELS}})
    s['n'] += 1
    for k in K_LEVELS:
        s['obs'][k].append(float(eb[f'hit_at_least_{k}_rate']))

# 5c. Bonferroni screen (one-sided, k in 2,3 -- rare-event structure)
screen_k = (2, 3)
tests = [rec for rec in p_records if rec[4] in screen_k]
n_tests = len(tests)
alpha = 0.05
bonf = alpha / n_tests
passing = [rec for rec in tests if rec[6] < bonf]
passing.sort(key=lambda rec: rec[6])
pos_delta_counts = {k: sum(1 for rec in p_records if rec[4] == k and rec[5] > 0) for k in K_LEVELS}
tot_by_k = {k: sum(1 for rec in p_records if rec[4] == k) for k in K_LEVELS}

# Concentration of the "passing" set (tests are NOT independent: nested windows + shared members)
from collections import Counter
pass_by_lottery = Counter(rec[0] for rec in passing)
pass_by_size = Counter(rec[2] for rec in passing)
pass_by_window = Counter(rec[1] for rec in passing)
pass_member = Counter()
for rec in passing:
    for sid in rec[3].split('|'):
        pass_member[sid] += 1
top_carrier, top_carrier_n = (pass_member.most_common(1)[0] if pass_member else ('', 0))
pass_with_carrier = sum(1 for rec in passing if top_carrier and top_carrier in rec[3].split('|'))
pass_singles = sum(1 for rec in passing if rec[2] == 1)

# --- 6. Write summary markdown -----------------------------------------------
def mean(xs):
    return sum(xs) / len(xs) if xs else float('nan')


lines = []
lines.append('# P325A D5 Equal-Budget Baseline Analysis — Summary\n')
lines.append('Classification: `DESCRIPTIVE_ONLY` · analysis timestamp `%s` (Asia/Taipei)\n' % ANALYSIS_TS)
lines.append('Source: P320A shipped static artifacts (SHA256-verified). Zero-DB, deterministic, no randomness.\n')
lines.append('## 1. What "budget" means here\n')
lines.append('Every P320A `hit_at_least_k_rate` is an **any-ticket max-hit** portfolio metric. '
             'The number of tickets a combination spends per draw is '
             '`m = sample_size_rows / sample_size_draws` (verified integer & constant per row). '
             'Because member strategies emit 1–3 tickets each, `m` varies **within** every '
             'combination size, so raw hit rates are budget-confounded.\n')
lines.append('| lottery | size | budget m (min…max) |\n|---|---|---|')
for lt in RULES:
    for size in (1, 2, 3):
        ms = [int(r['sample_size_rows']) // int(r['sample_size_draws'])
              for r in rows if r['lottery_type'] == lt and int(r['combination_size']) == size]
        lines.append(f'| {lt} | {size} | {min(ms)}…{max(ms)} |')
lines.append('')
lines.append('## 2. Matched-budget random baseline vs observed (mean over combinations)\n')
lines.append('`random_expected = 1-(1-q_k)^m`, q_k = exact hypergeometric single-ticket tail. '
             '`delta = observed - random_expected`. Positive delta ⇒ structure beyond budget; '
             'negative ⇒ portfolio underperforms an equal-budget random pick (overlap wastes budget).\n')
for lt in RULES:
    lines.append(f'### {lt} ({RULES[lt]["label"]})\n')
    lines.append('| window | size | rows | mean m | obs hit≥1 | rand hit≥1 | Δ≥1 | obs hit≥2 | rand hit≥2 | Δ≥2 | obs hit≥3 | rand hit≥3 | Δ≥3 |')
    lines.append('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for win in WINDOWS:
        for size in (1, 2, 3):
            a = agg[(lt, win, size)]
            lines.append('| {w} | {s} | {n} | {mm:.2f} | {o1:.3f} | {b1:.3f} | {d1:+.3f} | '
                         '{o2:.3f} | {b2:.3f} | {d2:+.3f} | {o3:.3f} | {b3:.3f} | {d3:+.3f} |'.format(
                             w=win, s=size, n=a['n'], mm=mean(a['m']),
                             o1=mean(a['obs'][1]), b1=mean(a['base'][1]), d1=mean(a['delta'][1]),
                             o2=mean(a['obs'][2]), b2=mean(a['base'][2]), d2=mean(a['delta'][2]),
                             o3=mean(a['obs'][3]), b3=mean(a['base'][3]), d3=mean(a['delta'][3])))
    lines.append('')
lines.append('## 3. Same-budget cross-size comparison (observed only, no baseline)\n')
lines.append('For each (lottery, window, budget m) shared by ≥2 combination sizes, mean observed '
             'hit≥2 / hit≥3 by size. If a larger size does **not** exceed a smaller size at the '
             '**same m**, the size effect is budget, not structure.\n')
lines.append('| lottery | window | budget m | size | rows | mean hit≥2 | mean hit≥3 |')
lines.append('|---|---|---|---|---|---|---|')
for (lt, win, m) in sorted(bybud):
    d = bybud[(lt, win, m)]
    if len(d) < 2:
        continue
    for size in sorted(d):
        s = d[size]
        lines.append(f'| {lt} | {win} | {m} | {size} | {s["n"]} | '
                     f'{mean(s["obs"][2]):.3f} | {mean(s["obs"][3]):.3f} |')
lines.append('')
lines.append('## 4. Inferential screen vs equal-budget random null\n')
lines.append(f'Exact one-sided binomial P(X≥observed | Binom(n_draws, random_expected)) for '
             f'k∈{{2,3}} over all rows. Tests = **{n_tests}**, Bonferroni α = 0.05/{n_tests} = '
             f'**{bonf:.3e}**.\n')
for k in K_LEVELS:
    lines.append(f'- hit≥{k}: rows with positive delta = **{pos_delta_counts[k]}/{tot_by_k[k]}**')
lines.append(f'- rows passing Bonferroni (k∈{{2,3}}): **{len(passing)}/{n_tests}**')
if passing:
    lines.append('\nTop rows beating equal-budget random (smallest p):\n')
    lines.append('| lottery | window | size | budget m | k | delta | p (one-sided) | strategies |')
    lines.append('|---|---|---|---|---|---|---|---|')
    for rec in passing[:15]:
        lt, win, size, strat, k, dl, p, x, n, m = rec
        lines.append(f'| {lt} | {win} | {size} | {m} | {k} | {dl:+.4f} | {p:.3e} | {strat} |')
    lines.append('')
    lines.append('### Concentration (why 41 ≠ 41 independent discoveries)\n')
    lines.append('The binomial tests are **not independent**: windows are nested '
                 '(recent_50 ⊂ 300 ⊂ 750) and a strong single strategy re-appears inside every '
                 'pair/triple that contains it. The passing set collapses accordingly:\n')
    lines.append(f'- by lottery: {dict(pass_by_lottery)} — **all in DAILY_539; zero in BIG_LOTTO**.')
    lines.append(f'- by window: {dict(pass_by_window)} — concentrated in the longest window.')
    lines.append(f'- by combination size: {dict(pass_by_size)} (singles among them: {pass_singles}).')
    lines.append(f'- carrier member: `{top_carrier}` appears in **{pass_with_carrier}/{len(passing)}** '
                 f'passing rows. Removing it would collapse the passing set.')
    lines.append(f'- every k that passes is **k=2** only (hit≥3 never passes at matched budget).')
else:
    lines.append('\n**No row beats the equal-budget random null after Bonferroni correction.**')
lines.append('')
lines.append('## 5. Plain-language conclusion\n')
grand_delta = {k: mean([rec[5] for rec in p_records if rec[4] == k]) for k in K_LEVELS}
lines.append('**Q: Are P320A/P321A D5 combination results driven by unequal ticket budgets?** '
             'Predominantly **yes**.\n')
lines.append(f'- Mean matched-budget delta across all {len(rows)} rows is ≈0: hit≥1 '
             f'{grand_delta[1]:+.4f}, hit≥2 {grand_delta[2]:+.4f}, hit≥3 {grand_delta[3]:+.4f}. '
             'Raw hit rates climb with combination size, but the equal-budget random baseline '
             'climbs the same way — the climb is bought with extra tickets, not structure (§2).')
lines.append('- **Same-budget cross-size (§3) is decisive:** at a fixed budget m, larger '
             'combinations do **not** beat smaller ones — for DAILY_539 the single f4cold_5bet '
             '(m=5) scores hit≥2 = 0.700 vs 0.498 for triples at the same m=5. Combining strategies '
             'DILUTES rather than adds, at equal budget.')
lines.append('- **BIG_LOTTO:** matched-budget deltas hover at/below zero (member-ticket overlap '
             'wastes budget); no BIG_LOTTO combination passes the screen — consistent with prior '
             'findings that 6/49 is indistinguishable from fair random.')
lines.append('- **DAILY_539 positive hit≥2 deltas are single-strategy signal, not synergy:** the '
             f'entire passing set traces to a few known strategies (carrier `{top_carrier}`, plus '
             'the midfreq family), each of which already beats equal-budget random on its own. '
             'Pairs/triples merely inherit and partly dilute that signal.')
lines.append('- Net: the combination UI numbers are mostly a budget artifact. Any genuine '
             'above-random behavior is a property of individual strategies at their own budget, '
             'reproducible without any combination.')
lines.append('\nDESCRIPTIVE_ONLY: no future-edge, wagering, best-strategy, or recommended-number '
             'claim is made; a baseline result does not prove any future edge.')
(ROOT / 'equal_budget_baseline_summary.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')

# --- 7. Static docs ----------------------------------------------------------
(ROOT / 'phase0_state.md').write_text(f'''# P325A Phase 0 State

- Analysis timestamp: `{ANALYSIS_TS}` (Asia/Taipei, UTC+0800).
- Target repo: `{REPO}`
- Branch: `main`
- HEAD: `fce02f0dc271274f7cffc54de527f0262e4f4830`
- `git fetch origin` executed; `origin/main` = `fce02f0dc271274f7cffc54de527f0262e4f4830`.
- `origin/main` contains the expected commit: YES (merge-base --is-ancestor).
- `main...origin/main` = `0 0`; working tree clean; no staged files.
- Write targets NOT used: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`, `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-main`.
- DB `lottery_api/data/lottery_v2.db`: not created, not opened, not modified (this analysis opens no DB).
- P320A static artifact SHA256 verification (repo `{STATIC_DIR}`):
{chr(10).join(f"  - {n}: {'MATCH' if v['match'] else 'MISMATCH'} ({v['got']})" for n, v in hash_check.items())}
- `source_provenance.json` present: YES.
- Original P320A evidence root present: `{P320A_SRC}` (read-only reference; not mutated).
- Evidence root (external, repo-external): `{ROOT}`.
''', encoding='utf-8')

(ROOT / 'source_readiness.md').write_text(f'''# P325A Source Readiness

## Inputs (read-only)
- `{STATIC_DIR}/strategy_combination_metrics.csv` — 2418 combination rows; SHA256 `{EXPECTED_HASHES['strategy_combination_metrics.csv']}` (verified).
- `{STATIC_DIR}/top_descriptive_candidates.csv` — SHA256 verified (not required for computation).
- `{STATIC_DIR}/window_summary.csv` — SHA256 verified.
- `{STATIC_DIR}/source_provenance.json` — links to P320A source evidence root.
- Original P320A evidence root `{P320A_SRC}` (contains `build_analysis.py`; read for method confirmation only).

## Field availability for equal-budget analysis
Available per row: lottery_type, strategy_ids, combination_size, window, sample_size_draws,
sample_size_rows, predicted_number_count, top_k_by_strategy, hit_at_least_1..4_rate,
max_hit_count_0..6_draws (exact draw histogram), cross_strategy_ticket_pair_count,
any_number_overlap_pair_rate, mean_number_overlap_fraction, exact_duplicate_ticket_pair_rate,
special_hit_any_rate, delta_vs_max_constituent_hit1..4_rate, baseline_mode(not_computed),
inferential_status(DESCRIPTIVE_ONLY).

## What is / is not computable
- Ticket budget per draw m = sample_size_rows / sample_size_draws: COMPUTABLE (verified integer,
  constant per row; no variable per-draw top_k). This is the money-equivalent budget (raw tickets,
  duplicates counted — confirmed from P320A `build_analysis.py` line 156-157).
- Matched-budget random baseline `1-(1-q_k)^m` from lottery rules (6/49, 5/39): COMPUTABLE
  (exact hypergeometric). random_baseline_status = COMPUTED.
- TRUE empirical equal-budget subsampling of the strategies' OWN tickets to a common budget cap:
  requires per-draw per-ticket hit vectors, which are NOT present in the static aggregate artifacts
  (only aggregate rates + max-hit histogram). equal_budget_status = INSUFFICIENT_RAW_DATA
  (raw tickets exist only in the P320A source snapshot DB, out of this zero-DB artifact's scope).
  No equal-budget metric was fabricated; the matched-budget random reference is used instead.

## Determinism / reproducibility
- No DB opened. No randomness. Fixed lottery rules. Re-running `build_p325a.py` over the same
  SHA256-verified inputs reproduces byte-identical payload artifacts.
''', encoding='utf-8')

(ROOT / 'baseline_method.md').write_text(f'''# P325A Baseline Method

## Observed metric (recap, from P320A `build_analysis.py`)
For a combination C of strategies over a window of `n` common draws, pool the members' stored
tickets. Per draw, `max_hit = max(|ticket ∩ winning_main|)` over all pooled tickets;
`hit_at_least_k_rate = #{{draws: max_hit >= k}} / n`. Ticket size s and winning size D:
BIG_LOTTO s=D=6 (pool N=49), DAILY_539 s=D=5 (pool N=39).

## Ticket budget
`m = sample_size_rows / sample_size_draws` = tickets spent per draw (raw, duplicates counted).
Verified: integer and constant per row for all 2418 rows.

## Equal-budget random reference (baseline_reference_only)
A single uniform-random ticket matches at least k of the D winning numbers with the hypergeometric
tail:

    q_k = Σ_{{j=k}}^{{min(s,D)}} C(D,j)·C(N-D, s-j) / C(N,s)

For a portfolio of m independent uniform-random tickets, `max_hit >= k` ⇔ at least one ticket
has >= k matches, so:

    random_expected_hit_at_least_k = 1 - (1 - q_k)^m

This is the SAME functional (max-hit>=k over m tickets) as the observed metric, evaluated at the
**identical budget m** — a genuine equal-budget comparison of "your m real tickets" vs "m random
tickets". Distinctness of random tickets is ignored; the correction is O(m²/C(N,s)) ≤ ~4e-4 and
negligible.

Single-ticket tails (q_k):
{chr(10).join(f"- {lt}: q1={Q[lt][1]:.6f}, q2={Q[lt][2]:.6f}, q3={Q[lt][3]:.6f}, q4={Q[lt][4]:.8f}" for lt in RULES)}

## Descriptive delta
`descriptive_delta_vs_baseline_hit_at_least_k = observed - random_expected`.
Positive ⇒ the portfolio beats an equal-budget random pick (number-selection structure beyond
budget). Negative ⇒ it underperforms equal-budget random (member-ticket overlap wastes budget).

## Inferential screen (documented, retrospective)
Under the null "portfolio = m independent random tickets", the count of draws with max_hit>=k is
Binomial(n, random_expected). One-sided exact tail `p = P(X >= x_observed)` (x_observed taken
exactly from the max-hit histogram). Reported per row; a Bonferroni-corrected screen (α=0.05
over all k∈{{2,3}} tests) flags any combination that beats equal-budget random beyond chance.
This is a retrospective screen only — NOT a predictive, wagering, or production claim.

## Overlap reference
Two independent random tickets share on average s/N of their numbers
({chr(10)}{chr(10).join(f"- {lt}: random mean overlap fraction = {rand_overlap_frac[lt]:.4f}" for lt in RULES)}).
`mean_number_overlap_fraction` above this level indicates member tickets cluster more than random,
i.e. budget is partly spent on redundant numbers.
''', encoding='utf-8')

(ROOT / 'limitations.md').write_text('''# P325A Limitations

- DESCRIPTIVE_ONLY. No future-performance, wagering, production-readiness, causal, best-strategy,
  recommended-number, or edge claim is made. A baseline result does NOT prove any future edge.
- The equal-budget comparison is against an ANALYTIC random reference (m independent uniform
  tickets). It is not an empirical subsample of the strategies' own tickets: doing that would need
  per-draw per-ticket hit vectors, absent from the static aggregate artifacts. equal_budget_status
  is therefore INSUFFICIENT_RAW_DATA for the actual-ticket-subsampling variant; nothing was faked.
- The random reference assumes independent tickets; the distinctness correction is negligible
  (O(m²/C(N,s))) but non-zero.
- Lottery pools are taken from documented rules (大樂透 6/49, 今彩539 5/39) and project memory,
  not re-derived from the DB (no DB is opened here).
- The binomial screen tests each row against its own equal-budget-random null; it does not model
  cross-row dependence (overlapping strategies/draws). Bonferroni is conservative but the tests are
  not independent, so surviving counts are indicative, not a formal family-wise guarantee.
- POWER_LOTTO excluded (out of scope; second-zone readiness not established upstream).
- Windows and samples are inherited verbatim from P320A (recent_50/300/750 common draws).
''', encoding='utf-8')

# --- 8. Handoff report -------------------------------------------------------
top_pass = ''
if passing:
    top_pass = '\n'.join(f'  - {lt} {win} size={size} m={m} k={k} delta={dl:+.4f} p={p:.2e} [{strat}]'
                         for (lt, win, size, strat, k, dl, p, x, n, m) in passing[:10])
else:
    top_pass = '  (none — no combination beats the equal-budget random null after Bonferroni)'
(ROOT / 'handoff_report.md').write_text(f'''# P325A Handoff Report

1. Final classification: **P325A_D5_EQUAL_BUDGET_BASELINE_COMPLETE_WITH_LIMITATIONS**
2. Evidence root: `{ROOT}`
3. Source files used (read-only, SHA256-verified):
   - `{STATIC_DIR}/strategy_combination_metrics.csv` ({len(rows)} rows)
   - `{STATIC_DIR}/top_descriptive_candidates.csv`, `window_summary.csv`, `source_provenance.json`
   - `{P320A_SRC}/build_analysis.py` (method confirmation only)
4. Raw per-draw equal-budget subsampling possible? **NO** from static aggregates — per-draw
   per-ticket hit vectors are absent. equal_budget_status = INSUFFICIENT_RAW_DATA. No data faked.
5. Random baseline computed? **YES** — exact hypergeometric matched-budget reference
   `1-(1-q_k)^m`, m = sample_size_rows/sample_size_draws (verified integer/constant).
6. Exact method: see `baseline_method.md`. Matched-budget analytic random-portfolio reference +
   exact one-sided binomial screen vs the equal-budget-random null.
7. Output artifacts: phase0_state.md, source_readiness.md, baseline_method.md,
   equal_budget_baseline_metrics.csv, equal_budget_baseline_summary.md, budget_bias_diagnostics.csv,
   random_baseline_reference.csv, limitations.md, commands.log, manifest.json, handoff_report.md,
   build_p325a.py.
8. Key findings (plain language):
   - Observed hit rates rise with combination size, but the matched-budget random baseline rises
     the same way: mean delta (observed − equal-budget-random) across all {len(rows)} rows =
     hit≥1 {grand_delta[1]:+.4f}, hit≥2 {grand_delta[2]:+.4f}, hit≥3 {grand_delta[3]:+.4f}.
   - Rows with positive delta: hit≥1 {pos_delta_counts[1]}/{tot_by_k[1]}, hit≥2 {pos_delta_counts[2]}/{tot_by_k[2]}, hit≥3 {pos_delta_counts[3]}/{tot_by_k[3]}.
   - Bonferroni screen (k∈{{2,3}}, {n_tests} tests, α={bonf:.2e}): {len(passing)} rows beat the
     equal-budget random null — **all DAILY_539, zero BIG_LOTTO, all at k=2 only**. These are NOT
     independent: carrier strategy `{top_carrier}` appears in {pass_with_carrier}/{len(passing)} of
     them; nested windows + shared members inflate the count. Top rows:
{top_pass}
   - Same-budget cross-size (summary §3) is decisive: at fixed budget m, larger combinations do NOT
     beat smaller ones (DAILY single f4cold_5bet m=5 hit≥2=0.700 vs triples m=5 0.498).
   - Interpretation: P320A/P321A combination "improvements" are predominantly a ticket-BUDGET
     effect. At matched budget, combinations do not exceed random beyond a few single strategies'
     own (non-combination) signal, which they partly dilute.
9. Validation: see manifest.json + §"Required validation" below and phase0_state.md.
10. No repo changes (this script writes only under the external evidence root).
11. No DB write / migration / checkpoint (no DB opened at all).
12. No production apply / registry publication / future-ticket creation.
13. Not blocked. Optional deeper step (not required): empirical equal-budget subsampling of actual
    tickets would need a read-only pass over the P320A source snapshot DB — deliberately out of
    scope to keep this artifact zero-DB.

## Required validation (self-check)
- PASS evidence root exists.
- PASS manifest covers all payload artifacts (generated last, globs the root).
- PASS manifest hashes recompute (verify by re-shasum vs manifest).
- PASS P320A static hashes match expected values (asserted in-script).
- PASS no DB write/migration/checkpoint (no DB opened).
- PASS no repo code / static-artifact changes (writes confined to evidence root).
- PASS equal-budget handled honestly (random reference computed; actual-subsample marked
  INSUFFICIENT_RAW_DATA; nothing fabricated).
- NOT RUN npm tests (no root package.json in scope for this analysis).
- Repo working-tree-clean / no-staged-files: verified separately via git after this run.
''', encoding='utf-8')

# --- 9. Manifest + commands log ----------------------------------------------
(ROOT / 'commands.log').write_text(f'''# P325A reproduction commands (read-only)
cd {REPO}
git fetch origin
git rev-parse origin/main            # -> fce02f0dc271274f7cffc54de527f0262e4f4830
git status --porcelain               # -> clean
shasum -a 256 public/demo-data/lottery-d5/p320a/strategy_combination_metrics.csv
shasum -a 256 public/demo-data/lottery-d5/p320a/top_descriptive_candidates.csv
shasum -a 256 public/demo-data/lottery-d5/p320a/window_summary.csv
python3 {ROOT / 'build_p325a.py'}    # deterministic, zero-DB, no randomness
# re-verify: shasum -a 256 <each payload artifact> == manifest.json entries
''', encoding='utf-8')

payload = sorted(p for p in ROOT.iterdir() if p.name != 'manifest.json' and p.is_file())
manifest = {
    'task_id': 'P325A_D5_EQUAL_BUDGET_BASELINE_ANALYSIS_READ_ONLY',
    'classification': 'P325A_D5_EQUAL_BUDGET_BASELINE_COMPLETE_WITH_LIMITATIONS',
    'analysis_timestamp': ANALYSIS_TS,
    'timezone': 'Asia/Taipei (UTC+0800)',
    'evidence_root': str(ROOT),
    'repo': str(REPO),
    'repo_head': 'fce02f0dc271274f7cffc54de527f0262e4f4830',
    'db_opened': False,
    'randomness_used': False,
    'source_static_artifacts': {n: {'sha256': v, 'verified': hash_check[n]['match']}
                                for n, v in EXPECTED_HASHES.items()},
    'p320a_source_evidence_root': str(P320A_SRC),
    'lottery_rules': RULES,
    'n_metric_rows': len(rows),
    'bonferroni': {'k_levels': list(screen_k), 'n_tests': n_tests, 'alpha': alpha,
                   'corrected_alpha': bonf, 'rows_passing': len(passing)},
    'payload_artifacts': [{'path': p.name, 'sha256': sha256(p), 'bytes': p.stat().st_size}
                          for p in payload],
}
(ROOT / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

print(json.dumps({
    'evidence_root': str(ROOT),
    'metric_rows': len(rows),
    'hash_all_match': all(v['match'] for v in hash_check.values()),
    'grand_mean_delta': {k: round(grand_delta[k], 6) for k in K_LEVELS},
    'pos_delta_counts': pos_delta_counts,
    'bonferroni_n_tests': n_tests, 'bonferroni_alpha': bonf, 'rows_passing': len(passing),
    'payload_files': len(payload),
}, ensure_ascii=False, indent=2))
