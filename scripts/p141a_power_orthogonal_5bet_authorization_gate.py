#!/usr/bin/env python3
"""
P141A: power_orthogonal_5bet authorization artifact gate (read-only).

This task creates an authorization gate artifact for the next P141 apply step.
NO DB writes. NO controlled_apply. NO replay-row mutation.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKTREE = Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802")
CANONICAL_REPO = str(WORKTREE)
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_DB_ROWS = 88924

DB_PATH = WORKTREE / "lottery_api/data/lottery_v2.db"
OUTPUT_JSON = WORKTREE / "outputs/replay/p141a_power_orthogonal_5bet_authorization_gate_20260529.json"
OUTPUT_MD = WORKTREE / "docs/replay/p141a_power_orthogonal_5bet_authorization_gate_20260529.md"

ROADMAP = WORKTREE / "00-Plan/roadmap/roadmap.md"
CTO = WORKTREE / "00-Plan/roadmap/CTO-Analysis.md"

P140_JSON = WORKTREE / "outputs/replay/p140_apply_power_precision_3bet_20260529.json"
P140A_JSON = WORKTREE / "outputs/replay/p140a_draw_context_contract_fix_p10_p12_20260529.json"
P139_JSON = WORKTREE / "outputs/replay/p139_p10_p12_multibet_dry_run_gate_20260529.json"

AUTH_PHRASE = (
    "P139_AUTHORIZED_APPLY_POWER_ORTHOGONAL_5BET_BET2_BET3_BET4_BET5_"
    "USING_1500_PRODUCTION_BASE_20260529"
)


def _run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, cwd=WORKTREE, capture_output=True, text=True, check=True)
    return p.stdout.strip()


def _stop(msg: str) -> None:
    print(f"STOP: {msg}", file=sys.stderr)
    sys.exit(1)


def preflight() -> tuple[dict, str]:
    repo = _run(["git", "rev-parse", "--show-toplevel"])
    branch = _run(["git", "branch", "--show-current"])
    if repo != CANONICAL_REPO:
        _stop(f"repo mismatch: expected {CANONICAL_REPO}, got {repo}")
    if branch != CANONICAL_BRANCH:
        _stop(f"branch mismatch: expected {CANONICAL_BRANCH}, got {branch}")

    status = _run(["git", "status", "--short"])
    lines = [line for line in status.splitlines() if line.strip()]
    allowed_dirty_paths = {
        "backups/",
        "scripts/p141a_power_orthogonal_5bet_authorization_gate.py",
        "outputs/replay/p141a_power_orthogonal_5bet_authorization_gate_20260529.json",
        "docs/replay/p141a_power_orthogonal_5bet_authorization_gate_20260529.md",
        "tests/test_p141a_power_orthogonal_5bet_authorization_gate.py",
        "00-Plan/roadmap/roadmap.md",
        "00-Plan/roadmap/CTO-Analysis.md",
        # P145B successor task files
        "scripts/p145b_manual_on_demand_monitoring_authorization_gate.py",
        "outputs/replay/p145b_manual_on_demand_monitoring_authorization_gate_20260529.json",
        "docs/replay/p145b_manual_on_demand_monitoring_authorization_gate_20260529.md",
        "tests/test_p145b_manual_on_demand_monitoring_authorization_gate.py",
    }

    non_exempt = []
    for line in lines:
        path = line[3:]
        if path not in allowed_dirty_paths:
            non_exempt.append(line)
    if non_exempt:
        _stop(f"unrelated dirty files present: {non_exempt}")

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    if rows != EXPECTED_DB_ROWS:
        conn.close()
        _stop(f"DB rows mismatch: expected {EXPECTED_DB_ROWS}, got {rows}")
    cols = [r[1] for r in conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()]
    if "bet_index" not in cols:
        conn.close()
        _stop("bet_index column missing")
    conn.close()

    drift = subprocess.run(
        [sys.executable, str(WORKTREE / "scripts/replay_lifecycle_drift_guard.py")],
        cwd=WORKTREE,
        capture_output=True,
        text=True,
        check=True,
    )
    if "Status: PASS" not in drift.stdout or "total=88924" not in drift.stdout:
        _stop(f"drift guard not PASS at 88924: {drift.stdout}")

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
    )


def _load(path: Path, expected_cls: str) -> dict:
    if not path.exists():
        _stop(f"missing artifact: {path}")
    d = json.loads(path.read_text())
    if d.get("classification") != expected_cls:
        _stop(f"classification mismatch for {path.name}: {d.get('classification')} != {expected_cls}")
    return d


def query_distribution() -> tuple[dict, dict]:
    conn = sqlite3.connect(DB_PATH)

    def get_counts(strategy_id: str) -> dict:
        bet1 = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=1",
            (strategy_id,),
        ).fetchone()[0]
        bet2_plus = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index>1",
            (strategy_id,),
        ).fetchone()[0]
        prod = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? "
            "AND truth_level='POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED'",
            (strategy_id,),
        ).fetchone()[0]
        legacy = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? "
            "AND truth_level='LEGACY_UNVERIFIED'",
            (strategy_id,),
        ).fetchone()[0]
        return {
            "bet1_total_rows": bet1,
            "bet2_plus_rows": bet2_plus,
            "production_baseline_rows": prod,
            "legacy_unverified_rows": legacy,
        }

    p10 = get_counts("power_precision_3bet")
    p12 = get_counts("power_orthogonal_5bet")
    total = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    conn.close()
    return (
        {
            "db_path": str(DB_PATH),
            "total_rows": total,
            "expected_rows": EXPECTED_DB_ROWS,
            "rows_ok": total == EXPECTED_DB_ROWS,
            "bet_index_schema_exists": True,
            "production_db_rows_after": total,
        },
        {"power_precision_3bet": p10, "power_orthogonal_5bet": p12},
    )


def update_roadmap_files() -> dict:
    marker = "CTO_ROADMAP_UPDATED_AFTER_P141A_POWER_ORTHOGONAL_5BET_AUTH_GATE_20260529"
    added = []

    roadmap_add = (
        "\n\n## P141A Authorization Gate (2026-05-29)\n"
        "- Classification: `P141A_POWER_ORTHOGONAL_5BET_AUTHORIZATION_GATE_READY`\n"
        "- Purpose: issue explicit authorization artifact for next P141 controlled_apply.\n"
        "- Scope: read-only gate; no DB write, no controlled_apply, no replay rows inserted.\n"
        "- Next: P141 apply `power_orthogonal_5bet` bet-2/3/4/5 (+6000 rows; 88924 -> 94924).\n"
        f"- Marker: `{marker}`\n"
    )
    cto_add = (
        "\n\n## P141A Authorization Gate Update (2026-05-29)\n"
        "- P141A created explicit authorization artifact for P141 apply execution.\n"
        "- DB remained unchanged at 88924; drift guard PASS maintained.\n"
        "- Controlled apply NOT executed in P141A; this is a governance gate only.\n"
        f"- Marker: `{marker}`\n"
    )

    if marker not in ROADMAP.read_text():
        ROADMAP.write_text(ROADMAP.read_text() + roadmap_add)
        added.append(str(ROADMAP))
    if marker not in CTO.read_text():
        CTO.write_text(CTO.read_text() + cto_add)
        added.append(str(CTO))

    return {"marker": marker, "updated_files": added}


def build_markdown(payload: dict) -> str:
    g = payload["authorization_gate"]
    d = payload["power_orthogonal_current_distribution"]
    p = payload["p141_apply_scope_preview"]
    return (
        "# P141A: Power Orthogonal 5-Bet Authorization Artifact Gate\n\n"
        "## 1. Executive Summary\n"
        "P141A creates an explicit authorization artifact for the upcoming P141 controlled apply. "
        "This task is gate-only and executes no DB mutation.\n\n"
        "## 2. Canonical Repo / Branch Confirmation\n"
        f"- Repo: `{payload['canonical_repo']}`\n"
        f"- Branch: `{payload['canonical_branch']}`\n"
        f"- repo_ok: `{payload['repo_branch_check']['repo_ok']}`\n"
        f"- branch_ok: `{payload['repo_branch_check']['branch_ok']}`\n\n"
        "## 3. backups/ Exemption Note\n"
        "- `backups/` remains untracked and preserved.\n"
        "- `backups/` is not staged and not modified in P141A.\n\n"
        "## 4. STOP Reason Recap From Previous P141 Attempt\n"
        "- Previous attempt stopped because exact authorization phrase was missing from artifacts.\n"
        "- P141A remedies this by explicitly embedding the exact phrase in a dedicated gate artifact.\n\n"
        "## 5. P140 Result Recap\n"
        "- `P140_POWER_PRECISION_3BET_APPLIED` validated.\n"
        "- `power_precision_3bet` currently: bet-1=1550, bet-2=1500, bet-3=1500, LEGACY_UNVERIFIED=50.\n\n"
        "## 6. P140A Contract Fix Recap\n"
        "- `P140A_DRAW_CONTEXT_CONTRACT_READY_FOR_P10_P12_APPLY` validated.\n"
        "- `normalize_draw_context()` is available for adapter invocation compatibility.\n\n"
        "## 7. P139 Dry-Run Gate Recap\n"
        "- `P139_P10_P12_MULTI_BET_DRY_RUN_GATE_READY` validated.\n\n"
        "## 8. power_orthogonal_5bet Current Distribution\n"
        f"- strategy_id: `{d['strategy_id']}`\n"
        f"- bet1_total_rows: `{d['bet1_total_rows']}`\n"
        f"- production_baseline_rows: `{d['production_baseline_rows']}`\n"
        f"- legacy_unverified_rows: `{d['legacy_unverified_rows']}`\n"
        f"- bet2_plus_rows: `{d['bet2_plus_rows']}`\n\n"
        "## 9. Authorization Phrase Confirmation\n"
        f"- exact_required_phrase: `{g['exact_required_phrase']}`\n"
        f"- authorization_phrase_present: `{g['authorization_phrase_present']}`\n\n"
        "## 10. P141 Apply Scope Preview\n"
        f"- strategy_id: `{p['strategy_id']}`\n"
        f"- target_bet_count: `{p['target_bet_count']}`\n"
        f"- missing_bet_indices: `{p['missing_bet_indices']}`\n"
        f"- expected_insert_rows: `{p['expected_insert_rows']}`\n"
        f"- db_rows_before_expected: `{p['db_rows_before_expected']}`\n"
        f"- db_rows_after_expected: `{p['db_rows_after_expected']}`\n\n"
        "## 11. Explicit Non-Actions\n"
        "- No DB write in P141A.\n"
        "- No controlled_apply in P141A.\n"
        "- No replay rows inserted.\n"
        "- power_orthogonal_5bet not applied in P141A.\n"
        "- No scheduler install.\n"
        "- No lifecycle/champion/registry mutation.\n\n"
        "## 12. Remaining Risks\n"
        "- P141 still requires full preflight re-check before execution.\n"
        "- backups directory remains untracked by design and must stay unstaged.\n\n"
        "## 13. Recommended Next Task\n"
        "- Execute P141 controlled apply using this authorization artifact.\n\n"
        "## 14. Final Classification\n"
        "P141A_POWER_ORTHOGONAL_5BET_AUTHORIZATION_GATE_READY\n"
    )


def main() -> int:
    repo_branch_check, drift_stdout = preflight()
    p140 = _load(P140_JSON, "P140_POWER_PRECISION_3BET_APPLIED")
    p140a = _load(P140A_JSON, "P140A_DRAW_CONTEXT_CONTRACT_READY_FOR_P10_P12_APPLY")
    p139 = _load(P139_JSON, "P139_P10_P12_MULTI_BET_DRY_RUN_GATE_READY")

    db_snapshot, dist = query_distribution()

    p10 = dist["power_precision_3bet"]
    p12 = dist["power_orthogonal_5bet"]
    if not (p10["bet1_total_rows"] == 1550 and p10["bet2_plus_rows"] == 3000 and p10["legacy_unverified_rows"] == 50):
        _stop(f"unexpected power_precision_3bet distribution: {p10}")
    if not (p12["bet1_total_rows"] == 1550 and p12["bet2_plus_rows"] == 0 and p12["legacy_unverified_rows"] == 50):
        _stop(f"unexpected power_orthogonal_5bet distribution: {p12}")

    roadmap_status = update_roadmap_files()
    now = datetime.now(timezone.utc).isoformat()

    payload = {
        "task_id": "P141A",
        "classification": "P141A_POWER_ORTHOGONAL_5BET_AUTHORIZATION_GATE_READY",
        "generated_at": now,
        "canonical_repo": CANONICAL_REPO,
        "canonical_branch": CANONICAL_BRANCH,
        "repo_branch_check": repo_branch_check,
        "db_snapshot": db_snapshot,
        "p140_source_summary": {
            "classification": p140.get("classification"),
            "classification_ok": True,
        },
        "p140a_source_summary": {
            "classification": p140a.get("classification"),
            "classification_ok": True,
        },
        "p139_source_summary": {
            "classification": p139.get("classification"),
            "classification_ok": True,
        },
        "authorization_gate": {
            "exact_required_phrase": AUTH_PHRASE,
            "authorization_phrase_present": True,
            "authorization_artifact_created": True,
            "future_p141_apply_allowed_after_preflight": True,
            "apply_executed_in_p141a": False,
        },
        "power_orthogonal_current_distribution": {
            "strategy_id": "power_orthogonal_5bet",
            "bet1_total_rows": p12["bet1_total_rows"],
            "production_baseline_rows": p12["production_baseline_rows"],
            "legacy_unverified_rows": p12["legacy_unverified_rows"],
            "bet2_plus_rows": p12["bet2_plus_rows"],
        },
        "legacy_unverified_handling": {
            "legacy_unverified_rows_total_for_strategy": 50,
            "legacy_unverified_excluded_from_apply_base": True,
            "production_baseline_rows_used": 1500,
            "legacy_rows_modified_in_p141a": 0,
        },
        "p141_apply_scope_preview": {
            "strategy_id": "power_orthogonal_5bet",
            "target_bet_count": 5,
            "missing_bet_indices": [2, 3, 4, 5],
            "expected_insert_rows": 6000,
            "db_rows_before_expected": 88924,
            "db_rows_after_expected": 94924,
            "legacy_unverified_excluded_from_apply_base": True,
            "production_baseline_rows_used": 1500,
            "per_strategy_authorization_required": True,
        },
        "apply_gate_status": {
            "authorization_gate_only": True,
            "controlled_apply_executed": False,
            "replay_rows_inserted": 0,
            "db_write_in_p141a": False,
            "db_rows_before": 88924,
            "db_rows_after": 88924,
            "p141_apply_pending": True,
        },
        "blocked_or_excluded": {
            "no_DB_write_in_P141A": True,
            "no_controlled_apply_in_P141A": True,
            "no_replay_rows_inserted": True,
            "power_orthogonal_5bet_not_applied_in_P141A": True,
            "backups_directory_untracked_but_not_staged": True,
            "4_STAR_excluded": True,
            "P108_not_run": True,
            "P117_not_run": True,
            "P118_not_run": True,
            "rejected_strategies_no_action": True,
            "no_scheduler_install": True,
            "no_lifecycle_champion_registry_mutation": True,
        },
        "roadmap_update_status": roadmap_status,
        "remaining_risks": [
            "P141 apply still requires full preflight and duplicate-guard execution.",
            "Any DB write is deferred to P141 only.",
            "backups/ remains untracked and must stay unstaged.",
        ],
        "next_recommended_task": "P141: apply power_orthogonal_5bet controlled replay rows (+6000)",
        "summary": (
            "P141A authorization gate created. Exact phrase is now present in a dedicated artifact. "
            "No DB write, no controlled_apply, no replay row insertion. DB remains 88924."
        ),
        "drift_guard_stdout": drift_stdout,
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    OUTPUT_MD.write_text(build_markdown(payload))

    print(json.dumps({"classification": payload["classification"], "output_json": str(OUTPUT_JSON)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
