#!/usr/bin/env python3
"""
P32 Raw Game Log Builder — CLI Entry Point.

Builds the 2024 raw game log artifact layer from Retrosheet game logs.
This is a PAPER_ONLY build — no odds, no predictions, no production write.

Usage:
  .venv/bin/python scripts/run_p32_build_2024_raw_game_logs.py \
    --source-path data/mlb_2024/raw/gl2024.txt \
    --output-dir data/mlb_2024/processed \
    --season 2024 \
    --paper-only true

Exit codes:
  0 = P32_RAW_GAME_LOG_ARTIFACT_READY
  1 = BLOCKED_* (source missing, schema invalid, etc.)
  2 = FAIL_* (unexpected error)

PAPER_ONLY=True
production_ready=False
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

sys.path.insert(0, str(REPO_ROOT))

from wbc_backend.recommendation.p32_raw_game_log_contract import (
    PAPER_ONLY,
    PRODUCTION_READY,
    P32RawGameLogBuildSummary,
    P32RawGameLogGateResult,
    P32RawGameLogSource,
    P32_RAW_GAME_LOG_ARTIFACT_READY,
    P32_BLOCKED_SOURCE_FILE_MISSING,
    P32_BLOCKED_SCHEMA_INVALID,
    P32_BLOCKED_NO_2024_GAMES,
    P32_BLOCKED_PROVENANCE_UNSAFE,
    P32_FAIL_INPUT_MISSING,
    P32_FAIL_NON_DETERMINISTIC,
)
from wbc_backend.recommendation.p32_retrosheet_game_log_parser import (
    load_retrosheet_game_log,
    parse_retrosheet_game_log_rows,
    filter_to_season,
    compute_outcome_coverage,
    validate_retrosheet_schema,
)
from wbc_backend.recommendation.p32_raw_game_artifact_writer import (
    write_raw_game_identity_artifact,
    write_raw_game_outcome_artifact,
    write_raw_game_joined_artifact,
    write_p32_summary,
    build_artifact_manifest,
)
from wbc_backend.recommendation.p32_provenance_attribution import (
    build_retrosheet_provenance_record,
    validate_retrosheet_attribution,
    write_provenance_record,
    summarize_provenance,
)

logging.basicConfig(level=logging.INFO, format="[P32] %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Report path (always written, even on blocker)
REPORT_PATH = REPO_ROOT / "00-BettingPlan" / "20260513" / "p32_raw_game_log_artifact_report.md"


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="P32 2024 Raw Game Log Artifact Builder (PAPER_ONLY)"
    )
    parser.add_argument(
        "--source-path",
        default="data/mlb_2024/raw/gl2024.txt",
        help="Path to Retrosheet gl2024.txt (absolute or relative to repo root).",
    )
    parser.add_argument(
        "--output-dir",
        default="data/mlb_2024/processed",
        help="Directory for processed output artifacts.",
    )
    parser.add_argument(
        "--season", type=int, default=2024, help="Season year (must be 2024)."
    )
    parser.add_argument(
        "--paper-only",
        default="true",
        help="Must be 'true' (PAPER_ONLY build only).",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------


def _build_report(
    gate: str,
    source_path: Path,
    output_dir: Path,
    summary: P32RawGameLogBuildSummary | None,
    provenance_summary: str,
    gate_result: P32RawGameLogGateResult,
    artifacts: list[str],
    blocker_reason: str,
    test_note: str = "",
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: list[str] = []

    lines.append("# P32 Raw Game Log Artifact Report")
    lines.append(f"\n**Date**: {now}")
    lines.append("**Phase**: P32 — 2024 Raw Game Log Artifact Layer (PAPER_ONLY)")
    lines.append(f"**PAPER_ONLY**: {PAPER_ONLY}")
    lines.append(f"**production_ready**: {PRODUCTION_READY}")
    lines.append("\n---")

    # 1. Repo evidence
    lines.append("\n## 1. Repo Evidence")
    lines.append("- Repo: `/Users/kelvin/Kelvin-WorkSpace/Betting-pool-p13`")
    lines.append("- Branch: `p13-clean`")
    lines.append("- P31 commit: `6b0ab64`")
    lines.append("- P31 gate: `P31_HONEST_DATA_AUDIT_READY`")

    # 2. P31 prior evidence
    lines.append("\n## 2. Prior Phase Evidence (P31)")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    lines.append("| Total classified sources | 1,397 |")
    lines.append("| RAW_PRIMARY | 1 (2025 only) |")
    lines.append("| RAW_SECONDARY | 0 |")
    lines.append("| DERIVED_OUTPUT | 1,372 |")
    lines.append("| SCHEMA_PARTIAL | 24 |")
    lines.append("| usable_2024_raw | 0 |")
    lines.append("| P32 recommendation | GO_PARTIAL_GAME_LOGS_ONLY |")

    # 3. Why partial
    lines.append("\n## 3. Why P32 Is Partial Only")
    lines.append(
        "P31 confirmed that 2024 closing moneyline odds have no confirmed license-safe "
        "provider. P32 therefore builds ONLY the game identity/outcome artifact from "
        "Retrosheet game logs. **No odds artifact is built. No prediction artifact is built.**"
    )

    # 4. Source availability
    lines.append("\n## 4. Source File Availability")
    lines.append(f"- Source path: `{source_path}`")
    if source_path.exists():
        stat = source_path.stat()
        lines.append(f"- Status: **AVAILABLE** ({stat.st_size:,} bytes)")
    else:
        lines.append("- Status: **MISSING**")
        lines.append(
            "\n> **Manual action required**: Download Retrosheet 2024 game logs from "
            "https://www.retrosheet.org/gamelogs/index.html and place the file at "
            f"`{source_path}`. Attribution is required per Retrosheet license."
        )

    # 5. Schema parser design
    lines.append("\n## 5. Retrosheet Schema Parser Design")
    lines.append("- File format: CSV with no header, 161+ positional columns.")
    lines.append("- Column 0: date (YYYYMMDD)")
    lines.append("- Column 1: game number in doubleheader (0/1/2)")
    lines.append("- Column 3: visiting (away) team 3-letter ID")
    lines.append("- Column 6: home team 3-letter ID")
    lines.append("- Column 9: visiting score")
    lines.append("- Column 10: home score")
    lines.append("- game_id: `<HOME>-<YYYYMMDD>-<game_number>` (deterministic)")
    lines.append("- y_true_home_win: 1 if home_score > away_score, 0 if away wins, None if tied/missing.")
    lines.append("- Missing scores → None (not fabricated).")

    # 6. Processed artifacts or blocker
    lines.append("\n## 6. Processed Artifact Outputs")
    if gate == P32_RAW_GAME_LOG_ARTIFACT_READY and summary is not None:
        lines.append(f"| Metric | Value |")
        lines.append(f"| --- | --- |")
        lines.append(f"| row_count_raw | {summary.row_count_raw:,} |")
        lines.append(f"| row_count_processed | {summary.row_count_processed:,} |")
        lines.append(f"| unique_game_id_count | {summary.unique_game_id_count:,} |")
        lines.append(f"| date_start | {summary.date_start} |")
        lines.append(f"| date_end | {summary.date_end} |")
        lines.append(f"| teams_detected_count | {summary.teams_detected_count} |")
        lines.append(f"| outcome_coverage_pct | {summary.outcome_coverage_pct:.2%} |")
        lines.append(f"| contains_odds | {summary.contains_odds} |")
        lines.append(f"| contains_predictions | {summary.contains_predictions} |")
        lines.append("\nArtifacts written:")
        for a in artifacts:
            lines.append(f"  - `{a}`")
    else:
        lines.append(f"**BLOCKER**: {gate}")
        if blocker_reason:
            lines.append(f"\nReason: {blocker_reason}")
        lines.append(
            "\nNo processed artifacts written. "
            "Re-run after resolving the blocker."
        )

    # 7. Provenance / attribution
    lines.append("\n## 7. Provenance / Attribution")
    lines.append("```")
    lines.append(provenance_summary.rstrip())
    lines.append("```")
    lines.append(
        "\n**Attribution text** (Retrosheet requirement):\n"
        "> The information used here was obtained free of charge from and is "
        "copyrighted by Retrosheet. Interested parties may contact Retrosheet at "
        "www.retrosheet.org."
    )

    # 8. Test results (placeholder — populated by test run)
    lines.append("\n## 8. Test Results")
    if test_note:
        lines.append(test_note)
    else:
        lines.append("Run: `./.venv/bin/pytest tests/test_p32_*.py -q`")

    # 9. Determinism
    lines.append("\n## 9. Determinism Result")
    if gate == P32_RAW_GAME_LOG_ARTIFACT_READY:
        lines.append(
            "Determinism: EXPECTED PASS — game_id is built from deterministic "
            "fields (home_team + date + game_number). CSV output is row-stable "
            "given the same source file."
        )
    else:
        lines.append(
            "Determinism: BLOCKER DETERMINISTIC — the `P32_BLOCKED_SOURCE_FILE_MISSING` "
            "gate is always emitted when the source file is absent. "
            "Blocker output is reproducible."
        )

    # 10. Production readiness
    lines.append("\n## 10. Production Readiness Statement")
    lines.append(f"| Control | Value |")
    lines.append(f"| --- | --- |")
    lines.append(f"| PAPER_ONLY | {PAPER_ONLY} |")
    lines.append(f"| production_ready | {PRODUCTION_READY} |")
    lines.append(f"| Live TSL called | False |")
    lines.append(f"| Real bets placed | False |")
    lines.append(f"| Odds artifact built | False |")
    lines.append(f"| Prediction artifact built | False |")
    lines.append(f"| Scheduler/daemon enabled | False |")

    # 11. Remaining limitations
    lines.append("\n## 11. Remaining Limitations")
    lines.append(
        "- **No 2024 closing odds**: Moneyline model training blocked until a "
        "license-safe odds source is confirmed.\n"
        "- **Sample wall not solved**: Raw game logs increase game-identity coverage "
        "but full model training rows require joined odds data.\n"
        "- **gl2024.txt requires manual download**: Source file not in repo. "
        "Must be obtained from Retrosheet.org with attribution.\n"
        "- **Retrosheet game logs exclude odds and starter stats by default**: "
        "Additional join with pitcher data (MLB Stats API) needed for full feature set."
    )

    # 12. Next phase
    lines.append("\n## 12. Next-Phase Recommendation")
    if gate == P32_RAW_GAME_LOG_ARTIFACT_READY:
        lines.append(
            "**Next recommended phase**: P33 — 2024 Prediction / Odds Source Gap Builder.\n"
            "- Confirm license-safe odds provider (The Odds API paid tier or approved alternative).\n"
            "- Join gl2024 game logs with closing moneyline odds.\n"
            "- Validate complete training row schema."
        )
    else:
        lines.append(
            "**Next recommended phase**: Manually provision Retrosheet gl2024.txt, then rerun P32.\n"
            f"  - Download from: {source_path}\n"
            f"    https://www.retrosheet.org/gamelogs/index.html\n"
            "  - Place at: `data/mlb_2024/raw/gl2024.txt`\n"
            "  - Attribution required (Retrosheet license).\n"
            "  - Rerun: `./.venv/bin/python scripts/run_p32_build_2024_raw_game_logs.py`"
        )

    # 13. Marker
    lines.append("\n---\n")
    if gate == P32_RAW_GAME_LOG_ARTIFACT_READY:
        lines.append("```")
        lines.append("P32_RAW_GAME_LOG_ARTIFACT_READY")
        lines.append("```")
        lines.append("\nP32_RAW_GAME_LOG_ARTIFACT_READY")
    else:
        lines.append("```")
        lines.append("P32_RAW_GAME_LOG_ARTIFACT_BLOCKED_SOURCE_MISSING")
        lines.append("```")
        lines.append("\nP32_RAW_GAME_LOG_ARTIFACT_BLOCKED_SOURCE_MISSING")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    args = _parse_args()

    # Validate paper-only argument
    if args.paper_only.lower() != "true":
        print("[P32] ERROR: --paper-only must be 'true'. This is a PAPER_ONLY build.")
        return 2

    if args.season != 2024:
        print(f"[P32] ERROR: --season must be 2024, got {args.season}.")
        return 2

    print(f"[P32] PAPER_ONLY={PAPER_ONLY}  production_ready={PRODUCTION_READY}")
    print(f"[P32] season={args.season}")

    # Resolve paths relative to repo root
    source_path = Path(args.source_path)
    if not source_path.is_absolute():
        source_path = REPO_ROOT / source_path
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = REPO_ROOT / output_dir

    print(f"[P32] source_path={source_path}")
    print(f"[P32] output_dir={output_dir}")

    # Always build provenance record (works even if file is missing)
    prov_record = build_retrosheet_provenance_record(source_path)
    prov_summary = summarize_provenance(prov_record)
    print(prov_summary)

    gate_result_kwargs = dict(
        gate="",
        season=args.season,
        source_path=str(source_path),
        row_count_raw=0,
        row_count_processed=0,
        unique_game_id_count=0,
        date_start="",
        date_end="",
        outcome_coverage_pct=0.0,
        provenance_status=prov_record.license_status,
        license_status=prov_record.license_status,
        paper_only=PAPER_ONLY,
        production_ready=PRODUCTION_READY,
    )

    summary: P32RawGameLogBuildSummary | None = None
    artifacts: list[str] = []
    blocker_reason = ""
    gate = ""

    # --- CHECK SOURCE EXISTS ---
    if not source_path.exists():
        blocker_reason = (
            f"Source file not found: {source_path}. "
            "Manually download from https://www.retrosheet.org/gamelogs/index.html "
            "and place at data/mlb_2024/raw/gl2024.txt."
        )
        gate = P32_BLOCKED_SOURCE_FILE_MISSING
        print(f"[P32] BLOCKED: {gate}")
        print(f"[P32] {blocker_reason}")

        gate_result_kwargs["gate"] = gate
        gate_result_kwargs["blocker_reason"] = blocker_reason
        gate_result = P32RawGameLogGateResult(**gate_result_kwargs)

    else:
        # --- PARSE AND PROCESS ---
        try:
            print("[P32] Loading source file...")
            raw_df = load_retrosheet_game_log(source_path)
            row_count_raw = len(raw_df)
            print(f"[P32] raw rows: {row_count_raw}")

            valid, schema_reason = validate_retrosheet_schema(raw_df)
            if not valid:
                gate = P32_BLOCKED_SCHEMA_INVALID
                blocker_reason = schema_reason
                raise ValueError(f"{gate}: {schema_reason}")

            print("[P32] Parsing rows...")
            parsed_df = parse_retrosheet_game_log_rows(raw_df)
            filtered_df = filter_to_season(parsed_df, args.season)

            if len(filtered_df) == 0:
                gate = P32_BLOCKED_NO_2024_GAMES
                blocker_reason = f"No rows for season={args.season} found in source."
                raise ValueError(f"{gate}: {blocker_reason}")

            row_count_processed = len(filtered_df)
            unique_game_ids = filtered_df["game_id"].nunique()
            date_start = str(filtered_df["game_date"].min())
            date_end = str(filtered_df["game_date"].max())
            teams = filtered_df["away_team"].nunique() + filtered_df["home_team"].nunique()
            outcome_cov = compute_outcome_coverage(filtered_df)

            print(f"[P32] row_count_raw={row_count_raw}")
            print(f"[P32] row_count_processed={row_count_processed}")
            print(f"[P32] unique_game_id_count={unique_game_ids}")
            print(f"[P32] date_start={date_start}  date_end={date_end}")
            print(f"[P32] outcome_coverage_pct={outcome_cov:.2%}")

            summary = P32RawGameLogBuildSummary(
                season=args.season,
                source_name="Retrosheet",
                source_path=str(source_path),
                row_count_raw=row_count_raw,
                row_count_processed=row_count_processed,
                unique_game_id_count=unique_game_ids,
                date_start=date_start,
                date_end=date_end,
                teams_detected_count=teams,
                outcome_coverage_pct=outcome_cov,
                schema_valid=True,
                blocker="",
                paper_only=PAPER_ONLY,
                production_ready=PRODUCTION_READY,
                contains_odds=False,
                contains_predictions=False,
            )

            # Write artifacts
            output_dir.mkdir(parents=True, exist_ok=True)
            a1 = write_raw_game_identity_artifact(filtered_df, output_dir)
            a2 = write_raw_game_outcome_artifact(filtered_df, output_dir)
            a3 = write_raw_game_joined_artifact(filtered_df, output_dir)
            a4 = write_p32_summary(summary, output_dir)
            a5 = write_provenance_record(prov_record, output_dir)

            # Write gate result JSON
            gate = P32_RAW_GAME_LOG_ARTIFACT_READY
            gate_result_kwargs.update(
                gate=gate,
                row_count_raw=row_count_raw,
                row_count_processed=row_count_processed,
                unique_game_id_count=unique_game_ids,
                date_start=date_start,
                date_end=date_end,
                outcome_coverage_pct=outcome_cov,
                artifacts=[str(a) for a in [a1, a2, a3, a4, a5]],
            )
            gate_result = P32RawGameLogGateResult(**gate_result_kwargs)
            artifacts = [str(a) for a in [a1, a2, a3, a4, a5]]

            # Manifest (after all files written)
            a6 = build_artifact_manifest(output_dir)
            artifacts.append(str(a6))

        except Exception as exc:
            if not gate:
                gate = P32_BLOCKED_SCHEMA_INVALID if "schema" in str(exc).lower() else "P32_FAIL_NON_DETERMINISTIC"
            blocker_reason = str(exc)
            print(f"[P32] ERROR: {exc}")
            traceback.print_exc()
            gate_result_kwargs["gate"] = gate
            gate_result_kwargs["blocker_reason"] = blocker_reason
            gate_result = P32RawGameLogGateResult(**gate_result_kwargs)

    # Write gate result JSON (always)
    output_dir.mkdir(parents=True, exist_ok=True)
    gate_json_path = output_dir / "p32_gate_result.json"
    gate_json_path.write_text(
        json.dumps(gate_result.to_dict(), indent=2), encoding="utf-8"
    )
    artifacts.append(str(gate_json_path))
    print(f"[P32] Wrote gate result: {gate_json_path}")

    # Write report (always)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report_text = _build_report(
        gate=gate,
        source_path=source_path,
        output_dir=output_dir,
        summary=summary,
        provenance_summary=prov_summary,
        gate_result=gate_result,
        artifacts=artifacts,
        blocker_reason=blocker_reason,
    )
    REPORT_PATH.write_text(report_text, encoding="utf-8")
    print(f"[P32] Wrote report: {REPORT_PATH}")

    # Final summary
    print(f"\n[P32] ===== BUILD COMPLETE =====")
    print(f"[P32] gate={gate}")
    print(f"[P32] season={args.season}")
    print(f"[P32] source_file_exists={source_path.exists()}")
    print(f"[P32] PAPER_ONLY={PAPER_ONLY}  production_ready={PRODUCTION_READY}")
    print(f"[P32] NOT PUSHED.")

    # Exit code
    if gate == P32_RAW_GAME_LOG_ARTIFACT_READY:
        return 0
    elif gate.startswith("P32_BLOCKED_"):
        return 1
    else:
        return 2


if __name__ == "__main__":
    sys.exit(main())
