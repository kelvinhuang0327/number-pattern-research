"""
P1.1 Strategy Denominator Cleanup — Read-Only Operator Classification Script

Purpose:
  Classifies the 73 artifact-only strategies from PR #103 inventory into:
  - PRODUCT_DENOMINATOR   (should count in replay coverage denominator)
  - RESEARCH_ARCHIVE      (internal experiment, not product-facing)
  - DUPLICATE_OR_SUPERSEDED (alternate naming of a canonical strategy)
  - NON_STRATEGY_ARTIFACT (not an actual strategy)
  - NEEDS_OPERATOR_DECISION (insufficient evidence)

Safety:
  - Read-only: no DB writes, no replay rows, no backtest, no registry changes
  - Can be re-run safely

Usage:
  python3 scripts/p11_strategy_denominator_cleanup_readonly.py \
    --inventory /tmp/p1_strategy_universe_inventory_20260515.json \
    --json-out outputs/replay/p11_strategy_denominator_cleanup_20260515.json \
    --csv-out  outputs/replay/p11_strategy_denominator_cleanup_20260515.csv
"""

import argparse
import csv
import datetime
import json
import os
import pathlib
import subprocess
import sys


# ---------------------------------------------------------------------------
# Classification database (operator-reviewed, evidence-based)
# ---------------------------------------------------------------------------

# Classification taxonomy constants
PRODUCT_DENOMINATOR     = "PRODUCT_DENOMINATOR"
RESEARCH_ARCHIVE        = "RESEARCH_ARCHIVE"
DUPLICATE_OR_SUPERSEDED = "DUPLICATE_OR_SUPERSEDED"
NON_STRATEGY_ARTIFACT   = "NON_STRATEGY_ARTIFACT"
NEEDS_OPERATOR_DECISION = "NEEDS_OPERATOR_DECISION"

# Base inventory file (from PR #103 branch)
_INVENTORY_SOURCE_FILES = [
    "outputs/replay/p1_strategy_lifecycle_inventory_20260511.json",
    "outputs/replay/p2_lifecycle_backfill_dry_run_manifest_20260510.json",
]

# Canonical registry (canonical_16 — from PR #103 registry scan)
CANONICAL_REGISTRY_IDS = frozenset([
    "power_precision_3bet", "power_orthogonal_5bet",
    "biglotto_triple_strike", "biglotto_deviation_2bet",
    "daily539_f4cold", "daily539_markov_cold",
    "biglotto_ts3_acb_4bet", "biglotto_ts3_markov_freq_5bet",
    "power_shlc_midfreq", "p1_deviation_2bet_539",
    "acb_1bet", "acb_markov_midfreq", "acb_markov_midfreq_3bet",
    "midfreq_acb_2bet", "midfreq_fourier_2bet",
    "h6_gate_mk20_ew85",
])

# ---------------------------------------------------------------------------
# Operator classification table — evidence-based, hand-reviewed
# ---------------------------------------------------------------------------
# Schema per entry:
#   classification: str
#   recommended_lifecycle_status: str
#   recommended_replay_display_semantics: str
#   canonical_or_successor_strategy_id: str | None
#   evidence_summary: str
#   risk_flags: list[str]
#   recommended_next_action: str

CLASSIFICATIONS: dict[str, dict] = {
    # ---- RESEARCH_ARCHIVE: H-series internal hypothesis labels ----
    # H001–H008 are internal experiment numbering labels with UNKNOWN lottery_type.
    # Not product-facing names; users would see meaningless "H001" entries.
    # All have clear rejection evidence (parameter sweeps, edge tests).
    # Recommended: exclude from replay product denominator.
    "H001": {
        "classification": RESEARCH_ARCHIVE,
        "recommended_lifecycle_status": "N/A",
        "recommended_replay_display_semantics": "N/A",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "Internal hypothesis experiment label. lottery_type=UNKNOWN. "
            "Rejection evidence: 1500p Edge劣化 vs baseline -0.60pp. "
            "No stable product identity; not suitable for replay page display."
        ),
        "risk_flags": [],
        "recommended_next_action": "Archive in research logs; exclude from replay denominator.",
    },
    "H002": {
        "classification": RESEARCH_ARCHIVE,
        "recommended_lifecycle_status": "N/A",
        "recommended_replay_display_semantics": "N/A",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "Internal hypothesis experiment label. lottery_type=UNKNOWN. "
            "Rejection evidence: parameter sweep mult=[0.1,0.2,0.3,0.5,0.8,1.0] all insignificant. "
            "No stable product identity."
        ),
        "risk_flags": [],
        "recommended_next_action": "Archive in research logs; exclude from replay denominator.",
    },
    "H003": {
        "classification": RESEARCH_ARCHIVE,
        "recommended_lifecycle_status": "N/A",
        "recommended_replay_display_semantics": "N/A",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "Internal hypothesis experiment label. lottery_type=UNKNOWN. "
            "Rejection evidence: parameter sweep alpha=[0.2,0.5,1.0,2.0] all insignificant. "
            "No stable product identity."
        ),
        "risk_flags": [],
        "recommended_next_action": "Archive in research logs; exclude from replay denominator.",
    },
    "H004": {
        "classification": RESEARCH_ARCHIVE,
        "recommended_lifecycle_status": "N/A",
        "recommended_replay_display_semantics": "N/A",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "Internal hypothesis experiment label. lottery_type=UNKNOWN. "
            "Rejection evidence: Ljung-Box p=0.8497 (white noise), no temporal structure. "
            "No stable product identity."
        ),
        "risk_flags": [],
        "recommended_next_action": "Archive in research logs; exclude from replay denominator.",
    },
    "H005": {
        "classification": RESEARCH_ARCHIVE,
        "recommended_lifecycle_status": "N/A",
        "recommended_replay_display_semantics": "N/A",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "Internal hypothesis experiment label. lottery_type=UNKNOWN. "
            "Rejection evidence: 741 pairs, 0 pairs with Lift≥1.3x (max Lift=1.054). "
            "No stable product identity."
        ),
        "risk_flags": [],
        "recommended_next_action": "Archive in research logs; exclude from replay denominator.",
    },
    "H006": {
        "classification": RESEARCH_ARCHIVE,
        "recommended_lifecycle_status": "N/A",
        "recommended_replay_display_semantics": "N/A",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "Internal hypothesis experiment label. lottery_type=UNKNOWN. "
            "Rejection evidence: McNemar net=+12 p=0.450 not significant. "
            "No stable product identity."
        ),
        "risk_flags": [],
        "recommended_next_action": "Archive in research logs; exclude from replay denominator.",
    },
    "H007": {
        "classification": RESEARCH_ARCHIVE,
        "recommended_lifecycle_status": "N/A",
        "recommended_replay_display_semantics": "N/A",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "Internal hypothesis experiment label. lottery_type=UNKNOWN. "
            "Rejection evidence: McNemar w1000 vs w500 net=-7 p=0.835 (w500 marginally better). "
            "No stable product identity."
        ),
        "risk_flags": [],
        "recommended_next_action": "Archive in research logs; exclude from replay denominator.",
    },
    "H008": {
        "classification": RESEARCH_ARCHIVE,
        "recommended_lifecycle_status": "N/A",
        "recommended_replay_display_semantics": "N/A",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "Internal hypothesis experiment label. lottery_type=UNKNOWN. "
            "Rejection evidence: parameter sweep gap^{1.2,1.5,2.0} all McNemar p>0.19. "
            "No stable product identity."
        ),
        "risk_flags": [],
        "recommended_next_action": "Archive in research logs; exclude from replay denominator.",
    },

    # ---- RESEARCH_ARCHIVE: Phase-0 pipeline prototypes ----
    # p0_*, p0b_*, p0c_* are early pipeline phase-0 experiment intermediate names.
    # Negative signal evidence, superseded by later canonical strategies.
    "p0_neighbor_injection": {
        "classification": RESEARCH_ARCHIVE,
        "recommended_lifecycle_status": "N/A",
        "recommended_replay_display_semantics": "N/A",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "Phase-0 pipeline prototype identifier. lottery_type=UNKNOWN. "
            "Intermediate experiment name — not a stable product strategy. "
            "Superseded by canonical biglotto/539 neighbor strategies."
        ),
        "risk_flags": [],
        "recommended_next_action": "Archive; exclude from replay denominator.",
    },
    "p0b_539_3bet_f_cold_fmid": {
        "classification": RESEARCH_ARCHIVE,
        "recommended_lifecycle_status": "N/A",
        "recommended_replay_display_semantics": "N/A",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "Phase-0B pipeline prototype. Permutation Signal Edge=-0.976% (negative). "
            "Temporary naming convention p0b_*; not a product-facing strategy name."
        ),
        "risk_flags": [],
        "recommended_next_action": "Archive; exclude from replay denominator.",
    },
    "p0c_539_3bet_f_cold_x2": {
        "classification": RESEARCH_ARCHIVE,
        "recommended_lifecycle_status": "N/A",
        "recommended_replay_display_semantics": "N/A",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "Phase-0C pipeline prototype. Signal Edge=-0.176% (negative). "
            "Same root cause as p0b — geometric coverage bias. "
            "Temporary naming convention; not a product-facing strategy name."
        ),
        "risk_flags": [],
        "recommended_next_action": "Archive; exclude from replay denominator.",
    },

    # ---- RESEARCH_ARCHIVE: Phase-2/3 pipeline prototypes ----
    "p2_mab_fusion": {
        "classification": RESEARCH_ARCHIVE,
        "recommended_lifecycle_status": "N/A",
        "recommended_replay_display_semantics": "N/A",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "Phase-2 MAB fusion pipeline prototype. lottery_type=UNKNOWN. "
            "Internal experiment identifier — not a stable product strategy name."
        ),
        "risk_flags": [],
        "recommended_next_action": "Archive; exclude from replay denominator.",
    },
    "p3_state_aware": {
        "classification": RESEARCH_ARCHIVE,
        "recommended_lifecycle_status": "N/A",
        "recommended_replay_display_semantics": "N/A",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "Phase-3 state-aware pipeline prototype. lottery_type=UNKNOWN. "
            "Internal experiment identifier — not a stable product strategy name."
        ),
        "risk_flags": [],
        "recommended_next_action": "Archive; exclude from replay denominator.",
    },

    # ---- RESEARCH_ARCHIVE: SGP research series ----
    "sgp_power_017_research": {
        "classification": RESEARCH_ARCHIVE,
        "recommended_lifecycle_status": "N/A",
        "recommended_replay_display_semantics": "N/A",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "Explicitly named 'research' variant (sgp_power_017_research). "
            "SGP sub-graph research series for Power Lotto — sweep/exploratory artifact. "
            "Not a product-facing strategy name."
        ),
        "risk_flags": [],
        "recommended_next_action": "Archive; exclude from replay denominator.",
    },
    "sgp_v9_apex_powerlotto": {
        "classification": RESEARCH_ARCHIVE,
        "recommended_lifecycle_status": "N/A",
        "recommended_replay_display_semantics": "N/A",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "SGP v9 Apex research series — versioned sweep candidate. "
            "Rejection evidence: 3-bet union M3+ Edge=-37.3% vs baseline. "
            "Version-numbered name (v9) indicates sweep candidate, not final product."
        ),
        "risk_flags": [],
        "recommended_next_action": "Archive; exclude from replay denominator.",
    },

    # ---- DUPLICATE_OR_SUPERSEDED ----
    # Alternate naming conventions for canonical registry strategies.
    "shlc_midfreq_power": {
        "classification": DUPLICATE_OR_SUPERSEDED,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": "power_shlc_midfreq",
        "evidence_summary": (
            "Alternate naming of canonical strategy power_shlc_midfreq. "
            "shlc_midfreq_power reverses the prefix/suffix ordering used in the canonical registry "
            "(power_* prefix convention). Both refer to SHLC MidFreq strategy for Power Lotto. "
            "Canonical power_shlc_midfreq is REJECTED with 50 DB replay rows."
        ),
        "risk_flags": ["naming_convention_inconsistency"],
        "recommended_next_action": (
            "Confirm duplicate with registry; exclude from denominator "
            "(already counted via canonical power_shlc_midfreq)."
        ),
    },
    "ts3_acb_4bet_biglotto": {
        "classification": DUPLICATE_OR_SUPERSEDED,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": "biglotto_ts3_acb_4bet",
        "evidence_summary": (
            "Alternate naming of canonical strategy biglotto_ts3_acb_4bet. "
            "ts3_acb_4bet_biglotto uses suffix lottery_type (biglotto); canonical uses prefix. "
            "Both refer to the TS3 ACB 4-bet strategy for Big Lotto. "
            "Canonical biglotto_ts3_acb_4bet is REJECTED with 50 DB replay rows."
        ),
        "risk_flags": ["naming_convention_inconsistency"],
        "recommended_next_action": (
            "Confirm duplicate with registry; exclude from denominator "
            "(already counted via canonical biglotto_ts3_acb_4bet)."
        ),
    },
    "ts3_markov_freq_5bet_biglotto": {
        "classification": DUPLICATE_OR_SUPERSEDED,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": "biglotto_ts3_markov_freq_5bet",
        "evidence_summary": (
            "Alternate naming of canonical strategy biglotto_ts3_markov_freq_5bet. "
            "ts3_markov_freq_5bet_biglotto uses suffix lottery_type; canonical uses prefix. "
            "Both refer to the TS3 Markov Freq 5-bet strategy for Big Lotto. "
            "Canonical biglotto_ts3_markov_freq_5bet is REJECTED with 50 DB replay rows."
        ),
        "risk_flags": ["naming_convention_inconsistency"],
        "recommended_next_action": (
            "Confirm duplicate with registry; exclude from denominator "
            "(already counted via canonical biglotto_ts3_markov_freq_5bet)."
        ),
    },

    # ---- NEEDS_OPERATOR_DECISION ----
    # Two strategies with UNKNOWN lifecycle that appeared in p2 dry run as ONLINE
    # (had prediction_items rows at some point), but have no current DB rows
    # and no registry entry. Evidence insufficient for automated classification.
    "fourier_rhythm_3bet": {
        "classification": NEEDS_OPERATOR_DECISION,
        "recommended_lifecycle_status": "UNKNOWN",
        "recommended_replay_display_semantics": "UNKNOWN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "Appeared in p2_lifecycle_backfill_dry_run_manifest_20260510 as lifecycle_status=ONLINE "
            "with source_evidence=lottery_api/data/lottery_v2.db:prediction_items. "
            "Currently: 0 rows in strategy_prediction_replays, 0 rows in prediction_items. "
            "Not in canonical registry. Was live at some point — unclear if renamed, retired, or removed. "
            "Missing: registry governance decision, rename history."
        ),
        "risk_flags": ["was_live_no_tombstone", "no_registry_entry"],
        "recommended_next_action": (
            "Operator must determine: (A) renamed to a canonical strategy, "
            "(B) retired without registry entry (→ add tombstone), or "
            "(C) false positive in p2 dry run. Then classify as PRODUCT_DENOMINATOR or RESEARCH_ARCHIVE."
        ),
    },
    "ts3_regime_3bet": {
        "classification": NEEDS_OPERATOR_DECISION,
        "recommended_lifecycle_status": "UNKNOWN",
        "recommended_replay_display_semantics": "UNKNOWN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "Appeared in p2_lifecycle_backfill_dry_run_manifest_20260510 as lifecycle_status=ONLINE "
            "with source_evidence=lottery_api/data/lottery_v2.db:prediction_items. "
            "Currently: 0 rows in strategy_prediction_replays, 0 rows in prediction_items. "
            "Not in canonical registry. ts3_regime_3bet could be a regime-switching variant "
            "of canonical ts3 strategies (biglotto_ts3_acb_4bet or biglotto_ts3_markov_freq_5bet). "
            "Missing: registry governance decision, rename/merge history."
        ),
        "risk_flags": ["was_live_no_tombstone", "no_registry_entry", "possible_ts3_variant"],
        "recommended_next_action": (
            "Operator must determine: (A) merged into canonical ts3 strategy, "
            "(B) retired without registry entry (→ add tombstone), or "
            "(C) false positive in p2 dry run. Then classify as PRODUCT_DENOMINATOR or DUPLICATE_OR_SUPERSEDED."
        ),
    },

    # ---- PRODUCT_DENOMINATOR: Properly evaluated and rejected strategies ----
    # All have: stable strategy_id, identified lottery_type, replay_display_eligible=True,
    # clear rejection evidence or well-defined research identity.
    # Should appear in replay page as REJECTED/FROZEN or RETIRED/NO_DATA entries.
    "539_3bet_orthogonal": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "DAILY_539. REJECTED. replay_display_eligible=True. "
            "Rejection: orthogonal overlap resolved (13.4→15 unique) but individual signal quality "
            "insufficient (permutation p=0.2388)."
        ),
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "acb_extremecol_2bet_539": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "DAILY_539. REJECTED. replay_display_eligible=True. ACB+ExtremeCol 2-bet combination.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "acb_hot_fourier_3bet_biglotto": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "BIG_LOTTO. REJECTED. replay_display_eligible=True. "
            "Rejection: McNemar p=0.545, cannot confirm superiority over Triple Strike."
        ),
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "acb_lag_echo_2bet_539": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "DAILY_539. REJECTED. replay_display_eligible=True. ACB+LagEcho 2-bet combination.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "acb_markov_extremecol_3bet_539": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "DAILY_539. REJECTED. replay_display_eligible=True. ACB+Markov+ExtremeCol 3-bet.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "acb_single_539": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "DAILY_539. REJECTED. replay_display_eligible=True. "
            "McNemar vs Cold p=0.0527 (marginal), vs StateSpace p=0.194."
        ),
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "apriori_3bet_biglotto": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "BIG_LOTTO. REJECTED. replay_display_eligible=True. Apriori association rules 3-bet.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "bandit_ucb1_2bet_539": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "DAILY_539. REJECTED. replay_display_eligible=True. "
            "Edge +1.84% far below manual MidFreq+ACB (+4.44%); bandit cannot learn optimal fixed policy."
        ),
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "bet2_fourier_expansion_biglotto": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "BIG_LOTTO. REJECTED. replay_display_eligible=True. Fourier expansion 2-bet.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "biglotto_6bet_zone_residual": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "BIG_LOTTO. REJECTED. replay_display_eligible=True. Zone residual 6-bet strategy.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "cluster_pivot_biglotto": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "BIG_LOTTO. REJECTED. replay_display_eligible=True. Cluster pivot strategy.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "cold_burst_3bet_539": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "DAILY_539. REJECTED. replay_display_eligible=True. Cold burst 3-bet strategy.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "cold_complement_biglotto": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "BIG_LOTTO. REJECTED. replay_display_eligible=True. Cold complement strategy.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "coldpool15_biglotto": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "BIG_LOTTO. REJECTED. replay_display_eligible=True. "
            "All three windows deteriorate: 150p=-2.67%, 500p=-1.20%, 1500p=-0.73%."
        ),
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "condfourier_3bet_539": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "DAILY_539. REJECTED. replay_display_eligible=True. "
            "Conditional Fourier 3-bet — abbreviated form of conditional_fourier_539. "
            "Distinct experiment with its own evaluation artifact."
        ),
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "conditional_fourier_539": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "DAILY_539. REJECTED. replay_display_eligible=True. "
            "Conditional Fourier strategy — distinct evaluation from condfourier_3bet_539."
        ),
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "consecutive_pair_detector_539": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "DAILY_539. REJECTED. replay_display_eligible=True. "
            "Rejection: Lift 1.08x non-actionable — consecutive pair occurrence only 3.2pp above random."
        ),
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "core_satellite_biglotto": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "BIG_LOTTO. REJECTED. replay_display_eligible=True. Core-satellite portfolio strategy.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "ewma_539": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "DAILY_539. REJECTED. replay_display_eligible=True. EWMA-based strategy.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "extreme_col_539": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "DAILY_539. REJECTED. replay_display_eligible=True. "
            "Base ExtremeCol strategy — precursor to extremecol_1bet_539 variants."
        ),
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "extremecol_1bet_539": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "DAILY_539. REJECTED. replay_display_eligible=True. ExtremeCol 1-bet variant.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "fourier30_markov30_biglotto": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "BIG_LOTTO. REJECTED. replay_display_eligible=True. Fourier(30)+Markov(30) combined.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "fourier_w100_pp3_power": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "POWER_LOTTO. REJECTED. replay_display_eligible=True. Fourier w100 + PP3 Power Lotto.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "gap_dynamic_threshold_biglotto": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "BIG_LOTTO. REJECTED. replay_display_eligible=True. Dynamic gap threshold strategy.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "gap_rebound_powerlotto": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "POWER_LOTTO. REJECTED. replay_display_eligible=True. Gap rebound strategy.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "habit_aware_fourier_v8_539": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "DAILY_539. REJECTED. replay_display_eligible=True. Habit-aware Fourier v8.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "hot_gap_return_biglotto": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "BIG_LOTTO. REJECTED. replay_display_eligible=True. Hot-gap return strategy.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "hot_stop_rebound_biglotto": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "BIG_LOTTO. REJECTED. replay_display_eligible=True. "
            "1500p Edge=+0.01% (essentially 0), z=+0.02, p=0.4924. Statistically insignificant."
        ),
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "hot_streak_override_biglotto": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "BIG_LOTTO. REJECTED. replay_display_eligible=True. Hot streak override strategy.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "lag_echo_1bet_539": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "DAILY_539. REJECTED. replay_display_eligible=True. LagEcho 1-bet strategy.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "lag_echo_acb_markov_3bet_539": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "DAILY_539. REJECTED. replay_display_eligible=True. LagEcho+ACB+Markov 3-bet.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "lift_pair_single_539": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "DAILY_539. REJECTED. replay_display_eligible=True. "
            "1500p Edge negative (-0.38%), inconsistent across three windows."
        ),
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "mab_ucb1_539": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "DAILY_539. REJECTED. replay_display_eligible=True. MAB UCB1 strategy.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "markov_1bet_539": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "DAILY_539. REJECTED. replay_display_eligible=True. "
            "z=1.22 (p≈0.11), below significance threshold p<0.05."
        ),
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "markov_2bet_biglotto": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "BIG_LOTTO. REJECTED. replay_display_eligible=True. Markov 2-bet strategy.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "markov_repeat_exception_biglotto": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "BIG_LOTTO. REJECTED. replay_display_eligible=True. Markov repeat exception strategy.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "markov_single_biglotto": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "BIG_LOTTO. REJECTED. replay_display_eligible=True. Markov single-number strategy.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "midfreq_extremecol_2bet_539": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "DAILY_539. REJECTED. replay_display_eligible=True. MidFreq+ExtremeCol 2-bet.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "momentum_regime_switching_539": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "DAILY_539. REJECTED. replay_display_eligible=True. Momentum regime-switching strategy.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "multiwindow_fourier_biglotto": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "BIG_LOTTO. REJECTED. replay_display_eligible=True. Multi-window Fourier strategy.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "neighbor_acb_2bet_539": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "DAILY_539. REJECTED. replay_display_eligible=True. "
            "Neighbour+ACB 2-bet weaker than MidFreq+ACB (2.79% vs 5.13%, McNemar p=0.0743)."
        ),
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "neighbor_injection_biglotto": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "BIG_LOTTO. REJECTED. replay_display_eligible=True. Neighbour injection strategy.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "p1_conditional_branch_powerlotto": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "POWER_LOTTO. REJECTED. replay_display_eligible=True. "
            "P1 conditional branch strategy for Power Lotto — follows p1_* product naming convention "
            "matching canonical p1_deviation_2bet_539 (REJECTED in registry). "
            "Was formally evaluated as a product candidate."
        ),
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "power_echo_boost": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "POWER_LOTTO. REJECTED. replay_display_eligible=True. Power echo boost strategy.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "power_pp3v2_combined": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "POWER_LOTTO. REJECTED. replay_display_eligible=True. "
            "PP3v2 combined variant — distinct experiment from canonical power_precision_3bet."
        ),
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "power_z3gap_watch": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "POWER_LOTTO. REJECTED. replay_display_eligible=True. Z3 gap watch strategy.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "short_term_hot_independent_bet": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "UNKNOWN lottery_type. REJECTED. replay_display_eligible=True. Short-term hot independent bet.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "special_mab_decay_adjustment_power": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "POWER_LOTTO. REJECTED. replay_display_eligible=True. Special MAB decay adjustment.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "streak_boost_neighbor_bet1": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "UNKNOWN lottery_type. REJECTED. replay_display_eligible=True. "
            "Interaction cancellation effect with multi-window fusion: 1500p Edge=+0.65% < original +1.05%, perm p=0.1."
        ),
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "structural_zone_guard_pp3_power": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "POWER_LOTTO. REJECTED. replay_display_eligible=True. Structural zone guard PP3.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "zone_cascade_guard_biglotto": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": "BIG_LOTTO. REJECTED. replay_display_eligible=True. Zone cascade guard strategy.",
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "zone_constraint_cold_bet2": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "UNKNOWN lottery_type. REJECTED. replay_display_eligible=True. "
            "Zone constraint with cold bet2 — adding zone constraint (Z3>=3) reduced hit rate (71 < 74)."
        ),
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
    "zone_gap_3bet_539": {
        "classification": PRODUCT_DENOMINATOR,
        "recommended_lifecycle_status": "REJECTED",
        "recommended_replay_display_semantics": "FROZEN",
        "canonical_or_successor_strategy_id": None,
        "evidence_summary": (
            "DAILY_539. REJECTED. replay_display_eligible=True. "
            "Failed permutation test — M2+ not superior to random 3-bet baseline."
        ),
        "risk_flags": [],
        "recommended_next_action": "Add to registry as REJECTED when P1.2 registry proposal is created.",
    },
}


def _get_base_commit(repo_root: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root, capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def _get_source_branch(repo_root: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root, capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def load_inventory(inventory_path: str) -> list[dict]:
    with open(inventory_path) as f:
        d = json.load(f)
    return [x for x in d["strategies"] if not x["in_registry"] and not x["in_db"]]


def build_classifications(artifact_only: list[dict]) -> list[dict]:
    result = []
    missing = []
    for item in artifact_only:
        sid = item["strategy_id"]
        if sid not in CLASSIFICATIONS:
            missing.append(sid)
            continue
        clf = CLASSIFICATIONS[sid]
        result.append({
            "strategy_id": sid,
            "classification": clf["classification"],
            "recommended_lifecycle_status": clf["recommended_lifecycle_status"],
            "recommended_replay_display_semantics": clf["recommended_replay_display_semantics"],
            "evidence_files": item.get("source_files", []),
            "evidence_summary": clf["evidence_summary"],
            "canonical_or_successor_strategy_id": clf["canonical_or_successor_strategy_id"],
            "risk_flags": clf["risk_flags"],
            "recommended_next_action": clf["recommended_next_action"],
        })
    if missing:
        print(f"[WARN] {len(missing)} strategy IDs not in CLASSIFICATIONS table: {missing}", file=sys.stderr)
    return result


def build_output(
    inventory_path: str,
    repo_root: str,
    classifications: list[dict],
    artifact_only_input_count: int,
) -> dict:
    from collections import Counter
    clf_ctr = Counter(x["classification"] for x in classifications)

    product_denom_count  = clf_ctr.get(PRODUCT_DENOMINATOR, 0)
    research_count       = clf_ctr.get(RESEARCH_ARCHIVE, 0)
    duplicate_count      = clf_ctr.get(DUPLICATE_OR_SUPERSEDED, 0)
    non_strategy_count   = clf_ctr.get(NON_STRATEGY_ARTIFACT, 0)
    needs_decision_count = clf_ctr.get(NEEDS_OPERATOR_DECISION, 0)

    # Clean denominator = canonical 16 + artifact-only PRODUCT_DENOMINATOR
    # DUPLICATE_OR_SUPERSEDED are already counted in canonical 16 (their canonical counterparts)
    canonical_count = 16
    clean_denom = canonical_count + product_denom_count  # no double-counting duplicates

    # Coverage against clean denominator
    # COVERED = 6 (ONLINE strategies with DB rows)
    # PARTIAL = 4 (REJECTED/OBSERVATION with DB rows) — all are in canonical 16
    covered_count = 6
    partial_count = 4

    estimated_rate = f"{covered_count}/{clean_denom}"
    estimated_pct  = f"{covered_count / clean_denom * 100:.1f}%"

    operator_queue = [
        {
            "strategy_id": x["strategy_id"],
            "classification": x["classification"],
            "missing_evidence": x["evidence_summary"],
            "risk_flags": x["risk_flags"],
            "recommended_next_action": x["recommended_next_action"],
        }
        for x in classifications if x["classification"] == NEEDS_OPERATOR_DECISION
    ]

    return {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "source_inventory_pr": 103,
        "source_branch": _get_source_branch(repo_root),
        "base_commit": _get_base_commit(repo_root),
        "final_classification": "P11_STRATEGY_DENOMINATOR_CLEANUP_READY",
        "summary": {
            "product_denominator_count":      product_denom_count,
            "research_archive_count":         research_count,
            "duplicate_or_superseded_count":  duplicate_count,
            "non_strategy_artifact_count":    non_strategy_count,
            "needs_operator_decision_count":  needs_decision_count,
            "artifact_only_input_count":      artifact_only_input_count,
            "canonical_registry_count":       canonical_count,
            "recommended_clean_denominator_count": clean_denom,
            "covered_count_against_clean_denominator": covered_count,
            "partial_count_against_clean_denominator": partial_count,
            "raw_coverage_rate_before_cleanup":    "6/89",
            "raw_coverage_pct_before_cleanup":     "6.7%",
            "estimated_coverage_rate_after_cleanup": estimated_rate,
            "estimated_coverage_pct_after_cleanup":  estimated_pct,
        },
        "classifications": classifications,
        "operator_decision_queue": operator_queue,
    }


def write_json(output: dict, path: str) -> None:
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"[INFO] JSON written: {path}")


def write_csv(classifications: list[dict], path: str) -> None:
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "strategy_id",
        "classification",
        "recommended_lifecycle_status",
        "recommended_replay_display_semantics",
        "evidence_files",
        "canonical_or_successor_strategy_id",
        "risk_flags",
        "recommended_next_action",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in classifications:
            row_copy = dict(row)
            row_copy["evidence_files"] = ";".join(row_copy.get("evidence_files", []))
            row_copy["risk_flags"] = ";".join(row_copy.get("risk_flags", []))
            writer.writerow(row_copy)
    print(f"[INFO] CSV written: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="P1.1 Strategy Denominator Cleanup (read-only)")
    parser.add_argument(
        "--inventory",
        default="outputs/replay/p1_strategy_universe_inventory_20260515.json",
        help="Path to P1 inventory JSON (can be /tmp copy from PR #103 branch)",
    )
    parser.add_argument(
        "--json-out",
        default="outputs/replay/p11_strategy_denominator_cleanup_20260515.json",
    )
    parser.add_argument(
        "--csv-out",
        default="outputs/replay/p11_strategy_denominator_cleanup_20260515.csv",
    )
    args = parser.parse_args()

    repo_root = str(pathlib.Path(__file__).resolve().parent.parent)
    print(f"[INFO] Repo: {repo_root}")
    print(f"[INFO] Inventory: {args.inventory}")

    # Resolve inventory path
    inv_path = args.inventory
    if not os.path.isabs(inv_path):
        inv_path = os.path.join(repo_root, inv_path)

    artifact_only = load_inventory(inv_path)
    print(f"[INFO] Artifact-only strategies loaded: {len(artifact_only)}")

    classifications = build_classifications(artifact_only)

    from collections import Counter
    clf_ctr = Counter(x["classification"] for x in classifications)
    print(f"[INFO] Classification counts: {dict(clf_ctr)}")

    output = build_output(inv_path, repo_root, classifications, len(artifact_only))

    s = output["summary"]
    print(f"Clean denominator:       {s['recommended_clean_denominator_count']}")
    print(f"Coverage after cleanup:  {s['estimated_coverage_rate_after_cleanup']} ({s['estimated_coverage_pct_after_cleanup']})")
    print(f"Needs operator decision: {s['needs_operator_decision_count']}")
    print(f"Final classification:    {output['final_classification']}")

    write_json(output, args.json_out)
    write_csv(classifications, args.csv_out)


if __name__ == "__main__":
    main()
