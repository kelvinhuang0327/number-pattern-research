import json, sys

def show(path, label):
    with open(path) as f:
        return json.load(f)

oof = show('outputs/predictions/PAPER/2026-05-11/model_deep_diagnostics_oof.json', 'OOF')
worst = show('outputs/predictions/PAPER/2026-05-11/model_worst_segments.json', 'WORST')

print('=== WORST SEGMENTS (top 10) ===')
for i, s in enumerate(worst['worst_segments'][:10], 1):
    print(f"  {i}. [{s['segment_by']}] {s['segment']}")
    print(f"     rows={s['row_count']}  bss={s['bss']}  ece={s['ece']}  avg_edge={s['avg_edge']}")
    print(f"     reason={s['rank_reason']}")

print()
print('=== OOF ORIENTATION DIAG ===')
for k, v in oof['orientation_diagnostics'].items():
    print(f'  {k}: {v}')

print()
print('=== OOF PROBABILITY DIAG ===')
for k, v in oof['probability_diagnostics'].items():
    print(f'  {k}: {v}')

print()
print('=== OOF SEGMENT by_home_bias_bucket ===')
for s in oof['segment_summary']['by_home_bias_bucket']:
    print(f"  {s['segment']}  rows={s['row_count']}  bss={s['bss']}  avg_edge={s['avg_edge']}")

print()
print('=== OOF SEGMENT by_favorite_side ===')
for s in oof['segment_summary']['by_favorite_side']:
    print(f"  {s['segment']}  rows={s['row_count']}  bss={s['bss']}  avg_edge={s['avg_edge']}")

print()
print('=== OOF SEGMENT by_confidence_bucket ===')
for s in oof['segment_summary']['by_confidence_bucket']:
    print(f"  {s['segment']}  rows={s['row_count']}  bss={s['bss']}  avg_edge={s['avg_edge']}")

print()
print('=== OOF SEGMENT by_month (sorted by bss) ===')
months = sorted(oof['segment_summary']['by_month'], key=lambda x: x['bss'] or 0)
for s in months:
    print(f"  {s['segment']}  rows={s['row_count']}  bss={s['bss']}  avg_edge={s['avg_edge']}")
