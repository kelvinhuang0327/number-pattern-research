"""
scripts/p24_full_strategy_universe_inventory.py
================================================
P24: Full Strategy Universe Inventory — read-only, no DB writes.

Generates a comprehensive inventory of ALL strategies in the replay system,
covering every lifecycle state from ONLINE row-backed through artifact-only.

Sources consulted (in priority order):
  1. lottery_api/models/replay_strategy_registry.py  — authoritative registry (18)
  2. strategy_prediction_replays DB table            — row counts + truth stats
  3. rejected/ directory                             — rejected governance artifacts (42)
  4. outputs/replay/p0_strategy_universe_inventory_20260517.json  — reference (512)

Replay visibility state values (P24):
  ONLINE_ROW_BACKED      — ONLINE in registry AND has rows in DB
  ONLINE_NO_ROWS         — ONLINE in registry BUT no rows in DB
  OBSERVATION            — OBSERVATION lifecycle in registry
  OFFLINE                — OFFLINE lifecycle in registry
  REJECTED_REGISTERED    — REJECTED lifecycle in registry (has adapter stub)
  RETIRED                — RETIRED lifecycle in registry (adapter preserved)
  ARTIFACT_ONLY          — NOT in registry, artifact file exists in rejected/
  NO_DATA                — referenced in external source but no artifact, no registry
  MANUAL_REVIEW          — ambiguous classification, requires human review

Output:
  outputs/replay/p24_full_strategy_universe_inventory_20260521.json

HARD CONSTRAINTS:
  - No DB writes
  - No strategy execution
  - dry_run_only=True
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

REPO_ROOT   = pathlib.Path(__file__).resolve().parent.parent
DB_PATH     = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
REJECTED_DIR = REPO_ROOT / "rejected"
OUTPUT_PATH  = REPO_ROOT / "outputs" / "replay" / "p24_full_strategy_universe_inventory_20260521.json"
P0_PATH      = REPO_ROOT / "outputs" / "replay" / "p0_strategy_universe_inventory_20260517.json"

sys.path.insert(0, str(REPO_ROOT))


# ─── Lottery type inference from filename suffix ──────────────────────────────

def _infer_lottery_type(stem: str) -> str:
    s = stem.lower()
    if s.endswith("_539") or "_539_" in s or s.startswith("539"):
        return "DAILY_539"
    if s.endswith("_biglotto") or "_biglotto_" in s or "biglotto" in s:
        return "BIG_LOTTO"
    if s.endswith("_powerlotto") or "powerlotto" in s or (
            s.endswith("_power") or "_power_" in s or "power" in s):
        return "POWER_LOTTO"
    return "UNSPECIFIED"


# ─── DB helpers ───────────────────────────────────────────────────────────────

def _load_db_stats(db_path: pathlib.Path) -> Dict[str, Dict[str, Any]]:
    """Return per-strategy DB stats keyed by strategy_id."""
    con = sqlite3.connect(str(db_path))
    rows = con.execute("""
        SELECT
            strategy_id,
            lottery_type,
            COUNT(*)                                       AS row_count,
            SUM(CASE WHEN truth_level IS NOT NULL THEN 1 ELSE 0 END) AS verified_count,
            GROUP_CONCAT(DISTINCT truth_level)             AS truth_levels_seen
        FROM strategy_prediction_replays
        GROUP BY strategy_id, lottery_type
    """).fetchall()
    con.close()

    result: Dict[str, Dict[str, Any]] = {}
    for sid, lt, rc, vc, tl_concat in rows:
        tl_seen = [x for x in (tl_concat or "").split(",") if x]
        result[sid] = {
            "lottery_type_db": lt,
            "row_count": rc,
            "verified_row_count": vc,
            "truth_levels_seen": tl_seen,
        }
    return result


def _total_production_rows(db_path: pathlib.Path) -> int:
    con = sqlite3.connect(str(db_path))
    (n,) = con.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()
    con.close()
    return n


# ─── Registry helpers ─────────────────────────────────────────────────────────

def _load_registry() -> List[Dict[str, Any]]:
    """Load all strategy lifecycle metadata from replay_strategy_registry."""
    from lottery_api.models.replay_strategy_registry import list_strategy_lifecycle_metadata
    return list_strategy_lifecycle_metadata()


# ─── Rejected artifact helpers ────────────────────────────────────────────────

def _load_rejected_artifacts(rejected_dir: pathlib.Path) -> Dict[str, pathlib.Path]:
    """Return {stem: path} for all .json files in rejected/."""
    return {f.stem: f for f in sorted(rejected_dir.glob("*.json"))}


def _read_rejected_artifact(path: pathlib.Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ─── P0 reference helpers ─────────────────────────────────────────────────────

def _load_p0_reference(p0_path: pathlib.Path) -> Dict[str, Any]:
    if not p0_path.exists():
        return {}
    try:
        return json.loads(p0_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ─── Category builder ─────────────────────────────────────────────────────────

_LIFECYCLE_TO_VIS = {
    "ONLINE":      None,         # resolved by DB check
    "OFFLINE":     "OFFLINE",
    "REJECTED":    "REJECTED_REGISTERED",
    "OBSERVATION": "OBSERVATION",
    "RETIRED":     "RETIRED",
}

# reconstructible_candidate rules per visibility state:
_RECONSTRUCTIBLE = {
    "ONLINE_ROW_BACKED":   False,  # already deployed
    "ONLINE_NO_ROWS":      True,   # ONLINE but missing rows — needs investigation
    "OBSERVATION":         True,   # has adapter, under shadow eval
    "OFFLINE":             True,   # has adapter, suspended
    "REJECTED_REGISTERED": True,   # has adapter stub, could be re-evaluated
    "RETIRED":             True,   # adapter preserved, could be revived
    "ARTIFACT_ONLY":       False,  # only backtest JSON, no adapter code
    "NO_DATA":             False,
    "MANUAL_REVIEW":       False,
}

_NEEDS_MANUAL_REVIEW = {
    "ONLINE_NO_ROWS":  True,   # why are there no rows for an ONLINE strategy?
    "MANUAL_REVIEW":   True,
}


def _build_registry_entries(
    registry_meta: List[Dict[str, Any]],
    db_stats: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for m in registry_meta:
        sid  = m["strategy_id"]
        name = m.get("strategy_name", sid)
        vers = m.get("strategy_version", "v0.0")
        lc   = m["lifecycle_status"]           # ONLINE / OFFLINE / REJECTED / …
        lts  = m.get("supported_lottery_types", [])
        lt   = lts[0] if lts else "UNSPECIFIED"

        db   = db_stats.get(sid, {})
        row_count          = db.get("row_count", 0)
        verified_row_count = db.get("verified_row_count", 0)
        truth_levels_seen  = db.get("truth_levels_seen", [])

        # Determine replay_visibility_state
        if lc == "ONLINE":
            vis = "ONLINE_ROW_BACKED" if row_count > 0 else "ONLINE_NO_ROWS"
        else:
            vis = _LIFECYCLE_TO_VIS.get(lc, "MANUAL_REVIEW")

        reconstructible = _RECONSTRUCTIBLE.get(vis, False)
        manual_review   = _NEEDS_MANUAL_REVIEW.get(vis, False)

        entries.append({
            "strategy_id":           sid,
            "display_name":          name,
            "strategy_version":      vers,
            "lottery_type":          lt,
            "lifecycle_state":       lc,
            "replay_visibility_state": vis,
            "row_count":             row_count,
            "verified_row_count":    verified_row_count,
            "truth_level_summary":   {"truth_levels_seen": truth_levels_seen},
            "source_path":           "lottery_api/models/replay_strategy_registry.py",
            "source_artifact":       None,
            "reconstructible_candidate": reconstructible,
            "needs_manual_review":   manual_review,
            "unsupported_reason":    None,
            "min_history":           m.get("min_history", 0),
        })
    return entries


def _build_artifact_only_entries(
    rejected_artifacts: Dict[str, pathlib.Path],
    registry_ids: set,
) -> List[Dict[str, Any]]:
    """Build entries for rejected/ artifacts NOT already in the registry."""
    entries: List[Dict[str, Any]] = []
    for stem, path in sorted(rejected_artifacts.items()):
        # skip if this exact stem is a registry strategy_id
        if stem in registry_ids:
            continue
        artifact = _read_rejected_artifact(path)
        lt        = _infer_lottery_type(stem)
        reason    = artifact.get("reason", "")
        decision  = artifact.get("decision", "FAIL")
        date_str  = artifact.get("date", "unknown")

        entries.append({
            "strategy_id":           stem,
            "display_name":          artifact.get("strategy", stem),
            "strategy_version":      "v0.0",
            "lottery_type":          lt,
            "lifecycle_state":       "REJECTED",
            "replay_visibility_state": "ARTIFACT_ONLY",
            "row_count":             0,
            "verified_row_count":    0,
            "truth_level_summary":   {"truth_levels_seen": []},
            "source_path":           None,
            "source_artifact":       f"rejected/{path.name}",
            "reconstructible_candidate": False,
            "needs_manual_review":   False,
            "unsupported_reason":    None,
            "artifact_decision":     decision,
            "artifact_date":         date_str,
            "artifact_reject_reason": reason[:200] if reason else None,
        })
    return entries


# ─── Summary helpers ──────────────────────────────────────────────────────────

def _count_by_field(entries: List[Dict], field: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for e in entries:
        k = e.get(field, "UNKNOWN") or "UNKNOWN"
        counts[k] = counts.get(k, 0) + 1
    return dict(sorted(counts.items()))


# ─── Main ─────────────────────────────────────────────────────────────────────

def generate_inventory(dry_run: bool = True) -> Dict[str, Any]:
    print("[P24] Loading registry …")
    registry_meta = _load_registry()
    registry_ids  = {m["strategy_id"] for m in registry_meta}

    print("[P24] Querying DB …")
    db_stats = _load_db_stats(DB_PATH)
    total_rows = _total_production_rows(DB_PATH)

    print("[P24] Scanning rejected/ artifacts …")
    rejected_artifacts = _load_rejected_artifacts(REJECTED_DIR)

    print("[P24] Loading P0 reference …")
    p0 = _load_p0_reference(P0_PATH)
    p0_total = p0.get("total_count", 0)
    p0_by_lc = p0.get("by_lifecycle", {})

    # Build strategy entries
    registry_entries  = _build_registry_entries(registry_meta, db_stats)
    artifact_entries  = _build_artifact_only_entries(rejected_artifacts, registry_ids)
    all_entries       = registry_entries + artifact_entries

    by_vis = _count_by_field(all_entries, "replay_visibility_state")
    by_lc  = _count_by_field(all_entries, "lifecycle_state")
    by_lt  = _count_by_field(all_entries, "lottery_type")

    inventory = {
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "phase":          "P24",
        "dry_run_only":   dry_run,
        "production_rows_verified": total_rows,
        "summary": {
            "total_strategies_inventoried": len(all_entries),
            "registry_total":              len(registry_entries),
            "artifact_only_total":         len(artifact_entries),
            "db_row_backed_strategies":    len(db_stats),
            "db_total_rows":               total_rows,
            "p0_universe_reference_count": p0_total,
            "p0_by_lifecycle_reference":   p0_by_lc,
        },
        "by_replay_visibility_state": by_vis,
        "by_lifecycle_state":         by_lc,
        "by_lottery_type":            by_lt,
        "strategies": all_entries,
    }
    return inventory


def main() -> None:
    inventory = generate_inventory(dry_run=True)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    n = len(inventory["strategies"])
    vis = inventory["by_replay_visibility_state"]
    rows = inventory["production_rows_verified"]
    print(f"[P24] Inventoried {n} strategies → {OUTPUT_PATH.name}")
    print(f"[P24] by_visibility_state: {vis}")
    print(f"[P24] Production rows verified: {rows}")
    print("[P24] P24_FULL_STRATEGY_UNIVERSE_INVENTORY_READY")


if __name__ == "__main__":
    main()
