#!/usr/bin/env python3
"""P333A read-only special-number range check (scorer-semantics reconciliation)."""
import hashlib, json, os, sqlite3
DB = "lottery_api/data/lottery_v2.db"
def sha256(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for c in iter(lambda:f.read(1<<20),b""): h.update(c)
    return h.hexdigest()
before=sha256(DB)
con=sqlite3.connect(f"file:{DB}?mode=ro",uri=True); cur=con.cursor()
out={}
# actual_special range in replay table per lottery
for lt in ("POWER_LOTTO","BIG_LOTTO","DAILY_539"):
    r=cur.execute("SELECT MIN(actual_special),MAX(actual_special),COUNT(DISTINCT actual_special) "
                  "FROM strategy_prediction_replays WHERE lottery_type=? AND actual_special IS NOT NULL",(lt,)).fetchone()
    p=cur.execute("SELECT MIN(predicted_special),MAX(predicted_special) "
                  "FROM strategy_prediction_replays WHERE lottery_type=? AND predicted_special IS NOT NULL",(lt,)).fetchone()
    out[lt]={"actual_special_min":r[0],"actual_special_max":r[1],"actual_special_distinct":r[2],
             "predicted_special_min":p[0],"predicted_special_max":p[1]}
# draws table special range per lottery (correct column = 'special')
draws={}
for lt in [x[0] for x in cur.execute("SELECT DISTINCT lottery_type FROM draws ORDER BY lottery_type").fetchall()]:
    r=cur.execute("SELECT COUNT(*),SUM(CASE WHEN special IS NOT NULL AND special!='' THEN 1 ELSE 0 END),"
                  "MIN(special),MAX(special) FROM draws WHERE lottery_type=?",(lt,)).fetchone()
    draws[lt]={"rows":r[0],"special_non_empty":r[1],"special_min":r[2],"special_max":r[3]}
out["draws"]=draws
con.close()
out["db_unchanged"]=(before==sha256(DB))
print(json.dumps(out,indent=2,ensure_ascii=False))
