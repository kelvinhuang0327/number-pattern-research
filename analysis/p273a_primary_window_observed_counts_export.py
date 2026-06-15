"""
P273A — Primary-Window Prize-Aware Observed-Counts Export (read-only).

Owner-approved primary decision windows are now SHORT=50 / MID=300 / LONG=750
distinct target draws. The previous 100 / 500 / 1500 export remains immutable;
1500 + all-history are REFERENCE-ONLY and must NOT drive strategy promotion,
elimination, stability PASS/FAIL, GO recommendation, or deployment screening.

THIS MODULE IS A READ-ONLY DATA EXPORT PREREQUISITE ONLY. It is NOT P273A
inference and NOT P273B feature mining. It computes NO random baseline, expected
successes, confidence interval, p-value, corrected significance, BH-FDR, edge
classification, GO recommendation, or any verdict.

Reuse contract (no rewrite, no fork of the committed exporter)
--------------------------------------------------------------
This wrapper IMPORTS and REUSES the committed, already-reviewed
``analysis/p273a_prizeaware_replay_export.py`` helpers verbatim:
  - frozen-cell load + endpoint verification (load_frozen_cells,
    verify_endpoints_against_p271a)
  - read-only connection + schema verification (open_readonly_connection,
    verify_schema) — URI mode=ro + PRAGMA query_only=ON, one connection,
    one explicit read transaction / one consistent snapshot
  - per-row processing + per-window aggregation (_process_rows,
    aggregate_window) — P271C scorer + P271E adapter eligibility/scoring
  - canonical payload digest (compute_payload_digest), sha256_file, _now_iso
The ONLY behavioural change is the exact window tuple (50, 300, 750) and the
owner-approved window-policy metadata. The committed exporter, its tests, and
its 100/500/1500 artifacts are NOT modified.

Key invariants (governance)
---------------------------
  - Import-safe: no DB open, no file write, no network/subprocess at import.
  - Opens the canonical DB strictly read-only (URI mode=ro, PRAGMA
    query_only=ON), one connection, one read transaction, one snapshot.
  - Permitted tables only: strategy_prediction_replays, draws. SELECT/PRAGMA
    reads only; no write statement of any kind.
  - POWER_LOTTO rows with a missing stored second-zone prediction are excluded
    and NEVER filled, defaulted, inferred, or replaced by the actual value.
  - Emits no inference, baseline, probability, p-value, correction, edge, or GO.

artifact_version = "p273a_primary_window_observed_counts_v1"
policy_version   = "primary_window_policy_v1_50_300_750"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

# --------------------------------------------------------------------------- #
# Import-safe path bootstrap so the committed exporter and lottery_api resolve  #
# whether this module is run as a script or imported (pytest sets pythonpath=.).#
# This only manipulates sys.path; it opens no DB and writes no file.            #
# --------------------------------------------------------------------------- #
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Reuse the committed, reviewed exporter helpers verbatim (no fork, no rewrite).
from analysis.p273a_prizeaware_replay_export import (  # noqa: E402
    ADAPTER_VERSION,
    CANONICAL_DB_PATH,
    CELL_QUERY,
    DB_OPEN_MODE,
    EXPECTED_FROZEN_CELL_COUNT,
    GOVERNED_ENDPOINT,
    LOTTERY_TYPES,
    P267C_JSON_PATH,
    P271A_JSON_PATH,
    P271C_SOURCE_PATH,
    P271E_SOURCE_PATH,
    REQUIRED_COLUMNS,
    SCORING_VERSION,
    SOURCE_VERIFICATION_STATUS,
    _now_iso,
    _process_rows,
    _strip_volatile,
    _VOLATILE_KEYS,
    aggregate_window,
    compute_payload_digest,
    load_frozen_cells,
    open_readonly_connection,
    sha256_file,
    verify_endpoints_against_p271a,
    verify_schema,
)

# --------------------------------------------------------------------------- #
# Frozen constants — owner-approved primary-window policy                       #
# --------------------------------------------------------------------------- #

TASK_ID = "P273A_PRIMARY_WINDOW_OBSERVED_COUNTS_EXPORT"
ARTIFACT_VERSION = "p273a_primary_window_observed_counts_v1"
POLICY_VERSION = "primary_window_policy_v1_50_300_750"

# The exact primary decision windows are FROZEN for this task. Any adjustment
# requires a separate pre-outcome owner-approved task and a new export.
PRIMARY_WINDOWS = (50, 300, 750)
PRIMARY_WINDOW_LABELS = {50: "SHORT", 300: "MID", 750: "LONG"}

# Reference-only horizons: recorded for transparency, never a decision input.
REFERENCE_ONLY_WINDOWS = (1500,)
REFERENCE_ONLY_DESCRIPTIONS = (
    "1500 draws",
    "all-history frequency or distribution",
    "any longer-horizon aggregate not in 50 / 300 / 750",
)
REFERENCE_ONLY_PROHIBITED_USES = (
    "strategy_promotion",
    "strategy_elimination",
    "stability_pass_or_fail",
    "go_recommendation",
    "production_deployment_screening",
)

# 36 frozen strategy×lottery cells × 3 primary windows. Recorded only; this
# export performs NO correction and NO inference.
CORRECTION_FAMILY_PLANNED = EXPECTED_FROZEN_CELL_COUNT * len(PRIMARY_WINDOWS)

# The immutable prior artifact (100/500/1500) is superseded for *primary*
# decisions but remains immutable and is reference-only going forward.
PRIOR_ARTIFACT_PATH = (
    "outputs/research/p273a_prizeaware_observed_counts_20260614.json"
)

DEFAULT_OUT_JSON = (
    "outputs/research/p273a_primary_window_observed_counts_20260615.json"
)
DEFAULT_OUT_MD = (
    "outputs/research/p273a_primary_window_observed_counts_20260615.md"
)

# Windows that must NEVER appear as a primary record in this artifact.
_FORBIDDEN_PRIMARY_WINDOWS = frozenset({100, 500, 1500})


class PrimaryWindowExportError(RuntimeError):
    """Raised when a primary-window invariant is violated -> STOP, no write."""


# --------------------------------------------------------------------------- #
# Per-cell computation: reuse _process_rows + aggregate_window with the new     #
# primary window tuple (committed compute_cell hardcodes 100/500/1500).         #
# --------------------------------------------------------------------------- #

def compute_cell_primary(conn, lottery_type: str, strategy_id: str) -> dict:
    """Read one cell's rows and aggregate ONLY the primary windows 50/300/750.

    Uses the committed read query and the committed per-row / per-window helpers
    verbatim; the sole difference from the base exporter is the window tuple.
    """
    rows = conn.execute(CELL_QUERY, (lottery_type, strategy_id)).fetchall()
    processed, distinct_draws_desc = _process_rows(rows)
    windows = []
    for w in PRIMARY_WINDOWS:
        rec = aggregate_window(
            processed, distinct_draws_desc, w, lottery_type, strategy_id
        )
        if rec["window"] in _FORBIDDEN_PRIMARY_WINDOWS:
            raise PrimaryWindowExportError(
                f"forbidden reference-only window leaked into primary export: "
                f"{rec['window']}"
            )
        rec["window_label"] = PRIMARY_WINDOW_LABELS[w]
        windows.append(rec)
    return {
        "lottery_type": lottery_type,
        "strategy_id": strategy_id,
        "distinct_draws_available": len(distinct_draws_desc),
        "windows": windows,
    }


# --------------------------------------------------------------------------- #
# Window-policy metadata block (pure)                                          #
# --------------------------------------------------------------------------- #

def build_window_policy() -> dict:
    return {
        "owner_approved": True,
        "policy_version": POLICY_VERSION,
        "primary_windows": list(PRIMARY_WINDOWS),
        "primary_window_labels": {
            str(k): v for k, v in PRIMARY_WINDOW_LABELS.items()
        },
        "reference_only_windows": list(REFERENCE_ONLY_WINDOWS),
        "reference_only_descriptions": list(REFERENCE_ONLY_DESCRIPTIONS),
        "reference_only_prohibited_uses": list(REFERENCE_ONLY_PROHIBITED_USES),
        "correction_family_planned": CORRECTION_FAMILY_PLANNED,
        "correction_family_note": (
            "36 frozen strategy×lottery cells × 3 primary windows = 108; "
            "this export records the intended family ONLY and performs no "
            "correction and no inference"
        ),
        "window_adjustment_rule": (
            "primary windows are frozen as 50/300/750 for this task; any "
            "statistical-expert adjustment requires a separate pre-outcome "
            "owner-approved task and a new export; do not adjust windows after "
            "viewing results"
        ),
        "prior_artifact_now_reference_only": PRIOR_ARTIFACT_PATH,
    }


# --------------------------------------------------------------------------- #
# Orchestration (single mode=ro connection, single read snapshot)             #
# --------------------------------------------------------------------------- #

def run_export(db_path: str = CANONICAL_DB_PATH,
               p267c_path: str = P267C_JSON_PATH,
               p271a_path: str = P271A_JSON_PATH,
               scorer_path: str = P271C_SOURCE_PATH,
               adapter_path: str = P271E_SOURCE_PATH) -> dict:
    """Run the full read-only primary-window export; return one canonical dict.

    Owns exactly one mode=ro connection and one read transaction (one snapshot).
    Performs no inference and no write of any kind to the database.
    """
    frozen_cells = load_frozen_cells(p267c_path)
    committed_conditions = verify_endpoints_against_p271a(p271a_path)
    source_hashes = {
        "p271a_json_sha256": sha256_file(p271a_path),
        "p267c_json_sha256": sha256_file(p267c_path),
        "p271c_source_sha256": sha256_file(scorer_path),
        "p271e_source_sha256": sha256_file(adapter_path),
    }

    conn, query_only_evidence = open_readonly_connection(db_path)
    transaction_start_at = _now_iso()
    try:
        conn.execute("BEGIN")  # explicit read transaction -> one snapshot
        schema = verify_schema(conn)
        cells = [
            compute_cell_primary(conn, c["lottery_type"], c["strategy_id"])
            for c in frozen_cells
        ]
        conn.execute("ROLLBACK")  # end read transaction; no write performed
    finally:
        conn.close()
    transaction_end_at = _now_iso()

    # Defensive: assert exactly the primary windows are present, nothing else.
    for cell in cells:
        windows_seen = [w["window"] for w in cell["windows"]]
        if windows_seen != list(PRIMARY_WINDOWS):
            raise PrimaryWindowExportError(
                f"cell {cell['lottery_type']}/{cell['strategy_id']} windows "
                f"{windows_seen} != primary {list(PRIMARY_WINDOWS)}"
            )

    # Roll up exclusion totals per lottery for transparency.
    exclusion_totals = {lt: Counter() for lt in LOTTERY_TYPES}
    for cell in cells:
        lt = cell["lottery_type"]
        for w in cell["windows"]:
            exclusion_totals[lt].update(w["exclusion_by_reason"])
    exclusion_summary = {
        lt: dict(sorted(counter.items()))
        for lt, counter in exclusion_totals.items()
    }

    endpoint_definitions = {
        lt: {
            "endpoint_id": GOVERNED_ENDPOINT[lt]["endpoint_id"],
            "committed_condition_sql": committed_conditions[lt],
            "task_shorthand": GOVERNED_ENDPOINT[lt]["task_shorthand"],
            "min_qualifying_tier": GOVERNED_ENDPOINT[lt]["min_qualifying_tier"],
            "scored_by": "lottery_api.prize_aware_scorer.any_prize_aware_win",
        }
        for lt in LOTTERY_TYPES
    }

    result = {
        "meta": {
            "task_id": TASK_ID,
            "artifact_version": ARTIFACT_VERSION,
            "policy_version": POLICY_VERSION,
            "scoring_version": SCORING_VERSION,
            "adapter_version": ADAPTER_VERSION,
            "source_verification_status": SOURCE_VERIFICATION_STATUS,
            "generated_at": _now_iso(),
            "frozen_strategy_cell_count": len(frozen_cells),
            "lotteries": list(LOTTERY_TYPES),
            "primary_windows": list(PRIMARY_WINDOWS),
            "analysis_unit": "distinct target_draw (draw-level any-bet)",
        },
        "window_policy": build_window_policy(),
        "safety_flags": {
            "db_read_only": True,
            "production_write": False,
            "services_controlled": False,
            "inference_performed": False,
            "edge_claim_made": False,
            "go_recommendation_made": False,
            "registry_mutation": False,
            "baseline_computed": False,
            "p_value_computed": False,
            "second_zone_manufactured": False,
        },
        "provenance": {
            "source_db_path": db_path,
            "db_open_mode": DB_OPEN_MODE,
            "query_only_evidence": query_only_evidence,
            "single_snapshot": True,
            "single_connection": True,
            "transaction_start_at": transaction_start_at,
            "transaction_end_at": transaction_end_at,
            "permitted_tables": sorted(REQUIRED_COLUMNS.keys()),
            "normalized_cell_query": CELL_QUERY,
            "schema": schema,
            "source_hashes": source_hashes,
            "canonical_payload_digest_excludes": sorted(_VOLATILE_KEYS),
            "frozen_cells": frozen_cells,
            "reused_export_module": "analysis/p273a_prizeaware_replay_export.py",
        },
        "endpoint_definitions": endpoint_definitions,
        "windowing_semantics": {
            "selection": "most-recent N distinct target_draw, CAST(target_draw AS INTEGER) DESC",
            "support_rule": "a draw counts toward support only if >= 1 eligible scoreable bet remains",
            "success_rule": "draw success = any eligible bet is an any_prize_aware_win",
            "bet_count_scope": "distinct scoreable bet_index per supported draw",
            "power_exclusion": "POWER_LOTTO rows with NULL predicted_special excluded (never filled)",
            "dedupe_rule": "rows deduplicated by (target_draw, bet_index) to avoid pseudo-replication",
            "primary_windows": list(PRIMARY_WINDOWS),
            "reference_only_excluded_from_export": list(REFERENCE_ONLY_WINDOWS),
        },
        "exclusion_summary_by_lottery": exclusion_summary,
        "cells": cells,
    }
    result["canonical_payload_digest"] = compute_payload_digest(result)
    return result


# --------------------------------------------------------------------------- #
# Markdown rendering (deterministic; derived from the one canonical result)   #
# --------------------------------------------------------------------------- #

def render_markdown(result: dict) -> str:
    meta = result["meta"]
    prov = result["provenance"]
    pol = result["window_policy"]
    lines = []
    A = lines.append
    A("# P273A — Primary-Window Prize-Aware Observed-Counts Export")
    A("")
    A(
        "> **Read-only observed-counts artifact.** No random baseline, expected "
        "successes, probability, p-value, correction, confidence interval, "
        "BH-FDR, edge classification, or GO recommendation is computed here. "
        "P273A inferential validation is a separate, future, separately "
        "authorized task."
    )
    A("")
    A("## Owner-approved primary-window policy")
    A("")
    A(f"- policy_version: `{pol['policy_version']}` (owner_approved: "
      f"`{str(pol['owner_approved']).lower()}`)")
    A(f"- **Primary decision windows:** "
      + ", ".join(f"{w} ({PRIMARY_WINDOW_LABELS[w]})" for w in PRIMARY_WINDOWS))
    A(f"- **Reference-only (excluded from this export):** "
      f"{', '.join(pol['reference_only_descriptions'])}")
    A(f"- Reference-only evidence must NOT drive: "
      f"{', '.join(pol['reference_only_prohibited_uses'])}")
    A(f"- correction_family_planned: **{pol['correction_family_planned']}** "
      f"(36 cells × 3 primary windows; correction/inference NOT performed)")
    A(f"- window_adjustment_rule: {pol['window_adjustment_rule']}")
    A(f"- prior 100/500/1500 artifact (now reference-only, immutable): "
      f"`{pol['prior_artifact_now_reference_only']}`")
    A("")
    A("## Run metadata")
    A("")
    A(f"- task_id: `{meta['task_id']}`")
    A(f"- artifact_version: `{meta['artifact_version']}`")
    A(f"- scoring_version: `{meta['scoring_version']}`")
    A(f"- adapter_version: `{meta['adapter_version']}`")
    A(f"- generated_at: `{meta['generated_at']}`")
    A(f"- frozen_strategy_cell_count: **{meta['frozen_strategy_cell_count']}**")
    A(f"- lotteries: {', '.join(meta['lotteries'])}")
    A(f"- primary_windows: {', '.join(str(w) for w in meta['primary_windows'])}")
    A(f"- source_verification_status: `{meta['source_verification_status']}`")
    A("")
    A("## Safety flags")
    A("")
    for key in (
        "db_read_only", "production_write", "services_controlled",
        "inference_performed", "edge_claim_made", "go_recommendation_made",
        "registry_mutation", "baseline_computed", "p_value_computed",
        "second_zone_manufactured",
    ):
        A(f"- {key}: `{str(result['safety_flags'][key]).lower()}`")
    A("")
    A("## Provenance")
    A("")
    A(f"- source_db_path: `{prov['source_db_path']}`")
    A(f"- db_open_mode: `{prov['db_open_mode']}`")
    A(f"- query_only_enabled: "
      f"`{str(prov['query_only_evidence']['query_only_enabled']).lower()}`")
    A(f"- single_snapshot: `{str(prov['single_snapshot']).lower()}` "
      f"(one connection, one read transaction)")
    A(f"- permitted_tables: {', '.join(prov['permitted_tables'])}")
    A(f"- reused_export_module: `{prov['reused_export_module']}`")
    A(f"- schema user_version: `{prov['schema']['user_version']}`")
    A(f"- schema_fingerprint_sha256: "
      f"`{prov['schema']['schema_fingerprint_sha256']}`")
    for label, key in (
        ("P271A spec", "p271a_json_sha256"),
        ("P267C artifact", "p267c_json_sha256"),
        ("P271C scorer src", "p271c_source_sha256"),
        ("P271E adapter src", "p271e_source_sha256"),
    ):
        A(f"- {label} SHA-256: `{prov['source_hashes'][key]}`")
    A(f"- canonical_payload_digest: `{result['canonical_payload_digest']}`")
    A("")
    A("## Governed endpoint (verified against P271A)")
    A("")
    A("| lottery | endpoint_id | condition (committed) | min tier |")
    A("|---|---|---|---|")
    for lt in LOTTERY_TYPES:
        ep = result["endpoint_definitions"][lt]
        A(f"| {lt} | `{ep['endpoint_id']}` | "
          f"`{ep['committed_condition_sql']}` | {ep['min_qualifying_tier']} |")
    A("")
    A("## Per-cell observed counts (primary windows 50 / 300 / 750)")
    A("")
    A("| lottery | strategy_id | window | label | support_draws | "
      "observed_successes | success_rate | scoreable_rows | excluded_rows | "
      "excl_missing_special | bet_count(min..max) | latest..earliest |")
    A("|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|---|")
    for cell in result["cells"]:
        for w in cell["windows"]:
            rate = (
                f"{w['observed_success_rate']:.6f}"
                if w["observed_success_rate"] is not None else "—"
            )
            bc = (
                f"{w['bet_count_min']}..{w['bet_count_max']}"
                if w["bet_count_min"] is not None else "—"
            )
            span = (
                f"{w['latest_target_draw']}..{w['earliest_target_draw']}"
                if w["latest_target_draw"] is not None else "—"
            )
            A(f"| {w['lottery_type']} | {w['strategy_id']} | {w['window']} | "
              f"{w['window_label']} | {w['support_draws']} | "
              f"{w['observed_successes']} | {rate} | {w['scoreable_rows']} | "
              f"{w['excluded_rows']} | {w['excluded_missing_special_rows']} | "
              f"{bc} | {span} |")
    A("")
    return "\n".join(lines)


def write_artifacts(result: dict, out_json: str, out_md: str) -> None:
    """Write the JSON and Markdown artifacts from the one canonical result."""
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    with open(out_md, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(result))
        fh.write("\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="P273A read-only primary-window (50/300/750) prize-aware "
                    "observed-counts export"
    )
    parser.add_argument("--db", default=CANONICAL_DB_PATH,
                        help="path to the canonical SQLite DB (opened mode=ro)")
    parser.add_argument("--p267c", default=P267C_JSON_PATH)
    parser.add_argument("--p271a", default=P271A_JSON_PATH)
    parser.add_argument("--scorer-src", default=P271C_SOURCE_PATH)
    parser.add_argument("--adapter-src", default=P271E_SOURCE_PATH)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)

    result = run_export(
        db_path=args.db,
        p267c_path=args.p267c,
        p271a_path=args.p271a,
        scorer_path=args.scorer_src,
        adapter_path=args.adapter_src,
    )
    write_artifacts(result, args.out_json, args.out_md)
    print(json.dumps({
        "task_id": TASK_ID,
        "policy_version": POLICY_VERSION,
        "primary_windows": list(PRIMARY_WINDOWS),
        "frozen_strategy_cell_count": result["meta"]["frozen_strategy_cell_count"],
        "correction_family_planned": CORRECTION_FAMILY_PLANNED,
        "canonical_payload_digest": result["canonical_payload_digest"],
        "out_json": args.out_json,
        "out_md": args.out_md,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
