import sqlite3, json

db = sqlite3.connect('lottery_api/data/lottery_v2.db')
db.row_factory = sqlite3.Row

# VALID runs whose latest_known_draw is 115000038 => they predict 039
runs = db.execute(
    "SELECT id, snapshot_source, strategy_name, analyzed "
    "FROM prediction_runs WHERE latest_known_draw='115000038' AND snapshot_source='VALID'"
).fetchall()

for r in runs:
    rid = r['id']
    print(f"Run {rid}: strategy={r['strategy_name']}, analyzed={r['analyzed']}")
    items = db.execute(
        "SELECT i.numbers, i.special, i.strategy_name, i.num_bets, "
        "       res.hit_count, res.matched_numbers, res.actual_draw "
        "FROM prediction_items i "
        "LEFT JOIN prediction_results res ON res.item_id=i.id "
        "WHERE i.run_id=?", (rid,)
    ).fetchall()
    for i, it in enumerate(items):
        print(f"  Bet {i+1}: {it['numbers']} sp={it['special']} hit={it['hit_count']} matched={it['matched_numbers']} draw={it['actual_draw']}")

# Next draw snapshot - latest_known_draw=115000039
print("\n--- Next draw 040 ---")
ms = db.execute(
    "SELECT id, snapshot_source, strategy_name, analyzed, latest_known_draw "
    "FROM prediction_runs WHERE latest_known_draw='115000039'"
).fetchall()
for m in ms:
    mid = m['id']
    print(f"Run {mid}: src={m['snapshot_source']}, strat={m['strategy_name']}, analyzed={m['analyzed']}")
    items = db.execute(
        "SELECT strategy_name, num_bets, numbers, special "
        "FROM prediction_items WHERE run_id=?", (mid,)
    ).fetchall()
    for it in items:
        print(f"  [{it['strategy_name']}][{it['num_bets']}bet] {it['numbers']} sp={it['special']}")

db.close()
