"""
replay_catalog_source.py
========================
Read-only catalog source adapter for P3+P4.

Priority order for catalog data:
  1. Live DB `strategy_catalog` table (if it exists — requires P2 --apply)
  2. outputs/replay/p2_catalog_apply_dry_run_20260520.json
  3. outputs/replay/p1_catalog_visibility_plan_20260519.json

HARD CONSTRAINTS:
  - read-only; no DB writes, no row generation, no backfill
  - returns normalized CatalogEntry list (dataclass from P1 contract)
  - preserves all 5 visibility states as-is; never upgrades ARTIFACT_CANDIDATE to ONLINE
  - dry_run_only=True for all fallback-sourced entries
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

_P2_JSON   = REPO_ROOT / "outputs" / "replay" / "p2_catalog_apply_dry_run_20260520.json"
_P1_JSON   = REPO_ROOT / "outputs" / "replay" / "p1_catalog_visibility_plan_20260519.json"
_DB_PATH   = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"


# ---------------------------------------------------------------------------
# Normalized catalog entry (superset of P1 CatalogEntry; no DB writes)
# ---------------------------------------------------------------------------

@dataclass
class NormalizedCatalogEntry:
    strategy_id:               str
    display_name:              str
    lottery_type:              str
    lifecycle_state:           str
    catalog_visibility_state:  str
    has_replay_rows:           bool    = False
    has_historical_predictions:bool    = False
    reconstructible_reason:    Optional[str] = None
    no_data_reason:            Optional[str] = None
    artifact_source_type:      str     = "NONE"
    source_paths:              List[str] = field(default_factory=list)
    provenance_hash:           Optional[str] = None
    dry_run_only:              bool    = True
    source:                    str     = "unknown"   # "db", "p2_json", "p1_json"

    # Safety: never allow generating rows or marking ONLINE via this adapter
    def can_generate_replay_rows(self) -> bool:
        return False

    def can_mark_online(self) -> bool:
        return self.lifecycle_state == "ONLINE" and not self.dry_run_only

    def to_dict(self) -> dict:
        return {
            "strategy_id":                self.strategy_id,
            "display_name":               self.display_name,
            "lottery_type":               self.lottery_type,
            "lifecycle_state":            self.lifecycle_state,
            "catalog_visibility_state":   self.catalog_visibility_state,
            "has_replay_rows":            self.has_replay_rows,
            "has_historical_predictions": self.has_historical_predictions,
            "reconstructible_reason":     self.reconstructible_reason,
            "no_data_reason":             self.no_data_reason,
            "artifact_source_type":       self.artifact_source_type,
            "source_paths":               self.source_paths,
            "provenance_hash":            self.provenance_hash,
            "dry_run_only":               self.dry_run_only,
            "source":                     self.source,
        }


# ---------------------------------------------------------------------------
# Internal: load from each source
# ---------------------------------------------------------------------------

def _from_live_db(db_path: Path) -> Optional[List[NormalizedCatalogEntry]]:
    """Return entries from live strategy_catalog table, or None if table absent."""
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM strategy_catalog ORDER BY strategy_id"
            ).fetchall()
        except sqlite3.OperationalError:
            return None
        finally:
            conn.close()

        entries = []
        for row in rows:
            d = dict(row)
            entries.append(NormalizedCatalogEntry(
                strategy_id               = d["strategy_id"],
                display_name              = d.get("display_name") or d["strategy_id"],
                lottery_type              = d.get("lottery_type", "UNKNOWN"),
                lifecycle_state           = d.get("lifecycle_state", "UNKNOWN"),
                catalog_visibility_state  = d.get("catalog_visibility_state", "UNSUPPORTED"),
                has_replay_rows           = bool(d.get("has_replay_rows", 0)),
                has_historical_predictions= bool(d.get("has_historical_predictions", 0)),
                reconstructible_reason    = d.get("reconstructible_reason"),
                no_data_reason            = d.get("no_data_reason"),
                artifact_source_type      = d.get("artifact_source_type", "NONE"),
                source_paths              = json.loads(d["source_paths"]) if d.get("source_paths") else [],
                provenance_hash           = d.get("provenance_hash"),
                dry_run_only              = bool(d.get("dry_run_only", 0)),
                source                    = "db",
            ))
        return entries
    except Exception:
        return None


def _from_p2_json(path: Path) -> Optional[List[NormalizedCatalogEntry]]:
    """Load entries from P2 dry-run JSON. Returns None if file absent."""
    if not path.exists():
        return None
    with open(path) as f:
        data = json.load(f)
    actions = data.get("actions", [])
    if not actions:
        return None

    entries = []
    for a in actions:
        sid = a.get("strategy_id", "")
        entries.append(NormalizedCatalogEntry(
            strategy_id               = sid,
            display_name              = sid,
            lottery_type              = a.get("lottery_type", "UNKNOWN"),
            lifecycle_state           = a.get("lifecycle_state", "UNKNOWN"),
            catalog_visibility_state  = a.get("catalog_visibility_state", "UNSUPPORTED"),
            has_replay_rows           = a.get("catalog_visibility_state") == "REGISTERED_WITH_REPLAY_ROWS",
            has_historical_predictions= False,
            reconstructible_reason    = None,
            no_data_reason            = None,
            artifact_source_type      = "NONE",
            source_paths              = [],
            provenance_hash           = None,
            dry_run_only              = True,
            source                    = "p2_json",
        ))
    return entries


def _from_p1_json(path: Path) -> Optional[List[NormalizedCatalogEntry]]:
    """Load entries from P1 visibility plan JSON. Returns None if file absent."""
    if not path.exists():
        return None
    with open(path) as f:
        data = json.load(f)

    entries = []

    # P1 "entries" = runtime-registered strategies (18)
    for e in data.get("entries", []):
        entries.append(NormalizedCatalogEntry(
            strategy_id               = e["strategy_id"],
            display_name              = e.get("display_name", e["strategy_id"]),
            lottery_type              = e.get("lottery_type", "UNKNOWN"),
            lifecycle_state           = e.get("lifecycle_state", "UNKNOWN"),
            catalog_visibility_state  = e.get("catalog_visibility_state", "UNSUPPORTED"),
            has_replay_rows           = bool(e.get("has_replay_rows", False)),
            has_historical_predictions= bool(e.get("has_historical_predictions", False)),
            reconstructible_reason    = e.get("reconstructible_reason"),
            no_data_reason            = e.get("no_data_reason"),
            artifact_source_type      = e.get("artifact_source_type", "NONE"),
            source_paths              = e.get("source_paths", []),
            provenance_hash           = e.get("provenance_hash"),
            dry_run_only              = True,
            source                    = "p1_json",
        ))

    # P1 "artifact_candidates_extra" = NOT_REGISTERED (41)
    for e in data.get("artifact_candidates_extra", []):
        entries.append(NormalizedCatalogEntry(
            strategy_id               = e["strategy_id"],
            display_name              = e.get("display_name", e["strategy_id"]),
            lottery_type              = e.get("lottery_type", "UNKNOWN"),
            lifecycle_state           = e.get("lifecycle_state", "NOT_REGISTERED"),
            catalog_visibility_state  = e.get("catalog_visibility_state", "ARTIFACT_CANDIDATE"),
            has_replay_rows           = False,
            has_historical_predictions= bool(e.get("has_historical_predictions", False)),
            reconstructible_reason    = e.get("reconstructible_reason"),
            no_data_reason            = e.get("no_data_reason"),
            artifact_source_type      = e.get("artifact_source_type", "NONE"),
            source_paths              = e.get("source_paths", []),
            provenance_hash           = e.get("provenance_hash"),
            dry_run_only              = True,
            source                    = "p1_json",
        ))

    return entries if entries else None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_catalog(
    db_path: Optional[Path] = None,
    p2_json: Optional[Path] = None,
    p1_json: Optional[Path] = None,
) -> List[NormalizedCatalogEntry]:
    """
    Load catalog entries from the highest-priority available source.
    Falls back from live DB → P2 JSON → P1 JSON.
    Never writes to DB; never returns empty list without raising.
    """
    _db  = db_path or _DB_PATH
    _p2  = p2_json or _P2_JSON
    _p1  = p1_json or _P1_JSON

    entries = _from_live_db(_db)
    if entries is not None:
        return entries

    entries = _from_p2_json(_p2)
    if entries is not None:
        return entries

    entries = _from_p1_json(_p1)
    if entries is not None:
        return entries

    raise RuntimeError(
        "No catalog source available. "
        f"Live DB table absent, P2 JSON not found at {_p2}, "
        f"P1 JSON not found at {_p1}."
    )


def load_catalog_with_source_info(
    db_path: Optional[Path] = None,
    p2_json: Optional[Path] = None,
    p1_json: Optional[Path] = None,
) -> dict:
    """Returns {entries: [...], source_used: str, total: int}."""
    _db  = db_path or _DB_PATH
    _p2  = p2_json or _P2_JSON
    _p1  = p1_json or _P1_JSON

    entries = _from_live_db(_db)
    source_used = "live_db"
    if entries is None:
        entries = _from_p2_json(_p2)
        source_used = "p2_json"
    if entries is None:
        entries = _from_p1_json(_p1)
        source_used = "p1_json"
    if entries is None:
        raise RuntimeError("No catalog source available.")

    return {
        "entries":     entries,
        "source_used": source_used,
        "total":       len(entries),
    }
