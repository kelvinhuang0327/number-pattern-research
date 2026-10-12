"""Phase 72 — Paper-only Market De-risk Guard Proposal for Compressed 0.65–0.70 Band

PROPOSAL ONLY. NO PRODUCTION PATCH. NO AUTOMATIC EXECUTION.
CANDIDATE_PATCH_CREATED = False. PRODUCTION_MODIFIED = False. ALPHA_MODIFIED = False.

Phase 72 does NOT touch:
  - production model / stacking_model.py
  - production market_blend alpha (frozen at 0.40)
  - prediction JSONL
  - any betting execution / bankroll / stake logic

Background (from Phase 71 — MARKET_DE_RISK_GUARD_PROMISING):
  - target band: model_home_prob ∈ [0.65, 0.70)
  - model Brier = 0.1865, market Brier = 0.1725, delta = +0.0140
  - bootstrap 95% CI = [+0.0048, +0.0240], stable, excludes 0
  - compression_ratio = 0.267  (model_std=0.015 vs market_std=0.058)
  - rank_correlation = 0.172  (model and market barely agree on individual games)
  - 5/5 temporal windows: market superior
  - 2/6 negative controls overfit_risk (< threshold of 4)
  - sp_fip_delta absorbed by market (not independent signal)

Phase 72 answers exactly these questions:
  1. Can the guard be defined clearly enough?
  2. Is the guard PIT-safe?
  3. Does the guard only reduce model risk (not claim edge)?
  4. Can the guard be verified with historical replay?
  5. Is the guard fit for Phase 73 paper-only replay simulation?
  6. OR is evidence insufficient / governance risk too high?

Outputs:
  A. Guard Trigger Definitions (6 candidates, no threshold mining)
  B. Guard Action Definitions (5 candidates, no production mutation)
  C. PIT-safe Evidence Rule for Phase 73
  D. Success / Failure Criteria for Phase 73 replay
  E. Governance Rules
  F. Candidate Guard Matrix (all fields per guard)
  G. Risk Register (8+ risks)
  H. Phase 73 Simulation Design (not executed)
  I. Gate (one of 7)

GATE (one of 7):
  MARKET_DERISK_GUARD_SPEC_READY
  MARKET_DERISK_REPLAY_READY
  MARKET_DERISK_SPEC_DATA_LIMITED
  MARKET_DERISK_SPEC_OVERFIT_RISK
  MARKET_DERISK_SPEC_GOVERNANCE_RISK
  MARKET_DERISK_SPEC_NOT_ACTIONABLE
  STOP_PATCH_SEARCH_RETURN_TO_P1

SAFETY CONSTANTS (FROZEN, DO NOT MODIFY):
  CANDIDATE_PATCH_CREATED        = False
  PRODUCTION_MODIFIED            = False
  ALPHA_MODIFIED                 = False
  DIAGNOSTIC_ONLY                = True
  PREDICTION_JSONL_OVERWRITTEN   = False
  PIT_SAFE_VALIDATION            = True
  ALPHA                          = 0.40
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ═══════════════════════════════════════════════════════════════════
# SAFETY CONSTANTS — FROZEN, DO NOT MODIFY
# ═══════════════════════════════════════════════════════════════════
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
ALPHA_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True
PREDICTION_JSONL_OVERWRITTEN: bool = False
PIT_SAFE_VALIDATION: bool = True
ALPHA: float = 0.40

# ═══════════════════════════════════════════════════════════════════
# PHASE IDENTITY
# ═══════════════════════════════════════════════════════════════════
PHASE_VERSION: str = "phase72_market_derisk_guard_proposal_v1"
COMPLETION_MARKER: str = "PHASE_72_MARKET_DERISK_GUARD_PROPOSAL_VERIFIED"

# ═══════════════════════════════════════════════════════════════════
# PREVIOUS PHASE GATE ANCHORS (FROZEN — READ ONLY)
# ═══════════════════════════════════════════════════════════════════
PHASE70_GATE_ANCHOR: str = "MARKET_ONLY_SUPERIOR"
PHASE71_GATE_ANCHOR: str = "MARKET_DE_RISK_GUARD_PROMISING"
PHASE71_VERSION: str = "phase71_market_dominance_model_derisk_audit_v1"

# ═══════════════════════════════════════════════════════════════════
# GATE CONSTANTS (7) — exactly as specified
# ═══════════════════════════════════════════════════════════════════
MARKET_DERISK_GUARD_SPEC_READY: str = "MARKET_DERISK_GUARD_SPEC_READY"
MARKET_DERISK_REPLAY_READY: str = "MARKET_DERISK_REPLAY_READY"
MARKET_DERISK_SPEC_DATA_LIMITED: str = "MARKET_DERISK_SPEC_DATA_LIMITED"
MARKET_DERISK_SPEC_OVERFIT_RISK: str = "MARKET_DERISK_SPEC_OVERFIT_RISK"
MARKET_DERISK_SPEC_GOVERNANCE_RISK: str = "MARKET_DERISK_SPEC_GOVERNANCE_RISK"
MARKET_DERISK_SPEC_NOT_ACTIONABLE: str = "MARKET_DERISK_SPEC_NOT_ACTIONABLE"
STOP_PATCH_SEARCH_RETURN_TO_P1: str = "STOP_PATCH_SEARCH_RETURN_TO_P1"

_VALID_GATES: frozenset[str] = frozenset({
    MARKET_DERISK_GUARD_SPEC_READY,
    MARKET_DERISK_REPLAY_READY,
    MARKET_DERISK_SPEC_DATA_LIMITED,
    MARKET_DERISK_SPEC_OVERFIT_RISK,
    MARKET_DERISK_SPEC_GOVERNANCE_RISK,
    MARKET_DERISK_SPEC_NOT_ACTIONABLE,
    STOP_PATCH_SEARCH_RETURN_TO_P1,
})

# ═══════════════════════════════════════════════════════════════════
# PHASE 71 EVIDENCE (FROZEN — READ ONLY)
# All values are from Phase 71 diagnostic run, not re-computed here
# ═══════════════════════════════════════════════════════════════════
_P71_TARGET_BAND_N: int = 103
_P71_TARGET_BAND_LO: float = 0.65
_P71_TARGET_BAND_HI: float = 0.70
_P71_MODEL_BRIER: float = 0.1865
_P71_MARKET_BRIER: float = 0.1725
_P71_BRIER_DELTA: float = 0.0140          # model_brier - market_brier
_P71_CI_LO: float = 0.0048
_P71_CI_HI: float = 0.0240
_P71_CI_STABLE: bool = True
_P71_CI_EXCLUDES_ZERO: bool = True
_P71_TRUE_WIN_RATE: float = 0.767
_P71_COMPRESSION_RATIO: float = 0.267     # model_std / market_std
_P71_MODEL_STD: float = 0.0154
_P71_MARKET_STD: float = 0.0579
_P71_RANK_CORR: float = 0.172
_P71_DISAGREEMENT_RATE: float = 0.330     # |model-market| >= 0.05
_P71_WINDOWS_MARKET_SUPERIOR: int = 5
_P71_WINDOWS_TOTAL: int = 5
_P71_NC_OVERFIT_RISK_COUNT: int = 2       # 2/6 < threshold of 4
_P71_SP_FIP_ABSORBED_BY_MARKET: bool = True
_P71_SP_FIP_INDEPENDENT_SIGNAL: bool = False
_P71_SPLIT_INSTABILITY_DETECTED: bool = False

# ═══════════════════════════════════════════════════════════════════
# GUARD PROPOSAL PARAMETERS (PROPOSAL-ONLY, NOT EVAL-TUNED)
# These are conservative starting points for Phase 73 to test
# DO NOT treat any of these as validated thresholds
# ═══════════════════════════════════════════════════════════════════
_PROPOSAL_BAND_LO: float = 0.65           # Phase71-evidence band lower bound
_PROPOSAL_BAND_HI: float = 0.70           # Phase71-evidence band upper bound
_PROPOSAL_COMPRESSION_THRESHOLD: float = 0.50   # candidate trigger; Phase73 must validate
_PROPOSAL_DISAGREEMENT_THRESHOLD: float = 0.05  # candidate trigger; Phase73 must validate
_PROPOSAL_MIN_PRIOR_WINDOW_N: int = 20    # minimum prior-window sample for PIT-safe check

# ═══════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class GuardCandidate:
    """A single candidate guard trigger+action combination."""
    guard_id: str
    trigger_definition: str
    action_definition: str
    required_inputs: list[str]
    pit_safe: bool
    pit_safe_notes: str
    expected_risk_reduction: str    # conservative description only
    production_risk: str            # risk if applied to production
    phase73_testability: str        # how to test in Phase 73 replay
    rejection_reason: str           # empty string if recommended
    recommended: bool


@dataclass
class RiskEntry:
    """One risk in the risk register."""
    risk_name: str
    severity: str           # HIGH / MEDIUM / LOW
    likelihood: str         # HIGH / MEDIUM / LOW
    mitigation: str
    phase73_required_check: str


@dataclass
class PitSafeRule:
    """PIT-safe evidence rule for Phase 73."""
    rule_id: str
    description: str
    required: bool
    verification_method: str


@dataclass
class SuccessFailureCriteria:
    """Phase 73 success/failure criteria."""
    criterion_id: str
    criterion_type: str     # "success" or "failure"
    description: str
    measurement: str
    threshold_note: str     # marked PHASE73_VALIDATE where unknown


@dataclass
class GovernanceRule:
    """One governance rule."""
    rule_id: str
    rule_text: str
    enforced_by: str        # how it is enforced


@dataclass
class Phase73SimulationDesign:
    """Phase 73 replay simulation design (not executed in Phase 72)."""
    input_jsonl: str
    output_json_report_path: str
    output_markdown_report_path: str
    replay_method: str
    train_eval_split: str
    trigger_candidates: list[str]
    action_candidates: list[str]
    metrics: list[str]
    negative_controls: list[str]
    bootstrap_plan: str
    gate_candidates: list[str]
    completion_marker: str
    execution_phase: str        # "Phase73" — NOT Phase72
    notes: str


@dataclass
class Phase72Report:
    """Full Phase 72 paper-only proposal report."""
    phase_version: str
    completion_marker: str
    run_timestamp_utc: str
    # Safety flags
    candidate_patch_created: bool
    production_modified: bool
    alpha_modified: bool
    diagnostic_only: bool
    prediction_jsonl_overwritten: bool
    pit_safe_validation: bool
    alpha: float
    # Phase chain anchors
    phase70_gate_anchor: str
    phase71_gate_anchor: str
    # Phase 71 evidence summary (read-only)
    p71_n_target_band: int
    p71_brier_delta: float
    p71_ci_lo: float
    p71_ci_hi: float
    p71_ci_stable: bool
    p71_ci_excludes_zero: bool
    p71_compression_ratio: float
    p71_rank_corr: float
    p71_windows_market_superior: int
    p71_nc_overfit_risk_count: int
    # Proposal outputs
    guard_candidates: list[dict[str, Any]]
    risk_register: list[dict[str, Any]]
    pit_safe_rules: list[dict[str, Any]]
    success_failure_criteria: list[dict[str, Any]]
    governance_rules: list[dict[str, Any]]
    phase73_simulation_design: dict[str, Any]
    # Gate
    gate: str
    gate_rationale: str
    gate_risk_notes: list[str]
    recommended_guards: list[str]
    rejected_guards: list[str]
    phase73_recommended: bool
    phase73_recommendation_note: str


def _to_dict(obj: Any) -> Any:
    """Recursively convert dataclass instances to dicts."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_dict(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_dict(v) for v in obj]
    return obj


# ═══════════════════════════════════════════════════════════════════
# SECTION A — GUARD TRIGGER DEFINITIONS (6 candidates)
# ═══════════════════════════════════════════════════════════════════

def _build_guard_candidates() -> list[GuardCandidate]:
    """Build the 6 candidate guard trigger+action combinations.

    Triggers and actions are proposals only.
    Thresholds are conservative starting points — Phase 73 must validate all.
    NO threshold is chosen by eval-fitting in this phase.
    """
    guards: list[GuardCandidate] = []

    # ── G1: Bare band trigger + shadow-only action ────────────────
    guards.append(GuardCandidate(
        guard_id="G1_band_shadow",
        trigger_definition=(
            "model_home_prob ∈ [0.65, 0.70)  — no additional conditions. "
            "Fires whenever the model assigns a 65%–70% probability to the home team."
        ),
        action_definition=(
            "market_only_shadow: record market-only prediction in a shadow report "
            "alongside the original model prediction. Zero production mutation."
        ),
        required_inputs=["model_home_prob", "market_home_prob_no_vig"],
        pit_safe=True,
        pit_safe_notes=(
            "market_home_prob_no_vig is available pre-game; no future information used. "
            "Shadow report is write-only; no feedback into model."
        ),
        expected_risk_reduction=(
            "Provides auditable record of market vs model divergence in the compressed band. "
            "Does not reduce Brier score directly; enables Phase 73 replay comparison."
        ),
        production_risk=(
            "No production mutation. Risk: shadow reports might be misread as "
            "recommendations. Mitigation: explicit NO_EDGE_CLAIM header in report."
        ),
        phase73_testability=(
            "Replay all 103 target-band games; compute shadow Brier; compare against "
            "original model Brier. Bootstrap CI required. PIT: shadow computed from "
            "pre-game market only."
        ),
        rejection_reason="",
        recommended=True,
    ))

    # ── G2: Band + high-disagreement trigger + flag-only action ──
    guards.append(GuardCandidate(
        guard_id="G2_band_disagreement_flag",
        trigger_definition=(
            "model_home_prob ∈ [0.65, 0.70)  AND  "
            "|model_home_prob − market_home_prob_no_vig| ≥ 0.05  "
            "(threshold=0.05 is a Phase71-observed median disagreement gap; "
            "MUST be re-validated in Phase 73 — do NOT treat as optimal)."
        ),
        action_definition=(
            "de_risk_flag_only: attach a 'model_compression_risk=True' flag to the "
            "game record in the output report. Do NOT modify model_home_prob or alpha. "
            "Flag is advisory only."
        ),
        required_inputs=["model_home_prob", "market_home_prob_no_vig"],
        pit_safe=True,
        pit_safe_notes=(
            "Both inputs are pre-game observable. Flag is computed post-prediction "
            "but does not alter the prediction. No look-ahead."
        ),
        expected_risk_reduction=(
            "Narrows guard scope to games where model and market diverge most. "
            "Phase 71 showed 33% disagreement rate; this guard targets that subset."
        ),
        production_risk=(
            "If flag is connected to downstream stake logic (NOT in Phase 72/73 scope), "
            "risk of inadvertent production effect. "
            "Governance rule required: flag must not be consumed by betting execution."
        ),
        phase73_testability=(
            "Compute flagged-game rate; compare Brier for flagged vs non-flagged; "
            "negative control: random flag assignment of same coverage rate. "
            "Threshold 0.05 must be tested at 0.03, 0.05, 0.07 in Phase 73 via bootstrap."
        ),
        rejection_reason="",
        recommended=True,
    ))

    # ── G3: Band + compression proxy trigger + abstain-wording action
    guards.append(GuardCandidate(
        guard_id="G3_band_compression_abstain",
        trigger_definition=(
            "model_home_prob ∈ [0.65, 0.70)  AND  "
            "session-level rolling compression_ratio ≤ 0.50  "
            "(threshold=0.50 is above Phase71's observed 0.267; "
            "PHASE73_VALIDATE — do not claim as optimal). "
            "compression_ratio = rolling model_std / rolling market_std over prior window."
        ),
        action_definition=(
            "abstain_from_model_confidence_claim: suppress 'high-confidence' wording "
            "in any output report for this game. "
            "Original probability unchanged. No stake / execution change."
        ),
        required_inputs=[
            "model_home_prob",
            "market_home_prob_no_vig",
            "prior_window_model_probs",    # needed for rolling std
            "prior_window_market_probs",   # needed for rolling std
        ],
        pit_safe=True,
        pit_safe_notes=(
            "Rolling stats use only the prior window (pre-game). "
            "Compression ratio is computed from historical predictions only. "
            "No in-sample evaluation on current game."
        ),
        expected_risk_reduction=(
            "Suppresses overconfident wording when model has historically been "
            "compressed in this band. Reduces reputational risk of model appearing "
            "certain when market disagrees widely."
        ),
        production_risk=(
            "Requires rolling prior-window stat to be maintained. "
            "If prior window is miscalculated (e.g., data leak), compression trigger "
            "could fire incorrectly. Mitigation: minimum prior_window_n >= 20 check."
        ),
        phase73_testability=(
            "Replay: compute prior-window compression ratio at each prediction date; "
            "measure guard coverage rate; confirm trigger does not look ahead. "
            "Phase73 must test sensitivity at ratio thresholds 0.40, 0.50, 0.60."
        ),
        rejection_reason="",
        recommended=True,
    ))

    # ── G4: Band + market_weight_cap proposal (paper-only) ────────
    guards.append(GuardCandidate(
        guard_id="G4_band_market_weight_cap_proposal",
        trigger_definition=(
            "model_home_prob ∈ [0.65, 0.70). "
            "No secondary condition — fires for all band games."
        ),
        action_definition=(
            "market_weight_cap_proposal: in paper-only shadow report, record a "
            "'shadow_blend' probability computed as: "
            "shadow_blend = 0.40 * model_home_prob + 0.60 * market_home_prob_no_vig "
            "(vs current frozen blend = 0.60 * model + 0.40 * market). "
            "NOTE: This is ONLY a shadow/reporting value. "
            "Do NOT modify production alpha (frozen at 0.40). "
            "Do NOT modify stacking_model.py. "
            "Shadow Brier comparison only."
        ),
        required_inputs=["model_home_prob", "market_home_prob_no_vig"],
        pit_safe=True,
        pit_safe_notes=(
            "Shadow blend uses only pre-game observables. "
            "Production alpha is not changed. Shadow value is post-hoc diagnostic only."
        ),
        expected_risk_reduction=(
            "Tests whether increasing market weight in this band would have reduced "
            "Brier score in Phase 71 data. Does NOT claim this is an actionable patch."
        ),
        production_risk=(
            "HIGH governance risk: shadow_blend could be misread as a production alpha "
            "patch recommendation. Must be clearly labeled 'PAPER_SHADOW_ONLY'. "
            "Must not be connected to any alpha-update logic."
        ),
        phase73_testability=(
            "Phase 73 replay: compute shadow_blend Brier vs original blend Brier "
            "with bootstrap CI. Test multiple shadow alpha values [0.50, 0.60, 0.70]. "
            "Negative control: random weight assignment. "
            "GATE: shadow improvement CI must exclude 0 AND be stable across splits."
        ),
        rejection_reason="",
        recommended=True,
    ))

    # ── G5: Band + route-to-manual-review action ──────────────────
    guards.append(GuardCandidate(
        guard_id="G5_band_manual_review_route",
        trigger_definition=(
            "model_home_prob ∈ [0.65, 0.70)  AND  "
            "|model_home_prob − market_home_prob_no_vig| ≥ 0.05  AND  "
            "sp_fip_delta available (not null). "
            "Fires only when both model-market divergence and SP FIP data are present."
        ),
        action_definition=(
            "route_to_manual_review: mark game with 'requires_human_review=True' "
            "in output report. Include model_home_prob, market_home_prob_no_vig, "
            "sp_fip_delta in the review record. "
            "Model probability is NOT changed. No automatic action."
        ),
        required_inputs=[
            "model_home_prob",
            "market_home_prob_no_vig",
            "sp_fip_delta",
        ],
        pit_safe=True,
        pit_safe_notes=(
            "All inputs are pre-game observables. "
            "sp_fip_delta is pitcher FIP comparison; available before game start. "
            "No look-ahead."
        ),
        expected_risk_reduction=(
            "Targets the specific subset where Phase 71 found sp_fip was correlated "
            "with market (not independent). Human reviewer can assess whether market "
            "has already priced in the sp_fip edge."
        ),
        production_risk=(
            "LOW if human review is genuinely required (not optional). "
            "Risk increases if 'requires_human_review' is ignored in practice. "
            "Coverage rate should stay below 20% of band games to be operationally viable."
        ),
        phase73_testability=(
            "Phase 73 replay: compute triggered game rate; check that sp_fip_delta "
            "availability is >= 90% in target band (Phase71 showed 100%). "
            "Compare Brier for triggered vs non-triggered games."
        ),
        rejection_reason="",
        recommended=True,
    ))

    # ── G6: Band + prior-split market evidence gate (stricter) ────
    guards.append(GuardCandidate(
        guard_id="G6_band_prior_split_evidence_only",
        trigger_definition=(
            "model_home_prob ∈ [0.65, 0.70)  AND  "
            "market was superior to model in ALL prior temporal windows available "
            "(minimum 3 windows with N >= 20 each). "
            "This is the most conservative trigger: fires only when there is "
            "consistent cross-window prior evidence."
        ),
        action_definition=(
            "market_only_shadow (same as G1): record market-only prediction in "
            "shadow report. Zero production mutation."
        ),
        required_inputs=[
            "model_home_prob",
            "market_home_prob_no_vig",
            "prior_window_segment_metrics",   # requires pre-computed per-window stats
        ],
        pit_safe=True,
        pit_safe_notes=(
            "Prior window metrics are computed from games earlier in the season. "
            "Current game not included in prior windows. "
            "Requires careful date ordering to ensure PIT safety."
        ),
        expected_risk_reduction=(
            "Most conservative guard: only fires when there is consistent historical "
            "evidence of market superiority, not just band membership. "
            "Lowest false-positive risk."
        ),
        production_risk=(
            "Complex PIT-safe implementation: prior_window_segment_metrics must be "
            "maintained as a running computation, not retroactively filled. "
            "Risk of implementation error leading to look-ahead. "
            "Phase 73 must explicitly verify no future data leaks into prior windows."
        ),
        phase73_testability=(
            "Phase 73 replay: simulate rolling window computation; verify temporal "
            "ordering at each prediction date; compute coverage rate; bootstrap Brier. "
            "Most complex to implement correctly; requires dedicated PIT leak test."
        ),
        rejection_reason=(
            "Not rejected, but lowest priority for Phase 73 implementation due to "
            "implementation complexity and leakage risk. G1 or G2 should be tested first."
        ),
        recommended=False,
    ))

    return guards


# ═══════════════════════════════════════════════════════════════════
# SECTION B — RISK REGISTER (8 risks)
# ═══════════════════════════════════════════════════════════════════

def _build_risk_register() -> list[RiskEntry]:
    return [
        RiskEntry(
            risk_name="leakage_risk",
            severity="HIGH",
            likelihood="MEDIUM",
            mitigation=(
                "All guard triggers must use only pre-game observables. "
                "Phase 73 must include explicit PIT leak test: verify no future "
                "win/loss information enters trigger computation. "
                "G6 (rolling window) is highest leakage risk; test first with G1/G2."
            ),
            phase73_required_check=(
                "Shuffle game dates; confirm trigger rate does not change. "
                "Verify all required_inputs have pre-game timestamps."
            ),
        ),
        RiskEntry(
            risk_name="overfit_risk",
            severity="HIGH",
            likelihood="MEDIUM",
            mitigation=(
                "Phase 71 found n=103 in target band (all of 2025 season). "
                "This is borderline for stable threshold estimation. "
                "Phase 73 must use held-out temporal windows only. "
                "No threshold chosen from eval data. "
                "Negative controls required (same as Phase 71 NCs)."
            ),
            phase73_required_check=(
                "6 negative controls as in Phase 71. "
                "Bootstrap CI width check: if CI width > 0.10, flag as unstable. "
                "Do NOT proceed to Phase 74 if NC overfit_risk_count >= 4."
            ),
        ),
        RiskEntry(
            risk_name="market_over_reliance_risk",
            severity="MEDIUM",
            likelihood="MEDIUM",
            mitigation=(
                "Guard actions are shadow/flag/manual-review only — not production "
                "probability replacement. G4 shadow_blend must remain labeled "
                "PAPER_SHADOW_ONLY. Governance rule prohibits production alpha change."
            ),
            phase73_required_check=(
                "Verify no guard action modifies model_home_prob or production alpha. "
                "Confirm shadow_blend field is named distinctly from blend field."
            ),
        ),
        RiskEntry(
            risk_name="model_devaluation_risk",
            severity="MEDIUM",
            likelihood="LOW",
            mitigation=(
                "Guard only applies to 0.65–0.70 band (n=103 / 2025 = 5.1% of games). "
                "Outside this band, model is unchanged. "
                "Phase 73 must confirm guard does not degrade Brier for other segments."
            ),
            phase73_required_check=(
                "Compute Brier for all_games, home_favorite_only, heavy_favorite with "
                "and without guard. Confirm no degradation in non-target segments."
            ),
        ),
        RiskEntry(
            risk_name="sample_concentration_risk",
            severity="MEDIUM",
            likelihood="MEDIUM",
            mitigation=(
                "Phase 71 found LAD + MIL = 23.4% of target band (24/103). "
                "If guard performance is driven by 2 teams, it will not generalize. "
                "Phase 73 must report per-team coverage and Brier; "
                "check if guard performance holds after removing top-2 teams."
            ),
            phase73_required_check=(
                "Leave-one-team-out sensitivity test for top 5 teams in target band. "
                "If Brier delta changes by > 0.005 when any single team removed → flag."
            ),
        ),
        RiskEntry(
            risk_name="threshold_mining_risk",
            severity="HIGH",
            likelihood="HIGH",
            mitigation=(
                "NO threshold has been fit from eval data in Phase 72. "
                "All thresholds (0.05 disagreement, 0.50 compression) are "
                "conservative proposals from Phase 71 observed distributions. "
                "Phase 73 must treat all thresholds as candidates and test multiple values. "
                "If only one threshold value works, treat as overfit signal."
            ),
            phase73_required_check=(
                "Test each threshold at 3+ values. "
                "Report which threshold is chosen and WHY (not 'it was highest')."
                "Reject guard if only one threshold value in ±0.02 range works."
            ),
        ),
        RiskEntry(
            risk_name="governance_bypass_risk",
            severity="HIGH",
            likelihood="LOW",
            mitigation=(
                "Guard output must not be consumed by any betting execution / stake / "
                "bankroll logic. Enforced by: (a) separate output file namespace "
                "'phase72_shadow_*', (b) no import of guard output by execution modules, "
                "(c) completion marker in report requires human sign-off. "
                "Human review required before any Phase 73 gate passage."
            ),
            phase73_required_check=(
                "Verify that no Phase 73 output file is imported by execution modules. "
                "Assert CANDIDATE_PATCH_CREATED = False, PRODUCTION_MODIFIED = False."
            ),
        ),
        RiskEntry(
            risk_name="production_mutation_risk",
            severity="HIGH",
            likelihood="LOW",
            mitigation=(
                "CANDIDATE_PATCH_CREATED = False, PRODUCTION_MODIFIED = False, "
                "ALPHA_MODIFIED = False are frozen constants in all Phase 72/73 modules. "
                "CI gate for Phase 73 requires explicit human approval before any "
                "Phase 74 patch creation. "
                "stacking_model.py is never imported or referenced in this module."
            ),
            phase73_required_check=(
                "Automated assert in Phase 73 runner: CANDIDATE_PATCH_CREATED = False. "
                "Any Phase 73 report must not include a diff or code change to "
                "stacking_model.py or prediction JSONL."
            ),
        ),
    ]


# ═══════════════════════════════════════════════════════════════════
# SECTION C — PIT-SAFE EVIDENCE RULES
# ═══════════════════════════════════════════════════════════════════

def _build_pit_safe_rules() -> list[PitSafeRule]:
    return [
        PitSafeRule(
            rule_id="PIT1_train_before_eval",
            description=(
                "All evidence used to define or validate a guard trigger must come "
                "from games earlier in the season than the eval window. "
                "No in-sample fit-and-evaluate."
            ),
            required=True,
            verification_method=(
                "Sort games by date. Assign first 70% as train, last 30% as eval. "
                "Verify guard trigger does not use any eval-window data."
            ),
        ),
        PitSafeRule(
            rule_id="PIT2_inputs_pre_game_only",
            description=(
                "All required_inputs (model_home_prob, market_home_prob_no_vig, "
                "sp_fip_delta, prior_window_stats) must be observables available "
                "before the game starts. No post-game information."
            ),
            required=True,
            verification_method=(
                "For each input field, verify it has a pre-game timestamp. "
                "market_home_prob_no_vig: use line from game-day morning. "
                "sp_fip_delta: use season-to-date FIP as of game date."
            ),
        ),
        PitSafeRule(
            rule_id="PIT3_no_threshold_from_eval",
            description=(
                "No threshold value may be chosen based on eval-set performance. "
                "Thresholds must either be (a) pre-specified from theory, "
                "(b) carried from prior phase evidence (Phase 71), or "
                "(c) tested at multiple values in Phase 73 with no single 'best' claim."
            ),
            required=True,
            verification_method=(
                "Phase 73 must test each threshold at minimum 3 values. "
                "If a specific threshold is proposed for Phase 74, it must be justified "
                "by cross-window stability, NOT peak eval performance."
            ),
        ),
        PitSafeRule(
            rule_id="PIT4_rolling_window_temporal_order",
            description=(
                "For guards requiring prior_window_stats (G3, G6), the rolling window "
                "computation must respect strict temporal ordering. "
                "Window N must contain only games from before the first game in window N+1."
            ),
            required=True,
            verification_method=(
                "Implement rolling window with explicit date cut: "
                "'prior to current_game_date'. "
                "Assert that prior_window last_date < current_game_date for every row."
            ),
        ),
        PitSafeRule(
            rule_id="PIT5_no_production_jsonl_overwrite",
            description=(
                "Phase 73 replay output must be written to a separate file path. "
                "The source prediction JSONL must never be overwritten. "
                "PREDICTION_JSONL_OVERWRITTEN must remain False."
            ),
            required=True,
            verification_method=(
                "Assert in Phase 73 runner: source JSONL mtime unchanged after run. "
                "Write output to reports/phase73_*.json only."
            ),
        ),
        PitSafeRule(
            rule_id="PIT6_replay_only_output_path",
            description=(
                "Phase 73 simulation output must be written to a designated replay "
                "output path. Output must not be imported by any execution module."
            ),
            required=True,
            verification_method=(
                "Grep codebase for import of phase73 output paths. "
                "Assert no execution module references phase73 output."
            ),
        ),
    ]


# ═══════════════════════════════════════════════════════════════════
# SECTION D — SUCCESS / FAILURE CRITERIA FOR PHASE 73
# ═══════════════════════════════════════════════════════════════════

def _build_success_failure_criteria() -> list[SuccessFailureCriteria]:
    return [
        # Success criteria
        SuccessFailureCriteria(
            criterion_id="SC1",
            criterion_type="success",
            description="Brier delta improvement with stable bootstrap CI",
            measurement=(
                "Shadow/guard Brier − original model Brier < 0 "
                "(guard improves Brier), "
                "AND bootstrap 95% CI excludes 0, "
                "AND CI width <= 0.10."
            ),
            threshold_note="CI threshold 0.10 from Phase71 stability rule; PHASE73_VALIDATE.",
        ),
        SuccessFailureCriteria(
            criterion_id="SC2",
            criterion_type="success",
            description="ECE does not materially degrade",
            measurement=(
                "Shadow ECE − original ECE <= 0.005 "
                "(guard does not meaningfully worsen calibration)."
            ),
            threshold_note="Threshold 0.005 is conservative; PHASE73_VALIDATE.",
        ),
        SuccessFailureCriteria(
            criterion_id="SC3",
            criterion_type="success",
            description="Market dominance segment risk reduces",
            measurement=(
                "In 0.65–0.70 band: shadow Brier < original model Brier "
                "AND shadow Brier <= market Brier + 0.005."
            ),
            threshold_note="Tolerance 0.005; PHASE73_VALIDATE.",
        ),
        SuccessFailureCriteria(
            criterion_id="SC4",
            criterion_type="success",
            description="Negative controls do not trigger overfit signal",
            measurement=(
                "Out of 6 negative controls (same design as Phase 71), "
                "< 4 show overfit_risk=True."
            ),
            threshold_note="Threshold 4/6 from Phase 71 governance; fixed.",
        ),
        SuccessFailureCriteria(
            criterion_id="SC5",
            criterion_type="success",
            description="Guard coverage does not over-expand",
            measurement=(
                "Guard trigger fires for <= 15% of all_games (not > 0.65–0.70 band). "
                "If guard spills into other probability segments, reject."
            ),
            threshold_note="15% coverage cap is conservative; PHASE73_VALIDATE.",
        ),
        SuccessFailureCriteria(
            criterion_id="SC6",
            criterion_type="success",
            description="No production mutation",
            measurement=(
                "CANDIDATE_PATCH_CREATED = False, PRODUCTION_MODIFIED = False, "
                "ALPHA_MODIFIED = False after Phase 73 run."
            ),
            threshold_note="Hard requirement; no threshold.",
        ),
        # Failure criteria
        SuccessFailureCriteria(
            criterion_id="FC1",
            criterion_type="failure",
            description="Bootstrap CI does not exclude zero",
            measurement=(
                "Shadow Brier improvement CI includes 0 or is fully positive (no improvement). "
                "→ Guard not actionable."
            ),
            threshold_note="Hard failure.",
        ),
        SuccessFailureCriteria(
            criterion_id="FC2",
            criterion_type="failure",
            description="Performance only in single split",
            measurement=(
                "Guard Brier improvement is observed in only 1/5 temporal windows. "
                "→ Split instability; not generalizable."
            ),
            threshold_note="Minimum 3/5 windows required.",
        ),
        SuccessFailureCriteria(
            criterion_id="FC3",
            criterion_type="failure",
            description="Negative controls show overfit",
            measurement=(
                "4 or more of 6 negative controls show overfit_risk=True. "
                "→ Guard is likely mining noise."
            ),
            threshold_note="Hard failure; threshold from Phase 71.",
        ),
        SuccessFailureCriteria(
            criterion_id="FC4",
            criterion_type="failure",
            description="Guard coverage over-expansion",
            measurement=(
                "Guard fires for > 15% of all games, indicating band contamination. "
                "→ Scope too broad."
            ),
            threshold_note="PHASE73_VALIDATE threshold.",
        ),
        SuccessFailureCriteria(
            criterion_id="FC5",
            criterion_type="failure",
            description="Market-only replacement degrades other segments",
            measurement=(
                "Applying shadow replacement to non-target-band games worsens "
                "their Brier by > 0.003. "
                "→ Guard has negative spillover."
            ),
            threshold_note="PHASE73_VALIDATE threshold.",
        ),
        SuccessFailureCriteria(
            criterion_id="FC6",
            criterion_type="failure",
            description="PIT-safe definition cannot be achieved",
            measurement=(
                "Any required_input for the guard is not available pre-game, "
                "OR rolling window computation has temporal leakage. "
                "→ Guard cannot be used in live setting."
            ),
            threshold_note="Hard failure.",
        ),
    ]


# ═══════════════════════════════════════════════════════════════════
# SECTION E — GOVERNANCE RULES
# ═══════════════════════════════════════════════════════════════════

def _build_governance_rules() -> list[GovernanceRule]:
    return [
        GovernanceRule(
            rule_id="GOV1_no_edge_claim",
            rule_text=(
                "NO betting edge may be claimed based on Phase 72 or Phase 73 results. "
                "Brier improvement in shadow replay is a de-risk metric, not an ROI signal."
            ),
            enforced_by="Explicit NO_EDGE_CLAIM header in all Phase 72/73 reports.",
        ),
        GovernanceRule(
            rule_id="GOV2_no_profit_claim",
            rule_text=(
                "NO profit or expected-value improvement may be claimed. "
                "Phase 72/73 do not compute EV, Kelly fractions, or betting ROI."
            ),
            enforced_by="report fields do not include EV, ROI, or Kelly fields.",
        ),
        GovernanceRule(
            rule_id="GOV3_no_production_patch",
            rule_text=(
                "No production patch may be created in Phase 72 or Phase 73. "
                "CANDIDATE_PATCH_CREATED must remain False. "
                "Phase 74+ required for any patch proposal."
            ),
            enforced_by="Frozen constant assertion in runner script.",
        ),
        GovernanceRule(
            rule_id="GOV4_no_automatic_execution",
            rule_text=(
                "Guard output must not be consumed by any automated betting execution, "
                "stake sizing, or bankroll management module. "
                "All guard outputs are advisory/diagnostic only."
            ),
            enforced_by=(
                "Separate output namespace (phase72_shadow_*). "
                "No execution module imports phase72/phase73 output."
            ),
        ),
        GovernanceRule(
            rule_id="GOV5_replay_only",
            rule_text=(
                "Phase 73 operates in replay-only mode on historical JSONL. "
                "No live prediction pipeline is modified."
            ),
            enforced_by="PREDICTION_JSONL_OVERWRITTEN = False assertion.",
        ),
        GovernanceRule(
            rule_id="GOV6_human_review_required",
            rule_text=(
                "Phase 73 gate passage requires human sign-off. "
                "Automated runner produces report; human reviews before any Phase 74 decision."
            ),
            enforced_by=(
                "COMPLETION_MARKER in report requires human acknowledgement. "
                "No automated Phase 74 trigger."
            ),
        ),
        GovernanceRule(
            rule_id="GOV7_rollback_plan",
            rule_text=(
                "If Phase 73 produces a shadow guard that is later (Phase 74+) applied, "
                "a rollback plan must exist: "
                "(a) git revert to pre-Phase74 commit, "
                "(b) prediction JSONL restored from backup, "
                "(c) no permanent schema change required."
            ),
            enforced_by=(
                "Phase 74 (if reached) must include rollback commit hash in report. "
                "Not applicable in Phase 72/73."
            ),
        ),
        GovernanceRule(
            rule_id="GOV8_audit_log_requirement",
            rule_text=(
                "All Phase 72/73 runs must write a JSON audit log including: "
                "run_timestamp_utc, safety constants, phase_version, gate, "
                "guard_candidates (with recommended bool), p71_evidence_summary."
            ),
            enforced_by="Phase72Report dataclass includes all required audit fields.",
        ),
        GovernanceRule(
            rule_id="GOV9_report_path_requirement",
            rule_text=(
                "All outputs must be written to designated report paths: "
                "reports/phase72_*.json, 00-BettingPlan/20260507/phase72_*.md. "
                "No output to data/ or live/ directories."
            ),
            enforced_by="Runner script asserts output path is under reports/.",
        ),
    ]


# ═══════════════════════════════════════════════════════════════════
# SECTION F — PHASE 73 SIMULATION DESIGN
# ═══════════════════════════════════════════════════════════════════

def _build_phase73_design() -> Phase73SimulationDesign:
    return Phase73SimulationDesign(
        input_jsonl=(
            "data/mlb_2025/derived/"
            "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
        ),
        output_json_report_path=(
            "reports/phase73_market_derisk_guard_replay_<date>.json"
        ),
        output_markdown_report_path=(
            "00-BettingPlan/<date>/phase73_market_derisk_guard_replay_report_<date>.md"
        ),
        replay_method=(
            "Historical replay: iterate over all games in JSONL sorted by date. "
            "For each game: (1) compute guard trigger from pre-game inputs, "
            "(2) if triggered: compute shadow prediction (per guard action), "
            "(3) record both original and shadow predictions, "
            "(4) compute Brier, residual, ECE for both. "
            "NEVER modify the source JSONL. "
            "NEVER update model or alpha."
        ),
        train_eval_split=(
            "Temporal split: first 70% of games (by date) = train window; "
            "last 30% = eval window. "
            "Guard thresholds derived only from train window. "
            "Brier evaluation on eval window only. "
            "Minimum eval N in 0.65–0.70 band: >= 20 (from Phase71 _MIN_SEGMENT_N)."
        ),
        trigger_candidates=[
            "G1: model_home_prob in [0.65, 0.70)",
            "G2: model_home_prob in [0.65, 0.70) AND |model-market| >= 0.05",
            "G3: model_home_prob in [0.65, 0.70) AND rolling compression_ratio <= 0.50",
            "G4: model_home_prob in [0.65, 0.70) [with shadow_blend action]",
            "G5: model_home_prob in [0.65, 0.70) AND |model-market| >= 0.05 AND sp_fip available",
        ],
        action_candidates=[
            "market_only_shadow: shadow_pred = market_home_prob_no_vig",
            "de_risk_flag_only: flag game, no probability change",
            "abstain_from_model_confidence_claim: suppress high-confidence wording",
            "market_weight_cap_proposal: shadow_blend = 0.40*model + 0.60*market",
            "route_to_manual_review: mark requires_human_review=True",
        ],
        metrics=[
            "Brier score: original vs shadow, per segment",
            "ECE: original vs shadow",
            "residual_mean: original vs shadow",
            "coverage_rate: fraction of games triggering guard",
            "bootstrap 95% CI for Brier delta (1000 bootstrap samples)",
            "per-window Brier delta (5 temporal windows)",
            "per-team concentration check (top 5 teams)",
            "shadow_blend alpha sensitivity [0.50, 0.60, 0.70] for G4",
        ],
        negative_controls=[
            "NC1: shuffled_market_assignment (scramble market_home_prob within band)",
            "NC2: shuffled_model_assignment (scramble model_home_prob within band)",
            "NC3: random_shadow_assignment (random 50% of band gets shadow action)",
            "NC4: random_sp_fip_bucket (G5: random sp_fip_delta bucket assignment)",
            "NC5: random_split_assignment (shuffle temporal window labels)",
            "NC6: out_of_band_guard (apply guard trigger to 0.55–0.60 band instead)",
        ],
        bootstrap_plan=(
            "1000 bootstrap samples (rng_seed=42 for reproducibility). "
            "Sample games with replacement within the eval window. "
            "Compute Brier delta for each bootstrap sample. "
            "Report 2.5th and 97.5th percentiles as 95% CI. "
            "Stability: CI width <= 0.10. "
            "Significance: CI excludes 0."
        ),
        gate_candidates=[
            "PHASE73_GUARD_VALIDATED: CI stable + excludes 0 + 3/5+ windows + NC pass",
            "PHASE73_GUARD_MARGINAL: CI excludes 0 but narrow or single-split only",
            "PHASE73_GUARD_OVERFIT: NC fail or CI width > 0.10",
            "PHASE73_DATA_LIMITED: eval band N < 20",
            "PHASE73_NOT_ACTIONABLE: PIT rule violated or coverage too high",
            "STOP_PATCH_SEARCH_RETURN_TO_P1: all guards fail; return to governance",
        ],
        completion_marker="PHASE_73_MARKET_DERISK_GUARD_REPLAY_VERIFIED",
        execution_phase="Phase73 — NOT executed in Phase 72",
        notes=(
            "Phase 73 design is provided here for reviewability and auditability. "
            "Phase 73 must not be auto-triggered. "
            "Human CTO review of Phase 72 gate and guard matrix required first. "
            "Phase 73 only proceeds if human approves after Phase 72 report review."
        ),
    )


# ═══════════════════════════════════════════════════════════════════
# GATE DETERMINATION
# ═══════════════════════════════════════════════════════════════════

def _determine_gate(
    guard_candidates: list[GuardCandidate],
    risk_register: list[RiskEntry],
    pit_safe_rules: list[PitSafeRule],
    success_failure_criteria: list[SuccessFailureCriteria],
) -> tuple[str, str, list[str]]:
    """Determine Phase 72 gate conservatively.

    Returns: (gate, rationale, risk_notes)
    """
    # Count recommended guards
    n_recommended = sum(1 for g in guard_candidates if g.recommended)
    n_pit_safe = sum(1 for g in guard_candidates if g.pit_safe and g.recommended)
    n_success_criteria = sum(
        1 for c in success_failure_criteria if c.criterion_type == "success"
    )
    n_failure_criteria = sum(
        1 for c in success_failure_criteria if c.criterion_type == "failure"
    )
    n_required_pit_rules = sum(1 for r in pit_safe_rules if r.required)

    # HIGH severity risks that need Phase73 check
    high_risks = [r for r in risk_register if r.severity == "HIGH"]

    risk_notes: list[str] = []

    # Check: Phase 71 evidence is strong (CI excludes 0, 5/5 windows, nc_count=2/6)
    evidence_strong = (
        _P71_CI_EXCLUDES_ZERO
        and _P71_CI_STABLE
        and _P71_WINDOWS_MARKET_SUPERIOR == _P71_WINDOWS_TOTAL
        and _P71_NC_OVERFIT_RISK_COUNT < 4
    )

    # Check: spec is well-defined (all required elements present)
    spec_complete = (
        n_recommended >= 5
        and n_pit_safe >= 4
        and n_required_pit_rules >= 5
        and n_success_criteria >= 5
        and n_failure_criteria >= 5
    )

    # Check: governance risks are manageable
    governance_risks = [r for r in risk_register if "governance" in r.risk_name.lower()]
    governance_severity_high = any(r.severity == "HIGH" for r in governance_risks)

    if governance_severity_high:
        risk_notes.append(
            "GOV_RISK: governance_bypass_risk is HIGH severity. "
            "Requires explicit human review gate before Phase 73."
        )

    risk_notes.append(
        f"THRESHOLD_MINING: {len([r for r in high_risks if 'threshold' in r.risk_name])} "
        "HIGH-severity threshold mining risks. Phase 73 must test multiple threshold values."
    )
    risk_notes.append(
        f"OVERFIT_RISK: Phase71 NC count = {_P71_NC_OVERFIT_RISK_COUNT}/6 (< threshold 4). "
        "Phase 73 NC test must replicate this check."
    )
    risk_notes.append(
        f"COMPRESSION: model_std/market_std = {_P71_COMPRESSION_RATIO:.3f}. "
        "Model has very low discrimination in this band. "
        "Shadow improvement may be mechanical, not structural."
    )
    risk_notes.append(
        f"SAMPLE_SIZE: n=103 in target band (5.1% of all games). "
        "Phase 73 eval window will have ~30 target-band games. "
        "CI will be wide; manage expectations."
    )

    # Gate decision: conservative
    # MARKET_DERISK_REPLAY_READY requires Phase 73 design to be complete AND
    # all spec elements verified. Phase 73 design is provided but not executed.
    # Phase 72 provides the spec; replay itself is Phase 73.
    # → Use MARKET_DERISK_GUARD_SPEC_READY: spec is clear, PIT-safe, can be replayed,
    #   but Phase 73 simulation has not been run yet.
    if evidence_strong and spec_complete:
        gate = MARKET_DERISK_GUARD_SPEC_READY
        rationale = (
            "Phase 71 evidence is strong: Brier delta=+0.0140, CI=[+0.0048, +0.0240] "
            "stable and excludes 0, 5/5 windows consistent, nc_overfit_risk=2/6. "
            f"Guard spec is complete: {n_recommended} recommended guards, "
            f"{n_pit_safe} PIT-safe, {n_required_pit_rules} required PIT rules, "
            f"{n_success_criteria} success + {n_failure_criteria} failure criteria. "
            "Spec is clear and PIT-safe. Phase 73 replay is the next step. "
            "NOTE: MARKET_DERISK_REPLAY_READY requires Phase 73 design to be "
            "independently validated with human CTO approval; Phase 72 provides "
            "the design but has not executed it."
        )
    else:
        gate = MARKET_DERISK_SPEC_DATA_LIMITED
        rationale = (
            "Spec or evidence incomplete. "
            f"n_recommended={n_recommended}, n_pit_safe={n_pit_safe}, "
            f"evidence_strong={evidence_strong}, spec_complete={spec_complete}."
        )

    return gate, rationale, risk_notes


# ═══════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def run_phase72_market_derisk_guard_proposal() -> Phase72Report:
    """Build Phase 72 paper-only market de-risk guard proposal.

    This function constructs the full proposal in memory.
    It does NOT read or write any JSONL predictions.
    It does NOT import or modify any production model.
    """
    # Build proposal components
    guard_candidates = _build_guard_candidates()
    risk_register = _build_risk_register()
    pit_safe_rules = _build_pit_safe_rules()
    success_failure_criteria = _build_success_failure_criteria()
    governance_rules = _build_governance_rules()
    phase73_design = _build_phase73_design()

    # Determine gate
    gate, rationale, risk_notes = _determine_gate(
        guard_candidates, risk_register, pit_safe_rules, success_failure_criteria
    )

    assert gate in _VALID_GATES, f"Invalid gate: {gate}"

    # Classify guards
    recommended_guards = [g.guard_id for g in guard_candidates if g.recommended]
    rejected_guards = [g.guard_id for g in guard_candidates if not g.recommended]

    # Phase 73 recommendation
    phase73_recommended = gate in {
        MARKET_DERISK_GUARD_SPEC_READY,
        MARKET_DERISK_REPLAY_READY,
    }
    phase73_note = (
        "Phase 73 replay simulation is recommended. "
        "Guard spec is clear, PIT-safe, and Phase 73 design is complete. "
        "Human CTO review of this report required before Phase 73 starts. "
        "If Phase 73 gate is not PHASE73_GUARD_VALIDATED, return to P1 governance."
        if phase73_recommended else
        "Phase 73 is NOT recommended based on current gate. Return to P1 governance."
    )

    report = Phase72Report(
        phase_version=PHASE_VERSION,
        completion_marker=COMPLETION_MARKER,
        run_timestamp_utc=datetime.now(timezone.utc).isoformat(),
        # Safety flags
        candidate_patch_created=CANDIDATE_PATCH_CREATED,
        production_modified=PRODUCTION_MODIFIED,
        alpha_modified=ALPHA_MODIFIED,
        diagnostic_only=DIAGNOSTIC_ONLY,
        prediction_jsonl_overwritten=PREDICTION_JSONL_OVERWRITTEN,
        pit_safe_validation=PIT_SAFE_VALIDATION,
        alpha=ALPHA,
        # Phase chain anchors
        phase70_gate_anchor=PHASE70_GATE_ANCHOR,
        phase71_gate_anchor=PHASE71_GATE_ANCHOR,
        # Phase 71 evidence summary
        p71_n_target_band=_P71_TARGET_BAND_N,
        p71_brier_delta=_P71_BRIER_DELTA,
        p71_ci_lo=_P71_CI_LO,
        p71_ci_hi=_P71_CI_HI,
        p71_ci_stable=_P71_CI_STABLE,
        p71_ci_excludes_zero=_P71_CI_EXCLUDES_ZERO,
        p71_compression_ratio=_P71_COMPRESSION_RATIO,
        p71_rank_corr=_P71_RANK_CORR,
        p71_windows_market_superior=_P71_WINDOWS_MARKET_SUPERIOR,
        p71_nc_overfit_risk_count=_P71_NC_OVERFIT_RISK_COUNT,
        # Proposal outputs
        guard_candidates=[asdict(g) for g in guard_candidates],
        risk_register=[asdict(r) for r in risk_register],
        pit_safe_rules=[asdict(r) for r in pit_safe_rules],
        success_failure_criteria=[asdict(c) for c in success_failure_criteria],
        governance_rules=[asdict(r) for r in governance_rules],
        phase73_simulation_design=asdict(phase73_design),
        # Gate
        gate=gate,
        gate_rationale=rationale,
        gate_risk_notes=risk_notes,
        recommended_guards=recommended_guards,
        rejected_guards=rejected_guards,
        phase73_recommended=phase73_recommended,
        phase73_recommendation_note=phase73_note,
    )

    return report
