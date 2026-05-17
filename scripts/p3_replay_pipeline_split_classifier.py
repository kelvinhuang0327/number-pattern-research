#!/usr/bin/env python3
"""Dry-run classifier for the replay historical reconstruction vs waiting split.

Hard rules:
- No DB writes
- No draw imports
- No replay row generation
- No prediction updates
- No strategy execution
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SOURCE_INVENTORY = PROJECT_ROOT / "outputs" / "replay" / "p0_strategy_universe_inventory_20260517.json"
SOURCE_INVENTORY_GIT_REF = "7c48cfd"
P1_FIXTURE = PROJECT_ROOT / "outputs" / "replay" / "p1_lifecycle_formalization_fixture_20260517.json"
WATCHER_GLOB = "outputs/replay/p6*_post_merge_watcher_verify_20260517.json"
WATCHER_REPORT_GLOB = "outputs/replay/p6*_scheduled_monitor_rerun_summary_20260517.json"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lottery_api.models.replay_pipeline_contract import (  # noqa: E402
    PIPELINE_STATES,
    classify_pipeline,
    can_write_replay_rows,
    blocks_historical_coverage,
)


def _load_json_text_from_git(ref: str, rel_path: str) -> str:
    return subprocess.check_output(["git", "show", f"{ref}:{rel_path}"], cwd=PROJECT_ROOT, text=True)


def _load_json_from_path_or_git(path: Path, git_ref: str | None = None) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if git_ref is None:
        raise FileNotFoundError(str(path))
    rel = str(path.relative_to(PROJECT_ROOT))
    return json.loads(_load_json_text_from_git(git_ref, rel))


def _load_inventory() -> dict:
    return _load_json_from_path_or_git(SOURCE_INVENTORY, SOURCE_INVENTORY_GIT_REF)


def _load_optional_fixture() -> dict | None:
    if P1_FIXTURE.exists():
        return json.loads(P1_FIXTURE.read_text(encoding="utf-8"))
    return None


def _load_watcher_targets() -> list[dict]:
    targets: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for pattern in (WATCHER_GLOB, WATCHER_REPORT_GLOB):
        for path in sorted(PROJECT_ROOT.glob(pattern)):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            for target in payload.get("targets", []):
                key = (str(target.get("lottery_type") or ""), str(target.get("strategy_name") or ""))
                if not key[0] or not key[1] or key in seen:
                    continue
                seen.add(key)
                targets.append({
                    "lottery_type": key[0],
                    "strategy_name": key[1],
                    "target_draw": target.get("target_draw"),
                    "pending_item_count": target.get("pending_item_count"),
                    "readiness_state": target.get("readiness_state"),
                })
    return targets


def _build_indexes(strategies: list[dict]) -> tuple[dict[str, dict], dict[str, dict]]:
    by_id: dict[str, dict] = {}
    by_name: dict[str, dict] = {}
    for row in strategies:
        sid = str(row.get("strategy_id") or "").strip()
        if sid:
            by_id[sid] = row
        name = str(row.get("display_name") or "").strip()
        if name:
            by_name[name.lower()] = row
    return by_id, by_name


def _resolve_future_waiting_strategy_id(target: dict, by_id: dict[str, dict], by_name: dict[str, dict]) -> str | None:
    strategy_name = str(target.get("strategy_name") or "").strip()
    lottery_type = str(target.get("lottery_type") or "").strip().upper()

    if strategy_name.lower() in by_name:
        return by_name[strategy_name.lower()]["strategy_id"]

    if lottery_type == "BIG_LOTTO" and "triple strike" in strategy_name.lower():
        return "biglotto_triple_strike"
    if lottery_type == "POWER_LOTTO" and "power precision" in strategy_name.lower():
        return "power_precision_3bet"
    return None


def _has_replay_rows(entry: dict) -> bool:
    return any("strategy_prediction_replays" in path for path in entry.get("source_paths", []))


def _candidate_reason(entry: dict) -> str:
    if _has_replay_rows(entry):
        return "historical_replay_rows_present; eligible_for_dry_run_reconstruction_baseline"
    historical_source = entry.get("historical_record_source") or "unknown"
    if historical_source == "none":
        return "no_historical_records_anywhere"
    return f"historical_record_source={historical_source}; dry_run_only"


def _future_waiting_reason(target: dict) -> str:
    return (
        "pending_draw_result|prediction_items_waiting|"
        f"target_draw={target.get('target_draw')}|"
        f"pending_item_count={target.get('pending_item_count')}"
    )


def _display_only_reason(entry: dict) -> str:
    return "no_historical_records_anywhere|inventory_only"


def _unsupported_reason(entry: dict) -> str:
    missing = []
    if not entry.get("strategy_id"):
        missing.append("missing_strategy_id")
    if not entry.get("source_paths"):
        missing.append("missing_source_paths")
    if not missing:
        missing.append("ambiguous_metadata")
    return "|".join(missing)


def _build_blocking_map() -> list[dict[str, Any]]:
    return [
        {
            "file_path": "lottery_api/routes/replay.py",
            "current_assumption": "history, summary, and fixture paths are handled as one replay surface with lifecycle filtering but no explicit pipeline split.",
            "why_it_mixes_reconstruction_waiting": "The endpoint can show historical rows and fixture rows, yet it does not distinguish historical reconstruction from future draw waiting.",
            "recommended_split": "Keep the endpoint read-only, but attach pipeline classification metadata so historical reconstruction and future waiting are rendered as separate concerns.",
            "risk_level": "MEDIUM",
            "code_change_required": "NO_FOR_P3_DRY_RUN",
        },
        {
            "file_path": "scripts/p6_next_draw_watcher_readonly.py",
            "current_assumption": "Watcher output represents pending prediction_items awaiting official draw publication.",
            "why_it_mixes_reconstruction_waiting": "If reused as replay evidence, it collapses future waiting into historical coverage accounting.",
            "recommended_split": "Keep it as FUTURE_WAITING only and exclude it from historical replay coverage denominators.",
            "risk_level": "LOW",
            "code_change_required": "NO",
        },
        {
            "file_path": "scripts/p3_retrospective_regeneration_dryrun.py",
            "current_assumption": "Retrospective regeneration already behaves like historical replay reconstruction, but only as a dry-run utility.",
            "why_it_mixes_reconstruction_waiting": "The script name and surrounding docs can be read as a replay regeneration path rather than a pure historical reconstruction lane.",
            "recommended_split": "Classify its outputs as HISTORICAL_RECONSTRUCTION and keep its result dry-run only.",
            "risk_level": "LOW",
            "code_change_required": "NO",
        },
        {
            "file_path": "scripts/replay_lifecycle_drift_guard.py",
            "current_assumption": "The drift guard validates database row distribution only and is intentionally blind to pipeline semantics.",
            "why_it_mixes_reconstruction_waiting": "It can be mistakenly treated as replay coverage logic even though it only guards baseline drift.",
            "recommended_split": "Leave drift guarding separate from pipeline classification; use the P3 classifier for coverage splits.",
            "risk_level": "LOW",
            "code_change_required": "NO",
        },
        {
            "file_path": "docs/replay/strategy_historical_replay_roadmap_20260515.md",
            "current_assumption": "The roadmap interleaves lifecycle, replay, and waiting-state language in one planning document.",
            "why_it_mixes_reconstruction_waiting": "The same doc describes historical replay coverage and waiting-for-draw monitoring, which obscures the product split.",
            "recommended_split": "Use a dedicated historical reconstruction policy and keep future waiting in operational watcher docs.",
            "risk_level": "LOW",
            "code_change_required": "NO",
        },
    ]


def _string_guard(payload: Any) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, str):
                assert value not in {"TBD", "TODO", "null"}, f"placeholder found in {key}"
            _string_guard(value)
    elif isinstance(payload, list):
        for item in payload:
            _string_guard(item)


def classify_inventory() -> dict:
    inventory = _load_inventory()
    fixture = _load_optional_fixture()
    watcher_targets = _load_watcher_targets()
    blocking_map = _build_blocking_map()

    strategies = inventory.get("strategies") or []
    if not isinstance(strategies, list):
        raise TypeError("inventory strategies must be a list")

    by_id, by_name = _build_indexes(strategies)
    future_waiting_ids: set[str] = set()
    future_waiting_candidates: list[dict] = []
    for target in watcher_targets:
        sid = _resolve_future_waiting_strategy_id(target, by_id, by_name)
        if not sid:
            continue
        future_waiting_ids.add(sid)
        entry = by_id.get(sid, {})
        future_waiting_candidates.append({
            "strategy_id": sid,
            "display_name": entry.get("display_name") or target.get("strategy_name") or sid,
            "lifecycle_state": entry.get("lifecycle_state") or "UNKNOWN",
            "lottery_type": entry.get("lottery_type") or target.get("lottery_type") or "UNSPECIFIED",
            "historical_record_source": entry.get("historical_record_source") or "none",
            "reason": _future_waiting_reason(target),
            "pipeline": "FUTURE_WAITING",
            "blocks_historical_coverage": blocks_historical_coverage({"future_waiting": True, "strategy_id": sid, "source_paths": entry.get("source_paths") or ["watcher_target"]}),
            "dry_run_only": True,
            "target_draw": target.get("target_draw"),
            "pending_item_count": target.get("pending_item_count"),
        })

    historical_reconstruction_candidates: list[dict] = []
    display_only_candidates: list[dict] = []
    unsupported_candidates: list[dict] = []
    by_pipeline = Counter()
    by_lifecycle_and_pipeline = {
        lc: {pipeline: 0 for pipeline in PIPELINE_STATES}
        for lc in inventory.get("by_lifecycle", {}).keys()
    }
    if not by_lifecycle_and_pipeline:
        for lc in ("PRODUCTION", "WATCHING", "PROVISIONAL", "REJECTED", "OFFLINE", "EXPERIMENTAL", "UNKNOWN"):
            by_lifecycle_and_pipeline[lc] = {pipeline: 0 for pipeline in PIPELINE_STATES}

    for entry in strategies:
        sid = str(entry.get("strategy_id") or "").strip()
        lifecycle_state = str(entry.get("lifecycle_state") or "UNKNOWN").strip() or "UNKNOWN"
        lottery_type = str(entry.get("lottery_type") or "UNSPECIFIED").strip() or "UNSPECIFIED"
        source_paths = entry.get("source_paths") or []
        pipeline = classify_pipeline({
            **entry,
            "future_waiting": sid in future_waiting_ids,
            "watcher_target": sid in future_waiting_ids,
        })
        if pipeline == "FUTURE_WAITING":
            by_pipeline[pipeline] += 1
            by_lifecycle_and_pipeline.setdefault(lifecycle_state, {p: 0 for p in PIPELINE_STATES})
            by_lifecycle_and_pipeline[lifecycle_state][pipeline] += 1
            continue

        if pipeline == "HISTORICAL_RECONSTRUCTION":
            has_replay_rows = _has_replay_rows(entry)
            candidate = {
                "strategy_id": sid,
                "display_name": entry.get("display_name") or sid,
                "lifecycle_state": lifecycle_state,
                "lottery_type": lottery_type,
                "historical_record_source": entry.get("historical_record_source") or "none",
                "has_historical_predictions": bool(entry.get("has_historical_predictions")),
                "has_replay_rows": has_replay_rows,
                "pipeline": pipeline,
                "dry_run_only": True,
                "reason": _candidate_reason(entry),
                "notes": entry.get("notes") or "",
            }
            historical_reconstruction_candidates.append(candidate)
            by_pipeline[pipeline] += 1
            by_lifecycle_and_pipeline.setdefault(lifecycle_state, {p: 0 for p in PIPELINE_STATES})
            by_lifecycle_and_pipeline[lifecycle_state][pipeline] += 1
            continue

        if pipeline == "DISPLAY_ONLY":
            candidate = {
                "strategy_id": sid,
                "display_name": entry.get("display_name") or sid,
                "lifecycle_state": lifecycle_state,
                "lottery_type": lottery_type,
                "historical_record_source": entry.get("historical_record_source") or "none",
                "pipeline": pipeline,
                "reason": _display_only_reason(entry),
            }
            display_only_candidates.append(candidate)
            by_pipeline[pipeline] += 1
            by_lifecycle_and_pipeline.setdefault(lifecycle_state, {p: 0 for p in PIPELINE_STATES})
            by_lifecycle_and_pipeline[lifecycle_state][pipeline] += 1
            continue

        candidate = {
            "strategy_id": sid or "UNKNOWN",
            "display_name": entry.get("display_name") or sid or "UNKNOWN",
            "lifecycle_state": lifecycle_state,
            "lottery_type": lottery_type,
            "historical_record_source": entry.get("historical_record_source") or "none",
            "pipeline": "UNSUPPORTED",
            "reason": _unsupported_reason(entry),
        }
        unsupported_candidates.append(candidate)
        by_pipeline["UNSUPPORTED"] += 1
        by_lifecycle_and_pipeline.setdefault(lifecycle_state, {p: 0 for p in PIPELINE_STATES})
        by_lifecycle_and_pipeline[lifecycle_state]["UNSUPPORTED"] += 1

    total_strategies = len(strategies)
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_inventory": "outputs/replay/p0_strategy_universe_inventory_20260517.json",
        "source_inventory_ref": SOURCE_INVENTORY_GIT_REF,
        "optional_p1_fixture_present": bool(fixture),
        "blocking_map": blocking_map,
        "total_strategies": total_strategies,
        "by_pipeline": {pipeline: int(by_pipeline.get(pipeline, 0)) for pipeline in PIPELINE_STATES},
        "by_lifecycle_and_pipeline": by_lifecycle_and_pipeline,
        "historical_reconstruction_candidates": historical_reconstruction_candidates,
        "future_waiting_candidates": future_waiting_candidates,
        "display_only_candidates": display_only_candidates,
        "unsupported_candidates": unsupported_candidates,
        "safety": {
            "db_write": False,
            "draw_import": False,
            "replay_row_generation": False,
            "prediction_update": False,
            "strategy_execution": False,
        },
    }

    if result["total_strategies"] != sum(result["by_pipeline"].values()):
        raise AssertionError("total/by_pipeline mismatch")

    if result["total_strategies"] != sum(inventory.get("by_lifecycle", {}).values()):
        raise AssertionError("total/by_lifecycle mismatch")

    _string_guard(result)
    return result


def _build_report(payload: dict) -> str:
    lines: list[str] = []
    a = lines.append
    a("# P3 Replay Pipeline Split Report - 20260517")
    a("")
    a(f"Generated at: `{payload['generated_at']}`")
    a("")
    a("## Final Classification")
    a("P3_REPLAY_PIPELINE_SPLIT_COMPLETED")
    a("")
    a("## P0/P1 Input Summary")
    a("- Total strategies: **506**")
    a("- Lifecycle breakdown: PRODUCTION 68, WATCHING 7, PROVISIONAL 6, REJECTED 90, OFFLINE 0, EXPERIMENTAL 307, UNKNOWN 28")
    a("- Replay coverage gap: 13 strategies with replay rows, 86 with historical records but no replay, 407 with no records anywhere")
    a("- P1 lifecycle states: PRODUCTION / WATCHING / PROVISIONAL / REJECTED / OFFLINE / EXPERIMENTAL / UNKNOWN")
    a("")
    a("## Blocking Map")
    for row in payload["blocking_map"]:
        a(f"- `{row['file_path']}`")
        a(f"  - Current assumption: {row['current_assumption']}")
        a(f"  - Why it mixes reconstruction / waiting: {row['why_it_mixes_reconstruction_waiting']}")
        a(f"  - Recommended split: {row['recommended_split']}")
        a(f"  - Risk level: {row['risk_level']} | Code change required: {row['code_change_required']}")
    a("")
    a("## Pipeline Split Result")
    for pipeline in PIPELINE_STATES:
        a(f"- {pipeline}: {payload['by_pipeline'][pipeline]}")
    a("")
    a("## Future Waiting Summary")
    a(f"- Count: {len(payload['future_waiting_candidates'])}")
    a("- These strategies are waiting on official draw publication and do not block historical coverage.")
    a("")
    a("## Display-Only / Unsupported Summary")
    a(f"- DISPLAY_ONLY: {len(payload['display_only_candidates'])}")
    a(f"- UNSUPPORTED: {len(payload['unsupported_candidates'])}")
    a("")
    a("## Top Historical Reconstruction Candidates")
    for row in payload["historical_reconstruction_candidates"][:10]:
        a(
            f"- `{row['strategy_id']}` | {row['lifecycle_state']} | {row['lottery_type']} | "
            f"{row['historical_record_source']} | {row['reason']}"
        )
    a("")
    a("## Safety Confirmation")
    a("- No DB writes")
    a("- No draw imports")
    a("- No replay rows generated")
    a("- No prediction updates")
    a("- No strategy execution")
    a("")
    a("## Next Step")
    a("Proceed to P4 replay page product acceptance, or move to P5 persistence/deployment source-of-truth decision after CTO review.")
    return "\n".join(lines) + "\n"


def _build_policy_doc(payload: dict) -> str:
    lines = [
        "# P3 Historical Reconstruction vs Future Waiting Policy",
        "",
        "1. Historical reconstruction does not wait for future draws.",
        "2. Future waiting must not block historical coverage.",
        "3. The 86 strategies with historical records but no replay rows are the next backfill-planning denominator.",
        "4. The 407 strategies with no records anywhere remain DISPLAY_ONLY or wait for future data policy changes.",
        "5. UNKNOWN lifecycle entries are not production-safe apply candidates.",
        "6. This phase does not write DB state; it only emits dry-run classification and policy artifacts.",
        "7. P4 can use the classification to review replay page acceptance, and P5 can use it to decide persistence / deployment source of truth.",
        "",
        "## Current Split",
        "",
        f"- HISTORICAL_RECONSTRUCTION: {payload['by_pipeline']['HISTORICAL_RECONSTRUCTION']}",
        f"- FUTURE_WAITING: {payload['by_pipeline']['FUTURE_WAITING']}",
        f"- DISPLAY_ONLY: {payload['by_pipeline']['DISPLAY_ONLY']}",
        f"- UNSUPPORTED: {payload['by_pipeline']['UNSUPPORTED']}",
        "",
        "## Safety",
        "",
        "- db_write: false",
        "- draw_import: false",
        "- replay_row_generation: false",
        "- prediction_update: false",
        "- strategy_execution: false",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-json",
        default=str(PROJECT_ROOT / "outputs" / "replay" / "p3_replay_pipeline_split_20260517.json"),
    )
    parser.add_argument(
        "--output-md",
        default=str(PROJECT_ROOT / "docs" / "replay" / "p3_replay_pipeline_split_report_20260517.md"),
    )
    parser.add_argument(
        "--policy-md",
        default=str(PROJECT_ROOT / "docs" / "replay" / "p3_historical_reconstruction_policy_20260517.md"),
    )
    args = parser.parse_args()

    payload = classify_inventory()
    out_json = Path(args.output_json)
    out_md = Path(args.output_md)
    policy_md = Path(args.policy_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    policy_md.parent.mkdir(parents=True, exist_ok=True)

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(_build_report(payload), encoding="utf-8")
    policy_md.write_text(_build_policy_doc(payload), encoding="utf-8")

    print(json.dumps({
        "status": "PASS",
        "total_strategies": payload["total_strategies"],
        "by_pipeline": payload["by_pipeline"],
        "output_json": str(out_json.relative_to(PROJECT_ROOT)),
        "output_md": str(out_md.relative_to(PROJECT_ROOT)),
        "policy_md": str(policy_md.relative_to(PROJECT_ROOT)),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
