"""
P351T endpoint/TestClient integration harness (external, read-only).

Purpose: exercise the real /api/replay/* FastAPI router (unmodified source,
loaded from the clean gate worktree) against the REAL canonical DB, without
copying/symlinking the DB into the worktree and without editing any repo file.

Mechanism: monkeypatch replay._open_conn (an in-memory function reassignment,
not a file edit) so it opens sqlite3 mode=ro + PRAGMA query_only=ON against the
canonical DB's real absolute path instead of the worktree-relative path. This
is strictly read-only at the SQLite engine level; no write is possible through
this connection.

This script lives entirely outside the repo and writes its output only to the
external evidence root. It performs no DB writes, no repo edits.
"""
import json
import sqlite3
import sys

GATE_WORKTREE = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p351t-final-gate"
CANONICAL_DB = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db"

sys.path.insert(0, GATE_WORKTREE)
sys.path.insert(0, GATE_WORKTREE + "/lottery_api")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lottery_api.routes import replay as replay_mod


def _open_conn_canonical():
    conn = sqlite3.connect(f"file:{CANONICAL_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


replay_mod._open_conn = _open_conn_canonical

app = FastAPI()
app.include_router(replay_mod.router)
client = TestClient(app)

results = {}

def call(name, url):
    try:
        r = client.get(url)
        body_preview = None
        try:
            j = r.json()
            if isinstance(j, dict):
                body_preview = {k: (v if not isinstance(v, list) else f"<list len={len(v)}>") for k, v in list(j.items())[:8]}
        except Exception:
            body_preview = r.text[:200]
        results[name] = {"url": url, "status": r.status_code, "body_preview": body_preview}
        return r
    except Exception as e:
        results[name] = {"url": url, "error": f"{type(e).__name__}: {e}"}
        return None

# Phase A: no-parameter / low-risk endpoints
call("strategies", "/api/replay/strategies")
call("strategy_lifecycle", "/api/replay/strategy-lifecycle")
call("runs", "/api/replay/runs")
call("freshness", "/api/replay/freshness")
call("strategy_catalog", "/api/replay/strategy-catalog")
call("evidence_dashboard", "/api/replay/evidence-dashboard")
call("best_strategy_overview", "/api/replay/best-strategy-overview")
call("d3_strategy_status_audit", "/api/replay/d3-strategy-status-audit")
call("history_overview", "/api/replay/history-overview?coverage_mode=true&bet_index=0")
call("d3_strategy_status_coverage", "/api/replay/d3-strategy-status-coverage")

# Phase B: parametrized endpoints using a real strategy_id + lottery_type
# discovered from Phase A's /api/replay/strategies response
# (item shape: {"strategy_id", "strategy_name", ..., "supported_lottery_types": [...]})
strategy_id = None
lottery_type = None
bet_index = 1
try:
    r = client.get("/api/replay/strategies")
    sj = r.json()
    rows = sj.get("strategies") or []
    if rows:
        first = rows[0]
        strategy_id = first.get("strategy_id")
        supported = first.get("supported_lottery_types") or []
        lottery_type = supported[0] if supported else None
except Exception as e:
    results["_strategy_discovery_error"] = str(e)

if strategy_id and lottery_type:
    call("history", f"/api/replay/history?lottery_type={lottery_type}&limit=5")
    call("summary", f"/api/replay/summary?lottery_type={lottery_type}")
    call(
        "history_detail",
        f"/api/replay/history-detail?lottery_type={lottery_type}&strategy_id={strategy_id}&bet_index={bet_index}&limit=5",
    )
    call(
        "history_detail_grouped",
        f"/api/replay/history-detail-grouped?lottery_type={lottery_type}&strategy_id={strategy_id}&bet_index={bet_index}&page_size=5",
    )
else:
    results["history"] = {"skipped": "no strategy_id/lottery_type discovered from /api/replay/strategies"}
    results["summary"] = {"skipped": "no strategy_id/lottery_type discovered from /api/replay/strategies"}
    results["history_detail"] = {"skipped": "no strategy_id/lottery_type discovered from /api/replay/strategies"}
    results["history_detail_grouped"] = {"skipped": "no strategy_id/lottery_type discovered from /api/replay/strategies"}

# Verify read-only guarantee: attempt a write through the same connection factory
# and confirm it is rejected by SQLite (mode=ro / query_only).
write_rejected = None
try:
    conn = _open_conn_canonical()
    try:
        conn.execute("CREATE TABLE p351t_should_never_exist (x INTEGER)")
        write_rejected = False
    except sqlite3.OperationalError as e:
        write_rejected = True
        write_rejected_reason = str(e)
    finally:
        conn.close()
except Exception as e:
    write_rejected = f"harness_error: {e}"

results["_read_only_guarantee_check"] = {
    "write_attempt_rejected": write_rejected,
    "reason": write_rejected_reason if write_rejected is True else None,
}

print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
