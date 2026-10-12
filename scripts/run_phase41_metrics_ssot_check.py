#!/usr/bin/env python3
"""
Phase 41: Metrics SSOT Verification Check
==========================================
Validates that wbc_backend/evaluation/metrics.py is the single source of truth
for all MLB evaluation computations. Runs fixture comparisons and detects
any divergence between the SSOT module and known report constants.

Usage:
  python scripts/run_phase41_metrics_ssot_check.py
  python scripts/run_phase41_metrics_ssot_check.py --json
  python scripts/run_phase41_metrics_ssot_check.py --report

Hard rules:
  - No external API / LLM calls.
  - No modification to model or production data.
  - No CANDIDATE_PATCH creation.
  - Pure deterministic fixture comparison.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from wbc_backend.evaluation.metrics import (
    american_odds_to_implied_prob,
    normalize_no_vig,
    american_moneyline_pair_to_no_vig,
    brier_score,
    brier_skill_score,
    log_loss_score,
    expected_calibration_error,
    reliability_bins,
    calibration_summary,
    compare_model_to_market,
)

# ── Phase 37/38 Report constants (ground truth) ───────────────────────────────
REPORT_MODEL_BRIER = 0.2796
REPORT_MARKET_BRIER = 0.2451
REPORT_BSS = -0.141          # 1 - 0.2796/0.2451
PHASE38_CLEANED_MARKET_BRIER = 0.2419


# ─────────────────────────────────────────────────────────────────────────────
# § Data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    check_id: str
    status: str        # PASS / FAIL / SKIP
    summary: str
    detail: str = ""
    expected: object = None
    actual: object = None


@dataclass
class Phase41Report:
    phase: str = "Phase 41"
    title: str = "Metrics SSOT Verification"
    checks: list[CheckResult] = field(default_factory=list)
    verdict: str = "INCOMPLETE"
    n_pass: int = 0
    n_fail: int = 0
    n_skip: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# § Individual checks
# ─────────────────────────────────────────────────────────────────────────────

def check_american_odds_even(report: Phase41Report) -> None:
    """C01: +100 → 0.5 (even money)"""
    val = american_odds_to_implied_prob("+100")
    ok = abs(val - 0.5) < 1e-9
    report.checks.append(CheckResult(
        check_id="C01_ODDS_EVEN",
        status="PASS" if ok else "FAIL",
        summary=f"+100 → {val:.6f} (expected 0.500000)",
        detail="american_odds_to_implied_prob('+100') must return exactly 0.5",
        expected=0.5,
        actual=val,
    ))


def check_american_odds_minus150(report: Phase41Report) -> None:
    """C02: -150 → 0.6"""
    val = american_odds_to_implied_prob("-150")
    expected = 150.0 / (150.0 + 100.0)
    ok = abs(val - expected) < 1e-9
    report.checks.append(CheckResult(
        check_id="C02_ODDS_MINUS150",
        status="PASS" if ok else "FAIL",
        summary=f"-150 → {val:.6f} (expected {expected:.6f})",
        detail="american_odds_to_implied_prob('-150') must return 150/250 = 0.6",
        expected=expected,
        actual=val,
    ))


def check_american_odds_plus120(report: Phase41Report) -> None:
    """C03: +120 → 100/220"""
    val = american_odds_to_implied_prob("+120")
    expected = 100.0 / 220.0
    ok = abs(val - expected) < 1e-9
    report.checks.append(CheckResult(
        check_id="C03_ODDS_PLUS120",
        status="PASS" if ok else "FAIL",
        summary=f"+120 → {val:.6f} (expected {expected:.6f})",
        expected=expected,
        actual=val,
    ))


def check_no_vig_sums_to_one(report: Phase41Report) -> None:
    """C04: no-vig normalization output sums to 1.0"""
    h, a = normalize_no_vig(0.6, 0.55)
    total = h + a
    ok = abs(total - 1.0) < 1e-10
    report.checks.append(CheckResult(
        check_id="C04_NO_VIG_SUM",
        status="PASS" if ok else "FAIL",
        summary=f"normalize_no_vig(0.6, 0.55) sum = {total:.10f} (expected 1.0)",
        expected=1.0,
        actual=total,
    ))


def check_no_vig_rejects_zero_total(report: Phase41Report) -> None:
    """C05: normalize_no_vig raises ValueError when total <= 0"""
    raised = False
    try:
        normalize_no_vig(0.0, 0.0)
    except ValueError:
        raised = True
    report.checks.append(CheckResult(
        check_id="C05_NO_VIG_ZERO",
        status="PASS" if raised else "FAIL",
        summary=f"normalize_no_vig(0, 0) raises ValueError: {raised}",
        detail="Must raise ValueError, not return a silent fallback",
        expected=True,
        actual=raised,
    ))


def check_brier_known_fixture(report: Phase41Report) -> None:
    """C06: brier_score known fixture — [0.9, 0.8], [1, 1] → 0.025"""
    val = brier_score([0.9, 0.8], [1.0, 1.0])
    expected = 0.025
    ok = abs(val - expected) < 1e-10
    report.checks.append(CheckResult(
        check_id="C06_BRIER_FIXTURE",
        status="PASS" if ok else "FAIL",
        summary=f"brier_score([0.9,0.8],[1,1]) = {val:.6f} (expected {expected})",
        expected=expected,
        actual=val,
    ))


def check_bss_report_constants(report: Phase41Report) -> None:
    """C07: BSS from report constants matches REPORT_BSS (-14.1%)"""
    bss = brier_skill_score(REPORT_MODEL_BRIER, REPORT_MARKET_BRIER)
    ok = bss is not None and abs(bss - REPORT_BSS) < 0.001
    report.checks.append(CheckResult(
        check_id="C07_BSS_REPORT_CONSTANTS",
        status="PASS" if ok else "FAIL",
        summary=f"BSS({REPORT_MODEL_BRIER}, {REPORT_MARKET_BRIER}) = {bss:.4f} (expected ≈ {REPORT_BSS})",
        detail="1 - 0.2796/0.2451 must match REPORT_BSS within 0.001",
        expected=REPORT_BSS,
        actual=bss,
    ))


def check_bss_positive_case(report: Phase41Report) -> None:
    """C08: BSS > 0 when model_brier < market_brier"""
    bss = brier_skill_score(0.22, 0.25)
    ok = bss is not None and bss > 0
    report.checks.append(CheckResult(
        check_id="C08_BSS_POSITIVE",
        status="PASS" if ok else "FAIL",
        summary=f"brier_skill_score(0.22, 0.25) = {bss} (expected > 0)",
        expected=">0",
        actual=bss,
    ))


def check_bss_baseline_zero(report: Phase41Report) -> None:
    """C09: BSS returns None when baseline_brier = 0"""
    bss = brier_skill_score(0.2, 0.0)
    ok = bss is None
    report.checks.append(CheckResult(
        check_id="C09_BSS_BASELINE_ZERO",
        status="PASS" if ok else "FAIL",
        summary=f"brier_skill_score(0.2, 0.0) = {bss!r} (expected None)",
        expected=None,
        actual=bss,
    ))


def check_log_loss_clips_safely(report: Phase41Report) -> None:
    """C10: log_loss_score handles 0.0 and 1.0 probabilities without crash"""
    try:
        val = log_loss_score([1.0, 0.0], [1.0, 0.0])
        ok = val >= 0.0
        detail = f"returned {val:.6f}"
    except Exception as e:
        ok = False
        val = None
        detail = f"raised {type(e).__name__}: {e}"
    report.checks.append(CheckResult(
        check_id="C10_LOG_LOSS_CLIP",
        status="PASS" if ok else "FAIL",
        summary=f"log_loss_score([1.0, 0.0], [1, 0]) no crash: {ok}",
        detail=detail,
        expected="finite ≥ 0",
        actual=val,
    ))


def check_brier_rejects_out_of_range(report: Phase41Report) -> None:
    """C11: brier_score raises ValueError for probability > 1"""
    raised = False
    try:
        brier_score([1.1], [1.0])
    except ValueError:
        raised = True
    report.checks.append(CheckResult(
        check_id="C11_BRIER_PROB_RANGE",
        status="PASS" if raised else "FAIL",
        summary=f"brier_score([1.1], [1]) raises ValueError: {raised}",
        detail="Probabilities outside [0, 1] must raise ValueError (not be silently clipped)",
        expected=True,
        actual=raised,
    ))


def check_ece_returns_dict(report: Phase41Report) -> None:
    """C12: expected_calibration_error returns dict with ece, n_bins, sample_size, bins"""
    r = expected_calibration_error([0.5, 0.5], [0.0, 1.0])
    required = {"ece", "n_bins", "sample_size", "bins"}
    ok = isinstance(r, dict) and required.issubset(r.keys())
    report.checks.append(CheckResult(
        check_id="C12_ECE_RETURNS_DICT",
        status="PASS" if ok else "FAIL",
        summary=f"ECE returns dict with required keys: {ok}",
        detail=f"keys found: {set(r.keys()) if isinstance(r, dict) else 'not a dict'}",
        expected=sorted(required),
        actual=sorted(r.keys()) if isinstance(r, dict) else None,
    ))


def check_reliability_bins_structure(report: Phase41Report) -> None:
    """C13: reliability_bins returns list of dicts with required keys"""
    bins = reliability_bins([0.3, 0.7], [0.0, 1.0])
    required = {"bin_lower", "bin_upper", "count", "mean_confidence", "mean_accuracy", "gap"}
    ok = (
        isinstance(bins, list) and
        len(bins) > 0 and
        all(required.issubset(b.keys()) for b in bins)
    )
    report.checks.append(CheckResult(
        check_id="C13_RELIABILITY_BINS",
        status="PASS" if ok else "FAIL",
        summary=f"reliability_bins returns list[dict] with all required keys: {ok}",
        detail=f"first bin keys: {set(bins[0].keys()) if bins else 'empty'}",
        expected=sorted(required),
        actual=sorted(bins[0].keys()) if bins else [],
    ))


def check_compare_model_to_market_keys(report: Phase41Report) -> None:
    """C14: compare_model_to_market returns all required keys"""
    r = compare_model_to_market(
        model_probs=[0.6, 0.4, 0.7],
        market_probs=[0.55, 0.45, 0.65],
        labels=[1.0, 0.0, 1.0],
    )
    required = {
        "sample_size", "model_brier", "market_brier", "bss",
        "model_log_loss", "market_log_loss", "model_ece", "market_ece",
        "reliability_bins",
    }
    ok = isinstance(r, dict) and required.issubset(r.keys())
    report.checks.append(CheckResult(
        check_id="C14_COMPARE_KEYS",
        status="PASS" if ok else "FAIL",
        summary=f"compare_model_to_market has all required keys: {ok}",
        expected=sorted(required),
        actual=sorted(r.keys()) if isinstance(r, dict) else None,
    ))


def check_prediction_persistence_uses_ssot(report: Phase41Report) -> None:
    """C15: prediction_persistence.recompute_metrics_from_rows uses metrics SSOT"""
    try:
        import inspect
        import wbc_backend.evaluation.prediction_persistence as pp
        source = inspect.getsource(pp.recompute_metrics_from_rows)
        uses_ssot = "_metrics_brier_score" in source or "from wbc_backend.evaluation.metrics" in source
        report.checks.append(CheckResult(
            check_id="C15_PERSISTENCE_USES_SSOT",
            status="PASS" if uses_ssot else "FAIL",
            summary=f"prediction_persistence.recompute_metrics_from_rows uses metrics SSOT: {uses_ssot}",
            detail="Source should reference _metrics_brier_score (delegating to metrics.py)",
            expected=True,
            actual=uses_ssot,
        ))
    except Exception as e:
        report.checks.append(CheckResult(
            check_id="C15_PERSISTENCE_USES_SSOT",
            status="FAIL",
            summary=f"Cannot inspect recompute_metrics_from_rows: {e}",
        ))


def check_phase37_script_delegates(report: Phase41Report) -> None:
    """C16: Phase 37 script imports from metrics SSOT"""
    try:
        script_path = ROOT / "scripts" / "run_phase37_mlb_bss_root_cause_audit.py"
        source = script_path.read_text(encoding="utf-8")
        delegates = "from wbc_backend.evaluation.metrics import" in source
        report.checks.append(CheckResult(
            check_id="C16_PHASE37_DELEGATES",
            status="PASS" if delegates else "FAIL",
            summary=f"Phase 37 script imports metrics SSOT: {delegates}",
            expected=True,
            actual=delegates,
        ))
    except Exception as e:
        report.checks.append(CheckResult(
            check_id="C16_PHASE37_DELEGATES",
            status="FAIL",
            summary=f"Cannot read Phase 37 script: {e}",
        ))


def check_phase38_script_delegates(report: Phase41Report) -> None:
    """C17: Phase 38 script imports from metrics SSOT"""
    try:
        script_path = ROOT / "scripts" / "run_phase38_mlb_bss_repair_preview.py"
        source = script_path.read_text(encoding="utf-8")
        delegates = "from wbc_backend.evaluation.metrics import" in source
        report.checks.append(CheckResult(
            check_id="C17_PHASE38_DELEGATES",
            status="PASS" if delegates else "FAIL",
            summary=f"Phase 38 script imports metrics SSOT: {delegates}",
            expected=True,
            actual=delegates,
        ))
    except Exception as e:
        report.checks.append(CheckResult(
            check_id="C17_PHASE38_DELEGATES",
            status="FAIL",
            summary=f"Cannot read Phase 38 script: {e}",
        ))


def check_no_external_api(report: Phase41Report) -> None:
    """C18: No external API calls in metrics.py"""
    try:
        metrics_path = ROOT / "wbc_backend" / "evaluation" / "metrics.py"
        source = metrics_path.read_text(encoding="utf-8")
        bad_imports = any(
            token in source
            for token in ["requests.get", "requests.post", "urllib.request", "openai", "anthropic", "httpx"]
        )
        ok = not bad_imports
        report.checks.append(CheckResult(
            check_id="C18_NO_EXTERNAL_API",
            status="PASS" if ok else "FAIL",
            summary=f"metrics.py contains no external API calls: {ok}",
            expected=False,
            actual=bad_imports,
        ))
    except Exception as e:
        report.checks.append(CheckResult(
            check_id="C18_NO_EXTERNAL_API",
            status="FAIL",
            summary=f"Cannot inspect metrics.py: {e}",
        ))


# ─────────────────────────────────────────────────────────────────────────────
# § Runner
# ─────────────────────────────────────────────────────────────────────────────

def run_phase41() -> Phase41Report:
    report = Phase41Report()

    checks = [
        check_american_odds_even,
        check_american_odds_minus150,
        check_american_odds_plus120,
        check_no_vig_sums_to_one,
        check_no_vig_rejects_zero_total,
        check_brier_known_fixture,
        check_bss_report_constants,
        check_bss_positive_case,
        check_bss_baseline_zero,
        check_log_loss_clips_safely,
        check_brier_rejects_out_of_range,
        check_ece_returns_dict,
        check_reliability_bins_structure,
        check_compare_model_to_market_keys,
        check_prediction_persistence_uses_ssot,
        check_phase37_script_delegates,
        check_phase38_script_delegates,
        check_no_external_api,
    ]

    for fn in checks:
        try:
            fn(report)
        except Exception as e:
            report.checks.append(CheckResult(
                check_id=getattr(fn, "__name__", "UNKNOWN"),
                status="FAIL",
                summary=f"Uncaught exception: {type(e).__name__}: {e}",
            ))

    report.n_pass = sum(1 for c in report.checks if c.status == "PASS")
    report.n_fail = sum(1 for c in report.checks if c.status == "FAIL")
    report.n_skip = sum(1 for c in report.checks if c.status == "SKIP")
    report.verdict = "PASS" if report.n_fail == 0 else "FAIL"

    return report


def generate_report(report: Phase41Report) -> str:
    lines = [
        f"# Phase 41 Metrics SSOT Report",
        f"",
        f"**Verdict**: `{report.verdict}`  ",
        f"**Pass**: {report.n_pass} | **Fail**: {report.n_fail} | **Skip**: {report.n_skip}",
        f"",
        f"## Check Results",
        f"",
        f"| ID | Status | Summary |",
        f"|---|---|---|",
    ]
    for c in report.checks:
        icon = "✅" if c.status == "PASS" else ("⚠️" if c.status == "SKIP" else "❌")
        lines.append(f"| `{c.check_id}` | {icon} {c.status} | {c.summary} |")

    lines += [
        f"",
        f"## Details",
        f"",
    ]
    for c in report.checks:
        if c.detail or c.status == "FAIL":
            lines.append(f"### {c.check_id}")
            lines.append(f"- **Status**: {c.status}")
            lines.append(f"- **Summary**: {c.summary}")
            if c.detail:
                lines.append(f"- **Detail**: {c.detail}")
            if c.expected is not None:
                lines.append(f"- **Expected**: `{c.expected}`")
            if c.actual is not None:
                lines.append(f"- **Actual**: `{c.actual}`")
            lines.append("")

    return "\n".join(lines)


def write_report(report: Phase41Report, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generate_report(report), encoding="utf-8")
    print(f"[Phase41] Report written to {output_path}", file=sys.stderr)


# ─────────────────────────────────────────────────────────────────────────────
# § CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 41: Metrics SSOT check")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--report", action="store_true", help="Write markdown report to docs/")
    parser.add_argument("--print", action="store_true", dest="print_report",
                        help="Print markdown report to stdout")
    args = parser.parse_args()

    report = run_phase41()

    if args.json:
        data = asdict(report)
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif args.print_report:
        print(generate_report(report))
    else:
        # Default: concise human-readable
        print(f"Phase 41 Metrics SSOT — {report.verdict} ({report.n_pass}/{len(report.checks)} checks)")
        for c in report.checks:
            icon = "PASS" if c.status == "PASS" else ("SKIP" if c.status == "SKIP" else "FAIL")
            print(f"  [{icon}] {c.check_id}: {c.summary}")

    if args.report:
        out = ROOT / "docs" / "orchestration" / "phase41_metrics_ssot_report_2026-05-04.md"
        write_report(report, out)

    return 0 if report.verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
