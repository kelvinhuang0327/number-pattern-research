"""
Enhanced Prediction Pipeline Service — Full Orchestration

Ties together:
  1. Data validation
  2. Feature engineering
  3. Model ensemble prediction
  4. Monte Carlo simulation
  5. Market calibration
  6. Bet optimization
  7. Institutional decision engine (7-phase intelligence)
  8. Portfolio optimization (CVaR / correlation-adjusted Kelly)
  9. Calibration monitoring (Brier / ECE / drift)
  10. Report generation
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import cast

from data.fetch_status import classify_tsl_feed_status, read_tsl_fetch_status
from data.tsl_snapshot import (
    TEAM_NAME_TO_CODE,
    build_tsl_line_movement_context,
    build_tsl_odds_time_series,
    load_tsl_snapshot,
)
from league_adapters.base import LeagueContext as _LeagueContext
from league_adapters.registry import get_league_adapter, normalize_league_name
from wbc_backend.betting.market import market_adjustment
from wbc_backend.betting.optimizer import (
    build_true_probs,
    classify_market_support_state,
    find_top_bets,
)
from wbc_backend.betting.portfolio_risk import (
    BetProposal,
    PortfolioRiskManager,
    compute_risk_of_ruin,
)
from wbc_backend.betting.bankroll_storage_v3 import BankrollStorageV3
from wbc_backend.betting.risk_control import BankrollState, update_bankroll
from wbc_backend.config.settings import AppConfig
from wbc_backend.data.validator import auto_fetch_missing_data, validate_dataset
from wbc_backend.data.wbc_verification import (
    WBCDataVerificationError,
    WBCAuthoritativeSnapshot,
    hydrate_matchup_from_snapshot,
    verify_game_artifact,
    verify_matchup,
)
from wbc_backend.domain.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    BetRecommendation,
    GameOutput,
    Matchup,
    OddsLine,
    PitcherSnapshot,
    PredictionResult,
    TeamSnapshot,
)
from wbc_backend.features.advanced import build_advanced_features
from wbc_backend.optimization.continuous_learning import ContinuousLearningSystem
from wbc_backend.intelligence.decision_engine import (
    InstitutionalDecisionEngine,
    DecisionReport,
)
from wbc_backend.models.ensemble import predict_matchup
from wbc_backend.models.dynamic_ensemble import record_outcome as record_ensemble_outcome
from wbc_backend.pipeline.wbc_rule_engine import apply_wbc_rules
from wbc_backend.pipeline.deployment_gate import (
    evaluate_deployment_gate,
)
from wbc_backend.reporting.prediction_registry import append_prediction_record
from wbc_backend.reporting.renderers import render_full_report, render_json
from wbc_backend.simulation.monte_carlo import run_monte_carlo
from wbc_backend.strategy.bet_decision_flow import (
    DecisionContext,
    run_decision_pipeline,
)

logger = logging.getLogger(__name__)
_TSL_DIRECT_SUPPORT_MAX_AGE_HOURS = 8.0
_MARKET_SUPPORT_PRIORITY = [
    "tsl_direct",
    "intl_only",
    "tsl_stale",
    "tsl_unlisted_market",
    "tsl_unlisted_matchup",
    "mixed",
    "unknown",
]
_MARKET_SUPPORT_RANK = {
    state: idx for idx, state in enumerate(_MARKET_SUPPORT_PRIORITY)
}
_PORTFOLIO_SUPPORT_MULTIPLIER = {
    "tsl_direct": 1.08,
    "intl_only": 0.98,
    "tsl_stale": 0.88,
    "tsl_unlisted_market": 0.84,
    "tsl_unlisted_matchup": 0.80,
    "mixed": 0.95,
    "unknown": 1.0,
}
_SUPPORT_PERF_MIN_GAMES = 3
_SUPPORT_PERF_ADJ_MIN = 0.92
_SUPPORT_PERF_ADJ_MAX = 1.08


def _normalize_player_name(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


class PredictionService:
    """
    Main prediction service — zero-intervention automated pipeline.

    Call flow:
      1. validate data → auto-patch if needed
      2. load matchup data
      3. run ensemble prediction
      4. apply WBC rules
      5. run Monte Carlo simulation (50K+)
      6. market calibration
      7. find top 3 bets
      8. institutional decision engine (7-phase gate)
      9. portfolio optimization (CVaR)
      10. calibration monitoring
      11. generate report
    """

    def __init__(self, config: AppConfig | None = None):
        self.config = config or AppConfig()
        self.bankroll_storage = BankrollStorageV3(
            self.config.sources.bankroll_storage_db,
        )
        self.bankroll = self.bankroll_storage.load()
        if self.bankroll.initial <= 0:
            self.bankroll = BankrollState(
                initial=self.config.bankroll.initial_bankroll,
                current=self.config.bankroll.initial_bankroll,
                peak=self.config.bankroll.initial_bankroll,
                daily_start=self.config.bankroll.initial_bankroll,
            )
            self.bankroll_storage.save(self.bankroll)
        # Institutional Decision Engine
        self.decision_engine = InstitutionalDecisionEngine(
            bankroll=self.bankroll.current,
        )
        self.portfolio_risk = PortfolioRiskManager(initial_bankroll=self.bankroll.current)
        self.continuous_learning = ContinuousLearningSystem()
        # Calibration tracking
        self._prob_history: list[float] = []
        self._outcome_history: list[int] = []
        self._last_sub_model_results = []
        self._last_tournament = "WBC"
        self._last_round_name = "Pool"

    def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        """Run the full prediction pipeline for a game."""
        logger.info("=" * 70)
        logger.info("🎯 ANALYZING GAME: %s", request.game_id)
        logger.info("=" * 70)

        # ── 1. Data Validation ───────────────────────────
        logger.info("[STEP 1] Validating data completeness...")
        validation = validate_dataset("MLB_2025", self.config)
        if not validation.is_valid:
            logger.info("[STEP 1] Data incomplete (%.1f%%), auto-fetching...",
                       validation.completeness_pct * 100)
            validation = auto_fetch_missing_data("MLB_2025", self.config)
        logger.info("[STEP 1] Data validation: completeness=%.1f%%, valid=%s",
                   validation.completeness_pct * 100, validation.is_valid)

        logger.info("[STEP 1B] Evaluating deployment gate...")
        deployment_gate = evaluate_deployment_gate(self.config)
        deployment_gate.ensure_ready()
        logger.info(
            "[STEP 1B] Deployment gate ready: calibration=%s, wf_brier=%.4f",
            deployment_gate.selected_calibration,
            float(deployment_gate.walkforward_summary.get("brier", 0.0)),
        )

        # ── 2. Build Matchup ─────────────────────────────
        logger.info("[STEP 2] Building matchup data...")
        matchup = self._build_matchup(request)
        verification = verify_matchup(
            matchup,
            self.config.sources.wbc_authoritative_snapshot_json,
        )
        verification.ensure_verified()
        logger.info(
            "[STEP 2] WBC data verified: %s (warnings=%d)",
            verification.canonical_game_id or matchup.game_id,
            sum(1 for issue in verification.issues if issue.severity != "ERROR"),
        )

        # ── 3. Advanced Features ─────────────────────────
        logger.info("[STEP 3] Computing advanced features...")
        adv_features = build_advanced_features(matchup)
        logger.info("[STEP 3] Features: fatigue_diff=%.3f, matchup_diff=%.3f, "
                   "bullpen_stress_diff=%.3f, clutch_diff=%.3f",
                   adv_features.feature_dict.get("sp_fatigue_diff", 0),
                   adv_features.feature_dict.get("matchup_edge_diff", 0),
                   adv_features.feature_dict.get("bullpen_stress_diff", 0),
                   adv_features.feature_dict.get("clutch_diff", 0))

        # ── 4. Ensemble Prediction ───────────────────────
        logger.info("[STEP 4] Running hybrid ensemble prediction...")
        pred = predict_matchup(matchup, self.config.model)
        if verification.status == "VERIFIED_WITH_FALLBACK":
            # 升為 deploy gate：先發認定依賴 fallback 時，禁止輸出下注建議
            # 仍保留 confidence 懲罰供報告使用
            pred.confidence_score *= 0.85
            pred.x_factors.append(
                "DEPLOY_GATE_FALLBACK: 先發資料未完整認定（VERIFIED_WITH_FALLBACK），"
                "本場次不輸出下注建議。"
            )
            logger.warning(
                "[STEP 2] VERIFIED_WITH_FALLBACK for %s — bet recommendations BLOCKED",
                matchup.game_id,
            )
        elif verification.used_fallback_lineup:
            pred.confidence_score *= 0.85
            pred.x_factors.append("Previous-game lineup fallback applied")
        logger.info("[STEP 4] Raw prediction: home=%.3f, away=%.3f, "
                   "score=%s %.1f - %s %.1f",
                   pred.home_win_prob, pred.away_win_prob,
                   matchup.home.team, pred.expected_home_runs,
                   matchup.away.team, pred.expected_away_runs)
        self._last_sub_model_results = list(pred.sub_model_results or [])
        self._last_tournament = matchup.tournament
        self._last_round_name = matchup.round_name

        # ── 5. WBC Rules ─────────────────────────────────
        if matchup.tournament.upper().startswith("WBC"):
            logger.info("[STEP 5] Applying WBC rule adjustments...")
            pred, notes, _ = apply_wbc_rules(matchup, pred)
            for note in notes:
                logger.info("[STEP 5] %s", note)
            # Hard serving-boundary cap after rule engine.
            pred.home_win_prob = max(0.15, min(0.85, float(pred.home_win_prob)))
            pred.away_win_prob = 1.0 - pred.home_win_prob

        # ── N.02 崩盤風險（mismatch_blowout_propensity）──────────────────────
        # 在 MC 之前計算，讓 volatility expansion 也能影響 OU 模擬尾部
        import math as _math
        _elo_gap = abs(matchup.home.elo - matchup.away.elo)
        _blowout_propensity = float(_math.tanh(_elo_gap / 150.0))

        # ── 6. Monte Carlo (50K) ─────────────────────────
        logger.info("[STEP 6] Running Monte Carlo simulation (%d sims)...",
                   self.config.model.mc_simulations)
        sim = run_monte_carlo(
            pred,
            line_total=request.line_total,
            line_spread_home=request.line_spread_home,
            simulations=self.config.model.mc_simulations,
            home_sp_fatigue=adv_features.home_sp_fatigue,
            away_sp_fatigue=adv_features.away_sp_fatigue,
            home_bullpen_stress=adv_features.home_bullpen_stress,
            away_bullpen_stress=adv_features.away_bullpen_stress,
            blowout_propensity=_blowout_propensity,
        )
        logger.info("[STEP 6] MC result: home_wp=%.3f, over=%.3f, "
                   "mean_total=%.1f, odd=%.3f (blowout_propensity=%.2f)",
                   sim.home_win_prob, sim.over_prob,
                   sim.mean_total_runs, sim.odd_prob, _blowout_propensity)

        # ── 7. Market Calibration ────────────────────────
        logger.info("[STEP 7] Running market calibration...")
        odds_lines = self._get_odds(request, matchup)
        tsl_status = read_tsl_fetch_status()
        self._attach_tsl_fetch_context(pred, matchup, odds_lines, tsl_status)
        tsl_matchup_status = pred.diagnostics.get("tsl_matchup") if pred.diagnostics else None
        if not odds_lines:
            pred.x_factors.append("No verified live odds available; market calibration skipped")
        tsl_odds_history = build_tsl_odds_time_series(
            matchup.away.team,
            matchup.home.team,
            markets=("ML",),
            max_snapshots=12,
            max_snapshot_age_hours=8.0,
        )
        market_result = market_adjustment(
            pred.home_win_prob,
            odds_lines,
            matchup.home.team,
            matchup.away.team,
            self.config.market,
            odds_history=tsl_odds_history or None,
            feed_status=tsl_status or None,
            matchup_status=tsl_matchup_status if isinstance(tsl_matchup_status, dict) else None,
        )
        adjusted_home_prob = market_result["adjusted_home_prob"]
        pred.market_bias_score = market_result["market_bias_score"]
        logger.info("[STEP 7] Market: model=%.3f → adjusted=%.3f, bias=%.3f, steams=%d",
                   pred.home_win_prob, adjusted_home_prob,
                   pred.market_bias_score, market_result["n_steam_moves"])

        # ── 8. Build true probabilities ──────────────────
        true_probs = build_true_probs(
            matchup.home.team, matchup.away.team,
            adjusted_home_prob, sim,
        )

        # ── 9. Find Top 3 Bets ──────────────────────────
        # Gate A: VERIFIED_WITH_FALLBACK 狀態禁止輸出下注建議
        # Gate B: MLB PAPER_ONLY — CLV 代理、無 Statcast、BSS = -14.1%
        _league_name = normalize_league_name(matchup.tournament)
        _league_adapter = get_league_adapter(_league_name)
        _league_rules = _league_adapter.rules(
            _LeagueContext(
                league=_league_name,
                game_id=matchup.game_id,
                home_team=matchup.home.team,
                away_team=matchup.away.team,
            )
        )
        _is_paper_only = _league_rules.deployment_mode != "live"

        # ── N.02 崩盤風險評估（已在 Step 6 前計算，此處直接使用）──────────
        if _blowout_propensity > 0.60:
            pred.x_factors.append(
                f"BLOWOUT_RISK: Elo gap {_elo_gap:.0f} → "
                f"mismatch_blowout_propensity={_blowout_propensity:.2f}"
                f"（大比分崩盤風險高，OU Under 已壓制）"
            )
            logger.info(
                "[STEP 8] High blowout propensity=%.2f (Elo gap %.0f) — OU Under suppressed",
                _blowout_propensity, _elo_gap,
            )

        if verification.status == "VERIFIED_WITH_FALLBACK":
            logger.warning(
                "[STEP 8] Bet finding SKIPPED — starter identity unverified (VERIFIED_WITH_FALLBACK)"
            )
            top_bets: list[BetRecommendation] = []
        elif _is_paper_only:
            logger.warning(
                "[STEP 8] %s PAPER_ONLY mode — bets suppressed. Reason: %s",
                _league_name.upper(),
                _league_rules.paper_only_reason,
            )
            pred.x_factors.append(
                f"{_league_name.upper()}_PAPER_ONLY: {_league_rules.paper_only_reason}"
            )
            top_bets = []
        else:
            logger.info("[STEP 8] Finding top EV bets...")
            top_bets = find_top_bets(
                odds_lines, true_probs,
                matchup.home.team, matchup.away.team,
                pred.confidence_score, self.config, self.bankroll,
                model_brier=pred.diagnostics.get("brier_score") if pred.diagnostics else None,
                calibration_ece=pred.diagnostics.get("ece") if pred.diagnostics else None,
                tsl_feed_status=tsl_status or None,
                tsl_matchup_status=tsl_matchup_status if isinstance(tsl_matchup_status, dict) else None,
                market_support_by_market=market_result.get("market_support_by_market"),
                blowout_propensity=_blowout_propensity,
            )

        # ── 10. Institutional Decision Engine (7-Phase) ──
        logger.info("[STEP 9] Running institutional decision engine...")
        decision_rpt = self._run_decision_engine(
            matchup, pred, adjusted_home_prob, odds_lines,
        )
        logger.info("[STEP 9] Decision: %s (%s) — edge=%.1f, regime=%s",
                   decision_rpt.decision, decision_rpt.confidence,
                   decision_rpt.edge_score, decision_rpt.market_regime)

        raw_top_bets_count = len(top_bets)
        top_bets = self._apply_bet_decision_flow(
            top_bets,
            matchup,
            pred,
            adjusted_home_prob,
            market_result,
        )
        top_bets = self._sort_bets_for_execution(top_bets)
        if raw_top_bets_count and not top_bets:
            pred.x_factors.append("All optimizer candidates were rejected by institutional bet gates")
        elif raw_top_bets_count > len(top_bets):
            pred.x_factors.append(
                f"Institutional bet gates filtered {raw_top_bets_count - len(top_bets)} candidate bets"
            )

        # ── 11. Portfolio Optimization ───────────────────
        logger.info("[STEP 10] Running portfolio optimization...")
        portfolio_metrics = self._run_portfolio_optimization(top_bets, decision_rpt, matchup)
        logger.info("[STEP 10] Portfolio: survival=%.1f%%, cvar=%.4f",
                   portfolio_metrics.get("survival_prob", 0) * 100,
                   portfolio_metrics.get("cvar_95", 0))

        # ── 12. Calibration Monitoring ───────────────────
        logger.info("[STEP 11] Calibration monitoring...")
        self._prob_history.append(adjusted_home_prob)
        calibration_metrics = self._run_calibration_monitoring()
        if calibration_metrics:
            logger.info("[STEP 11] Brier=%.4f, ECE=%.4f, drift=%s",
                       calibration_metrics.get("brier", 0),
                       calibration_metrics.get("ece", 0),
                       "YES" if calibration_metrics.get("drift_flag", 0) > 0 else "no")

        # ── 10. Build GameOutput ─────────────────────────
        best_bet_desc = ""
        best_ev = 0.0
        if top_bets:
            best = top_bets[0]
            best_bet_desc = f"{best.market} {best.side}"
            if best.line is not None:
                best_bet_desc += f" ({best.line:+.1f})"
            best_bet_desc += f" @ {best.sportsbook}"
            best_bet_desc += f" [{self._best_bet_support_label(best.market_support_state)}]"
            if best.decision_timing != "IMMEDIATE":
                best_bet_desc += f" [{best.decision_timing}]"
            best_ev = best.ev

        display_home_score, display_away_score, reconciled = self._resolve_display_scores(
            raw_home_runs=pred.expected_home_runs,
            raw_away_runs=pred.expected_away_runs,
            mean_total_runs=sim.mean_total_runs,
            final_home_prob=adjusted_home_prob,
        )
        if reconciled:
            pred.x_factors.append("Display score reconciled to final win-probability direction")

        game_output = GameOutput(
            game_id=request.game_id,
            home_team=matchup.home.team,
            away_team=matchup.away.team,
            home_win_prob=round(adjusted_home_prob, 4),
            away_win_prob=round(1 - adjusted_home_prob, 4),
            predicted_home_score=display_home_score,
            predicted_away_score=display_away_score,
            market_bias_score=pred.market_bias_score,
            ev_best=round(best_ev, 4),
            best_bet_strategy=best_bet_desc,
            confidence_index=pred.confidence_score,
            top_3_bets=top_bets,
        )

        # ── 13. Generate Reports ─────────────────────────
        markdown = render_full_report(
            game_output, pred, sim, market_result, adv_features,
            decision_report=decision_rpt,
            calibration_metrics=calibration_metrics,
            portfolio_metrics=portfolio_metrics,
            market_support_performance=self._load_market_support_performance_summary(),
        )
        json_report = render_json(
            game_output, pred, sim, market_result,
            decision_report=decision_rpt,
            calibration_metrics=calibration_metrics,
            portfolio_metrics=portfolio_metrics,
            market_support_performance=self._load_market_support_performance_summary(),
        )

        logger.info("=" * 70)
        logger.info("✅ ANALYSIS COMPLETE: %s", request.game_id)
        logger.info("=" * 70)

        append_prediction_record(
            config=self.config,
            request=request,
            matchup=matchup,
            verification=verification,
            deployment_gate=deployment_gate,
            game_output=game_output,
            pred=pred,
            sim=sim,
            top_bets=top_bets,
            decision_report=decision_rpt,
            calibration_metrics=calibration_metrics,
            portfolio_metrics=portfolio_metrics,
        )

        return AnalyzeResponse(
            game_output=game_output,
            markdown_report=markdown,
            json_report=json_report,
            decision_report=decision_rpt,
            calibration_metrics=calibration_metrics,
            portfolio_metrics=portfolio_metrics,
            deployment_gate_report=deployment_gate.to_dict(),
        )

    @staticmethod
    def _resolve_display_scores(
        raw_home_runs: float,
        raw_away_runs: float,
        mean_total_runs: float,
        final_home_prob: float,
    ) -> tuple[float, float, bool]:
        raw_diff = raw_home_runs - raw_away_runs
        final_diff = (final_home_prob * 2.0) - 1.0
        total = mean_total_runs if mean_total_runs > 0 else max(0.0, raw_home_runs + raw_away_runs)

        if raw_diff == 0 or final_diff == 0 or raw_diff * final_diff >= 0:
            return round(raw_home_runs, 2), round(raw_away_runs, 2), False

        home_runs = max(0.0, total * final_home_prob)
        away_runs = max(0.0, total - home_runs)
        return round(home_runs, 2), round(away_runs, 2), True

    def _load_market_support_performance_summary(self) -> dict[str, object] | None:
        target = Path(self.config.sources.reports_dir) / "market_support_performance_summary.json"
        if not target.exists():
            return None
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _best_bet_support_label(state: str) -> str:
        mapping = {
            "tsl_direct": "TSL_DIRECT",
            "intl_only": "INTL_ONLY",
            "tsl_stale": "TSL_STALE",
            "tsl_unlisted_market": "TSL_MARKET_GAP",
            "tsl_unlisted_matchup": "TSL_MATCHUP_GAP",
        }
        return mapping.get(str(state or ""), str(state or "UNKNOWN").upper())

    @staticmethod
    def _summarize_market_support(top_bets: list[BetRecommendation]) -> tuple[str, dict[str, int]]:
        if not top_bets:
            return "unknown", {}

        counts: dict[str, int] = {}
        for bet in top_bets:
            state = str(getattr(bet, "market_support_state", "") or "unknown")
            counts[state] = counts.get(state, 0) + 1

        if len(counts) == 1:
            return next(iter(counts)), counts

        dominant_state = max(
            counts.items(),
            key=lambda item: (
                item[1],
                -_MARKET_SUPPORT_PRIORITY.index(item[0]) if item[0] in _MARKET_SUPPORT_PRIORITY else -999,
            ),
        )[0]
        return dominant_state, counts

    @staticmethod
    def _sort_bets_for_execution(top_bets: list[BetRecommendation]) -> list[BetRecommendation]:
        if not top_bets:
            return []

        def _priority_key(bet: BetRecommendation) -> tuple[int, int, float, float]:
            support_rank = _MARKET_SUPPORT_RANK.get(
                str(getattr(bet, "market_support_state", "") or "unknown"),
                len(_MARKET_SUPPORT_RANK),
            )
            delay_minutes = int(getattr(bet, "delay_minutes", 0) or 0)
            return (
                support_rank,
                delay_minutes,
                -float(getattr(bet, "ev", 0.0)),
                -float(getattr(bet, "confidence", 0.0)),
            )

        return sorted(top_bets, key=_priority_key)

    @staticmethod
    def _performance_adjusted_support_multiplier(
        state: str,
        performance_summary: dict[str, object] | None,
    ) -> float:
        base = _PORTFOLIO_SUPPORT_MULTIPLIER.get(str(state or "unknown"), 1.0)
        if not performance_summary:
            return base

        groups = performance_summary.get("groups")
        if not isinstance(groups, dict):
            return base

        metrics = groups.get(str(state))
        if not isinstance(metrics, dict):
            return base

        games = int(metrics.get("games", 0) or 0)
        if games < _SUPPORT_PERF_MIN_GAMES:
            return base

        accuracy = float(metrics.get("winner_accuracy", 0.0) or 0.0)
        avg_brier = float(metrics.get("avg_brier", 0.25) or 0.25)

        # Small adaptive overlay: reward sustained accuracy, penalize poor calibration.
        overlay = 1.0 + ((accuracy - 0.5) * 0.12) - ((avg_brier - 0.20) * 0.25)
        overlay = max(_SUPPORT_PERF_ADJ_MIN, min(_SUPPORT_PERF_ADJ_MAX, overlay))
        return round(base * overlay, 4)

    @staticmethod
    def _attach_tsl_fetch_context(
        pred: PredictionResult,
        matchup: Matchup,
        odds_lines: list[OddsLine],
        status: dict | None = None,
    ) -> None:
        if status is None:
            status = read_tsl_fetch_status()
        if not status:
            return

        pred.diagnostics["tsl_status"] = status
        pred.diagnostics["tsl_fetch_success"] = 1.0 if status.get("success") else 0.0
        pred.diagnostics["tsl_games_count"] = float(status.get("games_count", 0) or 0)

        snapshot_ctx = PredictionService._lookup_tsl_matchup_snapshot(matchup)
        if snapshot_ctx:
            pred.diagnostics["tsl_matchup"] = snapshot_ctx

        note = str(status.get("note") or status.get("error") or "").strip()
        source = str(status.get("source") or "unknown").strip()
        fetched_at = str(status.get("fetched_at") or "").strip()

        if status.get("success"):
            if snapshot_ctx and snapshot_ctx.get("in_snapshot"):
                if snapshot_ctx.get("is_fresh", False):
                    pred.x_factors.append(
                        "TSL snapshot includes this matchup: "
                        f"game_id={snapshot_ctx.get('game_id')}, "
                        f"markets={snapshot_ctx.get('market_count', 0)}, "
                        f"codes={','.join(snapshot_ctx.get('market_codes', []))}"
                    )
                else:
                    pred.x_factors.append(
                        "TSL snapshot includes this matchup, but the latest Taiwan-market data is stale: "
                        f"age={snapshot_ctx.get('snapshot_age_hours', 999.0):.2f}h"
                    )
            else:
                pred.x_factors.append(
                    "TSL feed healthy, but this matchup is not present in the latest Taiwan-market snapshot"
                )
            pred.x_factors.append(
                f"TSL feed healthy: source={source}, games={status.get('games_count', 0)}, fetched_at={fetched_at}"
            )
            return

        if any(line.sportsbook == "TSL" for line in odds_lines):
            pred.x_factors.append(
                f"TSL feed degraded but cached odds still available: source={source}, fetched_at={fetched_at}"
            )
            return

        if "modern_pre_" in note and "403" in note:
            pred.x_factors.append(
                "TSL pre-match feed is currently blocked by the official source; Taiwan market calibration is running without fresh TSL odds"
            )
        elif "legacy_fetch_failed" in note:
            pred.x_factors.append(
                "Legacy TSL API no longer returns machine-readable odds; fallback source migration is still in progress"
            )
        else:
            pred.x_factors.append(
                f"TSL feed unavailable: source={source}, fetched_at={fetched_at}"
            )

    @staticmethod
    def _lookup_tsl_matchup_snapshot(matchup: Matchup) -> dict[str, object] | None:
        snapshot = load_tsl_snapshot()
        fetched_at = str(snapshot.get("fetched_at", ""))
        snapshot_age_hours = 999.0
        if fetched_at:
            try:
                fetched_dt = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
                snapshot_age_hours = max(
                    0.0,
                    (datetime.now(timezone.utc) - fetched_dt.astimezone(timezone.utc)).total_seconds() / 3600.0,
                )
            except ValueError:
                snapshot_age_hours = 999.0
        is_fresh = snapshot_age_hours <= _TSL_DIRECT_SUPPORT_MAX_AGE_HOURS
        games = snapshot.get("games", []) or []
        if not games:
            return {
                "in_snapshot": False,
                "snapshot_source": str(snapshot.get("source", "")),
                "snapshot_fetched_at": fetched_at,
                "snapshot_age_hours": round(snapshot_age_hours, 3),
                "is_fresh": is_fresh,
            }

        for game in games:
            away_code = TEAM_NAME_TO_CODE.get(str(game.get("awayTeamName", "")).strip(), "")
            home_code = TEAM_NAME_TO_CODE.get(str(game.get("homeTeamName", "")).strip(), "")
            if away_code != matchup.away.team or home_code != matchup.home.team:
                continue

            market_codes = []
            for market in game.get("markets", []) or []:
                code = str(market.get("marketCode", "")).strip()
                if code:
                    market_codes.append(code)

            return {
                "in_snapshot": True,
                "game_id": str(game.get("gameId", "")),
                "game_time": str(game.get("gameTime", "")),
                "market_count": len(market_codes),
                "market_codes": market_codes,
                "snapshot_source": str(snapshot.get("source", "")),
                "snapshot_fetched_at": fetched_at,
                "snapshot_age_hours": round(snapshot_age_hours, 3),
                "is_fresh": is_fresh,
            }

        return {
            "in_snapshot": False,
            "snapshot_source": str(snapshot.get("source", "")),
            "snapshot_fetched_at": fetched_at,
            "snapshot_age_hours": round(snapshot_age_hours, 3),
            "is_fresh": is_fresh,
        }

    def _build_matchup(self, request: AnalyzeRequest) -> Matchup:  # NOSONAR  # noqa: C901
        """
        Build a Matchup from the request.

        WBC schedule / starters / lineups are sourced from the authoritative
        local snapshot. If the game is missing or not verified there, analysis
        must stop.
        """
        from wbc_backend.ingestion.providers import WBCDataProvider

        provider = WBCDataProvider(self.config)
        schedule_df = provider.load_wbc_2026_live()
        snapshot_repo = WBCAuthoritativeSnapshot(
            self.config.sources.wbc_authoritative_snapshot_json,
        )
        snapshot_game = snapshot_repo.find_game(request.game_id)
        precheck = verify_game_artifact(
            game_id=request.game_id,
            expected_home=None,
            expected_away=None,
            expected_game_time=None,
            expected_home_sp=None,
            expected_away_sp=None,
            expected_home_lineup=None,
            expected_away_lineup=None,
            snapshot_path=self.config.sources.wbc_authoritative_snapshot_json,
        )
        if precheck.blocking and not precheck.used_fallback_lineup:
            precheck.ensure_verified()
        elif precheck.blocking:
            issue_summary = "; ".join(issue.message for issue in precheck.issues) or "fallback verification warning"
            logger.warning(
                "Proceeding with fallback authoritative snapshot for %s: %s",
                request.game_id,
                issue_summary,
            )

        # Find the game
        row = None
        for _, r in schedule_df.iterrows():
            aliases = {
                str(r.get("game_id", "")).upper(),
                *[part.strip().upper() for part in str(r.get("aliases", "")).split(",") if part.strip()],
            }
            if request.game_id.upper() in aliases:
                row = r
                break

        if row is None:
            raise WBCDataVerificationError(precheck)

        # Build team snapshots from provider data
        from wbc_backend.ingestion.unified_loader import UnifiedDataLoader
        from wbc_backend.cleaning.preprocess import clean_team_metrics
        loader = UnifiedDataLoader(self.config)

        try:
            metrics = clean_team_metrics(loader.load_team_metrics())
            lookup = metrics.set_index("team")
            pitcher_profiles = loader.load_wbc_pitcher_profiles()

            home_code = row["home"]
            away_code = row["away"]

            def _coalesce(primary, fallback, default):
                for value in (primary, fallback):
                    if value is None:
                        continue
                    if value != value:
                        continue
                    return value
                return default

            def _team(code, row_data, prefix):
                if code in lookup.index:
                    m = lookup.loc[code]
                    return TeamSnapshot(
                        team=code,
                        elo=float(_coalesce(m.get("elo"), None, 1500.0)),
                        batting_woba=float(_coalesce(m.get("woba"), None, 0.320)),
                        batting_ops_plus=float(_coalesce(m.get("ops_plus"), None, 100.0)),
                        pitching_fip=float(_coalesce(m.get("fip"), None, 3.80)),
                        pitching_whip=float(_coalesce(m.get("whip"), None, 1.25)),
                        pitching_stuff_plus=float(_coalesce(m.get("stuff_plus"), None, 100.0)),
                        der=float(_coalesce(m.get("der"), None, 0.700)),
                        bullpen_depth=float(_coalesce(m.get("bullpen_depth"), None, 8.0)),
                        pitch_limit=int(_coalesce(row_data.get(f"{prefix}_pitch_limit"), None, 65)),
                        bullpen_era=float(_coalesce(m.get("bullpen_era"), row_data.get(f"{prefix}_bullpen_era"), 3.50)),
                        bullpen_pitches_3d=int(_coalesce(m.get("bullpen_pitches_3d"), row_data.get(f"{prefix}_bullpen_pitches_3d"), 0)),
                        runs_per_game=float(_coalesce(m.get("runs_per_game"), row_data.get(f"{prefix}_runs_per_game"), 4.5)),
                        runs_allowed_per_game=float(_coalesce(m.get("runs_allowed_per_game"), row_data.get(f"{prefix}_runs_allowed_per_game"), 4.5)),
                        clutch_woba=float(_coalesce(m.get("clutch_woba"), row_data.get(f"{prefix}_clutch_woba"), 0.320)),
                        roster_strength_index=float(_coalesce(m.get("roster_strength_index"), row_data.get(f"{prefix}_roster_strength_index"), 80.0)),
                        missing_core_batter=bool(_coalesce(row_data.get(f"{prefix}_missing_core_batter"), None, False)),
                        ace_pitch_count_limited=bool(_coalesce(row_data.get(f"{prefix}_ace_limited"), None, False)),
                        top50_stars=int(_coalesce(m.get("top50_stars"), row_data.get(f"{prefix}_top50_stars"), 0)),
                        sample_size=int(_coalesce(m.get("sample_size"), row_data.get(f"{prefix}_sample_size"), 120)),
                        league_prior_strength=float(_coalesce(m.get("league_prior_strength"), row_data.get(f"{prefix}_league_prior_strength"), 0.0)),
                        win_pct_last_10=float(_coalesce(m.get("win_pct_last_10"), row_data.get(f"{prefix}_win_pct_last_10"), 0.5)),
                        rest_days=int(_coalesce(m.get("rest_days"), row_data.get(f"{prefix}_rest_days"), 1)),
                    )
                else:
                    return TeamSnapshot(
                        team=code, elo=1500, batting_woba=0.320,
                        batting_ops_plus=100, pitching_fip=3.80,
                        pitching_whip=1.25, pitching_stuff_plus=100,
                        der=0.700, bullpen_depth=8.0, pitch_limit=65,
                    )

            matchup = Matchup(
                game_id=row["game_id"],
                tournament=row.get("tournament", "WBC2026"),
                game_time_utc=row["game_time_utc"],
                home=_team(home_code, row, "home"),
                away=_team(away_code, row, "away"),
                venue=str(row.get("venue", "")),
                round_name=str(row.get("round_name", "Pool")),
                neutral_site=bool(row.get("neutral_site", True)),
                weather=str(row.get("weather", "dome")),
                umpire_id=str(row.get("umpire_id", "generic_avg")),
                elevation_m=float(row.get("elevation_m", 0.0)),
                temp_f=float(row.get("temp_f", 72.0)),
                humidity_pct=float(row.get("humidity_pct", 0.50)),
                wind_speed_mph=float(row.get("wind_speed_mph", 0.0)),
                wind_direction=str(row.get("wind_direction", "none")),
                is_dome=bool(row.get("is_dome", False)),
            )
            matchup = hydrate_matchup_from_snapshot(matchup, snapshot_game or {})
            matchup.home_sp = self._enrich_pitcher_snapshot(matchup.home_sp, matchup.home.team, pitcher_profiles)
            matchup.away_sp = self._enrich_pitcher_snapshot(matchup.away_sp, matchup.away.team, pitcher_profiles)
            matchup.home_bullpen = self._build_bullpen(matchup.home.team, matchup.home_sp, pitcher_profiles)
            matchup.away_bullpen = self._build_bullpen(matchup.away.team, matchup.away_sp, pitcher_profiles)
            return matchup

        except Exception as e:
            logger.error("Failed to build verified matchup for %s: %s", request.game_id, e)
            raise

    def _get_odds(self, request: AnalyzeRequest, matchup: Matchup) -> list[OddsLine]:
        """Get odds lines for the matchup."""
        from wbc_backend.ingestion.unified_loader import UnifiedDataLoader

        loader = UnifiedDataLoader(self.config)
        odds_map = loader.load_wbc_seed_odds()
        for key in (matchup.game_id, request.game_id, str(request.game_id).upper(), str(matchup.game_id).upper()):
            if key in odds_map:
                lines = list(odds_map[key])
                if self.config.sources.allow_seed_odds_for_live_predictions:
                    return lines
                non_seed = [line for line in lines if line.source_type != "seed"]
                if not non_seed and lines:
                    logger.warning(
                        "Ignoring %d seed odds lines for %s; live predictions require real market data",
                        len(lines),
                        key,
                    )
                return non_seed
        return []

    @staticmethod
    def _profile_to_pitcher(profile: dict[str, float]) -> PitcherSnapshot:
        return PitcherSnapshot(
            name=str(profile["name"]),
            team=str(profile.get("team", "")),
            era=float(profile.get("era", 3.80)),
            fip=float(profile.get("fip", 3.90)),
            whip=float(profile.get("whip", 1.25)),
            k_per_9=float(profile.get("k_per_9", 8.5)),
            bb_per_9=float(profile.get("bb_per_9", 3.0)),
            stuff_plus=float(profile.get("stuff_plus", 100.0)),
            ip_last_30=float(profile.get("ip_last_30", 20.0)),
            era_last_3=float(profile.get("era_last_3", profile.get("era", 3.80))),
            pitch_count_last_3d=int(profile.get("pitch_count_last_3d", 0)),
            fastball_velo=float(profile.get("fastball_velo", 93.0)),
            high_leverage_era=float(profile.get("high_leverage_era", profile.get("era", 3.80))),
            role=str(profile.get("role", "SP")),
            pitch_mix=dict(profile.get("pitch_mix", {}) or {}),
            recent_fastball_velos=[float(v) for v in profile.get("recent_fastball_velos", []) or []],
            career_fastball_velo=float(profile.get("career_fastball_velo", profile.get("fastball_velo", 93.0))),
            woba_vs_left=float(profile.get("woba_vs_left", 0.320)),
            woba_vs_right=float(profile.get("woba_vs_right", 0.320)),
            innings_last_14d=float(profile.get("innings_last_14d", 0.0)),
            season_avg_innings_per_14d=float(profile.get("season_avg_innings_per_14d", 0.0)),
            recent_spin_rate=float(profile.get("recent_spin_rate", 0.0)),
            career_spin_rate_mean=float(profile.get("career_spin_rate_mean", 0.0)),
            career_spin_rate_std=float(profile.get("career_spin_rate_std", 0.0)),
        )

    def _enrich_pitcher_snapshot(
        self,
        pitcher: PitcherSnapshot | None,
        team_code: str,
        pitcher_profiles: dict[str, dict[str, dict[str, float]]],
    ) -> PitcherSnapshot | None:
        if pitcher is None:
            return None
        team_profiles = pitcher_profiles.get(team_code, {})
        profile = team_profiles.get(_normalize_player_name(pitcher.name))
        if not profile:
            return pitcher
        enriched = self._profile_to_pitcher(profile)
        return cast(
            PitcherSnapshot,
            replace(enriched, name=pitcher.name, team=team_code, role=pitcher.role or enriched.role),
        )

    def _build_bullpen(
        self,
        team_code: str,
        starter: PitcherSnapshot | None,
        pitcher_profiles: dict[str, dict[str, dict[str, float]]],
    ) -> list[PitcherSnapshot]:
        team_profiles = pitcher_profiles.get(team_code, {})
        starter_name = _normalize_player_name(starter.name) if starter else ""
        relievers = []
        fallback = []
        for name_key, profile in team_profiles.items():
            if name_key == starter_name:
                continue
            pitcher = self._profile_to_pitcher(profile)
            if pitcher.role in {"RP", "PB"}:
                relievers.append(pitcher)
            else:
                fallback.append(pitcher)
        return relievers or fallback

    # ── Institutional Intelligence Integration ───────────────────────────

    def _run_decision_engine(  # NOSONAR
        self,
        matchup: Matchup,
        pred: PredictionResult,
        adjusted_home_prob: float,
        odds_lines: list[OddsLine],
    ) -> DecisionReport:
        """Run the 7-phase institutional decision engine."""
        # Extract sub-model probabilities from diagnostics
        sub_model_probs: dict[str, float] = {}
        if pred.sub_model_results:
            for sr in pred.sub_model_results:
                sub_model_probs[sr.model_name] = sr.home_win_prob

        # Find ML odds
        odds_home = 2.0
        odds_away = 1.85
        for o in odds_lines:
            if o.market == "ML":
                if o.side == matchup.home.team or o.side == "HOME":
                    odds_home = o.decimal_odds
                elif o.side == matchup.away.team or o.side == "AWAY":
                    odds_away = o.decimal_odds

        # Extract calibration params from diagnostics
        brier = pred.diagnostics.get("brier_score", 0.25) if pred.diagnostics else 0.25
        platt_a = pred.diagnostics.get("platt_a", 1.0) if pred.diagnostics else 1.0
        platt_b = pred.diagnostics.get("platt_b", 0.0) if pred.diagnostics else 0.0

        league = "WBC" if matchup.tournament.upper().startswith("WBC") else "MLB"
        tsl_line_ctx = build_tsl_line_movement_context(
            matchup.away.team,
            matchup.home.team,
            market="ML",
            game_time=matchup.game_time_utc,
            max_snapshots=12,
            max_snapshot_age_hours=8.0,
        )

        report = self.decision_engine.analyze_match(
            match_id=matchup.game_id,
            match_label=f"{matchup.away.team} @ {matchup.home.team}",
            sub_model_probs=sub_model_probs,
            calibrated_prob=adjusted_home_prob,
            odds_home=odds_home,
            odds_away=odds_away,
            brier_score=brier,
            platt_a=platt_a,
            platt_b=platt_b,
            opening_odds=float(tsl_line_ctx.get("opening_home_odds", 0.0)),
            line_movement_velocity=float(tsl_line_ctx.get("line_movement_velocity", 0.0)),
            total_line_moves=int(tsl_line_ctx.get("total_line_moves", 0)),
            line_history=cast(list, tsl_line_ctx.get("line_history", [])),
            odds_velocity=float(tsl_line_ctx.get("recent_velocity", 0.0)),
            odds_acceleration=float(tsl_line_ctx.get("odds_acceleration", 0.0)),
            league=league,
        )
        return report

    def _apply_bet_decision_flow(
        self,
        top_bets: list[BetRecommendation],
        matchup: Matchup,
        pred: PredictionResult,
        adjusted_home_prob: float,
        market_result: dict[str, float],
    ) -> list[BetRecommendation]:
        """Apply the institutional 5-gate flow to optimizer output."""
        if not top_bets:
            return []

        sub_model_probs: dict[str, float] = {}
        if pred.sub_model_results:
            for sr in pred.sub_model_results:
                sub_model_probs[sr.model_name] = sr.home_win_prob
        if not sub_model_probs:
            sub_model_probs["ensemble"] = adjusted_home_prob

        sharp_signals: list[str] = []
        if abs(float(getattr(pred, "market_bias_score", 0.0))) >= 0.03:
            sharp_signals.append("market_bias")
        if int(market_result.get("n_steam_moves", 0)) > 0:
            sharp_signals.append("steam")

        approved_bets: list[BetRecommendation] = []
        cumulative_exposure = float(self.bankroll.daily_exposure_pct)
        market_efficiency = max(
            0.0,
            min(1.0, 0.55 + float(market_result.get("market_weight_applied", 0.0))),
        )
        tsl_matchup_status = pred.diagnostics.get("tsl_matchup") if pred.diagnostics else None

        for bet in top_bets:
            market_support_state = (
                classify_market_support_state(bet, tsl_matchup_status if isinstance(tsl_matchup_status, dict) else None)
                if str(getattr(bet, "sportsbook", "")) == "TSL"
                else "intl_only"
            )

            ctx = DecisionContext(
                prediction=pred,
                sub_model_probs=sub_model_probs,
                market_implied_prob=float(bet.implied_probability),
                model_prob=float(bet.win_probability),
                odds=float(1.0 / max(bet.implied_probability, 0.01)),
                bankroll=float(self.bankroll.current),
                daily_exposure_pct=cumulative_exposure,
                peak_bankroll=float(self.bankroll.peak),
                consecutive_losses=int(self.bankroll.consecutive_losses),
                sharp_signals=sharp_signals,
                steam_detected=bool(market_result.get("n_steam_moves", 0)),
                market_efficiency=market_efficiency,
                home_code=matchup.home.team,
                away_code=matchup.away.team,
                market_support_state=market_support_state,
            )
            decision = run_decision_pipeline(bet, ctx)
            if not decision.approved:
                continue

            final_stake_pct = min(float(bet.stake_fraction), float(decision.final_stake_pct or bet.stake_fraction))
            final_stake_amount = min(
                float(bet.stake_amount),
                round(final_stake_pct * float(self.bankroll.current), 2),
            )
            confidence_scale = min(
                1.0,
                final_stake_pct / max(float(bet.stake_fraction), 1e-6),
            )
            approved_bets.append(replace(
                bet,
                stake_fraction=round(final_stake_pct, 4),
                stake_amount=round(final_stake_amount, 0),
                confidence=round(min(1.0, float(bet.confidence) * max(0.6, confidence_scale)), 4),
                approved=True,
                decision_timing=decision.timing,
                delay_minutes=decision.delay_minutes,
                reason=f"{bet.reason}; gate_summary={decision.summary}",
            ))
            cumulative_exposure += final_stake_pct

        return approved_bets

    def _run_portfolio_optimization(
        self,
        top_bets: list[BetRecommendation],
        decision_rpt: DecisionReport,
        matchup: Matchup | None = None,
    ) -> dict[str, float]:
        """Run portfolio-level risk optimization via Phase 7 portfolio_risk engine."""
        if not top_bets:
            return {"survival_prob": 1.0, "cvar_95": 0.0, "drawdown_scale": 1.0}

        # Keep portfolio risk state aligned with runtime bankroll snapshot.
        self.portfolio_risk.state.bankroll = float(self.bankroll.current)
        self.portfolio_risk.state.peak_bankroll = float(self.bankroll.peak)

        tournament = matchup.tournament if matchup else "WBC"
        round_name = matchup.round_name if matchup else "Pool"
        game_date = ""
        if matchup and getattr(matchup, "game_time_utc", ""):
            game_date = str(matchup.game_time_utc)[:10]

        market_support_performance = self._load_market_support_performance_summary()
        proposals: list[BetProposal] = []
        for b in top_bets:
            support_state = str(getattr(b, "market_support_state", "") or "unknown")
            support_mult = self._performance_adjusted_support_multiplier(
                support_state,
                market_support_performance,
            )
            proposals.append(BetProposal(
                game_id=f"{b.market}:{b.side}",
                market=b.market,
                side=b.side,
                win_prob=float(b.win_probability),
                odds=2.0 if b.implied_probability <= 0 else float(1.0 / b.implied_probability),
                ev=float(b.ev),
                edge=float(b.edge),
                individual_kelly=float(max(0.0, b.kelly_fraction) * support_mult),
                confidence=float(min(1.0, max(0.0, b.confidence) * support_mult)),
                tournament=tournament,
                game_date=game_date,
                group=round_name,
            ))

        sizing = self.portfolio_risk.size_portfolio(proposals)
        tsl_status = read_tsl_fetch_status()
        tsl_health = classify_tsl_feed_status(tsl_status)
        tsl_matchup = self._lookup_tsl_matchup_snapshot(matchup) if matchup else None
        avg_stake = float(sum(p.stake_fraction for p in sizing.positions) / max(1, len(sizing.positions)))
        avg_prob = float(sum(p.bet.win_prob for p in sizing.positions) / max(1, len(sizing.positions)))
        avg_odds = float(sum(p.bet.odds for p in sizing.positions) / max(1, len(sizing.positions)))
        ruin_metrics = compute_risk_of_ruin(
            bankroll=self.portfolio_risk.state.bankroll,
            avg_bet_size=max(0.0001, avg_stake),
            win_rate=max(0.01, min(0.99, avg_prob)),
            avg_odds=max(1.01, avg_odds),
            ruin_threshold=0.10,
        )

        risk_level = sizing.risk_level
        portfolio_warnings = list(sizing.warnings)
        if tsl_health["state"] == "blocked":
            portfolio_warnings.append("TSL pre-match feed blocked; Taiwan-market recommendations are running in degraded mode")
            if risk_level == "GREEN":
                risk_level = "YELLOW"
        elif tsl_health["stale_or_degraded"]:
            portfolio_warnings.append(f"TSL feed {tsl_health['state']}; verify market freshness before execution")
        elif tsl_matchup and not tsl_matchup.get("in_snapshot", False):
            portfolio_warnings.append("TSL feed healthy, but this matchup is not listed in the latest Taiwan-market snapshot")

        market_support_profile, market_support_breakdown = self._summarize_market_support(top_bets)
        market_support_tilt = "neutral"
        if market_support_profile == "tsl_direct":
            market_support_tilt = "direct_favored"
        elif market_support_profile in {"tsl_stale", "tsl_unlisted_market", "tsl_unlisted_matchup"}:
            market_support_tilt = "degraded_caution"
        elif market_support_profile == "intl_only":
            market_support_tilt = "international_favored"

        support_adjustments: dict[str, float] = {}
        for state in market_support_breakdown:
            support_adjustments[state] = self._performance_adjusted_support_multiplier(
                state,
                market_support_performance,
            )

        return {
            "survival_prob": round(max(0.0001, 1.0 - float(ruin_metrics.get("risk_of_ruin", 1.0))), 4),
            "cvar_95": round(-float(sizing.portfolio_variance), 6),
            "expected_return": round(float(sizing.expected_daily_return), 6),
            "gross_exposure": round(float(sizing.total_exposure), 4),
            "drawdown_scale": round(max(0.3, 1.0 - float(self.portfolio_risk.state.drawdown) * 2.0), 4),
            "current_drawdown": round(float(self.portfolio_risk.state.drawdown), 4),
            "decision_verdict": decision_rpt.decision,
            "edge_score": decision_rpt.edge_score,
            "risk_level": risk_level,
            "risk_of_ruin": float(ruin_metrics.get("risk_of_ruin", 1.0)),
            "warnings": portfolio_warnings,
            "data_quality_risk": tsl_health["severity"],
            "tsl_feed_state": tsl_health["state"],
            "tsl_feed_summary": tsl_health["summary"],
            "tsl_matchup_in_snapshot": bool(tsl_matchup.get("in_snapshot")) if tsl_matchup else False,
            "tsl_matchup_market_count": int(tsl_matchup.get("market_count", 0)) if tsl_matchup else 0,
            "market_support_profile": market_support_profile,
            "market_support_breakdown": market_support_breakdown,
            "market_support_tilt": market_support_tilt,
            "market_support_adjustments": support_adjustments,
        }

    def _run_calibration_monitoring(self) -> dict[str, float] | None:
        """Run calibration and drift detection on accumulated predictions."""
        if len(self._prob_history) < 10:
            return None

        from wbc_backend.research.infrastructure import (
            calibration_monitoring,
            drift_detection,
        )

        # Use stored outcomes (fill with 0.5-rounded proxy if no actuals yet)
        n = len(self._prob_history)
        if len(self._outcome_history) < n:
            # Pad with rounded probabilities as proxy until actuals arrive
            for i in range(len(self._outcome_history), n):
                self._outcome_history.append(int(self._prob_history[i] >= 0.5))

        cal = calibration_monitoring(self._prob_history, self._outcome_history)

        # Drift detection: compare first half vs second half
        drift_metrics: dict[str, float] = {}
        if n >= 20:
            mid = n // 2
            drift_metrics = drift_detection(
                self._prob_history[:mid],
                self._prob_history[mid:],
            )

        return {
            "brier": cal["brier"],
            "logloss": cal["logloss"],
            "ece": cal["ece"],
            "mce": cal["mce"],
            "n_predictions": float(n),
            **drift_metrics,
        }

    def record_outcome(  # NOSONAR
        self,
        actual_home_win: int,
        *,
        pnl: float = 0.0,
        stake: float = 0.0,
        game_id: str = "",
        market: str = "ML",
        side: str = "",
        odds: float = 0.0,
    ) -> None:
        """Record an actual game outcome for calibration tracking."""
        self._outcome_history.append(actual_home_win)

        if self._prob_history:
            try:
                cl_result = self.continuous_learning.process_game_result(
                    game_id=game_id or "unknown",
                    predicted_prob=float(self._prob_history[-1]),
                    actual_outcome=int(actual_home_win),
                    tournament="WBC",
                    round_name="Pool",
                    bet_pnl=float(pnl),
                )
                logger.info(
                    "[CONTINUOUS_LEARNING] game=%s status=%s actions=%s",
                    game_id or "unknown",
                    cl_result.get("system_status", "UNKNOWN"),
                    ",".join(cl_result.get("actions", [])) or "none",
                )
            except Exception as exc:
                logger.warning("Continuous learning update failed: %s", exc)

        # Update dynamic ensemble weights only after actual outcome is known.
        if game_id and self._prob_history:
            try:
                if self._last_sub_model_results:
                    record_ensemble_outcome(
                        sub_results=self._last_sub_model_results,
                        actual_home_win=int(actual_home_win),
                        tournament=self._last_tournament,
                        round_name=self._last_round_name,
                    )
            except Exception as exc:
                logger.warning("Dynamic ensemble outcome update failed: %s", exc)

        has_financial_update = stake > 0 or abs(pnl) > 1e-12
        if has_financial_update:
            update_bankroll(self.bankroll, pnl=pnl, stake=stake)
            if hasattr(self.decision_engine, "risk") and hasattr(self.decision_engine.risk, "state"):
                self.decision_engine.risk.state.current_bankroll = self.bankroll.current
                self.decision_engine.risk.state.peak_bankroll = max(
                    getattr(self.decision_engine.risk.state, "peak_bankroll", self.bankroll.peak),
                    self.bankroll.peak,
                )
            self.bankroll_storage.save(self.bankroll)
            if game_id:
                self.bankroll_storage.record_bet(
                    game_id=game_id,
                    market=market,
                    side=side,
                    odds=odds,
                    stake_pct=(stake / self.bankroll.current) if self.bankroll.current > 0 else 0.0,
                    stake_amount=stake,
                    pnl=pnl,
                    won=pnl >= 0,
                    bankroll_after=self.bankroll.current,
                    metadata={"actual_home_win": actual_home_win},
                )

        if has_financial_update:
            try:
                self.portfolio_risk.record_outcome(
                    game_id=game_id or "unknown",
                    pnl=float(pnl),
                    stake_amount=float(stake),
                )
            except Exception as exc:
                logger.warning("Portfolio risk outcome update failed: %s", exc)
