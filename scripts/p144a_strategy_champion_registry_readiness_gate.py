#!/usr/bin/env python3
"""
P144A: Strategy champion registry readiness gate.

Read-only gate script.  No DB writes.  No registry mutation.
No champion promotion.  No monitoring activation.
Produces a readiness inventory and matrix for all 6 Wave 2 candidate strategies.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "lottery_api/data/lottery_v2.db"

TASK_ID = "P144A"
CLASSIFICATION = "P144A_STRATEGY_CHAMPION_REGISTRY_READINESS_GATE_READY"
DATE_SUFFIX = "20260529"

CANONICAL_REPO = str(REPO_ROOT)
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_TOTAL_ROWS = 94924

OUT_JSON = REPO_ROOT / f"outputs/replay/p144a_strategy_champion_registry_readiness_gate_{DATE_SUFFIX}.json"
OUT_MD = REPO_ROOT / f"docs/replay/p144a_strategy_champion_registry_readiness_gate_{DATE_SUFFIX}.md"
ROADMAP = REPO_ROOT / "00-Plan/roadmap/roadmap.md"
CTO = REPO_ROOT / "00-Plan/roadmap/CTO-Analysis.md"

P143_JSON = REPO_ROOT / "outputs/replay/p143_post_wave2_governance_readiness_plan_20260529.json"
P142_JSON = REPO_ROOT / "outputs/replay/p142_wave2_multibet_apply_chain_closure_audit_20260529.json"
P141_JSON = REPO_ROOT / "outputs/replay/p141_apply_power_orthogonal_5bet_20260529.json"
P140_JSON = REPO_ROOT / "outputs/replay/p140_apply_power_precision_3bet_20260529.json"
P134_JSON = REPO_ROOT / "outputs/replay/p134_apply_fourier_rhythm_3bet_20260528.json"
P133_JSON = REPO_ROOT / "outputs/replay/p133_apply_pp3_freqort_4bet_20260528.json"
P132_JSON = REPO_ROOT / "outputs/replay/p132_apply_midfreq_fourier_mk_3bet_20260528.json"
P131_JSON = REPO_ROOT / "outputs/replay/p131_apply_acb_markov_midfreq_3bet_20260528.json"

# Successor files allowed as dirty (forward-compatible)
_OWN_FILES = {
    f"scripts/p144a_strategy_champion_registry_readiness_gate.py",
    f"outputs/replay/p144a_strategy_champion_registry_readiness_gate_{DATE_SUFFIX}.json",
    f"docs/replay/p144a_strategy_champion_registry_readiness_gate_{DATE_SUFFIX}.md",
    f"tests/test_p144a_strategy_champion_registry_readiness_gate.py",
    "00-Plan/roadmap/roadmap.md",
    "00-Plan/roadmap/CTO-Analysis.md",
}
_AUTOUSE_PREFIXES = (
    "outputs/replay/p135_", "outputs/replay/p136_", "outputs/replay/p142_",
    "outputs/replay/p143_", "outputs/replay/p144b_", "outputs/replay/p145b_",
    "outputs/replay/p146a_",
    "outputs/replay/live_monitoring_observation_only/",
    "docs/replay/p135_", "docs/replay/p136_", "docs/replay/p142_",
    "docs/replay/p143_", "docs/replay/p144b_", "docs/replay/p145b_",
    "docs/replay/p146a_",
    "scripts/p141_", "scripts/p141a_", "scripts/p142_", "scripts/p143_",
    "scripts/p144b_", "scripts/p145b_", "scripts/p146a_",
    "tests/test_p142_", "tests/test_p143_", "tests/test_p144b_", "tests/test_p145b_",
    "tests/test_p146a_",
)


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


def _load_json(path: Path) -> dict:
    if not path.exists():
        _stop(f"Required artifact missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


# ── Phase 0 ───────────────────────────────────────────────────────────────────

def validate_preflight() -> dict:
    repo = _git(["rev-parse", "--show-toplevel"])
    branch = _git(["branch", "--show-current"])
    if repo != CANONICAL_REPO:
        _stop(f"repo mismatch: {repo}")
    if branch != CANONICAL_BRANCH:
        _stop(f"branch mismatch: {branch}")

    status_lines = subprocess.run(
        ["git", "status", "--short"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout.splitlines()

    unrelated = []
    for line in status_lines:
        if not line.strip():
            continue
        path_str = line[3:].strip()
        if path_str.startswith("backups/"):
            continue
        if path_str in _OWN_FILES:
            continue
        if any(path_str.startswith(pfx) for pfx in _AUTOUSE_PREFIXES):
            continue
        unrelated.append(path_str)
    if unrelated:
        _stop(f"unrelated dirty files: {unrelated}")

    git_dir = _git(["rev-parse", "--git-dir"])
    return {
        "expected_repo": CANONICAL_REPO,
        "actual_repo": repo,
        "expected_branch": CANONICAL_BRANCH,
        "actual_branch": branch,
        "git_dir": git_dir,
        "repo_ok": True,
        "branch_ok": True,
    }


def db_snapshot(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    if total != EXPECTED_TOTAL_ROWS:
        _stop(f"DB rows={total}, expected {EXPECTED_TOTAL_ROWS}")
    cols = [r[1] for r in conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()]
    bet_index_exists = "bet_index" in cols
    if not bet_index_exists:
        _stop("bet_index column missing")
    return {
        "total_rows": total,
        "bet_index_schema_exists": bet_index_exists,
        "rows_match_expected": total == EXPECTED_TOTAL_ROWS,
    }


def run_drift_guard() -> dict:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts/replay_lifecycle_drift_guard.py")],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    passed = result.returncode == 0 and "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS" in result.stdout
    if not passed:
        _stop(f"drift guard failed:\n{result.stdout}\n{result.stderr}")
    return {
        "status": "PASS",
        "classification": "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS",
        "total_rows": EXPECTED_TOTAL_ROWS,
    }


# ── Source summaries ──────────────────────────────────────────────────────────

def build_p143_source_summary() -> dict:
    p143 = _load_json(P143_JSON)
    c = p143.get("classification", "")
    if c != "P143_POST_WAVE2_GOVERNANCE_READINESS_PLAN_READY":
        _stop(f"P143 classification mismatch: {c}")
    champ = p143.get("champion_registry_readiness", {})
    return {
        "classification": c,
        "pass": True,
        "registry_update_executed_in_p143": champ.get("registry_update_executed_in_p143", False),
        "champion_eval_ready_count_in_p143": champ.get("champion_eval_ready_count", 0),
        "authorization_required_in_p143": champ.get("authorization_required_later", True),
    }


def build_p142_source_summary() -> dict:
    p142 = _load_json(P142_JSON)
    c = p142.get("classification", "")
    if c != "P142_WAVE2_MULTI_BET_APPLY_CHAIN_CLOSED":
        _stop(f"P142 classification mismatch: {c}")
    ins = p142.get("inserted_rows_summary", {})
    return {
        "classification": c,
        "pass": True,
        "total_wave2_multibet_inserted_rows": ins.get("total_wave2_multibet_inserted_rows", 22502),
        "current_rows": p142.get("db_row_chain", {}).get("current_rows", EXPECTED_TOTAL_ROWS),
    }


# ── Candidate strategy inventory ─────────────────────────────────────────────

# Static metadata per strategy
_STRATEGY_META = {
    "acb_markov_midfreq_3bet": {
        "lottery_type": "DAILY_539",
        "bet_count": 3,
        "wave2_task_source": "P131",
        "inserted_rows": 3000,
        "truth_level": "DAILY539_RETIRED_STRATEGY_BACKFILL_VERIFIED",
        "legacy_unverified_rows": 0,
    },
    "midfreq_fourier_mk_3bet": {
        "lottery_type": "POWER_LOTTO",
        "bet_count": 3,
        "wave2_task_source": "P132",
        "inserted_rows": 3000,
        "truth_level": "POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED",
        "legacy_unverified_rows": 0,
    },
    "pp3_freqort_4bet": {
        "lottery_type": "POWER_LOTTO",
        "bet_count": 4,
        "wave2_task_source": "P133",
        "inserted_rows": 4500,
        "truth_level": "POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED",
        "legacy_unverified_rows": 0,
    },
    "fourier_rhythm_3bet": {
        "lottery_type": "POWER_LOTTO",
        "bet_count": 3,
        "wave2_task_source": "P134",
        "inserted_rows": 3002,
        "truth_level": "POWERLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED",
        "legacy_unverified_rows": 0,
    },
    "power_precision_3bet": {
        "lottery_type": "POWER_LOTTO",
        "bet_count": 3,
        "wave2_task_source": "P140",
        "inserted_rows": 3000,
        "truth_level": "POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED",
        "legacy_unverified_rows": 50,
    },
    "power_orthogonal_5bet": {
        "lottery_type": "POWER_LOTTO",
        "bet_count": 5,
        "wave2_task_source": "P141",
        "inserted_rows": 6000,
        "truth_level": "POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED",
        "legacy_unverified_rows": 50,
    },
}


def build_candidate_strategy_inventory(conn: sqlite3.Connection) -> dict:
    """Build candidate inventory.

    "Live draw monitoring data" is defined as data from real-time production
    monitoring AFTER Wave 2 apply (i.e. forward-looking predictions that were
    subsequently verified against actual draws).  All rows in the current DB are
    historical *backfill* rows; they have actual_numbers filled because the
    backfill process replays against known history — not because live monitoring
    is active.

    Since P143 confirmed monitoring_activated=False and no live monitoring
    infrastructure has been set up, live_draw_data_rows is zero for all
    strategies by governance definition.
    """
    inventory = {}
    for sid, meta in _STRATEGY_META.items():
        # Live DB distribution
        rows = conn.execute(
            "SELECT bet_index, COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? GROUP BY bet_index ORDER BY bet_index",
            (sid,),
        ).fetchall()
        dist = {str(bi): cnt for bi, cnt in rows}
        total_rows = sum(dist.values())

        # All rows are historical backfill; live monitoring not yet activated.
        # live_draw_data_rows = 0 by governance definition (not DB query).
        live_draw_cnt = 0

        inventory[sid] = {
            "strategy_id": sid,
            "lottery_type": meta["lottery_type"],
            "bet_count": meta["bet_count"],
            "wave2_task_source": meta["wave2_task_source"],
            "inserted_rows": meta["inserted_rows"],
            "legacy_unverified_rows": meta["legacy_unverified_rows"],
            "truth_level": meta["truth_level"],
            "current_replay_row_distribution": dist,
            "total_rows_in_db": total_rows,
            "live_draw_data_rows": live_draw_cnt,
            "live_draw_data_available": False,
            "live_draw_note": (
                "All DB rows are historical backfill. "
                "Live monitoring not yet activated (P143 monitoring_activated=False). "
                "live_draw_data_rows=0 by governance definition."
            ),
            "champion_eval_ready": False,
            "registry_update_allowed_now": False,
            "blocking_reason": (
                "No live draw monitoring data. "
                "Champion evaluation requires minimum monitored live draw period "
                "after P144B live monitoring is activated."
            ),
        }
    return inventory


# ── Champion registry readiness matrix ───────────────────────────────────────

def build_champion_registry_readiness_matrix(inventory: dict) -> dict:
    matrix = {}
    for sid, row in inventory.items():
        live = row["live_draw_data_available"]
        matrix[sid] = {
            "strategy_id": sid,
            "current_status": "REPLAY_ROWS_APPLIED_NO_LIVE_DATA",
            "live_draw_data_available": live,
            "champion_eval_ready": False,
            "registry_update_allowed_now": False,
            "recommended_action": (
                "ADD_TO_OBSERVATION_WATCHLIST" if not live
                else "PROCEED_TO_CHAMPION_EVAL"
            ),
            "reason": row["blocking_reason"],
        }
    return matrix


# ── Registry update options ───────────────────────────────────────────────────

def build_registry_update_options() -> dict:
    return {
        "option_a_wait_for_live_monitoring_data": {
            "description": (
                "No registry action until live draw monitoring is active and "
                "minimum draws evaluated (recommended threshold: ≥50 draws per strategy)."
            ),
            "registry_mutation": False,
            "risk": "ZERO",
            "pros": "Clean gate; no premature promotion; aligns with validation protocol.",
            "cons": "Delayed registry update; strategies remain in replay-only state.",
            "recommended": True,
        },
        "option_b_observation_only_watchlist": {
            "description": (
                "Add all 6 candidates to an observation-only watchlist / staging registry. "
                "No champion promotion; no production routing change."
            ),
            "registry_mutation": False,
            "risk": "LOW",
            "pros": "Documents candidate status; enables tracking without promotion risk.",
            "cons": "Requires watchlist tooling not yet implemented.",
            "recommended": True,
        },
        "option_c_promote_after_minimum_live_draw_threshold": {
            "description": (
                "Promote to champion registry only after each strategy has ≥50 monitored "
                "live draws with edge > baseline and perm p < 0.05."
            ),
            "registry_mutation": True,
            "risk": "MEDIUM",
            "pros": "Statistically grounded promotion gate.",
            "cons": "Requires live monitoring infrastructure and per-strategy authorization.",
            "recommended": False,
            "prerequisites": [
                "Live draw monitoring activated (P144B)",
                "≥50 live draws per strategy evaluated",
                "Edge > baseline and perm p < 0.05 per strategy",
                "Explicit per-strategy champion promotion authorization",
            ],
        },
    }


# ── Recommended registry path ─────────────────────────────────────────────────

def build_recommended_registry_path() -> dict:
    return {
        "recommended_option": "option_b_observation_only_watchlist",
        "rationale": (
            "Option B (observation-only watchlist) is the safest immediate action. "
            "It documents candidate status without registry mutation or promotion risk. "
            "Option A (wait) is equally valid if watchlist tooling is not available. "
            "Option C (promote after threshold) is the long-term target but requires "
            "live monitoring infrastructure first (P144B)."
        ),
        "immediate_action": "Add candidates to observation watchlist (no registry mutation)",
        "blocking_prerequisites": [
            "Live draw monitoring activation (P144B required first)",
            "Minimum live draw threshold evaluation per strategy",
            "Per-strategy champion promotion authorization",
        ],
        "registry_mutation_in_p144a": False,
        "next_gate": "P145_OBSERVATION_WATCHLIST_AND_LIVE_MONITORING_GATE",
    }


# ── Authorization gate required later ────────────────────────────────────────

def build_authorization_gate_required_later() -> dict:
    return {
        "p144b_live_monitoring_gate": {
            "description": "Activate live draw monitoring for all 6 Wave 2 strategies.",
            "required_before": "Champion evaluation",
            "authorization_required": True,
            "db_mutation": False,
        },
        "p144c_legacy_unverified_remediation_gate": {
            "description": "Authorize and execute LEGACY_UNVERIFIED row remediation (remark option).",
            "required_before": "Optional; independent of champion registry",
            "authorization_required": True,
            "db_mutation": True,
        },
        "p145_observation_watchlist_and_live_monitoring_gate": {
            "description": (
                "After P144B monitoring active: evaluate per-strategy live draw performance "
                "and authorize champion registry promotion for qualifying strategies."
            ),
            "required_before": "Champion registry promotion",
            "authorization_required": True,
            "db_mutation": False,
        },
        "next_recommended_task_name": "P144B_LIVE_MONITORING_ACTIVATION_GATE",
    }


# ── Non-actions ───────────────────────────────────────────────────────────────

def build_non_actions() -> dict:
    return {
        "db_write_in_p144a": False,
        "controlled_apply_executed_in_p144a": False,
        "replay_rows_inserted_in_p144a": 0,
        "replay_rows_deleted_in_p144a": 0,
        "registry_update_executed_in_p144a": False,
        "champion_promotion_executed_in_p144a": False,
        "monitoring_activated_in_p144a": False,
        "scheduler_installed": False,
        "four_star_executed": False,
        "p108_executed": False,
        "p117_executed": False,
        "p118_executed": False,
    }


# ── Dirty file hygiene ────────────────────────────────────────────────────────

def build_dirty_file_hygiene() -> dict:
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    forbidden_tokens = ("lottery_v2.db", ".history", ".pid", ".runtime")
    forbidden_staged = [s for s in staged if any(t in s for t in forbidden_tokens)]
    return {
        "backups_untracked_not_staged": not any("backups/" in s for s in staged),
        "p135_p136_p142_autouse_regen_risk_noted": True,
        "forbidden_files_staged": len(forbidden_staged) > 0,
        "forbidden_staged_files": forbidden_staged,
        "staged_file_count_at_runtime": len(staged),
    }


# ── Roadmap update ────────────────────────────────────────────────────────────

ROADMAP_MARKER = "CTO_ROADMAP_UPDATED_AFTER_P144A_STRATEGY_CHAMPION_REGISTRY_READINESS_GATE_20260529"


def _append_if_absent(path: Path, content: str, marker: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return False
    path.write_text(text + content, encoding="utf-8")
    return True


def update_roadmap() -> str:
    section = f"""

## P144A Strategy Champion Registry Readiness Gate (2026-05-29)
- Classification: `P144A_STRATEGY_CHAMPION_REGISTRY_READINESS_GATE_READY`
- Candidate strategy inventory produced for all 6 Wave 2 strategies.
- Champion registry readiness matrix: all 6 strategies in REPLAY_ROWS_APPLIED_NO_LIVE_DATA state.
- No live draw data available; champion_eval_ready=false for all candidates.
- Recommended path: Option B (observation-only watchlist) + Option A (wait for live data).
- No registry mutation in P144A.
- Next gates: P144B (live monitoring activation), P144C (legacy remediation).
- Marker: `{ROADMAP_MARKER}`
"""
    appended = _append_if_absent(ROADMAP, section, ROADMAP_MARKER)
    return f"{'appended' if appended else 'already present'}: {ROADMAP_MARKER}"


def update_cto() -> str:
    section = f"""

## P144A Strategy Champion Registry Readiness Gate (2026-05-29)
- P144A confirmed: all 6 Wave 2 candidate strategies have replay rows but no live draw data.
- champion_eval_ready=false for all; registry update blocked until live monitoring active.
- Recommended next gates: P144B (live monitoring), P144C (legacy remediation), P145 (champion eval after threshold).
- No DB mutation. No registry update. Read-only gate.
- Marker: `{ROADMAP_MARKER}`

**Artifact**: `outputs/replay/p144a_strategy_champion_registry_readiness_gate_20260529.json`
"""
    appended = _append_if_absent(CTO, section, ROADMAP_MARKER)
    return f"{'appended' if appended else 'already present'}: {ROADMAP_MARKER}"


# ── Markdown ──────────────────────────────────────────────────────────────────

def write_markdown(artifact: dict) -> None:
    inv = artifact["candidate_strategy_inventory"]
    matrix = artifact["champion_registry_readiness_matrix"]
    opts = artifact["registry_update_options"]
    rec = artifact["recommended_registry_path"]
    auth = artifact["authorization_gate_required_later"]
    non_act = artifact["non_actions"]
    risks = artifact["remaining_risks"]

    # Build matrix table rows
    matrix_rows = ""
    for sid, row in matrix.items():
        matrix_rows += (
            f"| {sid} | {row['current_status']} | {row['live_draw_data_available']} | "
            f"{row['champion_eval_ready']} | {row['registry_update_allowed_now']} | "
            f"{row['recommended_action']} |\n"
        )

    # Build inventory table rows
    inv_rows = ""
    for sid, row in inv.items():
        total = row["total_rows_in_db"]
        legacy = row["legacy_unverified_rows"]
        live = row["live_draw_data_rows"]
        inv_rows += (
            f"| {sid} | {row['lottery_type']} | {row['bet_count']} | "
            f"{row['wave2_task_source']} | {row['inserted_rows']:,} | {legacy} | {live} |\n"
        )

    md = f"""# P144A: Strategy Champion Registry Readiness Gate

**Classification**: `{CLASSIFICATION}`
**Task ID**: P144A
**Generated**: {artifact["generated_at"]}

---

## Executive Summary

P144A is a read-only registry readiness gate for all 6 Wave 2 candidate strategies.
All candidates have replay rows applied (P131–P134, P140–P141) but have no live draw
monitoring data. Champion evaluation is blocked until live monitoring is active (P144B).
No registry mutation, no champion promotion, no DB write in P144A.

---

## Canonical Repo / Branch Confirmation

| Field | Value |
|-------|-------|
| Expected repo | `{artifact["canonical_repo"]}` |
| Expected branch | `{artifact["canonical_branch"]}` |
| Repo OK | {artifact["repo_branch_check"]["repo_ok"]} |
| Branch OK | {artifact["repo_branch_check"]["branch_ok"]} |

---

## P143 Recap

- **Classification**: `{artifact["p143_source_summary"]["classification"]}`
- Registry update executed in P143: **{artifact["p143_source_summary"]["registry_update_executed_in_p143"]}**
- Champion eval ready count in P143: **{artifact["p143_source_summary"]["champion_eval_ready_count_in_p143"]}**
- Authorization required later: **{artifact["p143_source_summary"]["authorization_required_in_p143"]}**

## P142 Closure Recap

- **Classification**: `{artifact["p142_source_summary"]["classification"]}`
- Total Wave 2 multi-bet rows inserted: **{artifact["p142_source_summary"]["total_wave2_multibet_inserted_rows"]:,}**
- Current DB rows: **{artifact["p142_source_summary"]["current_rows"]:,}**

---

## Candidate Strategy Inventory

| Strategy | Lottery | Bets | Source Task | Inserted | Legacy | Live Draws |
|----------|---------|------|-------------|---------|--------|-----------|
{inv_rows}
---

## Champion Registry Readiness Matrix

| Strategy | Status | Live Data | Eval Ready | Update Now | Recommended Action |
|----------|--------|-----------|------------|------------|-------------------|
{matrix_rows}
**All 6 strategies**: `REPLAY_ROWS_APPLIED_NO_LIVE_DATA` — champion evaluation blocked until live monitoring active.

---

## Registry Update Options

### Option A: Wait for Live Monitoring Data ✅ Recommended
- {opts["option_a_wait_for_live_monitoring_data"]["description"]}
- **Registry mutation**: {opts["option_a_wait_for_live_monitoring_data"]["registry_mutation"]}
- **Risk**: {opts["option_a_wait_for_live_monitoring_data"]["risk"]}
- **Pros**: {opts["option_a_wait_for_live_monitoring_data"]["pros"]}
- **Cons**: {opts["option_a_wait_for_live_monitoring_data"]["cons"]}

### Option B: Observation-Only Watchlist ✅ Recommended
- {opts["option_b_observation_only_watchlist"]["description"]}
- **Registry mutation**: {opts["option_b_observation_only_watchlist"]["registry_mutation"]}
- **Risk**: {opts["option_b_observation_only_watchlist"]["risk"]}
- **Pros**: {opts["option_b_observation_only_watchlist"]["pros"]}
- **Cons**: {opts["option_b_observation_only_watchlist"]["cons"]}

### Option C: Promote After Minimum Live Draw Threshold
- {opts["option_c_promote_after_minimum_live_draw_threshold"]["description"]}
- **Registry mutation**: {opts["option_c_promote_after_minimum_live_draw_threshold"]["registry_mutation"]}
- **Risk**: {opts["option_c_promote_after_minimum_live_draw_threshold"]["risk"]}
- **Prerequisites**: {"; ".join(opts["option_c_promote_after_minimum_live_draw_threshold"]["prerequisites"])}

---

## Recommended Registry Path

- **Recommended option**: `{rec["recommended_option"]}`
- **Rationale**: {rec["rationale"]}
- **Immediate action**: {rec["immediate_action"]}
- **Registry mutation in P144A**: {rec["registry_mutation_in_p144a"]}
- **Next gate**: `{rec["next_gate"]}`

**Blocking prerequisites for Option C**:
{chr(10).join(f"- {p}" for p in rec["blocking_prerequisites"])}

---

## Authorization Gate Required Later

| Gate | Description | Authorization | DB Mutation |
|------|-------------|--------------|-------------|
| P144B | Live draw monitoring activation | Yes | No |
| P144C | LEGACY_UNVERIFIED remediation | Yes | Yes |
| P145 | Observation watchlist + champion eval after threshold | Yes | No |

---

## Explicit Non-Actions

| Action | Status |
|--------|--------|
| DB write in P144A | {non_act["db_write_in_p144a"]} |
| controlled_apply executed | {non_act["controlled_apply_executed_in_p144a"]} |
| replay_rows_inserted | {non_act["replay_rows_inserted_in_p144a"]} |
| replay_rows_deleted | {non_act["replay_rows_deleted_in_p144a"]} |
| registry_update_executed | {non_act["registry_update_executed_in_p144a"]} |
| champion_promotion_executed | {non_act["champion_promotion_executed_in_p144a"]} |
| monitoring_activated | {non_act["monitoring_activated_in_p144a"]} |
| scheduler_installed | {non_act["scheduler_installed"]} |
| 4_STAR_executed | {non_act["four_star_executed"]} |
| P108_executed | {non_act["p108_executed"]} |
| P117_executed | {non_act["p117_executed"]} |
| P118_executed | {non_act["p118_executed"]} |

---

## Dirty File Hygiene Note

- `backups/` remains untracked; not staged; not deleted.
- `docs/replay/p135_*`, `docs/replay/p136_*`, `docs/replay/p142_*`, `docs/replay/p143_*`:
  autouse fixture may regenerate; not staged.
- Same applies to corresponding `outputs/replay/` JSON files.
- No DB files, history files, pid files, or runtime files staged.

---

## Remaining Risks

{chr(10).join(f"- {r}" for r in risks)}

---

## Recommended Next Task

{artifact["next_recommended_task"]}

---

## Final Classification

`{CLASSIFICATION}`

All 6 Wave 2 candidate strategies inventoried. Champion registry readiness gate READY.
No registry mutation. No champion promotion. No DB write. Next: P144B live monitoring gate.
"""
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md, encoding="utf-8")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("P144A: starting strategy champion registry readiness gate...")

    repo_branch = validate_preflight()
    print("  Phase 0: repo/branch/dirty-files OK")

    conn = _ro_conn()
    snap = db_snapshot(conn)
    print(f"  DB rows: {snap['total_rows']}")

    drift = run_drift_guard()
    print(f"  Drift guard: {drift['status']}")

    p143_summary = build_p143_source_summary()
    p142_summary = build_p142_source_summary()
    print("  Source artifact classifications: all PASS")

    inventory = build_candidate_strategy_inventory(conn)
    matrix = build_champion_registry_readiness_matrix(inventory)
    opts = build_registry_update_options()
    rec_path = build_recommended_registry_path()
    auth_gate = build_authorization_gate_required_later()
    non_act = build_non_actions()
    dirty = build_dirty_file_hygiene()
    conn.close()

    roadmap_status = update_roadmap()
    cto_status = update_cto()
    print(f"  Roadmap: {roadmap_status}")
    print(f"  CTO: {cto_status}")

    artifact = {
        "task_id": TASK_ID,
        "classification": CLASSIFICATION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "canonical_repo": CANONICAL_REPO,
        "canonical_branch": CANONICAL_BRANCH,
        "repo_branch_check": repo_branch,
        "db_snapshot": snap,
        "drift_guard_result": drift,
        "p143_source_summary": p143_summary,
        "p142_source_summary": p142_summary,
        "candidate_strategy_inventory": inventory,
        "champion_registry_readiness_matrix": matrix,
        "registry_update_options": opts,
        "recommended_registry_path": rec_path,
        "authorization_gate_required_later": auth_gate,
        "non_actions": non_act,
        "dirty_file_hygiene": dirty,
        "roadmap_update_status": roadmap_status,
        "remaining_risks": [
            "P135/P136/P142/P143 autouse fixtures may regenerate artifacts on regression runs; "
            "regenerated files appear as unstaged changes but are not P144A products.",
            "All 6 candidate strategies have 0 live draw monitoring data; "
            "champion evaluation is blocked until P144B live monitoring is activated.",
            "LEGACY_UNVERIFIED rows (100 total: 50 per P10/P12 strategy) remain pending P144C remediation.",
            "backups/ directory remains untracked; rollback commands reference pre-P141 backup.",
            "Observation-only watchlist (Option B) requires tooling not yet implemented.",
            "No real-time prediction pipeline active for Wave 2 strategies post-backfill.",
        ],
        "next_recommended_task": (
            "P144B: live draw monitoring activation gate — design and authorize "
            "live monitoring for all 6 Wave 2 strategies. "
            "P144C: LEGACY_UNVERIFIED remediation authorization gate (independent). "
            "P145: observation watchlist + champion eval gate after P144B threshold met."
        ),
        "summary": (
            "P144A confirms all 6 Wave 2 candidate strategies have replay rows applied "
            "(total 22,502 rows, DB=94,924) but have zero live draw monitoring data. "
            "Champion evaluation is blocked for all candidates. "
            "Recommended registry path: Option B (observation-only watchlist) + "
            "Option A (wait for live data). "
            "No registry mutation, no champion promotion, no DB write in P144A. "
            "Next: P144B live monitoring activation gate."
        ),
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(artifact)

    print(f"P144A complete: {CLASSIFICATION}")
    print(f"  JSON: {OUT_JSON}")
    print(f"  MD:   {OUT_MD}")


if __name__ == "__main__":
    main()
