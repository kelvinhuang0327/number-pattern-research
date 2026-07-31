#!/usr/bin/env python3
"""
audit_p262a_replay_strategy_coverage.py
=======================================
P262A — Replay Strategy Coverage Audit (READ-ONLY).

Goal:
  Confirm whether the "歷史回放總覽" (History Replay Overview, P259A endpoint
  GET /api/replay/history-overview) covers all known strategies, and which
  strategies already have per-draw production replay rows vs which are missing.

This is an INVENTORY + REPORT task only. It:
  - DOES NOT write to the DB.
  - DOES NOT backfill / generate replay rows.
  - DOES NOT modify any strategy adapter or registry.
  - DOES NOT change production data.
  - Only emits a json + md report under outputs/research/ (repo artifact convention).

Coverage matrix is keyed at (strategy_id × lottery_type) granularity — the natural
key of both the replay table and the overview endpoint rows.

Universe of cells = UNION of:
  (A) registry cells   — every registered strategy × each supported_lottery_type
                         (lottery_api.models.replay_strategy_registry)
  (B) DB cells         — every distinct (lottery_type, strategy_id) that has
                         ≥1 row in strategy_prediction_replays

Overview-membership rule (replicated EXACTLY from
lottery_api/routes/replay.py::get_history_replay_overview):
  A (strategy_id × lottery_type) row is producible by the overview endpoint iff
    1. strategy_id is registered (appears in list_strategy_lifecycle_metadata), AND
    2. lottery_type is in that strategy's registry supported_lottery_types, AND
    3. derived_bet_count(strategy_id) == bet_index filter (bet_index=0 means "any").
  The endpoint DEFAULTS to bet_index=1, so the default view only shows
  derived_bet_count==1 strategies.

Run:
  python3 tools/audit_p262a_replay_strategy_coverage.py            # write reports
  python3 tools/audit_p262a_replay_strategy_coverage.py --print    # stdout only
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lottery_api.models.replay_strategy_registry import (  # noqa: E402
    list_strategy_lifecycle_metadata,
    list_executable_strategy_ids,
)
from lottery_api.models.replay_strategy_catalog_contract import (  # noqa: E402
    classify_visibility,
    CatalogVisibilityState,
    ArtifactSourceType,
)

DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
REJECTED_DIR = PROJECT_ROOT / "rejected"
RESEARCH_DIR = PROJECT_ROOT / "outputs" / "research"
TASK_ID = "P262A"
TASK_SLUG = "replay_strategy_coverage_audit"

# ── SSOT mirror: identical to lottery_api/routes/replay.py::_derive_bet_count ──


def derive_bet_count(strategy_id: str) -> int:
    """Derive declared bet count from strategy_id naming convention.

    MIRRORS lottery_api/routes/replay.py::_derive_bet_count exactly.
    Extracts the numeric suffix before 'bet' (e.g. '_3bet' -> 3).
    Falls back to the triple_strike special case, then defaults to 1.
    """
    m = re.search(r"[_-](\d+)bet", strategy_id)
    if m:
        return int(m.group(1))
    if "triple_strike" in strategy_id:
        return 3
    return 1


# ── DB access (READ-ONLY: SELECT statements only, no writes) ──────────────────


def _open_ro_conn(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Open a read-only connection. Falls back to a normal (unused-for-writes)
    connection if the ro URI fails (e.g. WAL flakiness against a live backend)."""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def collect_db_coverage(db_path: Path = DB_PATH) -> Dict[Tuple[str, str], dict]:
    """Aggregate replay coverage per (lottery_type, strategy_id). READ-ONLY."""
    conn = _open_ro_conn(db_path)
    try:
        rows = conn.execute(
            """
            SELECT
                lottery_type,
                strategy_id,
                COUNT(*)                          AS replay_row_count,
                COUNT(DISTINCT target_draw)       AS distinct_draw_count,
                MAX(bet_index)                    AS max_bet_index,
                MIN(bet_index)                    AS min_bet_index,
                COUNT(DISTINCT bet_index)         AS distinct_bet_indices,
                MIN(CAST(target_draw AS INTEGER)) AS min_draw_int,
                MAX(CAST(target_draw AS INTEGER)) AS max_draw_int,
                SUM(CASE WHEN replay_status='PREDICTED' THEN 1 ELSE 0 END) AS predicted_cnt
            FROM strategy_prediction_replays
            GROUP BY lottery_type, strategy_id
            """
        ).fetchall()
    finally:
        conn.close()

    out: Dict[Tuple[str, str], dict] = {}
    for r in rows:
        out[(r["lottery_type"], r["strategy_id"])] = {
            "replay_row_count": r["replay_row_count"],
            "distinct_draw_count": r["distinct_draw_count"],
            "max_bet_index": r["max_bet_index"],
            "min_bet_index": r["min_bet_index"],
            "distinct_bet_indices": r["distinct_bet_indices"],
            "min_target_draw": str(r["min_draw_int"]) if r["min_draw_int"] else None,
            "max_target_draw": str(r["max_draw_int"]) if r["max_draw_int"] else None,
            "predicted_cnt": r["predicted_cnt"] or 0,
        }
    return out


def collect_rejected_artifacts(rejected_dir: Path = REJECTED_DIR) -> List[str]:
    """List rejected/ archive artifact stems (read-only scan)."""
    if not rejected_dir.is_dir():
        return []
    return sorted(
        p.stem
        for p in rejected_dir.glob("*.json")
        if p.name.lower() != "readme.json"
    )


def _norm_tokens(name: str) -> frozenset:
    """Normalise a strategy_id / filename into a token set for fuzzy linkage.

    rejected/ filenames reorder tokens vs strategy_ids (e.g. strategy
    'biglotto_ts3_acb_4bet' ↔ file 'ts3_acb_4bet_biglotto'), so we compare
    token SETS (order-insensitive, strict equality — no subset matching).
    """
    return frozenset(t for t in re.split(r"[_\-]+", name.lower()) if t)


def build_rejected_index(rejected_ids: List[str]) -> Dict[frozenset, str]:
    """Map token-set -> rejected artifact filename (last wins on rare collision)."""
    return {_norm_tokens(stem): stem for stem in rejected_ids}


def match_rejected_artifact(
    strategy_id: str, rejected_index: Dict[frozenset, str]
) -> Optional[str]:
    """Return the rejected/ filename matching strategy_id by token set, else None."""
    return rejected_index.get(_norm_tokens(strategy_id))


# ── Matrix construction ───────────────────────────────────────────────────────


def build_audit(
    db_path: Path = DB_PATH,
    rejected_dir: Path = REJECTED_DIR,
) -> dict:
    """Build the full coverage audit payload. Pure read; no side effects."""
    registry = list_strategy_lifecycle_metadata()
    exec_ids = set(list_executable_strategy_ids())
    db_cov = collect_db_coverage(db_path)
    rejected_ids = collect_rejected_artifacts(rejected_dir)
    rejected_index = build_rejected_index(rejected_ids)

    # Registry index: strategy_id -> meta
    reg_index = {m["strategy_id"]: m for m in registry}

    # Registry-supported (strategy_id, lottery_type) cells
    reg_cells = {
        (m["strategy_id"], lt)
        for m in registry
        for lt in m["supported_lottery_types"]
    }
    # DB cells — db_cov keys are (lottery_type, strategy_id); normalise to
    # (strategy_id, lottery_type) so the union matches reg_cells ordering.
    db_cells = {(sid, lt) for (lt, sid) in db_cov.keys()}

    all_cells = sorted(reg_cells | db_cells)

    matrix: List[dict] = []
    for sid, lt in all_cells:
        meta = reg_index.get(sid)
        registered = meta is not None
        supported_by_registry_for_lt = (sid, lt) in reg_cells
        derived_bets = derive_bet_count(sid)
        db = db_cov.get((lt, sid))
        has_rows = db is not None and db["replay_row_count"] > 0
        replay_row_count = db["replay_row_count"] if db else 0
        distinct_draw_count = db["distinct_draw_count"] if db else 0
        max_bet_index = db["max_bet_index"] if db else 0

        lifecycle = meta["lifecycle_status"] if meta else "UNREGISTERED"
        strategy_name = (
            meta["strategy_name"] if meta
            else (db_name_for(sid, lt, db_path) or sid)
        )
        is_exec = sid in exec_ids
        matched_artifact = match_rejected_artifact(sid, rejected_index)
        has_artifact = matched_artifact is not None

        # Overview membership (replicates route logic)
        appears_in_overview_any = registered and supported_by_registry_for_lt
        appears_in_default_view = appears_in_overview_any and derived_bets == 1

        # can_open_detail: the P259B detail endpoint scopes purely by
        # (lottery_type, strategy_id) and returns rows whenever they exist —
        # it does NOT gate on registry membership. So API-level openability ==
        # has_rows. But a user can only *reach* the detail page from an overview
        # row, so we also track the product-level reachability.
        can_open_detail_api = has_rows
        can_open_detail_from_ui = appears_in_overview_any and has_rows

        # catalog_visibility_state via the canonical contract classifier
        artifact_source = (
            ArtifactSourceType.REJECTED_JSON if has_artifact else ArtifactSourceType.NONE
        )
        visibility_state = classify_visibility(
            lifecycle_state=lifecycle if registered else "REJECTED",
            replay_row_count=replay_row_count,
            has_historical_predictions=False,
            artifact_source_type=artifact_source,
            is_registered=registered,
        )

        missing_reason = _missing_reason(
            registered=registered,
            supported_by_registry_for_lt=supported_by_registry_for_lt,
            has_rows=has_rows,
            appears_in_default_view=appears_in_default_view,
            derived_bets=derived_bets,
            max_bet_index=max_bet_index,
            lifecycle=lifecycle,
            has_artifact=has_artifact,
        )

        # bet_index coverage check: name implies N bets but stored max_bet_index < N
        partial_bet_index = has_rows and (max_bet_index < derived_bets)

        matrix.append({
            "strategy_id": sid,
            "strategy_name": strategy_name,
            "lifecycle": lifecycle,
            "lottery_type": lt,
            "registered": registered,
            "is_executable": is_exec,
            "supported_by_registry_for_lottery_type": supported_by_registry_for_lt,
            "derived_bet_count": derived_bets,
            "appears_in_overview": "YES" if appears_in_overview_any else "NO",
            "appears_in_default_bet1_view": "YES" if appears_in_default_view else "NO",
            "has_replay_rows": "YES" if has_rows else "NO",
            "replay_row_count": replay_row_count,
            "distinct_draw_count": distinct_draw_count,
            "max_bet_index": max_bet_index,
            "partial_bet_index_coverage": partial_bet_index,
            "can_open_detail": "YES" if can_open_detail_api else "NO",
            "can_open_detail_from_ui": "YES" if can_open_detail_from_ui else "NO",
            "has_rejected_artifact": has_artifact,
            "rejected_artifact_file": matched_artifact,
            "catalog_visibility_state": visibility_state,
            "missing_reason": missing_reason,
        })

    summary = _summarize(matrix, registry, db_cov, rejected_ids)
    issues = _detect_issues(matrix, registry, db_cov)

    return {
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "title": "Replay Strategy Coverage Audit — All Strategies vs Replay Rows",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "no_db_write": True,
        "no_replay_backfill": True,
        "no_adapter_change": True,
        "no_migration": True,
        "db_path": str(DB_PATH.relative_to(PROJECT_ROOT)),
        "overview_endpoint": "GET /api/replay/history-overview",
        "overview_default_bet_index": 1,
        "methodology": {
            "cell_key": "(strategy_id x lottery_type)",
            "cell_universe": "UNION(registry supported cells, DB distinct cells)",
            "overview_membership_rule": (
                "registered AND lottery_type in registry supported_lottery_types "
                "AND derived_bet_count == bet_index (bet_index=0 => any)"
            ),
            "bet_count_source": "derive_bet_count() mirrors routes/replay.py::_derive_bet_count",
        },
        "summary": summary,
        "issues": issues,
        "coverage_matrix": matrix,
        "rejected_artifact_strategy_ids": rejected_ids,
    }


def db_name_for(sid: str, lt: str, db_path: Path) -> Optional[str]:
    """Best-effort strategy_name lookup from DB for unregistered (orphan) ids."""
    conn = _open_ro_conn(db_path)
    try:
        r = conn.execute(
            "SELECT strategy_name FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND lottery_type=? AND strategy_name IS NOT NULL "
            "LIMIT 1",
            (sid, lt),
        ).fetchone()
        return r["strategy_name"] if r else None
    finally:
        conn.close()


def _missing_reason(
    *,
    registered: bool,
    supported_by_registry_for_lt: bool,
    has_rows: bool,
    appears_in_default_view: bool,
    derived_bets: int,
    max_bet_index: int,
    lifecycle: str,
    has_artifact: bool,
) -> str:
    """Human-readable explanation of why a cell is (not) fully covered."""
    reasons = []
    if not registered:
        reasons.append(
            "ORPHAN: has replay rows but NOT registered -> never iterated by "
            "overview endpoint (overview only walks the registry)"
        )
    elif not supported_by_registry_for_lt:
        reasons.append(
            f"REGISTRY_LOTTERY_MISMATCH: replay rows exist for {lifecycle} strategy "
            "under a lottery_type the registry does not list -> cell never produced "
            "by overview"
        )
    if registered and supported_by_registry_for_lt and not has_rows:
        if has_artifact:
            reasons.append(
                f"ARTIFACT_ONLY: registered ({lifecycle}) with rejected/ artifact "
                "but zero production replay rows"
            )
        else:
            reasons.append(
                f"REGISTERED_NO_DATA: registered ({lifecycle}) but zero production "
                "replay rows and no rejected/ artifact"
            )
    if registered and supported_by_registry_for_lt and has_rows and not appears_in_default_view:
        reasons.append(
            f"HIDDEN_IN_DEFAULT_VIEW: derived_bet_count={derived_bets} so the row is "
            "only visible when the overview bet_index filter == "
            f"{derived_bets} (default bet_index=1 hides it)"
        )
    if has_rows and max_bet_index < derived_bets:
        reasons.append(
            f"PARTIAL_BET_INDEX: name implies {derived_bets} bets but stored "
            f"max_bet_index={max_bet_index}"
        )
    if not reasons:
        return "OK: covered (registered, lottery matched, rows present, in default view)"
    return " | ".join(reasons)


def _summarize(matrix, registry, db_cov, rejected_ids) -> dict:
    reg_ids = {m["strategy_id"] for m in registry}
    db_ids = {sid for (_lt, sid) in db_cov.keys()}
    overview_ids = {
        row["strategy_id"] for row in matrix if row["appears_in_overview"] == "YES"
    }
    default_view_ids = {
        row["strategy_id"]
        for row in matrix
        if row["appears_in_default_bet1_view"] == "YES"
    }
    with_rows_ids = {
        row["strategy_id"] for row in matrix if row["has_replay_rows"] == "YES"
    }
    all_known_ids = reg_ids | db_ids
    no_rows_registered = sorted(reg_ids - db_ids)
    orphan_ids = sorted(db_ids - reg_ids)

    return {
        "total_known_strategies": len(all_known_ids),
        "total_registered_strategies": len(reg_ids),
        "total_db_strategies_with_rows": len(db_ids),
        "strategies_in_overview_any_bet_index": len(overview_ids),
        "strategies_in_overview_default_bet1_view": len(default_view_ids),
        "strategies_with_replay_rows": len(with_rows_ids),
        "strategies_without_replay_rows": len(all_known_ids - with_rows_ids),
        "registered_without_replay_rows": no_rows_registered,
        "orphan_strategies_rows_but_unregistered": orphan_ids,
        "total_cells": len(matrix),
        "cells_appears_in_overview": sum(
            1 for r in matrix if r["appears_in_overview"] == "YES"
        ),
        "cells_in_default_bet1_view": sum(
            1 for r in matrix if r["appears_in_default_bet1_view"] == "YES"
        ),
        "cells_has_rows": sum(1 for r in matrix if r["has_replay_rows"] == "YES"),
        "cells_can_open_detail": sum(1 for r in matrix if r["can_open_detail"] == "YES"),
        "lifecycle_counts": _lifecycle_counts(registry),
        "rejected_artifact_count": len(rejected_ids),
    }


def _lifecycle_counts(registry) -> dict:
    counts: dict = {}
    for m in registry:
        counts[m["lifecycle_status"]] = counts.get(m["lifecycle_status"], 0) + 1
    return counts


def _detect_issues(matrix, registry, db_cov) -> List[dict]:
    """Flag concrete coverage issues for the report."""
    issues: List[dict] = []

    orphans = sorted({
        (r["lottery_type"], r["strategy_id"])
        for r in matrix if not r["registered"]
    })
    if orphans:
        issues.append({
            "type": "ORPHAN_REPLAY_ROWS",
            "severity": "HIGH",
            "description": (
                "Strategies with production replay rows that are NOT in the "
                "registry — the overview endpoint walks the registry only, so "
                "these never appear in the overview and have no UI path to detail."
            ),
            "cells": [f"{lt}:{sid}" for (lt, sid) in orphans],
        })

    lottery_mismatch = sorted({
        (r["lottery_type"], r["strategy_id"])
        for r in matrix
        if r["registered"]
        and not r["supported_by_registry_for_lottery_type"]
        and r["has_replay_rows"] == "YES"
    })
    if lottery_mismatch:
        issues.append({
            "type": "REGISTRY_LOTTERY_TYPE_MISMATCH",
            "severity": "HIGH",
            "description": (
                "Replay rows exist for a (strategy, lottery_type) pair where the "
                "registry does NOT list that lottery_type for the strategy. The "
                "overview iterates registry supported_lottery_types, so these "
                "rows are never surfaced."
            ),
            "cells": [f"{lt}:{sid}" for (lt, sid) in lottery_mismatch],
        })

    hidden_default = sorted({
        (r["lottery_type"], r["strategy_id"], r["derived_bet_count"])
        for r in matrix
        if r["appears_in_overview"] == "YES"
        and r["appears_in_default_bet1_view"] == "NO"
        and r["has_replay_rows"] == "YES"
    })
    if hidden_default:
        issues.append({
            "type": "HIDDEN_IN_DEFAULT_BET1_VIEW",
            "severity": "MEDIUM",
            "description": (
                "Multi-bet strategies with replay rows are hidden from the "
                "default overview view because the endpoint defaults to "
                "bet_index=1; they only appear when the caller sets bet_index to "
                "the strategy's derived bet count (or bet_index=0)."
            ),
            "cells": [f"{lt}:{sid}(derived_bet={b})" for (lt, sid, b) in hidden_default],
        })

    artifact_only = sorted({
        r["strategy_id"]
        for r in matrix
        if r["has_replay_rows"] == "NO" and r["has_rejected_artifact"]
    })
    if artifact_only:
        issues.append({
            "type": "ARTIFACT_ONLY_NO_REPLAY_ROWS",
            "severity": "LOW",
            "description": (
                "Strategies registered with a rejected/ archive artifact but no "
                "production replay rows. Expected for rejected strategies; listed "
                "for completeness (do NOT backfill in P262A)."
            ),
            "strategy_ids": artifact_only,
        })

    partial_bet = sorted({
        (r["lottery_type"], r["strategy_id"], r["derived_bet_count"], r["max_bet_index"])
        for r in matrix
        if r["partial_bet_index_coverage"]
    })
    if partial_bet:
        issues.append({
            "type": "PARTIAL_BET_INDEX_COVERAGE",
            "severity": "MEDIUM",
            "description": (
                "strategy_id naming implies N bets but the replay table only "
                "stores up to max_bet_index < N for that (strategy, lottery)."
            ),
            "cells": [
                f"{lt}:{sid}(name={b}bet,max_bet_index={mb})"
                for (lt, sid, b, mb) in partial_bet
            ],
        })

    no_rows_registered = sorted(
        {m["strategy_id"] for m in registry}
        - {sid for (_lt, sid) in db_cov.keys()}
    )
    if no_rows_registered:
        issues.append({
            "type": "REGISTERED_WITHOUT_REPLAY_ROWS",
            "severity": "INFO",
            "description": (
                "Registered strategies with zero replay rows in any lottery_type. "
                "Most are REJECTED/OBSERVATION stubs with no production data."
            ),
            "strategy_ids": no_rows_registered,
        })

    return issues


# ── Report rendering ──────────────────────────────────────────────────────────


def render_markdown(audit: dict) -> str:
    s = audit["summary"]
    lines: List[str] = []
    lines.append(f"# {audit['task_id']} — {audit['title']}")
    lines.append("")
    lines.append(f"- Generated: `{audit['generated_at']}`")
    lines.append(f"- DB: `{audit['db_path']}`  (READ-ONLY, no writes)")
    lines.append(f"- Overview endpoint: `{audit['overview_endpoint']}` "
                 f"(default bet_index={audit['overview_default_bet_index']})")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total known strategies (registry ∪ DB): **{s['total_known_strategies']}**")
    lines.append(f"- Registered strategies: **{s['total_registered_strategies']}** "
                 f"({s['lifecycle_counts']})")
    lines.append(f"- Strategies with replay rows: **{s['strategies_with_replay_rows']}**")
    lines.append(f"- Strategies WITHOUT replay rows: **{s['strategies_without_replay_rows']}**")
    lines.append(f"- Strategies reachable in overview (any bet_index): "
                 f"**{s['strategies_in_overview_any_bet_index']}**")
    lines.append(f"- Strategies visible in DEFAULT (bet_index=1) overview view: "
                 f"**{s['strategies_in_overview_default_bet1_view']}**")
    lines.append(f"- Rejected-archive artifacts: **{s['rejected_artifact_count']}**")
    lines.append(f"- Coverage cells (strategy×lottery): **{s['total_cells']}** "
                 f"(in_overview={s['cells_appears_in_overview']}, "
                 f"default_view={s['cells_in_default_bet1_view']}, "
                 f"has_rows={s['cells_has_rows']}, "
                 f"can_open_detail={s['cells_can_open_detail']})")
    lines.append("")
    lines.append("### Orphan strategies (replay rows but UNREGISTERED → never in overview)")
    lines.append("")
    if s["orphan_strategies_rows_but_unregistered"]:
        for sid in s["orphan_strategies_rows_but_unregistered"]:
            lines.append(f"- `{sid}`")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("### Registered strategies WITHOUT replay rows")
    lines.append("")
    if s["registered_without_replay_rows"]:
        for sid in s["registered_without_replay_rows"]:
            lines.append(f"- `{sid}`")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("## Issues")
    lines.append("")
    for iss in audit["issues"]:
        lines.append(f"### [{iss['severity']}] {iss['type']}")
        lines.append("")
        lines.append(iss["description"])
        lines.append("")
        items = iss.get("cells") or iss.get("strategy_ids") or []
        for it in items:
            lines.append(f"- `{it}`")
        lines.append("")
    lines.append("## Coverage Matrix")
    lines.append("")
    header = (
        "| strategy_id | name | lifecycle | lottery | in_overview | "
        "default_view | has_rows | rows | draws | max_bet | can_detail | "
        "visibility | missing_reason |"
    )
    lines.append(header)
    lines.append("|" + "---|" * 14)
    for r in audit["coverage_matrix"]:
        lines.append(
            f"| {r['strategy_id']} | {r['strategy_name']} | {r['lifecycle']} | "
            f"{r['lottery_type']} | {r['appears_in_overview']} | "
            f"{r['appears_in_default_bet1_view']} | {r['has_replay_rows']} | "
            f"{r['replay_row_count']} | {r['distinct_draw_count']} | "
            f"{r['max_bet_index']} | {r['can_open_detail']} | "
            f"{r['catalog_visibility_state']} | {r['missing_reason']} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_reports(audit: dict, research_dir: Path = RESEARCH_DIR) -> Tuple[Path, Path]:
    research_dir.mkdir(parents=True, exist_ok=True)
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    stem = f"{TASK_ID.lower()}_{TASK_SLUG}_{date}"
    json_path = research_dir / f"{stem}.json"
    md_path = research_dir / f"{stem}.md"
    json_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(audit), encoding="utf-8")
    return json_path, md_path


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="P262A Replay Strategy Coverage Audit (read-only)")
    ap.add_argument("--print", dest="print_only", action="store_true",
                    help="print summary to stdout only; do not write report files")
    args = ap.parse_args(argv)

    audit = build_audit()
    s = audit["summary"]

    print(f"[{TASK_ID}] Replay Strategy Coverage Audit (READ-ONLY)")
    print(f"  total known strategies          : {s['total_known_strategies']}")
    print(f"  registered                      : {s['total_registered_strategies']} "
          f"{s['lifecycle_counts']}")
    print(f"  with replay rows                : {s['strategies_with_replay_rows']}")
    print(f"  without replay rows             : {s['strategies_without_replay_rows']}")
    print(f"  in overview (any bet_index)     : {s['strategies_in_overview_any_bet_index']}")
    print(f"  in default bet_index=1 view     : {s['strategies_in_overview_default_bet1_view']}")
    print(f"  orphans (rows, unregistered)    : "
          f"{s['orphan_strategies_rows_but_unregistered']}")
    print(f"  registered w/o rows             : {s['registered_without_replay_rows']}")
    print(f"  issues                          : {[i['type'] for i in audit['issues']]}")

    if not args.print_only:
        json_path, md_path = write_reports(audit)
        print(f"  wrote: {json_path.relative_to(PROJECT_ROOT)}")
        print(f"  wrote: {md_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
