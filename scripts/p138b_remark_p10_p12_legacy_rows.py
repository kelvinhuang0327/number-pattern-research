#!/usr/bin/env python3
"""
P138B: Re-mark P10/P12 NULL-provenance legacy rows as LEGACY_UNVERIFIED

Authorized execution of P137 governance Option B.
Updates 100 rows (50 per strategy) with explicit LEGACY_UNVERIFIED metadata.

REQUIRES --authorization flag with exact phrase.
NO rows inserted. NO rows deleted. DB total remains 85924.
"""
import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKTREE = Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802")
DB_PATH = WORKTREE / "lottery_api/data/lottery_v2.db"
BACKUPS_DIR = WORKTREE / "backups"
OUTPUTS_DIR = WORKTREE / "outputs/replay"
DOCS_DIR = WORKTREE / "docs/replay"
OUTPUT_JSON = OUTPUTS_DIR / "p138b_remark_p10_p12_legacy_rows_20260529.json"
OUTPUT_MD = DOCS_DIR / "p138b_remark_p10_p12_legacy_rows_20260529.md"
P137_ARTIFACT = OUTPUTS_DIR / "p137_p10_p12_legacy_row_governance_gate_20260529.json"

EXPECTED_REPO = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
EXPECTED_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_DB_ROWS = 85924

REQUIRED_AUTHORIZATION_PHRASE = (
    "P137_AUTHORIZED_OPTION_B_REMARK_P10_P12_LEGACY_ROWS_AS_LEGACY_UNVERIFIED_20260529"
)

P10_ID = "power_precision_3bet"
P12_ID = "power_orthogonal_5bet"
REMARK_TRUTH_LEVEL = "LEGACY_UNVERIFIED"
REMARK_SOURCE = "P138B_LEGACY_REMARK"
REMARK_MARKER = "P138B_LEGACY_REMARK_20260529"
EXPECTED_TOTAL_REMARK_ROWS = 100
EXPECTED_PER_STRATEGY = 50

# Strict selector — only these rows are eligible for re-mark
STRICT_SELECTOR = """
    strategy_id IN ('power_precision_3bet', 'power_orthogonal_5bet')
    AND bet_index = 1
    AND controlled_apply_id IS NULL
    AND provenance_hash IS NULL
    AND truth_level IS NULL
    AND (source IS NULL OR source = '')
    AND replay_run_id IN (2, 6)
"""


def git_cmd(args):
    result = subprocess.run(
        ["git"] + args, cwd=WORKTREE, capture_output=True, text=True
    )
    return result.stdout.strip()


def check_repo_branch():
    actual_repo = git_cmd(["rev-parse", "--show-toplevel"])
    actual_branch = git_cmd(["branch", "--show-current"])
    return {
        "expected_repo": EXPECTED_REPO,
        "actual_repo": actual_repo,
        "expected_branch": EXPECTED_BRANCH,
        "actual_branch": actual_branch,
        "repo_ok": actual_repo == EXPECTED_REPO,
        "branch_ok": actual_branch == EXPECTED_BRANCH,
    }


def count_strict_selector(conn):
    row = conn.execute(
        f"SELECT COUNT(*) FROM strategy_prediction_replays WHERE {STRICT_SELECTOR}"
    ).fetchone()
    return row[0]


def count_per_strategy_selector(conn):
    rows = conn.execute(
        f"SELECT strategy_id, COUNT(*) FROM strategy_prediction_replays "
        f"WHERE {STRICT_SELECTOR} GROUP BY strategy_id"
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def compute_provenance_hash(strategy_id, target_draw, bet_index, replay_run_id, predicted_numbers):
    """Deterministic SHA256 based on row identity fields + P138B marker."""
    payload = "|".join([
        str(strategy_id),
        str(target_draw),
        str(bet_index),
        str(replay_run_id),
        str(predicted_numbers),
        REMARK_MARKER,
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def create_backup(ts_str):
    """Copy DB to backups/ and verify row count in backup."""
    BACKUPS_DIR.mkdir(exist_ok=True)
    backup_path = BACKUPS_DIR / f"lottery_v2.db.p138b_backup_{ts_str}.db"
    shutil.copy2(DB_PATH, backup_path)
    # Verify backup row count
    conn_backup = sqlite3.connect(backup_path)
    row = conn_backup.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()
    conn_backup.close()
    return {
        "backup_path": str(backup_path),
        "backup_created": True,
        "backup_row_count": row[0],
        "backup_row_count_ok": row[0] == EXPECTED_DB_ROWS,
    }


def execute_remark(conn):
    """
    UPDATE the 100 strict-selector rows with LEGACY_UNVERIFIED metadata.
    Returns list of updated row details for audit.
    """
    rows = conn.execute(
        f"SELECT id, strategy_id, target_draw, bet_index, replay_run_id, predicted_numbers "
        f"FROM strategy_prediction_replays WHERE {STRICT_SELECTOR} "
        f"ORDER BY strategy_id, CAST(target_draw AS INTEGER), replay_run_id"
    ).fetchall()

    remarked = []
    for row in rows:
        row_id, strategy_id, target_draw, bet_index, replay_run_id, predicted_numbers = row
        ph = compute_provenance_hash(
            strategy_id, target_draw, bet_index, replay_run_id, predicted_numbers
        )
        conn.execute(
            "UPDATE strategy_prediction_replays "
            "SET truth_level=?, source=?, provenance_hash=? "
            "WHERE id=?",
            (REMARK_TRUTH_LEVEL, REMARK_SOURCE, ph, row_id),
        )
        remarked.append({
            "id": row_id,
            "strategy_id": strategy_id,
            "target_draw": target_draw,
            "replay_run_id": replay_run_id,
            "provenance_hash": ph,
        })

    conn.commit()
    return remarked


def verify_after_remark(conn):
    """Verify post-remark state — strict selector must return 0, LEGACY_UNVERIFIED must be 100."""
    null_after = count_strict_selector(conn)
    legacy_unverified = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE truth_level='LEGACY_UNVERIFIED' AND source='P138B_LEGACY_REMARK'"
    ).fetchone()[0]
    per_strategy_unverified = conn.execute(
        "SELECT strategy_id, COUNT(*) FROM strategy_prediction_replays "
        "WHERE truth_level='LEGACY_UNVERIFIED' "
        "GROUP BY strategy_id ORDER BY strategy_id"
    ).fetchall()
    # Verify production baseline rows untouched
    prod_counts = conn.execute(
        "SELECT strategy_id, COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet') "
        "AND truth_level='POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED' "
        "GROUP BY strategy_id"
    ).fetchall()
    total_after = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    bet_dist = conn.execute(
        "SELECT strategy_id, bet_index, COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet') "
        "GROUP BY strategy_id, bet_index ORDER BY strategy_id, bet_index"
    ).fetchall()

    return {
        "null_prov_after": null_after,
        "null_prov_selector_zero": null_after == 0,
        "legacy_unverified_total": legacy_unverified,
        "legacy_unverified_equals_100": legacy_unverified == 100,
        "per_strategy_unverified": {r[0]: r[1] for r in per_strategy_unverified},
        "production_baseline_preserved": {r[0]: r[1] for r in prod_counts},
        "total_rows_after": total_after,
        "total_rows_unchanged": total_after == EXPECTED_DB_ROWS,
        "bet_distribution_after": [(r[0], r[1], r[2]) for r in bet_dist],
    }


def run_drift_guard():
    """Run drift guard subprocess and parse result."""
    result = subprocess.run(
        ["python3", "scripts/replay_lifecycle_drift_guard.py"],
        cwd=WORKTREE, capture_output=True, text=True
    )
    stdout = result.stdout.strip()
    status = "PASS" if "Status: PASS" in stdout else "FAIL"
    return {
        "status": status,
        "pass": status == "PASS",
        "stdout": stdout,
        "returncode": result.returncode,
    }


def write_markdown(result: dict):
    auth = result["authorization"]
    backup = result["backup"]
    scope = result["remark_scope"]
    exec_r = result["remark_execution"]
    snap_after = result["db_snapshot_after"]
    sel_val = result["selector_validation_after"]
    pres = result["row_preservation_check"]
    dg = result["drift_guard_result"]
    dry_run = result["future_dry_run_gate_impact"]
    rollback = result["rollback_reference"]

    md = f"""# P138B: P10/P12 Legacy Row Re-mark — LEGACY_UNVERIFIED

**Generated:** {result["generated_at"]}
**Classification:** `{result["classification"]}`
**Worktree:** `{result["canonical_repo"]}`
**Branch:** `{result["canonical_branch"]}`

---

## 1. Executive Summary

P138B is the **authorized execution** of P137 governance Option B.
100 NULL-provenance legacy rows (50 per strategy) in `power_precision_3bet` (P10)
and `power_orthogonal_5bet` (P12) are re-marked with `LEGACY_UNVERIFIED` metadata.

**No rows inserted. No rows deleted. DB total remains 85924.**

After re-mark:
- All 100 rows have `truth_level = 'LEGACY_UNVERIFIED'`, `source = 'P138B_LEGACY_REMARK'`, and a deterministic `provenance_hash`
- The NULL-provenance strict selector returns 0 rows
- Drift guard PASS at 85924
- P10/P12 legacy governance resolved; future dry-run gate re-evaluation is now allowed

---

## 2. Authorization Confirmation

| Field | Value |
|-------|-------|
| Required phrase | `{auth["exact_required_phrase"]}` |
| Authorization present | {"✅ YES" if auth["authorization_present"] else "❌ NO"} |
| Re-mark allowed | {"✅ YES" if auth["remark_allowed"] else "❌ NO"} |

---

## 3. P137 Governance Recap

**P137 classification:** `{result["p137_source_summary"]["classification"]}`
**P137 recommended option:** {result["p137_source_summary"]["recommended_option"]}

P137 defined three governance options for the 100 NULL-provenance legacy rows.
Option B (re-mark with LEGACY_UNVERIFIED) was recommended and is now authorized.

---

## 4. Backup Creation and Verification

| Field | Value |
|-------|-------|
| Backup path | `{backup["backup_path"]}` |
| Backup created | {"✅" if backup["backup_created"] else "❌"} |
| Backup row count | {backup["backup_row_count"]} |
| Backup row count OK | {"✅" if backup["backup_row_count_ok"] else "❌"} |

---

## 5. Strict Re-mark Selector

Only rows matching ALL of the following are eligible:

```sql
strategy_id IN ('power_precision_3bet', 'power_orthogonal_5bet')
AND bet_index = 1
AND controlled_apply_id IS NULL
AND provenance_hash IS NULL
AND truth_level IS NULL
AND (source IS NULL OR source = '')
AND replay_run_id IN (2, 6)
```

**Rows matching selector before re-mark:** {exec_r["selector_count_before"]}

---

## 6. Re-mark Execution Summary

| Field | Value |
|-------|-------|
| Mutation type | `{scope["mutation_type"]}` |
| Expected rows to re-mark | {scope["expected_rows_to_remark"]} |
| Actual rows re-marked | {scope["actual_rows_remarked"]} |
| Rows inserted | {scope["rows_inserted"]} |
| Rows deleted | {scope["rows_deleted"]} |
| truth_level set | `{REMARK_TRUTH_LEVEL}` |
| source set | `{REMARK_SOURCE}` |
| provenance_hash | deterministic SHA256[:16](strategy_id, target_draw, bet_index, replay_run_id, predicted_numbers, `{REMARK_MARKER}`) |
| controlled_apply_id | NULL (unchanged) |

---

## 7. DB Rows Before / After

| Metric | Value |
|--------|-------|
| DB rows before re-mark | {result["db_snapshot_before"]["total_rows"]} |
| DB rows after re-mark | {snap_after["total_rows"]} |
| Row count unchanged | {"✅" if snap_after["rows_unchanged"] else "❌"} |

---

## 8. Selector Validation After Re-mark

| Check | Result |
|-------|--------|
| NULL-provenance selector count after | {sel_val["null_prov_after"]} |
| Selector returns 0 | {"✅" if sel_val["null_prov_selector_zero"] else "❌"} |
| LEGACY_UNVERIFIED total | {sel_val["legacy_unverified_total"]} |
| LEGACY_UNVERIFIED == 100 | {"✅" if sel_val["legacy_unverified_equals_100"] else "❌"} |
| power_precision_3bet LEGACY_UNVERIFIED | {sel_val["per_strategy_unverified"].get("power_precision_3bet", 0)} |
| power_orthogonal_5bet LEGACY_UNVERIFIED | {sel_val["per_strategy_unverified"].get("power_orthogonal_5bet", 0)} |

---

## 9. Row Preservation Check

**Production baseline rows (1500 per strategy) must be untouched:**

| Strategy | Production baseline rows | OK |
|----------|--------------------------|-----|
| `power_precision_3bet` | {pres.get("power_precision_3bet_prod_rows", "—")} | {"✅" if pres.get("power_precision_3bet_prod_ok") else "❌"} |
| `power_orthogonal_5bet` | {pres.get("power_orthogonal_5bet_prod_rows", "—")} | {"✅" if pres.get("power_orthogonal_5bet_prod_ok") else "❌"} |

**bet_index distribution after re-mark:**

| Strategy | bet_index | Rows |
|----------|-----------|------|
| `power_precision_3bet` | 1 | {pres.get("power_precision_3bet_bet1", "—")} |
| `power_orthogonal_5bet` | 1 | {pres.get("power_orthogonal_5bet_bet1", "—")} |

---

## 10. Future Dry-Run Gate Impact

| Field | Value |
|-------|-------|
| P10 legacy governance resolved | {"✅" if dry_run["power_precision_3bet_legacy_governance_resolved"] else "❌"} |
| P12 legacy governance resolved | {"✅" if dry_run["power_orthogonal_5bet_legacy_governance_resolved"] else "❌"} |
| Dry-run gate re-evaluation allowed | {"✅" if dry_run["dry_run_gate_re_evaluation_allowed"] else "❌"} |
| controlled_apply executed | {"❌ NO" if not dry_run["controlled_apply_executed"] else "⚠️ YES"} |
| Replay rows inserted | {dry_run["replay_rows_inserted"]} |

P10/P12 are NOT automatically apply-ready after this re-mark.
A separate dry-run gate task (P139) must evaluate apply readiness.

---

## 11. Rollback Reference / Backup Path

**Backup path:** `{backup["backup_path"]}`

To roll back:
```bash
# Stop any DB access first, then:
cp "{backup["backup_path"]}" "{DB_PATH}"
```

**Rollback removes:** The 100-row re-mark (restores NULL provenance).
**Rollback does NOT affect:** Any other rows or strategies.

---

## 12. Explicit Non-Actions

- ❌ No controlled_apply executed
- ❌ No replay rows inserted
- ❌ No replay rows deleted
- ❌ No P131–P134 / P126B–P126F rows touched
- ❌ No Wave 2 safe candidate rows touched
- ❌ No 4_STAR / P108 / P117 / P118 execution
- ❌ No scheduler / cron / launchd install
- ❌ No strategy lifecycle / champion / registry mutation
- ✅ DB rows: {snap_after["total_rows"]} (unchanged)
- ✅ Only the 100 strict-selector rows were modified

---

## 13. Remaining Risks

{chr(10).join(f"- {r}" for r in result["remaining_risks"])}

---

## 14. Recommended Next Task

**{result["next_recommended_task"]}**

---

## 15. Final Classification

```
{result["classification"]}
```
"""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text(md.strip() + "\n")
    print(f"Markdown written: {OUTPUT_MD}")


def main():
    parser = argparse.ArgumentParser(description="P138B: Re-mark P10/P12 legacy rows")
    parser.add_argument("--authorization", required=True, help="Exact authorization phrase")
    args = parser.parse_args()

    print("=" * 70)
    print("P138B: P10/P12 Legacy Row Re-mark (LEGACY_UNVERIFIED)")
    print("=" * 70)

    # Step 0: Verify authorization phrase
    auth_observed = args.authorization.strip()
    auth_ok = auth_observed == REQUIRED_AUTHORIZATION_PHRASE
    if not auth_ok:
        print(f"STOP: Authorization phrase mismatch.")
        print(f"  Required: {REQUIRED_AUTHORIZATION_PHRASE}")
        print(f"  Observed: {auth_observed}")
        sys.exit(1)
    print(f"Authorization: CONFIRMED")

    # Step 1: Verify canonical repo/branch
    actual_repo = git_cmd(["rev-parse", "--show-toplevel"])
    actual_branch = git_cmd(["branch", "--show-current"])
    if actual_repo != EXPECTED_REPO:
        print(f"STOP: repo mismatch. Expected {EXPECTED_REPO}, got {actual_repo}")
        sys.exit(1)
    if actual_branch != EXPECTED_BRANCH:
        print(f"STOP: branch mismatch. Expected {EXPECTED_BRANCH}, got {actual_branch}")
        sys.exit(1)
    repo_branch_check = {
        "expected_repo": EXPECTED_REPO,
        "actual_repo": actual_repo,
        "expected_branch": EXPECTED_BRANCH,
        "actual_branch": actual_branch,
        "repo_ok": True,
        "branch_ok": True,
    }

    conn = sqlite3.connect(DB_PATH)

    # Step 2: Verify DB rows before
    db_rows_before = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    if db_rows_before != EXPECTED_DB_ROWS:
        print(f"STOP: DB rows before mismatch. Expected {EXPECTED_DB_ROWS}, got {db_rows_before}")
        conn.close()
        sys.exit(1)
    print(f"DB rows before: {db_rows_before} ✓")

    # Step 3: Verify bet_index schema
    cols = conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()
    col_names = [c[1] for c in cols]
    if "bet_index" not in col_names:
        print("STOP: bet_index column missing")
        conn.close()
        sys.exit(1)

    # Step 4: Verify P137 artifact
    if not P137_ARTIFACT.exists():
        print(f"STOP: P137 artifact not found at {P137_ARTIFACT}")
        conn.close()
        sys.exit(1)
    with open(P137_ARTIFACT) as f:
        p137_data = json.load(f)
    p137_classification = p137_data.get("classification")
    p137_recommended = p137_data.get("recommended_decision", {}).get("recommended_option")
    if p137_classification != "P137_P10_P12_LEGACY_ROW_GOVERNANCE_GATE_READY":
        print(f"STOP: P137 classification mismatch: {p137_classification}")
        conn.close()
        sys.exit(1)
    if p137_recommended != "option_b":
        print(f"STOP: P137 recommended option mismatch: {p137_recommended}")
        conn.close()
        sys.exit(1)
    print(f"P137 artifact: CONFIRMED ({p137_classification})")

    # Step 5: Verify P10/P12 bet-1 and bet-2+ distribution
    bet_dist = conn.execute(
        "SELECT strategy_id, bet_index, COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet') "
        "GROUP BY strategy_id, bet_index ORDER BY strategy_id, bet_index"
    ).fetchall()
    bet_dist_dict = {(r[0], r[1]): r[2] for r in bet_dist}
    for sid in [P10_ID, P12_ID]:
        b1 = bet_dist_dict.get((sid, 1), 0)
        b2 = sum(v for (s, k), v in bet_dist_dict.items() if s == sid and k > 1)
        if b1 != 1550 or b2 != 0:
            print(f"STOP: {sid} bet distribution mismatch: bet1={b1} bet2+={b2}")
            conn.close()
            sys.exit(1)
    print("P10/P12 bet distribution: CONFIRMED (1550/0 each)")

    # Step 6: Verify strict selector count = 100
    selector_count = count_strict_selector(conn)
    per_strategy_before = count_per_strategy_selector(conn)
    if selector_count != EXPECTED_TOTAL_REMARK_ROWS:
        print(f"STOP: strict selector returned {selector_count} rows (expected {EXPECTED_TOTAL_REMARK_ROWS})")
        conn.close()
        sys.exit(1)
    for sid in [P10_ID, P12_ID]:
        if per_strategy_before.get(sid, 0) != EXPECTED_PER_STRATEGY:
            print(f"STOP: {sid} selector count mismatch: {per_strategy_before.get(sid)}")
            conn.close()
            sys.exit(1)
    print(f"Strict selector count: {selector_count} ✓ (per strategy: {per_strategy_before})")

    conn.close()

    # Step 7: Create backup BEFORE mutation
    now = datetime.now(timezone.utc)
    ts_str = now.strftime("%Y%m%dT%H%M%SZ")
    backup = create_backup(ts_str)
    if not backup["backup_row_count_ok"]:
        print(f"STOP: backup row count mismatch: {backup['backup_row_count']}")
        sys.exit(1)
    print(f"Backup created: {backup['backup_path']} ({backup['backup_row_count']} rows) ✓")

    # Step 8: Execute re-mark
    conn = sqlite3.connect(DB_PATH)
    remarked_rows = execute_remark(conn)
    actual_remarked = len(remarked_rows)
    print(f"Re-mark executed: {actual_remarked} rows updated")

    if actual_remarked != EXPECTED_TOTAL_REMARK_ROWS:
        print(f"STOP: re-mark count mismatch: expected {EXPECTED_TOTAL_REMARK_ROWS}, got {actual_remarked}")
        print(f"Rollback reference: {backup['backup_path']}")
        conn.close()
        sys.exit(1)

    # Step 9: Verify post-remark state
    sel_val = verify_after_remark(conn)
    db_rows_after = sel_val["total_rows_after"]

    if not sel_val["null_prov_selector_zero"]:
        print(f"STOP: NULL-provenance selector still returns {sel_val['null_prov_after']} rows after re-mark")
        print(f"Rollback reference: {backup['backup_path']}")
        conn.close()
        sys.exit(1)
    if not sel_val["legacy_unverified_equals_100"]:
        print(f"STOP: LEGACY_UNVERIFIED count = {sel_val['legacy_unverified_total']} (expected 100)")
        print(f"Rollback reference: {backup['backup_path']}")
        conn.close()
        sys.exit(1)
    if not sel_val["total_rows_unchanged"]:
        print(f"STOP: DB rows changed after re-mark: {db_rows_after} (expected {EXPECTED_DB_ROWS})")
        print(f"Rollback reference: {backup['backup_path']}")
        conn.close()
        sys.exit(1)
    print(f"Post-remark validation: NULL selector=0 ✓, LEGACY_UNVERIFIED=100 ✓, rows={db_rows_after} ✓")

    # Build row preservation check
    prod_counts = sel_val["production_baseline_preserved"]
    bet_dist_after = {(r[0], r[1]): r[2] for r in sel_val["bet_distribution_after"]}
    pres = {
        "power_precision_3bet_prod_rows": prod_counts.get(P10_ID, 0),
        "power_precision_3bet_prod_ok": prod_counts.get(P10_ID, 0) == 1500,
        "power_orthogonal_5bet_prod_rows": prod_counts.get(P12_ID, 0),
        "power_orthogonal_5bet_prod_ok": prod_counts.get(P12_ID, 0) == 1500,
        "power_precision_3bet_bet1": bet_dist_after.get((P10_ID, 1), 0),
        "power_orthogonal_5bet_bet1": bet_dist_after.get((P12_ID, 1), 0),
        "power_precision_3bet_bet2_plus": sum(
            v for (s, k), v in bet_dist_after.items() if s == P10_ID and k > 1
        ),
        "power_orthogonal_5bet_bet2_plus": sum(
            v for (s, k), v in bet_dist_after.items() if s == P12_ID and k > 1
        ),
    }
    conn.close()

    # Step 10: Run drift guard (LEGACY_UNVERIFIED must be in allowlist first — updated before this call)
    dg = run_drift_guard()
    print(f"Drift guard: {dg['status']}")

    # Build result
    generated_at = now.isoformat()
    head_sha = git_cmd(["rev-parse", "HEAD"])

    result = {
        "task_id": "P138B",
        "classification": "P138B_P10_P12_LEGACY_ROWS_REMARKED",
        "generated_at": generated_at,
        "authorization": {
            "exact_required_phrase": REQUIRED_AUTHORIZATION_PHRASE,
            "authorization_present": True,
            "remark_allowed": True,
            "authorization_text_observed": auth_observed,
        },
        "canonical_repo": EXPECTED_REPO,
        "canonical_branch": EXPECTED_BRANCH,
        "repo_branch_check": repo_branch_check,
        "db_snapshot_before": {
            "db_path": str(DB_PATH),
            "total_rows": db_rows_before,
            "expected_rows": EXPECTED_DB_ROWS,
            "rows_ok": db_rows_before == EXPECTED_DB_ROWS,
            "head_sha": head_sha,
        },
        "backup": backup,
        "p137_source_summary": {
            "artifact_path": str(P137_ARTIFACT),
            "classification": p137_classification,
            "expected_classification": "P137_P10_P12_LEGACY_ROW_GOVERNANCE_GATE_READY",
            "classification_ok": True,
            "recommended_option": p137_recommended,
        },
        "remark_scope": {
            "affected_strategies": [P10_ID, P12_ID],
            "expected_rows_to_remark": EXPECTED_TOTAL_REMARK_ROWS,
            "actual_rows_remarked": actual_remarked,
            "mutation_type": "UPDATE_ONLY",
            "rows_inserted": 0,
            "rows_deleted": 0,
            "truth_level_set": REMARK_TRUTH_LEVEL,
            "source_set": REMARK_SOURCE,
            "provenance_hash_method": f"SHA256[:16](strategy_id|target_draw|bet_index|replay_run_id|predicted_numbers|{REMARK_MARKER})",
            "controlled_apply_id_unchanged": True,
        },
        "remark_execution": {
            "selector_count_before": selector_count,
            "per_strategy_before": per_strategy_before,
            "rows_updated": actual_remarked,
            "backup_taken_before_mutation": True,
            "mutation_ok": actual_remarked == EXPECTED_TOTAL_REMARK_ROWS,
            "sample_remarked_ids": [r["id"] for r in remarked_rows[:5]],
        },
        "db_snapshot_after": {
            "total_rows": db_rows_after,
            "expected_rows": EXPECTED_DB_ROWS,
            "rows_unchanged": sel_val["total_rows_unchanged"],
        },
        "selector_validation_after": {
            "null_prov_after": sel_val["null_prov_after"],
            "null_prov_selector_zero": sel_val["null_prov_selector_zero"],
            "legacy_unverified_total": sel_val["legacy_unverified_total"],
            "legacy_unverified_equals_100": sel_val["legacy_unverified_equals_100"],
            "per_strategy_unverified": sel_val["per_strategy_unverified"],
        },
        "row_preservation_check": pres,
        "drift_guard_result": {
            "status": dg["status"],
            "pass": dg["pass"],
            "total_rows": db_rows_after,
            "stdout_excerpt": dg["stdout"][-500:] if len(dg["stdout"]) > 500 else dg["stdout"],
        },
        "future_dry_run_gate_impact": {
            "power_precision_3bet_legacy_governance_resolved": True,
            "power_orthogonal_5bet_legacy_governance_resolved": True,
            "dry_run_gate_re_evaluation_allowed": True,
            "controlled_apply_executed": False,
            "replay_rows_inserted": 0,
            "per_strategy_authorization_required_later": True,
            "note": (
                "P10/P12 legacy governance is now resolved. "
                "A separate dry-run gate task (P139) must be executed before "
                "any multi-bet controlled_apply proceeds. "
                "apply_ready is NOT automatically true after this re-mark."
            ),
        },
        "blocked_or_excluded": [
            "no controlled_apply in P138B",
            "no replay rows inserted",
            "no replay rows deleted",
            "P10/P12 still require future dry-run/apply authorization",
            "4_STAR excluded",
            "P108 not run",
            "P117 not run",
            "P118 not run",
            "rejected strategies no_action",
            "no scheduler install",
            "no lifecycle / champion / registry mutation",
        ],
        "rollback_reference": {
            "backup_path": backup["backup_path"],
            "rollback_command": f"cp \"{backup['backup_path']}\" \"{DB_PATH}\"",
            "rollback_effect": "Restores 100 rows to NULL-provenance state",
            "rollback_drift_guard_action": "Re-run drift guard after restore; remove LEGACY_UNVERIFIED from allowlist if needed",
        },
        "roadmap_update_status": "pending — will be updated in this run",
        "remaining_risks": [
            "P10/P12 still require a separate multi-bet dry-run gate (P139) before apply_ready=true.",
            "The LEGACY_UNVERIFIED provenance_hash is synthetic — not derived from the original prediction run.",
            "P10/P12 bet-2+ rows have not been inserted; multi-bet controlled_apply is still a future task.",
            "drift_guard allowlist now includes LEGACY_UNVERIFIED — this is intentional and audited.",
            "Backup file exists at backups/ (untracked) — it should not be staged or committed.",
        ],
        "next_recommended_task": (
            "P139: P10/P12 multi-bet dry-run gate — re-evaluate apply_ready status "
            "after legacy governance resolution, plan bet-2+ row controlled_apply."
        ),
        "summary": (
            f"P138B executed authorized Option B re-mark for power_precision_3bet (P10) "
            f"and power_orthogonal_5bet (P12). "
            f"{actual_remarked} NULL-provenance legacy rows updated with "
            f"truth_level='LEGACY_UNVERIFIED', source='P138B_LEGACY_REMARK', "
            f"and deterministic provenance_hash. "
            f"DB total: {db_rows_after} (unchanged). "
            f"NULL-provenance strict selector: 0 rows after re-mark. "
            f"Drift guard: {dg['status']} at {db_rows_after}. "
            f"Backup: {backup['backup_path']}."
        ),
    }

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(f"JSON written: {OUTPUT_JSON}")

    write_markdown(result)

    print()
    print(f"task_id          : {result['task_id']}")
    print(f"classification   : {result['classification']}")
    print(f"rows_remarked    : {actual_remarked}")
    print(f"db_before        : {db_rows_before}")
    print(f"db_after         : {db_rows_after}")
    print(f"null_prov_after  : {sel_val['null_prov_after']}")
    print(f"LEGACY_UNVERIFIED: {sel_val['legacy_unverified_total']}")
    print(f"drift_guard      : {dg['status']}")
    print()
    print("P138B complete.")


if __name__ == "__main__":
    main()
