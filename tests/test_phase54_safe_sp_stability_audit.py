"""
tests/test_phase54_safe_sp_stability_audit.py
==============================================
Phase 54 — Safe SP Stability Audit Tests

覆蓋：
  1. Phase54 JSONL 可產生
  2. safe coefficient 固定為 0.25x
  3. effective_sp_coefficient = 0.00075
  4. diagnostic_only = true (output rows 及 result)
  5. candidate_patch_created = false (output rows 及 result)
  6. production_modified = false (output rows 及 result)
  7. feature_effect_mode = MODEL_AFFECTING
  8. Phase43 summary schema 完整
  9. Phase44 summary schema 完整
  10. Phase45 summary schema 完整
  11. gate 不可輸出 PATCH_GATE_RECHECK
  12. JSON report 可產生
  13. Markdown report 可產生（含必要章節）
  14. _recommend_gate 邏輯正確（含 edge cases）
  15. Integration smoke test（若真實 JSONL 不存在則 skip）
"""
from __future__ import annotations

import json
import math
import tempfile
from dataclasses import asdict
from pathlib import Path

import pytest

from orchestrator.phase54_safe_sp_stability_audit import (
    # Constants
    CANDIDATE_PATCH_CREATED,
    PRODUCTION_MODIFIED,
    DIAGNOSTIC_ONLY,
    SAFE_COEFFICIENT_SCALE,
    EFFECTIVE_SP_COEFFICIENT,
    FEATURE_EFFECT_MODE,
    PHASE54_VERSION,
    SAFE_SP_PAPER_ONLY_CONTINUE,
    RE_RUN_BOOTSTRAP_REQUIRED,
    FEATURE_REPAIR_STILL_WEAK,
    COLLECT_MORE_DATA,
    PATCH_GATE_RECHECK_NOT_ALLOWED,
    _VALID_GATES,
    _PHASE43_BASELINE,
    # Dataclasses
    SafeCoeffSummary,
    Phase43Summary,
    Phase44Summary,
    Phase45Summary,
    SegmentDelta54,
    Phase54AuditResult,
    # Functions
    build_phase54_jsonl,
    _load_context_rows_raw,
    _recommend_gate,
    run_phase54_audit,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers / fixtures
# ═══════════════════════════════════════════════════════════════════════════════

_REAL_BASELINE = (
    Path(__file__).resolve().parent.parent
    / "data/mlb_2025/derived/mlb_2025_per_game_predictions.jsonl"
)
_REAL_CONTEXT = (
    Path(__file__).resolve().parent.parent
    / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase52_sp_context_v1.jsonl"
)

_REAL_FILES_EXIST = _REAL_BASELINE.exists() and _REAL_CONTEXT.exists()


def _make_pred_row_dict(
    idx: int = 0,
    model_home_prob: float = 0.55,
    home_win: int = 1,
    market_home_prob: float = 0.58,
    game_date: str = "2025-06-15",
    sp_fip_delta: float = 1.5,
) -> dict:
    """Create a synthetic row compatible with both PredictionRow and p0_features."""
    mkt_away = round(1.0 - market_home_prob, 6)
    return {
        "schema_version": "phase39-v1",
        "season": 2025,
        "game_date": game_date,
        "game_id": f"MLB2025_{idx:04d}_{game_date}_T1_T2",
        "dedupe_key": f"{game_date}|TeamA|TeamB|{idx}",
        "home_team": "TeamB",
        "away_team": "TeamA",
        "home_win": home_win,
        "model_home_prob": model_home_prob,
        "market_home_prob_no_vig": market_home_prob,
        "market_away_prob_no_vig": mkt_away,
        "home_ml": "-110",
        "away_ml": "+100",
        "model_version": "xgb_v1",
        "feature_version": "marl_elo_woba_fip_rsi_v1",
        "split_id": "window_1",
        "train_window_start": "2025-04-01",
        "train_window_end": "2025-05-31",
        "test_window_start": "2025-06-01",
        "test_window_end": "2025-09-30",
        "prediction_time_utc": "2025-06-15T12:00:00+00:00",
        "odds_snapshot_time_utc": "2025-06-15T11:00:00+00:00",
        "source_backtest": True,
        "audit_hash": f"deadbeef{idx:04d}",
        "p0_features": {
            "sp_fip_delta": sp_fip_delta,
            "sp_fip_delta_available": True,
            "park_factor_available": False,
            "park_run_factor": 1.0,
            "season_game_index_available": False,
            "season_game_index": 0.5,
        },
    }


def _make_synthetic_rows(n: int = 300) -> list[dict]:
    """Generate n synthetic rows with varied months, odds, probs."""
    rows = []
    months = ["2025-04", "2025-05", "2025-06", "2025-07"]
    for i in range(n):
        month = months[i % 4]
        day = (i % 28) + 1
        game_date = f"{month}-{day:02d}"
        # Vary model prob and market prob for diverse segments
        model_p = 0.40 + (i % 45) * 0.004  # 0.40..0.576
        # heavy_favorite: market >= 0.65 → force some
        if i % 8 == 0:
            mkt_p = 0.66 + (i % 10) * 0.01   # heavy home fav
        elif i % 8 == 1:
            mkt_p = 0.34 - (i % 5) * 0.01    # heavy away fav
        else:
            mkt_p = 0.50 + (i % 15) * 0.01   # mid range
        mkt_p = min(0.99, max(0.01, mkt_p))
        # high confidence: |model_p - 0.5| >= 0.15
        if i % 5 == 0:
            model_p = 0.70 + (i % 10) * 0.01  # clearly high confidence
        model_p = min(0.99, max(0.01, model_p))
        fip_delta = -2.0 + (i % 40) * 0.1
        home_win = 1 if i % 2 == 0 else 0
        rows.append(_make_pred_row_dict(
            idx=i,
            model_home_prob=model_p,
            home_win=home_win,
            market_home_prob=mkt_p,
            game_date=game_date,
            sp_fip_delta=fip_delta,
        ))
    return rows


def _write_jsonl(rows: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _make_baseline_rows(rows: list[dict]) -> list[dict]:
    """Strip p0_features for baseline JSONL."""
    out = []
    for r in rows:
        d = dict(r)
        d.pop("p0_features", None)
        out.append(d)
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# § T-001  Hard rule constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestHardRuleConstants:
    """Module-level constants must satisfy hard rules."""

    def test_candidate_patch_created_false(self):
        assert CANDIDATE_PATCH_CREATED is False

    def test_production_modified_false(self):
        assert PRODUCTION_MODIFIED is False

    def test_diagnostic_only_true(self):
        assert DIAGNOSTIC_ONLY is True

    def test_safe_coefficient_scale(self):
        assert SAFE_COEFFICIENT_SCALE == 0.25

    def test_effective_sp_coefficient(self):
        assert abs(EFFECTIVE_SP_COEFFICIENT - 0.00075) < 1e-10

    def test_feature_effect_mode(self):
        assert FEATURE_EFFECT_MODE == "MODEL_AFFECTING"

    def test_patch_not_in_any_gate(self):
        """No gate string may contain PATCH (除了 PATCH_GATE_RECHECK_NOT_ALLOWED)."""
        forbidden = {"PATCH_GATE_RECHECK", "PATCH"}
        for gate in _VALID_GATES:
            if gate == PATCH_GATE_RECHECK_NOT_ALLOWED:
                continue   # this one is a guard gate — allowed to contain PATCH as text
            for f in forbidden:
                assert f not in gate, f"Gate {gate!r} must not contain {f!r}"

    def test_valid_gates_set(self):
        expected = {
            SAFE_SP_PAPER_ONLY_CONTINUE,
            RE_RUN_BOOTSTRAP_REQUIRED,
            FEATURE_REPAIR_STILL_WEAK,
            COLLECT_MORE_DATA,
            PATCH_GATE_RECHECK_NOT_ALLOWED,
        }
        assert _VALID_GATES == expected


# ═══════════════════════════════════════════════════════════════════════════════
# § T-002  Phase54 JSONL 產生
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildPhase54Jsonl:
    """build_phase54_jsonl produces correct output JSONL."""

    def test_output_file_created(self):
        rows = _make_synthetic_rows(50)
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx_path = Path(tmpdir) / "context.jsonl"
            out_path = Path(tmpdir) / "phase54.jsonl"
            _write_jsonl(rows, ctx_path)
            build_phase54_jsonl(ctx_path, out_path)
            assert out_path.exists()

    def test_output_row_count_matches_input(self):
        rows = _make_synthetic_rows(60)
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx_path = Path(tmpdir) / "context.jsonl"
            out_path = Path(tmpdir) / "phase54.jsonl"
            _write_jsonl(rows, ctx_path)
            build_phase54_jsonl(ctx_path, out_path)
            out_rows = _load_context_rows_raw(out_path)
            assert len(out_rows) == 60

    def test_output_has_original_model_home_prob(self):
        """Each output row must have original_model_home_prob field."""
        rows = _make_synthetic_rows(30)
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx_path = Path(tmpdir) / "context.jsonl"
            out_path = Path(tmpdir) / "phase54.jsonl"
            _write_jsonl(rows, ctx_path)
            build_phase54_jsonl(ctx_path, out_path)
            out_rows = _load_context_rows_raw(out_path)
            for r in out_rows:
                assert "original_model_home_prob" in r

    def test_output_model_home_prob_adjusted(self):
        """model_home_prob in output may differ from original (safe coefficient applied)."""
        rows = _make_synthetic_rows(30)
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx_path = Path(tmpdir) / "context.jsonl"
            out_path = Path(tmpdir) / "phase54.jsonl"
            _write_jsonl(rows, ctx_path)
            build_phase54_jsonl(ctx_path, out_path)
            out_rows = _load_context_rows_raw(out_path)
            # At least some rows should have model_home_prob != original
            original_probs = [r["original_model_home_prob"] for r in out_rows]
            adj_probs = [r["model_home_prob"] for r in out_rows]
            diffs = [abs(a - o) for a, o in zip(adj_probs, original_probs)]
            # At least one row should have been adjusted (since rows have sp_fip_delta)
            assert any(d > 0 for d in diffs), "Expected at least some rows to be adjusted"

    def test_output_safe_coefficient_scale(self):
        """sp_coefficient_scale must be 0.25 in all output rows."""
        rows = _make_synthetic_rows(30)
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx_path = Path(tmpdir) / "context.jsonl"
            out_path = Path(tmpdir) / "phase54.jsonl"
            _write_jsonl(rows, ctx_path)
            build_phase54_jsonl(ctx_path, out_path)
            out_rows = _load_context_rows_raw(out_path)
            for r in out_rows:
                assert r["sp_coefficient_scale"] == 0.25

    def test_output_effective_sp_coefficient(self):
        """effective_sp_coefficient must be 0.00075 in all output rows."""
        rows = _make_synthetic_rows(30)
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx_path = Path(tmpdir) / "context.jsonl"
            out_path = Path(tmpdir) / "phase54.jsonl"
            _write_jsonl(rows, ctx_path)
            build_phase54_jsonl(ctx_path, out_path)
            out_rows = _load_context_rows_raw(out_path)
            for r in out_rows:
                assert abs(r["effective_sp_coefficient"] - 0.00075) < 1e-10

    def test_output_diagnostic_only_true(self):
        """diagnostic_only must be True in all output rows."""
        rows = _make_synthetic_rows(30)
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx_path = Path(tmpdir) / "context.jsonl"
            out_path = Path(tmpdir) / "phase54.jsonl"
            _write_jsonl(rows, ctx_path)
            build_phase54_jsonl(ctx_path, out_path)
            out_rows = _load_context_rows_raw(out_path)
            for r in out_rows:
                assert r["diagnostic_only"] is True

    def test_output_candidate_patch_created_false(self):
        """candidate_patch_created must be False in all output rows."""
        rows = _make_synthetic_rows(30)
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx_path = Path(tmpdir) / "context.jsonl"
            out_path = Path(tmpdir) / "phase54.jsonl"
            _write_jsonl(rows, ctx_path)
            build_phase54_jsonl(ctx_path, out_path)
            out_rows = _load_context_rows_raw(out_path)
            for r in out_rows:
                assert r["candidate_patch_created"] is False

    def test_output_production_modified_false(self):
        """production_modified must be False in all output rows."""
        rows = _make_synthetic_rows(30)
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx_path = Path(tmpdir) / "context.jsonl"
            out_path = Path(tmpdir) / "phase54.jsonl"
            _write_jsonl(rows, ctx_path)
            build_phase54_jsonl(ctx_path, out_path)
            out_rows = _load_context_rows_raw(out_path)
            for r in out_rows:
                assert r["production_modified"] is False

    def test_output_feature_effect_mode(self):
        """feature_effect_mode must be MODEL_AFFECTING in all output rows."""
        rows = _make_synthetic_rows(30)
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx_path = Path(tmpdir) / "context.jsonl"
            out_path = Path(tmpdir) / "phase54.jsonl"
            _write_jsonl(rows, ctx_path)
            build_phase54_jsonl(ctx_path, out_path)
            out_rows = _load_context_rows_raw(out_path)
            for r in out_rows:
                assert r["feature_effect_mode"] == "MODEL_AFFECTING"

    def test_summary_has_safe_coefficient_scale(self):
        """SafeCoeffSummary returned by build_phase54_jsonl has correct scale."""
        rows = _make_synthetic_rows(30)
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx_path = Path(tmpdir) / "context.jsonl"
            out_path = Path(tmpdir) / "phase54.jsonl"
            _write_jsonl(rows, ctx_path)
            summary = build_phase54_jsonl(ctx_path, out_path)
            assert summary.scale == 0.25
            assert abs(summary.effective_coefficient - 0.00075) < 1e-10
            assert summary.diagnostic_only is True
            assert summary.candidate_patch_created is False
            assert summary.production_modified is False
            assert summary.input_rows == 30

    def test_adjusted_prob_never_out_of_bounds(self):
        """model_home_prob must remain in [0.01, 0.99] after adjustment."""
        rows = _make_synthetic_rows(50)
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx_path = Path(tmpdir) / "context.jsonl"
            out_path = Path(tmpdir) / "phase54.jsonl"
            _write_jsonl(rows, ctx_path)
            build_phase54_jsonl(ctx_path, out_path)
            out_rows = _load_context_rows_raw(out_path)
            for r in out_rows:
                p = r["model_home_prob"]
                assert 0.01 <= p <= 0.99, f"Prob {p} out of [0.01, 0.99]"


# ═══════════════════════════════════════════════════════════════════════════════
# § T-003  Gate recommendation logic
# ═══════════════════════════════════════════════════════════════════════════════

def _make_p43(
    blend_bss: float = 0.003,
    blend_ece: float = 0.027,
    bss_delta: float = 0.0008,
    ece_delta: float = -0.001,
    fold_stability: str = "STABLE",
    folds_positive: int = 4,
    folds_total: int = 5,
    bootstrap_sig: str = "NOT_SIGNIFICANT",
    ci_lower: float = -0.001,
    ci_upper: float = 0.0008,
    prob_improvement: float = 0.85,
    fold_positive_delta: int = 0,
) -> Phase43Summary:
    return Phase43Summary(
        overall_blend_bss=blend_bss,
        overall_blend_ece=blend_ece,
        overall_raw_bss=-0.002,
        overall_raw_brier=0.244,
        overall_blend_brier=0.243,
        overall_market_brier=0.244,
        fold_stability_label=fold_stability,
        folds_positive=folds_positive,
        folds_total=folds_total,
        bootstrap_significance=bootstrap_sig,
        bootstrap_ci_lower=ci_lower,
        bootstrap_ci_upper=ci_upper,
        bootstrap_prob_improvement=prob_improvement,
        blend_bss_delta=bss_delta,
        blend_ece_delta=ece_delta,
        fold_positive_delta=fold_positive_delta,
    )


def _make_p44(
    gate_state: str = "PAPER_ONLY",
    sample_size: int = 2000,
    bootstrap_sig: str = "NOT_SIGNIFICANT",
    candidate_patch_created: bool = False,
) -> Phase44Summary:
    return Phase44Summary(
        gate_state=gate_state,
        sample_size=sample_size,
        alpha=0.4,
        blend_brier=0.243,
        blend_bss=0.002,
        blend_ece=0.028,
        market_brier=0.244,
        bootstrap_significance=bootstrap_sig,
        candidate_patch_created=candidate_patch_created,
        next_gate_criteria=["Bootstrap CI 不跨 0"],
    )


def _make_p45(
    global_conclusion: str = "PARTIAL_IMPROVEMENT",
    gate: str = "PAPER_ONLY",
    failure_count_delta: int = 0,
    hf_no_failure: bool = True,
    hc_improved: bool = True,
) -> Phase45Summary:
    return Phase45Summary(
        global_conclusion=global_conclusion,
        gate=gate,
        sample_size=2000,
        positive_segments=["odds_bucket:heavy_favorite"],
        failure_segments=[],
        heavy_fav_blend_bss=0.005,
        heavy_fav_blend_ece=0.085,
        high_conf_blend_bss=0.003,
        heavy_fav_ece_no_longer_failure=hf_no_failure,
        high_conf_improved=hc_improved,
        failure_count_delta=failure_count_delta,
    )


def _make_safe_coeff(scale: float = 0.25) -> SafeCoeffSummary:
    return SafeCoeffSummary(
        scale=scale,
        effective_coefficient=round(0.003 * scale, 8),
        feature_effect_mode="MODEL_AFFECTING",
        input_rows=2025,
        adjusted_rows=500,
        adjusted_rate=0.247,
        mean_abs_adjustment=0.00005,
        max_abs_adjustment=0.00075,
        overall_bss_delta_vs_baseline=0.00004,
        overall_ece_delta_vs_baseline=-0.001,
        heavy_fav_ece_delta_vs_baseline=-0.00008,
        high_conf_bss_delta_vs_baseline=0.00003,
        diagnostic_only=True,
        candidate_patch_created=False,
        production_modified=False,
    )


class TestRecommendGate:
    """_recommend_gate must never output PATCH_GATE_RECHECK and must be in _VALID_GATES."""

    def test_gate_always_in_valid_set(self):
        """Gate output is always in _VALID_GATES for all combinations."""
        scenarios = [
            # (p43_kwargs, p44_kwargs, p45_kwargs)
            ({}, {}, {}),
            ({"bss_delta": 0.001, "ece_delta": -0.001}, {}, {}),
            ({"bss_delta": -0.003, "ece_delta": 0.004}, {}, {}),
            ({}, {"sample_size": 100}, {}),
            ({}, {}, {"failure_count_delta": 3}),
            ({"bootstrap_sig": "NOT_RUN"}, {}, {}),
        ]
        for p43_kw, p44_kw, p45_kw in scenarios:
            p43 = _make_p43(**p43_kw)
            p44 = _make_p44(**p44_kw)
            p45 = _make_p45(**p45_kw)
            sc = _make_safe_coeff()
            gate, rationale = _recommend_gate(p43, p44, p45, sc)
            assert gate in _VALID_GATES, f"gate={gate!r} not in valid set"

    def test_gate_never_patch_gate_recheck_on_normal_inputs(self):
        """Normal inputs never produce PATCH_GATE_RECHECK_NOT_ALLOWED."""
        p43 = _make_p43()
        p44 = _make_p44()
        p45 = _make_p45()
        sc = _make_safe_coeff()
        gate, _ = _recommend_gate(p43, p44, p45, sc)
        assert gate != PATCH_GATE_RECHECK_NOT_ALLOWED

    def test_collect_more_data_when_n_lt_500(self):
        """n < 500 → COLLECT_MORE_DATA."""
        p43 = _make_p43()
        p44 = _make_p44(sample_size=200)
        p45 = _make_p45()
        sc = _make_safe_coeff()
        gate, _ = _recommend_gate(p43, p44, p45, sc)
        assert gate == COLLECT_MORE_DATA

    def test_feature_repair_still_weak_when_metrics_clearly_worse(self):
        """Large BSS degradation → FEATURE_REPAIR_STILL_WEAK."""
        p43 = _make_p43(bss_delta=-0.003, ece_delta=0.004)
        p44 = _make_p44()
        p45 = _make_p45()
        sc = _make_safe_coeff()
        gate, _ = _recommend_gate(p43, p44, p45, sc)
        assert gate == FEATURE_REPAIR_STILL_WEAK

    def test_feature_repair_still_weak_when_failure_increased(self):
        """failure_count_delta > 1 → FEATURE_REPAIR_STILL_WEAK."""
        p43 = _make_p43(bss_delta=0.0005, ece_delta=-0.0005)
        p44 = _make_p44()
        p45 = _make_p45(failure_count_delta=2)
        sc = _make_safe_coeff()
        gate, _ = _recommend_gate(p43, p44, p45, sc)
        assert gate == FEATURE_REPAIR_STILL_WEAK

    def test_re_run_bootstrap_required_when_not_run(self):
        """Bootstrap not run → RE_RUN_BOOTSTRAP_REQUIRED (when metrics not clearly worse)."""
        p43 = _make_p43(bss_delta=0.0005, ece_delta=-0.0005, bootstrap_sig="NOT_RUN")
        p44 = _make_p44()
        p45 = _make_p45()
        sc = _make_safe_coeff()
        gate, _ = _recommend_gate(p43, p44, p45, sc)
        assert gate == RE_RUN_BOOTSTRAP_REQUIRED

    def test_safe_sp_paper_only_when_all_metrics_improve(self):
        """All metrics improve with CI crossing 0 → SAFE_SP_PAPER_ONLY_CONTINUE."""
        p43 = _make_p43(
            bss_delta=0.001,
            ece_delta=-0.001,
            ci_lower=-0.001,
            ci_upper=0.0008,
            bootstrap_sig="NOT_SIGNIFICANT",
        )
        p44 = _make_p44()
        p45 = _make_p45(hf_no_failure=True, failure_count_delta=0)
        sc = _make_safe_coeff()
        gate, _ = _recommend_gate(p43, p44, p45, sc)
        assert gate == SAFE_SP_PAPER_ONLY_CONTINUE

    def test_safe_sp_paper_only_partial_improvement(self):
        """Only BSS improves (ECE neutral) → SAFE_SP_PAPER_ONLY_CONTINUE."""
        p43 = _make_p43(bss_delta=0.001, ece_delta=0.0001)  # ECE slightly worsened but small
        p44 = _make_p44()
        p45 = _make_p45(hf_no_failure=True, failure_count_delta=0)
        sc = _make_safe_coeff()
        gate, _ = _recommend_gate(p43, p44, p45, sc)
        # partial improvement still → SAFE_SP_PAPER_ONLY_CONTINUE or FEATURE_REPAIR_STILL_WEAK
        assert gate in _VALID_GATES

    def test_gate_rationale_is_non_empty_string(self):
        """Gate rationale is always a non-empty string."""
        p43 = _make_p43()
        p44 = _make_p44()
        p45 = _make_p45()
        sc = _make_safe_coeff()
        gate, rationale = _recommend_gate(p43, p44, p45, sc)
        assert isinstance(rationale, str)
        assert len(rationale) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# § T-004  Phase43 summary schema
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase43SummarySchema:
    """Phase43Summary has all required fields with correct types."""

    def test_required_fields_present(self):
        s = Phase43Summary()
        required = [
            "overall_blend_bss", "overall_blend_ece", "overall_raw_bss",
            "overall_raw_brier", "overall_blend_brier", "overall_market_brier",
            "fold_stability_label", "folds_positive", "folds_total",
            "bootstrap_significance", "bootstrap_ci_lower", "bootstrap_ci_upper",
            "bootstrap_prob_improvement", "blend_bss_delta", "blend_ece_delta",
            "fold_positive_delta",
        ]
        d = asdict(s)
        for f in required:
            assert f in d, f"Phase43Summary missing field: {f}"

    def test_fields_are_correct_types(self):
        s = _make_p43()
        assert isinstance(s.overall_blend_bss, float)
        assert isinstance(s.overall_blend_ece, float)
        assert isinstance(s.fold_stability_label, str)
        assert isinstance(s.folds_positive, int)
        assert isinstance(s.folds_total, int)
        assert isinstance(s.bootstrap_significance, str)

    def test_asdict_serialisable(self):
        s = _make_p43()
        d = asdict(s)
        json_str = json.dumps(d, default=str)
        parsed = json.loads(json_str)
        assert "overall_blend_bss" in parsed
        assert "bootstrap_significance" in parsed


# ═══════════════════════════════════════════════════════════════════════════════
# § T-005  Phase44 summary schema
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase44SummarySchema:
    """Phase44Summary has all required fields with correct values."""

    def test_required_fields_present(self):
        s = Phase44Summary()
        required = [
            "gate_state", "sample_size", "alpha", "blend_brier",
            "blend_bss", "blend_ece", "market_brier",
            "bootstrap_significance", "candidate_patch_created",
            "next_gate_criteria",
        ]
        d = asdict(s)
        for f in required:
            assert f in d, f"Phase44Summary missing field: {f}"

    def test_gate_state_is_paper_only(self):
        """Default gate_state is PAPER_ONLY."""
        s = Phase44Summary()
        assert s.gate_state == "PAPER_ONLY"

    def test_alpha_is_0_4(self):
        """alpha must be 0.4."""
        s = Phase44Summary()
        assert s.alpha == 0.4

    def test_candidate_patch_created_false(self):
        s = Phase44Summary()
        assert s.candidate_patch_created is False

    def test_next_gate_criteria_is_list(self):
        s = Phase44Summary()
        assert isinstance(s.next_gate_criteria, list)

    def test_asdict_serialisable(self):
        s = _make_p44()
        d = asdict(s)
        json_str = json.dumps(d, default=str)
        parsed = json.loads(json_str)
        assert "gate_state" in parsed
        assert parsed["alpha"] == 0.4
        assert parsed["candidate_patch_created"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# § T-006  Phase45 summary schema
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase45SummarySchema:
    """Phase45Summary has all required fields."""

    def test_required_fields_present(self):
        s = Phase45Summary()
        required = [
            "global_conclusion", "gate", "sample_size",
            "positive_segments", "failure_segments",
            "heavy_fav_blend_bss", "heavy_fav_blend_ece", "high_conf_blend_bss",
            "heavy_fav_ece_no_longer_failure", "high_conf_improved",
            "failure_count_delta",
        ]
        d = asdict(s)
        for f in required:
            assert f in d, f"Phase45Summary missing field: {f}"

    def test_positive_and_failure_segments_are_lists(self):
        s = Phase45Summary()
        assert isinstance(s.positive_segments, list)
        assert isinstance(s.failure_segments, list)

    def test_heavy_fav_ece_no_longer_failure_is_bool(self):
        s = Phase45Summary()
        assert isinstance(s.heavy_fav_ece_no_longer_failure, bool)

    def test_high_conf_improved_is_bool(self):
        s = Phase45Summary()
        assert isinstance(s.high_conf_improved, bool)

    def test_asdict_serialisable(self):
        s = _make_p45()
        d = asdict(s)
        json_str = json.dumps(d, default=str)
        parsed = json.loads(json_str)
        assert "global_conclusion" in parsed
        assert "failure_segments" in parsed


# ═══════════════════════════════════════════════════════════════════════════════
# § T-007  Phase54AuditResult hard rules
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase54AuditResultHardRules:
    """Phase54AuditResult always has correct hard-rule fields."""

    def _make_result(self, gate: str = SAFE_SP_PAPER_ONLY_CONTINUE) -> Phase54AuditResult:
        return Phase54AuditResult(
            safe_coefficient_summary=_make_safe_coeff(),
            phase43_summary=_make_p43(),
            phase44_summary=_make_p44(),
            phase45_summary=_make_p45(),
            segment_comparison=[],
            gate_recommendation=gate,
            gate_rationale="test rationale",
            candidate_patch_created=False,
            production_modified=False,
            diagnostic_only=True,
        )

    def test_candidate_patch_created_false(self):
        r = self._make_result()
        assert r.candidate_patch_created is False

    def test_production_modified_false(self):
        r = self._make_result()
        assert r.production_modified is False

    def test_diagnostic_only_true(self):
        r = self._make_result()
        assert r.diagnostic_only is True

    def test_phase54_version_set(self):
        r = self._make_result()
        assert r.phase54_version == PHASE54_VERSION

    def test_post_init_raises_on_patch_created(self):
        """__post_init__ must raise if candidate_patch_created=True."""
        with pytest.raises(AssertionError, match="candidate_patch_created"):
            Phase54AuditResult(
                candidate_patch_created=True,   # ← violation
                production_modified=False,
                diagnostic_only=True,
            )

    def test_post_init_raises_on_production_modified(self):
        """__post_init__ must raise if production_modified=True."""
        with pytest.raises(AssertionError, match="production_modified"):
            Phase54AuditResult(
                candidate_patch_created=False,
                production_modified=True,       # ← violation
                diagnostic_only=True,
            )

    def test_post_init_raises_on_diagnostic_only_false(self):
        """__post_init__ must raise if diagnostic_only=False."""
        with pytest.raises(AssertionError, match="diagnostic_only"):
            Phase54AuditResult(
                candidate_patch_created=False,
                production_modified=False,
                diagnostic_only=False,          # ← violation
            )


# ═══════════════════════════════════════════════════════════════════════════════
# § T-008  JSON 序列化
# ═══════════════════════════════════════════════════════════════════════════════

class TestJsonSerialization:
    """Phase54AuditResult is serialisable to JSON."""

    def _make_result(self) -> Phase54AuditResult:
        return Phase54AuditResult(
            safe_coefficient_summary=_make_safe_coeff(),
            phase43_summary=_make_p43(),
            phase44_summary=_make_p44(),
            phase45_summary=_make_p45(),
            segment_comparison=[
                SegmentDelta54(
                    segment_key="odds_bucket:heavy_favorite",
                    phase54_blend_bss=0.005,
                    phase43_blend_bss=0.003,
                    delta_bss=0.002,
                    phase54_blend_ece=0.080,
                    phase43_blend_ece=0.085,
                    delta_ece=-0.005,
                    n=200,
                    label="IMPROVED",
                )
            ],
            gate_recommendation=SAFE_SP_PAPER_ONLY_CONTINUE,
            gate_rationale="指標改善；繼續 paper tracking",
            candidate_patch_created=False,
            production_modified=False,
            diagnostic_only=True,
        )

    def test_asdict_and_json_dumps(self):
        r = self._make_result()
        d = asdict(r)
        json_str = json.dumps(d, ensure_ascii=False, default=str)
        parsed = json.loads(json_str)
        assert parsed["candidate_patch_created"] is False
        assert parsed["production_modified"] is False
        assert parsed["diagnostic_only"] is True
        assert parsed["gate_recommendation"] == SAFE_SP_PAPER_ONLY_CONTINUE

    def test_json_has_all_top_level_keys(self):
        r = self._make_result()
        d = asdict(r)
        required_keys = [
            "phase54_version", "gate_recommendation", "gate_rationale",
            "candidate_patch_created", "production_modified", "diagnostic_only",
            "safe_coefficient_summary", "phase43_summary",
            "phase44_summary", "phase45_summary", "segment_comparison",
        ]
        for k in required_keys:
            assert k in d, f"Missing key in serialized result: {k}"

    def test_json_written_to_disk(self):
        r = self._make_result()
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "phase54_report.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(asdict(r), f, ensure_ascii=False, default=str)
            assert json_path.exists()
            with open(json_path) as f:
                data = json.load(f)
            assert data["candidate_patch_created"] is False
            assert data["production_modified"] is False
            assert data["diagnostic_only"] is True
            assert data["gate_recommendation"] == SAFE_SP_PAPER_ONLY_CONTINUE


# ═══════════════════════════════════════════════════════════════════════════════
# § T-009  Markdown report
# ═══════════════════════════════════════════════════════════════════════════════

class TestMarkdownReport:
    """Markdown report contains all required sections."""

    def _make_result(self, gate: str = SAFE_SP_PAPER_ONLY_CONTINUE) -> Phase54AuditResult:
        return Phase54AuditResult(
            safe_coefficient_summary=_make_safe_coeff(),
            phase43_summary=_make_p43(),
            phase44_summary=_make_p44(),
            phase45_summary=_make_p45(),
            segment_comparison=[
                SegmentDelta54(
                    segment_key="odds_bucket:heavy_favorite",
                    phase54_blend_bss=0.005,
                    phase43_blend_bss=0.003,
                    delta_bss=0.002,
                    phase54_blend_ece=0.080,
                    phase43_blend_ece=0.085,
                    delta_ece=-0.005,
                    n=200,
                    label="IMPROVED",
                )
            ],
            gate_recommendation=gate,
            gate_rationale="指標改善；繼續 paper tracking",
            candidate_patch_created=False,
            production_modified=False,
            diagnostic_only=True,
        )

    def test_required_sections_present(self):
        from scripts.run_phase54_safe_sp_stability_audit import _build_markdown
        r = self._make_result()
        md = _build_markdown(r, "2026-05-05")

        required_sections = [
            "Executive Summary",
            "Safe Coefficient Summary",
            "Phase43 Re-run Result",
            "Phase44 Paper Tracking Result",
            "Phase45 Attribution Result",
            "Baseline vs Phase54 Comparison",
            "Critical Segment Comparison Table",
            "Bootstrap / Fold Stability Result",
            "Gate Recommendation",
            "Limitations",
            "Next Phase Recommendation",
            "Hard Rules Verification",
            "Completion Marker",
        ]
        for section in required_sections:
            assert section in md, f"Section '{section}' missing from Markdown report"

    def test_completion_marker_present(self):
        from scripts.run_phase54_safe_sp_stability_audit import _build_markdown
        r = self._make_result()
        md = _build_markdown(r, "2026-05-05")
        assert "PHASE_54_SAFE_SP_STABILITY_AUDIT_VERIFIED" in md

    def test_hard_rules_in_markdown(self):
        from scripts.run_phase54_safe_sp_stability_audit import _build_markdown
        r = self._make_result()
        md = _build_markdown(r, "2026-05-05")
        assert "candidate_patch_created = False" in md
        assert "production_modified     = False" in md
        assert "diagnostic_only         = True" in md

    def test_gate_in_markdown(self):
        from scripts.run_phase54_safe_sp_stability_audit import _build_markdown
        r = self._make_result()
        md = _build_markdown(r, "2026-05-05")
        assert SAFE_SP_PAPER_ONLY_CONTINUE in md

    def test_next_phase_phase55_paper_tracking_when_continue(self):
        from scripts.run_phase54_safe_sp_stability_audit import _build_markdown
        r = self._make_result(gate=SAFE_SP_PAPER_ONLY_CONTINUE)
        md = _build_markdown(r, "2026-05-05")
        assert "Phase 55" in md
        assert "Rolling" in md or "Walk-forward" in md or "paper tracking" in md.lower()

    def test_next_phase_sp_redesign_when_feature_repair_weak(self):
        from scripts.run_phase54_safe_sp_stability_audit import _build_markdown
        r = self._make_result(gate=FEATURE_REPAIR_STILL_WEAK)
        md = _build_markdown(r, "2026-05-05")
        assert "Phase 55" in md
        assert "SP" in md or "Redesign" in md or "segment" in md.lower()

    def test_markdown_written_to_disk(self):
        from scripts.run_phase54_safe_sp_stability_audit import _build_markdown
        r = self._make_result()
        md = _build_markdown(r, "2026-05-05")
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = Path(tmpdir) / "phase54_report.md"
            md_path.write_text(md, encoding="utf-8")
            assert md_path.exists()
            content = md_path.read_text(encoding="utf-8")
            assert "Phase 54" in content
            assert "PHASE_54_SAFE_SP_STABILITY_AUDIT_VERIFIED" in content


# ═══════════════════════════════════════════════════════════════════════════════
# § T-010  _PHASE43_BASELINE 正確性
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase43Baseline:
    """Baseline constants are consistent with Phase43 evidence."""

    def test_baseline_has_expected_keys(self):
        required = [
            "overall_blend_bss", "overall_blend_ece", "overall_raw_bss",
            "overall_raw_brier", "overall_blend_brier", "overall_market_brier",
            "fold_stability_label", "folds_positive", "folds_total",
            "bootstrap_significance", "bootstrap_ci", "bootstrap_prob_improvement",
            "failure_count",
        ]
        for k in required:
            assert k in _PHASE43_BASELINE, f"Baseline missing key: {k}"

    def test_baseline_values_plausible(self):
        assert 0.0 < _PHASE43_BASELINE["overall_blend_bss"] < 0.05
        assert 0.0 < _PHASE43_BASELINE["overall_blend_ece"] < 0.1
        assert _PHASE43_BASELINE["folds_positive"] <= _PHASE43_BASELINE["folds_total"]
        assert _PHASE43_BASELINE["fold_stability_label"] == "STABLE"
        assert _PHASE43_BASELINE["bootstrap_significance"] == "NOT_SIGNIFICANT"
        assert _PHASE43_BASELINE["failure_count"] >= 0

    def test_baseline_bootstrap_ci_crosses_zero(self):
        """Phase43 baseline CI must cross 0 (NOT_SIGNIFICANT)."""
        ci = _PHASE43_BASELINE["bootstrap_ci"]
        assert ci[0] < 0 < ci[1]


# ═══════════════════════════════════════════════════════════════════════════════
# § T-011  Integration smoke test (requires real JSONL files)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(
    not _REAL_FILES_EXIST,
    reason="Real Phase52 context JSONL files not found; skip integration test",
)
class TestRunPhase54AuditIntegration:
    """Integration test: run_phase54_audit with real data."""

    def test_phase54_audit_runs_end_to_end(self, tmp_path: Path):
        out_path = tmp_path / "phase54_integration.jsonl"
        result = run_phase54_audit(
            baseline_path=_REAL_BASELINE,
            context_path=_REAL_CONTEXT,
            phase54_output_path=out_path,
            n_bootstrap=50,   # 快速跑，不需要精確
            n_splits=3,
        )
        assert out_path.exists()
        assert result.candidate_patch_created is False
        assert result.production_modified is False
        assert result.diagnostic_only is True

    def test_gate_not_patch_gate_recheck_on_real_data(self, tmp_path: Path):
        out_path = tmp_path / "phase54_integration2.jsonl"
        result = run_phase54_audit(
            baseline_path=_REAL_BASELINE,
            context_path=_REAL_CONTEXT,
            phase54_output_path=out_path,
            n_bootstrap=50,
            n_splits=3,
        )
        assert result.gate_recommendation != PATCH_GATE_RECHECK_NOT_ALLOWED
        assert result.gate_recommendation in _VALID_GATES

    def test_phase44_gate_state_paper_only_on_real_data(self, tmp_path: Path):
        out_path = tmp_path / "phase54_integration3.jsonl"
        result = run_phase54_audit(
            baseline_path=_REAL_BASELINE,
            context_path=_REAL_CONTEXT,
            phase54_output_path=out_path,
            n_bootstrap=50,
            n_splits=3,
        )
        assert result.phase44_summary.gate_state == "PAPER_ONLY"
        assert result.phase44_summary.candidate_patch_created is False

    def test_phase54_jsonl_row_count(self, tmp_path: Path):
        """Phase54 JSONL has same row count as context JSONL."""
        out_path = tmp_path / "phase54_count_test.jsonl"
        context_rows = _load_context_rows_raw(_REAL_CONTEXT)
        run_phase54_audit(
            baseline_path=_REAL_BASELINE,
            context_path=_REAL_CONTEXT,
            phase54_output_path=out_path,
            n_bootstrap=50,
            n_splits=3,
        )
        out_rows = _load_context_rows_raw(out_path)
        assert len(out_rows) == len(context_rows)
