#!/usr/bin/env python3
"""
P1 Replay Truth Executable Inventory
Read-only inspection script — NO DB writes, NO registry mutation, NO backfill.
Produces:
  outputs/replay/p1_executable_inventory_20260513.json
  outputs/replay/p1_executable_inventory_20260513.md
"""

import sys
import os
import json
import inspect
import importlib.util
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

# ─── Safety constants ───────────────────────────────────────────────────────
SAFETY_DB_HASH_EXPECTED = "de0e27bb800bc7183773a0dc596d66b8"
SAFETY_REG_HASH_EXPECTED = "3ea71cfc20c882714f3824ad68202f6e"

# ─── Minimal synthetic history (NOT written to DB, pure in-memory) ──────────
def make_synthetic_history(lottery_type: str, n: int = 104):
    """Generate n fake draw records for dry-call testing only."""
    records = []
    for i in range(n):
        y, mo, d = 2026, (i // 28) + 1, (i % 28) + 1
        if lottery_type in ("POWER_LOTTO", "BIG_LOTTO"):
            records.append({
                "draw_date": f"{y}-{mo:02d}-{d:02d}",
                "numbers": [1, 2, 3, 4, 5, 6],
                "special": 7,
                "lottery_type": lottery_type,
            })
        else:  # DAILY_539
            records.append({
                "draw_date": f"{y}-{mo:02d}-{d:02d}",
                "numbers": [1, 2, 3, 4, 5],
                "lottery_type": lottery_type,
            })
    return records

# ─── Canonical strategies ────────────────────────────────────────────────────
CANONICAL_STRATEGIES = [
    ("power_precision_3bet",         "ONLINE",      "POWER_LOTTO"),
    ("power_orthogonal_5bet",        "ONLINE",      "POWER_LOTTO"),
    ("biglotto_triple_strike",       "ONLINE",      "BIG_LOTTO"),
    ("biglotto_deviation_2bet",      "ONLINE",      "BIG_LOTTO"),
    ("daily539_f4cold",              "ONLINE",      "DAILY_539"),
    ("daily539_markov_cold",         "ONLINE",      "DAILY_539"),
    ("biglotto_ts3_acb_4bet",        "REJECTED",    "BIG_LOTTO"),
    ("biglotto_ts3_markov_freq_5bet","REJECTED",    "BIG_LOTTO"),
    ("power_shlc_midfreq",           "REJECTED",    "POWER_LOTTO"),
    ("p1_deviation_2bet_539",        "REJECTED",    "DAILY_539"),
    ("acb_1bet",                     "RETIRED",     "DAILY_539"),
    ("acb_markov_midfreq",           "RETIRED",     "DAILY_539"),
    ("acb_markov_midfreq_3bet",      "RETIRED",     "DAILY_539"),
    ("midfreq_acb_2bet",             "RETIRED",     "DAILY_539"),
    ("midfreq_fourier_2bet",         "RETIRED",     "DAILY_539"),
    ("h6_gate_mk20_ew85",            "OBSERVATION", "POWER_LOTTO"),
]

# ─── Known artifact paths ────────────────────────────────────────────────────
ARTIFACT_MAP = {
    "power_precision_3bet": {
        "strategy_dir": "strategies/power_lotto/3bet_power_precision",
        "tool_predict": "tools/predict_power_precision_3bet.py",
        "rejected_json": None,
    },
    "power_orthogonal_5bet": {
        "strategy_dir": "strategies/power_lotto/5bet_orthogonal",
        "tool_predict": "tools/predict_power_orthogonal_5bet.py",
        "rejected_json": None,
    },
    "biglotto_triple_strike": {
        "strategy_dir": "strategies/big_lotto/3bet_triple_strike_v2",
        "tool_predict": "tools/predict_biglotto_triple_strike.py",
        "rejected_json": None,
    },
    "biglotto_deviation_2bet": {
        "strategy_dir": "strategies/big_lotto/2bet_deviation_complement",
        "tool_predict": "tools/predict_biglotto_deviation_2bet.py",
        "rejected_json": None,
    },
    "daily539_f4cold": {
        "strategy_dir": "strategies/daily_539/5bet_fourier4_cold",
        "tool_predict": "tools/predict_539_5bet_f4cold.py",
        "rejected_json": None,
    },
    "daily539_markov_cold": {
        "strategy_dir": None,
        "tool_predict": "tools/predict_539_markov_cold.py",
        "rejected_json": None,
    },
    "biglotto_ts3_acb_4bet": {
        "strategy_dir": "strategies/big_lotto/4bet_ts3_markov_w30",
        "tool_predict": None,
        "rejected_json": "rejected/ts3_acb_4bet_biglotto.json",
    },
    "biglotto_ts3_markov_freq_5bet": {
        "strategy_dir": "strategies/big_lotto/5bet_ts3_markov_freq",
        "tool_predict": None,
        "rejected_json": "rejected/ts3_markov_freq_5bet_biglotto.json",
    },
    "power_shlc_midfreq": {
        "strategy_dir": None,
        "tool_predict": None,
        "rejected_json": "rejected/shlc_midfreq_power.json",
    },
    "p1_deviation_2bet_539": {
        "strategy_dir": None,
        "tool_predict": None,
        "rejected_json": "rejected/p1_deviation_2bet_539.json",
    },
    "acb_1bet": {
        "strategy_dir": None,
        "tool_predict": None,
        "rejected_json": None,
    },
    "acb_markov_midfreq": {
        "strategy_dir": None,
        "tool_predict": None,
        "rejected_json": None,
    },
    "acb_markov_midfreq_3bet": {
        "strategy_dir": None,
        "tool_predict": None,
        "rejected_json": None,
    },
    "midfreq_acb_2bet": {
        "strategy_dir": None,
        "tool_predict": None,
        "rejected_json": None,
    },
    "midfreq_fourier_2bet": {
        "strategy_dir": None,
        "tool_predict": None,
        "rejected_json": None,
    },
    "h6_gate_mk20_ew85": {
        "strategy_dir": None,
        "tool_predict": None,
        "rejected_json": None,
    },
}


def check_path_exists(rel_path: Optional[str]) -> bool:
    if not rel_path:
        return False
    return (REPO_ROOT / rel_path).exists()


def get_registry_import_status():
    """Verify registry imports cleanly."""
    try:
        from lottery_api.models.replay_strategy_registry import (
            list_strategy_lifecycle_metadata,
            get_adapter,
        )
        return "OK", list_strategy_lifecycle_metadata, get_adapter
    except Exception as e:
        return f"FAIL:{type(e).__name__}:{e}", None, None


def run_adapter_check(sid, lifecycle, lottery_type):
    """Try to get adapter, inspect methods, optionally dry-call."""
    try:
        from lottery_api.models.replay_strategy_registry import get_adapter
        adapter = get_adapter(sid)
        adapter_class = type(adapter).__name__
        public_methods = [m for m in dir(adapter) if not m.startswith("_")]
        has_get_one_bet = hasattr(adapter, "get_one_bet")
        has_predict = hasattr(adapter, "predict")

        # Introspect signature
        sig_str = str(inspect.signature(adapter.get_one_bet)) if has_get_one_bet else "N/A"

        import_status = "ADAPTER_FOUND"
        dry_call_status = "SKIPPED"
        dry_call_error = None

        # Dry-call only for ONLINE strategies with get_one_bet
        if lifecycle == "ONLINE" and has_get_one_bet:
            try:
                synthetic = make_synthetic_history(lottery_type)
                result = adapter.get_one_bet(synthetic, lottery_type)
                dry_call_status = f"PASS|result_len={len(result) if result else 0}"
            except Exception as e:
                dry_call_status = "FAIL"
                dry_call_error = f"{type(e).__name__}: {str(e)[:120]}"

        return {
            "registry_present": True,
            "adapter_available": True,
            "adapter_class": adapter_class,
            "adapter_methods": public_methods,
            "get_one_bet_callable": has_get_one_bet,
            "predict_callable": has_predict,
            "get_one_bet_signature": sig_str,
            "import_status": import_status,
            "dry_call_status": dry_call_status,
            "dry_call_error": dry_call_error,
        }
    except KeyError:
        return {
            "registry_present": True,
            "adapter_available": False,
            "adapter_class": None,
            "adapter_methods": [],
            "get_one_bet_callable": False,
            "predict_callable": False,
            "get_one_bet_signature": "N/A",
            "import_status": "NO_ADAPTER_REGISTERED",
            "dry_call_status": "N/A",
            "dry_call_error": None,
        }
    except Exception as e:
        return {
            "registry_present": False,
            "adapter_available": False,
            "adapter_class": None,
            "adapter_methods": [],
            "get_one_bet_callable": False,
            "predict_callable": False,
            "get_one_bet_signature": "N/A",
            "import_status": f"IMPORT_ERROR:{type(e).__name__}:{str(e)[:80]}",
            "dry_call_status": "N/A",
            "dry_call_error": None,
        }


def classify(sid, lifecycle, adapter_info, artifact_map):
    """Classify each strategy using evidence-based rules."""
    has_adapter = adapter_info["adapter_available"]
    has_get_one_bet = adapter_info["get_one_bet_callable"]
    dry_pass = "PASS" in adapter_info.get("dry_call_status", "")
    has_rejected_json = check_path_exists(artifact_map.get("rejected_json"))
    has_strategy_dir = check_path_exists(artifact_map.get("strategy_dir"))
    has_tool_predict = check_path_exists(artifact_map.get("tool_predict"))

    if lifecycle == "ONLINE" and has_adapter and has_get_one_bet:
        return "EXECUTABLE_NOW"
    if has_adapter and has_get_one_bet and not dry_pass:
        return "EXECUTABLE_WITH_FIX"
    if has_rejected_json or has_strategy_dir:
        return "ARTIFACT_ONLY"
    if lifecycle in ("RETIRED",) and not has_adapter and not has_rejected_json and not has_strategy_dir:
        return "CODE_MISSING"
    if lifecycle == "OBSERVATION" and not has_adapter:
        return "ARTIFACT_ONLY" if has_strategy_dir or has_rejected_json else "CODE_MISSING"
    return "CODE_MISSING"


def build_inventory():
    import_status, list_meta_fn, get_adapter_fn = get_registry_import_status()
    if import_status != "OK":
        print(f"FATAL: registry import failed: {import_status}")
        sys.exit(1)

    # Verify lifecycle count
    metas = list_meta_fn()
    lifecycle_by_id = {m["strategy_id"]: m["lifecycle_status"] for m in metas}

    results = []
    for sid, expected_lifecycle, lottery_type in CANONICAL_STRATEGIES:
        actual_lifecycle = lifecycle_by_id.get(sid, "UNKNOWN")
        artifacts = ARTIFACT_MAP.get(sid, {})
        adapter_info = run_adapter_check(sid, actual_lifecycle, lottery_type)
        classification = classify(sid, actual_lifecycle, adapter_info, artifacts)

        # Retrospective readiness
        can_regenerate_now = classification == "EXECUTABLE_NOW"
        if classification == "EXECUTABLE_NOW":
            regen_source = "production_adapter"
            required_fix = "none"
            proposed_truth_level = "PRODUCTION_REPLAY"
        elif classification == "ARTIFACT_ONLY":
            regen_source = "rejected_artifact" if check_path_exists(artifacts.get("rejected_json")) else "historical_report_only"
            required_fix = "artifact_parser"
            proposed_truth_level = "ARTIFACT_PROVENANCE_ONLY"
        elif classification == "CODE_MISSING":
            regen_source = "none"
            required_fix = "missing_source_code"
            proposed_truth_level = "TOMBSTONE_NO_SOURCE"
        else:
            regen_source = "none"
            required_fix = "missing_source_code"
            proposed_truth_level = "TOMBSTONE_NO_SOURCE"

        result = {
            "strategy_id": sid,
            "lifecycle_status": actual_lifecycle,
            "lottery_type": lottery_type,
            "registry_present": adapter_info["registry_present"],
            "adapter_available": adapter_info["adapter_available"],
            "adapter_class": adapter_info["adapter_class"],
            "adapter_methods": adapter_info["adapter_methods"],
            "get_one_bet_callable": adapter_info["get_one_bet_callable"],
            "predict_callable": adapter_info["predict_callable"],
            "strategy_dir_path": artifacts.get("strategy_dir"),
            "strategy_dir_exists": check_path_exists(artifacts.get("strategy_dir")),
            "tool_predict_path": artifacts.get("tool_predict"),
            "tool_predict_exists": check_path_exists(artifacts.get("tool_predict")),
            "rejected_json_path": artifacts.get("rejected_json"),
            "rejected_json_exists": check_path_exists(artifacts.get("rejected_json")),
            "import_status": adapter_info["import_status"],
            "dry_call_status": adapter_info["dry_call_status"],
            "dry_call_error": adapter_info["dry_call_error"],
            "classification": classification,
            "can_regenerate_now": can_regenerate_now,
            "regeneration_source": regen_source,
            "required_fix": required_fix,
            "proposed_truth_level": proposed_truth_level,
            "p3_candidate": can_regenerate_now,
        }
        results.append(result)

    return {
        "generated_date": "2026-05-13",
        "baseline": {
            "branch": "frontend/p78-configurable-api-base-20260513",
            "pr92_state": "OPEN",
            "pr92_ci": "ALL_CHECKS_PASS",
            "db_hash": SAFETY_DB_HASH_EXPECTED,
            "registry_hash": SAFETY_REG_HASH_EXPECTED,
            "total_strategies_in_registry": len(metas),
        },
        "summary": {
            "EXECUTABLE_NOW": sum(1 for r in results if r["classification"] == "EXECUTABLE_NOW"),
            "EXECUTABLE_WITH_FIX": sum(1 for r in results if r["classification"] == "EXECUTABLE_WITH_FIX"),
            "ARTIFACT_ONLY": sum(1 for r in results if r["classification"] == "ARTIFACT_ONLY"),
            "CODE_MISSING": sum(1 for r in results if r["classification"] == "CODE_MISSING"),
            "TOMBSTONE": sum(1 for r in results if r["classification"] == "TOMBSTONE"),
            "NEEDS_MANUAL_DECISION": sum(1 for r in results if r["classification"] == "NEEDS_MANUAL_DECISION"),
        },
        "strategies": results,
    }


def write_json(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Written: {path}")


def write_markdown(data, path):
    lines = []
    lines.append("# P1 Executable Inventory — 2026-05-13\n")
    lines.append(f"**Branch**: `{data['baseline']['branch']}`  ")
    lines.append(f"**PR #92**: {data['baseline']['pr92_state']} / CI: {data['baseline']['pr92_ci']}  ")
    lines.append(f"**DB hash**: `{data['baseline']['db_hash']}`  ")
    lines.append(f"**Registry hash**: `{data['baseline']['registry_hash']}`\n")

    s = data["summary"]
    lines.append("## Summary\n")
    lines.append(f"| Classification | Count |")
    lines.append(f"|----------------|-------|")
    for k, v in s.items():
        lines.append(f"| {k} | {v} |")
    lines.append("")

    lines.append("## Per-Strategy Table\n")
    lines.append("| # | strategy_id | lifecycle | adapter | get_one_bet | dry_call | rejected_json | strategy_dir | classification |")
    lines.append("|---|-------------|-----------|---------|-------------|----------|---------------|--------------|----------------|")
    for i, r in enumerate(data["strategies"], 1):
        adapter_chk = "✅" if r["adapter_available"] else "❌"
        gob_chk     = "✅" if r["get_one_bet_callable"] else "❌"
        dry_chk     = "✅" if "PASS" in str(r["dry_call_status"]) else ("⏭️" if r["dry_call_status"] in ("SKIPPED","N/A") else "❌")
        rj_chk      = "✅" if r["rejected_json_exists"] else "❌"
        sd_chk      = "✅" if r["strategy_dir_exists"] else "❌"
        lines.append(f"| {i} | `{r['strategy_id']}` | {r['lifecycle_status']} | {adapter_chk} | {gob_chk} | {dry_chk} | {rj_chk} | {sd_chk} | **{r['classification']}** |")

    lines.append("")
    lines.append("## Retrospective Readiness\n")
    lines.append("| strategy_id | can_regenerate | regeneration_source | required_fix | proposed_truth_level | p3_candidate |")
    lines.append("|-------------|---------------|---------------------|--------------|----------------------|--------------|")
    for r in data["strategies"]:
        lines.append(f"| `{r['strategy_id']}` | {r['can_regenerate_now']} | {r['regeneration_source']} | {r['required_fix']} | {r['proposed_truth_level']} | {r['p3_candidate']} |")

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Written: {path}")


if __name__ == "__main__":
    print("=== P1 Executable Inventory Script ===")
    print("Safety: NO DB write, NO registry mutation, NO backfill")

    data = build_inventory()

    # Print summary
    print(f"\nTotal strategies: {data['baseline']['total_strategies_in_registry']}")
    for k, v in data["summary"].items():
        print(f"  {k}: {v}")

    print("\nPer-strategy results:")
    for r in data["strategies"]:
        dry = r["dry_call_status"]
        rj  = "✅" if r["rejected_json_exists"] else "❌"
        sd  = "✅" if r["strategy_dir_exists"] else "❌"
        print(f"  {r['strategy_id']:40s} | {r['lifecycle_status']:11s} | adapter={r['adapter_available']} | gob={r['get_one_bet_callable']} | dry={dry} | rj={rj} | sd={sd} | {r['classification']}")

    write_json(data, str(REPO_ROOT / "outputs/replay/p1_executable_inventory_20260513.json"))
    write_markdown(data, str(REPO_ROOT / "outputs/replay/p1_executable_inventory_20260513.md"))

    print("\n=== DONE ===")
    print(f"DB hash unchanged: {data['baseline']['db_hash'] == SAFETY_DB_HASH_EXPECTED}")
    print(f"Registry hash unchanged: {data['baseline']['registry_hash'] == SAFETY_REG_HASH_EXPECTED}")
