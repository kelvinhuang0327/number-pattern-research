import hashlib, json, sqlite3, sys, os
sys.path.insert(0, "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/cold-wal-actionable-fail-closed-r1")
sys.path.insert(0, "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/cold-wal-actionable-fail-closed-r1/lottery_api")
from database import ColdWalReadOnlyError, DatabaseManager

db_path = sys.argv[1]
mode = sys.argv[2]

def sha256(p):
    if not os.path.exists(p):
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

wal_path = db_path + "-wal"
shm_path = db_path + "-shm"

orig_connect = sqlite3.connect
calls = {"n": 0}
def counting_connect(*a, **kw):
    calls["n"] += 1
    return orig_connect(*a, **kw)
sqlite3.connect = counting_connect

result = {
    "executable": sys.executable,
    "python_version": sys.version.split()[0],
    "sqlite_version": sqlite3.sqlite_version,
    "fixture_mode": mode,
    "db_hash_before": sha256(db_path),
    "wal_sidecar_before": sha256(wal_path),
    "shm_sidecar_before": sha256(shm_path),
}
manager = DatabaseManager(db_path=db_path, read_only=True)
try:
    draws = manager.get_canonical_draws(lottery_type="BIG_LOTTO")
    result["exception"] = None
    result["row_count"] = len(draws)
except ColdWalReadOnlyError as exc:
    result["exception"] = "ColdWalReadOnlyError"
except Exception as exc:
    result["exception"] = type(exc).__name__ + ": " + str(exc)

result["sqlite3_connect_called"] = calls["n"] > 0
result["connect_call_count"] = calls["n"]
result["db_hash_after"] = sha256(db_path)
result["wal_sidecar_after"] = sha256(wal_path)
result["shm_sidecar_after"] = sha256(shm_path)
result["result"] = (
    "PASS" if (
        (mode == "cold" and result["exception"] == "ColdWalReadOnlyError" and not result["sqlite3_connect_called"]
         and result["wal_sidecar_after"] is None and result["shm_sidecar_after"] is None
         and result["db_hash_before"] == result["db_hash_after"])
        or
        (mode == "control" and result["exception"] is None and result.get("row_count") == 2)
    ) else "FAIL"
)
print(json.dumps(result, indent=2))
