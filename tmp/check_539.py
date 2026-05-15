import sqlite3, json

conn = sqlite3.connect('data/lottery_v2.db')
conn.row_factory = sqlite3.Row

# Check latest DAILY_539 draws
print('=== Latest DAILY_539 draws ===')
rows = conn.execute(
    "SELECT draw, date, numbers FROM draws WHERE lottery_type='DAILY_539' ORDER BY draw DESC LIMIT 10"
).fetchall()
for r in rows:
    print(f"  {r['draw']}  {r['date']}  {r['numbers']}")

print()

# Check prediction runs for DAILY_539
print('=== Recent DAILY_539 prediction_runs ===')
runs = conn.execute(
    "SELECT id, latest_known_draw, latest_known_date, strategy_name, snapshot_source, analyzed, analysis_note, created_at FROM prediction_runs WHERE lottery_type='DAILY_539' ORDER BY id DESC LIMIT 15"
).fetchall()
for r in runs:
    note = r['analysis_note'][:60] if r['analysis_note'] else None
    print(f"  run_id={r['id']}  draw={r['latest_known_draw']}  date={r['latest_known_date']}  strategy={r['strategy_name']}  src={r['snapshot_source']}  analyzed={r['analyzed']}  note={note}  at={r['created_at']}")

print()

# Check prediction items/results for latest DAILY_539
print('=== Recent DAILY_539 prediction results ===')
results = conn.execute("""
    SELECT pr.id as run_id, pr.latest_known_draw, pi.bet_index, pi.numbers, pi.strategy_name,
           pres.actual_draw, pres.actual_numbers, pres.hit_count, pres.matched_numbers, pres.researched
    FROM prediction_runs pr
    JOIN prediction_items pi ON pi.run_id = pr.id
    LEFT JOIN prediction_results pres ON pres.item_id = pi.id
    WHERE pr.lottery_type='DAILY_539'
    ORDER BY pr.id DESC, pi.bet_index
    LIMIT 40
""").fetchall()
for r in results:
    print(f"  run={r['run_id']}  known={r['latest_known_draw']}  bet={r['bet_index']}  nums={r['numbers']}  strat={r['strategy_name']}  actual_draw={r['actual_draw']}  actual={r['actual_numbers']}  hit={r['hit_count']}  match={r['matched_numbers']}  researched={r['researched']}")

print()

# Check DB schema for prediction_results
print('=== prediction_results schema ===')
schema = conn.execute("PRAGMA table_info(prediction_results)").fetchall()
for col in schema:
    print(f"  {col['name']}  {col['type']}  default={col['dflt_value']}")

print()
print('=== prediction_runs schema ===')
schema2 = conn.execute("PRAGMA table_info(prediction_runs)").fetchall()
for col in schema2:
    print(f"  {col['name']}  {col['type']}  default={col['dflt_value']}")

conn.close()
