#!/usr/bin/env python3
"""
p1_catalog_visibility_plan.py
==============================
P1 Catalog Visibility Planner — READ-ONLY.

Reads the DB registry + artifact inventory to produce a catalog visibility
plan for all known strategies. Does NOT write to DB. Does NOT execute
strategy logic. Does NOT import draw data.

Outputs:
  outputs/replay/p1_catalog_visibility_plan_20260519.json
  docs/replay/p1_catalog_visibility_plan_20260519.md

Usage:
  python3 scripts/p1_catalog_visibility_plan.py
  python3 scripts/p1_catalog_visibility_plan.py --json-out <path> --md-out <path>
"""

import argparse
import datetime
import json
import pathlib
import sqlite3
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH   = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

# Append repo root so lottery_api is importable
sys.path.insert(0, str(REPO_ROOT))

from lottery_api.models.replay_strategy_catalog_contract import (
    ArtifactSourceType,
    CatalogEntry,
    CatalogVisibilityState,
    classify_visibility,
)
from lottery_api.models.replay_strategy_registry import (
    list_strategy_lifecycle_metadata,
)


# ---------------------------------------------------------------------------
# Artifact discovery helpers (read-only file/DB scans)
# ---------------------------------------------------------------------------

def _scan_rejected_jsons() -> dict[str, pathlib.Path]:
    """Scan rejected/ folder. Returns {strategy_id: path}."""
    rejected_dir = REPO_ROOT / "rejected"
    result: dict[str, pathlib.Path] = {}
    if not rejected_dir.exists():
        return result
    for p in rejected_dir.glob("*.json"):
        try:
            data = json.loads(p.read_text())
            sid = data.get("strategy_id") or p.stem
            result[sid] = p
        except Exception:
            result[p.stem] = p
    return result


def _get_replay_row_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Return {strategy_id: row_count} from strategy_prediction_replays."""
    rows = conn.execute(
        "SELECT strategy_id, COUNT(*) as cnt FROM strategy_prediction_replays GROUP BY strategy_id"
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def _get_prediction_run_strategy_ids(conn: sqlite3.Connection) -> set[str]:
    """Return strategy_name values found in prediction_items (proxy for historical predictions)."""
    rows = conn.execute(
        "SELECT DISTINCT strategy_name FROM prediction_items WHERE strategy_name IS NOT NULL"
    ).fetchall()
    return {r[0] for r in rows}


def _detect_artifact_source(
    strategy_id: str,
    rejected_jsons: dict[str, pathlib.Path],
    prediction_strategy_ids: set[str],
    source_paths: list[str],
) -> str:
    """Determine best artifact source type from available artifacts."""
    if strategy_id in prediction_strategy_ids:
        source_paths.append(f"DB:prediction_items[strategy_name={strategy_id!r}]")
        return ArtifactSourceType.PREDICTION_LOG

    if strategy_id in rejected_jsons:
        source_paths.append(str(rejected_jsons[strategy_id].relative_to(REPO_ROOT)))
        return ArtifactSourceType.REJECTED_JSON

    # Scan for Python code defining the strategy
    for py_file in (REPO_ROOT / "lottery_api").rglob("*.py"):
        try:
            if strategy_id in py_file.read_text():
                rel = str(py_file.relative_to(REPO_ROOT))
                if rel not in source_paths:
                    source_paths.append(rel)
                return ArtifactSourceType.CODE_SCAN
        except Exception:
            pass

    return ArtifactSourceType.NONE


# ---------------------------------------------------------------------------
# Main planner
# ---------------------------------------------------------------------------

def build_plan(db_path: pathlib.Path) -> dict:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    registry_entries = list_strategy_lifecycle_metadata()
    replay_counts    = _get_replay_row_counts(conn)
    pred_strategy_ids = _get_prediction_run_strategy_ids(conn)
    rejected_jsons   = _scan_rejected_jsons()
    conn.close()

    registered_ids = {e["strategy_id"] for e in registry_entries}

    entries: list[CatalogEntry] = []
    visibility_counts: dict[str, int] = {s: 0 for s in CatalogVisibilityState._ALL}

    for meta in registry_entries:
        sid            = meta["strategy_id"]
        lottery_types  = meta.get("supported_lottery_types", [])
        lottery_type   = lottery_types[0] if lottery_types else "UNKNOWN"
        lifecycle_state = meta["lifecycle_status"]
        row_count      = replay_counts.get(sid, 0)
        has_hist_pred  = sid in pred_strategy_ids

        source_paths: list[str] = []
        artifact_source = _detect_artifact_source(
            sid, rejected_jsons, pred_strategy_ids, source_paths
        )

        visibility_state = classify_visibility(
            lifecycle_state=lifecycle_state,
            replay_row_count=row_count,
            has_historical_predictions=has_hist_pred,
            artifact_source_type=artifact_source,
            is_registered=True,
        )

        reconstructible_reason = None
        no_data_reason = None

        if visibility_state == CatalogVisibilityState.RECONSTRUCTIBLE:
            if has_hist_pred:
                reconstructible_reason = (
                    "prediction_items rows exist for this strategy_name; "
                    "can reconstruct predictions from historical prediction runs"
                )
            elif artifact_source == ArtifactSourceType.REJECTED_JSON:
                reconstructible_reason = (
                    f"rejected/{sid}.json artifact found; "
                    "strategy config and validation results preserved"
                )
            elif artifact_source == ArtifactSourceType.CODE_SCAN:
                reconstructible_reason = (
                    "strategy found in Python source; "
                    "can re-run backtest from code to generate replay rows"
                )

        elif visibility_state == CatalogVisibilityState.REGISTERED_NO_DATA:
            no_data_reason = (
                f"Strategy {sid!r} is {lifecycle_state} in registry "
                f"but has 0 replay rows and no discoverable artifact"
            )
        elif visibility_state == CatalogVisibilityState.UNSUPPORTED:
            no_data_reason = (
                f"Strategy {sid!r} is {lifecycle_state}; "
                f"no replay rows, no artifact, no historical predictions"
            )

        entry = CatalogEntry(
            strategy_id=sid,
            display_name=meta.get("strategy_name", sid),
            lottery_type=lottery_type,
            lifecycle_state=lifecycle_state,
            catalog_visibility_state=visibility_state,
            source_paths=source_paths,
            artifact_source_type=artifact_source,
            has_replay_rows=row_count > 0,
            has_historical_predictions=has_hist_pred,
            replay_row_count=row_count,
            reconstructible_reason=reconstructible_reason,
            no_data_reason=no_data_reason,
            created_by_phase="P1",
            dry_run_only=True,
        )
        entries.append(entry)
        visibility_counts[visibility_state] += 1

    # Identify ARTIFACT_CANDIDATE strategies (in code/artifacts but not in registry)
    artifact_candidates_extra: list[dict] = []
    for sid, path in rejected_jsons.items():
        if sid not in registered_ids:
            entry_dict = {
                "strategy_id": sid,
                "display_name": sid,
                "lottery_type": "UNKNOWN",
                "lifecycle_state": "NOT_REGISTERED",
                "catalog_visibility_state": CatalogVisibilityState.ARTIFACT_CANDIDATE,
                "source_paths": [str(path.relative_to(REPO_ROOT))],
                "artifact_source_type": ArtifactSourceType.REJECTED_JSON,
                "has_replay_rows": False,
                "has_historical_predictions": False,
                "replay_row_count": 0,
                "reconstructible_reason": None,
                "no_data_reason": "Not in runtime registry; artifact exists in rejected/",
                "created_by_phase": "P1",
                "dry_run_only": True,
            }
            artifact_candidates_extra.append(entry_dict)
            visibility_counts[CatalogVisibilityState.ARTIFACT_CANDIDATE] += 1

    reconstructible_candidates = [
        e.strategy_id for e in entries
        if e.catalog_visibility_state == CatalogVisibilityState.RECONSTRUCTIBLE
    ]

    planned_actions = []
    for e in entries:
        if e.catalog_visibility_state == CatalogVisibilityState.REGISTERED_WITH_REPLAY_ROWS:
            action = "SKIP"
            reason = f"Already has {e.replay_row_count} replay rows"
        elif e.catalog_visibility_state == CatalogVisibilityState.RECONSTRUCTIBLE:
            action = "INSERT_PENDING_P5"
            reason = f"Reconstructible via {e.artifact_source_type}; deferred to P5-P7"
        elif e.catalog_visibility_state == CatalogVisibilityState.REGISTERED_NO_DATA:
            action = "SKIP"
            reason = "No artifact; no action in P1"
        else:
            action = "SKIP"
            reason = f"{e.catalog_visibility_state}"
        planned_actions.append({
            "strategy_id": e.strategy_id,
            "action": action,
            "reason": reason,
            "dry_run_only": True,
        })

    return {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "phase": "P1",
        "dry_run_only": True,
        "runtime_canonical_before": {
            "total": len(registered_ids),
            "replay_row_strategies": len([e for e in entries if e.has_replay_rows]),
            "by_lifecycle": _summarize_lifecycle(entries),
        },
        "artifact_candidate_count": len(artifact_candidates_extra),
        "by_visibility_state": visibility_counts,
        "reconstructible_candidates": reconstructible_candidates,
        "reconstructible_count": len(reconstructible_candidates),
        "entries": [e.to_dict() for e in entries],
        "artifact_candidates_extra": artifact_candidates_extra,
        "planned_actions": planned_actions,
        "notes": (
            "All entries have dry_run_only=True. "
            "can_generate_replay_rows() returns False for all entries. "
            "RECONSTRUCTIBLE strategies are P5-P7 inputs. "
            "ARTIFACT_CANDIDATE strategies are NOT in runtime registry and "
            "require governance review before any row generation."
        ),
    }


def _summarize_lifecycle(entries: list[CatalogEntry]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for e in entries:
        counts[e.lifecycle_state] = counts.get(e.lifecycle_state, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="P1 catalog visibility planner (read-only)")
    parser.add_argument("--json-out", default=None)
    parser.add_argument("--md-out",   default=None)
    args = parser.parse_args()

    default_json = REPO_ROOT / "outputs" / "replay" / "p1_catalog_visibility_plan_20260519.json"
    default_md   = REPO_ROOT / "docs"    / "replay" / "p1_catalog_visibility_plan_20260519.md"

    json_out = pathlib.Path(args.json_out) if args.json_out else default_json
    md_out   = pathlib.Path(args.md_out)   if args.md_out   else default_md

    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    plan = build_plan(DB_PATH)

    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
    print(f"JSON written: {json_out}")

    bv = plan["by_visibility_state"]
    rc = plan["runtime_canonical_before"]

    md_lines = [
        "# P1 Catalog Visibility Plan — 2026-05-19",
        "",
        f"Generated: {plan['generated_at']}  Phase: P1  dry_run_only: true",
        "",
        "## Runtime Canonical Universe (Before P1 Apply)",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Total registered strategies | **{rc['total']}** |",
        f"| Strategies with replay rows | **{rc['replay_row_strategies']}** |",
    ]
    for lc, cnt in rc["by_lifecycle"].items():
        md_lines.append(f"| {lc} | {cnt} |")

    md_lines += [
        "",
        "## Visibility State Distribution",
        "",
        "| State | Count |",
        "|-------|-------|",
    ]
    for state, cnt in bv.items():
        md_lines.append(f"| {state} | {cnt} |")

    md_lines += [
        "",
        f"## Artifact Candidates (not in registry): {plan['artifact_candidate_count']}",
        "",
        "> These strategies exist in `rejected/` or artifact scan but are NOT in the",
        "> runtime registry. They require governance review before any row generation.",
        "",
        "## RECONSTRUCTIBLE Candidates (P5-P7 inputs)",
        "",
        f"Count: **{plan['reconstructible_count']}**",
        "",
    ]
    for sid in plan["reconstructible_candidates"]:
        md_lines.append(f"- `{sid}`")

    md_lines += [
        "",
        "## Planned Actions (all dry_run_only=True)",
        "",
        "| Strategy | Action | Reason |",
        "|----------|--------|--------|",
    ]
    for pa in plan["planned_actions"]:
        md_lines.append(f"| `{pa['strategy_id']}` | {pa['action']} | {pa['reason']} |")

    md_lines += [
        "",
        "## Notes",
        "",
        plan["notes"],
        "",
        "## Safety Confirmation",
        "",
        "- ✅ No DB writes",
        "- ✅ No draw imports",
        "- ✅ No replay rows generated",
        "- ✅ No prediction execution",
        "- ✅ All entries: dry_run_only=True",
        "- ✅ can_generate_replay_rows() → False",
        "- ✅ ARTIFACT_CANDIDATE strategies: lifecycle_state=NOT_REGISTERED",
    ]

    md_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.write_text("\n".join(md_lines) + "\n")
    print(f"Markdown written: {md_out}")

    print(f"\nSummary:")
    print(f"  Runtime canonical: {rc['total']} strategies")
    print(f"  Artifact candidates (extra): {plan['artifact_candidate_count']}")
    print(f"  Visibility state breakdown: {bv}")
    print(f"  RECONSTRUCTIBLE candidates: {plan['reconstructible_count']}")


if __name__ == "__main__":
    main()
