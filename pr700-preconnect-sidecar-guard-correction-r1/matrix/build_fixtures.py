import json, sqlite3, shutil, sys
from pathlib import Path

fixtures_dir = Path("fixtures")
fixtures_dir.mkdir(exist_ok=True)

rows = [
    {"draw": "115000001", "date": "2026/01/01", "lottery_type": "BIG_LOTTO", "numbers": [1,2,3,4,5,44]},
    {"draw": "115000002", "date": "2026/01/08", "lottery_type": "BIG_LOTTO", "numbers": [7,8,9,10,11,49]},
]

def build_wal_conn(path, rows):
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE draws (id INTEGER PRIMARY KEY AUTOINCREMENT, draw TEXT NOT NULL,
        date TEXT NOT NULL, lottery_type TEXT NOT NULL, numbers TEXT NOT NULL, special INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP, jackpot_amount REAL DEFAULT NULL, sell_amount REAL DEFAULT NULL,
        total_amount REAL DEFAULT NULL, numbers_positional TEXT DEFAULT NULL, UNIQUE(draw, lottery_type))""")
    for r in rows:
        conn.execute("INSERT INTO draws (draw,date,lottery_type,numbers,special) VALUES (?,?,?,?,?)",
                     (r["draw"], r["date"], r["lottery_type"], json.dumps(r["numbers"]), r.get("special",0)))
    conn.commit()
    return conn

# cold fixture: WAL header, no sidecars
source = fixtures_dir / "_source.db"
conn = build_wal_conn(source, rows)
conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
conn.close()
cold_path = fixtures_dir / "cold.db"
shutil.copyfile(source, cold_path)
assert not Path(str(cold_path) + "-wal").exists()
assert not Path(str(cold_path) + "-shm").exists()

# control fixture: plain rollback-journal db
control_path = fixtures_dir / "control.db"
conn = sqlite3.connect(str(control_path))
conn.execute("""CREATE TABLE draws (id INTEGER PRIMARY KEY AUTOINCREMENT, draw TEXT NOT NULL,
    date TEXT NOT NULL, lottery_type TEXT NOT NULL, numbers TEXT NOT NULL, special INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, jackpot_amount REAL DEFAULT NULL, sell_amount REAL DEFAULT NULL,
    total_amount REAL DEFAULT NULL, numbers_positional TEXT DEFAULT NULL, UNIQUE(draw, lottery_type))""")
for r in rows:
    conn.execute("INSERT INTO draws (draw,date,lottery_type,numbers,special) VALUES (?,?,?,?,?)",
                 (r["draw"], r["date"], r["lottery_type"], json.dumps(r["numbers"]), r.get("special",0)))
conn.commit()
conn.close()

print("fixtures built:", cold_path, control_path)
