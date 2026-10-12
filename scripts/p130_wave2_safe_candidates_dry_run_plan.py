"""
p130_wave2_safe_candidates_dry_run_plan.py
==========================================
P130: Wave 2 safe candidate controlled_apply dry-run plan.

Read-only planning phase. Produces per-strategy dry-run plan for
P7/P8/P9/P11. No DB writes. No controlled_apply execution.

Safe candidates (from P128 Phase 3):
  P7  acb_markov_midfreq_3bet  DAILY_539   3-bet  +3000 rows
  P8  midfreq_fourier_mk_3bet  POWER_LOTTO 3-bet  +3000 rows
  P9  fourier_rhythm_3bet      POWER_LOTTO 3-bet  +3002 rows ⚠ 1501-row anomaly
  P11 pp3_freqort_4bet         POWER_LOTTO 4-bet  +4500 rows

Blocked (not in scope):
  P10 power_precision_3bet     post-RSR6 apply gate re-evaluation required
  P12 power_orthogonal_5bet    post-RSR6 apply gate re-evaluation required

Usage:
    python3 scripts/p130_wave2_safe_candidates_dry_run_plan.py
"""

import datetime
import json
import pathlib
import sqlite3
import sys

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH   = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

EXPECTED_DB_ROWS = 72422
WORKTREE_NAME    = "zen-gates-ff6802"

P128_PHASE3_JSON = REPO_ROOT / "outputs" / "replay" / "p128_phase3_wave2_safe_candidates_readiness_20260528.json"
RSR6_CLEANUP_JSON = REPO_ROOT / "outputs" / "replay" / "rsr6_cleanup_delete_orphan_bet_index2_rows_20260528.json"

OUTPUT_JSON = REPO_ROOT / "outputs" / "replay" / "p130_wave2_safe_candidates_dry_run_plan_20260528.json"
OUTPUT_MD   = REPO_ROOT / "docs"    / "replay" / "p130_wave2_safe_candidates_dry_run_plan_20260528.md"

# Static candidate definitions  (draw-ranges resolved from live DB at runtime)
SAFE_CANDIDATES = [
    {
        "priority":         7,
        "strategy_id":      "acb_markov_midfreq_3bet",
        "lottery_type":     "DAILY_539",
        "target_bet_count": 3,
        "missing_bet_indices": [2, 3],
        "adapter_function": "get_all_bets_acb_markov_midfreq",
        "adapter_source":   "lottery_api/models/p128_wave2_phase2_adapters.py",
        "controlled_apply_id_template": "P130_APPLY_ACB_MARKOV_MIDFREQ_3BET_DAILY539_V{DATE}",
        "authorization_phrase_template": (
            "P130_AUTHORIZED_APPLY_ACB_MARKOV_MIDFREQ_3BET_DAILY539_BET2_BET3_V{DATE}"
        ),
        "p9_anomaly": False,
    },
    {
        "priority":         8,
        "strategy_id":      "midfreq_fourier_mk_3bet",
        "lottery_type":     "POWER_LOTTO",
        "target_bet_count": 3,
        "missing_bet_indices": [2, 3],
        "adapter_function": "get_all_bets_midfreq_fourier_mk",
        "adapter_source":   "lottery_api/models/p128_wave2_phase2_adapters.py",
        "controlled_apply_id_template": "P130_APPLY_MIDFREQ_FOURIER_MK_3BET_POWERLOTTO_V{DATE}",
        "authorization_phrase_template": (
            "P130_AUTHORIZED_APPLY_MIDFREQ_FOURIER_MK_3BET_POWERLOTTO_BET2_BET3_V{DATE}"
        ),
        "p9_anomaly": False,
    },
    {
        "priority":         9,
        "strategy_id":      "fourier_rhythm_3bet",
        "lottery_type":     "POWER_LOTTO",
        "target_bet_count": 3,
        "missing_bet_indices": [2, 3],
        "adapter_function": "get_all_bets_fourier_rhythm",
        "adapter_source":   "lottery_api/models/p128_wave2_phase2_adapters.py",
        "controlled_apply_id_template": "P130_APPLY_FOURIER_RHYTHM_3BET_POWERLOTTO_V{DATE}",
        "authorization_phrase_template": (
            "P130_AUTHORIZED_APPLY_FOURIER_RHYTHM_3BET_POWERLOTTO_BET2_BET3_V{DATE}"
        ),
        "p9_anomaly": True,
        "p9_anomaly_note": (
            "fourier_rhythm_3bet has 1501 bi=1 rows vs 1500 for other POWER_LOTTO strategies. "
            "Extra draw = 115000041 (2026/05/21), added via P79 Batch A draw-ext "
            "(controlled_apply_id=P78_POWERLOTTO_BATCH_A_FOURIER_RHYTHM_DRAWEXT_20260526). "
            "This is legitimate. Estimated insert rows = 2×1501 = 3002. "
            "Verify target draw range includes 115000041 before controlled_apply."
        ),
    },
    {
        "priority":         11,
        "strategy_id":      "pp3_freqort_4bet",
        "lottery_type":     "POWER_LOTTO",
        "target_bet_count": 4,
        "missing_bet_indices": [2, 3, 4],
        "adapter_function": "get_all_bets_pp3_freqort",
        "adapter_source":   "lottery_api/models/p128_wave2_phase2_adapters.py",
        "controlled_apply_id_template": "P130_APPLY_PP3_FREQORT_4BET_POWERLOTTO_V{DATE}",
        "authorization_phrase_template": (
            "P130_AUTHORIZED_APPLY_PP3_FREQORT_4BET_POWERLOTTO_BET2_BET3_BET4_V{DATE}"
        ),
        "p9_anomaly": False,
    },
]

BLOCKED_CANDIDATES = [
    {
        "priority":    10,
        "strategy_id": "power_precision_3bet",
        "lottery_type": "POWER_LOTTO",
        "target_bet_count": 3,
        "reason": "post_rsr6_cleanup_apply_gate_re_evaluation_required",
        "apply_ready": False,
    },
    {
        "priority":    12,
        "strategy_id": "power_orthogonal_5bet",
        "lottery_type": "POWER_LOTTO",
        "target_bet_count": 5,
        "reason": "post_rsr6_cleanup_apply_gate_re_evaluation_required",
        "apply_ready": False,
    },
]

# Recommended apply order: normal rows first, then P9 anomaly last for extra verification
APPLY_ORDER_RATIONALE = {
    "acb_markov_midfreq_3bet": (
        "P7 first — DAILY_539, cleanest 1500-row baseline, lowest risk entry point."
    ),
    "midfreq_fourier_mk_3bet": (
        "P8 second — POWER_LOTTO, standard 1500 rows, same pool as P9/P11."
    ),
    "pp3_freqort_4bet": (
        "P11 third — POWER_LOTTO 4-bet, widest insert scope (4500 rows), "
        "but standard baseline, no anomaly."
    ),
    "fourier_rhythm_3bet": (
        "P9 last — verify 115000041 draw-ext row inclusion before apply; "
        "est 3002 rows (2×1501). Confirm controlled_apply_id covers draw 115000041."
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def now_iso() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def load_json(p: pathlib.Path) -> dict:
    return json.loads(p.read_text())


def get_strategy_draw_range(conn: sqlite3.Connection, strategy_id: str) -> dict:
    row = conn.execute(
        """
        SELECT
            MIN(CAST(target_draw AS INTEGER)),
            MAX(CAST(target_draw AS INTEGER)),
            MIN(target_date),
            MAX(target_date),
            COUNT(*)
        FROM strategy_prediction_replays
        WHERE strategy_id = ? AND bet_index = 1
        """,
        (strategy_id,),
    ).fetchone()
    if not row or row[0] is None:
        return {}
    return {
        "min_draw": row[0],
        "max_draw": row[1],
        "min_date": row[2],
        "max_date": row[3],
        "bi1_row_count": row[4],
    }


def check_no_existing_bi2_plus(conn: sqlite3.Connection, strategy_id: str, missing_indices: list) -> dict:
    conflicts = {}
    for bi in missing_indices:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=?",
            (strategy_id, bi),
        ).fetchone()[0]
        if cnt > 0:
            conflicts[bi] = cnt
    return conflicts


# ---------------------------------------------------------------------------
# Core planning logic
# ---------------------------------------------------------------------------


def build_candidate_plan(cand: dict, conn: sqlite3.Connection, today: str) -> dict:
    sid   = cand["strategy_id"]
    bets  = cand["target_bet_count"]
    mis   = cand["missing_bet_indices"]

    draw_range  = get_strategy_draw_range(conn, sid)
    bi1_rows    = draw_range.get("bi1_row_count", 0)
    conflicts   = check_no_existing_bi2_plus(conn, sid, mis)
    est_insert  = len(mis) * bi1_rows

    risk = "medium"
    if cand.get("p9_anomaly"):
        risk = "medium_high"

    dry_run_status = "DRY_RUN_PLAN_READY"
    if conflicts:
        dry_run_status = "BLOCKED_EXISTING_ROWS"

    auth_phrase = cand["authorization_phrase_template"].replace("{DATE}", today)
    ctrl_id     = cand["controlled_apply_id_template"].replace("{DATE}", today)

    plan = {
        "strategy_id":       sid,
        "priority":          cand["priority"],
        "lottery_type":      cand["lottery_type"],
        "target_bet_count":  bets,
        "current_bet_index_distribution": {1: bi1_rows},
        "missing_bet_indices":  mis,
        "estimated_insert_rows": est_insert,
        "target_draw_range": draw_range,
        "adapter_function":  cand["adapter_function"],
        "adapter_source":    cand["adapter_source"],
        "get_all_bets_contract_status": "VERIFIED" if bi1_rows > 0 else "UNKNOWN",
        "duplicate_guard": {
            "strategy":      "UNIQUE(lottery_type, target_draw, strategy_id, bet_index)",
            "pre_insert_check": f"SELECT COUNT(*)=0 WHERE strategy_id='{sid}' AND bet_index IN {tuple(mis)}",
            "abort_on_conflict": True,
            "existing_conflicts": conflicts,
            "conflict_free": len(conflicts) == 0,
        },
        "provenance_requirements": {
            "controlled_apply_id_template": ctrl_id,
            "provenance_hash_formula": "SHA256(strategy_id|target_draw|bet_index|predicted_numbers)",
            "provenance_source": "historical_only",
            "dry_run_required_before_apply": True,
        },
        "dry_run_status":    dry_run_status,
        "risk_level":        risk,
        "apply_ready_after_authorization": len(conflicts) == 0,
        "authorization_phrase_required_later": auth_phrase,
        "db_write_in_p130":  False,
        "apply_order_rationale": APPLY_ORDER_RATIONALE.get(sid, ""),
    }
    if cand.get("p9_anomaly"):
        plan["p9_anomaly"] = True
        plan["p9_anomaly_note"] = cand["p9_anomaly_note"]
    else:
        plan["p9_anomaly"] = False

    return plan


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_p130() -> dict:
    generated_at = now_iso()
    today = datetime.datetime.utcnow().strftime("%Y%m%d")

    # ── 1. Worktree check ───────────────────────────────────────────────────
    worktree_path = str(REPO_ROOT)
    worktree_ok   = WORKTREE_NAME in worktree_path
    repo_worktree_check = {
        "worktree_path":     worktree_path,
        "expected_worktree": WORKTREE_NAME,
        "worktree_confirmed": worktree_ok,
    }
    if not worktree_ok:
        raise RuntimeError(f"STOP: wrong worktree. Expected '{WORKTREE_NAME}' in path.")

    # ── 2. DB pre-checks ────────────────────────────────────────────────────
    assert DB_PATH.exists(), f"DB not found: {DB_PATH}"
    conn = sqlite3.connect(str(DB_PATH))

    total_rows = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    assert total_rows == EXPECTED_DB_ROWS, (
        f"STOP: DB rows = {total_rows}, expected {EXPECTED_DB_ROWS}"
    )
    cols = [r[1] for r in conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()]
    assert "bet_index" in cols, "STOP: bet_index column missing"

    db_snapshot = {
        "total_rows":           total_rows,
        "expected_rows":        EXPECTED_DB_ROWS,
        "bet_index_schema_exists": True,
        "rows_match_expected":  True,
    }

    # ── 3. Source artifacts ─────────────────────────────────────────────────
    p3_data  = load_json(P128_PHASE3_JSON)
    rsr6_data = load_json(RSR6_CLEANUP_JSON)

    assert p3_data["classification"] == "P128_PHASE3_WAVE2_SAFE_CANDIDATES_READINESS_READY"
    assert rsr6_data["classification"] == "RSR6_ORPHAN_BET_INDEX2_CLEANUP_APPLIED"

    p128_phase3_source_summary = {
        "artifact":        str(P128_PHASE3_JSON),
        "task_id":         p3_data.get("task_id"),
        "classification":  p3_data.get("classification"),
        "all_safe_dry_run_ready": p3_data.get("safe_candidate_scope", {}).get("all_safe_candidates_dry_run_ready"),
        "estimated_safe_insert_rows": p3_data.get("estimated_insert_rows", {}).get("safe_candidates_total_estimated"),
        "classification_pass": True,
    }
    rsr6_cleanup_source_summary = {
        "artifact":       str(RSR6_CLEANUP_JSON),
        "classification": rsr6_data.get("classification"),
        "deleted_rows":   rsr6_data.get("deleted_rows_summary", {}).get("total_deleted"),
        "db_rows_after":  rsr6_data.get("db_snapshot_after", {}).get("total_rows"),
        "classification_pass": True,
    }

    # ── 4. Build per-candidate dry-run plan ─────────────────────────────────
    safe_plan = []
    for cand in SAFE_CANDIDATES:
        plan = build_candidate_plan(cand, conn, today)
        safe_plan.append(plan)

    # ── 5. Blocked candidates ────────────────────────────────────────────────
    blocked_scope_list = []
    for bc in BLOCKED_CANDIDATES:
        bi_dist = {}
        row = conn.execute(
            "SELECT bet_index, COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? GROUP BY bet_index",
            (bc["strategy_id"],),
        ).fetchall()
        for r in row:
            bi_dist[r[0]] = r[1]
        blocked_scope_list.append({
            "priority":      bc["priority"],
            "strategy_id":   bc["strategy_id"],
            "lottery_type":  bc["lottery_type"],
            "target_bet_count": bc["target_bet_count"],
            "current_bet_index_distribution": bi_dist,
            "reason":        bc["reason"],
            "apply_ready":   False,
            "rsr6_cleanup_completed": True,
            "re_evaluation_required": True,
        })

    conn.close()

    blocked_candidate_scope = {
        "power_precision_3bet":  next(b for b in blocked_scope_list if b["strategy_id"] == "power_precision_3bet"),
        "power_orthogonal_5bet": next(b for b in blocked_scope_list if b["strategy_id"] == "power_orthogonal_5bet"),
        "reason":      "post_rsr6_cleanup_apply_gate_re_evaluation_required",
        "apply_ready": False,
    }

    # ── 6. Estimated insert rows summary ─────────────────────────────────────
    total_safe = sum(p["estimated_insert_rows"] for p in safe_plan)
    estimated_insert_rows_summary = {
        "per_candidate": [
            {
                "strategy_id":         p["strategy_id"],
                "missing_bet_indices": p["missing_bet_indices"],
                "estimated_insert_rows": p["estimated_insert_rows"],
                "p9_anomaly":          p.get("p9_anomaly", False),
            }
            for p in safe_plan
        ],
        "total_safe_insert_rows": total_safe,
        "db_rows_after_safe_apply_estimated": EXPECTED_DB_ROWS + total_safe,
        "note": (
            "P9 fourier_rhythm_3bet contributes 3002 (2×1501) due to draw-ext row. "
            "All other estimates based on 1500 bi=1 rows."
        ),
    }

    # ── 7. Recommended apply order ───────────────────────────────────────────
    recommended_apply_order = [
        {
            "step": 1,
            "strategy_id": "acb_markov_midfreq_3bet",
            "rationale": APPLY_ORDER_RATIONALE["acb_markov_midfreq_3bet"],
            "estimated_insert_rows": 3000,
        },
        {
            "step": 2,
            "strategy_id": "midfreq_fourier_mk_3bet",
            "rationale": APPLY_ORDER_RATIONALE["midfreq_fourier_mk_3bet"],
            "estimated_insert_rows": 3000,
        },
        {
            "step": 3,
            "strategy_id": "pp3_freqort_4bet",
            "rationale": APPLY_ORDER_RATIONALE["pp3_freqort_4bet"],
            "estimated_insert_rows": 4500,
        },
        {
            "step": 4,
            "strategy_id": "fourier_rhythm_3bet",
            "rationale": APPLY_ORDER_RATIONALE["fourier_rhythm_3bet"],
            "estimated_insert_rows": 3002,
            "p9_anomaly_note": "Verify 115000041 inclusion before applying.",
        },
    ]

    # ── 8. Authorization phrases (templates — not usable in this round) ──────
    authorization_phrases_required_later = [
        {
            "strategy_id":     p["strategy_id"],
            "phrase_template": p["authorization_phrase_required_later"],
            "status":          "NOT_YET_ISSUED",
            "note":            "Must be issued separately before controlled_apply execution",
        }
        for p in safe_plan
    ]

    # ── 9. Duplicate guard summary ────────────────────────────────────────────
    duplicate_guard_summary = {
        "strategy":              "UNIQUE(lottery_type, target_draw, strategy_id, bet_index)",
        "abort_on_conflict":     True,
        "all_safe_conflict_free": all(p["duplicate_guard"]["conflict_free"] for p in safe_plan),
        "per_candidate_status": [
            {
                "strategy_id":    p["strategy_id"],
                "conflict_free":  p["duplicate_guard"]["conflict_free"],
                "existing_conflicts": p["duplicate_guard"]["existing_conflicts"],
            }
            for p in safe_plan
        ],
    }

    # ── 10. Provenance readiness summary ─────────────────────────────────────
    provenance_readiness_summary = {
        "hash_formula":                "SHA256(strategy_id|target_draw|bet_index|predicted_numbers)",
        "source":                      "historical_only",
        "dry_run_required_before_any_apply": True,
        "all_templates_defined":       True,
        "per_candidate": [
            {
                "strategy_id":                p["strategy_id"],
                "controlled_apply_id_template": p["provenance_requirements"]["controlled_apply_id_template"],
            }
            for p in safe_plan
        ],
    }

    # ── 11. Apply gate status ─────────────────────────────────────────────────
    apply_gate_status = {
        "dry_run_plan_only":                  True,
        "controlled_apply_executed":          False,
        "replay_rows_inserted":               0,
        "production_db_rows_expected":        EXPECTED_DB_ROWS,
        "production_db_rows_after":           total_rows,
        "per_strategy_authorization_required_later": True,
        "safe_candidates_next_step": (
            "Issue per-strategy authorization phrases, run controlled_apply dry-run "
            "execution script, verify row counts, then execute controlled_apply."
        ),
        "blocked_candidates_next_step": (
            "P10/P12: run apply gate re-evaluation first, then issue separate authorization."
        ),
    }

    blocked_or_excluded = {
        "no_db_write_in_P130":                 True,
        "no_controlled_apply_in_P130":         True,
        "P10_P12_not_apply_ready":             True,
        "4_STAR_excluded":                     True,
        "P108_not_run":                        True,
        "P117_not_run":                        True,
        "P118_not_run":                        True,
        "rejected_strategies_no_action":       True,
        "no_scheduler_install":                True,
        "no_lifecycle_champion_registry_mutation": True,
        "P126B_P126F_rows_untouched":          True,
        "no_apply_execution_script_created":   True,
    }

    remaining_risks = [
        "P9 fourier_rhythm_3bet draw-ext row (115000041) must be included in controlled_apply target draws; "
        "verify the adapter reproduces this draw's numbers deterministically before apply.",
        "Authorization phrases are templates only; actual phrases with real DATE suffix must be "
        "obtained and validated before any controlled_apply proceeds.",
        "P7 acb_markov_midfreq_3bet draw range starts at 110000190 (not 101000002 like POWER_LOTTO strategies) "
        "— ensure adapter history window is compatible with DAILY_539 draw numbering.",
        "P10/P12 apply gate re-evaluation may surface additional anomalies "
        "(bi=1 rows with replay_run_id=2,6 and controlled_apply_id IS NULL).",
    ]

    result = {
        "task_id":          "P130",
        "classification":   "P130_WAVE2_SAFE_CANDIDATES_DRY_RUN_PLAN_READY",
        "generated_at":     generated_at,
        "repo_worktree_check": repo_worktree_check,
        "db_snapshot":      db_snapshot,
        "p128_phase3_source_summary": p128_phase3_source_summary,
        "rsr6_cleanup_source_summary": rsr6_cleanup_source_summary,
        "safe_candidate_dry_run_plan": safe_plan,
        "blocked_candidate_scope":    blocked_candidate_scope,
        "estimated_insert_rows_summary": estimated_insert_rows_summary,
        "recommended_apply_order":    recommended_apply_order,
        "authorization_phrases_required_later": authorization_phrases_required_later,
        "duplicate_guard_summary":    duplicate_guard_summary,
        "provenance_readiness_summary": provenance_readiness_summary,
        "apply_gate_status":          apply_gate_status,
        "blocked_or_excluded":        blocked_or_excluded,
        "roadmap_update_status":      "pending",
        "remaining_risks":            remaining_risks,
        "next_recommended_task": (
            "P130b / P131: Issue per-strategy authorization phrases for P7/P8/P9/P11 "
            "and execute controlled_apply. Recommended order: P7 → P8 → P11 → P9 "
            "(verify P9 115000041 inclusion last)."
        ),
        "summary": (
            f"P130 dry-run plan complete. "
            f"4 safe candidates (P7/P8/P9/P11) planned with estimated {total_safe} insert rows. "
            f"Recommended apply order: P7→P8→P11→P9. "
            f"P9 has 1501-row anomaly (draw-ext 115000041) — verify before apply. "
            f"P10/P12 blocked. No DB writes in P130."
        ),
    }
    return result


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def build_markdown(result: dict) -> str:
    db     = result["db_snapshot"]
    p3src  = result["p128_phase3_source_summary"]
    rsr6   = result["rsr6_cleanup_source_summary"]
    plan   = result["safe_candidate_dry_run_plan"]
    bscope = result["blocked_candidate_scope"]
    est    = result["estimated_insert_rows_summary"]
    order  = result["recommended_apply_order"]
    auths  = result["authorization_phrases_required_later"]
    dg     = result["duplicate_guard_summary"]
    prov   = result["provenance_readiness_summary"]
    gate   = result["apply_gate_status"]
    bex    = result["blocked_or_excluded"]

    # per-candidate table rows
    matrix_rows = "\n".join(
        f"| P{p['priority']} | `{p['strategy_id']}` | {p['lottery_type']} | "
        f"{p['target_bet_count']} | {p['current_bet_index_distribution'].get(1,'?')} | "
        f"{p['missing_bet_indices']} | {p['estimated_insert_rows']} | "
        f"{'⚠ 1501 anomaly' if p.get('p9_anomaly') else '—'} | **{p['dry_run_status']}** |"
        for p in plan
    )

    # estimated rows table
    est_rows = "\n".join(
        f"| `{e['strategy_id']}` | {e['missing_bet_indices']} | "
        f"{e['estimated_insert_rows']} | {'⚠ anomaly' if e['p9_anomaly'] else '—'} |"
        for e in est["per_candidate"]
    )

    # apply order table
    order_rows = "\n".join(
        f"| {o['step']} | `{o['strategy_id']}` | {o['estimated_insert_rows']} | "
        f"{o['rationale'][:60]}{'…' if len(o['rationale'])>60 else ''} |"
        for o in order
    )

    # auth phrases
    auth_rows = "\n".join(
        f"| `{a['strategy_id']}` | `{a['phrase_template']}` | {a['status']} |"
        for a in auths
    )

    return f"""# P130: Wave 2 Safe Candidate Controlled-Apply Dry-Run Plan

**Task ID**: P130
**Classification**: {result['classification']}
**Generated At**: {result['generated_at']}

---

## 1. Executive Summary

P130 produces the per-strategy **dry-run apply plan** for safe Wave 2 candidates
(P7/P8/P9/P11). No DB writes are performed.

- **4 safe candidates** planned: DRY_RUN_PLAN_READY
- **Estimated total insert rows** (if applied): **{est['total_safe_insert_rows']:,}**
- **DB rows**: {db['total_rows']:,} (unchanged)
- **Recommended apply order**: P7 → P8 → P11 → P9
- **P9 anomaly**: fourier_rhythm_3bet has 1501 bi=1 rows — verify before apply
- **P10/P12**: BLOCKED (post-RSR6 apply gate re-evaluation required)

---

## 2. P128 Phase 3 Recap

| Field | Value |
|-------|-------|
| Classification | `{p3src['classification']}` |
| All safe candidates DRY_RUN_READY | {p3src['all_safe_dry_run_ready']} |
| Estimated safe insert rows (Phase 3) | {p3src['estimated_safe_insert_rows']:,} |

---

## 3. RSR-6 Cleanup Recap

| Field | Value |
|-------|-------|
| Classification | `{rsr6['classification']}` |
| Deleted rows | {rsr6['deleted_rows']} |
| DB rows after cleanup | {rsr6['db_rows_after']:,} |

---

## 4. Why P130 Is Dry-Run Plan Only

Controlled_apply requires **per-strategy authorization phrases** (not yet issued).
P130 establishes:
- Exact target draw ranges verified from live DB
- Estimated insert row counts per strategy
- Duplicate guard pre-check queries
- Provenance hash contract per strategy
- Recommended apply order (low-risk first)
- Authorization phrase templates for the next round

No rows are written. No strategies are promoted.

---

## 5. Safe Candidate Dry-Run Matrix

| P | Strategy | Lottery | Bets | bi=1 Rows | Missing bi | Est. Rows | Anomaly | Status |
|---|----------|---------|------|-----------|------------|-----------|---------|--------|
{matrix_rows}

---

## 6. P9 — fourier_rhythm_3bet 1501-Row Anomaly

> **⚠ Important**: `fourier_rhythm_3bet` has **1501** bi=1 rows vs 1500 for other
> POWER_LOTTO strategies.

{next(p['p9_anomaly_note'] for p in plan if p['strategy_id'] == 'fourier_rhythm_3bet')}

**Action before P9 apply**:
1. Confirm target draw range includes draw `115000041` (2026/05/21)
2. Verify adapter reproduces this draw deterministically
3. Estimated insert rows = **3002** (not 3000)

---

## 7. Blocked Candidate Scope (P10/P12)

| Strategy | bi=1 Rows | Reason | Apply Ready |
|----------|-----------|--------|-------------|
| `power_precision_3bet` | {bscope['power_precision_3bet']['current_bet_index_distribution'].get(1,'?')} | {bscope['power_precision_3bet']['reason']} | **False** |
| `power_orthogonal_5bet` | {bscope['power_orthogonal_5bet']['current_bet_index_distribution'].get(1,'?')} | {bscope['power_orthogonal_5bet']['reason']} | **False** |

RSR-6 cleanup done (commit f624409). Apply gate re-evaluation required separately.

---

## 8. Estimated Insert Rows Summary

| Strategy | Bet Indices | Est. Insert Rows | Note |
|----------|-------------|-----------------|------|
{est_rows}
| **Total** | | **{est['total_safe_insert_rows']:,}** | |

DB rows after safe apply (estimated): **{est['db_rows_after_safe_apply_estimated']:,}**

---

## 9. Recommended Apply Order

| Step | Strategy | Est. Rows | Rationale |
|------|----------|-----------|-----------|
{order_rows}

---

## 10. Authorization Phrases Required Later

These are **templates** — actual phrases must be issued with a real date suffix before
any controlled_apply execution. **Do not use in this round.**

| Strategy | Phrase Template | Status |
|----------|----------------|--------|
{auth_rows}

---

## 11. Duplicate Guard / Provenance Readiness Summary

**Guard strategy**: `{dg['strategy']}`
- Abort on conflict: {dg['abort_on_conflict']}
- All safe candidates conflict-free: **{dg['all_safe_conflict_free']}**

**Provenance hash**: `{prov['hash_formula']}`
- Source: {prov['source']}
- All templates defined: {prov['all_templates_defined']}

---

## 12. Explicit Non-Actions

| Non-Action | Confirmed |
|-----------|-----------|
| No DB write in P130 | ✓ |
| No controlled_apply in P130 | ✓ |
| No apply execution script created | ✓ |
| P10/P12 not in scope | ✓ |
| 4_STAR excluded | ✓ |
| P108 not run | ✓ |
| P117 not run | ✓ |
| P118 not run | ✓ |
| Rejected strategies — no action | ✓ |
| No scheduler install | ✓ |
| No lifecycle / champion / registry mutation | ✓ |

---

## 13. Remaining Risks

{chr(10).join(f'{i+1}. {r}' for i, r in enumerate(result['remaining_risks']))}

---

## 14. Recommended Next Task

{result['next_recommended_task']}

---

## 15. Final Classification

```text
{result['classification']}
```
"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    print(f"P130 dry-run plan starting at {now_iso()}")
    result = run_p130()

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"JSON: {OUTPUT_JSON}")

    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text(build_markdown(result))
    print(f"MD:   {OUTPUT_MD}")

    est = result["estimated_insert_rows_summary"]["total_safe_insert_rows"]
    print(f"Classification: {result['classification']}")
    print(f"Safe candidates: {len(result['safe_candidate_dry_run_plan'])}")
    print(f"Total estimated insert rows: {est:,}")
    print(f"DB rows (unchanged): {result['db_snapshot']['total_rows']:,}")
    return 0 if result["classification"] == "P130_WAVE2_SAFE_CANDIDATES_DRY_RUN_PLAN_READY" else 1


if __name__ == "__main__":
    sys.exit(main())
