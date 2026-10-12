#!/usr/bin/env python3
"""
scripts/run_p20_daily_paper_mlb_orchestrator.py

P20 Daily PAPER MLB Recommendation Orchestrator CLI.

Chains: P16.6 → P19 → P17-replay outputs into a single daily summary artifact.

Exit codes:
  0 — P20_DAILY_PAPER_ORCHESTRATOR_READY
  1 — Blocked (gate not ready or contract violation)
  2 — Fatal error (missing input, unexpected exception)

PAPER_ONLY — no production systems, no real bets.

Usage:
    python scripts/run_p20_daily_paper_mlb_orchestrator.py \\
        --run-date 2026-05-12 \\
        --p16-6-dir outputs/predictions/PAPER/2026-05-12/p16_6_recommendation_gate_p18_policy \\
        --p19-dir outputs/predictions/PAPER/2026-05-12/p19_odds_identity_join_repair \\
        --p17-replay-dir outputs/predictions/PAPER/2026-05-12/p17_replay_with_p19_identity \\
        --output-dir outputs/predictions/PAPER/2026-05-12/p20_daily_paper_orchestrator \\
        --paper-only true
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

# Ensure the repo root is importable regardless of cwd
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from wbc_backend.recommendation.p20_artifact_manifest import (
    build_artifact_manifest,
    summarize_manifest,
    validate_manifest,
)
from wbc_backend.recommendation.p20_daily_paper_orchestrator_contract import (
    P20_DAILY_PAPER_ORCHESTRATOR_READY,
)
from wbc_backend.recommendation.p20_daily_summary_aggregator import (
    aggregate_daily_paper_summary,
    load_phase_outputs,
    validate_daily_summary_contract,
    write_daily_summary_outputs,
)


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in ("true", "1", "yes")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="P20 Daily PAPER MLB Orchestrator",
    )
    parser.add_argument("--run-date", required=True, help="Date string e.g. 2026-05-12")
    parser.add_argument("--p16-6-dir", required=True, help="P16.6 output directory")
    parser.add_argument("--p19-dir", required=True, help="P19 output directory")
    parser.add_argument("--p17-replay-dir", required=True, help="P17 replay output directory")
    parser.add_argument("--output-dir", required=True, help="P20 output directory")
    parser.add_argument(
        "--paper-only",
        default="true",
        help="Must be 'true'. Safety guard (default: true)",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    paper_only = _parse_bool(args.paper_only)
    if not paper_only:
        print("ERROR: --paper-only must be true. PAPER pipeline only.", file=sys.stderr)
        return 2

    print(f"[P20] run_date={args.run_date}")
    print(f"[P20] p16_6_dir={args.p16_6_dir}")
    print(f"[P20] p19_dir={args.p19_dir}")
    print(f"[P20] p17_replay_dir={args.p17_replay_dir}")
    print(f"[P20] output_dir={args.output_dir}")

    # -- Step 1: Build artifact manifest (validates required inputs exist) --
    print("[P20] Step 1: Building artifact manifest...")
    try:
        manifest = build_artifact_manifest(
            run_date=args.run_date,
            p16_6_dir=args.p16_6_dir,
            p19_dir=args.p19_dir,
            p17_replay_dir=args.p17_replay_dir,
            p20_output_dir=args.output_dir,
        )
    except Exception as exc:
        print(f"[P20] FATAL: Failed to build manifest — {exc}", file=sys.stderr)
        traceback.print_exc()
        return 2

    manifest_validation = validate_manifest(manifest)
    if not manifest_validation.valid:
        print(
            f"[P20] BLOCKED: {manifest_validation.error_code} — {manifest_validation.error_message}",
            file=sys.stderr,
        )
        return 1

    print(f"[P20]   Required inputs: {manifest.required_artifacts_present} present, "
          f"{manifest.required_artifacts_missing} missing")

    # -- Step 2: Load phase outputs --
    print("[P20] Step 2: Loading phase outputs...")
    try:
        phase_outputs = load_phase_outputs(
            p16_6_dir=args.p16_6_dir,
            p19_dir=args.p19_dir,
            p17_replay_dir=args.p17_replay_dir,
        )
    except FileNotFoundError as exc:
        print(f"[P20] FATAL: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"[P20] FATAL: Unexpected error loading phase outputs — {exc}", file=sys.stderr)
        traceback.print_exc()
        return 2

    # -- Step 3: Aggregate daily summary --
    print("[P20] Step 3: Aggregating daily paper summary...")
    summary = aggregate_daily_paper_summary(
        run_date=args.run_date,
        phase_outputs=phase_outputs,
        generated_artifact_count=4,  # JSON, MD, manifest, gate
    )

    # -- Step 4: Validate contract --
    print("[P20] Step 4: Validating contract...")
    contract_result = validate_daily_summary_contract(summary)
    if not contract_result.valid:
        print(
            f"[P20] BLOCKED: {contract_result.error_code} — {contract_result.error_message}",
            file=sys.stderr,
        )
        # Still write outputs so the gate result is visible
        manifest_summary = summarize_manifest(manifest)
        write_daily_summary_outputs(summary, manifest_summary, args.output_dir)
        return 1

    # -- Step 5: Write outputs --
    print("[P20] Step 5: Writing output files...")
    manifest_summary = summarize_manifest(manifest)
    written = write_daily_summary_outputs(summary, manifest_summary, args.output_dir)

    # -- Step 6: Rebuild manifest with actual output hashes --
    manifest2 = build_artifact_manifest(
        run_date=args.run_date,
        p16_6_dir=args.p16_6_dir,
        p19_dir=args.p19_dir,
        p17_replay_dir=args.p17_replay_dir,
        p20_output_dir=args.output_dir,
    )
    manifest_summary2 = summarize_manifest(manifest2)
    # Overwrite artifact_manifest.json with final hashes
    import json as _json
    from pathlib import Path as _Path
    out_dir = _Path(args.output_dir)
    with open(out_dir / "artifact_manifest.json", "w", encoding="utf-8") as fh:
        _json.dump(manifest_summary2, fh, indent=2, ensure_ascii=False)

    print(f"[P20] Output files written: {len(written)}")
    for p in written:
        print(f"[P20]   {p}")

    # -- Summary --
    print()
    print(f"[P20] Gate: {summary.p20_gate}")
    print(f"[P20] n_active_paper_entries: {summary.n_active_paper_entries}")
    print(f"[P20] n_settled_win: {summary.n_settled_win}")
    print(f"[P20] n_settled_loss: {summary.n_settled_loss}")
    print(f"[P20] n_unsettled: {summary.n_unsettled}")
    print(f"[P20] roi_units: {summary.roi_units:.6f}")
    print(f"[P20] hit_rate: {summary.hit_rate:.6f}")
    print(f"[P20] settlement_join_method: {summary.settlement_join_method}")
    print(f"[P20] game_id_coverage: {summary.game_id_coverage:.4f}")
    print()

    if summary.p20_gate == P20_DAILY_PAPER_ORCHESTRATOR_READY:
        print(f"[P20] SUCCESS: {P20_DAILY_PAPER_ORCHESTRATOR_READY}")
        return 0
    else:
        print(f"[P20] BLOCKED: {summary.p20_gate}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
