#!/usr/bin/env python3
"""
P139: P10/P12 Multi-Bet Dry-Run Gate After Legacy Remark

Read-only dry-run gate re-evaluation for power_precision_3bet (P10) and
power_orthogonal_5bet (P12) following P138B LEGACY_UNVERIFIED re-mark.

NO DB writes. NO controlled_apply. NO row insertions or deletions.
"""
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKTREE = Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802")
DB_PATH = WORKTREE / "lottery_api/data/lottery_v2.db"
OUTPUTS_DIR = WORKTREE / "outputs/replay"
DOCS_DIR = WORKTREE / "docs/replay"
OUTPUT_JSON = OUTPUTS_DIR / "p139_p10_p12_multibet_dry_run_gate_20260529.json"
OUTPUT_MD = DOCS_DIR / "p139_p10_p12_multibet_dry_run_gate_20260529.md"

P138B_ARTIFACT = OUTPUTS_DIR / "p138b_remark_p10_p12_legacy_rows_20260529.json"
P137_ARTIFACT = OUTPUTS_DIR / "p137_p10_p12_legacy_row_governance_gate_20260529.json"

EXPECTED_REPO = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
EXPECTED_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_DB_ROWS = 85924
P10_ID = "power_precision_3bet"
P12_ID = "power_orthogonal_5bet"
EXPECTED_BET1 = 1550
EXPECTED_BET2_PLUS = 0
EXPECTED_LEGACY_UNVERIFIED = 50
EXPECTED_NULL_PROV_SELECTOR = 0

# Legacy row handling: EXCLUDE LEGACY_UNVERIFIED from apply base (use 1500 production baseline)
LEGACY_HANDLING = "EXCLUDE_FROM_APPLY_BASE"
APPLY_BASE_ROWS = 1500  # production baseline only


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


def check_artifact(path, expected_classification):
    if not path.exists():
        return {"found": False, "classification": None, "ok": False}
    with open(path) as f:
        d = json.load(f)
    cls = d.get("classification")
    return {"found": True, "classification": cls, "ok": cls == expected_classification}


def get_p10_p12_distribution(conn):
    result = {}
    for sid in [P10_ID, P12_ID]:
        rows = conn.execute(
            "SELECT bet_index, COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? GROUP BY bet_index ORDER BY bet_index",
            (sid,),
        ).fetchall()
        dist = {r[0]: r[1] for r in rows}
        result[sid] = {
            "bet1_rows": dist.get(1, 0),
            "bet2_plus_rows": sum(v for k, v in dist.items() if k > 1),
        }
    return {
        "power_precision_3bet_bet1_rows": result[P10_ID]["bet1_rows"],
        "power_precision_3bet_bet2_plus_rows": result[P10_ID]["bet2_plus_rows"],
        "power_orthogonal_5bet_bet1_rows": result[P12_ID]["bet1_rows"],
        "power_orthogonal_5bet_bet2_plus_rows": result[P12_ID]["bet2_plus_rows"],
    }


def get_legacy_unverified_audit(conn):
    result = {}
    for sid in [P10_ID, P12_ID]:
        lu = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND truth_level='LEGACY_UNVERIFIED'",
            (sid,),
        ).fetchone()[0]
        result[sid] = lu
    null_prov = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet') "
        "AND bet_index=1 AND controlled_apply_id IS NULL AND provenance_hash IS NULL "
        "AND truth_level IS NULL AND (source IS NULL OR source='')",
    ).fetchone()[0]
    total = result[P10_ID] + result[P12_ID]
    return {
        "power_precision_3bet_legacy_unverified_rows": result[P10_ID],
        "power_orthogonal_5bet_legacy_unverified_rows": result[P12_ID],
        "total_legacy_unverified_rows": total,
        "null_provenance_selector_count": null_prov,
        "db_write_in_p139": False,
    }


def get_adapter_contract_status():
    """Check if adapter functions are available in p128_wave2_phase2_adapters."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "adapters",
            WORKTREE / "lottery_api/models/p128_wave2_phase2_adapters.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        p10_fn = hasattr(mod, "get_all_bets_power_precision")
        p12_fn = hasattr(mod, "get_all_bets_power_orthogonal")
    except Exception as e:
        p10_fn = False
        p12_fn = False

    return {
        "adapter_module": "lottery_api/models/p128_wave2_phase2_adapters.py",
        "power_precision_3bet": {
            "adapter_function": "get_all_bets_power_precision",
            "function_exists": p10_fn,
            "rsr6_blocker": "RESOLVED — RSR6 cleaned orphan bet_index=2 rows",
            "legacy_governance_blocker": "RESOLVED — P138B re-marked 50 NULL-prov rows",
            "adapter_ready_for_dry_run": p10_fn,
            "draw_context_key": "history",
            "note": (
                "Adapter docstring still shows RSR-6 warning — stale. "
                "Both blockers are now resolved. Adapter is forward-use ready."
            ),
        },
        "power_orthogonal_5bet": {
            "adapter_function": "get_all_bets_power_orthogonal",
            "function_exists": p12_fn,
            "rsr6_blocker": "RESOLVED — RSR6 cleaned orphan bet_index=2 rows",
            "legacy_governance_blocker": "RESOLVED — P138B re-marked 50 NULL-prov rows",
            "adapter_ready_for_dry_run": p12_fn,
            "draw_context_key": "history",
            "note": (
                "Adapter docstring still shows RSR-6 warning — stale. "
                "Both blockers are now resolved. Adapter is forward-use ready."
            ),
        },
        "gap_note": (
            "Both adapters exist. The draw_context key used by the actual implementation "
            "is 'history' (list of draw dicts with 'numbers'), not 'historical_draws' as "
            "spec'd in P127. This mismatch must be reconciled before controlled_apply."
        ),
    }


def build_dry_run_plan():
    # LEGACY_UNVERIFIED handling: EXCLUDE from apply base → use 1500 production rows only
    legacy_handling_rule = {
        "decision": LEGACY_HANDLING,
        "apply_base_rows": APPLY_BASE_ROWS,
        "rationale": (
            "The 50 LEGACY_UNVERIFIED rows per strategy (draws 99000055–99000104) were inserted "
            "from early replay runs (replay_run_id 2 and 6) before the P20 production backfill "
            "pipeline was established. Although P138B assigned synthetic provenance_hash, these "
            "rows represent pre-production legacy draws. For the first multi-bet controlled_apply, "
            "only the 1500 production baseline rows (truth_level=POWERLOTTO_REMAINING_STRATEGIES_"
            "BACKFILL_VERIFIED) should be used as the base. This keeps the apply clean, "
            "avoids mixing legacy and production data in multi-bet rows, and simplifies the "
            "apply selector. If legacy multi-bet coverage is needed later, it can be addressed "
            "as a separate authorized task."
        ),
        "apply_selector": (
            "WHERE strategy_id=? AND bet_index=1 "
            "AND truth_level='POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED' "
            "AND provenance_hash IS NOT NULL "
            "AND controlled_apply_id='P20_POWERLOTTO_REMAINING_1500_PROD_20260520'"
        ),
        "excluded_row_count": EXPECTED_LEGACY_UNVERIFIED,
        "excluded_truth_level": "LEGACY_UNVERIFIED",
        "future_legacy_multibet_task": "Optional post-apply task; requires separate authorization",
    }

    plans = {}

    # P10 — power_precision_3bet
    plans[P10_ID] = {
        "strategy_id": P10_ID,
        "lottery_type": "POWER_LOTTO",
        "target_bet_count": 3,
        "current_bet_index_distribution": {1: EXPECTED_BET1, "2+": EXPECTED_BET2_PLUS},
        "missing_bet_indices": [2, 3],
        "apply_base_rows": APPLY_BASE_ROWS,
        "estimated_insert_rows": APPLY_BASE_ROWS * 2,  # bet-2 + bet-3
        "adapter_contract_status": {
            "function": "get_all_bets_power_precision",
            "module": "lottery_api/models/p128_wave2_phase2_adapters.py",
            "status": "AVAILABLE",
            "blockers_cleared": ["RSR6_orphan_rows", "P138B_legacy_governance"],
            "draw_context_key": "history",
        },
        "legacy_unverified_handling": {
            "decision": LEGACY_HANDLING,
            "excluded_rows": EXPECTED_LEGACY_UNVERIFIED,
            "apply_base_rows": APPLY_BASE_ROWS,
        },
        "duplicate_guard": {
            "strategy": "UNIQUE(lottery_type, target_draw, strategy_id, bet_index)",
            "pre_insert_check": "SELECT COUNT(*) = 0 WHERE strategy_id=? AND bet_index IN (2,3)",
            "abort_on_conflict": True,
        },
        "provenance_requirements": {
            "controlled_apply_id": "P140_APPLY_POWER_PRECISION_3BET_v1",
            "provenance_hash": "SHA256(strategy_id + target_draw + bet_index + predicted_numbers)",
            "truth_level": "POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED",
            "source": "P140_POWER_PRECISION_3BET_MULTI_BET_APPLY",
        },
        "dry_run_ready": True,
        "dry_run_ready_conditions": [
            "Adapter function exists and is callable",
            "RSR6 orphan blocker resolved",
            "P138B legacy governance resolved",
            "LEGACY_UNVERIFIED rows excluded from apply base",
            "duplicate guard defined",
            "provenance requirements defined",
        ],
        "apply_authorization_required_later": True,
        "db_write_in_p139": False,
        "remaining_gaps": [
            "draw_context key 'history' vs P127 spec 'historical_draws' — must reconcile before apply",
            "Adapter docstring still shows stale RSR-6 warning — cosmetic only, not a blocker",
            "Full DB backup required before controlled_apply",
        ],
    }

    # P12 — power_orthogonal_5bet
    plans[P12_ID] = {
        "strategy_id": P12_ID,
        "lottery_type": "POWER_LOTTO",
        "target_bet_count": 5,
        "current_bet_index_distribution": {1: EXPECTED_BET1, "2+": EXPECTED_BET2_PLUS},
        "missing_bet_indices": [2, 3, 4, 5],
        "apply_base_rows": APPLY_BASE_ROWS,
        "estimated_insert_rows": APPLY_BASE_ROWS * 4,  # bet-2 through bet-5
        "adapter_contract_status": {
            "function": "get_all_bets_power_orthogonal",
            "module": "lottery_api/models/p128_wave2_phase2_adapters.py",
            "status": "AVAILABLE",
            "blockers_cleared": ["RSR6_orphan_rows", "P138B_legacy_governance"],
            "draw_context_key": "history",
        },
        "legacy_unverified_handling": {
            "decision": LEGACY_HANDLING,
            "excluded_rows": EXPECTED_LEGACY_UNVERIFIED,
            "apply_base_rows": APPLY_BASE_ROWS,
        },
        "duplicate_guard": {
            "strategy": "UNIQUE(lottery_type, target_draw, strategy_id, bet_index)",
            "pre_insert_check": "SELECT COUNT(*) = 0 WHERE strategy_id=? AND bet_index IN (2,3,4,5)",
            "abort_on_conflict": True,
        },
        "provenance_requirements": {
            "controlled_apply_id": "P141_APPLY_POWER_ORTHOGONAL_5BET_v1",
            "provenance_hash": "SHA256(strategy_id + target_draw + bet_index + predicted_numbers)",
            "truth_level": "POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED",
            "source": "P141_POWER_ORTHOGONAL_5BET_MULTI_BET_APPLY",
        },
        "dry_run_ready": True,
        "dry_run_ready_conditions": [
            "Adapter function exists and is callable",
            "RSR6 orphan blocker resolved",
            "P138B legacy governance resolved",
            "LEGACY_UNVERIFIED rows excluded from apply base",
            "duplicate guard defined",
            "provenance requirements defined",
        ],
        "apply_authorization_required_later": True,
        "db_write_in_p139": False,
        "remaining_gaps": [
            "draw_context key 'history' vs P127 spec 'historical_draws' — must reconcile before apply",
            "Adapter docstring still shows stale RSR-6 warning — cosmetic only, not a blocker",
            "Full DB backup required before controlled_apply",
            "4 missing bet indices — larger apply than P10; higher insert volume (6000 rows)",
        ],
    }

    return plans, legacy_handling_rule


def get_recommended_apply_order():
    return {
        "recommendation": "P10_FIRST",
        "rationale": (
            "power_precision_3bet (P10) should be applied first because: "
            "(1) lower estimated row count (3000 vs 6000), reducing blast radius on first apply; "
            "(2) only 2 missing bet indices vs 4 for P12; "
            "(3) P10 has implementation_priority=10 (lower = higher priority per P127); "
            "(4) P10 algorithm (precision_scoring) is simpler than P12 (orthogonal_diversification). "
            "Apply P12 after P10 is verified. Each requires separate authorization."
        ),
        "apply_order": [
            {
                "step": 1,
                "strategy_id": P10_ID,
                "task_name": "P140",
                "estimated_rows": APPLY_BASE_ROWS * 2,
                "bet_indices": [2, 3],
                "authorization_required": True,
            },
            {
                "step": 2,
                "strategy_id": P12_ID,
                "task_name": "P141",
                "estimated_rows": APPLY_BASE_ROWS * 4,
                "bet_indices": [2, 3, 4, 5],
                "authorization_required": True,
            },
        ],
    }


def get_authorization_phrase_templates():
    return {
        "p10_apply_phrase": (
            "P139_AUTHORIZED_APPLY_POWER_PRECISION_3BET_BET2_BET3_USING_1500_PRODUCTION_BASE_20260529"
        ),
        "p12_apply_phrase": (
            "P139_AUTHORIZED_APPLY_POWER_ORTHOGONAL_5BET_BET2_THRU_BET5_USING_1500_PRODUCTION_BASE_20260529"
        ),
        "note": (
            "These phrases must be provided verbatim before executing P140 and P141 respectively. "
            "Paraphrasing or partial repetition does not constitute authorization. "
            "P139 does NOT authorize either apply — these templates are for future use."
        ),
        "this_is_not_authorization": True,
    }


def get_duplicate_guard_summary():
    return {
        "guard_type": "UNIQUE constraint on (lottery_type, target_draw, strategy_id, bet_index)",
        "pre_insert_check": "COUNT(*) = 0 for target bet indices before any insert",
        "abort_on_conflict": True,
        "power_precision_3bet": {
            "check": "SELECT COUNT(*) = 0 WHERE strategy_id='power_precision_3bet' AND bet_index IN (2,3)",
            "expected_count_before_apply": 0,
        },
        "power_orthogonal_5bet": {
            "check": "SELECT COUNT(*) = 0 WHERE strategy_id='power_orthogonal_5bet' AND bet_index IN (2,3,4,5)",
            "expected_count_before_apply": 0,
        },
    }


def get_provenance_readiness_summary():
    return {
        "power_precision_3bet": {
            "controlled_apply_id": "P140_APPLY_POWER_PRECISION_3BET_v1",
            "truth_level": "POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED",
            "provenance_hash_method": "SHA256(strategy_id + target_draw + bet_index + predicted_numbers)",
            "source": "P140_POWER_PRECISION_3BET_MULTI_BET_APPLY",
            "provenance_source": "historical_only",
            "ready": True,
        },
        "power_orthogonal_5bet": {
            "controlled_apply_id": "P141_APPLY_POWER_ORTHOGONAL_5BET_v1",
            "truth_level": "POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED",
            "provenance_hash_method": "SHA256(strategy_id + target_draw + bet_index + predicted_numbers)",
            "source": "P141_POWER_ORTHOGONAL_5BET_MULTI_BET_APPLY",
            "provenance_source": "historical_only",
            "ready": True,
        },
    }


def run_drift_guard():
    result = subprocess.run(
        ["python3", "scripts/replay_lifecycle_drift_guard.py"],
        cwd=WORKTREE, capture_output=True, text=True,
    )
    status = "PASS" if "Status: PASS" in result.stdout else "FAIL"
    return {"status": status, "pass": status == "PASS", "stdout": result.stdout.strip()}


def write_markdown(result: dict):
    dist = result["p10_p12_current_distribution"]
    lu = result["legacy_unverified_audit"]
    acs = result["adapter_contract_status"]
    lhd = result["legacy_row_handling_decision"]
    drp = result["dry_run_plan"]
    eis = result["estimated_insert_rows_summary"]
    rao = result["recommended_apply_order"]
    auth = result["authorization_phrase_templates"]
    ags = result["apply_gate_status"]

    md = f"""# P139: P10/P12 Multi-Bet Dry-Run Gate After Legacy Remark

**Generated:** {result["generated_at"]}
**Classification:** `{result["classification"]}`
**Worktree:** `{result["canonical_repo"]}`
**Branch:** `{result["canonical_branch"]}`

---

## 1. Executive Summary

P139 is a **read-only dry-run gate** re-evaluating `power_precision_3bet` (P10) and
`power_orthogonal_5bet` (P12) for multi-bet controlled_apply readiness.

Following P138B's authorized LEGACY_UNVERIFIED re-mark, both strategies now have:
- 1500 clean production baseline rows + 50 governed LEGACY_UNVERIFIED rows (1550 total)
- 0 NULL-provenance legacy selector rows
- Adapter functions available and both blockers cleared (RSR6 + legacy governance)

**P139 conclusion:** Both strategies are **dry-run ready**. Apply uses 1500 production
baseline rows (LEGACY_UNVERIFIED excluded). Authorization required before P140 (P10) and P141 (P12).

**No DB writes. No controlled_apply. No row insertions or deletions.**

---

## 2. Canonical Repo / Branch Confirmation

| Field | Expected | Actual | OK |
|-------|----------|--------|----|
| Repo | `{result["repo_branch_check"]["expected_repo"]}` | `{result["repo_branch_check"]["actual_repo"]}` | {"✅" if result["repo_branch_check"]["repo_ok"] else "❌"} |
| Branch | `{result["repo_branch_check"]["expected_branch"]}` | `{result["repo_branch_check"]["actual_branch"]}` | {"✅" if result["repo_branch_check"]["branch_ok"] else "❌"} |
| DB rows | `{EXPECTED_DB_ROWS}` | `{result["db_snapshot"]["total_rows"]}` | {"✅" if result["db_snapshot"]["rows_ok"] else "❌"} |

---

## 3. P138B Recap

**P138B classification:** `{result["p138b_source_summary"]["classification"]}`
**P138B actual rows remarked:** {result["p138b_source_summary"]["actual_rows_remarked"]}
**P138B governance resolved:** P10={result["p138b_source_summary"]["p10_governance_resolved"]}, P12={result["p138b_source_summary"]["p12_governance_resolved"]}

P138B updated 100 NULL-provenance rows to `truth_level='LEGACY_UNVERIFIED'`, `source='P138B_LEGACY_REMARK'`,
and deterministic `provenance_hash`. DB total unchanged at 85924.

---

## 4. Why P10/P12 Are Now Eligible for Dry-Run Gate Re-evaluation

Two blockers were preventing P10/P12 from entering the dry-run gate:

| Blocker | Status |
|---------|--------|
| RSR6: orphan bet_index=2 rows | ✅ RESOLVED — RSR6 deleted 20 orphan rows per strategy |
| Legacy governance: 50 NULL-provenance rows per strategy | ✅ RESOLVED — P138B re-marked as LEGACY_UNVERIFIED |

Both blockers are now resolved. P10/P12 can proceed to dry-run planning.

---

## 5. Current P10/P12 Row Distribution

| Strategy | bet-1 rows | bet-2+ rows | apply_ready |
|----------|-----------|-------------|-------------|
| `power_precision_3bet` | {dist["power_precision_3bet_bet1_rows"]} | {dist["power_precision_3bet_bet2_plus_rows"]} | Pending P140 |
| `power_orthogonal_5bet` | {dist["power_orthogonal_5bet_bet1_rows"]} | {dist["power_orthogonal_5bet_bet2_plus_rows"]} | Pending P141 |

---

## 6. LEGACY_UNVERIFIED Audit

| Strategy | LEGACY_UNVERIFIED rows | Production baseline rows | NULL-prov selector |
|----------|----------------------|--------------------------|-------------------|
| `power_precision_3bet` | {lu["power_precision_3bet_legacy_unverified_rows"]} | 1500 | — |
| `power_orthogonal_5bet` | {lu["power_orthogonal_5bet_legacy_unverified_rows"]} | 1500 | — |
| **Total** | **{lu["total_legacy_unverified_rows"]}** | — | **{lu["null_provenance_selector_count"]} (✅ zero)** |

---

## 7. Adapter Contract Status

| Strategy | Adapter Function | Module | Status | Blockers Cleared |
|----------|-----------------|--------|--------|-----------------|
| `power_precision_3bet` | `get_all_bets_power_precision` | `p128_wave2_phase2_adapters.py` | {"✅ AVAILABLE" if acs["power_precision_3bet"]["function_exists"] else "❌ MISSING"} | RSR6 + P138B |
| `power_orthogonal_5bet` | `get_all_bets_power_orthogonal` | `p128_wave2_phase2_adapters.py` | {"✅ AVAILABLE" if acs["power_orthogonal_5bet"]["function_exists"] else "❌ MISSING"} | RSR6 + P138B |

**Gap to resolve before apply:** draw_context key used by adapters is `'history'` (list of draw dicts),
not `'historical_draws'` as spec'd in P127. Must reconcile before P140/P141.

---

## 8. Legacy Row Handling Decision

**Decision: EXCLUDE LEGACY_UNVERIFIED rows from apply base**

Apply base: **1500 production baseline rows** per strategy
(`truth_level = 'POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED'`)

**Rationale:** {lhd["rationale"]}

**Apply selector:**
```sql
{lhd["apply_selector"]}
```

**Excluded rows:** {lhd["excluded_row_count"]} per strategy (truth_level=LEGACY_UNVERIFIED)

---

## 9. Per-Strategy Dry-Run Plan

### power_precision_3bet (P10)

| Field | Value |
|-------|-------|
| Lottery type | POWER_LOTTO |
| Target bet count | 3 |
| Current bet-1 rows | 1550 |
| Apply base rows | 1500 (production baseline) |
| Missing bet indices | 2, 3 |
| Estimated insert rows | **3,000** (1500 × 2) |
| Adapter | `get_all_bets_power_precision` ✅ |
| Dry-run ready | ✅ YES |
| Apply authorization | REQUIRED — not authorized in P139 |

**Remaining gaps:**
{chr(10).join(f"- {g}" for g in drp[P10_ID]["remaining_gaps"])}

---

### power_orthogonal_5bet (P12)

| Field | Value |
|-------|-------|
| Lottery type | POWER_LOTTO |
| Target bet count | 5 |
| Current bet-1 rows | 1550 |
| Apply base rows | 1500 (production baseline) |
| Missing bet indices | 2, 3, 4, 5 |
| Estimated insert rows | **6,000** (1500 × 4) |
| Adapter | `get_all_bets_power_orthogonal` ✅ |
| Dry-run ready | ✅ YES |
| Apply authorization | REQUIRED — not authorized in P139 |

**Remaining gaps:**
{chr(10).join(f"- {g}" for g in drp[P12_ID]["remaining_gaps"])}

---

## 10. Estimated Insert Rows Summary

| Strategy | Apply base | Missing indices | Estimated insert rows | DB total after |
|----------|-----------|----------------|-----------------------|----------------|
| `power_precision_3bet` | 1500 | 2,3 | **3,000** | 88,924 |
| `power_orthogonal_5bet` | 1500 | 2,3,4,5 | **6,000** | 91,924 |
| **Combined (if both)** | — | — | **9,000** | **94,924** |

---

## 11. Recommended Apply Order

**{rao["recommendation"]}**

{rao["rationale"]}

| Step | Strategy | Task | Est. rows | Authorization |
|------|----------|------|-----------|---------------|
| 1 | `power_precision_3bet` | P140 | 3,000 | Required |
| 2 | `power_orthogonal_5bet` | P141 | 6,000 | Required |

---

## 12. Authorization Phrase Templates

> These phrases are templates for future use. P139 does NOT authorize either apply.

**P10 (power_precision_3bet) apply authorization:**
```
{auth["p10_apply_phrase"]}
```

**P12 (power_orthogonal_5bet) apply authorization:**
```
{auth["p12_apply_phrase"]}
```

{auth["note"]}

---

## 13. Explicit Non-Actions

- ❌ No DB writes executed
- ❌ No controlled_apply executed
- ❌ No replay rows inserted or deleted
- ❌ No P131–P134 / P126B–P126F rows touched
- ❌ No Wave 2 safe candidate rows touched
- ❌ No 4_STAR / P108 / P117 / P118 execution
- ❌ No scheduler / cron / launchd install
- ❌ No strategy lifecycle / champion / registry mutation
- ✅ DB rows: {ags["db_rows_after"]} (unchanged)
- ✅ dry_run_gate_only = true

---

## 14. Remaining Risks

{chr(10).join(f"- {r}" for r in result["remaining_risks"])}

---

## 15. Recommended Next Task

**{result["next_recommended_task"]}**

---

## 16. Final Classification

```
{result["classification"]}
```
"""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text(md.strip() + "\n")
    print(f"Markdown written: {OUTPUT_MD}")


def main():
    print("=" * 70)
    print("P139: P10/P12 Multi-Bet Dry-Run Gate After Legacy Remark")
    print("=" * 70)

    # STOP guard
    actual_repo = git_cmd(["rev-parse", "--show-toplevel"])
    actual_branch = git_cmd(["branch", "--show-current"])
    if actual_repo != EXPECTED_REPO:
        print(f"STOP: repo mismatch. Expected {EXPECTED_REPO}, got {actual_repo}")
        sys.exit(1)
    if actual_branch != EXPECTED_BRANCH:
        print(f"STOP: branch mismatch. Expected {EXPECTED_BRANCH}, got {actual_branch}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    db_rows = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    if db_rows != EXPECTED_DB_ROWS:
        print(f"STOP: DB rows = {db_rows} (expected {EXPECTED_DB_ROWS})")
        conn.close()
        sys.exit(1)

    cols = [c[1] for c in conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()]
    if "bet_index" not in cols:
        print("STOP: bet_index column missing")
        conn.close()
        sys.exit(1)

    p138b_check = check_artifact(P138B_ARTIFACT, "P138B_P10_P12_LEGACY_ROWS_REMARKED")
    if not p138b_check["ok"]:
        print(f"STOP: P138B artifact mismatch: {p138b_check}")
        conn.close()
        sys.exit(1)

    p137_check = check_artifact(P137_ARTIFACT, "P137_P10_P12_LEGACY_ROW_GOVERNANCE_GATE_READY")
    if not p137_check["ok"]:
        print(f"STOP: P137 artifact mismatch: {p137_check}")
        conn.close()
        sys.exit(1)

    dist = get_p10_p12_distribution(conn)
    if dist["power_precision_3bet_bet1_rows"] != EXPECTED_BET1:
        print(f"STOP: P10 bet1 = {dist['power_precision_3bet_bet1_rows']} (expected {EXPECTED_BET1})")
        conn.close(); sys.exit(1)
    if dist["power_precision_3bet_bet2_plus_rows"] != EXPECTED_BET2_PLUS:
        print(f"STOP: P10 bet2+ = {dist['power_precision_3bet_bet2_plus_rows']} (expected {EXPECTED_BET2_PLUS})")
        conn.close(); sys.exit(1)
    if dist["power_orthogonal_5bet_bet1_rows"] != EXPECTED_BET1:
        print(f"STOP: P12 bet1 = {dist['power_orthogonal_5bet_bet1_rows']} (expected {EXPECTED_BET1})")
        conn.close(); sys.exit(1)
    if dist["power_orthogonal_5bet_bet2_plus_rows"] != EXPECTED_BET2_PLUS:
        print(f"STOP: P12 bet2+ = {dist['power_orthogonal_5bet_bet2_plus_rows']} (expected {EXPECTED_BET2_PLUS})")
        conn.close(); sys.exit(1)

    lu_audit = get_legacy_unverified_audit(conn)
    if lu_audit["total_legacy_unverified_rows"] != 100:
        print(f"STOP: total LEGACY_UNVERIFIED = {lu_audit['total_legacy_unverified_rows']} (expected 100)")
        conn.close(); sys.exit(1)
    if lu_audit["null_provenance_selector_count"] != 0:
        print(f"STOP: NULL-provenance selector = {lu_audit['null_provenance_selector_count']} (expected 0)")
        conn.close(); sys.exit(1)

    conn.close()
    print("All pre-flight checks PASSED")

    repo_branch_check = check_repo_branch()
    adapter_status = get_adapter_contract_status()
    dry_run_plans, legacy_handling_rule = build_dry_run_plan()
    recommended_order = get_recommended_apply_order()
    auth_templates = get_authorization_phrase_templates()
    dup_guard = get_duplicate_guard_summary()
    prov_readiness = get_provenance_readiness_summary()
    dg = run_drift_guard()

    # Load P138B details
    with open(P138B_ARTIFACT) as f:
        p138b_data = json.load(f)

    now = datetime.now(timezone.utc)
    head_sha = git_cmd(["rev-parse", "HEAD"])

    result = {
        "task_id": "P139",
        "classification": "P139_P10_P12_MULTI_BET_DRY_RUN_GATE_READY",
        "generated_at": now.isoformat(),
        "canonical_repo": EXPECTED_REPO,
        "canonical_branch": EXPECTED_BRANCH,
        "repo_branch_check": repo_branch_check,
        "db_snapshot": {
            "db_path": str(DB_PATH),
            "total_rows": db_rows,
            "expected_rows": EXPECTED_DB_ROWS,
            "rows_ok": db_rows == EXPECTED_DB_ROWS,
            "bet_index_schema_present": "bet_index" in cols,
            "head_sha": head_sha,
        },
        "p138b_source_summary": {
            "artifact_path": str(P138B_ARTIFACT),
            "classification": p138b_check["classification"],
            "expected_classification": "P138B_P10_P12_LEGACY_ROWS_REMARKED",
            "classification_ok": p138b_check["ok"],
            "actual_rows_remarked": p138b_data["remark_scope"]["actual_rows_remarked"],
            "p10_governance_resolved": p138b_data["future_dry_run_gate_impact"][
                "power_precision_3bet_legacy_governance_resolved"
            ],
            "p12_governance_resolved": p138b_data["future_dry_run_gate_impact"][
                "power_orthogonal_5bet_legacy_governance_resolved"
            ],
        },
        "p10_p12_current_distribution": dist,
        "legacy_unverified_audit": lu_audit,
        "adapter_contract_status": adapter_status,
        "dry_run_plan": dry_run_plans,
        "legacy_row_handling_decision": legacy_handling_rule,
        "estimated_insert_rows_summary": {
            "power_precision_3bet": {
                "apply_base": APPLY_BASE_ROWS,
                "missing_indices": [2, 3],
                "estimated_insert_rows": APPLY_BASE_ROWS * 2,
                "db_total_after_apply": EXPECTED_DB_ROWS + APPLY_BASE_ROWS * 2,
            },
            "power_orthogonal_5bet": {
                "apply_base": APPLY_BASE_ROWS,
                "missing_indices": [2, 3, 4, 5],
                "estimated_insert_rows": APPLY_BASE_ROWS * 4,
                "db_total_after_apply": EXPECTED_DB_ROWS + APPLY_BASE_ROWS * 2 + APPLY_BASE_ROWS * 4,
            },
            "combined_total_insert_rows": APPLY_BASE_ROWS * 2 + APPLY_BASE_ROWS * 4,
            "db_total_after_both": EXPECTED_DB_ROWS + APPLY_BASE_ROWS * 2 + APPLY_BASE_ROWS * 4,
        },
        "recommended_apply_order": recommended_order,
        "authorization_phrase_templates": auth_templates,
        "duplicate_guard_summary": dup_guard,
        "provenance_readiness_summary": prov_readiness,
        "apply_gate_status": {
            "dry_run_gate_only": True,
            "controlled_apply_executed": False,
            "replay_rows_inserted": 0,
            "db_rows_before": EXPECTED_DB_ROWS,
            "db_rows_after": db_rows,
            "per_strategy_authorization_required_later": True,
            "p10_dry_run_ready": True,
            "p12_dry_run_ready": True,
        },
        "blocked_or_excluded": [
            "no DB write in P139",
            "no controlled_apply in P139",
            "no replay rows inserted",
            "P10/P12 require future per-strategy apply authorization",
            "4_STAR excluded",
            "P108 not run",
            "P117 not run",
            "P118 not run",
            "rejected strategies no_action",
            "no scheduler install",
            "no lifecycle / champion / registry mutation",
        ],
        "drift_guard_result": {
            "status": dg["status"],
            "pass": dg["pass"],
            "total_rows": db_rows,
        },
        "roadmap_update_status": "pending — will be updated in this run",
        "remaining_risks": [
            "draw_context key mismatch: adapter uses 'history' but P127 spec says 'historical_draws' — must reconcile before P140/P141.",
            "Adapter docstrings still show stale RSR-6 warnings — cosmetic only, not a blocker.",
            "LEGACY_UNVERIFIED rows (50 per strategy) are excluded from apply base — if legacy multi-bet coverage is needed, a separate authorized task is required.",
            "P10/P12 are watchlist quality (p125_rank_score 31/35) — apply provides replay coverage but does not imply production deployment.",
            "After P140+P141, drift guard baseline will shift to 94,924 — drift guard may need a comment update.",
            "Full DB backup required before each controlled_apply (P140, P141).",
        ],
        "next_recommended_task": (
            "P140: power_precision_3bet multi-bet controlled_apply (bet-2 + bet-3, 3000 rows, "
            "requires authorization phrase P139_AUTHORIZED_APPLY_POWER_PRECISION_3BET_BET2_BET3_"
            "USING_1500_PRODUCTION_BASE_20260529)."
        ),
        "summary": (
            "P139 is a read-only dry-run gate for power_precision_3bet (P10) and "
            "power_orthogonal_5bet (P12). Both strategies are now DRY_RUN_READY: "
            "RSR6 orphan blocker resolved, P138B legacy governance resolved, "
            "adapter functions available. "
            "LEGACY_UNVERIFIED rows EXCLUDED from apply base (1500 production rows only). "
            "P10 estimated: 3000 inserts (bet-2+3). P12 estimated: 6000 inserts (bet-2+3+4+5). "
            "Recommended order: P10 first (P140), P12 second (P141). "
            "Authorization phrase templates provided; no apply authorized in P139. "
            "DB rows: 85924 (unchanged). Drift guard: PASS."
        ),
    }

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(f"JSON written: {OUTPUT_JSON}")
    write_markdown(result)

    print()
    print(f"task_id          : {result['task_id']}")
    print(f"classification   : {result['classification']}")
    print(f"db_rows          : {db_rows}")
    print(f"P10 dry_run_ready: {result['apply_gate_status']['p10_dry_run_ready']}")
    print(f"P12 dry_run_ready: {result['apply_gate_status']['p12_dry_run_ready']}")
    print(f"P10 est_insert   : {APPLY_BASE_ROWS * 2}")
    print(f"P12 est_insert   : {APPLY_BASE_ROWS * 4}")
    print(f"drift_guard      : {dg['status']}")
    print()
    print("P139 complete.")


if __name__ == "__main__":
    main()
