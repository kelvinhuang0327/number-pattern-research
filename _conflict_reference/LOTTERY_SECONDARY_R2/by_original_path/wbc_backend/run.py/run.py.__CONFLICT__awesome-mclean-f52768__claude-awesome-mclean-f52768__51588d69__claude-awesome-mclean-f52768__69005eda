#!/usr/bin/env python3
"""
WBC Automated Prediction Backend — Main Entry Point

Usage:
    python -m wbc_backend.run                  # Full pipeline: analyze default game
    python -m wbc_backend.run --game WBC26-X   # Analyze specific game
    python -m wbc_backend.run --train          # Force model retrain
    python -m wbc_backend.run --backtest       # Run full backtest
    python -m wbc_backend.run --improve        # Run self-improvement cycle
    python -m wbc_backend.run --research-cycle # Run V3 research phase-gate cycle
    python -m wbc_backend.run --scheduler      # Start automated scheduler
    python -m wbc_backend.run --all            # Full pipeline + train + backtest + improve
    python -m wbc_backend.run --json           # Also output JSON
"""
from __future__ import annotations

import argparse
import logging
import sys

# ── Logging Setup ────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("wbc_backend")


def main():  # NOSONAR  # noqa: C901
    parser = argparse.ArgumentParser(
        description="WBC 2026 Automated Prediction Backend",
    )
    parser.add_argument("--game", type=str, default="WBC26-TPE-AUS-001",
                        help="Game ID to analyze")
    parser.add_argument("--line-total", type=float, default=7.5,
                        help="Over/Under line")
    parser.add_argument("--line-spread", type=float, default=-1.5,
                        help="Home spread line")
    parser.add_argument("--train", action="store_true",
                        help="Force model retrain before analysis")
    parser.add_argument("--backtest", action="store_true",
                        help="Run full backtest")
    parser.add_argument("--improve", action="store_true",
                        help="Run self-improvement cycle")
    parser.add_argument("--research-cycle", action="store_true",
                        help="Run V3 research phase-gate cycle")
    parser.add_argument("--scheduler", action="store_true",
                        help="Start automated scheduler (background)")
    parser.add_argument("--all", action="store_true",
                        help="Run everything: validate + train + analyze + backtest + improve")
    parser.add_argument("--json", action="store_true",
                        help="Also print JSON output")

    args = parser.parse_args()

    print()
    print("=" * 70)
    print("🏟️  WBC 2026 AUTOMATED PREDICTION BACKEND")
    print("=" * 70)
    print()

    from wbc_backend.config.settings import AppConfig
    config = AppConfig()

    if args.all:
        args.train = True
        args.backtest = True
        args.improve = True
        args.research_cycle = True

    # ── Step 1: Data Validation ──────────────────────────
    print("━" * 50)
    print("📡 STEP 1: Data Validation")
    print("━" * 50)
    from wbc_backend.data.validator import validate_dataset, auto_fetch_missing_data

    report = validate_dataset("MLB_2025", config)
    print("  Source: MLB_2025")
    print(f"  Records: {report.total_records}")
    print(f"  Completeness: {report.completeness_pct:.1%}")
    print(f"  Valid: {report.is_valid}")
    if not report.is_valid:
        print("  ⚠️  Auto-fetching missing data...")
        report = auto_fetch_missing_data("MLB_2025", config)
        print(f"  → Completeness after fetch: {report.completeness_pct:.1%}")
    print()

    # ── Step 2: Model Training ───────────────────────────
    if args.train:
        print("━" * 50)
        print("🧠 STEP 2: Auto-Train Models")
        print("━" * 50)
        from wbc_backend.models.trainer import auto_train_models

        results = auto_train_models(config)
        for r in results:
            print(f"  {r.model_name:12s} → acc={r.accuracy:.4f} | "
                  f"logloss={r.logloss:.4f} | brier={r.brier_score:.4f}")
        print()

    # ── Step 3: Analyze Game ─────────────────────────────
    print("━" * 50)
    print(f"🎯 STEP 3: Analyze Game — {args.game}")
    print("━" * 50)
    from wbc_backend.data.wbc_verification import WBCDataVerificationError
    from wbc_backend.pipeline.deployment_gate import DeploymentGateError
    from wbc_backend.pipeline.service import PredictionService

    service = PredictionService(config)
    from wbc_backend.domain.schemas import AnalyzeRequest

    request = AnalyzeRequest(
        game_id=args.game,
        line_total=args.line_total,
        line_spread_home=args.line_spread,
    )
    response = None
    try:
        response = service.analyze(request)
    except WBCDataVerificationError as exc:
        print("  BLOCKED: authoritative WBC data verification failed.")
        for issue in exc.result.issues:
            print(f"    - [{issue.severity}] {issue.message}")
        print()
        print("  Populate data/wbc_2026_authoritative_snapshot.json with official schedule, roster,")
        print("  starting pitchers, and lineups before running analysis again.")
        if not (args.backtest or args.improve or args.research_cycle or args.scheduler):
            return
    except DeploymentGateError as exc:
        print("  BLOCKED: deployment gate rejected the current model package.")
        for check in exc.report.checks:
            marker = "OK" if check.passed else "FAIL"
            print(f"    - [{marker}] {check.name}: {check.details}")
        if not (args.backtest or args.improve or args.research_cycle or args.scheduler):
            return

    # Print markdown report
    if response is not None:
        print(response.markdown_report)

    if args.json and response is not None:
        print()
        print("━" * 50)
        print("📋 JSON OUTPUT")
        print("━" * 50)
        print(response.json_report)

    # ── Step 4: Backtest ─────────────────────────────────
    if args.backtest:
        print()
        print("━" * 50)
        print("📊 STEP 4: Institutional Backtest")
        print("━" * 50)
        from wbc_backend.evaluation.institutional_backtest import run_wbc_2023_backtest

        bt = run_wbc_2023_backtest(initial_bankroll=config.bankroll.initial_bankroll)
        print(f"  Games: {bt.n_games_total}")
        print(f"  Bets: {bt.n_bets_placed}")
        print(f"  Accuracy: {bt.accuracy:.3f}")
        print(f"  Brier: {bt.brier_score:.4f}")
        print(f"  ROI: {bt.roi:.3%}")
        print(f"  Sharpe: {bt.sharpe_ratio:.3f}")
        print(f"  Max Drawdown: {bt.max_drawdown:.3%}")
        print(f"  p-value (vs random): {bt.p_value_vs_random:.4f}")
        if bt.p_value_vs_random < 0.05:
            print("  Significance: PASS (p < 0.05)")
        else:
            print("  Significance: FAIL (p >= 0.05)")

    # ── Step 5: Self-Improvement ─────────────────────────
    if args.improve:
        print()
        print("━" * 50)
        print("🧬 STEP 5: Self-Improvement")
        print("━" * 50)
        from wbc_backend.optimization.self_improve import self_improve

        si_result = self_improve(config=config)
        print(f"  Cycle: #{si_result['cycle_number']}")
        print(f"  Feature selection: {si_result.get('feature_status', {})}")
        print(f"  Model status: {si_result.get('model_status', {})}")
        print(f"  New weights: {si_result.get('new_weights', {})}")

    # ── Step 6: V3 Research Cycle ───────────────────────
    if args.research_cycle:
        print()
        print("━" * 50)
        print("🧪 STEP 6: V3 Research Phase-Gate Cycle")
        print("━" * 50)
        from wbc_backend.research.runtime import run_research_cycle

        rc = run_research_cycle(seed=42)
        print(f"  All Passed: {rc['all_passed']}")
        print(f"  Phases: {rc['phase_count']}")
        for item in rc["phase_results"]:
            print(f"    - {item['phase']}: passed={item['passed']} metrics={item['metrics']}")

    # ── Step 7: Scheduler ────────────────────────────────
    if args.scheduler:
        print()
        print("━" * 50)
        print("🔁 STEP 7: Starting Automated Scheduler")
        print("━" * 50)
        from wbc_backend.scheduler.jobs import AutoScheduler

        scheduler = AutoScheduler(config)
        scheduler.setup_default_tasks()
        scheduler.start()
        print("  Scheduler running in background.")
        print("  Tasks:")
        for task in scheduler.tasks:
            hours = task.interval_seconds / 3600
            print(f"    • {task.name}: every {hours:.0f}h")

        print()
        print("  Press Ctrl+C to stop.")
        try:
            import time
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            scheduler.stop()
            print("\n  Scheduler stopped.")

    print()
    print("=" * 70)
    print("✅ WBC BACKEND COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
