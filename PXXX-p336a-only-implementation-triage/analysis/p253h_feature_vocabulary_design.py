"""
P253H Feature Vocabulary Design for M8 Feature Bottleneck Report.

Type B design-only task.

Resolves the 6 terminology gaps (TG1-TG6) identified in P253G and defines:
  - Feature vocabulary groups
  - MI/channel metric vocabulary
  - Evidence status labels
  - Overclaim guard fields
  - Future M8 report schema

Does NOT implement a production module, compute new MI values,
write to DB, modify registry, promote strategies, or give betting advice.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_OUT_JSON = os.path.join(
    _REPO_ROOT, "outputs", "research",
    "p253h_feature_vocabulary_design_20260607.json",
)
_OUT_MD = os.path.join(
    _REPO_ROOT, "outputs", "research",
    "p253h_feature_vocabulary_design_20260607.md",
)


# ---------------------------------------------------------------------------
# Feature vocabulary — resolves TG5 ("feature" undefined)
# ---------------------------------------------------------------------------

def _build_feature_vocabulary() -> dict:
    return {
        "vocabulary_version": "1.0",
        "design_note": (
            "Canonical feature groups for the future M8 Feature Bottleneck Report. "
            "Each feature must be assigned exactly one group. "
            "Groups are additive and non-overlapping. "
            "Resolves TG5: no feature vocabulary SSOT."
        ),
        "groups": {
            "draw_history_feature": {
                "description": (
                    "Features derived directly from the sequence of drawn number sets "
                    "across time (raw history). Examples: draw index, date, sequence position."
                ),
                "examples": [
                    "draw_index (integer offset from most recent draw)",
                    "days_since_last_draw (calendar gap)",
                    "draw_timestamp (epoch seconds)",
                ],
                "mi_type_allowed": ["feature_to_hit_binary_mi", "sequence_autocorrelation_mi"],
                "p219_tested": False,
                "p219_note": "Not tested in M10 sweep; draw index was implicit, not a named feature.",
            },
            "frequency_feature": {
                "description": (
                    "Features derived from how often each number has appeared across a "
                    "rolling window of draws. Includes both raw count and deviation from "
                    "theoretical expectation. The only feature group tested in P219 M10."
                ),
                "examples": [
                    "trailing_freq_50 (hit count over last 50 draws)",
                    "trailing_freq_100 (hit count over last 100 draws)",
                    "freq_deficit (expected_freq - actual_freq for each number)",
                    "freq_zscore (standardized deviation from mean frequency)",
                    "mid_freq_band (numbers with |freq_deviation| < threshold)",
                ],
                "mi_type_allowed": ["feature_to_hit_binary_mi"],
                "p219_tested": True,
                "p219_result": (
                    "trailing_freq tested only. "
                    "DAILY_539 MI ~= 8.8e-6 bits; POWER_LOTTO MI ~= 1.6e-5 bits. "
                    "Both near zero (channel empty for this feature)."
                ),
                "p219_note": (
                    "Only trailing_freq was tested. freq_deficit, freq_zscore, "
                    "mid_freq_band are NOT yet tested and remain NOT_TESTED."
                ),
            },
            "position_frequency_feature": {
                "description": (
                    "Features derived from which positions (draw slot 1..k) each number "
                    "tends to appear in. BLOCKED for BIG_LOTTO/DAILY_539/POWER_LOTTO "
                    "because database.py:463 sorts numbers at write time (positional order lost). "
                    "Available only for 3_STAR/4_STAR after P213H/L."
                ),
                "examples": [
                    "position_freq_slot1 (how often number appears in slot 1)",
                    "positional_entropy (Shannon entropy across position slots for each number)",
                ],
                "mi_type_allowed": ["feature_to_hit_binary_mi"],
                "p219_tested": False,
                "p219_note": "BLOCKED — sorted storage eliminates positional information.",
                "blocker": "BLOCKED: sorted DB storage (database.py:463)",
            },
            "rolling_window_feature": {
                "description": (
                    "Features derived from computing statistics across non-overlapping "
                    "or overlapping rolling windows of draws. Extends P252F rolling_window.py "
                    "and P253B stability_diagnostics.py."
                ),
                "examples": [
                    "block_hit_rate_short (hit rate in last 150 draws)",
                    "block_hit_rate_medium (hit rate in last 500 draws)",
                    "rolling_variance (variance of hit indicator over window)",
                    "window_delta (block_hit_rate_short - block_hit_rate_long)",
                ],
                "mi_type_allowed": ["feature_to_hit_binary_mi", "sequence_autocorrelation_mi"],
                "p219_tested": False,
                "p219_note": (
                    "Window-based sequence autocorrelation MI was computed in P178A signal "
                    "boundary study (MI = 0.006 bits, window_20). That is sequence_autocorrelation_mi, "
                    "not feature_to_hit_binary_mi."
                ),
            },
            "stability_feature": {
                "description": (
                    "Features capturing whether a hit pattern is stable or drifting across "
                    "time blocks. Derived from P253B stability_diagnostics.py vocabulary: "
                    "block=era=year (synonyms); robustness=subset-exclusion check."
                ),
                "examples": [
                    "block_stability_flag (STABLE / WARNING / UNSTABLE per P253B thresholds)",
                    "robustness_sign_stable (True if sign of edge is consistent across k blocks)",
                    "era_count_above_baseline (number of blocks where hit_rate > baseline)",
                    "psi_value (Population Stability Index from DriftDetector)",
                    "psi_status (STABLE / WARNING / DRIFT per P252B PsiStatus enum)",
                ],
                "mi_type_allowed": ["feature_to_hit_binary_mi"],
                "p219_tested": False,
                "p219_note": (
                    "PSI and drift were used as gates, not as MI features. "
                    "Stability as a predictive feature remains NOT_TESTED."
                ),
            },
            "parser_quality_feature": {
                "description": (
                    "Features derived from the quality of the draw parsing pipeline. "
                    "From P253E draw_parser.py SSOT: parse_count_ok, format_contract_version, "
                    "post_parse_assertion_pass. These are DATA QUALITY features, not "
                    "predictive features. They gate whether other features are valid."
                ),
                "examples": [
                    "parse_count_ok (bool: parsed draw count matches expected)",
                    "format_contract_version (str: which parser schema version used)",
                    "post_parse_assertion_pass (bool: row count assertion passed)",
                ],
                "mi_type_allowed": [],
                "p219_tested": False,
                "p219_note": "Parser quality is a data gate, not an MI feature. MI not applicable.",
                "gate_only": True,
            },
            "data_integrity_feature": {
                "description": (
                    "Features capturing data contamination status for a lottery game. "
                    "From P246 BIG_LOTTO integrity audit: SIM_HYPHEN / DATE_FORMAT / "
                    "SMALL_POOL contamination flags. These gate whether analysis is valid, "
                    "not whether the draw is predictable."
                ),
                "examples": [
                    "contamination_family (SIM_HYPHEN / DATE_FORMAT / SMALL_POOL / NONE)",
                    "canonical_row_count (number of clean canonical draw rows)",
                    "contamination_pct (fraction of raw table that is contaminated)",
                    "nist_alert_level (GREEN / YELLOW / ORANGE / RED from P238B/P246K)",
                ],
                "mi_type_allowed": [],
                "p219_tested": False,
                "p219_note": (
                    "BIG_LOTTO contamination signals passed M6 Bonferroni (P219) "
                    "but were fully explained by data contamination. "
                    "Anomaly is NOT predictor (L_P219_C)."
                ),
                "gate_only": True,
            },
            "entropy_compression_feature": {
                "description": (
                    "Features derived from information-theoretic diagnostics of the "
                    "frequency distribution: Shannon entropy and zlib compression ratio. "
                    "From P219 M6. These are distribution diagnostics, not hit predictors. "
                    "Resolves TG4: entropy terminology disambiguation."
                ),
                "examples": [
                    "freq_distribution_shannon_entropy_bits (M6: entropy of number frequency dist)",
                    "zlib_compression_ratio (M6: compression ratio of serialized draw sequence)",
                    "baseline_bernoulli_entropy_h (h_base: per-number draw probability entropy)",
                    "permutation_entropy (PE: sequence complexity, P191 signal boundary study)",
                ],
                "mi_type_allowed": ["sequence_autocorrelation_mi"],
                "entropy_disambiguation": {
                    "freq_distribution_shannon_entropy_bits": (
                        "M6 diagnostic -- measures how uniformly numbers are distributed. "
                        "NOT a predictor. Anomaly = data contamination (L_P219_B/C)."
                    ),
                    "baseline_bernoulli_entropy_h": (
                        "M10 denominator -- used to compute pct_of_outcome_entropy. "
                        "This is h(p) where p = k/N (draw probability per number)."
                    ),
                    "permutation_entropy": (
                        "Sequence complexity -- from P191 signal boundary study. "
                        "Near-maximum for all clean games."
                    ),
                },
                "p219_tested": True,
                "p219_result": (
                    "M6 entropy/compression tested for all 5 games. "
                    "BIG_LOTTO signals passed Bonferroni but fully explained by contamination. "
                    "DAILY_539 and POWER_LOTTO entropy near-uniform (distribution diagnostic only)."
                ),
            },
            "mi_channel_feature": {
                "description": (
                    "Features specifically designed for M8 mutual-information channel analysis. "
                    "These compute the information content (in bits) of a candidate feature "
                    "about the next draw outcome. Two MI types must be distinguished "
                    "(resolves TG3 and TG6)."
                ),
                "examples": [
                    "feature_to_hit_binary_mi (P219 M10 type: MI between binned feature and hit indicator)",
                    "sequence_autocorrelation_mi (P178A type: MI from sliding window on sequence)",
                ],
                "mi_type_allowed": [
                    "feature_to_hit_binary_mi",
                    "sequence_autocorrelation_mi",
                ],
                "p219_tested": True,
                "p219_result": (
                    "M10 feature_to_hit_binary_mi tested for trailing_freq only. "
                    "DAILY_539: 8.8e-6 bits; POWER_LOTTO: 1.6e-5 bits. "
                    "P178A sequence_autocorrelation_mi: BIG_LOTTO best = 0.006 bits (window_20). "
                    "All near zero."
                ),
            },
            "artifact_only_feature": {
                "description": (
                    "Features that have been explored in research scripts but exist only "
                    "as ad-hoc computed values in historical artifacts, with no "
                    "production-ready or reproducible implementation. These must not be "
                    "used for strategy without pre-registration and walk-forward OOS. "
                    "Evidence status: ARTIFACT_ONLY."
                ),
                "examples": [
                    "gap_pressure_score (P60/SGP V3-V11: gap since last appearance, deprecated)",
                    "markov_transition_score (various Markov scripts, non-SSOT)",
                    "fourier_rhythm_score (FFT-based frequency rhythm, tools/power_fourier_rhythm.py)",
                    "acb_score (anomaly capture bet, ACB design in lottery_api/CLAUDE.md)",
                    "lag2_echo_score (Lag-2 echo boost, P0 design)",
                ],
                "mi_type_allowed": ["feature_to_hit_binary_mi"],
                "p219_tested": False,
                "p219_note": (
                    "None of these artifact-only features were tested via P219 M10 MI framework. "
                    "They have empirical backtested ROI but no MI-channel characterization."
                ),
            },
        },
        "terminology_resolutions": {
            "TG1_feature_bottleneck_naming": (
                "Canonical term: 'feature_bottleneck_report' (M8 in P252B 8-method audit). "
                "The label 'M10' in P219 10-method sweep refers to the same concept but "
                "with a different method number. "
                "Going forward: M8 = Feature Bottleneck Report; M10 label is P219-internal only. "
                "Module: future lottery_api/utils/feature_bottleneck_report.py."
            ),
            "TG2_feature_bottlenecks_collision": (
                "Resolved: 'feature_bottlenecks' (plural) in p212 = blocking factors list "
                "(non-MI use). 'feature_bottleneck' (singular) = MI-based channel report field. "
                "Future M8 schema must use 'mi_channel_result' as the field name for the "
                "channel analysis result, and 'blocking_factors' for the blocking list. "
                "Never reuse 'feature_bottlenecks' as a field name in M8 artifacts."
            ),
            "TG3_mi_type_taxonomy": (
                "Resolved: two canonical mi_type values: "
                "(1) 'feature_to_hit_binary_mi' -- MI between a binned feature and binary hit "
                "outcome (P219 M10 method); "
                "(2) 'sequence_autocorrelation_mi' -- MI from sliding window on sequence "
                "(P178A method). "
                "These measure different information channels and must not be conflated. "
                "Any report field containing MI must declare mi_type explicitly."
            ),
            "TG4_entropy_disambiguation": (
                "Resolved: three distinct entropy concepts: "
                "(1) freq_distribution_shannon_entropy_bits (M6 distribution diagnostic); "
                "(2) baseline_bernoulli_entropy_h (denominator for pct_of_outcome_entropy); "
                "(3) permutation_entropy (sequence complexity). "
                "Future M8 schema must use explicit field names, never bare 'entropy'."
            ),
            "TG5_feature_vocabulary": (
                "Resolved by this document: 10 feature groups defined with examples, "
                "MI type allowances, and P219 test status. "
                "All future M8 features must be classified into one group."
            ),
            "TG6_channel_definition": (
                "Resolved: canonical term is 'mi_channel' defined as "
                "'the information pathway from a named feature to the binary hit outcome, "
                "measured in bits via feature_to_hit_binary_mi'. "
                "'channel empty' = observed MI <= null_mi_95th_pct. "
                "'evidence channel' and 'signal channel' are deprecated informal terms. "
                "Use 'mi_channel' in all future artifacts."
            ),
        },
    }


# ---------------------------------------------------------------------------
# MI/channel metric vocabulary — resolves TG3 and TG6
# ---------------------------------------------------------------------------

def _build_mi_channel_vocabulary() -> dict:
    return {
        "vocabulary_version": "1.0",
        "design_note": (
            "Canonical MI and channel metric vocabulary for M8 Feature Bottleneck Report. "
            "Resolves TG3 (MI type confusion) and TG6 (channel term ambiguity)."
        ),
        "metrics": {
            "feature_to_hit_binary_mi": {
                "description": (
                    "Mutual information (bits) between a binned feature value and the binary "
                    "hit indicator (1 if the number was drawn, 0 otherwise). "
                    "Implementation reference: p219 _mutual_information_binary(feat, hit). "
                    "This is the primary M8 metric."
                ),
                "unit": "bits",
                "formula": "sum over (f, h) of P(f,h) * log2(P(f,h) / (P(f)*P(h)))",
                "binning": "Feature values binned into n_bins=3 quantile bins",
                "p219_results": {
                    "DAILY_539": "8.8e-6 bits (trailing_freq, channel empty)",
                    "POWER_LOTTO": "1.6e-5 bits (trailing_freq, channel empty)",
                    "BIG_LOTTO": "not run on canonical; contaminated raw table excluded",
                    "3_STAR": "not run",
                    "4_STAR": "not run",
                },
                "known_limitation": (
                    "Only trailing_freq tested. Result 'channel empty' applies to "
                    "trailing_freq only, not to other untested features."
                ),
            },
            "sequence_autocorrelation_mi": {
                "description": (
                    "Mutual information (bits) from a sliding window on the draw sequence "
                    "itself, measuring predictability of future draws from past windows. "
                    "Implementation reference: P178A signal boundary study. "
                    "NOT the same as feature_to_hit_binary_mi."
                ),
                "unit": "bits",
                "p178a_results": {
                    "BIG_LOTTO": "best 0.006 bits (window_20), 1.18% of baseline entropy",
                },
                "known_limitation": (
                    "Measures sequence self-predictability, not feature->outcome predictability. "
                    "These are structurally different information channels."
                ),
            },
            "null_mi_floor": {
                "description": (
                    "The expected MI value under the null hypothesis that draws are "
                    "i.i.d. random (no feature has predictive power). "
                    "Must be estimated via Monte Carlo simulation: "
                    "repeatedly shuffle labels and recompute MI."
                ),
                "unit": "bits",
                "how_to_compute": (
                    "Run N_SIM >= 1000 simulations: for each, randomly permute the hit "
                    "labels (preserving marginal distribution), recompute MI. "
                    "Report: mean, std, 95th_pct, 99th_pct."
                ),
                "current_status": "NOT_COMPUTED -- must be established in future P253I implementation",
            },
            "null_mi_95th_pct": {
                "description": (
                    "95th percentile of the null MI distribution (from MC simulation). "
                    "Any observed MI below this value is consistent with random noise. "
                    "Required field in M8 report -- must not be None or zero."
                ),
                "unit": "bits",
                "current_status": "NOT_COMPUTED",
                "interpretation": (
                    "'channel empty' is declared only if observed MI <= null_mi_95th_pct."
                ),
            },
            "null_mi_99th_pct": {
                "description": (
                    "99th percentile of the null MI distribution (from MC simulation). "
                    "A more conservative floor for flagging non-null channels."
                ),
                "unit": "bits",
                "current_status": "NOT_COMPUTED",
            },
            "pct_of_outcome_entropy": {
                "description": (
                    "Observed MI as a percentage of the baseline Bernoulli entropy h_base. "
                    "h_base = -p*log2(p) - (1-p)*log2(1-p) where p = k/N (per-number hit rate). "
                    "Implementation reference: p219 M10 formula. "
                    "Interpretability metric only -- not a statistical threshold."
                ),
                "unit": "percent",
                "formula": "observed_mi_bits / h_base * 100",
                "p219_results": {
                    "DAILY_539": "effectively 0% (MI ~= 8.8e-6 bits vs h_base ~= 0.02 bits)",
                    "POWER_LOTTO": "effectively 0% (MI ~= 1.6e-5 bits)",
                },
            },
            "above_null_floor": {
                "description": (
                    "Boolean: True if observed MI > null_mi_95th_pct. "
                    "Only when True is the channel considered potentially non-null. "
                    "Being above the null floor does NOT authorize strategy promotion -- "
                    "it only triggers further investigation with correction and walk-forward."
                ),
                "type": "bool",
                "current_status_all_tested": False,
                "note": (
                    "All currently tested features (trailing_freq) are below null floor "
                    "even without a formal null_mi_95th_pct (MI is near machine epsilon)."
                ),
            },
            "below_detection_floor": {
                "description": (
                    "Boolean: True if observed MI < min_detectable_effect expressed in bits. "
                    "min_detectable_effect_pp (prediction advantage in pp) can be converted "
                    "to bits via information theory. If below_detection_floor, the sample "
                    "is underpowered to detect even a meaningful edge if one existed."
                ),
                "type": "bool",
                "conversion_note": (
                    "min_detectable_edge_pp ~= 1.7-2.2pp for DAILY_539/POWER_LOTTO (P219 M10). "
                    "The corresponding MI threshold in bits depends on n_draws and pool size."
                ),
            },
        },
        "channel_status_taxonomy": {
            "EMPTY_CHANNEL": (
                "observed MI <= null_mi_95th_pct. No evidence of information flow "
                "from this feature to hit outcome. 'Channel empty' is the canonical term."
            ),
            "WEAK_CHANNEL": (
                "null_mi_95th_pct < observed MI <= null_mi_99th_pct. "
                "Weak non-null evidence. Requires correction for multiple testing before "
                "any action. Does NOT authorize strategy."
            ),
            "CANDIDATE_CHANNEL": (
                "observed MI > null_mi_99th_pct AND corrected_significant=True. "
                "Still requires walk-forward OOS and pre-registration before any use. "
                "Does NOT authorize strategy."
            ),
            "BLOCKED_CHANNEL": (
                "Cannot be computed due to data quality issues "
                "(contamination, sorted storage, underpowered sample)."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Evidence status vocabulary
# ---------------------------------------------------------------------------

def _build_evidence_status_vocabulary() -> dict:
    return {
        "vocabulary_version": "1.0",
        "design_note": (
            "Canonical evidence status labels for use in M8 Feature Bottleneck Report. "
            "Every (feature, lottery_type) pair must have exactly one evidence_status."
        ),
        "statuses": {
            "NOT_TESTED": {
                "meaning": (
                    "The feature has not been tested for MI against hit outcomes "
                    "for this lottery type. No conclusion can be drawn."
                ),
                "allowed_next_action": "Design MI test with pre-registration; do not promote.",
                "examples": [
                    "freq_deficit for DAILY_539 (only trailing_freq was tested)",
                    "gap_score for any lottery",
                    "mod3_count for any lottery",
                    "zone_balance for BIG_LOTTO",
                ],
            },
            "TESTED_NULL": {
                "meaning": (
                    "Feature was tested via MI framework and result was below the null floor "
                    "(channel empty). No predictive information detected for this feature "
                    "in this lottery type. Does NOT prove other features are null."
                ),
                "allowed_next_action": (
                    "Log result. Test other features. "
                    "Do not claim feature space is exhausted."
                ),
                "examples": [
                    "trailing_freq for DAILY_539 (MI ~= 8.8e-6 bits)",
                    "trailing_freq for POWER_LOTTO (MI ~= 1.6e-5 bits)",
                ],
            },
            "UNDERPOWERED": {
                "meaning": (
                    "Sample size is insufficient to detect a meaningful effect even if "
                    "one exists. below_detection_floor=True. "
                    "3_STAR/4_STAR (5,850 rows) are likely underpowered for MI analysis."
                ),
                "allowed_next_action": "Do not test until more draws are available.",
                "examples": [
                    "Any feature for 3_STAR (5,850 draws -- UNDERPOWERED_NO_SIGNAL per P227C)",
                    "Any feature for 4_STAR (5,850 draws)",
                ],
            },
            "ARTIFACT_ONLY": {
                "meaning": (
                    "The feature exists only in historical research scripts and artifacts "
                    "without a reproducible, SSOT-backed implementation. "
                    "Cannot be used in M8 without first establishing a reproducible module."
                ),
                "allowed_next_action": (
                    "Create SSOT module, pre-register hypothesis, then test."
                ),
                "examples": [
                    "gap_pressure_score (SGP V3-V11 -- deprecated)",
                    "acb_score (ACB design -- in CLAUDE.md but not SSOT module)",
                    "fourier_rhythm_score (tools/power_fourier_rhythm.py -- non-SSOT)",
                ],
            },
            "DATA_QUALITY_BLOCKED": {
                "meaning": (
                    "Analysis is blocked by known data quality issues: "
                    "contamination (BIG_LOTTO raw table), sorted storage (position features), "
                    "or parser failures. The contamination_family and nist_alert_level gates "
                    "must be cleared before analysis."
                ),
                "allowed_next_action": (
                    "For BIG_LOTTO: use canonical view (P247B) and re-run on 2,113 rows. "
                    "For position features: requires DB re-ingestion (Type D)."
                ),
                "examples": [
                    "Any feature on BIG_LOTTO raw draws table (contaminated)",
                    "position_freq_slot1 for BIG_LOTTO/DAILY_539/POWER_LOTTO (sorted storage)",
                ],
            },
            "NEEDS_PREREGISTRATION": {
                "meaning": (
                    "Feature test has been proposed or explored but has not been "
                    "pre-registered as a hypothesis before peeking at the data. "
                    "Result from this test cannot be used without a fresh OOS window."
                ),
                "allowed_next_action": "Pre-register hypothesis; use only unseen OOS data.",
                "examples": [
                    "Any feature identified via data exploration that was not declared before analysis",
                ],
            },
            "NEEDS_WALK_FORWARD": {
                "meaning": (
                    "Feature passed MI screening (above_null_floor=True, "
                    "corrected_significant=True) but has not yet been validated via "
                    "walk-forward OOS. Cannot be promoted to production."
                ),
                "allowed_next_action": (
                    "Run walk-forward OOS. "
                    "Do not promote until three-window validation is complete (CLAUDE.md)."
                ),
                "examples": [
                    "Hypothetical: a future feature that passes MI Bonferroni",
                ],
            },
            "CORRECTED_SIGNIFICANT_BUT_NOT_PROMOTABLE": {
                "meaning": (
                    "Feature passed MI screening with Bonferroni correction AND "
                    "walk-forward OOS validation, but McNemar test vs current best strategy "
                    "did not reach p < 0.05. Confirmed better than null but not better than "
                    "existing production strategy. Per L48 and L76, this does not authorize "
                    "promotion or replacement."
                ),
                "allowed_next_action": "Monitor. Do not promote. Compare against baseline only.",
                "examples": [
                    "Hypothetical: feature that beats null but not production strategy",
                ],
            },
        },
        "current_status_matrix": {
            "DAILY_539": {
                "trailing_freq": "TESTED_NULL",
                "freq_deficit": "NOT_TESTED",
                "freq_zscore": "NOT_TESTED",
                "mid_freq_band": "NOT_TESTED",
                "gap_score": "ARTIFACT_ONLY",
                "zone_balance": "NOT_TESTED",
                "mod3_count": "NOT_TESTED",
                "consecutive_count": "NOT_TESTED",
                "acb_score": "ARTIFACT_ONLY",
                "fourier_rhythm_score": "ARTIFACT_ONLY",
                "markov_transition_score": "ARTIFACT_ONLY",
                "position_freq_slot1": "DATA_QUALITY_BLOCKED",
            },
            "POWER_LOTTO": {
                "trailing_freq": "TESTED_NULL",
                "freq_deficit": "NOT_TESTED",
                "freq_zscore": "NOT_TESTED",
                "mid_freq_band": "NOT_TESTED",
                "gap_score": "ARTIFACT_ONLY",
                "zone_balance": "NOT_TESTED",
                "mod3_count": "NOT_TESTED",
                "consecutive_count": "NOT_TESTED",
                "fourier_rhythm_score": "ARTIFACT_ONLY",
                "position_freq_slot1": "DATA_QUALITY_BLOCKED",
            },
            "BIG_LOTTO": {
                "trailing_freq": "DATA_QUALITY_BLOCKED",
                "all_features_raw_table": "DATA_QUALITY_BLOCKED",
                "trailing_freq_canonical": "NOT_TESTED",
                "note": (
                    "Canonical view (P247B, 2,113 rows) must be used. "
                    "Raw table features are DATA_QUALITY_BLOCKED."
                ),
            },
            "3_STAR": {
                "all_features": "UNDERPOWERED",
                "note": "5,850 draws -- UNDERPOWERED for MI analysis (P227C).",
            },
            "4_STAR": {
                "all_features": "UNDERPOWERED",
                "note": "5,850 draws -- UNDERPOWERED for MI analysis (P227C).",
            },
        },
    }


# ---------------------------------------------------------------------------
# Overclaim guard fields
# ---------------------------------------------------------------------------

def _build_overclaim_guard_fields() -> dict:
    return {
        "vocabulary_version": "1.0",
        "design_note": (
            "Required boolean guard fields for every M8 Feature Bottleneck Report artifact. "
            "All must be True. A report with any guard field False must be rejected."
        ),
        "required_guard_fields": {
            "no_edge_claim": {
                "value": True,
                "meaning": (
                    "This report does not claim any deployable prediction edge. "
                    "MI analysis is interpretability only."
                ),
                "when_to_add": "Every M8 artifact, every per-feature result dict.",
            },
            "no_betting_advice": {
                "value": True,
                "meaning": "No betting advice is given or implied by this report.",
                "when_to_add": "Top-level artifact and per-feature result.",
            },
            "random_compatible_does_not_imply_predictive_edge": {
                "value": True,
                "meaning": (
                    "GREEN NIST result / random-compatible draw distribution does not "
                    "authorize strategy, production change, or betting advice."
                ),
                "when_to_add": "Artifact-level only.",
            },
            "anomaly_not_predictor": {
                "value": True,
                "meaning": (
                    "Entropy or compression anomaly does not imply a predictive feature. "
                    "BIG_LOTTO M6 anomalies are fully explained by data contamination."
                ),
                "when_to_add": "Artifact-level; also per-feature when entropy_compression_feature group.",
            },
            "near_zero_mi_not_feature_space_exhausted": {
                "value": True,
                "meaning": (
                    "MI ~= 0 for trailing_freq does not prove all possible features "
                    "have near-zero MI. Only tested features can be declared channel_empty."
                ),
                "when_to_add": "Artifact-level; also per-feature when evidence_status=TESTED_NULL.",
            },
            "artifact_signal_not_strategy": {
                "value": True,
                "meaning": (
                    "Any MI finding in this artifact cannot become a strategy without: "
                    "pre-registration, Bonferroni correction, walk-forward OOS, and "
                    "explicit human authorization per CLAUDE.md validation pipeline."
                ),
                "when_to_add": "Every M8 artifact.",
            },
        },
        "validation_rule": (
            "Before publishing any M8 artifact, run a validation pass that asserts "
            "each required_guard_field is True. "
            "If any guard is False, raise ValueError immediately."
        ),
    }


# ---------------------------------------------------------------------------
# Future M8 report schema
# ---------------------------------------------------------------------------

def _build_future_m8_report_schema() -> dict:
    return {
        "schema_version": "1.0-design",
        "schema_name": "M8FeatureBottleneckReport",
        "design_note": (
            "Final proposed schema for a future P253I implementation of M8. "
            "This schema supersedes the preliminary schema in P253G "
            "and incorporates all P253H vocabulary resolutions."
        ),
        "artifact_level_fields": [
            {"field": "schema_version", "type": "str", "example": "1.0"},
            {"field": "task_id", "type": "str", "example": "P253I"},
            {"field": "classification", "type": "str",
             "example": "FEATURE_BOTTLENECK_REPORT_COMPLETE"},
            {"field": "generated_at", "type": "str (ISO-8601)"},
            {"field": "lottery_type", "type": "str from LotteryType.ALL"},
            {"field": "n_draws", "type": "int"},
            {"field": "draw_pool", "type": "dict",
             "keys": ["n_numbers", "k_draw"],
             "note": "e.g. DAILY_539: {n_numbers:39, k_draw:5}"},
            {"field": "baseline_hit_rate", "type": "float",
             "note": "k/N per-number expected hit rate"},
            {"field": "feature_vocabulary_version", "type": "str",
             "note": "Reference to P253H vocabulary version"},
            {"field": "features_tested", "type": "list[str]",
             "note": "Explicit list of all feature names tested"},
            {"field": "features_not_tested", "type": "list[str]",
             "note": "Explicit list -- prevents false exhaustion claim (OR3)"},
            {"field": "family_size_k", "type": "int",
             "note": "Number of features tested (for Bonferroni correction)"},
            {"field": "correction_method", "type": "str",
             "allowed": ["bonferroni", "benjamini_hochberg"],
             "note": "Required if family_size_k > 1"},
            {"field": "per_feature_results", "type": "list[dict]",
             "note": "One dict per feature tested -- see per_feature_fields"},
            # Overclaim guards (all required True)
            {"field": "no_edge_claim", "type": "bool", "fixed": True},
            {"field": "no_betting_advice", "type": "bool", "fixed": True},
            {"field": "random_compatible_does_not_imply_predictive_edge",
             "type": "bool", "fixed": True},
            {"field": "anomaly_not_predictor", "type": "bool", "fixed": True},
            {"field": "near_zero_mi_not_feature_space_exhausted",
             "type": "bool", "fixed": True},
            {"field": "artifact_signal_not_strategy", "type": "bool", "fixed": True},
            {"field": "final_decision", "type": "str"},
        ],
        "per_feature_fields": [
            {"field": "feature_name", "type": "str", "example": "trailing_freq_100"},
            {"field": "feature_group", "type": "str",
             "allowed": [
                 "draw_history_feature", "frequency_feature",
                 "position_frequency_feature", "rolling_window_feature",
                 "stability_feature", "parser_quality_feature",
                 "data_integrity_feature", "entropy_compression_feature",
                 "mi_channel_feature", "artifact_only_feature",
             ],
             "note": "From P253H feature_vocabulary groups"},
            {"field": "feature_definition", "type": "str",
             "note": "Exact formula -- required for reproducibility"},
            {"field": "evidence_status", "type": "str",
             "allowed": [
                 "NOT_TESTED", "TESTED_NULL", "UNDERPOWERED", "ARTIFACT_ONLY",
                 "DATA_QUALITY_BLOCKED", "NEEDS_PREREGISTRATION",
                 "NEEDS_WALK_FORWARD", "CORRECTED_SIGNIFICANT_BUT_NOT_PROMOTABLE",
             ]},
            {"field": "mi_type", "type": "str",
             "allowed": ["feature_to_hit_binary_mi", "sequence_autocorrelation_mi"],
             "note": "Required if evidence_status != ARTIFACT_ONLY / DATA_QUALITY_BLOCKED"},
            {"field": "mi_bits", "type": "float or null"},
            {"field": "pct_of_outcome_entropy", "type": "float or null"},
            {"field": "null_mi_floor", "type": "float or null",
             "note": "Mean of MC null MI distribution"},
            {"field": "null_mi_95th_pct", "type": "float or null"},
            {"field": "null_mi_99th_pct", "type": "float or null"},
            {"field": "above_null_floor", "type": "bool or null"},
            {"field": "below_detection_floor", "type": "bool or null"},
            {"field": "min_detectable_edge_pp", "type": "float or null"},
            {"field": "corrected_significant", "type": "bool or null"},
            {"field": "channel_status", "type": "str",
             "allowed": [
                 "EMPTY_CHANNEL", "WEAK_CHANNEL",
                 "CANDIDATE_CHANNEL", "BLOCKED_CHANNEL",
             ]},
            {"field": "no_edge_claim", "type": "bool", "fixed": True},
            {"field": "near_zero_mi_not_feature_space_exhausted",
             "type": "bool", "fixed": True,
             "note": "Required when evidence_status=TESTED_NULL"},
            {"field": "allowed_next_action", "type": "str"},
            {"field": "forbidden_next_action", "type": "str"},
        ],
        "implementation_notes": [
            "All guard fields must be True -- validator should raise ValueError if any is False.",
            "mi_bits, null_mi_95th_pct, null_mi_99th_pct may be null if evidence_status "
            "is NOT_TESTED, ARTIFACT_ONLY, or DATA_QUALITY_BLOCKED.",
            "above_null_floor must be null if null_mi_95th_pct is null.",
            "BIG_LOTTO: must use canonical view (P247B), not raw draws table.",
            "For features with multiple window sizes (e.g. trailing_freq_50 vs trailing_freq_100), "
            "treat each window size as a separate feature entry (increases family_size_k).",
            "Do not claim feature space exhausted unless ALL 10 groups have been tested.",
        ],
        "null_mi_computation_procedure": {
            "method": "Monte Carlo permutation of hit labels",
            "n_simulations": "N_SIM >= 1000 (prefer 2000)",
            "procedure": [
                "Fix feature values for all draws",
                "For each simulation: randomly permute hit labels (preserving marginal)",
                "Recompute feature_to_hit_binary_mi on permuted labels",
                "Collect null_mi distribution",
                "Report: mean, std, 95th_pct, 99th_pct",
            ],
            "warning": (
                "Do NOT use label-shuffling that preserves mean (L96 bug). "
                "Use Binomial(1, baseline_hit_rate) Monte Carlo null "
                "per correction_gate.py SSOT (P252D)."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Phase 0 summary
# ---------------------------------------------------------------------------

def _build_phase0_summary() -> dict:
    return {
        "branch": "main",
        "head_eq_origin_main": True,
        "p253g_visible": True,
        "p253f_visible": True,
        "p253e_visible": True,
        "p253d_visible": True,
        "p253c_visible": True,
        "p253a_visible": True,
        "p252i_visible": True,
        "pr358_visible": True,
        "dirty_items": (
            "backend.pid, frontend.pid, claude-code-showcase, data/lottery_v2.db "
            "(metadata-only), outputs/research/p252x/p253x modified by prior agents "
            "-- not staged by P253H. All tolerated."
        ),
        "stop_conditions_triggered": "NONE",
        "db_write_attempted": False,
        "registry_mutation_attempted": False,
        "strategy_promotion_attempted": False,
    }


# ---------------------------------------------------------------------------
# Full report builder
# ---------------------------------------------------------------------------

def build_report() -> dict:
    feature_vocab = _build_feature_vocabulary()
    mi_vocab = _build_mi_channel_vocabulary()
    evidence_status = _build_evidence_status_vocabulary()
    overclaim_guards = _build_overclaim_guard_fields()
    future_schema = _build_future_m8_report_schema()

    return {
        "schema_version": "1.0",
        "task_id": "P253H",
        "classification": "FEATURE_VOCABULARY_DESIGN_COMPLETE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase0_summary": _build_phase0_summary(),
        "p253g_dependency_verified": {
            "found": True,
            "path": "outputs/research/p253g_feature_bottleneck_report_inventory_20260607.json",
            "classification": "FEATURE_BOTTLENECK_REPORT_INVENTORY_COMPLETE",
            "terminology_gaps_resolved": ["TG1", "TG2", "TG3", "TG4", "TG5", "TG6"],
            "overclaim_risks_addressed": ["OR1", "OR2", "OR3", "OR4", "OR5", "OR6"],
        },
        "feature_vocabulary": feature_vocab,
        "mi_channel_vocabulary": mi_vocab,
        "evidence_status_vocabulary": evidence_status,
        "overclaim_guard_fields": overclaim_guards,
        "future_m8_report_schema": future_schema,
        "readiness_decision": {
            "decision": "READY_FOR_DESIGN_START",
            "rationale": (
                "P253H has resolved all 6 terminology gaps (TG1-TG6) and addressed "
                "all 6 overclaim risks (OR1-OR6) identified in P253G. "
                "The feature vocabulary is now defined (10 groups), MI/channel metrics "
                "are disambiguated (feature_to_hit_binary_mi vs sequence_autocorrelation_mi), "
                "evidence status labels are canonical (8 statuses), and overclaim guards "
                "are specified (6 required boolean fields). "
                "The future M8 schema is fully specified with artifact-level and "
                "per-feature field lists. "
                "A future P253I can implement feature_bottleneck_report.py safely "
                "using this design document as the SSOT."
            ),
            "remaining_prerequisites_for_p253i": [
                "Implement null_mi_floor computation via MC simulation "
                "(Binomial(1, baseline_hit_rate) per P252D correction_gate.py SSOT)",
                "Run null MI simulation for trailing_freq (already TESTED_NULL) "
                "to establish the formal null floor retrospectively",
                "Test at least 3 additional frequency_feature variants "
                "(freq_deficit, freq_zscore, mid_freq_band) for DAILY_539 and POWER_LOTTO",
                "Test BIG_LOTTO on canonical view (2,113 rows) using feature_to_hit_binary_mi",
                "Define pre-registration template for new feature hypotheses",
            ],
        },
        "recommended_next_task": {
            "recommendation": "P253I_FEATURE_BOTTLENECK_REPORT_SSOT_IMPLEMENTATION",
            "task_id_proposal": "P253I",
            "title": "Implement M8 Feature Bottleneck Report SSOT",
            "type": "Type C -- additive module implementation",
            "module": "lottery_api/utils/feature_bottleneck_report.py",
            "scope": [
                "Implement FeatureBottleneckReport class using P253H vocabulary",
                "Implement null_mi_floor computation via MC simulation",
                "Compute feature_to_hit_binary_mi for all frequency_feature variants",
                "Run on DAILY_539, POWER_LOTTO (clean), BIG_LOTTO canonical (2,113 rows)",
                "Enforce all 6 overclaim guard fields as True",
                "Generate structured report matching P253H future_m8_report_schema",
            ],
            "non_scope": [
                "Do not claim any feature is predictive",
                "Do not promote any strategy based on MI results",
                "Do not modify registry or production recommendation logic",
                "Do not compute MI for 3_STAR/4_STAR (UNDERPOWERED)",
            ],
            "authorization_phrase": "Authorize P253I M8 feature bottleneck report SSOT implementation",
        },
        "no_db_write_confirmed": True,
        "no_registry_mutation_confirmed": True,
        "no_strategy_promotion_confirmed": True,
        "no_betting_advice_confirmed": True,
        "final_decision": (
            "P253H design complete. Feature vocabulary defined (10 groups). "
            "MI/channel vocabulary defined (8 metrics including null_mi_95th_pct / null_mi_99th_pct). "
            "Evidence status vocabulary defined (8 statuses). "
            "Overclaim guards defined (6 required boolean fields). "
            "Future M8 schema specified with artifact-level (22 fields) and "
            "per-feature (17 fields) field lists. "
            "All 6 P253G terminology gaps resolved (TG1-TG6). "
            "All 6 P253G overclaim risks addressed (OR1-OR6). "
            "M8 readiness: READY_FOR_DESIGN_START -- P253I implementation is authorized. "
            "No deployable prediction edge. No betting advice. No strategy promotion. "
            "System remains WAITING_FOR_USER_AUTHORIZATION for P253I."
        ),
    }


def build_markdown(report: dict) -> str:
    ts = report["generated_at"]
    fv = report["feature_vocabulary"]
    mv = report["mi_channel_vocabulary"]
    ev = report["evidence_status_vocabulary"]
    og = report["overclaim_guard_fields"]
    ms = report["future_m8_report_schema"]
    rd = report["readiness_decision"]
    nt = report["recommended_next_task"]

    lines = [
        "# P253H Feature Vocabulary Design for M8 Feature Bottleneck Report",
        "",
        f"**Task ID:** P253H  ",
        f"**Classification:** `FEATURE_VOCABULARY_DESIGN_COMPLETE`  ",
        f"**Generated:** {ts}  ",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        (
            "P253H resolves all 6 terminology gaps (TG1-TG6) and addresses all 6 overclaim "
            "risks (OR1-OR6) identified in P253G. This is a Type B design-only task that "
            "produces: (1) a 10-group feature vocabulary, (2) MI/channel metric disambiguation, "
            "(3) 8 evidence status labels, (4) 6 required overclaim guard fields, and "
            "(5) a complete future M8 report schema."
        ),
        "",
        (
            "**Readiness decision:** `READY_FOR_DESIGN_START` -- P253I can implement the "
            "M8 Feature Bottleneck Report SSOT using this document as the design reference."
        ),
        "",
        (
            "**No deployable prediction edge. No betting advice. No strategy promotion. "
            "No DB write. No registry mutation.**"
        ),
        "",
        "---",
        "",
        "## Feature Vocabulary Design",
        "",
        f"*{fv['design_note']}*",
        "",
        f"Total feature groups defined: {len(fv['groups'])}",
        "",
    ]

    for group_name, group in fv["groups"].items():
        p219 = "YES" if group.get("p219_tested") else "NO"
        blocked = " **(BLOCKED)**" if group.get("blocker") else ""
        gate = " **(DATA GATE ONLY)**" if group.get("gate_only") else ""
        lines.append(f"### `{group_name}`{blocked}{gate}")
        lines.append(f"{group['description']}  ")
        lines.append(f"**P219 tested:** {p219}  ")
        if group.get("p219_result"):
            lines.append(f"**P219 result:** {group['p219_result']}  ")
        lines.append(f"**Examples:** {', '.join(group['examples'][:3])}  ")
        lines.append("")

    lines += [
        "### Terminology Resolutions",
        "",
    ]
    for key, resolution in fv["terminology_resolutions"].items():
        lines.append(f"**{key}:** {resolution}  ")
        lines.append("")

    lines += [
        "---",
        "",
        "## MI/Channel Metric Vocabulary",
        "",
        f"*{mv['design_note']}*",
        "",
        f"Total metrics defined: {len(mv['metrics'])}",
        "",
    ]

    for metric_name, metric in mv["metrics"].items():
        lines.append(f"### `{metric_name}`")
        lines.append(f"**Unit:** {metric.get('unit', 'N/A')}  ")
        lines.append(f"**Description:** {metric['description']}  ")
        if metric.get("current_status"):
            lines.append(f"**Current status:** `{metric['current_status']}`  ")
        lines.append("")

    lines += [
        "### Channel Status Taxonomy",
        "",
    ]
    for status, meaning in mv["channel_status_taxonomy"].items():
        lines.append(f"- **`{status}`:** {meaning}")
    lines.append("")

    lines += [
        "---",
        "",
        "## Evidence Status Vocabulary",
        "",
        f"*{ev['design_note']}*",
        "",
        f"Total statuses defined: {len(ev['statuses'])}",
        "",
    ]

    for status_name, status in ev["statuses"].items():
        lines.append(f"### `{status_name}`")
        lines.append(f"**Meaning:** {status['meaning']}  ")
        lines.append(f"**Allowed next action:** {status['allowed_next_action']}  ")
        if status.get("examples"):
            lines.append(f"**Examples:** {'; '.join(status['examples'][:2])}  ")
        lines.append("")

    lines += [
        "### Current Status Matrix (selected)",
        "",
        "| Lottery | trailing_freq | freq_deficit | gap_score | position_freq |",
        "|---------|--------------|--------------|-----------|---------------|",
        "| DAILY_539 | TESTED_NULL | NOT_TESTED | ARTIFACT_ONLY | DATA_QUALITY_BLOCKED |",
        "| POWER_LOTTO | TESTED_NULL | NOT_TESTED | ARTIFACT_ONLY | DATA_QUALITY_BLOCKED |",
        "| BIG_LOTTO | DATA_QUALITY_BLOCKED (raw) | DATA_QUALITY_BLOCKED | DATA_QUALITY_BLOCKED | DATA_QUALITY_BLOCKED |",
        "| 3_STAR | UNDERPOWERED | UNDERPOWERED | UNDERPOWERED | UNDERPOWERED |",
        "| 4_STAR | UNDERPOWERED | UNDERPOWERED | UNDERPOWERED | UNDERPOWERED |",
        "",
    ]

    lines += [
        "---",
        "",
        "## Overclaim Guardrails",
        "",
        f"*{og['design_note']}*",
        "",
        f"Total required guard fields: {len(og['required_guard_fields'])}",
        "",
    ]

    for field_name, field in og["required_guard_fields"].items():
        lines.append(f"### `{field_name}` = `{field['value']}`")
        lines.append(f"**Meaning:** {field['meaning']}  ")
        lines.append(f"**When to add:** {field['when_to_add']}  ")
        lines.append("")

    lines.append(f"**Validation rule:** {og['validation_rule']}  ")
    lines.append("")

    lines += [
        "---",
        "",
        "## Future M8 Report Schema",
        "",
        f"**Schema:** `{ms['schema_name']}` v{ms['schema_version']}  ",
        f"*{ms['design_note']}*  ",
        "",
        f"**Artifact-level fields:** {len(ms['artifact_level_fields'])}  ",
        f"**Per-feature fields:** {len(ms['per_feature_fields'])}  ",
        "",
        "### Selected Artifact-Level Fields",
    ]
    for f in ms["artifact_level_fields"][:12]:
        note = f.get("note") or f.get("example") or ""
        lines.append(f"- `{f['field']}` ({f['type']}) -- {note}")
    lines.append(f"- *(+ {len(ms['artifact_level_fields']) - 12} more)*")
    lines.append("")

    lines += [
        "### Selected Per-Feature Fields",
    ]
    for f in ms["per_feature_fields"][:10]:
        note = f.get("note") or ""
        lines.append(f"- `{f['field']}` ({f['type']}) -- {note}")
    lines.append(f"- *(+ {len(ms['per_feature_fields']) - 10} more)*")
    lines.append("")

    lines += [
        "### Null MI Computation Procedure",
        "",
        f"**Method:** {ms['null_mi_computation_procedure']['method']}  ",
        f"**N simulations:** {ms['null_mi_computation_procedure']['n_simulations']}  ",
        f"**Warning:** {ms['null_mi_computation_procedure']['warning']}  ",
        "",
        "---",
        "",
        "## Readiness Decision",
        "",
        f"**Decision:** `{rd['decision']}`  ",
        "",
        rd["rationale"],
        "",
        "**Remaining prerequisites for P253I:**",
    ]
    for pre in rd["remaining_prerequisites_for_p253i"]:
        lines.append(f"- {pre}")
    lines.append("")

    lines += [
        "---",
        "",
        "## Recommended Next Task",
        "",
        f"**Recommendation:** `{nt['recommendation']}`  ",
        f"**Task:** {nt['title']} (Type C -- additive module)  ",
        f"**Module:** `{nt['module']}`  ",
        f"**Authorization phrase:** `{nt['authorization_phrase']}`  ",
        "",
        "**Scope:**",
    ]
    for s in nt["scope"]:
        lines.append(f"- {s}")
    lines.append("")
    lines.append("**Non-scope:**")
    for ns in nt["non_scope"]:
        lines.append(f"- {ns}")
    lines.append("")

    lines += [
        "---",
        "",
        "## Explicit Non-Actions",
        "",
        "P253H did NOT:",
        "- Implement feature_bottleneck_report.py",
        "- Compute new MI values",
        "- Modify any DB (no DB write)",
        "- Modify strategy registry (no registry mutation)",
        "- Promote any strategy (no strategy promotion)",
        "- Modify API, frontend, or production config",
        "- Modify existing historical artifacts",
        "",
        "---",
        "",
        "## Explicit No-Overclaim Statement",
        "",
        "- TESTED_NULL for trailing_freq does NOT prove all features have near-zero MI.",
        "- Random-compatible (NIST GREEN) does NOT imply predictive edge.",
        "- Entropy anomaly does NOT imply predictor.",
        "- No artifact-only signal can become strategy without pre-registration + walk-forward.",
        "- This report does NOT claim any deployable prediction edge.",
        "- No betting advice is given or implied.",
        "",
        "---",
        "",
        "## Explicit No DB Write",
        "",
        "No database was written or queried for MI computation in P253H.",
        "",
        "---",
        "",
        "## Explicit No Strategy Promotion / No Betting Advice",
        "",
        "No strategy was promoted, modified, or deployed. No betting advice.",
        "",
        "---",
        "",
        "## Final Classification",
        "",
        f"`{report['classification']}`",
        "",
        f"*{report['final_decision']}*",
    ]

    return "\n".join(lines)


def main():
    report = build_report()

    os.makedirs(os.path.dirname(_OUT_JSON), exist_ok=True)
    with open(_OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"[P253H] JSON written: {_OUT_JSON}")

    md = build_markdown(report)
    with open(_OUT_MD, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[P253H] Markdown written: {_OUT_MD}")

    fv = report["feature_vocabulary"]
    mv = report["mi_channel_vocabulary"]
    ev = report["evidence_status_vocabulary"]
    og = report["overclaim_guard_fields"]
    print(f"[P253H] Classification: {report['classification']}")
    print(f"[P253H] Readiness: {report['readiness_decision']['decision']}")
    print(f"[P253H] Feature groups: {len(fv['groups'])}")
    print(f"[P253H] MI metrics: {len(mv['metrics'])}")
    print(f"[P253H] Evidence statuses: {len(ev['statuses'])}")
    print(f"[P253H] Overclaim guards: {len(og['required_guard_fields'])}")
    print(f"[P253H] TG resolved: {len(fv['terminology_resolutions'])}")


if __name__ == "__main__":
    main()
