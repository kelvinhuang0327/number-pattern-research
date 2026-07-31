#!/usr/bin/env python3
"""
P19 Odds Identity Join Repair CLI

Repairs the game_id identity join gap that blocked P17 settlement.

Usage:
  python scripts/run_p19_odds_identity_join_repair.py \
    --p15-ledger  outputs/.../simulation_ledger.csv \
    --p15-joined  outputs/.../joined_oof_with_odds.csv \
    --p16-6-recommendation-rows  outputs/.../recommendation_rows.csv \
    --p17-ledger  outputs/.../paper_recommendation_ledger.csv \
    --output-dir  outputs/.../p19_odds_identity_join_repair \
    --paper-only  true

PAPER_ONLY — no production systems, no real bets, no live TSL.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from wbc_backend.recommendation.p19_identity_field_audit import audit_identity_columns
from wbc_backend.recommendation.p19_p15_ledger_identity_enricher import (
    IDENTITY_ENRICHED_BY_VERIFIED_POSITIONAL_ALIGNMENT,
    IDENTITY_ENRICHED_BY_ROW_IDX,
    IDENTITY_BLOCKED_UNSAFE_ALIGNMENT,
    IDENTITY_BLOCKED_MISSING_GAME_ID_SOURCE,
    IDENTITY_BLOCKED_DUPLICATE_GAME_ID,
    enrich_simulation_ledger_with_identity,
    validate_enriched_ledger,
    summarize_identity_enrichment,
    P19_BLOCKED_UNSAFE_POSITIONAL_ALIGNMENT,
)
from wbc_backend.recommendation.p17_settlement_join_audit import (
    audit_recommendation_to_enriched_p15_join,
    summarize_settlement_join_quality,
)

SCRIPT_VERSION = "P19_ODDS_IDENTITY_JOIN_REPAIR_V1"

# Gate decisions
P19_IDENTITY_JOIN_REPAIR_READY = "P19_IDENTITY_JOIN_REPAIR_READY"
P19_BLOCKED_UNSAFE_POSITIONAL_ALIGNMENT = P19_BLOCKED_UNSAFE_POSITIONAL_ALIGNMENT
P19_BLOCKED_MISSING_GAME_ID_SOURCE = "P19_BLOCKED_MISSING_GAME_ID_SOURCE"
P19_BLOCKED_DUPLICATE_GAME_ID = "P19_BLOCKED_DUPLICATE_GAME_ID"
P19_BLOCKED_CONTRACT_VIOLATION = "P19_BLOCKED_CONTRACT_VIOLATION"
P19_FAIL_INPUT_MISSING = "P19_FAIL_INPUT_MISSING"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, obj: dict) -> None:
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=str)


def _write_md(path: Path, content: str) -> None:
    with open(path, "w") as f:
        f.write(content)


def _identity_field_audit_md(audit, paths: dict) -> str:
    lines = ["# P19 Identity Field Audit\n"]
    lines.append(f"Generated: {_now()}\n\n")
    lines.append("## Files Checked\n")
    for name, p in paths.items():
        has_id = name in audit.files_with_game_id
        lines.append(f"- `{name}`: `{p}` — game_id: {'✓' if has_id else '✗'}\n")
    lines.append("\n## Coverage Reports\n")
    for cr in audit.coverage_reports:
        lines.append(
            f"- `{cr.column}` in {audit.files_checked[audit.coverage_reports.index(cr)]}: "
            f"{cr.n_non_null}/{cr.n_total} ({cr.coverage*100:.1f}%) quality={cr.quality}\n"
        )
    if audit.comparison:
        lines.append("\n## Alignment Check (simulation_ledger vs joined_oof)\n")
        c = audit.comparison
        lines.append(f"- Sort key: `{c.sort_key_used}`\n")
        lines.append(f"- y_true match: {c.ytrue_match}\n")
        lines.append(f"- fold_id match: {c.fold_id_match}\n")
        lines.append(f"- max p_model diff: {c.p_model_max_diff}\n")
        lines.append(f"- max p_market diff: {c.p_market_max_diff}\n")
        lines.append(f"- **alignment_safe: {c.alignment_safe}**\n")
        lines.append(f"- reason: {c.alignment_reason}\n")
    lines.append(f"\n## Enrichment Feasible: {audit.enrichment_feasible}\n")
    if audit.enrichment_blocker:
        lines.append(f"**Blocker**: {audit.enrichment_blocker}\n")
    return "".join(lines)


def _enrichment_summary_md(summary: dict, validation_ok: bool) -> str:
    lines = ["# P19 Identity Enrichment Summary\n\n"]
    for k, v in summary.items():
        lines.append(f"- **{k}**: {v}\n")
    lines.append(f"\n**Contract Validation**: {'PASS' if validation_ok else 'FAIL'}\n")
    return "".join(lines)


def _settlement_join_repair_md(join_result, rec_summary: dict) -> str:
    lines = ["# P19 Settlement Join Repair Audit\n\n"]
    lines.append(f"- join_method: `{join_result.join_method}`\n")
    lines.append(f"- join_quality: **{join_result.join_quality}**\n")
    lines.append(f"- n_recommendations: {join_result.n_recommendations}\n")
    lines.append(f"- n_joined: {join_result.n_joined}\n")
    lines.append(f"- n_unmatched: {join_result.n_unmatched}\n")
    lines.append(f"- join_coverage: {join_result.join_coverage*100:.2f}%\n")
    lines.append(f"- n_duplicate_game_ids: {join_result.n_duplicate_game_ids}\n")
    if join_result.risk_notes:
        lines.append("\n## Risk Notes\n")
        for note in join_result.risk_notes:
            lines.append(f"- {note}\n")
    return "".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=SCRIPT_VERSION)
    parser.add_argument("--p15-ledger", required=True)
    parser.add_argument("--p15-joined", required=True)
    parser.add_argument("--p16-6-recommendation-rows", required=True)
    parser.add_argument("--p17-ledger", required=False, default="")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--paper-only", default="true")

    args = parser.parse_args()

    print(f"[P19] Script: {SCRIPT_VERSION}")

    # Safety guard
    if args.paper_only.lower() != "true":
        print("[P19] FATAL: --paper-only must be 'true'. This script is PAPER_ONLY.", file=sys.stderr)
        return 2

    print("[P19] PAPER_ONLY=True, PRODUCTION_READY=False")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Load inputs ──────────────────────────────────────────────────────────
    paths = {
        "simulation_ledger": args.p15_ledger,
        "joined_oof": args.p15_joined,
        "recommendation_rows": args.p16_6_recommendation_rows,
    }
    if args.p17_ledger:
        paths["p17_ledger"] = args.p17_ledger

    for name, path in paths.items():
        if not Path(path).exists():
            print(f"[P19] FATAL: Missing input: {path}", file=sys.stderr)
            gate_result = {
                "gate_decision": P19_FAIL_INPUT_MISSING,
                "paper_only": True,
                "production_ready": False,
                "error_message": f"Missing input file: {path}",
                "script_version": SCRIPT_VERSION,
                "generated_at": _now(),
            }
            _write_json(output_dir / "p19_gate_result.json", gate_result)
            return 2

    sim_df = pd.read_csv(args.p15_ledger)
    jof_df = pd.read_csv(args.p15_joined)
    rec_df = pd.read_csv(args.p16_6_recommendation_rows)

    print(f"[P19] Loaded {len(sim_df)} simulation_ledger rows")
    print(f"[P19] Loaded {len(jof_df)} joined_oof_with_odds rows")
    print(f"[P19] Loaded {len(rec_df)} recommendation rows")

    # ── Task 2: Identity field audit ─────────────────────────────────────────
    print("[P19] Running identity field audit …")
    audit = audit_identity_columns(paths)

    print(f"[P19] Files with game_id: {audit.files_with_game_id}")
    print(f"[P19] Files without game_id: {audit.files_without_game_id}")
    print(f"[P19] Enrichment feasible: {audit.enrichment_feasible}")
    if audit.enrichment_blocker:
        print(f"[P19] Enrichment blocker: {audit.enrichment_blocker}")

    # Write identity_field_audit.json
    audit_json: dict = {
        "files_checked": audit.files_checked,
        "files_with_game_id": audit.files_with_game_id,
        "files_without_game_id": audit.files_without_game_id,
        "enrichment_feasible": audit.enrichment_feasible,
        "enrichment_blocker": audit.enrichment_blocker,
        "coverage_reports": [
            {
                "column": cr.column,
                "n_total": cr.n_total,
                "n_non_null": cr.n_non_null,
                "coverage": cr.coverage,
                "quality": cr.quality,
                "unique_count": cr.unique_count,
            }
            for cr in audit.coverage_reports
        ],
        "alignment": {
            "sort_key_used": audit.comparison.sort_key_used if audit.comparison else None,
            "ytrue_match": audit.comparison.ytrue_match if audit.comparison else None,
            "fold_id_match": audit.comparison.fold_id_match if audit.comparison else None,
            "p_model_max_diff": audit.comparison.p_model_max_diff if audit.comparison else None,
            "p_market_max_diff": audit.comparison.p_market_max_diff if audit.comparison else None,
            "alignment_safe": audit.comparison.alignment_safe if audit.comparison else None,
            "alignment_reason": audit.comparison.alignment_reason if audit.comparison else None,
        } if audit.comparison else None,
        "paper_only": True,
        "production_ready": False,
        "generated_at": _now(),
    }
    _write_json(output_dir / "identity_field_audit.json", audit_json)
    _write_md(
        output_dir / "identity_field_audit.md",
        _identity_field_audit_md(audit, paths),
    )
    print(f"[P19] Wrote {output_dir}/identity_field_audit.json")

    # Determine gate if enrichment is not feasible
    if not audit.enrichment_feasible:
        blocker = audit.enrichment_blocker or ""
        if "unsafe" in blocker.lower() or "mismatch" in blocker.lower():
            gate = P19_BLOCKED_UNSAFE_POSITIONAL_ALIGNMENT
        elif "missing" in blocker.lower():
            gate = P19_BLOCKED_MISSING_GAME_ID_SOURCE
        elif "duplicate" in blocker.lower():
            gate = P19_BLOCKED_DUPLICATE_GAME_ID
        else:
            gate = P19_BLOCKED_MISSING_GAME_ID_SOURCE

        gate_result = {
            "gate_decision": gate,
            "paper_only": True,
            "production_ready": False,
            "error_message": blocker,
            "script_version": SCRIPT_VERSION,
            "generated_at": _now(),
        }
        _write_json(output_dir / "p19_gate_result.json", gate_result)
        print(f"\n[P19] Overall gate decision: {gate}")
        return 1

    # ── Task 3: Enrich simulation_ledger with identity ───────────────────────
    print("[P19] Enriching simulation_ledger with game_id …")
    enriched_df = enrich_simulation_ledger_with_identity(sim_df, jof_df)
    validation = validate_enriched_ledger(enriched_df)

    method = (
        enriched_df["identity_enrichment_method"].iloc[0]
        if "identity_enrichment_method" in enriched_df.columns and len(enriched_df) > 0
        else "UNKNOWN"
    )
    enrichment_summary = summarize_identity_enrichment(enriched_df)

    n_with_game_id_before = 0  # simulation_ledger has no game_id
    n_with_game_id_after = enrichment_summary["n_with_game_id"]
    game_id_coverage_after = enrichment_summary["game_id_coverage"]

    print(f"[P19] Enrichment method: {method}")
    print(f"[P19] game_id coverage: {n_with_game_id_before} → {n_with_game_id_after} ({game_id_coverage_after*100:.1f}%)")
    print(f"[P19] Contract validation: {'PASS' if validation.valid else 'FAIL'}")

    if not validation.valid:
        gate_result = {
            "gate_decision": P19_BLOCKED_CONTRACT_VIOLATION,
            "paper_only": True,
            "production_ready": False,
            "error_message": validation.error_message,
            "script_version": SCRIPT_VERSION,
            "generated_at": _now(),
        }
        _write_json(output_dir / "p19_gate_result.json", gate_result)
        print(f"\n[P19] Overall gate decision: {P19_BLOCKED_CONTRACT_VIOLATION}")
        return 1

    # Write enriched simulation ledger
    enriched_csv_path = output_dir / "enriched_simulation_ledger.csv"
    enriched_df.to_csv(enriched_csv_path, index=False)
    print(f"[P19] Wrote {enriched_csv_path} ({len(enriched_df)} rows)")

    enrichment_summary["generated_at"] = _now()
    _write_json(output_dir / "identity_enrichment_summary.json", enrichment_summary)
    _write_md(
        output_dir / "identity_enrichment_summary.md",
        _enrichment_summary_md(enrichment_summary, validation.valid),
    )
    print(f"[P19] Wrote {output_dir}/identity_enrichment_summary.json")

    # ── Settlement join repair ────────────────────────────────────────────────
    print("[P19] Running settlement join repair audit …")
    joined_df, join_result = audit_recommendation_to_enriched_p15_join(rec_df, enriched_df)
    rec_summary = summarize_settlement_join_quality(joined_df)

    print(
        f"[P19] Join: {join_result.join_method} | "
        f"coverage={join_result.join_coverage*100:.1f}% | "
        f"quality={join_result.join_quality}"
    )
    for note in join_result.risk_notes:
        print(f"  [RISK] {note}")

    join_audit_dict = {
        "join_method": join_result.join_method,
        "join_quality": join_result.join_quality,
        "n_recommendations": join_result.n_recommendations,
        "n_joined": join_result.n_joined,
        "n_unmatched": join_result.n_unmatched,
        "n_duplicate_game_ids": join_result.n_duplicate_game_ids,
        "join_coverage": join_result.join_coverage,
        "y_true_quality": rec_summary,
        "risk_notes": list(join_result.risk_notes),
        "paper_only": True,
        "production_ready": False,
        "generated_at": _now(),
    }
    _write_json(output_dir / "settlement_join_repair_audit.json", join_audit_dict)
    _write_md(
        output_dir / "settlement_join_repair_audit.md",
        _settlement_join_repair_md(join_result, rec_summary),
    )
    print(f"[P19] Wrote {output_dir}/settlement_join_repair_audit.json")

    # ── Determine final gate ──────────────────────────────────────────────────
    # Ready criteria: game_id coverage >= 99%, join quality HIGH
    game_id_coverage_pct = game_id_coverage_after
    y_true_coverage = rec_summary.get("y_true_coverage", 0.0)

    if game_id_coverage_pct >= 0.99 and join_result.join_quality == "HIGH":
        gate = P19_IDENTITY_JOIN_REPAIR_READY
    elif method in {IDENTITY_BLOCKED_UNSAFE_ALIGNMENT}:
        gate = P19_BLOCKED_UNSAFE_POSITIONAL_ALIGNMENT
    elif method in {IDENTITY_BLOCKED_MISSING_GAME_ID_SOURCE}:
        gate = P19_BLOCKED_MISSING_GAME_ID_SOURCE
    elif method in {IDENTITY_BLOCKED_DUPLICATE_GAME_ID}:
        gate = P19_BLOCKED_DUPLICATE_GAME_ID
    else:
        gate = P19_BLOCKED_MISSING_GAME_ID_SOURCE

    gate_result = {
        "gate_decision": gate,
        "paper_only": True,
        "production_ready": False,
        "enrichment_method": method,
        "game_id_coverage_before": 0.0,
        "game_id_coverage_after": game_id_coverage_pct,
        "join_method": join_result.join_method,
        "join_quality": join_result.join_quality,
        "join_coverage": join_result.join_coverage,
        "n_active_recommendations": int(
            rec_df[rec_df.get("gate_decision", pd.Series()) == "P16_6_ELIGIBLE_PAPER_RECOMMENDATION"].shape[0]
            if "gate_decision" in rec_df.columns else 0
        ),
        "script_version": SCRIPT_VERSION,
        "generated_at": _now(),
    }
    _write_json(output_dir / "p19_gate_result.json", gate_result)
    print(f"\n[P19] Overall gate decision: {gate}")

    return 0 if gate == P19_IDENTITY_JOIN_REPAIR_READY else 1


if __name__ == "__main__":
    sys.exit(main())
