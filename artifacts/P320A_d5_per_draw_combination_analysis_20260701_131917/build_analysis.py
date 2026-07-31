#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/kelvin/Kelvin-WorkSpace/p320a_d5_per_draw_combination_analysis_20260701_131917')
REPO = Path('/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p300a-d5-ui')
DB = REPO / 'backups/p213l_lottery_v2_backup_20260605_20260605_151715.db'
IDENTITY = REPO / 'outputs/research/p273a_distinct_ticket_identity_20260615.json'
WINDOWS = (50, 300, 750)
LOTTERIES = ('BIG_LOTTO', 'DAILY_539')
MAIN_COUNTS = {'BIG_LOTTO': 6, 'DAILY_539': 5}
CLASSIFICATION = 'DESCRIPTIVE_ONLY'


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def rate(n: int, d: int) -> str:
    return f'{n / d:.12f}' if d else ''


def mean(values: list[float]) -> str:
    return f'{sum(values) / len(values):.12f}' if values else ''


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


identity_doc = json.loads(IDENTITY.read_text(encoding='utf-8'))
identity_cells = {
    (c['lottery_type'], c['strategy_id']): c
    for c in identity_doc['cells'] if c['lottery_type'] in LOTTERIES
}
strategies = {
    lt: sorted(sid for (game, sid) in identity_cells if game == lt)
    for lt in LOTTERIES
}

sidecars = [Path(str(DB) + suffix) for suffix in ('-wal', '-shm', '-journal')]
sidecars_before = {str(p): {'exists': p.exists(), 'size': p.stat().st_size if p.exists() else None,
                            'mtime_ns': p.stat().st_mtime_ns if p.exists() else None} for p in sidecars}
db_hash_before = sha256(DB)
db_stat_before = {'size': DB.stat().st_size, 'mtime_ns': DB.stat().st_mtime_ns}

uri = f'file:{DB}?mode=ro&immutable=1'
con = sqlite3.connect(uri, uri=True)
con.row_factory = sqlite3.Row
con.execute('PRAGMA query_only=ON')
assert con.execute('PRAGMA query_only').fetchone()[0] == 1
columns = [r['name'] for r in con.execute('PRAGMA table_info(strategy_prediction_replays)')]
required = {'lottery_type', 'target_draw', 'strategy_id', 'bet_index', 'predicted_numbers',
            'predicted_special', 'actual_numbers', 'actual_special', 'replay_status', 'dry_run'}
assert required <= set(columns), sorted(required - set(columns))

rows_by_key: dict[tuple[str, str, str], list[tuple[int, ...]]] = defaultdict(list)
actual_by_draw: dict[tuple[str, str], tuple[int, ...]] = {}
special_by_draw: dict[tuple[str, str], int | None] = {}
row_count_by_lottery = Counter()
query = '''
SELECT lottery_type, target_draw, strategy_id, bet_index,
       predicted_numbers, predicted_special, actual_numbers, actual_special
FROM strategy_prediction_replays
WHERE lottery_type IN ('BIG_LOTTO','DAILY_539')
  AND replay_status='PREDICTED' AND dry_run=0
ORDER BY lottery_type, CAST(target_draw AS INTEGER) DESC, strategy_id, bet_index
'''
for row in con.execute(query):
    lt, draw, sid = row['lottery_type'], str(row['target_draw']), row['strategy_id']
    if sid not in strategies[lt]:
        continue
    pred = tuple(sorted(json.loads(row['predicted_numbers'])))
    actual = tuple(sorted(json.loads(row['actual_numbers'])))
    assert len(pred) == MAIN_COUNTS[lt] and len(set(pred)) == len(pred)
    assert len(actual) == MAIN_COUNTS[lt] and len(set(actual)) == len(actual)
    key = (lt, draw)
    if key in actual_by_draw:
        assert actual_by_draw[key] == actual
        assert special_by_draw[key] == row['actual_special']
    else:
        actual_by_draw[key] = actual
        special_by_draw[key] = row['actual_special']
    rows_by_key[(lt, sid, draw)].append(pred)
    row_count_by_lottery[lt] += 1
con.close()

# Exact alignment of the committed 750-draw ticket identities with this DB snapshot.
identity_checked_draws = 0
identity_checked_tickets = 0
for (lt, sid), cell in identity_cells.items():
    for draw in cell['supported_draws']:
        expected = sorted(tuple(g['canonical_ticket_content']['main_numbers'])
                          for g in draw['canonical_ticket_groups'])
        observed = sorted(rows_by_key[(lt, sid, str(draw['target_draw']))])
        assert expected == observed, (lt, sid, draw['target_draw'])
        identity_checked_draws += 1
        identity_checked_tickets += len(expected)

common_draws: dict[str, list[str]] = {}
for lt in LOTTERIES:
    draw_sets = [{draw for (game, sid, draw) in rows_by_key if game == lt and sid == strategy}
                 for strategy in strategies[lt]]
    common = set.intersection(*draw_sets)
    common_draws[lt] = sorted(common, key=int, reverse=True)
    assert len(common_draws[lt]) >= 750

metrics: list[dict] = []
single_lookup: dict[tuple[str, str, int], dict] = {}
dist_columns = [f'max_hit_count_{i}_draws' for i in range(7)]
fields = [
    'classification', 'lottery_type', 'strategy_ids', 'combination_size', 'window',
    'latest_target_draw', 'earliest_target_draw', 'sample_size_draws', 'sample_size_rows',
    'top_k_by_strategy', 'predicted_number_count', 'hit_at_least_1_rate',
    'hit_at_least_2_rate', 'hit_at_least_3_rate', 'hit_at_least_4_rate',
    *dist_columns, 'cross_strategy_ticket_pair_count', 'any_number_overlap_pair_rate',
    'mean_number_overlap_fraction', 'exact_duplicate_ticket_pair_rate',
    'special_zone_status', 'special_hit_any_rate', 'baseline_mode', 'inferential_status',
    'readiness_status', 'exclusion_reason', 'delta_vs_max_constituent_hit1_rate',
    'delta_vs_max_constituent_hit2_rate', 'delta_vs_max_constituent_hit3_rate',
    'delta_vs_max_constituent_hit4_rate',
]

for lt in LOTTERIES:
    for size in (1, 2, 3):
        for combo in itertools.combinations(strategies[lt], size):
            for window in WINDOWS:
                draws = common_draws[lt][:window]
                hit_dist = Counter()
                special_any = 0
                sample_rows = 0
                overlap_fractions: list[float] = []
                overlap_any: list[float] = []
                exact_duplicates: list[float] = []
                top_k = {}
                for draw in draws:
                    actual = set(actual_by_draw[(lt, draw)])
                    tickets_by_strategy = {sid: rows_by_key[(lt, sid, draw)] for sid in combo}
                    for sid, tickets in tickets_by_strategy.items():
                        top_k.setdefault(sid, set()).add(len(tickets))
                    tickets = [ticket for sid in combo for ticket in tickets_by_strategy[sid]]
                    sample_rows += len(tickets)
                    hits = [len(set(ticket) & actual) for ticket in tickets]
                    max_hit = max(hits)
                    hit_dist[max_hit] += 1
                    if lt == 'BIG_LOTTO':
                        special = special_by_draw[(lt, draw)]
                        special_any += int(any(special in ticket for ticket in tickets))
                    for a, b in itertools.combinations(combo, 2):
                        for ta in tickets_by_strategy[a]:
                            for tb in tickets_by_strategy[b]:
                                overlap = len(set(ta) & set(tb))
                                overlap_fractions.append(overlap / MAIN_COUNTS[lt])
                                overlap_any.append(float(overlap > 0))
                                exact_duplicates.append(float(ta == tb))
                record = {
                    'classification': CLASSIFICATION,
                    'lottery_type': lt,
                    'strategy_ids': '|'.join(combo),
                    'combination_size': size,
                    'window': f'recent_{window}',
                    'latest_target_draw': draws[0],
                    'earliest_target_draw': draws[-1],
                    'sample_size_draws': len(draws),
                    'sample_size_rows': sample_rows,
                    'top_k_by_strategy': '|'.join(f"{sid}:{'/'.join(map(str, sorted(vals)))}" for sid, vals in top_k.items()),
                    'predicted_number_count': MAIN_COUNTS[lt],
                    'hit_at_least_1_rate': rate(sum(v for k, v in hit_dist.items() if k >= 1), len(draws)),
                    'hit_at_least_2_rate': rate(sum(v for k, v in hit_dist.items() if k >= 2), len(draws)),
                    'hit_at_least_3_rate': rate(sum(v for k, v in hit_dist.items() if k >= 3), len(draws)),
                    'hit_at_least_4_rate': rate(sum(v for k, v in hit_dist.items() if k >= 4), len(draws)),
                    **{f'max_hit_count_{i}_draws': hit_dist[i] for i in range(7)},
                    'cross_strategy_ticket_pair_count': len(overlap_fractions),
                    'any_number_overlap_pair_rate': mean(overlap_any),
                    'mean_number_overlap_fraction': mean(overlap_fractions),
                    'exact_duplicate_ticket_pair_rate': mean(exact_duplicates),
                    'special_zone_status': ('BIG_SPECIAL_ACTUAL_AVAILABLE_PLAYER_MAIN_MATCH_EVALUATED'
                                            if lt == 'BIG_LOTTO' else 'NOT_APPLICABLE'),
                    'special_hit_any_rate': rate(special_any, len(draws)) if lt == 'BIG_LOTTO' else '',
                    'baseline_mode': 'not_computed',
                    'inferential_status': CLASSIFICATION,
                    'readiness_status': 'READY_DESCRIPTIVE_ONLY',
                    'exclusion_reason': '',
                }
                if size == 1:
                    for n in range(1, 5):
                        record[f'delta_vs_max_constituent_hit{n}_rate'] = '0.000000000000'
                    single_lookup[(lt, combo[0], window)] = record
                else:
                    for n in range(1, 5):
                        current = float(record[f'hit_at_least_{n}_rate'])
                        constituent = max(float(single_lookup[(lt, sid, window)][f'hit_at_least_{n}_rate']) for sid in combo)
                        record[f'delta_vs_max_constituent_hit{n}_rate'] = f'{current - constituent:.12f}'
                metrics.append(record)

write_csv(ROOT / 'strategy_combination_metrics.csv', fields, metrics)

# Fixed-size descriptive shortlist: highest hit>=3, then hit>=2, then lower overlap.
candidate_fields = fields + ['selection_rule']
candidates: list[dict] = []
for lt in LOTTERIES:
    for window in WINDOWS:
        for size in (2, 3):
            group = [r for r in metrics if r['lottery_type'] == lt and r['window'] == f'recent_{window}'
                     and r['combination_size'] == size]
            group.sort(key=lambda r: (-float(r['hit_at_least_3_rate']),
                                      -float(r['hit_at_least_2_rate']),
                                      float(r['mean_number_overlap_fraction']), r['strategy_ids']))
            for r in group[:5]:
                candidates.append({**r, 'selection_rule': 'DESCRIPTIVE_TOP5_BY_HIT3_THEN_HIT2_THEN_LOWER_OVERLAP'})
write_csv(ROOT / 'top_descriptive_candidates.csv', candidate_fields, candidates)

summary_fields = ['classification', 'lottery_type', 'window', 'latest_target_draw',
                  'earliest_target_draw', 'common_draw_count_available', 'strategy_count',
                  'single_metric_rows', 'pair_metric_rows', 'triple_metric_rows',
                  'baseline_mode', 'inferential_status']
summaries = []
for lt in LOTTERIES:
    for window in WINDOWS:
        draws = common_draws[lt][:window]
        summaries.append({
            'classification': CLASSIFICATION, 'lottery_type': lt, 'window': f'recent_{window}',
            'latest_target_draw': draws[0], 'earliest_target_draw': draws[-1],
            'common_draw_count_available': len(common_draws[lt]), 'strategy_count': len(strategies[lt]),
            'single_metric_rows': len(strategies[lt]),
            'pair_metric_rows': len(list(itertools.combinations(strategies[lt], 2))),
            'triple_metric_rows': len(list(itertools.combinations(strategies[lt], 3))),
            'baseline_mode': 'not_computed', 'inferential_status': CLASSIFICATION,
        })
write_csv(ROOT / 'window_summary.csv', summary_fields, summaries)

top_lines = []
for row in candidates:
    top_lines.append(f"| {row['lottery_type']} | {row['window']} | {row['combination_size']} | {row['strategy_ids']} | {row['hit_at_least_2_rate']} | {row['hit_at_least_3_rate']} | {row['delta_vs_max_constituent_hit3_rate']} | {row['mean_number_overlap_fraction']} |")
(ROOT / 'strategy_combination_metrics.md').write_text('''# P320A Per-Draw Strategy Combination Metrics

Classification: `DESCRIPTIVE_ONLY`

Each draw-level combination pools the constituent strategies' stored tickets. `max_hit_count` is the largest main-number match count among those tickets. `hit_at_least_N_rate` is the fraction of common target draws whose maximum is at least N. This is an any-ticket portfolio metric, not a union-number ticket. Deltas compare the combination with its strongest constituent single-strategy rate in the same frozen sample and are descriptive only.

Overlap metrics enumerate cross-strategy ticket pairs per draw. `mean_number_overlap_fraction` is intersection size divided by the lottery's ticket size; exact duplicates are separately reported. Random baselines and inference were not computed.

## Descriptive candidate rows

| Lottery | Window | Size | Strategy IDs | Hit>=2 | Hit>=3 | Delta hit>=3 | Mean overlap |
|---|---:|---:|---|---:|---:|---:|---:|
''' + '\n'.join(top_lines) + '\n', encoding='utf-8')

sidecars_after = {str(p): {'exists': p.exists(), 'size': p.stat().st_size if p.exists() else None,
                           'mtime_ns': p.stat().st_mtime_ns if p.exists() else None} for p in sidecars}
db_hash_after = sha256(DB)
db_stat_after = {'size': DB.stat().st_size, 'mtime_ns': DB.stat().st_mtime_ns}
assert sidecars_before == sidecars_after
assert db_hash_before == db_hash_after and db_stat_before == db_stat_after

source = f'''# Source Readiness

- Source: `{DB}` (pre-existing tracked backup snapshot).
- Open mode: SQLite URI `mode=ro&immutable=1`; `PRAGMA query_only=1` verified.
- Table: `strategy_prediction_replays`.
- Required columns present: {', '.join(sorted(required))}.
- Source rows retained for scope: BIG_LOTTO={row_count_by_lottery['BIG_LOTTO']}; DAILY_539={row_count_by_lottery['DAILY_539']}.
- Complete predicted/actual main-number rows: verified by parsing every retained row.
- Per-draw actual consistency: verified across all strategies and bet indexes.
- Committed identity alignment: {identity_checked_draws} strategy/draw records and {identity_checked_tickets} distinct tickets matched exactly against `{IDENTITY}`.
- DB SHA256 before/after: `{db_hash_before}` / `{db_hash_after}`.
- DB size/mtime before/after: `{db_stat_before}` / `{db_stat_after}`.
- Sidecars before/after: `{json.dumps(sidecars_before, sort_keys=True)}` / `{json.dumps(sidecars_after, sort_keys=True)}`.
- True per-draw combination overlap readiness: PASS for BIG_LOTTO and DAILY_539.
- POWER_LOTTO: excluded; canonical second-zone completeness is not established for full scoring.
'''
(ROOT / 'source_readiness.md').write_text(source, encoding='utf-8')

(ROOT / 'powerlotto_scope_note.md').write_text('''# POWER_LOTTO Scope Note

Status: `BLOCKED` for this analysis. The prior source evidence records substantial missing `predicted_special` values, and no canonical POWER_LOTTO view is verified here. No second-zone value was filled, inferred, defaulted, randomized, or copied from actual results. POWER_LOTTO rows were not scored.
''', encoding='utf-8')

(ROOT / 'limitations.md').write_text('''# Limitations

- Results are retrospective and `DESCRIPTIVE_ONLY`; no future-performance, wagering, production-readiness, or causal claim is made.
- `baseline_mode=not_computed`; no random edge or inferential significance is claimed.
- Pair/triple success is an any-ticket maximum-hit portfolio metric. Larger combinations inherently spend more tickets and are not equal-budget comparisons.
- The descriptive candidate file is a deterministic display shortlist, not an endorsement.
- Windows use the most recent common draw IDs across every in-scope strategy, ordered numerically by `target_draw`.
- BIG_LOTTO main hits and actual special-number containment are reported separately. DAILY_539 has no special/zone component.
- POWER_LOTTO is excluded because second-zone source readiness is incomplete.
''', encoding='utf-8')

print(json.dumps({'metrics_rows': len(metrics), 'candidate_rows': len(candidates),
                  'identity_checked_draws': identity_checked_draws,
                  'identity_checked_tickets': identity_checked_tickets,
                  'db_sha256': db_hash_before, 'sidecars_unchanged': True,
                  'common_draws': {k: len(v) for k, v in common_draws.items()}}, sort_keys=True))
