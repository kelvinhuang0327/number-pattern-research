#!/usr/bin/env python3
"""
p1_catalog_visibility_plan.py
================================
P1 Catalog Visibility — Dry-run catalog expansion planner.

MISSION: Read-only scan of DB + code registry + artifact sources to produce
a dry-run plan showing which artifact-level strategies can be registered for
catalog visibility (NO_DATA entries, no replay row generation).

HARD CONSTRAINTS:
  - NO DB writes (read-only throughout)
  - NO draw import
  - NO replay row generation
  - NO prediction updates
  - NO strategy execution

Usage:
    python3 scripts/p1_catalog_visibility_plan.py

Outputs:
    outputs/replay/p1_catalog_visibility_plan_20260518.json
    docs/replay/p1_catalog_visibility_plan_20260518.md
"""
from __future__ import annotations

import datetime
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
INVENTORY_PATH = PROJECT_ROOT / "outputs" / "replay" / "p1_strategy_lifecycle_inventory_20260511.json"
REJECTED_DIR = PROJECT_ROOT / "rejected"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "replay"
DOCS_DIR = PROJECT_ROOT / "docs" / "replay"

DATE_SUFFIX = "20260518"

# ─── Load code registry ───────────────────────────────────────────────────────

def load_code_registry() -> list[dict]:
    """Load all strategies from the code registry (read-only)."""
    from lottery_api.models.replay_strategy_registry import list_strategy_lifecycle_metadata
    return list_strategy_lifecycle_metadata()


# ─── Load inventory JSON ──────────────────────────────────────────────────────

def load_inventory() -> dict:
    """Load the P1 strategy lifecycle inventory JSON."""
    if not INVENTORY_PATH.exists():
        return {"candidates": [], "total": 0}
    return json.loads(INVENTORY_PATH.read_text())


# ─── Scan rejected JSONs ──────────────────────────────────────────────────────

def scan_rejected_jsons() -> list[dict]:
    """
    Scan rejected/ directory for strategy JSON files.
    Returns list of dicts: {strategy_id, display_name, lottery_type, source_path, blocked_reason}
    """
    results = []
    if not REJECTED_DIR.exists():
        return results

    for f in sorted(REJECTED_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
        except Exception:
            # Not parseable — try to infer strategy_id from filename
            results.append({
                "strategy_id": f.stem,
                "display_name": f.stem,
                "lottery_type": _infer_lottery_from_path(str(f)),
                "source_path": str(f.relative_to(PROJECT_ROOT)),
                "blocked_reason": "JSON parse error",
                "parse_ok": False,
            })
            continue

        strategy_id = data.get("strategy_id", f.stem)
        results.append({
            "strategy_id": strategy_id,
            "display_name": data.get("strategy", data.get("display_name", strategy_id)),
            "lottery_type": _infer_lottery_from_path(str(f)),
            "source_path": str(f.relative_to(PROJECT_ROOT)),
            "blocked_reason": data.get("blocked_reason", data.get("decision", "")),
            "parse_ok": True,
        })
    return results


def _infer_lottery_from_path(path: str) -> str:
    """Infer lottery type from file path / filename."""
    p = path.lower()
    if "539" in p or "daily" in p:
        return "DAILY_539"
    elif "power" in p or "powerlotto" in p:
        return "POWER_LOTTO"
    elif "biglotto" in p or "big_lotto" in p:
        return "BIG_LOTTO"
    return "UNKNOWN"


# ─── DB inspection (read-only) ────────────────────────────────────────────────

def get_db_strategy_replay_row_counts(con: sqlite3.Connection) -> dict[str, int]:
    """
    Returns strategy_scope -> row_count from strategy_replay_runs.
    strategy_scope may be comma-separated (multi-strategy runs).
    """
    counts: dict[str, int] = {}
    try:
        rows = con.execute("SELECT strategy_scope, COUNT(*) FROM strategy_replay_runs GROUP BY strategy_scope").fetchall()
        for scope, cnt in rows:
            if scope:
                for sid in scope.split(","):
                    sid = sid.strip()
                    counts[sid] = counts.get(sid, 0) + cnt
    except Exception:
        pass
    return counts


def get_db_prediction_strategy_names(con: sqlite3.Connection) -> set[str]:
    """Returns set of strategy_name values from prediction_runs."""
    names = set()
    try:
        rows = con.execute("SELECT DISTINCT strategy_name FROM prediction_runs WHERE strategy_name IS NOT NULL").fetchall()
        for (name,) in rows:
            if name:
                names.add(name)
    except Exception:
        pass
    return names


# ─── Plan builder ─────────────────────────────────────────────────────────────

# Known bogus IDs from inventory (generic names, not real strategies)
_BOGUS_IDS = frozenset({"big_lotto", "daily_539", "power_lotto", "strategy"})

# Known lifecycle mapping for UNKNOWN → inferred lifecycle
_UNKNOWN_TO_LIFECYCLE: dict[str, str] = {}  # Will be set from H-codes (all REJECTED based on MEMORY.md)


def build_plan() -> dict:
    """
    Build the full catalog expansion plan (dry-run, no DB writes).
    Returns a dict matching the required JSON schema.
    """
    generated_at = datetime.datetime.utcnow().isoformat() + "Z"

    # 1. Load code registry
    code_strats = load_code_registry()
    code_registry_ids = {s["strategy_id"] for s in code_strats}
    code_registry_map = {s["strategy_id"]: s for s in code_strats}

    # 2. Load inventory
    inventory = load_inventory()
    inventory_candidates = inventory.get("candidates", [])

    # 3. Scan rejected JSONs
    rejected_jsons = scan_rejected_jsons()
    rejected_json_map = {r["strategy_id"]: r for r in rejected_jsons}

    # 4. Open DB read-only
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        replay_row_counts = get_db_strategy_replay_row_counts(con)
        prediction_names = get_db_prediction_strategy_names(con)
    finally:
        con.close()

    # ─── Categorize entries ────────────────────────────────────────────────────

    entries = []
    skipped_entries = []

    # A) Existing code registry strategies (all 18)
    for sid, smeta in code_registry_map.items():
        replay_rows = replay_row_counts.get(sid, 0)
        has_rows = replay_rows > 0
        lc_raw = smeta.get("lifecycle_status", "ONLINE")

        # Map lifecycle
        if lc_raw == "ONLINE":
            lc_enum = "ONLINE"
            vis = "REGISTERED_WITH_REPLAY_ROWS" if has_rows else "REGISTERED_NO_DATA"
        elif lc_raw == "REJECTED":
            lc_enum = "REJECTED"
            vis = "REGISTERED_WITH_REPLAY_ROWS" if has_rows else "REGISTERED_NO_DATA"
        elif lc_raw == "RETIRED":
            lc_enum = "RETIRED"
            vis = "REGISTERED_WITH_REPLAY_ROWS" if has_rows else "REGISTERED_NO_DATA"
        elif lc_raw == "OBSERVATION":
            lc_enum = "OBSERVATION"
            vis = "REGISTERED_WITH_REPLAY_ROWS" if has_rows else "REGISTERED_NO_DATA"
        else:
            lc_enum = lc_raw
            vis = "REGISTERED_WITH_REPLAY_ROWS" if has_rows else "REGISTERED_NO_DATA"

        no_data_reason = None
        if not has_rows:
            no_data_reason = f"NO_REPLAY_ROWS: strategy is {lc_enum}, not yet backfilled"

        # Source paths
        source_paths = []
        rj = rejected_json_map.get(sid)
        if rj:
            source_paths.append(rj["source_path"])
        if not source_paths:
            # Try rejected/ by common name patterns
            candidates_for_id = [r for r in rejected_jsons if r["strategy_id"] == sid]
            source_paths = [r["source_path"] for r in candidates_for_id]

        # Lottery type
        lottery_type = smeta.get("supported_lottery_types", ["UNKNOWN"])[0] if smeta.get("supported_lottery_types") else "UNKNOWN"

        entries.append({
            "strategy_id": sid,
            "display_name": smeta.get("strategy_name", sid),
            "lottery_type": lottery_type,
            "lifecycle_state": lc_enum,
            "catalog_visibility_state": vis,
            "source_paths": source_paths,
            "artifact_source_type": "CODE_REGISTRY",
            "has_replay_rows": has_rows,
            "replay_row_count": replay_rows,
            "has_historical_predictions": smeta.get("strategy_name", sid) in prediction_names or sid in prediction_names,
            "no_data_reason": no_data_reason,
            "provenance_hash": hashlib.sha256((sid + "|CODE_REGISTRY").encode()).hexdigest(),
            "created_by_phase": "P1_CATALOG_VISIBILITY_20260518",
            "dry_run_only": True,
            "is_new_entry": False,
        })

    # B) Artifact candidates (from inventory, NOT in code registry)
    processed_artifact_ids = set()
    for cand in inventory_candidates:
        sid = cand.get("strategy_id", "")
        if not sid or sid in code_registry_ids or sid in _BOGUS_IDS:
            if sid in _BOGUS_IDS:
                skipped_entries.append({
                    "strategy_id": sid,
                    "reason": "BOGUS_ID: generic name from inventory scan (MEMORY.md or strategy.yaml)",
                    "source_paths": cand.get("source_paths", []),
                })
            continue

        lc_raw = cand.get("lifecycle_status", "UNKNOWN")
        if lc_raw == "UNKNOWN":
            # H-codes are REJECTED per MEMORY.md; others need verification
            if sid.startswith("H") and sid[1:].isdigit():
                lc_enum = "REJECTED"
            else:
                # Cannot safely determine lifecycle — mark ARTIFACT_ONLY
                lc_enum = "ARTIFACT_ONLY"
        elif lc_raw == "REJECTED":
            lc_enum = "REJECTED"
        else:
            lc_enum = lc_raw

        # Artifact candidates must NOT be ONLINE
        if lc_enum == "ONLINE":
            skipped_entries.append({
                "strategy_id": sid,
                "reason": "LIFECYCLE_CONFLICT: UNKNOWN artifact cannot be ONLINE",
                "source_paths": cand.get("source_paths", []),
            })
            continue

        source_paths = cand.get("source_paths", [])
        rj = rejected_json_map.get(sid)
        if rj and rj["source_path"] not in source_paths:
            source_paths = list(source_paths) + [rj["source_path"]]

        lottery_type = cand.get("lottery_type", "UNKNOWN")
        if lottery_type not in ("BIG_LOTTO", "DAILY_539", "POWER_LOTTO", "CROSS_GAME", "UNKNOWN"):
            lottery_type = "UNKNOWN"

        blocked_reason = cand.get("blocked_reason", "Rejected in governance review")

        entries.append({
            "strategy_id": sid,
            "display_name": cand.get("display_name", sid),
            "lottery_type": lottery_type,
            "lifecycle_state": lc_enum,
            "catalog_visibility_state": "ARTIFACT_CANDIDATE",
            "source_paths": source_paths,
            "artifact_source_type": "RESEARCH_INVENTORY",
            "has_replay_rows": False,
            "replay_row_count": 0,
            "has_historical_predictions": False,
            "no_data_reason": f"NO_REPLAY_ROWS: {blocked_reason}",
            "provenance_hash": cand.get("source_provenance_hash") or hashlib.sha256((sid + "|".join(sorted(source_paths))).encode()).hexdigest(),
            "created_by_phase": "P1_CATALOG_VISIBILITY_20260518",
            "dry_run_only": True,
            "is_new_entry": True,
        })
        processed_artifact_ids.add(sid)

    # C) Rejected JSONs not yet in inventory or code registry
    for sid, rj in rejected_json_map.items():
        if sid in code_registry_ids or sid in processed_artifact_ids or sid in _BOGUS_IDS:
            continue
        # Extra artifact from rejected/ folder not in inventory
        entries.append({
            "strategy_id": sid,
            "display_name": rj.get("display_name", sid),
            "lottery_type": rj.get("lottery_type", "UNKNOWN"),
            "lifecycle_state": "REJECTED",
            "catalog_visibility_state": "ARTIFACT_CANDIDATE",
            "source_paths": [rj["source_path"]],
            "artifact_source_type": "REJECTED_JSON",
            "has_replay_rows": False,
            "replay_row_count": 0,
            "has_historical_predictions": False,
            "no_data_reason": f"NO_REPLAY_ROWS: {rj.get('blocked_reason', 'Rejected strategy from artifact')}",
            "provenance_hash": hashlib.sha256((sid + rj["source_path"]).encode()).hexdigest(),
            "created_by_phase": "P1_CATALOG_VISIBILITY_20260518",
            "dry_run_only": True,
            "is_new_entry": True,
        })
        processed_artifact_ids.add(sid)

    # ─── Aggregate stats ───────────────────────────────────────────────────────

    runtime_canonical_count = len(code_registry_ids)
    artifact_candidates = [e for e in entries if e["catalog_visibility_state"] == "ARTIFACT_CANDIDATE"]
    new_entries = [e for e in entries if e.get("is_new_entry", False)]
    no_data_entries = [e for e in entries if not e["has_replay_rows"]]
    existing_updates = [e for e in entries if not e.get("is_new_entry", False)]

    # By lottery type
    by_lottery: dict[str, dict] = {}
    for e in entries:
        lt = e["lottery_type"]
        if lt not in by_lottery:
            by_lottery[lt] = {"total": 0, "new": 0, "no_data": 0}
        by_lottery[lt]["total"] += 1
        if e.get("is_new_entry"):
            by_lottery[lt]["new"] += 1
        if not e["has_replay_rows"]:
            by_lottery[lt]["no_data"] += 1

    # By lifecycle
    by_lifecycle: dict[str, dict] = {}
    for e in entries:
        lc = e["lifecycle_state"]
        if lc not in by_lifecycle:
            by_lifecycle[lc] = {"total": 0, "new": 0, "no_data": 0}
        by_lifecycle[lc]["total"] += 1
        if e.get("is_new_entry"):
            by_lifecycle[lc]["new"] += 1
        if not e["has_replay_rows"]:
            by_lifecycle[lc]["no_data"] += 1

    return {
        "generated_at": generated_at,
        "runtime_canonical_before": runtime_canonical_count,
        "artifact_candidate_count": len(artifact_candidates),
        "planned_new_registry_entries": len(new_entries),
        "planned_existing_registry_updates": len(existing_updates),
        "planned_no_data_entries": len(no_data_entries),
        "by_lottery": by_lottery,
        "by_lifecycle": by_lifecycle,
        "entries": entries,
        "skipped_entries": skipped_entries,
        "safety": {
            "db_write": False,
            "draw_import": False,
            "replay_row_generation": False,
            "prediction_update": False,
            "strategy_execution": False,
        },
    }


def write_markdown(plan: dict) -> Path:
    """Write a markdown summary of the plan."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DOCS_DIR / f"p1_catalog_visibility_plan_{DATE_SUFFIX}.md"

    entries = plan["entries"]
    skipped = plan["skipped_entries"]

    lines = [
        f"# P1 Catalog Visibility Plan ({DATE_SUFFIX})",
        "",
        f"**Generated**: {plan['generated_at']}",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Runtime canonical strategies (before) | {plan['runtime_canonical_before']} |",
        f"| Artifact candidates found | {plan['artifact_candidate_count']} |",
        f"| Planned new registry entries | {plan['planned_new_registry_entries']} |",
        f"| Planned existing registry updates (no change) | {plan['planned_existing_registry_updates']} |",
        f"| Planned NO_DATA entries | {plan['planned_no_data_entries']} |",
        f"| Skipped (bogus/unsafe) | {len(skipped)} |",
        "",
        "## Safety Constraints",
        "",
        "| Constraint | Status |",
        "|------------|--------|",
        "| DB write | DISABLED (dry-run only) |",
        "| Draw import | DISABLED |",
        "| Replay row generation | DISABLED |",
        "| Prediction update | DISABLED |",
        "| Strategy execution | DISABLED |",
        "",
        "## By Lottery Type",
        "",
        "| Lottery | Total | New | NO_DATA |",
        "|---------|-------|-----|---------|",
    ]
    for lt, stats in sorted(plan["by_lottery"].items()):
        lines.append(f"| {lt} | {stats['total']} | {stats['new']} | {stats['no_data']} |")

    lines += [
        "",
        "## By Lifecycle State",
        "",
        "| Lifecycle | Total | New | NO_DATA |",
        "|-----------|-------|-----|---------|",
    ]
    for lc, stats in sorted(plan["by_lifecycle"].items()):
        lines.append(f"| {lc} | {stats['total']} | {stats['new']} | {stats['no_data']} |")

    lines += [
        "",
        "## Entries",
        "",
        "| strategy_id | lottery_type | lifecycle | visibility | new | has_rows |",
        "|-------------|--------------|-----------|------------|-----|----------|",
    ]
    for e in sorted(entries, key=lambda x: x["strategy_id"]):
        is_new = "YES" if e.get("is_new_entry") else "no"
        has_rows = "YES" if e["has_replay_rows"] else "no"
        lines.append(
            f"| {e['strategy_id']} | {e['lottery_type']} | {e['lifecycle_state']} "
            f"| {e['catalog_visibility_state']} | {is_new} | {has_rows} |"
        )

    if skipped:
        lines += [
            "",
            "## Skipped Entries",
            "",
            "| strategy_id | reason |",
            "|-------------|--------|",
        ]
        for s in skipped:
            lines.append(f"| {s['strategy_id']} | {s['reason'][:80]} |")

    out_path.write_text("\n".join(lines))
    return out_path


def main():
    print(f"P1 Catalog Visibility Planner — {DATE_SUFFIX}")
    print(f"DB: {DB_PATH}")
    print(f"Inventory: {INVENTORY_PATH}")
    print()

    plan = build_plan()

    # Write JSON output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_out = OUTPUT_DIR / f"p1_catalog_visibility_plan_{DATE_SUFFIX}.json"
    json_out.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
    print(f"JSON plan written: {json_out}")

    # Write markdown
    md_out = write_markdown(plan)
    print(f"Markdown plan written: {md_out}")

    # Summary
    print()
    print("=== PLAN SUMMARY ===")
    print(f"Runtime canonical (before): {plan['runtime_canonical_before']}")
    print(f"Artifact candidates: {plan['artifact_candidate_count']}")
    print(f"Planned new entries: {plan['planned_new_registry_entries']}")
    print(f"Planned NO_DATA entries: {plan['planned_no_data_entries']}")
    print(f"Skipped (bogus/unsafe): {len(plan['skipped_entries'])}")
    print()
    print("Safety: ALL WRITES DISABLED (dry-run)")
    print()
    print("Classification: P1_CATALOG_VISIBILITY_PLAN_DRY_RUN_COMPLETE")


if __name__ == "__main__":
    main()
