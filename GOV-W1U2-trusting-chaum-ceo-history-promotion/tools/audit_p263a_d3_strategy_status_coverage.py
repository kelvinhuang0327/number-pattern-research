#!/usr/bin/env python3
"""P263A — D3 Strategy Status / Contract Audit Coverage Audit (READ-ONLY).

Audits whether the D3 Strategy Status / Contract Audit page
(`GET /api/replay/d3-strategy-status-audit`, artifact-backed by
`outputs/research/p258n_d3_strategy_status_audit_payload_20260609.json`) covers
the post-P262B known-strategy universe, and which lifecycle / status / success-rate
fields it does and does not expose.

The audit reconciles three sources, all READ-ONLY:
  1. Strategy registry  — lottery_api/models/replay_strategy_registry.py
  2. Replay DB cells    — strategy_prediction_replays (SELECT only)
  3. D3 page payload    — the P258N artifact the D3 route serves

It does NOT:
  - write the DB, backfill replay rows, or open it read-write
  - mutate the registry or any adapter
  - modify the D3 UI / API
  - self-define an undefined success-rate contract

Re-run:  python3 tools/audit_p263a_d3_strategy_status_coverage.py
         (writes the JSON + MD artifacts under outputs/research/)
Import:  from tools.audit_p263a_d3_strategy_status_coverage import build_audit
         (pure function; returns the audit dict, writes nothing)
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
D3_ARTIFACT = (
    REPO_ROOT / "outputs" / "research"
    / "p258n_d3_strategy_status_audit_payload_20260609.json"
)
OUT_JSON = (
    REPO_ROOT / "outputs" / "research"
    / "p263a_d3_strategy_status_coverage_audit_20260609.json"
)
OUT_MD = (
    REPO_ROOT / "outputs" / "research"
    / "p263a_d3_strategy_status_coverage_audit_20260609.md"
)

# Fields the audit task asks D3 to expose, with the key(s) that would satisfy each.
REQUESTED_FIELD_KEYS = {
    "strategy_id": ("strategy_id",),
    "strategy_name": ("strategy_name",),
    "lottery_type": ("lottery_type",),
    "lifecycle": ("lifecycle_status", "lifecycle"),
    "registry_status": ("registry_status",),
    "contract_status": ("d3_contract_status", "contract_status"),
    "replay_row_count": ("replay_row_count",),
    "distinct_draw_count": ("distinct_draw_count",),
    "can_open_detail": ("can_open_detail",),
    "missing_reason": ("missing_reason",),
    "status_reason": ("status_reason",),
    "status_updated_at": ("status_updated_at", "lifecycle_updated_at"),
    "status_source": ("status_source",),
    "reject_reason": ("reject_reason",),
    "reject_updated_at": ("reject_updated_at",),
    "reject_source_artifact": ("reject_source_artifact",),
    "success_rate_30": ("success_rate_30", "hit_rate_30", "win_rate_30"),
    "success_rate_100": ("success_rate_100", "hit_rate_100", "win_rate_100"),
    "success_rate_500": ("success_rate_500", "hit_rate_500", "win_rate_500"),
    "success_rate_1500": ("success_rate_1500", "hit_rate_1500", "win_rate_1500"),
}

# Success-rate contract questions that are UNDEFINED in the codebase. The audit
# surfaces these; it must NOT pick answers (per task STOP condition #2).
SUCCESS_RATE_CONTRACT_UNDEFINED = [
    "Is hit_count >= 1 a success, or a per-lottery threshold (539 M2+/M3+, BIG/POWER M3+)?",
    "Is special_hit counted toward success or excluded?",
    "Multi-bet: any-bet-hit per draw, or per-bet average?",
    "Do per-lottery hit_count thresholds differ across 539 / BIG_LOTTO / POWER_LOTTO?",
    "Window basis: last-N by target_draw (CAST INTEGER DESC) or by draw_date?",
    "Window set: system evidence uses 150/500/1500; task asks 30/100/500/1500 — "
    "confirm intended windows (30/100 have no precedent in this repo).",
]


def _load_registry():
    """Return (cells, supported_set, ids_set, lifecycle_by_id, exec_ids). READ-ONLY."""
    sys.path.insert(0, str(REPO_ROOT / "lottery_api"))
    from models.replay_strategy_registry import (  # type: ignore
        list_strategy_lifecycle_metadata,
        list_executable_strategy_ids,
    )
    meta = list_strategy_lifecycle_metadata()
    exec_ids = set(list_executable_strategy_ids())
    supported = set()
    lifecycle_by_id = {}
    ids = set()
    for m in meta:
        ids.add(m["strategy_id"])
        lifecycle_by_id[m["strategy_id"]] = m["lifecycle_status"]
        for lt in m["supported_lottery_types"]:
            supported.add((lt, m["strategy_id"]))
    return supported, ids, lifecycle_by_id, exec_ids


def _load_db_cells(db_path: Path):
    """Return {(lottery_type, strategy_id): {rows, draws, bets}} via SELECT only."""
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT lottery_type, strategy_id,
                   COUNT(*) AS rows,
                   COUNT(DISTINCT target_draw) AS draws,
                   GROUP_CONCAT(DISTINCT bet_index) AS bets
            FROM strategy_prediction_replays
            GROUP BY lottery_type, strategy_id
            """
        ).fetchall()
        per_lottery = dict(
            conn.execute(
                "SELECT lottery_type, COUNT(*) FROM strategy_prediction_replays "
                "GROUP BY lottery_type"
            ).fetchall()
        )
    finally:
        conn.close()
    cells = {}
    for r in rows:
        cells[(r["lottery_type"], r["strategy_id"])] = {
            "rows": r["rows"],
            "draws": r["draws"],
            "bets": sorted(int(b) for b in str(r["bets"]).split(",") if b.strip()),
        }
    return cells, per_lottery


def _missing_reason(lifecycle: str, registry_status: str, has_rows: bool):
    if has_rows:
        return None
    if registry_status in ("unregistered_orphan", "registry_lottery_mismatch"):
        return None
    if lifecycle == "OBSERVATION":
        return "observation_no_data"
    if lifecycle in ("REJECTED", "RETIRED", "OFFLINE"):
        return "registered_without_rows"
    return "no_production_replay"


def build_audit(db_path: Path = DB_PATH, d3_artifact: Path = D3_ARTIFACT) -> dict:
    """Pure, read-only. Returns the full coverage-audit dict; writes nothing."""
    supported, reg_ids, lifecycle_by_id, exec_ids = _load_registry()
    db_cells, db_per_lottery = _load_db_cells(db_path)

    # Universe = registry-supported cells UNION DB cells.
    universe_keys = sorted(set(supported) | set(db_cells.keys()))

    matrix = []
    for (lt, sid) in universe_keys:
        if (lt, sid) in supported:
            registry_status = "registered"
            lifecycle = lifecycle_by_id.get(sid, "UNKNOWN")
        elif sid in reg_ids:
            registry_status = "registry_lottery_mismatch"
            lifecycle = lifecycle_by_id.get(sid, "UNKNOWN")
        else:
            registry_status = "unregistered_orphan"
            lifecycle = "UNREGISTERED"
        has_rows = (lt, sid) in db_cells
        matrix.append({
            "lottery_type": lt,
            "strategy_id": sid,
            "registry_status": registry_status,
            "lifecycle": lifecycle,
            "has_replay_rows": has_rows,
            "can_open_detail": has_rows,  # P262B: can_open_detail == has_replay_rows
            "distinct_draw_count": db_cells.get((lt, sid), {}).get("draws", 0),
            "replay_row_count": db_cells.get((lt, sid), {}).get("rows", 0),
            "missing_reason": _missing_reason(lifecycle, registry_status, has_rows),
            "appears_in_replay_overview": True,  # coverage_mode surfaces every cell
        })

    # ---- D3 page contents ----
    d3 = json.loads(Path(d3_artifact).read_text(encoding="utf-8"))
    d3_rows = d3.get("rows", [])
    d3_keys = set()
    for r in d3_rows:
        d3_keys.update(r.keys())
    d3_cell_set = {(r["lottery_type"], r["strategy_id"]) for r in d3_rows}

    universe_set = set(universe_keys)
    d3_in_universe = sorted(d3_cell_set & universe_set)
    d3_phantom = sorted(d3_cell_set - universe_set)  # in D3, not in registry/DB

    for row in matrix:
        row["appears_in_D3"] = (row["lottery_type"], row["strategy_id"]) in d3_cell_set

    # D3 field availability (derived from the artifact's actual row keys).
    def has(field):
        return any(k in d3_keys for k in REQUESTED_FIELD_KEYS[field])

    field_availability = {f: has(f) for f in REQUESTED_FIELD_KEYS}
    # status_reason: artifact carries d3_contract_reason (contract only), not a
    # lifecycle/evidence status reason → report as contract-only, not satisfied.
    field_availability["status_reason"] = False
    missing_fields = sorted(f for f, ok in field_availability.items() if not ok)

    # Lifecycle disagreement: D3 lifecycle_status vs registry lifecycle for mapped cells.
    d3_lifecycle = {
        (r["lottery_type"], r["strategy_id"]): r.get("lifecycle_status")
        for r in d3_rows
    }
    lifecycle_disagreements = []
    for (lt, sid) in d3_in_universe:
        reg_life = lifecycle_by_id.get(sid, "UNREGISTERED")
        d3_life = d3_lifecycle.get((lt, sid))
        if d3_life and d3_life != reg_life:
            lifecycle_disagreements.append({
                "lottery_type": lt, "strategy_id": sid,
                "d3_lifecycle": d3_life, "registry_lifecycle": reg_life,
            })

    # replay_row_count integrity: D3 uses a per-lottery aggregate. Check it.
    d3_replay_by_lottery = {}
    for r in d3_rows:
        d3_replay_by_lottery.setdefault(r["lottery_type"], set()).add(
            r.get("replay_row_count")
        )
    replay_count_findings = []
    for lt, vals in sorted(d3_replay_by_lottery.items()):
        d3_val = next(iter(vals)) if len(vals) == 1 else sorted(vals)
        db_val = db_per_lottery.get(lt)
        replay_count_findings.append({
            "lottery_type": lt,
            "d3_replay_row_count": d3_val,
            "db_lottery_total": db_val,
            "is_per_strategy": False,
            "matches_db_total": (len(vals) == 1 and d3_val == db_val),
        })

    coverage_count = sum(1 for r in matrix if r["appears_in_D3"])
    return {
        "task": "P263A_D3_STRATEGY_STATUS_COVERAGE_AUDIT",
        "generated_for_head": "ccd45cdee6e2dd233652f91038b8e3326044f482",
        "read_only": True,
        "universe": {
            "total_cells": len(universe_keys),
            "total_strategy_ids": len({sid for (_lt, sid) in universe_keys}),
            "registry_cells": len(supported),
            "db_cells": len(db_cells),
            "registered_without_rows": sorted(
                f"{lt}:{sid}" for (lt, sid) in supported
                if (lt, sid) not in db_cells
            ),
            "unregistered_orphans": sorted(
                f"{lt}:{sid}" for r in matrix
                if r["registry_status"] == "unregistered_orphan"
                for (lt, sid) in [(r["lottery_type"], r["strategy_id"])]
            ),
            "registry_lottery_mismatch": sorted(
                f"{lt}:{sid}" for r in matrix
                if r["registry_status"] == "registry_lottery_mismatch"
                for (lt, sid) in [(r["lottery_type"], r["strategy_id"])]
            ),
        },
        "d3": {
            "route": "/api/replay/d3-strategy-status-audit",
            "data_source": "artifact_only",
            "artifact": str(Path(d3_artifact).relative_to(REPO_ROOT)),
            "row_count": len(d3_rows),
            "coverage_count": coverage_count,
            "coverage_cells": [f"{lt}:{sid}" for (lt, sid) in d3_in_universe],
            "phantom_rows": [f"{lt}:{sid}" for (lt, sid) in d3_phantom],
            "missing_cells": [
                f"{r['lottery_type']}:{r['strategy_id']}"
                for r in matrix if not r["appears_in_D3"]
            ],
            "field_availability": field_availability,
            "missing_fields": missing_fields,
            "lifecycle_disagreements": lifecycle_disagreements,
            "replay_row_count_findings": replay_count_findings,
        },
        "success_rate": {
            "raw_data_exists_in_replay_db": True,
            "raw_data_columns": ["hit_count", "special_hit", "predicted_numbers",
                                 "actual_numbers", "hit_numbers", "target_draw",
                                 "target_date", "bet_index"],
            "exposed_by_d3": False,
            "exposed_by_any_api": False,
            "contract_defined": False,
            "contract_open_questions": SUCCESS_RATE_CONTRACT_UNDEFINED,
        },
        "status_reject_reason": {
            "registry_has_reason_field": False,
            "registry_has_updated_at_field": False,
            "registry_has_source_field": False,
            "rejected_artifacts_dir": "rejected/ (43 json files)",
            "rejected_artifacts_used_by_d3": False,
            "replay_status_uniform_predicted": True,
        },
        "coverage_matrix": matrix,
    }


def _render_md(a: dict) -> str:
    u, d3 = a["universe"], a["d3"]
    lines = [
        "# P263A — D3 Strategy Status / Contract Audit Coverage Audit",
        "",
        "_Read-only audit. No UI/API/DB/registry/adapter change._",
        "",
        "## Summary",
        f"- Universe: **{u['total_cells']} cells / {u['total_strategy_ids']} strategy_ids** "
        f"(registry {u['registry_cells']}, DB {u['db_cells']}).",
        f"- D3 coverage: **{d3['coverage_count']} / {u['total_cells']} cells** "
        f"({d3['row_count']} D3 rows = {d3['coverage_count']} mapped + "
        f"{len(d3['phantom_rows'])} phantom).",
        f"- registered-without-rows ({len(u['registered_without_rows'])}): "
        f"{', '.join(u['registered_without_rows'])}",
        f"- unregistered orphans ({len(u['unregistered_orphans'])}): "
        f"{', '.join(u['unregistered_orphans'])}",
        f"- registry/lottery mismatch ({len(u['registry_lottery_mismatch'])}): "
        f"{', '.join(u['registry_lottery_mismatch'])}",
        "",
        "## D3 missing fields",
        ", ".join(d3["missing_fields"]) or "(none)",
        "",
        "## D3 lifecycle disagreements (D3 vs registry)",
    ]
    for d in d3["lifecycle_disagreements"]:
        lines.append(
            f"- {d['lottery_type']}:{d['strategy_id']} — "
            f"D3={d['d3_lifecycle']} vs registry={d['registry_lifecycle']}"
        )
    lines += ["", "## D3 replay_row_count findings (per-lottery aggregate)"]
    for f in d3["replay_row_count_findings"]:
        lines.append(
            f"- {f['lottery_type']}: D3={f['d3_replay_row_count']} "
            f"vs DB total={f['db_lottery_total']} "
            f"(matches={f['matches_db_total']})"
        )
    lines += [
        "",
        "## Success-rate (30/100/500/1500) availability",
        f"- raw data exists in strategy_prediction_replays: "
        f"{a['success_rate']['raw_data_exists_in_replay_db']}",
        f"- exposed by D3 / any API: {a['success_rate']['exposed_by_d3']} / "
        f"{a['success_rate']['exposed_by_any_api']}",
        f"- contract defined: {a['success_rate']['contract_defined']}",
        "- open contract questions:",
    ]
    for q in a["success_rate"]["contract_open_questions"]:
        lines.append(f"  - {q}")
    lines += [
        "",
        "## Coverage matrix",
        "| lottery | strategy_id | in_D3 | lifecycle | registry_status | has_rows | can_open_detail | missing_reason |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in a["coverage_matrix"]:
        lines.append(
            f"| {r['lottery_type']} | {r['strategy_id']} | "
            f"{'YES' if r['appears_in_D3'] else 'NO'} | {r['lifecycle']} | "
            f"{r['registry_status']} | {'Y' if r['has_replay_rows'] else 'N'} | "
            f"{'Y' if r['can_open_detail'] else 'N'} | {r['missing_reason'] or '-'} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    audit = build_audit()
    OUT_JSON.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    OUT_MD.write_text(_render_md(audit), encoding="utf-8")
    print(f"D3 coverage: {audit['d3']['coverage_count']} / "
          f"{audit['universe']['total_cells']} cells")
    print(f"phantom D3 rows: {len(audit['d3']['phantom_rows'])}")
    print(f"missing fields: {len(audit['d3']['missing_fields'])}")
    print(f"wrote {OUT_JSON.relative_to(REPO_ROOT)}")
    print(f"wrote {OUT_MD.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
