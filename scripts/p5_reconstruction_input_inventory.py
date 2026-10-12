"""
p5_reconstruction_input_inventory.py
=====================================
P5 read-only input inventory scanner.

Scans source evidence for all RECONSTRUCTIBLE catalog strategies.
Does NOT execute strategy logic, does NOT generate prediction numbers,
does NOT write DB.

Output classifications:
  SOURCE_AVAILABLE        — DB prediction log exists with items for known draws
  SOURCE_MISSING          — no usable historical prediction payload found
  PROVENANCE_MISSING      — source exists but cannot establish provenance chain
  UNSAFE_TO_RECONSTRUCT   — CODE_SCAN only; re-execution prohibited (P5 constraint)
  NEEDS_P6_POLICY         — source is strategy code; needs P6 promotion before any apply
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lottery_api.services.replay_catalog_source import load_catalog_with_source_info

DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P2_JSON = REPO_ROOT / "outputs" / "replay" / "p2_catalog_apply_dry_run_20260520.json"
P1_JSON = REPO_ROOT / "outputs" / "replay" / "p1_catalog_visibility_plan_20260519.json"
P4_JSON = REPO_ROOT / "outputs" / "replay" / "p4_coverage_matrix_dry_run_20260520.json"
OUT_DIR = REPO_ROOT / "outputs" / "replay"
DOC_DIR = REPO_ROOT / "docs" / "replay"


def _load_p1_metadata_overlay(p1_json: Path) -> dict[str, dict]:
    """
    Load rich artifact metadata from P1 JSON for RECONSTRUCTIBLE entries.
    P2 JSON strips artifact_source_type/source_paths; P1 has the full detail.
    Returns {strategy_id: p1_entry_dict}.
    """
    if not p1_json.exists():
        return {}
    with open(p1_json) as f:
        data = json.load(f)
    overlay: dict[str, dict] = {}
    for entry in data.get("entries", []):
        if entry.get("catalog_visibility_state") == "RECONSTRUCTIBLE":
            overlay[entry["strategy_id"]] = entry
    return overlay


def _apply_p1_overlay(entry, overlay: dict[str, dict]) -> None:
    """
    Mutate entry in-place: patch artifact_source_type and source_paths
    from P1 overlay when the loaded source (P2 JSON) has stripped them.
    Read-only relative to DB; only modifies in-memory entry object.
    """
    p1 = overlay.get(entry.strategy_id)
    if p1 is None:
        return
    if entry.artifact_source_type in ("NONE", None):
        entry.artifact_source_type = p1.get("artifact_source_type", "NONE")
    if not entry.source_paths:
        entry.source_paths = p1.get("source_paths", [])
    if not entry.reconstructible_reason:
        entry.reconstructible_reason = p1.get("reconstructible_reason")

# Evidence classes
SOURCE_AVAILABLE         = "SOURCE_AVAILABLE"
SOURCE_MISSING           = "SOURCE_MISSING"
PROVENANCE_MISSING       = "PROVENANCE_MISSING"
UNSAFE_TO_RECONSTRUCT    = "UNSAFE_TO_RECONSTRUCT"
NEEDS_P6_POLICY          = "NEEDS_P6_POLICY"


def _db_row_count(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]


def _get_prediction_log_draw_coverage(
    conn: sqlite3.Connection,
    strategy_id: str,
    lottery_type: str,
    target_draws: list[str],
) -> dict[str, dict]:
    """
    Return {draw: {run_id, item_count, has_result, predicted_numbers}} for
    draws that have historical prediction payload in prediction_items/runs.
    Checks both: direct prediction_runs and MULTI_STRATEGY sub-items.
    Read-only.
    """
    covered: dict[str, dict] = {}

    # 1. Direct runs (prediction_runs.strategy_name = strategy_id)
    rows = conn.execute(
        """
        SELECT CAST(prun.latest_known_draw AS INTEGER)+1 AS tgt,
               prun.id AS run_id,
               GROUP_CONCAT(pi.numbers, '|') AS all_numbers,
               COUNT(pi.id) AS item_count
          FROM prediction_runs prun
          JOIN prediction_items pi ON pi.run_id = prun.id
         WHERE prun.strategy_name = ?
           AND prun.lottery_type  = ?
         GROUP BY tgt, prun.id
         ORDER BY tgt
        """,
        (strategy_id, lottery_type),
    ).fetchall()
    for r in rows:
        draw = str(r[0])
        if draw in target_draws:
            # Check if result resolved
            has_result = bool(conn.execute(
                """
                SELECT 1 FROM prediction_items pi
                JOIN prediction_runs prun2 ON pi.run_id = prun2.id
                JOIN prediction_results pr ON pr.item_id = pi.id
                WHERE prun2.id = ? AND pr.actual_draw = ?
                LIMIT 1
                """,
                (r[1], draw),
            ).fetchone())
            covered[draw] = {
                "run_id":     r[1],
                "item_count": r[3],
                "has_result": has_result,
                "source":     "DIRECT_RUN",
                "numbers_sample": r[2].split("|")[0] if r[2] else None,
            }

    # 2. MULTI_STRATEGY sub-items (prediction_items.strategy_name = strategy_id)
    rows2 = conn.execute(
        """
        SELECT CAST(prun.latest_known_draw AS INTEGER)+1 AS tgt,
               prun.id AS run_id,
               GROUP_CONCAT(pi.numbers, '|') AS all_numbers,
               COUNT(pi.id) AS item_count
          FROM prediction_items pi
          JOIN prediction_runs prun ON pi.run_id = prun.id
         WHERE pi.strategy_name  = ?
           AND prun.lottery_type = ?
         GROUP BY tgt, prun.id
         ORDER BY tgt
        """,
        (strategy_id, lottery_type),
    ).fetchall()
    for r in rows2:
        draw = str(r[0])
        if draw in target_draws and draw not in covered:
            has_result = bool(conn.execute(
                """
                SELECT 1 FROM prediction_items pi2
                JOIN prediction_results pr ON pr.item_id = pi2.id
                WHERE pi2.strategy_name = ? AND pr.actual_draw = ?
                LIMIT 1
                """,
                (strategy_id, draw),
            ).fetchone())
            covered[draw] = {
                "run_id":     r[1],
                "item_count": r[3],
                "has_result": has_result,
                "source":     "MULTI_STRATEGY",
                "numbers_sample": r[2].split("|")[0] if r[2] else None,
            }

    return covered


def _check_artifact_file(path_str: str) -> dict:
    """Check if an artifact file exists and is readable. Read-only."""
    if path_str.startswith("DB:"):
        return {"exists": True, "type": "DB_TABLE", "readable": True}
    path = REPO_ROOT / path_str
    if not path.exists():
        return {"exists": False, "type": "FILE", "readable": False}
    try:
        with open(path) as f:
            content = f.read(512)
        return {"exists": True, "type": "FILE", "readable": True,
                "size_bytes": path.stat().st_size}
    except Exception as e:
        return {"exists": True, "type": "FILE", "readable": False, "error": str(e)}


def classify_evidence(
    strategy_id: str,
    artifact_source_type: str,
    source_paths: list[str],
    draw_coverage: dict[str, dict],
    target_draws: list[str],
) -> str:
    """Classify reconstruction evidence quality."""
    if artifact_source_type in ("CODE_SCAN",):
        return NEEDS_P6_POLICY

    if artifact_source_type == "PREDICTION_LOG":
        if draw_coverage:
            return SOURCE_AVAILABLE
        return SOURCE_MISSING

    if artifact_source_type == "REJECTED_JSON":
        # Check if file readable and has prediction payload
        for sp in source_paths:
            check = _check_artifact_file(sp)
            if check["exists"] and check["readable"]:
                return PROVENANCE_MISSING  # file exists but no per-draw payload
        return SOURCE_MISSING

    return SOURCE_MISSING


def run_inventory(
    target_draws: list[str] | None = None,
    db_path: Path = DB_PATH,
    p2_json: Path = P2_JSON,
    p1_json: Path = P1_JSON,
    p4_json: Path = P4_JSON,
) -> dict:
    """
    Build reconstruction input inventory. Read-only; does not write DB.
    """
    # Catalog
    catalog_info = load_catalog_with_source_info(
        db_path=db_path, p2_json=p2_json, p1_json=p1_json
    )
    entries      = catalog_info["entries"]
    source_used  = catalog_info["source_used"]

    # P2 JSON strips artifact metadata; apply P1 overlay for RECONSTRUCTIBLE entries
    p1_overlay = _load_p1_metadata_overlay(p1_json)
    for e in entries:
        if e.catalog_visibility_state == "RECONSTRUCTIBLE":
            _apply_p1_overlay(e, p1_overlay)

    recon_entries = [e for e in entries if e.catalog_visibility_state == "RECONSTRUCTIBLE"]

    # P4 matrix
    with open(p4_json) as f:
        p4 = json.load(f)

    pending_cells = [
        r for r in p4["matrix"] if r["coverage_status"] == "RECONSTRUCTIBLE_PENDING"
    ]
    if target_draws is None:
        target_draws = sorted(set(r["draw"] for r in pending_cells), key=lambda x: int(x))

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    row_count_before = _db_row_count(conn)

    strategy_inventories = []
    for entry in recon_entries:
        sid  = entry.strategy_id
        lt   = entry.lottery_type
        asrc = entry.artifact_source_type
        spaths = entry.source_paths or []

        # Artifact file checks
        artifact_checks = [_check_artifact_file(sp) for sp in spaths]

        # DB draw coverage (PREDICTION_LOG or MULTI_STRATEGY)
        draw_coverage: dict[str, dict] = {}
        if asrc in ("PREDICTION_LOG", "CODE_SCAN"):
            draw_coverage = _get_prediction_log_draw_coverage(
                conn, sid, lt, target_draws
            )

        # Draws in target range
        lt_target_draws = [d for d in target_draws
                           if any(r["draw"] == d and r["lottery_type"] == lt
                                  for r in pending_cells)]

        evidence_class = classify_evidence(
            sid, asrc, spaths, draw_coverage, lt_target_draws
        )

        covered_draws  = sorted(draw_coverage.keys(), key=lambda x: int(x))
        missing_draws  = [d for d in lt_target_draws if d not in draw_coverage]
        plannable      = len(covered_draws)
        skippable      = len(missing_draws)

        strategy_inventories.append({
            "strategy_id":         sid,
            "lottery_type":        lt,
            "lifecycle_state":     entry.lifecycle_state,
            "catalog_visibility_state": entry.catalog_visibility_state,
            "artifact_source_type":    asrc,
            "source_paths":            spaths,
            "artifact_checks":         artifact_checks,
            "evidence_class":          evidence_class,
            "target_draw_count":       len(lt_target_draws),
            "covered_draws_count":     plannable,
            "missing_draws_count":     skippable,
            "covered_draws":           covered_draws[:5],  # sample
            "missing_draws":           missing_draws[:5],  # sample
            "draw_coverage_detail":    {
                k: v for k, v in list(draw_coverage.items())[:3]  # sample
            },
            "dry_run_only": True,
        })

    row_count_after = _db_row_count(conn)
    conn.close()

    assert row_count_before == row_count_after, "DB modified during inventory!"

    # Summary
    by_class = {}
    for inv in strategy_inventories:
        c = inv["evidence_class"]
        by_class.setdefault(c, []).append(inv["strategy_id"])

    total_plannable = sum(i["covered_draws_count"] for i in strategy_inventories)
    total_skippable = sum(i["missing_draws_count"]  for i in strategy_inventories)

    return {
        "generated_at":           datetime.utcnow().isoformat() + "Z",
        "phase":                  "P5",
        "mode":                   "DRY_RUN",
        "dry_run":                True,
        "catalog_source":         source_used,
        "reconstructible_count":  len(recon_entries),
        "target_draws_total":     len(pending_cells),
        "target_draw_range":      f"{target_draws[0]}-{target_draws[-1]}" if target_draws else "",
        "by_evidence_class":      {k: v for k, v in by_class.items()},
        "total_plannable_cells":  total_plannable,
        "total_skippable_cells":  total_skippable,
        "db_row_count_before":    row_count_before,
        "db_row_count_after":     row_count_after,
        "strategies":             strategy_inventories,
    }


def write_outputs(result: dict, json_out: Path, md_out: Path | None) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    with open(json_out, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"JSON written to: {json_out}")

    if md_out:
        md_out.parent.mkdir(parents=True, exist_ok=True)
        _write_md(result, md_out)
        print(f"MD written to: {md_out}")


def _write_md(r: dict, path: Path) -> None:
    lines = [
        "# P5 Reconstruction Input Inventory",
        "",
        f"Generated: {r['generated_at']}",
        f"Catalog source: `{r['catalog_source']}`  ",
        f"RECONSTRUCTIBLE strategies: {r['reconstructible_count']}  ",
        f"Target draw range: `{r['target_draw_range']}`  ",
        f"Target cells total: {r['target_draws_total']}  ",
        f"Plannable cells: {r['total_plannable_cells']}  ",
        f"Skippable cells: {r['total_skippable_cells']}  ",
        "",
        "## Evidence Class Summary",
        "",
        "| Class | Strategies |",
        "|-------|-----------|",
    ]
    for cls, strats in r["by_evidence_class"].items():
        lines.append(f"| `{cls}` | {', '.join(strats)} |")

    lines += [
        "",
        "## Per-Strategy Detail",
        "",
        "| Strategy | LT | Lifecycle | Evidence | Target | Plannable | Skippable |",
        "|---|---|---|---|---|---|---|",
    ]
    for inv in r["strategies"]:
        lines.append(
            f"| {inv['strategy_id']} | {inv['lottery_type']} | {inv['lifecycle_state']} "
            f"| `{inv['evidence_class']}` | {inv['target_draw_count']} "
            f"| {inv['covered_draws_count']} | {inv['missing_draws_count']} |"
        )

    lines += [
        "",
        "## Safety",
        f"- DB rows before: {r['db_row_count_before']}",
        f"- DB rows after:  {r['db_row_count_after']}",
        f"- Rows unchanged: {r['db_row_count_before'] == r['db_row_count_after']}",
        "- **No rows inserted in this inventory run.**",
    ]
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="P5 Reconstruction Input Inventory (read-only)")
    parser.add_argument("--json-out", default=str(OUT_DIR / "p5_reconstruction_input_inventory_20260520.json"))
    parser.add_argument("--md-out",   default=str(DOC_DIR / "p5_reconstruction_input_inventory_20260520.md"))
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    print("P5 Reconstruction Input Inventory — scanning source evidence...")
    result = run_inventory()

    print(f"  RECONSTRUCTIBLE strategies: {result['reconstructible_count']}")
    print(f"  Target cells: {result['target_draws_total']}")
    print(f"  Plannable cells: {result['total_plannable_cells']}")
    print(f"  Skippable cells: {result['total_skippable_cells']}")
    print(f"  By evidence class: {list(result['by_evidence_class'].keys())}")

    if not args.no_write:
        write_outputs(result, Path(args.json_out), Path(args.md_out) if args.md_out else None)

    if result["db_row_count_before"] != result["db_row_count_after"]:
        print("CRITICAL: DB row count changed!", file=sys.stderr)
        sys.exit(1)
    print("Final classification: P5_RECONSTRUCTION_INPUT_INVENTORY_PASS")


if __name__ == "__main__":
    main()
