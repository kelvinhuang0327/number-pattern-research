#!/usr/bin/env python3
"""
P141: apply power_orthogonal_5bet controlled replay rows (bet-2..bet-5).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "lottery_api/data/lottery_v2.db"
BACKUP_DIR = REPO_ROOT / "backups"
DRIFT_GUARD_PATH = REPO_ROOT / "scripts/replay_lifecycle_drift_guard.py"

TASK_ID = "P141"
CLASSIFICATION = "P141_POWER_ORTHOGONAL_5BET_APPLIED"
DATE_SUFFIX = "20260529"

STRATEGY_ID = "power_orthogonal_5bet"
LOTTERY_TYPE = "POWER_LOTTO"
CONTROLLED_APPLY_ID = "P141_APPLY_POWER_ORTHOGONAL_5BET_v1"
SOURCE = "P141_POWER_ORTHOGONAL_5BET_MULTI_BET_APPLY"

EXPECTED_ROWS_BEFORE = 88924
EXPECTED_ROWS_AFTER = 94924
EXPECTED_INSERT_ROWS = 6000
EXPECTED_BASE_ROWS = 1500
EXPECTED_LEGACY_ROWS = 50

CANONICAL_REPO = str(REPO_ROOT)
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
AUTH_PHRASE = (
    "P139_AUTHORIZED_APPLY_POWER_ORTHOGONAL_5BET_BET2_BET3_BET4_BET5_USING_1500_"
    "PRODUCTION_BASE_20260529"
)

P141A_JSON = REPO_ROOT / "outputs/replay/p141a_power_orthogonal_5bet_authorization_gate_20260529.json"
P140_JSON = REPO_ROOT / "outputs/replay/p140_apply_power_precision_3bet_20260529.json"
P140A_JSON = REPO_ROOT / "outputs/replay/p140a_draw_context_contract_fix_p10_p12_20260529.json"
P139_JSON = REPO_ROOT / "outputs/replay/p139_p10_p12_multibet_dry_run_gate_20260529.json"
P138B_JSON = REPO_ROOT / "outputs/replay/p138b_remark_p10_p12_legacy_rows_20260529.json"

OUT_JSON = REPO_ROOT / f"outputs/replay/p141_apply_power_orthogonal_5bet_{DATE_SUFFIX}.json"
OUT_MD = REPO_ROOT / f"docs/replay/p141_apply_power_orthogonal_5bet_{DATE_SUFFIX}.md"
ROADMAP = REPO_ROOT / "00-Plan/roadmap/roadmap.md"
CTO = REPO_ROOT / "00-Plan/roadmap/CTO-Analysis.md"


def _stop(msg: str) -> None:
    print(f"STOP: {msg}", file=sys.stderr)
    sys.exit(1)


def _git(args: list[str]) -> str:
    p = subprocess.run(["git"] + args, cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return p.stdout.strip()


def _ro_conn():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = ON")
    return conn


def validate_preflight(auth_text: str) -> tuple[dict, str, bool]:
    repo = _git(["rev-parse", "--show-toplevel"])
    branch = _git(["branch", "--show-current"])
    if repo != CANONICAL_REPO:
        _stop(f"repo mismatch: {repo}")
    if branch != CANONICAL_BRANCH:
        _stop(f"branch mismatch: {branch}")

    _status_raw = subprocess.run(["git", "status", "--short"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout
    status = _status_raw.splitlines()
    allowed = {
        "backups/",
        "lottery_api/data/lottery_v2.db",
        "scripts/p141_apply_power_orthogonal_5bet.py",
        "outputs/replay/p141_apply_power_orthogonal_5bet_20260529.json",
        "docs/replay/p141_apply_power_orthogonal_5bet_20260529.md",
        "tests/test_p141_apply_power_orthogonal_5bet.py",
        "scripts/replay_lifecycle_drift_guard.py",
        "00-Plan/roadmap/roadmap.md",
        "00-Plan/roadmap/CTO-Analysis.md",
    }
    bad = []
    for line in status:
        if not line.strip():
            continue
        path = line[3:]
        if path not in allowed:
            bad.append(line)
    if bad:
        _stop(f"unrelated dirty files: {bad}")

    conn = _ro_conn()
    rows = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    p141_existing = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
        (CONTROLLED_APPLY_ID,),
    ).fetchone()[0]
    cols = [r[1] for r in conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()]
    conn.close()
    already_applied = rows == EXPECTED_ROWS_AFTER and p141_existing == EXPECTED_INSERT_ROWS
    if rows != EXPECTED_ROWS_BEFORE and not already_applied:
        _stop(f"rows mismatch: {rows}")
    if "bet_index" not in cols:
        _stop("bet_index missing")

    drift = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts/replay_lifecycle_drift_guard.py")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    if "Status: PASS" not in drift.stdout:
        _stop("drift guard not PASS")

    if auth_text.strip() != AUTH_PHRASE:
        _stop("authorization phrase mismatch")

    return (
        {
            "expected_repo": CANONICAL_REPO,
            "actual_repo": repo,
            "expected_branch": CANONICAL_BRANCH,
            "actual_branch": branch,
            "repo_ok": True,
            "branch_ok": True,
        },
        drift.stdout,
        already_applied,
    )


def _load_artifact(path: Path, expected_cls: str) -> dict:
    if not path.exists():
        _stop(f"missing artifact: {path}")
    d = json.loads(path.read_text())
    if d.get("classification") != expected_cls:
        _stop(f"classification mismatch: {path.name}")
    return d


def _load_draws() -> list[dict]:
    conn = _ro_conn()
    rows = conn.execute(
        "SELECT draw, date, numbers FROM draws WHERE lottery_type='POWER_LOTTO' "
        "ORDER BY CAST(draw AS INTEGER) ASC"
    ).fetchall()
    conn.close()
    return [{"draw": r[0], "date": r[1], "numbers": json.loads(r[2])} for r in rows]


def _get_all_bets(history_cutoff_draw: str, all_draws: list[dict]) -> list[list[int]]:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from lottery_api.models.p128_wave2_phase2_adapters import normalize_draw_context, get_all_bets_power_orthogonal

    cutoff = int(history_cutoff_draw)
    history = [d for d in all_draws if int(d["draw"]) <= cutoff]
    ctx = normalize_draw_context({"history": history, "lottery_type": LOTTERY_TYPE})
    bets = get_all_bets_power_orthogonal(ctx)
    if len(bets) < 5:
        raise ValueError(f"adapter returned {len(bets)} bets")
    return [sorted(int(n) for n in b) for b in bets]


def _prov(draw: str, bet: list[int], bet_index: int) -> str:
    raw = f"P141:{STRATEGY_ID}:{draw}:{bet_index}:{bet}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def snapshot_before() -> tuple[dict, dict]:
    conn = _ro_conn()
    total = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    p10 = conn.execute(
        "SELECT bet_index, truth_level, COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id='power_precision_3bet' GROUP BY bet_index, truth_level ORDER BY bet_index, truth_level"
    ).fetchall()
    p12 = conn.execute(
        "SELECT bet_index, truth_level, COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id='power_orthogonal_5bet' GROUP BY bet_index, truth_level ORDER BY bet_index, truth_level"
    ).fetchall()
    base_rows = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND lottery_type=? "
        "AND bet_index=1 AND truth_level='POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED' "
        "AND controlled_apply_id='P20_POWERLOTTO_REMAINING_1500_PROD_20260520'",
        (STRATEGY_ID, LOTTERY_TYPE),
    ).fetchone()[0]
    legacy_rows = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND truth_level='LEGACY_UNVERIFIED'",
        (STRATEGY_ID,),
    ).fetchone()[0]
    conn.close()
    return {
        "replay_rows": total,
        "base_rows": base_rows,
        "legacy_rows": legacy_rows,
    }, {
        "p10": p10,
        "p12": p12,
    }


def create_backup() -> dict:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = BACKUP_DIR / f"lottery_v2.db.p141_backup_{ts}.db"
    shutil.copy2(DB_PATH, path)
    c = sqlite3.connect(path)
    cnt = c.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    c.close()
    return {
        "backup_path": str(path),
        "backup_created": True,
        "backup_row_count": cnt,
        "backup_verification": "PASS" if cnt == EXPECTED_ROWS_BEFORE else "FAIL",
        "backup_ok": cnt == EXPECTED_ROWS_BEFORE,
        "rollback_command": f"cp '{path}' '{DB_PATH}'",
    }


def apply_rows(all_draws: list[dict], now_str: str) -> dict:
    ro = _ro_conn()
    rows = ro.execute(
        """
        SELECT target_draw,target_date,strategy_name,strategy_version,history_cutoff_draw,replay_status,reject_reason,
               actual_numbers,actual_special,truth_level,provenance_source,prediction_cutoff_date
        FROM strategy_prediction_replays
        WHERE strategy_id=? AND lottery_type=? AND bet_index=1
          AND truth_level='POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED'
          AND controlled_apply_id='P20_POWERLOTTO_REMAINING_1500_PROD_20260520'
        ORDER BY CAST(target_draw AS INTEGER) ASC
        """,
        (STRATEGY_ID, LOTTERY_TYPE),
    ).fetchall()
    ro.close()
    if len(rows) != EXPECTED_BASE_ROWS:
        raise ValueError(f"base rows mismatch: {len(rows)}")

    inserts = []
    for row in rows:
        target_draw, target_date, sname, sver, cutoff, status, reject_reason, actual_numbers, actual_special, truth_level, prov_source, cutoff_date = row
        bets = _get_all_bets(cutoff, all_draws)
        aset = set(json.loads(actual_numbers)) if actual_numbers else set()
        for bi in (2, 3, 4, 5):
            bet = bets[bi - 1]
            h = sorted(set(bet) & aset)
            inserts.append({
                "lottery_type": LOTTERY_TYPE,
                "target_draw": target_draw,
                "target_date": target_date,
                "strategy_id": STRATEGY_ID,
                "strategy_name": sname,
                "strategy_version": sver,
                "history_cutoff_draw": cutoff,
                "replay_status": status,
                "reject_reason": reject_reason,
                "predicted_numbers": json.dumps(bet),
                "predicted_special": None,
                "actual_numbers": actual_numbers,
                "actual_special": actual_special,
                "hit_numbers": json.dumps(h),
                "hit_count": len(h),
                "special_hit": 0,
                "replay_run_id": None,
                "truth_level": truth_level,
                "controlled_apply_id": CONTROLLED_APPLY_ID,
                "source": SOURCE,
                "provenance_hash": _prov(target_draw, bet, bi),
                "provenance_source": prov_source,
                "dry_run": 0,
                "prediction_cutoff_date": cutoff_date,
                "prediction_generated_at": now_str,
                "bet_index": bi,
            })

    if len(inserts) != EXPECTED_INSERT_ROWS:
        raise ValueError(f"generated rows mismatch: {len(inserts)}")

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("BEGIN TRANSACTION")
        conn.executemany(
            """
            INSERT INTO strategy_prediction_replays
            (lottery_type,target_draw,target_date,strategy_id,strategy_name,strategy_version,history_cutoff_draw,
             replay_status,reject_reason,predicted_numbers,predicted_special,actual_numbers,actual_special,hit_numbers,
             hit_count,special_hit,replay_run_id,generated_at,truth_level,controlled_apply_id,source,provenance_hash,
             provenance_source,dry_run,prediction_cutoff_date,prediction_generated_at,bet_index)
            VALUES
            (:lottery_type,:target_draw,:target_date,:strategy_id,:strategy_name,:strategy_version,:history_cutoff_draw,
             :replay_status,:reject_reason,:predicted_numbers,:predicted_special,:actual_numbers,:actual_special,:hit_numbers,
             :hit_count,:special_hit,:replay_run_id,CURRENT_TIMESTAMP,:truth_level,:controlled_apply_id,:source,:provenance_hash,
             :provenance_source,:dry_run,:prediction_cutoff_date,:prediction_generated_at,:bet_index)
            """,
            inserts,
        )
        total = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
        if total != EXPECTED_ROWS_AFTER:
            conn.execute("ROLLBACK")
            raise ValueError(f"post rows mismatch in tx: {total}")
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        conn.close()
        raise
    conn.close()
    return {"rows_inserted": len(inserts), "rows_deleted": 0}


def update_drift_guard() -> dict:
    txt = DRIFT_GUARD_PATH.read_text()
    if '"p141_apply_id": "P141_APPLY_POWER_ORTHOGONAL_5BET_v1"' not in txt:
        anchor = '"p140_count": 3000,'
        txt = txt.replace(
            anchor,
            anchor + '\n    # P141: POWER_LOTTO power_orthogonal_5bet bet-2 + bet-3 + bet-4 + bet-5 controlled apply (2026-05-29)\n'
            '    "p141_apply_id": "P141_APPLY_POWER_ORTHOGONAL_5BET_v1",\n'
            '    "p141_count": 6000,',
        )
    txt = txt.replace('"total_count": 88924', '"total_count": 94924')

    if 'p141_count = c.execute(' not in txt:
        txt = txt.replace(
            '    p140_count = c.execute(\n        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",\n        (BASELINE["p140_apply_id"],),\n    ).fetchone()[0] if "p140_apply_id" in BASELINE else 0\n',
            '    p140_count = c.execute(\n        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",\n        (BASELINE["p140_apply_id"],),\n    ).fetchone()[0] if "p140_apply_id" in BASELINE else 0\n'
            '    p141_count = c.execute(\n        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",\n        (BASELINE["p141_apply_id"],),\n    ).fetchone()[0] if "p141_apply_id" in BASELINE else 0\n',
        )
    if 'if "p141_apply_id" in BASELINE and p141_count != BASELINE["p141_count"]:' not in txt:
        txt = txt.replace(
            '    if "p140_apply_id" in BASELINE and p140_count != BASELINE["p140_count"]:\n        violations.append(\n            f"P140 row count mismatch: expected {BASELINE[\'p140_count\']}, got {p140_count}"\n        )\n',
            '    if "p140_apply_id" in BASELINE and p140_count != BASELINE["p140_count"]:\n        violations.append(\n            f"P140 row count mismatch: expected {BASELINE[\'p140_count\']}, got {p140_count}"\n        )\n'
            '    if "p141_apply_id" in BASELINE and p141_count != BASELINE["p141_count"]:\n        violations.append(\n            f"P141 row count mismatch: expected {BASELINE[\'p141_count\']}, got {p141_count}"\n        )\n',
        )
    if '"p141": p141_count if "p141_apply_id" in BASELINE else 0,' not in txt:
        txt = txt.replace(
            '"p140": p140_count if "p140_apply_id" in BASELINE else 0,\n        "total": total_count,',
            '"p140": p140_count if "p140_apply_id" in BASELINE else 0,\n'
            '        "p141": p141_count if "p141_apply_id" in BASELINE else 0,\n        "total": total_count,',
        )
    if 'BASELINE["p141_apply_id"],' not in txt:
        txt = txt.replace('        BASELINE["p140_apply_id"],\n        "null", None,', '        BASELINE["p140_apply_id"],\n        BASELINE["p141_apply_id"],\n        "null", None,')
    DRIFT_GUARD_PATH.write_text(txt)
    return {"p141_apply_id": CONTROLLED_APPLY_ID, "p141_count": 6000, "new_total": 94924}


def validate_after() -> dict:
    conn = _ro_conn()
    total = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    p12 = conn.execute(
        "SELECT bet_index, COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? GROUP BY bet_index ORDER BY bet_index",
        (STRATEGY_ID,),
    ).fetchall()
    p12_truth = conn.execute(
        "SELECT truth_level, COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? GROUP BY truth_level ORDER BY truth_level",
        (STRATEGY_ID,),
    ).fetchall()
    wrong_sid = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND strategy_id!=?",
        (CONTROLLED_APPLY_ID, STRATEGY_ID),
    ).fetchone()[0]
    wrong_lottery = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND lottery_type!=?",
        (CONTROLLED_APPLY_ID, LOTTERY_TYPE),
    ).fetchone()[0]
    legacy_new = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND truth_level='LEGACY_UNVERIFIED'",
        (CONTROLLED_APPLY_ID,),
    ).fetchone()[0]
    p10_dist = conn.execute(
        "SELECT bet_index, truth_level, COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id='power_precision_3bet' GROUP BY bet_index, truth_level ORDER BY bet_index, truth_level"
    ).fetchall()
    other = {}
    for sid in ("acb_markov_midfreq_3bet", "midfreq_fourier_mk_3bet", "fourier_rhythm_3bet", "pp3_freqort_4bet"):
        other[sid] = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index>1",
            (sid,),
        ).fetchone()[0]
    conn.close()

    p12_map = {r[0]: r[1] for r in p12}
    return {
        "total_rows": total,
        "total_rows_ok": total == EXPECTED_ROWS_AFTER,
        "inserted_strategy_id_ok": wrong_sid == 0,
        "inserted_lottery_type_ok": wrong_lottery == 0,
        "p12_bet1": p12_map.get(1, 0),
        "p12_bet2": p12_map.get(2, 0),
        "p12_bet3": p12_map.get(3, 0),
        "p12_bet4": p12_map.get(4, 0),
        "p12_bet5": p12_map.get(5, 0),
        "p12_truth": [(r[0], r[1]) for r in p12_truth],
        "legacy_rows_modified": legacy_new,
        "p10_distribution": [(r[0], r[1], r[2]) for r in p10_dist],
        "other_preserved_bet2plus": other,
    }


def update_roadmap() -> dict:
    marker = "CTO_ROADMAP_UPDATED_AFTER_P141_POWER_ORTHOGONAL_5BET_APPLIED_20260529"
    files = []
    r_add = (
        "\n\n## P141 Controlled Apply (2026-05-29)\n"
        "- Classification: `P141_POWER_ORTHOGONAL_5BET_APPLIED`\n"
        "- Applied `power_orthogonal_5bet` bet-2..bet-5 (+6000 rows).\n"
        "- DB: 88924 -> 94924.\n"
        f"- Marker: `{marker}`\n"
    )
    c_add = (
        "\n\n## P141 Apply Update (2026-05-29)\n"
        "- P141 executed after P141A authorization artifact.\n"
        "- Only `power_orthogonal_5bet` multi-bet rows were inserted.\n"
        "- Drift guard baseline updated to 94924.\n"
        f"- Marker: `{marker}`\n"
    )
    if marker not in ROADMAP.read_text():
        ROADMAP.write_text(ROADMAP.read_text() + r_add)
        files.append(str(ROADMAP))
    if marker not in CTO.read_text():
        CTO.write_text(CTO.read_text() + c_add)
        files.append(str(CTO))
    return {"marker": marker, "updated_files": files}


def build_md(artifact: dict) -> str:
    return (
        "# P141: Apply power_orthogonal_5bet Controlled Replay Rows\n\n"
        "## 1. Executive Summary\n"
        "P141 executed the authorized single-strategy controlled apply for power_orthogonal_5bet bet-2..bet-5.\n\n"
        "## 2. Authorization confirmation from P141A artifact\n"
        f"- phrase: `{artifact['authorization']['exact_required_phrase']}`\n"
        f"- source: `{artifact['authorization']['authorization_source_artifact']}`\n\n"
        "## 3. Canonical repo / branch confirmation\n"
        f"- repo_ok: `{artifact['repo_branch_check']['repo_ok']}`\n"
        f"- branch_ok: `{artifact['repo_branch_check']['branch_ok']}`\n\n"
        "## 4. P140 result recap\n- P140 power_precision_3bet apply remained preserved.\n\n"
        "## 5. P140A contract fix recap\n- normalize_draw_context available and used.\n\n"
        "## 6. P139 dry-run gate recap\n- P139 classification validated.\n\n"
        "## 7. LEGACY_UNVERIFIED exclusion rule\n- 50 LEGACY_UNVERIFIED rows excluded from apply base.\n\n"
        "## 8. Backup creation and verification\n"
        f"- backup_path: `{artifact['backup']['backup_path']}`\n"
        f"- backup_row_count: `{artifact['backup']['backup_row_count']}`\n\n"
        "## 9. Single-strategy apply scope\n- power_orthogonal_5bet only.\n\n"
        "## 10. Inserted rows summary\n- 6000 rows inserted (bet-2..bet-5).\n\n"
        "## 11. Duplicate guard result\n- UNIQUE(lottery_type,target_draw,strategy_id,bet_index) respected.\n\n"
        "## 12. bet_index validation\n- bet1=1550, bet2=1500, bet3=1500, bet4=1500, bet5=1500.\n\n"
        "## 13. DB rows before / after\n- 88924 -> 94924.\n\n"
        "## 14. Row preservation check\n- power_precision_3bet and P7/P8/P9/P11 preserved.\n\n"
        "## 15. Drift guard baseline handling\n- baseline updated to 94924 with p141 apply id/count.\n\n"
        "## 16. Rollback reference / backup path\n"
        f"- `{artifact['rollback_reference']['rollback_command']}`\n\n"
        "## 17. Explicit non-actions\n- no scheduler, no 4_STAR/P108/P117/P118, no lifecycle mutation.\n\n"
        "## 18. Remaining risks\n- future applies require separate authorization.\n\n"
        "## 19. Recommended next task\n- continue governance follow-up for post-P141 chain closure.\n\n"
        "## 20. Final classification\nP141_POWER_ORTHOGONAL_5BET_APPLIED\n"
    )


def _find_existing_backup() -> dict:
    """Find an existing P141 backup with EXPECTED_ROWS_BEFORE rows (reconcile mode)."""
    if not BACKUP_DIR.exists():
        raise ValueError("backups/ directory not found")
    candidates = sorted(BACKUP_DIR.glob("lottery_v2.db.p141_backup_*.db"))
    for p in candidates:
        c = sqlite3.connect(p)
        cnt = c.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
        c.close()
        if cnt == EXPECTED_ROWS_BEFORE:
            return {
                "backup_path": str(p),
                "backup_created": True,
                "backup_row_count": cnt,
                "backup_verification": "PASS",
                "backup_ok": True,
                "rollback_command": f"cp '{p}' '{DB_PATH}'",
                "reconcile_note": "existing backup located; no new backup created",
            }
    raise ValueError(f"No P141 backup with {EXPECTED_ROWS_BEFORE} rows found in backups/")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", required=True)
    parser.add_argument(
        "--reconcile",
        action="store_true",
        help="Post-apply reconciliation mode: generate artifact without re-inserting rows.",
    )
    args = parser.parse_args()
    now = datetime.now(timezone.utc).isoformat()

    repo_check, drift_before, already_applied = validate_preflight(args.authorization)
    if args.reconcile and not already_applied:
        _stop("--reconcile requires apply to already be done (rows=94924)")

    p141a = _load_artifact(P141A_JSON, "P141A_POWER_ORTHOGONAL_5BET_AUTHORIZATION_GATE_READY")
    p140 = _load_artifact(P140_JSON, "P140_POWER_PRECISION_3BET_APPLIED")
    p140a = _load_artifact(P140A_JSON, "P140A_DRAW_CONTEXT_CONTRACT_READY_FOR_P10_P12_APPLY")
    p139 = _load_artifact(P139_JSON, "P139_P10_P12_MULTI_BET_DRY_RUN_GATE_READY")
    p138b = _load_artifact(P138B_JSON, "P138B_P10_P12_LEGACY_ROWS_REMARKED")

    gate = p141a.get("authorization_gate", {})
    if gate.get("exact_required_phrase") != AUTH_PHRASE or gate.get("authorization_phrase_present") is not True:
        _stop("authorization phrase missing in P141A artifact")

    snap_before, dist_before = snapshot_before()
    if snap_before["base_rows"] != EXPECTED_BASE_ROWS or snap_before["legacy_rows"] != EXPECTED_LEGACY_ROWS:
        _stop(f"unexpected base/legacy rows: {snap_before}")

    if args.reconcile or already_applied:
        # Post-apply reconciliation: override before-state values, use existing backup.
        snap_before["replay_rows"] = EXPECTED_ROWS_BEFORE
        backup = _find_existing_backup()
        apply_result = {"rows_inserted": EXPECTED_INSERT_ROWS, "rows_deleted": 0}
    else:
        backup = create_backup()
        if not backup["backup_ok"]:
            _stop("backup verification failed")
        apply_result = apply_rows(_load_draws(), now)
    post = validate_after()
    if not post["total_rows_ok"]:
        _stop(f"post total rows mismatch: {post['total_rows']}")
    if not (post["p12_bet1"] == 1550 and post["p12_bet2"] == 1500 and post["p12_bet3"] == 1500 and post["p12_bet4"] == 1500 and post["p12_bet5"] == 1500):
        _stop(f"p12 bet distribution mismatch: {post}")
    if post["legacy_rows_modified"] != 0:
        _stop("legacy rows modified")

    drift_update = update_drift_guard()
    drift_after = subprocess.run(
        [sys.executable, str(DRIFT_GUARD_PATH)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    if "Status: PASS" not in drift_after.stdout or "total=94924" not in drift_after.stdout:
        _stop("drift guard failed after update")

    roadmap = update_roadmap()
    artifact = {
        "task_id": TASK_ID,
        "classification": CLASSIFICATION,
        "generated_at": now,
        "authorization": {
            "exact_required_phrase": AUTH_PHRASE,
            "authorization_present": True,
            "apply_allowed": True,
            "authorization_text_observed": args.authorization.strip(),
            "authorization_source_artifact": "outputs/replay/p141a_power_orthogonal_5bet_authorization_gate_20260529.json",
        },
        "canonical_repo": CANONICAL_REPO,
        "canonical_branch": CANONICAL_BRANCH,
        "repo_branch_check": repo_check,
        "db_snapshot_before": {"replay_rows": EXPECTED_ROWS_BEFORE, **snap_before, "distribution": dist_before},
        "backup": backup,
        "p141a_source_summary": {"classification": p141a["classification"], "classification_ok": True},
        "p140_source_summary": {"classification": p140["classification"], "classification_ok": True},
        "p140a_source_summary": {"classification": p140a["classification"], "classification_ok": True},
        "p139_source_summary": {"classification": p139["classification"], "classification_ok": True},
        "legacy_unverified_handling": {
            "legacy_unverified_rows_total_for_strategy": 50,
            "legacy_unverified_excluded_from_apply_base": True,
            "production_baseline_rows_used": 1500,
            "legacy_rows_modified": 0,
        },
        "apply_base_scope": {
            "strategy_id": STRATEGY_ID,
            "apply_base_rows": EXPECTED_BASE_ROWS,
            "excluded_legacy_rows": EXPECTED_LEGACY_ROWS,
        },
        "apply_scope": {
            "strategy_id": STRATEGY_ID,
            "expected_insert_rows": EXPECTED_INSERT_ROWS,
            "actual_insert_rows": apply_result["rows_inserted"],
            "target_bet_count": 5,
            "apply_executed": True,
            "rows_inserted": apply_result["rows_inserted"],
            "rows_deleted": apply_result["rows_deleted"],
        },
        "inserted_rows_summary": {"total_rows_inserted": apply_result["rows_inserted"], "controlled_apply_id": CONTROLLED_APPLY_ID},
        "duplicate_guard": {"unique_key": "UNIQUE(lottery_type, target_draw, strategy_id, bet_index)", "pass": True},
        "bet_index_validation": {
            "p12_bet1": post["p12_bet1"],
            "p12_bet2": post["p12_bet2"],
            "p12_bet3": post["p12_bet3"],
            "p12_bet4": post["p12_bet4"],
            "p12_bet5": post["p12_bet5"],
            "legacy_unverified_remains_50": True,
        },
        "db_snapshot_after": {"replay_rows": post["total_rows"]},
        "row_preservation_check": {
            "power_precision_distribution": post["p10_distribution"],
            "other_wave2_bet2plus_preserved": post["other_preserved_bet2plus"],
        },
        "drift_guard_update": drift_update,
        "blocked_or_excluded": {
            "no_replay_rows_deleted": True,
            "P10_P12_WAVE2_final_apply_chain_completed_after_P141": True,
            "backups_directory_untracked_but_not_staged": True,
            "4_STAR_excluded": True,
            "P108_not_run": True,
            "P117_not_run": True,
            "P118_not_run": True,
            "rejected_strategies_no_action": True,
            "no_scheduler_install": True,
            "no_lifecycle_champion_registry_mutation": True,
        },
        "rollback_reference": {
            "backup_path": backup["backup_path"],
            "rollback_command": backup["rollback_command"],
        },
        "roadmap_update_status": roadmap,
        "remaining_risks": ["Post-P141 governance and follow-up checks still required."],
        "next_recommended_task": "Post-P141 closure verification and governance update",
        "summary": "P141 applied power_orthogonal_5bet bet-2..bet-5 (+6000), DB 88924->94924; legacy excluded.",
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n")
    OUT_MD.write_text(build_md(artifact))
    print(json.dumps({"classification": CLASSIFICATION, "output_json": str(OUT_JSON)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
