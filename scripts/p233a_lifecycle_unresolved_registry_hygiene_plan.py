#!/usr/bin/env python3
"""
p233a_lifecycle_unresolved_registry_hygiene_plan.py
=====================================================
P233A — Lifecycle-Unresolved Registry Hygiene Plan (Read-Only).

Produces a governance plan for the 20 LIFECYCLE_UNRESOLVED strategy+lottery
entries discovered in the P232A all-catalog scoreboard.

HARD GOVERNANCE RULES:
  - Does NOT modify lottery_api/models/replay_strategy_registry.py.
  - Does NOT write DB rows.
  - Does NOT promote any strategy to ONLINE or DEPLOYABLE.
  - Does NOT create executable adapters.
  - lifecycle suggestions are governance labels for future _NON_EXECUTABLE_STUB
    additions only — they do not change any production system.
  - Suggestions are evidence-based (rejected/ archive, drift guard comments,
    controlled-apply history) and conservative (RETIRED or REJECTED only;
    never ONLINE/DEPLOYABLE).

Evidence sources used (all read-only):
  1. outputs/research/p232a_all_catalog_strategy_replay_scoreboard_20260604.json
     — confirmed 20 LIFECYCLE_UNRESOLVED entries.
  2. rejected/ directory — JSON files indicate prior governance REJECTED decisions.
  3. scripts/replay_lifecycle_drift_guard.py — comments record production apply
     history (P59 / P66 / P79 / P94 / P126D controlled applies).
  4. scripts/p94_tierb_controlled_apply.py — Tier B adapter list.
  5. tools/quick_predict.py + tools/backtest_power_5bet_stack.py +
     tools/rsm_bootstrap.py — function definitions for POWER_LOTTO strategies
     that were production-predicted.
  6. git log — ratified P93/P94/P59/P66 controlled apply commits.

Usage:
  .venv/bin/python3 scripts/p233a_lifecycle_unresolved_registry_hygiene_plan.py
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List


def _p291u_repo_root():
    current = Path(__file__)
    if not current.is_absolute():
        raise FileNotFoundError(f"Source file path is not absolute: {current}")
    for parent in (current.parent, *current.parents):
        if (parent / "lottery_api").is_dir():
            return parent
    raise FileNotFoundError(f"Unable to locate repository root from source file: {current}")


def _p291u_default_db_path():
    db_path = _p291u_repo_root() / "lottery_api" / "data" / "lottery_v2.db"
    if not db_path.is_file():
        raise FileNotFoundError(f"Default lottery DB path is missing or non-regular: {db_path}")
    return db_path


def _p291u_resolve_db_path(db_path=None):
    if db_path is None:
        return _p291u_default_db_path()
    path = Path(db_path)
    if not path.is_absolute():
        raise ValueError(f"Explicit DB path must be absolute: {db_path}")
    if not path.is_file():
        raise FileNotFoundError(f"Explicit DB path is missing or non-regular: {path}")
    return path


def _p291u_connect_resolved(db_path, *, uri=False):
    if uri:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    return sqlite3.connect(str(db_path))


REPO_ROOT = Path(__file__).resolve().parent.parent

P232A_JSON = REPO_ROOT / "outputs" / "research" / (
    "p232a_all_catalog_strategy_replay_scoreboard_20260604.json"
)
REJECTED_DIR = REPO_ROOT / "rejected"
OUTPUT_DIR = REPO_ROOT / "outputs" / "research"
DATE_TAG = "20260604"

FORBIDDEN_SUGGESTIONS = frozenset({
    "ONLINE", "DEPLOYABLE", "ONLINE_RECOMMENDED", "PRODUCTION_READY",
    "PROMOTE", "BEST_STRATEGY_TO_USE",
})

# ─── Evidence catalog (read-only; does NOT modify the registry) ───────────────
#
# Two evidence tracks:
#  A. rejected/ archive: JSON files present → evidence of prior REJECTED decision.
#  B. Production/controlled-apply history: strategy was applied to production DB
#     via authorized controlled-apply PRs; rows exist; strategy has since been
#     superseded by newer ONLINE strategies → RETIRED.
#
# Note: none of the 20 strategies should become ONLINE/DEPLOYABLE based on this
# plan. P233B (if authorized) would only add _NON_EXECUTABLE_STUB entries.

_EVIDENCE_MAP: Dict[str, Dict[str, Any]] = {
    # ── BIG_LOTTO ─────────────────────────────────────────────────────────────
    "biglotto_echo_aware_3bet": {
        "lottery_type": "BIG_LOTTO",
        "suggested_lifecycle": "RETIRED",
        "evidence": "P93/P94 Tier-B Controlled Replay Apply (commit cd981f3); "
                    "referenced in scripts/p93_tierb_dryrun_rehearsal.py and "
                    "scripts/p94a_biglotto_all_strategy_betcount_benchmark.py. "
                    "Superseded by biglotto_deviation_2bet / ts3_regime_3bet (ONLINE).",
        "registry_action": "ADD_NON_EXECUTABLE_STUB",
        "stub_name": "大樂透 Echo Aware 3注",
    },
    "biglotto_ts3_markov_4bet_w30": {
        "lottery_type": "BIG_LOTTO",
        "suggested_lifecycle": "RETIRED",
        "evidence": "P93/P94 Tier-B Controlled Replay Apply (commit cd981f3); "
                    "referenced in scripts/p93_tierb_dryrun_rehearsal.py and "
                    "scripts/p113_p112_action_decision_matrix.py. "
                    "4-bet variant superseded by current BIG_LOTTO ONLINE strategies.",
        "registry_action": "ADD_NON_EXECUTABLE_STUB",
        "stub_name": "大樂透 TS3+Markov 4注 w30",
    },
    "bet2_fourier_expansion_biglotto": {
        "lottery_type": "BIG_LOTTO",
        "suggested_lifecycle": "REJECTED",
        "evidence": "rejected/bet2_fourier_expansion_biglotto.json exists in "
                    "archive directory — prior governance REJECTED decision recorded.",
        "registry_action": "ADD_NON_EXECUTABLE_STUB",
        "stub_name": "大樂透 Bet2 Fourier Expansion",
    },
    "cold_complement_biglotto": {
        "lottery_type": "BIG_LOTTO",
        "suggested_lifecycle": "REJECTED",
        "evidence": "rejected/cold_complement_biglotto.json exists in archive directory. "
                    "Also referenced in scripts/p44_wave3_biglotto_performance_analysis.py "
                    "Wave 3 analysis (prior to current ONLINE strategies).",
        "registry_action": "ADD_NON_EXECUTABLE_STUB",
        "stub_name": "大樂透 Cold Complement",
    },
    "coldpool15_biglotto": {
        "lottery_type": "BIG_LOTTO",
        "suggested_lifecycle": "REJECTED",
        "evidence": "rejected/coldpool15_biglotto.json exists. "
                    "tools/backtest_biglotto_coldpool_15.py explicitly labels action "
                    "as '→ 歸檔 rejected/coldpool15_biglotto.json'.",
        "registry_action": "ADD_NON_EXECUTABLE_STUB",
        "stub_name": "大樂透 ColdPool-15",
    },
    "fourier30_markov30_biglotto": {
        "lottery_type": "BIG_LOTTO",
        "suggested_lifecycle": "REJECTED",
        "evidence": "rejected/fourier30_markov30_biglotto.json exists. "
                    "Referenced in scripts/p44_wave3_biglotto_performance_analysis.py "
                    "Wave 3 analysis.",
        "registry_action": "ADD_NON_EXECUTABLE_STUB",
        "stub_name": "大樂透 Fourier30+Markov30",
    },
    "markov_2bet_biglotto": {
        "lottery_type": "BIG_LOTTO",
        "suggested_lifecycle": "REJECTED",
        "evidence": "rejected/markov_2bet_biglotto.json exists. "
                    "Referenced in scripts/p44_wave3_biglotto_performance_analysis.py.",
        "registry_action": "ADD_NON_EXECUTABLE_STUB",
        "stub_name": "大樂透 Markov 2注",
    },
    "markov_single_biglotto": {
        "lottery_type": "BIG_LOTTO",
        "suggested_lifecycle": "REJECTED",
        "evidence": "rejected/markov_single_biglotto.json exists. "
                    "Referenced in scripts/p44_wave3_biglotto_performance_analysis.py.",
        "registry_action": "ADD_NON_EXECUTABLE_STUB",
        "stub_name": "大樂透 Markov Single",
    },
    # ── DAILY_539 ─────────────────────────────────────────────────────────────
    "539_3bet_orthogonal": {
        "lottery_type": "DAILY_539",
        "suggested_lifecycle": "REJECTED",
        "evidence": "rejected/539_3bet_orthogonal.json exists in archive directory "
                    "— prior governance REJECTED decision recorded.",
        "registry_action": "ADD_NON_EXECUTABLE_STUB",
        "stub_name": "今彩539 3注正交",
    },
    "acb_single_539": {
        "lottery_type": "DAILY_539",
        "suggested_lifecycle": "REJECTED",
        "evidence": "rejected/acb_single_539.json exists in archive directory. "
                    "Likely an earlier ACB single-bet variant before acb_1bet (RETIRED).",
        "registry_action": "ADD_NON_EXECUTABLE_STUB",
        "stub_name": "今彩539 ACB Single",
    },
    "daily539_f4cold_3bet": {
        "lottery_type": "DAILY_539",
        "suggested_lifecycle": "RETIRED",
        "evidence": "Referenced in scripts/p94_tierb_controlled_apply.py Tier-B apply list "
                    "(P94_TIER_B_CONTROLLED_APPLY_SUCCESS, commit cd981f3). Also "
                    "scripts/replay_lifecycle_drift_guard.py line ~98: "
                    "'P126D: DAILY_539 f4cold_3bet multi-bet (3000 rows)'. "
                    "Superseded by daily539_f4cold (ONLINE).",
        "registry_action": "ADD_NON_EXECUTABLE_STUB",
        "stub_name": "今彩539 F4Cold 3注",
    },
    "daily539_f4cold_5bet": {
        "lottery_type": "DAILY_539",
        "suggested_lifecycle": "RETIRED",
        "evidence": "Referenced in scripts/p94_tierb_controlled_apply.py Tier-B apply list "
                    "(P94_TIER_B_CONTROLLED_APPLY_SUCCESS). 5-bet multi-bet variant. "
                    "Superseded by daily539_f4cold (ONLINE).",
        "registry_action": "ADD_NON_EXECUTABLE_STUB",
        "stub_name": "今彩539 F4Cold 5注",
    },
    "markov_1bet_539": {
        "lottery_type": "DAILY_539",
        "suggested_lifecycle": "REJECTED",
        "evidence": "rejected/markov_1bet_539.json exists in archive directory "
                    "— prior governance REJECTED decision recorded.",
        "registry_action": "ADD_NON_EXECUTABLE_STUB",
        "stub_name": "今彩539 Markov 1注",
    },
    "p0b_539_3bet_f_cold_fmid": {
        "lottery_type": "DAILY_539",
        "suggested_lifecycle": "REJECTED",
        "evidence": "rejected/p0b_539_3bet_f_cold_fmid.json exists in archive directory. "
                    "git history shows it was previously a _LifecycleStub in "
                    "replay_strategy_registry.py before being removed.",
        "registry_action": "ADD_NON_EXECUTABLE_STUB",
        "stub_name": "今彩539 P0B 3注 F+Cold+FMid",
    },
    "p0c_539_3bet_f_cold_x2": {
        "lottery_type": "DAILY_539",
        "suggested_lifecycle": "REJECTED",
        "evidence": "rejected/p0c_539_3bet_f_cold_x2.json exists in archive directory. "
                    "Paired with p0b as P0C variant; likely same rejection round.",
        "registry_action": "ADD_NON_EXECUTABLE_STUB",
        "stub_name": "今彩539 P0C 3注 F+Cold×2",
    },
    "zone_gap_3bet_539": {
        "lottery_type": "DAILY_539",
        "suggested_lifecycle": "REJECTED",
        "evidence": "rejected/zone_gap_3bet_539.json exists in archive directory "
                    "— prior governance REJECTED decision recorded.",
        "registry_action": "ADD_NON_EXECUTABLE_STUB",
        "stub_name": "今彩539 Zone Gap 3注",
    },
    # ── POWER_LOTTO ───────────────────────────────────────────────────────────
    "cold_complement_2bet": {
        "lottery_type": "POWER_LOTTO",
        "suggested_lifecycle": "RETIRED",
        "evidence": "scripts/replay_lifecycle_drift_guard.py line ~86: "
                    "'P66: POWER_LOTTO Wave 6 controlled production apply — "
                    "cold_complement_2bet + zonal_entropy_2bet (3000 rows) (2026-05-25)'. "
                    "Was production-applied; superseded by fourier_rhythm_3bet / "
                    "power_orthogonal_5bet (ONLINE).",
        "registry_action": "ADD_NON_EXECUTABLE_STUB",
        "stub_name": "威力彩 Cold Complement 2注",
    },
    "fourier30_markov30_2bet": {
        "lottery_type": "POWER_LOTTO",
        "suggested_lifecycle": "RETIRED",
        "evidence": "scripts/replay_lifecycle_drift_guard.py line ~84: "
                    "'P59: POWER_LOTTO Wave 5 controlled production apply — "
                    "fourier30_markov30_2bet (1500 rows) (2026-05-25)'. "
                    "Also P79 Batch A draw-ext apply (line ~89/134). "
                    "Was production-applied; superseded by fourier_rhythm_3bet (ONLINE).",
        "registry_action": "ADD_NON_EXECUTABLE_STUB",
        "stub_name": "威力彩 Fourier30+Markov30 2注",
    },
    "power_fourier_rhythm_2bet": {
        "lottery_type": "POWER_LOTTO",
        "suggested_lifecycle": "RETIRED",
        "evidence": "tools/quick_predict.py defines power_fourier_rhythm_2bet() — "
                    "a 2-bet production prediction function. "
                    "git history shows it was previously a _LifecycleStub in "
                    "replay_strategy_registry.py before being removed. "
                    "Superseded by fourier_rhythm_3bet (ONLINE).",
        "registry_action": "ADD_NON_EXECUTABLE_STUB",
        "stub_name": "威力彩 Power Fourier Rhythm 2注",
    },
    "zonal_entropy_2bet": {
        "lottery_type": "POWER_LOTTO",
        "suggested_lifecycle": "RETIRED",
        "evidence": "scripts/replay_lifecycle_drift_guard.py line ~86: "
                    "'P66: POWER_LOTTO Wave 6 controlled production apply — "
                    "cold_complement_2bet + zonal_entropy_2bet (3000 rows) (2026-05-25)'. "
                    "Was production-applied; superseded by ONLINE strategies.",
        "registry_action": "ADD_NON_EXECUTABLE_STUB",
        "stub_name": "威力彩 Zonal Entropy 2注",
    },
}


# ─── Data loading ─────────────────────────────────────────────────────────────

def load_unresolved_entries() -> List[Dict[str, Any]]:
    """Load the 20 LIFECYCLE_UNRESOLVED entries from the P232A scoreboard JSON."""
    with open(P232A_JSON, encoding="utf-8") as f:
        sb = json.load(f)
    return [
        s for s in sb["all_strategy_scoreboard"]
        if s["lifecycle_status"] == "LIFECYCLE_UNRESOLVED"
    ]


def total_replay_rows() -> int:
    _p291u_db_path = _p291u_resolve_db_path()
    db_path = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
    conn = _p291u_connect_resolved(_p291u_db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    finally:
        conn.close()


# ─── Plan builder ─────────────────────────────────────────────────────────────

def build_plan() -> Dict[str, Any]:
    rows_before = total_replay_rows()

    unresolved = load_unresolved_entries()
    assert len(unresolved) == 20, f"Expected 20 unresolved entries, got {len(unresolved)}"

    entries = []
    lifecycle_summary: Dict[str, int] = {"REJECTED": 0, "RETIRED": 0, "UNKNOWN_REQUIRES_REVIEW": 0}
    rejected_count = 0
    retired_count = 0

    for s in sorted(unresolved, key=lambda x: (x["lottery_type"], x["strategy_id"])):
        sid = s["strategy_id"]
        lt = s["lottery_type"]
        ev = _EVIDENCE_MAP.get(sid, {})
        suggestion = ev.get("suggested_lifecycle", "UNKNOWN_REQUIRES_REVIEW")

        assert suggestion not in FORBIDDEN_SUGGESTIONS, (
            f"Forbidden lifecycle suggestion {suggestion!r} for {sid}"
        )

        # Verify rejected/ archive presence
        rejected_archive = REJECTED_DIR / f"{sid}.json"
        has_rejected_archive = rejected_archive.exists()

        entry = {
            "strategy_id": sid,
            "lottery_type": lt,
            "row_count": s.get("row_count", 0),
            "distinct_target_draws": s.get("distinct_target_draws", 0),
            "first_target_draw": s.get("first_target_draw"),
            "last_target_draw": s.get("last_target_draw"),
            "bet_index_values": s.get("bet_index_values"),
            "is_multi_bet": s.get("is_multi_bet"),
            "mean_hit_count_row_level": s.get("mean_hit_count_row_level"),
            "delta_vs_baseline": s.get("delta_vs_baseline"),
            "historical_classification": s.get("historical_classification"),
            "has_rejected_archive": has_rejected_archive,
            "suggested_lifecycle": suggestion,
            "evidence_summary": ev.get("evidence", "No specific evidence found"),
            "registry_action": ev.get("registry_action", "ADD_NON_EXECUTABLE_STUB"),
            "proposed_stub_name": ev.get("stub_name", sid),
        }
        entries.append(entry)
        lifecycle_summary[suggestion] = lifecycle_summary.get(suggestion, 0) + 1
        if suggestion == "REJECTED":
            rejected_count += 1
        elif suggestion == "RETIRED":
            retired_count += 1

    rows_after = total_replay_rows()

    # Build P233B allowlist (what files a future P233B task would be permitted to modify)
    p233b_allowlist = [
        "lottery_api/models/replay_strategy_registry.py",
        "outputs/research/p233b_lifecycle_unresolved_registry_hygiene_execute_YYYYMMDD.json",
        "outputs/research/p233b_lifecycle_unresolved_registry_hygiene_execute_YYYYMMDD.md",
        "tests/test_p233b_lifecycle_unresolved_registry_hygiene_execute.py",
    ]

    return {
        "phase": "P233A_LIFECYCLE_UNRESOLVED_REGISTRY_HYGIENE_PLAN",
        "date": DATE_TAG,
        "execution_status": "PLAN_EXECUTED_OK",
        "db_read_only": True,
        "db_write_performed": rows_after != rows_before,
        "db_rows_before": rows_before,
        "db_rows_after": rows_after,
        "registry_modified": False,
        "unresolved_count": len(entries),
        "lifecycle_suggestion_summary": {
            "REJECTED": rejected_count,
            "RETIRED": retired_count,
            "UNKNOWN_REQUIRES_REVIEW": lifecycle_summary.get("UNKNOWN_REQUIRES_REVIEW", 0),
        },
        "per_lottery_counts": {
            "BIG_LOTTO": sum(1 for e in entries if e["lottery_type"] == "BIG_LOTTO"),
            "DAILY_539": sum(1 for e in entries if e["lottery_type"] == "DAILY_539"),
            "POWER_LOTTO": sum(1 for e in entries if e["lottery_type"] == "POWER_LOTTO"),
        },
        "unresolved_entries": entries,
        "p233b_allowlist_if_authorized": p233b_allowlist,
        "caveats": [
            "P233A is a PLAN ONLY — no registry file is modified.",
            "lifecycle suggestions are conservative governance labels for future "
            "_NON_EXECUTABLE_STUB additions; they do not affect any production system.",
            "REJECTED suggestion = evidence of prior governance rejection decision "
            "(rejected/ archive file exists).",
            "RETIRED suggestion = strategy was production-applied via authorized controlled "
            "apply (P59/P66/P79/P94/P126D) and has been superseded by current ONLINE strategies.",
            "No strategy is suggested as ONLINE, DEPLOYABLE, or any promotion label.",
            "P233B execution (actual registry edits) requires separate explicit user authorization.",
            "Historical replay metrics do not authorize deployment — they are evidence only.",
        ],
        "final_classification": "P233A_LIFECYCLE_UNRESOLVED_REGISTRY_HYGIENE_PLAN_COMPLETE",
    }


# ─── Markdown report ──────────────────────────────────────────────────────────

def write_markdown(result: Dict[str, Any], md_path: Path) -> None:
    entries = result["unresolved_entries"]
    lines: List[str] = []
    A = lines.append

    A("# P233A — Lifecycle-Unresolved Registry Hygiene Plan\n")
    A(f"**Date:** {result['date']}  ")
    A(f"**Task:** `P233A_LIFECYCLE_UNRESOLVED_REGISTRY_HYGIENE_PLAN`  ")
    A(f"**Status:** PLAN ONLY / READ-ONLY / ZERO REGISTRY WRITE / ZERO DB WRITE\n")
    A("> **No registry changes in P233A.** This document records the evidence-based "
      "lifecycle suggestion for each of the 20 LIFECYCLE_UNRESOLVED entries. "
      "Actual registry stub additions require a separate P233B task with explicit "
      "user authorization. Not betting advice. Not deployment authorization.\n")

    A("## Executive Summary\n")
    A("| Metric | Value |")
    A("|---|---|")
    A(f"| LIFECYCLE_UNRESOLVED entries | {result['unresolved_count']} |")
    A(f"| Suggested REJECTED | {result['lifecycle_suggestion_summary']['REJECTED']} |")
    A(f"| Suggested RETIRED | {result['lifecycle_suggestion_summary']['RETIRED']} |")
    A(f"| DB write performed | {result['db_write_performed']} |")
    A(f"| Registry modified | {result['registry_modified']} |")
    A("")

    A("## Why 20 LIFECYCLE_UNRESOLVED Entries Exist\n")
    A("These strategy+lottery combos have replay rows in the production DB but are "
      "absent from the current `_ALL_ADAPTERS` list in `replay_strategy_registry.py`. "
      "Two root causes:")
    A("1. **Prior governance decisions** — strategy was evaluated and REJECTED; a "
      "`rejected/` archive JSON was recorded but the strategy was never added to "
      "`_NON_EXECUTABLE_STUBS` (or was later removed).")
    A("2. **Production-applied and superseded** — strategy was applied to the production "
      "DB via authorized controlled apply (P59/P66/P79/P94/P126D), accumulated replay rows, "
      "and was then superseded by newer ONLINE strategies without a RETIRED stub being registered.\n")

    A("## Evidence Sources (all read-only)\n")
    A("- `rejected/` directory: presence of `{strategy_id}.json` = prior REJECTED decision")
    A("- `scripts/replay_lifecycle_drift_guard.py`: comments record P59/P66/P79/P94/P126D "
      "production applies")
    A("- `scripts/p94_tierb_controlled_apply.py`: Tier-B adapter list")
    A("- `tools/quick_predict.py`, `tools/backtest_power_5bet_stack.py`, "
      "`tools/rsm_bootstrap.py`: production prediction functions")
    A("- git log: ratified P93/P94/P59/P66 controlled apply commits\n")

    lottery_order = ["BIG_LOTTO", "DAILY_539", "POWER_LOTTO"]
    for lt in lottery_order:
        lt_entries = [e for e in entries if e["lottery_type"] == lt]
        if not lt_entries:
            continue
        A(f"## {lt} — {len(lt_entries)} LIFECYCLE_UNRESOLVED Entries\n")
        A("| Strategy ID | Draws | Rows | BetIdx | RowMean | Δbaseline | Has rejected/ | Suggestion |")
        A("|---|---:|---:|---|---:|---:|---|---|")
        for e in lt_entries:
            bi = ",".join(str(b) for b in (e.get("bet_index_values") or []))
            mean = e.get("mean_hit_count_row_level")
            delta = e.get("delta_vs_baseline")
            m = f"{mean:.4f}" if mean is not None else "—"
            dd = (f"+{delta:.4f}" if delta and delta > 0 else f"{delta:.4f}") if delta is not None else "—"
            arch = "✓" if e["has_rejected_archive"] else "—"
            sug = e["suggested_lifecycle"]
            A(f"| `{e['strategy_id']}` | {e['distinct_target_draws']} | {e['row_count']} "
              f"| {bi} | {m} | {dd} | {arch} | **{sug}** |")
        A("")

        A(f"### {lt} — Evidence Details\n")
        for e in lt_entries:
            A(f"**`{e['strategy_id']}`** ({e['suggested_lifecycle']})")
            A(f"- {e['evidence_summary']}\n")

    A("## Proposed P233B Allowlist (if user authorizes execution)\n")
    A("> P233B is NOT authorized by this P233A plan alone. It requires separate explicit "
      "user authorization.\n")
    A("If authorized, P233B should be restricted to:")
    for f in result["p233b_allowlist_if_authorized"]:
        A(f"- `{f}`")
    A("")
    A("P233B action: add `_LifecycleStub` entries to `_NON_EXECUTABLE_STUBS` list in "
      "`replay_strategy_registry.py` for each of the 20 entries with their "
      "suggested lifecycle status. No DB write. No executable adapters. "
      "No production / recommendation logic change.\n")

    A("## Caveats\n")
    for c in result["caveats"]:
        A(f"- {c}")
    A("")
    A(f"## Final Classification\n`{result['final_classification']}`\n")
    A(f"> DB write: **{result['db_write_performed']}** | "
      f"Registry modified: **{result['registry_modified']}**\n")

    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines), encoding="utf-8")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> Dict[str, Any]:
    result = build_plan()

    assert not result["db_write_performed"], "BUG: DB write detected"
    assert not result["registry_modified"], "BUG: registry modification detected"

    out_json = OUTPUT_DIR / f"p233a_lifecycle_unresolved_registry_hygiene_plan_{DATE_TAG}.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"[P233A] JSON written: {out_json}")

    out_md = OUTPUT_DIR / f"p233a_lifecycle_unresolved_registry_hygiene_plan_{DATE_TAG}.md"
    write_markdown(result, out_md)
    print(f"[P233A] Markdown written: {out_md}")

    rej = result["lifecycle_suggestion_summary"]["REJECTED"]
    ret = result["lifecycle_suggestion_summary"]["RETIRED"]
    print(f"[P233A] Unresolved count: {result['unresolved_count']} "
          f"(REJECTED={rej}, RETIRED={ret})")
    print(f"[P233A] Classification: {result['final_classification']}")
    return result


if __name__ == "__main__":
    res = main()
    import sys
    sys.exit(0 if res.get("execution_status") == "PLAN_EXECUTED_OK" else 1)
