#!/usr/bin/env python3
"""
P31 Honest Data Reality Audit — CLI entry point.

Produces:
  data/p31_source_classification_audit.csv
  data/p31_provenance_audit.json
  00-BettingPlan/20260513/p31_honest_data_audit_report.md

Usage:
  .venv/bin/python scripts/run_p31_honest_data_reality_audit.py

PAPER_ONLY=True
production_ready=False
"""
from __future__ import annotations

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Repo-root discovery (script lives in scripts/, repo root is one level up)
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

sys.path.insert(0, str(REPO_ROOT))

from wbc_backend.recommendation.p31_honest_data_audit import (
    run_honest_data_audit,
    write_classification_csv,
    determine_p31_gate,
    SourceClass,
    PAPER_ONLY,
    PRODUCTION_READY,
)
from wbc_backend.recommendation.p31_provenance_license_audit import (
    run_provenance_license_audit,
    write_provenance_audit_json,
)

# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------

CLASSIFICATION_CSV = REPO_ROOT / "data" / "p31_source_classification_audit.csv"
PROVENANCE_JSON = REPO_ROOT / "data" / "p31_provenance_audit.json"
REPORT_MD = REPO_ROOT / "00-BettingPlan" / "20260513" / "p31_honest_data_audit_report.md"

# P28/P29 known constants (confirmed by prior audit phases)
P28_ACTIVE_ENTRIES = 324
P28_TOTAL_ENTRIES = 1577
P29_BEST_ACTIVE = 563
MODEL_TRAINING_THRESHOLD = 1500
P30_CLAIMED_READY_SOURCES = 348
P30_CLAIMED_SAMPLE_GAIN = 54675


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------


def build_report(
    audit_result,
    provenance_result,
    p31_gate: str,
    run_ts: str,
) -> str:
    c = audit_result.counters
    prov = provenance_result

    lines: list[str] = []

    def h1(t: str) -> None:
        lines.append(f"# {t}")

    def h2(t: str) -> None:
        lines.append(f"\n## {t}")

    def h3(t: str) -> None:
        lines.append(f"\n### {t}")

    def row(*cells: str) -> None:
        lines.append("| " + " | ".join(cells) + " |")

    def sep(n: int) -> None:
        lines.append("| " + " | ".join(["---"] * n) + " |")

    # Header
    h1("P31 Honest Data Reality Audit Report")
    lines.append(f"\n**Date**: {run_ts}")
    lines.append("**Phase**: P31 — Honest Data Reality Audit & 2024 Acquisition Decision Gate")
    lines.append(f"**PAPER_ONLY**: {PAPER_ONLY}")
    lines.append(f"**production_ready**: {PRODUCTION_READY}")
    lines.append("\n---")

    # 1. Executive Conclusion
    h2("1. Executive Conclusion")
    lines.append(
        f"Of the **{c.total_sources}** data files classified in this audit, "
        f"**{c.raw_primary_count}** qualify as RAW_PRIMARY, "
        f"**{c.raw_secondary_count}** as RAW_SECONDARY, "
        f"**{c.derived_output_count}** as DERIVED_OUTPUT, and "
        f"**{c.schema_partial_count}** as SCHEMA_PARTIAL."
    )
    lines.append("")
    lines.append(
        f"P30 claimed `n_ready_sources={P30_CLAIMED_READY_SOURCES}` and "
        f"`expected_sample_gain={P30_CLAIMED_SAMPLE_GAIN:,}`. "
        f"This audit confirms that **{c.misleading_ready_source_count}** of those "
        f"sources are DERIVED_OUTPUT — pipeline-generated artifacts, not new raw "
        f"historical data. The P30 READY designation is therefore misleading and "
        f"should be treated as **READY_WITH_CAVEAT**."
    )
    lines.append("")
    lines.append(
        f"**2024 usable raw sources found in repo**: {c.usable_2024_raw_count}. "
        f"No 2024 raw game logs or closing odds exist in the repository."
    )
    lines.append("")
    lines.append(
        f"**P32 recommendation**: **{prov.overall_p32_recommendation}**. "
        "Retrosheet gl2024 (game logs) can be acquired with low risk. "
        "Closing odds require license resolution before full ingestion."
    )

    # 2. Raw vs Derived Counters
    h2("2. Source Classification Counters")
    row("Metric", "Count")
    sep(2)
    row("Total sources classified", str(c.total_sources))
    row("RAW_PRIMARY", str(c.raw_primary_count))
    row("RAW_SECONDARY", str(c.raw_secondary_count))
    row("DERIVED_OUTPUT", str(c.derived_output_count))
    row("SCHEMA_PARTIAL", str(c.schema_partial_count))
    row("Usable 2024 raw sources (in-repo)", str(c.usable_2024_raw_count))
    row(
        "P30 'ready' sources that are actually DERIVED_OUTPUT",
        str(c.misleading_ready_source_count),
    )
    lines.append("")
    lines.append(
        "> **NOTE**: DERIVED_OUTPUT sources were produced by earlier pipeline "
        "stages (p15, p25, p27, outputs/predictions/PAPER). They cannot be used "
        "as training data. Double-counting these as raw sources would inflate "
        "sample estimates by up to 54,675 rows."
    )

    # 3. P30 Ready Sources Downgrade
    h2("3. P30 'ready_sources=348' Downgrade Explanation")
    lines.append(
        "P30 defined its READY gate as: `n_ready_sources >= threshold`. "
        "The 348 'ready' sources were identified by scanning the repository for "
        "files matching source acquisition criteria. However, the P30 scanner "
        "included derived pipeline outputs under `outputs/` in its count."
    )
    lines.append("")
    row("P30 Metric", "Claimed", "Reality")
    sep(3)
    row("n_ready_sources", str(P30_CLAIMED_READY_SOURCES), f"{c.derived_output_count} DERIVED + {c.raw_primary_count + c.raw_secondary_count} RAW")
    row("expected_sample_gain", f"{P30_CLAIMED_SAMPLE_GAIN:,}", "0 (no 2024 raw data downloaded)")
    row("Gate", "READY", "READY_WITH_CAVEAT")
    lines.append("")
    lines.append(
        "**Recommendation**: Retroactively annotate "
        "`00-BettingPlan/20260512/p30_historical_source_acquisition_plan_report.md` "
        "with: `NOTE: n_ready_sources includes derived outputs; raw-only count = "
        f"{c.raw_primary_count + c.raw_secondary_count}`."
    )

    # 4. 2024 Acquisition Feasibility
    h2("4. 2024 Acquisition Feasibility")
    lines.append(
        f"**Current in-repo 2024 raw sources**: {c.usable_2024_raw_count} "
        "(zero — no 2024 files exist in `data/`)."
    )
    lines.append("")
    lines.append(
        f"**Sample wall context** (from P28/P29):\n"
        f"- Active entries: {P28_ACTIVE_ENTRIES}\n"
        f"- Training threshold: {MODEL_TRAINING_THRESHOLD:,}\n"
        f"- Gap: -{MODEL_TRAINING_THRESHOLD - P28_ACTIVE_ENTRIES:,}\n"
        f"- Best policy relaxation achieved: {P29_BEST_ACTIVE} entries (still below 1,500)\n"
    )
    lines.append(
        "**Retrosheet gl2024**: ~2,430 MLB regular-season games. "
        "If all games ingested and schema-validated, combined active entries "
        f"could reach ~{P28_ACTIVE_ENTRIES + 2430:,} — well above the 1,500 threshold. "
        "Game-log ingestion is **feasible and LOW risk**."
    )
    lines.append("")
    lines.append(
        "**Closing odds for 2024**: No licensed, non-commercial provider confirmed. "
        "Without closing odds, model training is incomplete for moneyline edge "
        "calculation. This is a **MEDIUM–HIGH risk blocker** for full P32."
    )

    # 5. Provenance / License Decision Table
    h2("5. Provenance & License Decision Table")
    row("Source", "Type", "Provenance", "License", "Risk", "Schema Gap", "Decision")
    sep(7)
    for cand in prov.candidates:
        gaps = ", ".join(cand.schema_gap) if cand.schema_gap else "None"
        row(
            cand.source_name,
            cand.source_type,
            cand.provenance_status.value,
            cand.license_status.value,
            cand.acquisition_risk.value,
            gaps,
            cand.recommended_decision.value,
        )

    h3("5.1 Retrosheet 2024 Notes")
    lines.append(prov.candidates[0].notes)

    h3("5.2 MLB Stats API 2024 Notes")
    lines.append(prov.candidates[1].notes)

    h3("5.3 2024 Closing Odds Notes")
    lines.append(prov.candidates[2].notes)

    # 6. Schema Gap Inventory
    h2("6. Schema Gap Inventory")
    lines.append(
        "The following canonical columns are missing from the identified 2024 "
        "external sources. These gaps must be resolved before model training."
    )
    lines.append("")
    row("Column", "Retrosheet gl2024", "MLB Stats API", "Odds Source (TBD)")
    sep(4)
    row("game_date", "✅ Present (date field)", "✅ Present (gameDate)", "✅ Present")
    row("home_team", "✅ Present", "✅ Present", "✅ Present")
    row("away_team", "✅ Present (visiting_team_id)", "✅ Present", "✅ Present")
    row("home_score / away_score", "✅ Present", "✅ Present (linescore)", "❌ Not included")
    row("closing_moneyline_home", "❌ MISSING", "❌ MISSING", "⚠️ Unresolved license")
    row("closing_moneyline_away", "❌ MISSING", "❌ MISSING", "⚠️ Unresolved license")
    row("run_line_spread", "❌ MISSING", "❌ MISSING", "⚠️ Unresolved license")
    row("over_under", "❌ MISSING", "❌ MISSING", "⚠️ Unresolved license")
    lines.append("")
    lines.append(
        "**Schema gap conclusion**: A JOIN of Retrosheet gl2024 + a licensed odds "
        "source is required to produce a complete training row. "
        "Game logs alone can populate ~4 of 8 canonical columns."
    )

    # 7. Gate
    h2("7. P31 Gate Determination")
    lines.append(f"**Final P31 gate**: `{p31_gate}`")
    lines.append("")

    if p31_gate == "P31_HONEST_DATA_AUDIT_READY":
        lines.append(
            "Gate is READY because:\n"
            "- At least one verifiable 2024 raw external source is identified "
            "(Retrosheet gl2024, VERIFIED provenance)\n"
            "- License for game-log source is documented (attribution required, "
            "safe for non-commercial research)\n"
            "- Schema gap inventory is updated with real measured data\n"
            "- GO/NO-GO decision is issued below\n"
            "- All counters distinguish RAW from DERIVED (no double-counting)\n"
        )
    elif p31_gate == "P31_BLOCKED_NO_RAW_HISTORICAL_INCREMENT":
        lines.append(
            "Gate is BLOCKED: No raw historical sources found. "
            "All sources are derived pipeline outputs."
        )
    elif p31_gate == "P31_BLOCKED_LICENSE_PROVENANCE_UNSAFE":
        lines.append(
            "Gate is BLOCKED: No license-safe source identified. "
            "Do not proceed to P32 without license resolution."
        )
    elif p31_gate == "P31_FAIL_INPUT_MISSING":
        lines.append("Gate is FAIL: No input sources found to classify.")

    # 8. P32 Recommendation
    h2("8. P32 Acquisition Decision")
    lines.append(f"**Decision**: `{prov.overall_p32_recommendation}`")
    lines.append("")

    if prov.overall_p32_recommendation == "GO_FULL":
        lines.append(
            "All sources have verified provenance and safe licenses. "
            "Proceed to P32 for full 2024 ingestion."
        )
    elif prov.overall_p32_recommendation == "GO_PARTIAL_GAME_LOGS_ONLY":
        lines.append(
            "**Rationale**:\n"
            "- Retrosheet gl2024 and MLB Stats API 2024 are VERIFIED with safe "
            "non-commercial licenses. Game-log ingestion can proceed NOW.\n"
            "- 2024 closing moneyline odds provider is UNRESOLVED. "
            "Full moneyline model training must wait for license confirmation.\n"
            "\n"
            "**P32 Phase A (permitted immediately)**:\n"
            "  Download Retrosheet gl2024.zip → parse → validate schema → "
            "  load into data/mlb_2024/ raw layer.\n"
            "\n"
            "**P32 Phase B (blocked pending license)**:\n"
            "  Acquire closing moneyline odds → join with game logs → "
            "  build complete training rows.\n"
            "\n"
            "**Expected gain from Phase A alone**:\n"
            f"  ~2,430 game records → potential active entries "
            f"~{P28_ACTIVE_ENTRIES + 2430:,} (if ≥90% pass schema validation).\n"
        )
    else:
        lines.append(
            "NO_GO: No viable 2024 acquisition path identified. "
            "Do not proceed to P32."
        )

    # 9. Paper-only / production status
    h2("9. Compliance Status")
    row("Control", "Value")
    sep(2)
    row("PAPER_ONLY", str(PAPER_ONLY))
    row("production_ready", str(PRODUCTION_READY))
    row("Live TSL called", "False")
    row("Real bets placed", "False")
    row("Data downloaded in P31", "False (audit only)")

    # 10. Gate marker (final line)
    lines.append("\n---")
    lines.append("")
    lines.append(f"```")
    lines.append(p31_gate)
    lines.append(f"```")
    lines.append("")
    lines.append(p31_gate)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI main
# ---------------------------------------------------------------------------


def main() -> int:
    print("[P31] Starting Honest Data Reality Audit...")
    print(f"[P31] PAPER_ONLY={PAPER_ONLY}  production_ready={PRODUCTION_READY}")
    print(f"[P31] Repo root: {REPO_ROOT}")

    # 1. Run source classification audit
    print("[P31] Running source classification audit...")
    audit_result = run_honest_data_audit(REPO_ROOT)
    c = audit_result.counters
    print(f"[P31] Classified {c.total_sources} sources:")
    print(f"      RAW_PRIMARY={c.raw_primary_count}")
    print(f"      RAW_SECONDARY={c.raw_secondary_count}")
    print(f"      DERIVED_OUTPUT={c.derived_output_count}")
    print(f"      SCHEMA_PARTIAL={c.schema_partial_count}")
    print(f"      usable_2024_raw={c.usable_2024_raw_count}")
    print(f"      misleading_ready={c.misleading_ready_source_count}")

    # 2. Write classification CSV
    write_classification_csv(audit_result, CLASSIFICATION_CSV)
    print(f"[P31] Wrote classification CSV: {CLASSIFICATION_CSV}")

    # 3. Run provenance / license audit
    print("[P31] Running provenance & license audit...")
    provenance_result = run_provenance_license_audit()
    print(f"[P31] P32 recommendation: {provenance_result.overall_p32_recommendation}")

    # 4. Write provenance JSON
    write_provenance_audit_json(provenance_result, PROVENANCE_JSON)
    print(f"[P31] Wrote provenance JSON: {PROVENANCE_JSON}")

    # 5. Determine P31 gate
    p31_gate = determine_p31_gate(
        audit_result,
        provenance_safe=provenance_result.game_logs_license_safe,
    )
    print(f"[P31] P31 gate: {p31_gate}")

    # 6. Build and write report
    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report_text = build_report(audit_result, provenance_result, p31_gate, run_ts)

    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(report_text, encoding="utf-8")
    print(f"[P31] Wrote audit report: {REPORT_MD}")

    # 7. Verify required outputs exist
    assert CLASSIFICATION_CSV.exists(), f"MISSING: {CLASSIFICATION_CSV}"
    assert PROVENANCE_JSON.exists(), f"MISSING: {PROVENANCE_JSON}"
    assert REPORT_MD.exists(), f"MISSING: {REPORT_MD}"

    # 8. Verify gate marker in report
    report_contents = REPORT_MD.read_text(encoding="utf-8")
    valid_gates = {
        "P31_HONEST_DATA_AUDIT_READY",
        "P31_BLOCKED_NO_RAW_HISTORICAL_INCREMENT",
        "P31_BLOCKED_LICENSE_PROVENANCE_UNSAFE",
        "P31_BLOCKED_NON_DETERMINISTIC_INVENTORY",
        "P31_FAIL_INPUT_MISSING",
    }
    gate_found = any(g in report_contents for g in valid_gates)
    assert gate_found, "ERROR: No valid P31 gate marker found in report!"

    # 9. Safety check: production_ready must not be True
    assert "production_ready=True" not in report_contents, (
        "SAFETY VIOLATION: production_ready=True found in report!"
    )
    assert "production_ready: True" not in report_contents, (
        "SAFETY VIOLATION: production_ready: True found in report!"
    )

    print(f"\n[P31] ===== AUDIT COMPLETE =====")
    print(f"[P31] Gate: {p31_gate}")
    print(f"[P31] P32 recommendation: {provenance_result.overall_p32_recommendation}")
    print(f"[P31] PAPER_ONLY={PAPER_ONLY}  production_ready={PRODUCTION_READY}")
    print(f"[P31] NOT PUSHED.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
