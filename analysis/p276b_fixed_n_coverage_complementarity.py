"""
P276B — Fixed-N Cross-Strategy Coverage & Complementarity Study (read-only)

Determines whether fixed-N cross-strategy ticket portfolios provide genuine
COMPLEMENTARITY beyond three matched comparators, separating strategy skill
from ticket-count and number-coverage effects:

  1. the best equal-budget single constituent strategy,
  2. an ordinary-random N-distinct-ticket portfolio (uniform legal tickets),
  3. a maximally-diversified-random N-distinct-ticket portfolio
     (coverage-maximizing, minimal pairwise overlap).

SCIENTIFIC STATUS BOUNDARY
--------------------------
This study reuses already-committed, retrospective P273A ticket identities and
reads only settled draw outcomes from the canonical DB (strictly read-only).
ALL draws at or before the frozen cutoff are
RETROSPECTIVE_EXPLORATORY_NONCONFIRMATORY. No historical split is fresh
confirmatory evidence. True confirmation begins only with draws strictly later
than the frozen cutoff. ``prediction_success_claim`` is always False; the
expected status is FUTURE_CONFIRMATION_PENDING. No strategy is promoted, no
registry mutated, no production write performed, no controlled_apply, no
activation.

INVARIANTS (governance)
-----------------------
  - Import-safe: no DB open, no file write, no network/subprocess at import.
  - Reuses the committed P271C scorer (lottery_api.prize_aware_scorer) and
    P271E adapter eligibility WITHOUT modification.
  - Tickets are the FROZEN committed P273A distinct-ticket identities; their
    fingerprints are re-verified (fail-closed) before use.
  - The canonical DB is opened strictly read-only: URI mode=ro, PRAGMA
    query_only=ON, and a SQLite authorizer that denies every write/DDL action.
  - Historical P276B evidence is a bounded post-hoc retrospective analysis:
    a first-N outcome-scoring smoke run occurred before the final round-robin
    selector was adopted. Historical values are descriptive only.
  - The final round-robin selector and full future contract are frozen only
    prospectively from the corrected artifact/commit forward.
  - Reconstructed per-cell/per-window prize-aware counts MUST reproduce the
    committed P273A primary-window observed counts and the P275B success_draws.
    Any mismatch raises and STOPs the run with no artifact written.
  - Prize-aware and M3+ are kept as SEPARATE outcome families (scoring and
    multiple-testing).
  - POWER_LOTTO rows with a missing predicted second zone are excluded as
    missing eligibility; never imputed, never counted as losses.
  - 50-draw (SHORT) windows are integrity / early-warning only and cannot
    support promotion.

artifact_version = "p276b_fixed_n_coverage_complementarity_v2"
scoring_version  = delegated to lottery_api.prize_aware_scorer.SCORING_VERSION
source_verification_status = "MANUAL_VERIFICATION_REQUIRED"
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone

import numpy as np
from scipy import stats

from lottery_api.prize_aware_replay_adapter import (
    ADAPTER_VERSION,
    _check_eligibility,
)
from lottery_api.prize_aware_scorer import (
    SCORING_VERSION,
    SOURCE_VERIFICATION_STATUS,
    score_prize_aware_ticket,
)

# ---------------------------------------------------------------------------
# Frozen identifiers / paths
# ---------------------------------------------------------------------------

TASK_ID = "P276B_FIXED_N_COVERAGE_COMPLEMENTARITY_BUILD"
ARTIFACT_VERSION = "p276b_fixed_n_coverage_complementarity_v2"

CANONICAL_DB_PATH = "lottery_api/data/lottery_v2.db"
DB_OPEN_MODE = "sqlite3 URI mode=ro + PRAGMA query_only=ON + write-denying authorizer"

# Committed scientific inputs (read-only).
P275B_MATRIX_JSON = (
    "outputs/research/p275b_unified_prize_aware_success_matrix_20260616.json"
)
P273A_IDENTITY_JSON = (
    "outputs/research/p273a_distinct_ticket_identity_20260615.json"
)
P273A_PRIMARY_COUNTS_JSON = (
    "outputs/research/p273a_primary_window_observed_counts_20260615.json"
)
P273A_INFERENTIAL_JSON = (
    "outputs/research/p273a_prize_aware_inferential_validation_20260615.json"
)
P271C_SCORER_SRC = "lottery_api/prize_aware_scorer.py"
P271E_ADAPTER_SRC = "lottery_api/prize_aware_replay_adapter.py"

DEFAULT_OUT_JSON = (
    "outputs/research/p276b_fixed_n_coverage_complementarity_20260617.json"
)
DEFAULT_OUT_MD = (
    "outputs/research/p276b_fixed_n_coverage_complementarity_20260617.md"
)

# Pinned committed digest of the P275B matrix (integrity gate).
P275B_CANONICAL_DIGEST = (
    "c1b99e57024f528e39e4beeca03cb22dd3278eb1d356aafbe48d8485695102f6"
)

# Primary windows (SHORT non-promoting). Reference-only window never primary.
PRIMARY_WINDOWS = (50, 300, 750)
SHORT_NON_PROMOTING_WINDOW = 50
INFERENTIAL_WINDOWS = (300, 750)  # MID, LONG (future inferential checkpoints)
WINDOW_LABELS = {50: "SHORT", 300: "MID", 750: "LONG"}

LOTTERY_TYPES = ("DAILY_539", "BIG_LOTTO", "POWER_LOTTO")
PRIMARY_LOTTERY = "DAILY_539"

# Game geometry (mirrors the committed scorer/adapter; used only for random
# ticket generation, never to redefine scoring).
MAIN_PICK_COUNT = {"POWER_LOTTO": 6, "BIG_LOTTO": 6, "DAILY_539": 5}
MAIN_NUMBER_MAX = {"POWER_LOTTO": 38, "BIG_LOTTO": 49, "DAILY_539": 39}
SECOND_ZONE_MAX = 8

# Monte Carlo (canonical run). Tests may pass smaller counts.
GLOBAL_SEED = 20260617
MC_REPLICATES = 10000
MC_Q_SAMPLES = 200000  # samples to estimate per-draw union-win probability Q

# ---------------------------------------------------------------------------
# Bounded retrospective portfolio family (post-hoc for historical evidence).
# Each portfolio pools the per-draw committed tickets of its source cells in
# the listed priority order, dedupes by canonical fingerprint preserving first
# occurrence, and selects exactly `ticket_budget` distinct tickets. A draw with
# fewer than `ticket_budget` distinct tickets is INELIGIBLE for that portfolio
# (never back-filled). Selection is deterministic and outcome-blind.
# ---------------------------------------------------------------------------

BOUNDED_RETROSPECTIVE_PORTFOLIO_FAMILY = [
    # --- PRIMARY: DAILY_539 (max six primary portfolios) ---
    {"portfolio_id": "D539_N3_f4cold3", "lottery_type": "DAILY_539",
     "ticket_budget": 3, "tier": "PRIMARY", "kind": "SINGLE",
     "source_cells": ["daily539_f4cold_3bet"]},
    {"portfolio_id": "D539_N3_acbmm3", "lottery_type": "DAILY_539",
     "ticket_budget": 3, "tier": "PRIMARY", "kind": "SINGLE",
     "source_cells": ["acb_markov_midfreq_3bet"]},
    {"portfolio_id": "D539_N3_f4cold3_x_acbmm3", "lottery_type": "DAILY_539",
     "ticket_budget": 3, "tier": "PRIMARY", "kind": "CROSS",
     "source_cells": ["daily539_f4cold_3bet", "acb_markov_midfreq_3bet"]},
    {"portfolio_id": "D539_N5_f4cold5", "lottery_type": "DAILY_539",
     "ticket_budget": 5, "tier": "PRIMARY", "kind": "SINGLE",
     "source_cells": ["daily539_f4cold_5bet"]},
    {"portfolio_id": "D539_N5_f4cold5_x_acbmm3", "lottery_type": "DAILY_539",
     "ticket_budget": 5, "tier": "PRIMARY", "kind": "CROSS",
     "source_cells": ["daily539_f4cold_5bet", "acb_markov_midfreq_3bet"]},
    {"portfolio_id": "D539_N5_f4cold5_x_f4cold3_x_acbmm3",
     "lottery_type": "DAILY_539", "ticket_budget": 5, "tier": "PRIMARY",
     "kind": "CROSS",
     "source_cells": ["daily539_f4cold_5bet", "daily539_f4cold_3bet",
                      "acb_markov_midfreq_3bet"]},
    # --- SECONDARY: BIG_LOTTO generalization (descriptive only, no promotion) ---
    {"portfolio_id": "BIG_N3_echo3", "lottery_type": "BIG_LOTTO",
     "ticket_budget": 3, "tier": "SECONDARY", "kind": "SINGLE",
     "source_cells": ["biglotto_echo_aware_3bet"]},
    {"portfolio_id": "BIG_N4_ts3markov4", "lottery_type": "BIG_LOTTO",
     "ticket_budget": 4, "tier": "SECONDARY", "kind": "SINGLE",
     "source_cells": ["biglotto_ts3_markov_4bet_w30"]},
]

# Confirmatory FUTURE family (Bonferroni). Only PRIMARY (DAILY_539) CROSS
# portfolios at the two inferential windows (MID, LONG). SHORT cannot promote;
# SECONDARY families are descriptive and excluded from the confirmatory family.
# Frozen size = (#primary CROSS portfolios) x len(INFERENTIAL_WINDOWS).
CONFIRMATORY_PRIMARY_CROSS_PORTFOLIOS = [
    p["portfolio_id"] for p in BOUNDED_RETROSPECTIVE_PORTFOLIO_FAMILY
    if p["tier"] == "PRIMARY" and p["kind"] == "CROSS"
]
CONFIRMATORY_FAMILY_SIZE = (
    len(CONFIRMATORY_PRIMARY_CROSS_PORTFOLIOS) * len(INFERENTIAL_WINDOWS)
)
FAMILY_ALPHA = 0.05
HISTORICAL_STATUS_LABEL = (
    "RETROSPECTIVE_POST_HOC_BOUNDED_EXPLORATORY_NONCONFIRMATORY"
)
HISTORICAL_BONFERRONI_ROLE = "DESCRIPTIVE_MULTIPLICITY_ADJUSTED_ONLY"
SUPERSEDED_IDENTITY_ONLY_FAMILY_SHA256 = (
    "48d0c30d7c7643204a76bd0c6b30823c9d74b3061f10e81042bc2399eeb38440"
)

TICKET_SELECTION_ALGORITHM = {
    "algorithm_id": "ROUND_ROBIN_INTERLEAVE_V1",
    "version": "p276d_corrected_semantics",
    "rules": [
        "iterate ticket positions 0,1,2,...",
        "within each position, visit source strategies in declared source order",
        "dedupe by canonical ticket fingerprint preserving first occurrence",
        "stop exactly at ticket_budget N",
        "draw is ineligible when fewer than N distinct tickets remain",
        "never back-fill with random or outcome-aware tickets",
    ],
    "supersedes_historical_smoke_selector": "FIRST_N_CONCAT_V0",
}

ORDINARY_RANDOM_BASELINE = {
    "algorithm_id": "ORDINARY_RANDOM_DISTINCT_LEGAL_TICKETS_V1",
    "version": "p276b_v1",
    "description":
        "N distinct legal tickets sampled uniformly without replacement; "
        "POWER second zone uniform 1-8.",
}

DIVERSIFIED_RANDOM_BASELINE = {
    "algorithm_id": "MAXIMALLY_DIVERSIFIED_RANDOM_V1",
    "version": "p276b_v1",
    "description":
        "Seeded universe-permutation disjoint blocks maximizing number coverage "
        "and minimizing pairwise overlap; POWER second zone seeded "
        "coverage-maximizing.",
}

PRIMARY_HYPOTHESES = [
    {
        "hypothesis_id": "P276D-FUTURE-H1-PRIZE-AWARE-CROSS-BEATS-CONSTITUENTS-AND-DIVERSIFIED",
        "outcome_family": "prize_aware",
        "claim":
            "A fixed-N strategy portfolio has higher prize-aware union success "
            "than both every required equal-N constituent comparator and the "
            "maximally-diversified-random equal-N baseline.",
    }
]


class P276BError(RuntimeError):
    """Raising one STOPs the run with no artifact written (fail-closed)."""


class ReproductionError(P276BError):
    """Reconstructed counts do not reproduce committed counts."""


class IntegrityError(P276BError):
    """A committed input failed an integrity / digest / fingerprint check."""


class DBReadOnlyError(P276BError):
    """Read-only access or the write-denying authorizer could not be verified."""


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _strip_keys(obj, exclude):
    """Recursively drop keys in `exclude` (matches committed digest style)."""
    if isinstance(obj, dict):
        return {k: _strip_keys(v, exclude) for k, v in obj.items()
                if k not in exclude}
    if isinstance(obj, list):
        return [_strip_keys(v, exclude) for v in obj]
    return obj


def canonical_digest(obj, exclude) -> str:
    """Deterministic SHA-256 over `obj` with `exclude` keys removed recursively.

    Serialization matches the committed P273A/P275B convention:
    sort_keys=True, ensure_ascii=False, compact separators.
    """
    payload = _strip_keys(copy.deepcopy(obj), set(exclude))
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# Our artifact's own digest excludes only wall-clock + the self-hash.
SELF_DIGEST_EXCLUDE = frozenset({"canonical_payload_digest", "generated_at"})
# Volatile fields excluded from the committed-payload reproduction digests.
_P275B_SELF_EXCLUDE = frozenset({"canonical_payload_digest", "generated_at"})


def canonical_ticket_serialization(content: dict) -> str:
    """Stable compact JSON used for identity fingerprints (mirrors P273A)."""
    return json.dumps(content, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def canonical_ticket_fingerprint(content: dict) -> str:
    blob = canonical_ticket_serialization(content).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def wilson_interval(successes: int, n: int, z: float = 1.959963984540054):
    """Wilson score 95% interval for a binomial proportion."""
    if n == 0:
        return [None, None]
    p = successes / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return [max(0.0, center - half), min(1.0, center + half)]


def clopper_pearson_interval(successes: int, n: int, alpha: float = 0.05):
    """Clopper-Pearson exact 95% interval for a binomial proportion."""
    if n == 0:
        return [None, None]
    lo = 0.0 if successes == 0 else stats.beta.ppf(alpha / 2, successes,
                                                    n - successes + 1)
    hi = 1.0 if successes == n else stats.beta.ppf(1 - alpha / 2,
                                                    successes + 1,
                                                    n - successes)
    return [float(lo), float(hi)]


def mcnemar_exact(b: int, c: int):
    """Exact two-sided McNemar test on discordant counts b, c.

    b = portfolio wins & comparator loses; c = comparator wins & portfolio loses.
    Returns (n_discordant, p_value). p via exact binomial on min(b,c)~Bin(n,0.5).
    """
    n = b + c
    if n == 0:
        return 0, 1.0
    p = float(stats.binomtest(min(b, c), n, 0.5, alternative="two-sided").pvalue)
    return n, p


def jaccard(set_a: set, set_b: set) -> float:
    union = set_a | set_b
    if not union:
        return None
    return len(set_a & set_b) / len(union)


# ---------------------------------------------------------------------------
# Committed-input loading + integrity verification (no DB, no outcomes)
# ---------------------------------------------------------------------------

def load_and_verify_inputs(p275b_path=P275B_MATRIX_JSON,
                           identity_path=P273A_IDENTITY_JSON,
                           primary_counts_path=P273A_PRIMARY_COUNTS_JSON,
                           inferential_path=P273A_INFERENTIAL_JSON,
                           scorer_path=P271C_SCORER_SRC,
                           adapter_path=P271E_ADAPTER_SRC) -> dict:
    """Load committed inputs and verify their structural invariants.

    Verifies the P275B canonical digest matches the pinned committed value
    (108 rows, 36 frozen cells, windows 50/300/750, prediction_success_claim
    False), re-verifies every committed ticket-identity fingerprint, and
    records SHA-256 of every committed input + the reused scorer/adapter source.
    Raises IntegrityError on any mismatch.
    """
    with open(p275b_path, encoding="utf-8") as fh:
        p275b = json.load(fh)
    with open(identity_path, encoding="utf-8") as fh:
        identity = json.load(fh)
    with open(primary_counts_path, encoding="utf-8") as fh:
        primary_counts = json.load(fh)
    with open(inferential_path, encoding="utf-8") as fh:
        inferential = json.load(fh)

    # --- P275B invariants + digest ---
    if len(p275b.get("matrix_rows", [])) != 108:
        raise IntegrityError("P275B matrix_rows != 108")
    if p275b.get("matrix_summary", {}).get("frozen_cells") != 36:
        raise IntegrityError("P275B frozen_cells != 36")
    if tuple(sorted(p275b["scope"]["primary_windows"].values())) != (50, 300, 750):
        raise IntegrityError("P275B primary windows != 50/300/750")
    if p275b.get("prediction_success_claim") is not False:
        raise IntegrityError("P275B prediction_success_claim is not False")
    embedded = p275b.get("canonical_payload_digest")
    if embedded != P275B_CANONICAL_DIGEST:
        raise IntegrityError(
            f"P275B embedded digest {embedded} != pinned {P275B_CANONICAL_DIGEST}")
    recomputed = canonical_digest(p275b, _P275B_SELF_EXCLUDE)
    if recomputed != P275B_CANONICAL_DIGEST:
        raise IntegrityError(
            f"P275B recomputed digest {recomputed} != pinned "
            f"{P275B_CANONICAL_DIGEST}")

    # --- identity artifact: 36 cells + fingerprint re-verification ---
    cells = identity.get("cells", [])
    if len(cells) != 36:
        raise IntegrityError("P273A identity cells != 36")
    fp_checked = 0
    for cell in cells:
        for sd in cell.get("supported_draws", []):
            for grp in sd.get("canonical_ticket_groups", []):
                content = grp["canonical_ticket_content"]
                recomputed_fp = canonical_ticket_fingerprint(content)
                if recomputed_fp != grp["fingerprint_sha256"]:
                    raise IntegrityError(
                        f"identity fingerprint mismatch in "
                        f"{cell['lottery_type']}/{cell['strategy_id']} "
                        f"draw {sd['target_draw']}")
                fp_checked += 1

    source_hashes = {
        "p275b_matrix_json_sha256": sha256_file(p275b_path),
        "p273a_identity_json_sha256": sha256_file(identity_path),
        "p273a_primary_counts_json_sha256": sha256_file(primary_counts_path),
        "p273a_inferential_json_sha256": sha256_file(inferential_path),
        "p271c_scorer_src_sha256": sha256_file(scorer_path),
        "p271e_adapter_src_sha256": sha256_file(adapter_path),
    }
    return {
        "p275b": p275b,
        "identity": identity,
        "primary_counts": primary_counts,
        "inferential": inferential,
        "source_hashes": source_hashes,
        "fingerprints_reverified": fp_checked,
    }


def canonical_sha256(obj) -> str:
    """Deterministic SHA-256 over a canonical JSON object."""
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _contract_hash_payload(cutoffs=None) -> dict:
    """Full future-contract payload covered by future_contract_sha256."""
    return {
        "artifact_version": ARTIFACT_VERSION,
        "portfolio_family": copy.deepcopy(
            BOUNDED_RETROSPECTIVE_PORTFOLIO_FAMILY),
        "source_strategy_ids_and_order": [
            {
                "portfolio_id": p["portfolio_id"],
                "source_cells": list(p["source_cells"]),
            }
            for p in BOUNDED_RETROSPECTIVE_PORTFOLIO_FAMILY
        ],
        "fixed_ticket_budgets": sorted({
            p["ticket_budget"] for p in BOUNDED_RETROSPECTIVE_PORTFOLIO_FAMILY
        }),
        "primary_fixed_ticket_budgets": [3, 5],
        "ticket_selection_algorithm": copy.deepcopy(TICKET_SELECTION_ALGORITHM),
        "ordinary_random_baseline": copy.deepcopy(ORDINARY_RANDOM_BASELINE),
        "diversified_random_baseline": copy.deepcopy(DIVERSIFIED_RANDOM_BASELINE),
        "global_seed": GLOBAL_SEED,
        "mc_replicates": MC_REPLICATES,
        "mc_q_samples": MC_Q_SAMPLES,
        "primary_hypotheses": copy.deepcopy(PRIMARY_HYPOTHESES),
        "hypothesis_family": {
            "family_id": "P276D_FUTURE_CONFIRMATORY_CROSS_PORTFOLIO_FAMILY",
            "primary_cross_portfolios":
                list(CONFIRMATORY_PRIMARY_CROSS_PORTFOLIOS),
            "future_confirmatory_family_size": CONFIRMATORY_FAMILY_SIZE,
            "lotteries": list(LOTTERY_TYPES),
            "primary_lottery": PRIMARY_LOTTERY,
            "primary_windows": list(PRIMARY_WINDOWS),
            "inferential_windows": list(INFERENTIAL_WINDOWS),
            "short_non_promotion_rule":
                "SHORT_50 is integrity / early-warning only and cannot promote.",
            "correction_policy": "BONFERRONI",
            "bonferroni_per_test_alpha":
                FAMILY_ALPHA / CONFIRMATORY_FAMILY_SIZE,
        },
        "outcome_families": {
            "prize_aware_and_m3plus_separate": True,
            "historical_bonferroni_role": HISTORICAL_BONFERRONI_ROLE,
            "future_bonferroni_policy": "BONFERRONI",
        },
        "cutoff_rule":
            "latest committed-ticket target draw per lottery at contract freeze",
        "cutoff_target_draw_by_lottery": copy.deepcopy(cutoffs),
        "future_eligibility_rule":
            "only draws strictly after both the cutoff target draw and corrected "
            "contract freeze are eligible, and only with prospectively generated "
            "committed tickets",
        "contract_reset_rule":
            "any family, selector, baseline, seed, hypothesis, or correction "
            "change resets the future clock",
    }


def build_bounded_retrospective_analysis_contract() -> dict:
    """Truthful historical contract: bounded, post-hoc, non-confirmatory."""
    identity_only_hash = canonical_sha256(
        BOUNDED_RETROSPECTIVE_PORTFOLIO_FAMILY)
    analysis_payload = {
        "status_label": HISTORICAL_STATUS_LABEL,
        "portfolio_family": copy.deepcopy(
            BOUNDED_RETROSPECTIVE_PORTFOLIO_FAMILY),
        "ticket_selection_algorithm": copy.deepcopy(TICKET_SELECTION_ALGORITHM),
        "historical_bonferroni_role": HISTORICAL_BONFERRONI_ROLE,
        "historical_outcomes_previously_observed": True,
        "selector_changed_after_initial_outcome_run": True,
        "final_selector": "ROUND_ROBIN",
        "bounded_family": True,
        "unbounded_combination_search_performed": False,
        "primary_lottery": PRIMARY_LOTTERY,
        "primary_windows": list(PRIMARY_WINDOWS),
        "fixed_ticket_budgets": [3, 5],
        "global_seed": GLOBAL_SEED,
        "mc_replicates": MC_REPLICATES,
        "mc_q_samples": MC_Q_SAMPLES,
    }
    return {
        "status_label": HISTORICAL_STATUS_LABEL,
        "bounded_family": True,
        "historical_outcomes_previously_observed": True,
        "selector_changed_after_initial_outcome_run": True,
        "execution_chronology": [
            "P276A selected the candidate direction and source strategies after "
            "reviewing prior historical P275B outcome evidence.",
            "An initial first-N ticket selector was used in a historical "
            "outcome-scoring smoke run.",
            "That run showed CROSS portfolio degeneration to the first source "
            "with b/c=0/0.",
            "The selector was then changed to ROUND_ROBIN after those outcomes "
            "had been observed.",
            "Final historical results were generated using ROUND_ROBIN and are "
            "post-hoc descriptive evidence.",
        ],
        "final_selector": "ROUND_ROBIN",
        "ticket_selection_algorithm": copy.deepcopy(TICKET_SELECTION_ALGORITHM),
        "historical_preregistration_claim": False,
        "historical_bonferroni_role": HISTORICAL_BONFERRONI_ROLE,
        "historical_results_are_confirmatory": False,
        "bounded_retrospective_analysis_sha256":
            canonical_sha256(analysis_payload),
        "superseded_identity_only_family_sha256": identity_only_hash,
        "superseded_identity_only_family_hash_note":
            "This hash covers only the portfolio identity list and is retained "
            "for provenance; it is not a historical preregistration hash.",
        "portfolio_family": copy.deepcopy(
            BOUNDED_RETROSPECTIVE_PORTFOLIO_FAMILY),
        "portfolio_family_size": len(BOUNDED_RETROSPECTIVE_PORTFOLIO_FAMILY),
        "fixed_ticket_budgets": [3, 5],
        "descriptive_multiplicity_family_size": CONFIRMATORY_FAMILY_SIZE,
        "descriptive_bonferroni_per_test_alpha":
            FAMILY_ALPHA / CONFIRMATORY_FAMILY_SIZE,
        "short_50_is_integrity_early_warning_only": True,
        "cannot_promote_or_activate": True,
        "cannot_set_prediction_success_claim_true": True,
    }


def build_frozen_future_contract(cutoffs: dict) -> dict:
    """Prospective-only future confirmation contract."""
    payload = _contract_hash_payload(cutoffs)
    return {
        "status": "FUTURE_CONFIRMATION_PENDING",
        "future_confirmation_status": "FUTURE_CONFIRMATION_PENDING",
        "future_contract_prospectively_frozen": True,
        "future_contract_sha256": canonical_sha256(payload),
        "future_contract_hash_coverage": sorted(payload.keys()),
        "cutoff_target_draw_by_lottery": copy.deepcopy(cutoffs),
        "cutoff_note":
            "latest committed-ticket target draw per lottery; genuine "
            "confirmation requires walk-forward strategy predictions for draws "
            "strictly later than the cutoff and after the corrected contract "
            "freeze.",
        "future_evidence_requires_prospectively_generated_tickets": True,
        "historical_results_not_future_confirmation": True,
        "any_contract_change_resets_future_clock": True,
        "future_primary_H1": PRIMARY_HYPOTHESES[0]["claim"],
        "future_H0":
            "The observed union advantage is fully explained by ticket count or "
            "number coverage.",
        "future_confirmatory_family_size": CONFIRMATORY_FAMILY_SIZE,
        "future_bonferroni_policy": "BONFERRONI",
        "bonferroni_per_test_alpha": FAMILY_ALPHA / CONFIRMATORY_FAMILY_SIZE,
        "checkpoints": {
            "future_50": "integrity / early-warning only",
            "future_300": "first inferential checkpoint",
            "future_750": "long inferential checkpoint",
        },
        "ticket_selection_algorithm": copy.deepcopy(TICKET_SELECTION_ALGORITHM),
        "contract_hash_payload": payload,
    }


def build_legacy_identity_only_family_hash() -> str:
    """Provenance hash retained for comparison with the superseded artifact."""
    return canonical_sha256(BOUNDED_RETROSPECTIVE_PORTFOLIO_FAMILY)


def freeze_contract() -> dict:
    """Backward-compatible alias for tests that need the historical contract."""
    return build_bounded_retrospective_analysis_contract()


def build_historical_and_future_contracts(cutoffs=None) -> dict:
    """Build both corrected semantic contracts."""
    historical = build_bounded_retrospective_analysis_contract()
    contracts = {"historical_analysis_contract": historical}
    if cutoffs is not None:
        contracts["frozen_future_contract"] = build_frozen_future_contract(cutoffs)
    else:
        contracts["future_contract_hash_payload_template"] = _contract_hash_payload()
    return contracts


# ---------------------------------------------------------------------------
# Read-only DB access (mode=ro + query_only + write-denying authorizer)
# ---------------------------------------------------------------------------

def _build_deny_action_set():
    """Action codes for INSERT/UPDATE/DELETE/CREATE/DROP/ALTER/ATTACH/DETACH/
    REINDEX and vtable DDL. Resolved via getattr for portability."""
    names = (
        "SQLITE_CREATE_INDEX", "SQLITE_CREATE_TABLE", "SQLITE_CREATE_TEMP_INDEX",
        "SQLITE_CREATE_TEMP_TABLE", "SQLITE_CREATE_TEMP_TRIGGER",
        "SQLITE_CREATE_TEMP_VIEW", "SQLITE_CREATE_TRIGGER", "SQLITE_CREATE_VIEW",
        "SQLITE_DELETE", "SQLITE_DROP_INDEX", "SQLITE_DROP_TABLE",
        "SQLITE_DROP_TEMP_INDEX", "SQLITE_DROP_TEMP_TABLE",
        "SQLITE_DROP_TEMP_TRIGGER", "SQLITE_DROP_TEMP_VIEW", "SQLITE_DROP_TRIGGER",
        "SQLITE_DROP_VIEW", "SQLITE_INSERT", "SQLITE_UPDATE", "SQLITE_ATTACH",
        "SQLITE_DETACH", "SQLITE_ALTER_TABLE", "SQLITE_REINDEX",
        "SQLITE_CREATE_VTABLE", "SQLITE_DROP_VTABLE",
    )
    out = set()
    for nm in names:
        val = getattr(sqlite3, nm, None)
        if val is not None:
            out.add(val)
    return frozenset(out)


_DENY_ACTIONS = _build_deny_action_set()


def _deny_writes_authorizer(action, arg1, arg2, dbname, source):
    """SQLite authorizer: deny every write/DDL action, allow read-only ops.

    Read actions (SELECT/READ/TRANSACTION/PRAGMA/FUNCTION) are permitted; the
    connection is additionally mode=ro + query_only=ON, so the database file
    cannot be mutated even if an allowed action were attempted.
    """
    if action in _DENY_ACTIONS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def open_readonly_connection(db_path: str):
    """Open the DB strictly read-only with three layered guards.

    URI mode=ro, PRAGMA query_only=ON (verified), and a write/DDL-denying
    authorizer. Returns (conn, evidence). Raises DBReadOnlyError on failure.
    """
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.isolation_level = None
    conn.execute("PRAGMA query_only=ON")
    row = conn.execute("PRAGMA query_only").fetchone()
    enabled = bool(row and row[0] == 1)
    if not enabled:
        conn.close()
        raise DBReadOnlyError("PRAGMA query_only did not report enabled")
    conn.set_authorizer(_deny_writes_authorizer)
    evidence = {
        "connection_uri": uri,
        "mode_ro": True,
        "query_only_pragma_value": row[0] if row else None,
        "query_only_enabled": enabled,
        "write_denying_authorizer_installed": True,
        "single_connection": True,
        "single_snapshot": True,
    }
    return conn, evidence


def db_file_metadata(db_path: str) -> dict:
    st = os.stat(db_path)
    return {
        "path_identifier": os.path.basename(db_path),
        "sha256": sha256_file(db_path),
        "size_bytes": st.st_size,
        "modification_time_utc":
            datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
    }


def _parse_numbers(raw):
    if isinstance(raw, list):
        return [int(x) for x in raw]
    return [int(x) for x in json.loads(raw)]


def load_outcomes(conn, needed):
    """Load actual outcomes for the needed (lottery, draw) pairs from `draws`.

    `needed` = dict lottery_type -> set of draw-id strings.
    Returns dict (lottery_type, draw) -> {"main": [...], "special": int|None}.
    Reads only the `draws` table. The draw join must be unique (1 row).
    """
    outcomes = {}
    row_counts = {}
    latest_draw = {}
    cur = conn.cursor()
    # Capture overall table row counts + latest draw per lottery (metadata).
    for lt in LOTTERY_TYPES:
        row_counts[lt] = cur.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type=?", (lt,)).fetchone()[0]
        r = cur.execute(
            "SELECT draw FROM draws WHERE lottery_type=? "
            "ORDER BY CAST(draw AS INTEGER) DESC LIMIT 1", (lt,)).fetchone()
        latest_draw[lt] = r[0] if r else None
    for lt, draws in needed.items():
        for draw in draws:
            rows = cur.execute(
                "SELECT numbers, special FROM draws "
                "WHERE lottery_type=? AND draw=?", (lt, draw)).fetchall()
            if len(rows) != 1:
                raise ReproductionError(
                    f"draw join not unique for {lt}/{draw}: {len(rows)} rows")
            numbers, special = rows[0]
            main = _parse_numbers(numbers)
            sp = None if (special is None or special == 0) else int(special)
            # DAILY_539 has no special; treat stored 0/NULL as None.
            if lt == "DAILY_539":
                sp = None
            outcomes[(lt, draw)] = {"main": main, "special": sp}
    return outcomes, {"draws_row_counts": row_counts, "latest_draw": latest_draw}


# ---------------------------------------------------------------------------
# Per-draw scoring of committed tickets (reuses the committed scorer)
# ---------------------------------------------------------------------------

def _score_ticket(lottery_type, predicted_main, predicted_second_zone,
                  outcome):
    """Score one ticket against an outcome. Returns (prize_aware, m3plus)."""
    actual_main = outcome["main"]
    if lottery_type == "POWER_LOTTO":
        result = score_prize_aware_ticket(
            lottery_type=lottery_type,
            predicted_main_numbers=predicted_main,
            actual_main_numbers=actual_main,
            predicted_second_zone=predicted_second_zone,
            actual_second_zone=outcome["special"],
            actual_special_number=None,
        )
    elif lottery_type == "BIG_LOTTO":
        result = score_prize_aware_ticket(
            lottery_type=lottery_type,
            predicted_main_numbers=predicted_main,
            actual_main_numbers=actual_main,
            predicted_second_zone=None,
            actual_second_zone=None,
            actual_special_number=outcome["special"],
        )
    else:  # DAILY_539
        result = score_prize_aware_ticket(
            lottery_type=lottery_type,
            predicted_main_numbers=predicted_main,
            actual_main_numbers=actual_main,
            predicted_second_zone=None,
            actual_second_zone=None,
            actual_special_number=None,
        )
    return bool(result["any_prize_aware_win"]), bool(result["is_m3_plus"])


def build_cell_per_draw(identity, outcomes):
    """Build per-(lottery,strategy) per-draw distinct tickets + win vectors.

    Returns dict (lottery_type, strategy_id) -> {
        "draws_desc": [draw, ...]   # most-recent first
        "tickets": {draw: [(fingerprint, main_tuple, second_zone|None), ...]}
        "prize_win": {draw: bool}   # union over the cell's distinct tickets
        "m3_win": {draw: bool}
        "ticket_budget": int        # max distinct tickets per draw (native N)
        "duplicate_collapsed": int
    }
    """
    out = {}
    for cell in identity["cells"]:
        lt = cell["lottery_type"]
        sid = cell["strategy_id"]
        tickets = {}          # draw -> [(fingerprint, main_tuple, sz), ...]
        ticket_prize = {}     # draw -> {fingerprint: bool}
        ticket_m3 = {}        # draw -> {fingerprint: bool}
        prize_win = {}        # draw -> union prize-aware win over cell tickets
        m3_win = {}           # draw -> union M3+ win over cell tickets
        budget = 0
        for sd in cell.get("supported_draws", []):
            draw = sd["target_draw"]
            outcome = outcomes.get((lt, draw))
            if outcome is None:
                raise ReproductionError(f"missing outcome for {lt}/{draw}")
            tlist = []
            pmap = {}
            mmap = {}
            pwin = False
            mwin = False
            for grp in sd["canonical_ticket_groups"]:
                content = grp["canonical_ticket_content"]
                fp = grp["fingerprint_sha256"]
                main = tuple(content["main_numbers"])
                sz = content.get("predicted_second_zone")
                tlist.append((fp, main, sz))
                pa, m3 = _score_ticket(lt, list(main), sz, outcome)
                pmap[fp] = pa
                mmap[fp] = m3
                pwin = pwin or pa
                mwin = mwin or m3
            tickets[draw] = tlist
            ticket_prize[draw] = pmap
            ticket_m3[draw] = mmap
            prize_win[draw] = pwin
            m3_win[draw] = mwin
            budget = max(budget, len(tlist))
        draws_desc = sorted(tickets.keys(), key=lambda d: int(d), reverse=True)
        out[(lt, sid)] = {
            "draws_desc": draws_desc,
            "tickets": tickets,
            "ticket_prize": ticket_prize,
            "ticket_m3": ticket_m3,
            "prize_win": prize_win,
            "m3_win": m3_win,
            "ticket_budget": budget,
            "duplicate_collapsed": cell.get(
                "same_bet_index_duplicate_rows_collapsed", 0),
        }
    return out


# ---------------------------------------------------------------------------
# Reproduction gate (fail-closed) against committed primary-window counts
# ---------------------------------------------------------------------------

def reproduce_committed_counts(cell_data, primary_counts, p275b):
    """Reproduce committed P273A primary-window observed_successes and P275B
    success_draws (prize-aware union per draw) for windows 50/300/750.

    Raises ReproductionError on any mismatch. Returns a reproduction report.
    """
    # The committed window is the most-recent N *distinct target draws*
    # (including ineligible ones for POWER); we reproduce by counting eligible
    # union wins within the committed [earliest_target_draw, latest_target_draw]
    # integer range. (DAILY_539 has no exclusions, so the bound equals the
    # most-recent N eligible draws.) Iteration is driven by the committed
    # artifact (the source of truth), checking every committed window present.
    p275b_success = {}
    for row in p275b["matrix_rows"]:
        p275b_success[(row["lottery_type"], row["strategy_id"],
                       row["window_draw_count"])] = row["success_draws"]

    checked = 0
    p275b_checked = 0
    mismatches = []
    for cell in primary_counts["cells"]:
        lt = cell["lottery_type"]
        sid = cell["strategy_id"]
        data = cell_data.get((lt, sid))
        if data is None:
            raise ReproductionError(f"no reconstructed cell for {lt}/{sid}")
        for w in cell["windows"]:
            window = w["window"]
            if w["earliest_target_draw"] is None:
                continue
            lo = int(w["earliest_target_draw"])
            hi = int(w["latest_target_draw"])
            in_range = [d for d in data["draws_desc"] if lo <= int(d) <= hi]
            recon_succ = sum(1 for d in in_range if data["prize_win"][d])
            recon_support = len(in_range)
            checked += 1
            if recon_succ != w["observed_successes"]:
                mismatches.append(
                    f"P273A {lt}/{sid}/w{window}: succ recon={recon_succ} "
                    f"exp={w['observed_successes']}")
            if recon_support != w["support_draws"]:
                mismatches.append(
                    f"P273A {lt}/{sid}/w{window}: support recon={recon_support} "
                    f"exp={w['support_draws']}")
            exp275 = p275b_success.get((lt, sid, window))
            if exp275 is not None:
                p275b_checked += 1
                if recon_succ != exp275:
                    mismatches.append(
                        f"P275B {lt}/{sid}/w{window}: recon={recon_succ} "
                        f"exp={exp275}")
    if mismatches:
        raise ReproductionError(
            "count reproduction failed: " + "; ".join(mismatches[:10]))
    return {
        "reproduction_status": "PASS",
        "p273a_primary_window_cells_checked": checked,
        "p275b_success_draws_cross_checked": p275b_checked,
        "fail_closed": True,
    }


# ---------------------------------------------------------------------------
# Portfolio construction (deterministic, outcome-blind)
# ---------------------------------------------------------------------------

def _select_n_tickets(lt, n, sources, cell_data, draw):
    """Round-robin select exactly N distinct tickets across source cells.

    Deterministic, outcome-blind: iterate ticket positions 0,1,2,...; at each
    position take that-position ticket from each source cell in priority order;
    dedupe by canonical fingerprint preserving first occurrence; stop at N.
    Genuinely INTERLEAVES strategies so a cross portfolio is not the first
    constituent alone. Returns (chosen, duplicates_seen) where chosen is a list
    of (fingerprint, prize_bool, m3_bool), or (None, duplicates_seen) if fewer
    than N distinct tickets exist (draw ineligible; never back-filled).
    """
    lists = []
    for sid in sources:
        data = cell_data.get((lt, sid))
        lists.append((sid, data["tickets"].get(draw, []) if data else []))
    seen = set()
    chosen = []
    dup = 0
    max_len = max((len(tl) for _s, tl in lists), default=0)
    for pos in range(max_len):
        for sid, tl in lists:
            if pos >= len(tl):
                continue
            fp, _main, _sz = tl[pos]
            if fp in seen:
                dup += 1
                continue
            seen.add(fp)
            data = cell_data[(lt, sid)]
            chosen.append((fp, data["ticket_prize"][draw][fp],
                           data["ticket_m3"][draw][fp]))
            if len(chosen) >= n:
                return chosen, dup
    if len(chosen) < n:
        return None, dup
    return chosen, dup


def build_portfolio_per_draw(portfolio, cell_data):
    """Select exactly N distinct tickets per draw (round-robin across sources).

    Draws with < N distinct tickets are INELIGIBLE (never back-filled). Portfolio
    win on a draw = union over the selected tickets' per-ticket wins (each scored
    once by the committed scorer in build_cell_per_draw). Returns eligible/
    ineligible draws, per-draw prize/M3 union win, duplicate-ticket rate,
    constituent native budgets, and the aligned draw universe (intersection of
    the source cells' supported draws).
    """
    lt = portfolio["lottery_type"]
    n = portfolio["ticket_budget"]
    sources = portfolio["source_cells"]

    native_budgets = {}
    draw_sets = []
    for sid in sources:
        data = cell_data.get((lt, sid))
        native_budgets[sid] = 0 if data is None else data["ticket_budget"]
        draw_sets.append(set() if data is None else set(data["draws_desc"]))
    aligned = set.intersection(*draw_sets) if draw_sets else set()
    aligned_desc = sorted(aligned, key=lambda d: int(d), reverse=True)

    eligible = []
    ineligible = []
    prize_win = {}
    m3_win = {}
    dup_total = 0
    selected_total = 0
    for draw in aligned_desc:
        chosen, dup_here = _select_n_tickets(lt, n, sources, cell_data, draw)
        if chosen is None:
            ineligible.append(draw)
            continue
        dup_total += dup_here
        selected_total += n
        eligible.append(draw)
        prize_win[draw] = any(p for (_f, p, _m) in chosen)
        m3_win[draw] = any(m for (_f, _p, m) in chosen)
    return {
        "eligible_draws": eligible,
        "ineligible_draws": ineligible,
        "prize_win": prize_win,
        "m3_win": m3_win,
        "duplicate_ticket_rate": (dup_total / (selected_total + dup_total)
                                  if (selected_total + dup_total) else 0.0),
        "constituent_native_budgets": native_budgets,
        "aligned_draw_universe": aligned_desc,
    }


# ---------------------------------------------------------------------------
# Random baselines: per-draw union-win probability Q (ordinary / diversified)
# ---------------------------------------------------------------------------

def _ticket_hits(ticket_set, outcome_main_set):
    return len(ticket_set & outcome_main_set)


def _prize_win_from_counts(lottery_type, hit_count, special_hit):
    if lottery_type == "DAILY_539":
        return hit_count >= 2
    if lottery_type == "BIG_LOTTO":
        return hit_count >= 3 or (hit_count == 2 and special_hit == 1)
    return hit_count >= 3 or (hit_count >= 1 and special_hit == 1)  # POWER


def _m3_from_counts(hit_count):
    return hit_count >= 3


def estimate_baseline_Q(lottery_type, n, outcomes_list, rng, kind,
                        n_samples):
    """Monte-Carlo estimate of per-draw union-win probability Q for an N-ticket
    random portfolio (kind in {"ordinary","diversified"}), for prize-aware and
    M3+ families.

    The per-draw union-win probability is invariant across draws by combinatorial
    symmetry of uniform outcomes (verified by the low cross-draw variance check
    in tests); we therefore sample N-ticket portfolios against cycled actual
    outcomes to obtain an unbiased Q estimate, then form the window null as
    Binomial(W, Q). Returns {"prize_Q":, "m3_Q":, "mean_pairwise_overlap":}.
    """
    main_max = MAIN_NUMBER_MAX[lottery_type]
    pick = MAIN_PICK_COUNT[lottery_type]
    universe = np.arange(1, main_max + 1)
    n_out = len(outcomes_list)
    prize_hits = 0
    m3_hits = 0
    overlap_sum = 0.0
    overlap_count = 0
    for s in range(n_samples):
        outcome = outcomes_list[s % n_out]
        omain = set(outcome["main"])
        ospecial = outcome["special"]
        tickets = _gen_random_tickets(lottery_type, n, rng, kind, universe,
                                      pick)
        # pairwise overlap (mean shared numbers across ticket pairs)
        if n >= 2:
            for i in range(n):
                for j in range(i + 1, n):
                    overlap_sum += len(tickets[i][0] & tickets[j][0])
                    overlap_count += 1
        prize = False
        m3 = False
        for tset, tsz in tickets:
            hc = _ticket_hits(tset, omain)
            if lottery_type == "POWER_LOTTO":
                sh = 1 if (ospecial is not None and tsz == ospecial) else 0
            elif lottery_type == "BIG_LOTTO":
                sh = 1 if (ospecial is not None and ospecial in tset) else 0
            else:
                sh = 0
            if _prize_win_from_counts(lottery_type, hc, sh):
                prize = True
            if _m3_from_counts(hc):
                m3 = True
        prize_hits += 1 if prize else 0
        m3_hits += 1 if m3 else 0
    return {
        "prize_Q": prize_hits / n_samples,
        "m3_Q": m3_hits / n_samples,
        "mean_pairwise_overlap": (overlap_sum / overlap_count
                                  if overlap_count else 0.0),
        "n_samples": n_samples,
    }


def _gen_random_tickets(lottery_type, n, rng, kind, universe, pick):
    """Generate N distinct legal tickets. Returns list of (set, second_zone)."""
    tickets = []
    if kind == "ordinary":
        seen = set()
        guard = 0
        while len(tickets) < n and guard < 10000:
            guard += 1
            chosen = frozenset(int(x) for x in
                               rng.choice(universe, size=pick, replace=False))
            if lottery_type == "POWER_LOTTO":
                sz = int(rng.integers(1, SECOND_ZONE_MAX + 1))
                key = (chosen, sz)
            else:
                key = (chosen, None)
            if key in seen:
                continue
            seen.add(key)
            tickets.append((set(chosen), key[1]))
    else:  # diversified: coverage-maximizing, minimal pairwise overlap
        perm = rng.permutation(universe)
        idx = 0
        for i in range(n):
            block = []
            for _ in range(pick):
                block.append(int(perm[idx % len(perm)]))
                idx += 1
            # If wrap caused a duplicate within a ticket, top up from universe.
            block_set = set(block)
            while len(block_set) < pick:
                cand = int(rng.choice(universe))
                block_set.add(cand)
            tickets.append((block_set, None))
        if lottery_type == "POWER_LOTTO":
            # independent seeded second-zone assignment, maximize coverage
            zperm = rng.permutation(np.arange(1, SECOND_ZONE_MAX + 1))
            tickets = [(t[0], int(zperm[i % len(zperm)]))
                       for i, t in enumerate(tickets)]
    return tickets


def window_null_distribution(Q, window_w, rng, replicates):
    """Null distribution of the window success COUNT for per-draw iid Bernoulli(Q).

    Per-draw union-win is iid Bernoulli(Q) (outcome-blind random tickets,
    symmetric outcomes), so the window success count ~ Binomial(W, Q). Returns
    the array of `replicates` simulated success counts.
    """
    if Q <= 0:
        return np.zeros(replicates, dtype=int)
    return rng.binomial(window_w, Q, size=replicates)


def mc_p_value(observed_success, null_counts):
    """One-sided upper MC p-value with add-one correction."""
    r = len(null_counts)
    ge = int(np.sum(null_counts >= observed_success))
    return (1 + ge) / (1 + r)


def _derived_rng(*parts):
    """Deterministic numpy Generator seeded from GLOBAL_SEED + parts."""
    h = hashlib.sha256(("|".join(str(p) for p in (GLOBAL_SEED,) + parts))
                       .encode("utf-8")).hexdigest()
    return np.random.default_rng(int(h[:16], 16))


def _union_rate_over(draws, win_map):
    if not draws:
        return None, 0, 0
    succ = sum(1 for d in draws if win_map.get(d))
    return succ / len(draws), succ, len(draws)


def _portfolio_win_for_sources(lt, n, sources, cell_data, draws):
    """Per-draw union win for a portfolio restricted to `sources` (first-k),
    using the same round-robin selector. Returns (prize_map, m3_map, eligible).
    """
    prize = {}
    m3 = {}
    eligible = set()
    for draw in draws:
        chosen, _dup = _select_n_tickets(lt, n, sources, cell_data, draw)
        if chosen is None:
            continue
        eligible.add(draw)
        prize[draw] = any(p for (_f, p, _m) in chosen)
        m3[draw] = any(m for (_f, _p, m) in chosen)
    return prize, m3, eligible


def compute_portfolio_metrics(portfolio, port_data, cell_data, baseline_Q):
    """All required metrics for one portfolio, both outcome families, all windows."""
    lt = portfolio["lottery_type"]
    n = portfolio["ticket_budget"]
    sources = portfolio["source_cells"]
    native = port_data["constituent_native_budgets"]
    equal_budget_constituents = [s for s in sources if native.get(s) == n]

    eligible_set = set(port_data["eligible_draws"])
    windows_out = []
    for window in PRIMARY_WINDOWS:
        window_draws = port_data["aligned_draw_universe"][:window]
        elig_in_win = [d for d in window_draws if d in eligible_set]
        support = len(elig_in_win)
        rec = {
            "window": window,
            "window_label": WINDOW_LABELS[window],
            "promotion_eligible_window": window != SHORT_NON_PROMOTING_WINDOW,
            "window_draw_count": len(window_draws),
            "support_draws": support,
            "ineligible_draws_in_window":
                len([d for d in window_draws if d not in eligible_set]),
            "duplicate_ticket_rate": port_data["duplicate_ticket_rate"],
        }
        for family, win_map_key in (("prize_aware", "prize_win"),
                                    ("m3_plus", "m3_win")):
            win_map = port_data[win_map_key]
            rate, succ, _ = _union_rate_over(elig_in_win, win_map)
            fam = {
                "union_success_draws": succ,
                "support_draws": support,
                "union_success_rate": rate,
                "wilson_ci_95": wilson_interval(succ, support),
                "clopper_pearson_ci_95": clopper_pearson_interval(succ, support),
            }
            # --- best equal-budget constituent comparator (paired) ---
            best = None
            for sid in equal_budget_constituents:
                cwin = (cell_data[(lt, sid)]["prize_win"] if family == "prize_aware"
                        else cell_data[(lt, sid)]["m3_win"])
                crate, csucc, _ = _union_rate_over(elig_in_win, cwin)
                if crate is None:
                    continue
                if best is None or crate > best["rate"]:
                    best = {"strategy_id": sid, "rate": crate,
                            "success": csucc, "win_map": cwin}
            if best is not None:
                b = sum(1 for d in elig_in_win
                        if win_map.get(d) and not best["win_map"].get(d))
                c = sum(1 for d in elig_in_win
                        if best["win_map"].get(d) and not win_map.get(d))
                ndis, pmc = mcnemar_exact(b, c)
                fam["best_equal_budget_constituent"] = {
                    "strategy_id": best["strategy_id"],
                    "union_success_rate": best["rate"],
                    "union_success_draws": best["success"],
                    "portfolio_minus_constituent_abs": (
                        rate - best["rate"] if rate is not None else None),
                    "unique_complementary_wins_portfolio_only": b,
                    "unique_complementary_wins_constituent_only": c,
                    "mcnemar_discordant": ndis,
                    "mcnemar_p_value_exact": pmc,
                }
            else:
                fam["best_equal_budget_constituent"] = None
            # --- random baselines (ordinary, diversified) ---
            qkey = (lt, n)
            fam["random_baselines"] = {}
            for kind in ("ordinary", "diversified"):
                Q = baseline_Q[qkey][kind][
                    "prize_Q" if family == "prize_aware" else "m3_Q"]
                rng = _derived_rng("null", lt, n, kind, family, window)
                null_counts = window_null_distribution(Q, support, rng,
                                                        MC_REPLICATES)
                pval = mc_p_value(succ, null_counts) if support else None
                fam["random_baselines"][kind] = {
                    "baseline_union_win_probability": Q,
                    "expected_success_draws": (Q * support if support else 0),
                    "absolute_excess": (rate - Q if rate is not None else None),
                    "relative_excess": (rate / Q if (rate is not None and Q > 0)
                                        else None),
                    "mc_p_value_one_sided_upper": pval,
                    "mc_replicates": MC_REPLICATES,
                    "mean_pairwise_overlap":
                        baseline_Q[qkey][kind]["mean_pairwise_overlap"],
                }
            # --- pairwise Jaccard of winning-draw sets (cross portfolios) ---
            if portfolio["kind"] == "CROSS" and family == "prize_aware":
                winsets = {}
                for sid in sources:
                    cwin = cell_data[(lt, sid)]["prize_win"]
                    winsets[sid] = set(d for d in elig_in_win if cwin.get(d))
                jac = []
                ids = sources
                for i in range(len(ids)):
                    for j in range(i + 1, len(ids)):
                        jac.append({
                            "pair": [ids[i], ids[j]],
                            "jaccard_winning_draws":
                                jaccard(winsets[ids[i]], winsets[ids[j]]),
                        })
                fam["pairwise_winning_draw_jaccard"] = jac
            # --- marginal coverage gain per added strategy (cross) ---
            if portfolio["kind"] == "CROSS":
                gains = []
                prev_rate = 0.0
                for k in range(1, len(sources) + 1):
                    sub = sources[:k]
                    pw, mw, esub = _portfolio_win_for_sources(
                        lt, n, sub, cell_data, elig_in_win)
                    sub_map = pw if family == "prize_aware" else mw
                    sub_draws = [d for d in elig_in_win if d in esub]
                    srate, _, _ = _union_rate_over(sub_draws, sub_map)
                    gains.append({
                        "k_sources": k,
                        "sources_prefix": list(sub),
                        "eligible_draws": len(sub_draws),
                        "union_success_rate": srate,
                        "marginal_gain_vs_prev": (
                            (srate - prev_rate) if srate is not None else None),
                    })
                    if srate is not None:
                        prev_rate = srate
                fam["marginal_coverage_gain"] = gains
            rec[family] = fam
        windows_out.append(rec)
    return {
        "portfolio_id": portfolio["portfolio_id"],
        "lottery_type": lt,
        "ticket_budget": n,
        "tier": portfolio["tier"],
        "kind": portfolio["kind"],
        "source_cells": list(sources),
        "equal_budget_constituents": equal_budget_constituents,
        "constituent_native_budgets": native,
        "n_eligible_draws_total": len(port_data["eligible_draws"]),
        "n_ineligible_draws_total": len(port_data["ineligible_draws"]),
        "windows": windows_out,
    }


DESCRIPTIVE_ALPHA = 0.05  # retrospective descriptive threshold (exploratory)


def derive_verdict(portfolio_metrics):
    """Pick exactly one scientific verdict from PRIMARY CROSS portfolios.

    Significance-based for historical description (alpha = 0.05). Future-only
    confirmation uses the separate frozen future contract. For each PRIMARY
    CROSS portfolio at an inferential window
    (300/750), the prize-aware family is judged:
      * complementary_over_constituent: union rate strictly above the best
        equal-budget constituent AND McNemar favours the portfolio (b > c) with
        exact p < alpha;
      * beats_diversified: diversified-random absolute excess > 0 with MC
        p < alpha.

    RETROSPECTIVE_COMPLEMENTARITY_PRESENT_FUTURE_CONFIRMATION_PENDING:
        some cross portfolio is complementary_over_constituent AND beats
        diversified random.
    RETROSPECTIVE_COVERAGE_ONLY_NO_SKILL_EVIDENCE:
        some cross portfolio is complementary_over_constituent but none also
        beats diversified random (apparent gain is coverage, not skill).
    NO_RETROSPECTIVE_COMPLEMENTARITY_EVIDENCE:
        no cross portfolio is complementary_over_constituent.
    INSUFFICIENT_REPRODUCIBLE_EVIDENCE:
        no evaluable primary cross portfolio.
    """
    primary_cross = [m for m in portfolio_metrics
                     if m["tier"] == "PRIMARY" and m["kind"] == "CROSS"]
    evaluable = False
    any_complementary = False
    complementary_and_beats_div = False
    for m in primary_cross:
        for w in m["windows"]:
            if w["window"] == SHORT_NON_PROMOTING_WINDOW:
                continue
            fam = w["prize_aware"]
            rate = fam["union_success_rate"]
            bec = fam["best_equal_budget_constituent"]
            if rate is None or bec is None:
                continue
            evaluable = True
            div = fam["random_baselines"]["diversified"]
            complementary = (
                rate > bec["union_success_rate"]
                and bec["unique_complementary_wins_portfolio_only"] >
                bec["unique_complementary_wins_constituent_only"]
                and bec["mcnemar_p_value_exact"] is not None
                and bec["mcnemar_p_value_exact"] < DESCRIPTIVE_ALPHA
            )
            beats_div = (
                div["absolute_excess"] is not None
                and div["absolute_excess"] > 0
                and div["mc_p_value_one_sided_upper"] is not None
                and div["mc_p_value_one_sided_upper"] < DESCRIPTIVE_ALPHA
            )
            if complementary:
                any_complementary = True
                if beats_div:
                    complementary_and_beats_div = True
    if not evaluable:
        return "INSUFFICIENT_REPRODUCIBLE_EVIDENCE"
    if complementary_and_beats_div:
        return "RETROSPECTIVE_COMPLEMENTARITY_PRESENT_FUTURE_CONFIRMATION_PENDING"
    if any_complementary:
        return "RETROSPECTIVE_COVERAGE_ONLY_NO_SKILL_EVIDENCE"
    return "NO_RETROSPECTIVE_COMPLEMENTARITY_EVIDENCE"


def run_study(db_path=CANONICAL_DB_PATH, mc_replicates=MC_REPLICATES,
              mc_q_samples=MC_Q_SAMPLES, **input_paths):
    """Full read-only study. Returns one canonical result dict (no file write)."""
    global MC_REPLICATES, MC_Q_SAMPLES
    MC_REPLICATES = mc_replicates
    MC_Q_SAMPLES = mc_q_samples

    inputs = load_and_verify_inputs(**input_paths)
    historical_contract = build_bounded_retrospective_analysis_contract()

    # Determine the (lottery, draw) outcomes needed from the committed identities.
    needed = defaultdict(set)
    for cell in inputs["identity"]["cells"]:
        lt = cell["lottery_type"]
        for sd in cell.get("supported_draws", []):
            needed[lt].add(sd["target_draw"])

    db_meta_pre = db_file_metadata(db_path)
    conn, ro_evidence = open_readonly_connection(db_path)
    try:
        conn.execute("BEGIN")
        outcomes, db_tables_meta = load_outcomes(conn, needed)
        conn.execute("ROLLBACK")
    finally:
        conn.close()
    db_meta_post = db_file_metadata(db_path)
    if db_meta_pre["sha256"] != db_meta_post["sha256"]:
        raise DBReadOnlyError("DB SHA-256 changed during execution")

    cell_data = build_cell_per_draw(inputs["identity"], outcomes)
    reproduction = reproduce_committed_counts(
        cell_data, inputs["primary_counts"], inputs["p275b"])

    # Build per-lottery outcome lists for baseline Q estimation in a
    # DETERMINISTIC draw order (sets iterate non-deterministically under hash
    # randomization; sorting by draw int makes the MC fully reproducible).
    outcomes_by_lt = defaultdict(list)
    for lt in LOTTERY_TYPES:
        for draw in sorted(needed[lt], key=lambda d: int(d)):
            outcomes_by_lt[lt].append(outcomes[(lt, draw)])

    # Portfolios + baseline Q per (lottery, N).
    portfolio_metrics = []
    baseline_Q = {}
    cutoffs = {}
    for portfolio in BOUNDED_RETROSPECTIVE_PORTFOLIO_FAMILY:
        lt = portfolio["lottery_type"]
        n = portfolio["ticket_budget"]
        if (lt, n) not in baseline_Q:
            baseline_Q[(lt, n)] = {}
            for kind in ("ordinary", "diversified"):
                rng = _derived_rng("Q", lt, n, kind)
                baseline_Q[(lt, n)][kind] = estimate_baseline_Q(
                    lt, n, outcomes_by_lt[lt], rng, kind, mc_q_samples)
        port_data = build_portfolio_per_draw(portfolio, cell_data)
        portfolio_metrics.append(
            compute_portfolio_metrics(portfolio, port_data, cell_data,
                                      baseline_Q))

    # Frozen future cutoff = latest committed-ticket target draw per lottery.
    for lt in LOTTERY_TYPES:
        draws = sorted(needed[lt], key=lambda d: int(d)) if needed[lt] else []
        cutoffs[lt] = draws[-1] if draws else None
    future_contract = build_frozen_future_contract(cutoffs)

    verdict = derive_verdict(portfolio_metrics)

    # Synthetic-style invariant: diversified overlap <= ordinary overlap.
    overlap_ok = True
    overlap_report = {}
    for (lt, n), kinds in baseline_Q.items():
        o = kinds["ordinary"]["mean_pairwise_overlap"]
        d = kinds["diversified"]["mean_pairwise_overlap"]
        overlap_report[f"{lt}_N{n}"] = {"ordinary": o, "diversified": d,
                                        "diversified_le_ordinary": d <= o + 1e-9}
        overlap_ok = overlap_ok and (d <= o + 1e-9)

    serializable_baseline_Q = {
        f"{lt}|N{n}": {k: kinds[k] for k in kinds}
        for (lt, n), kinds in baseline_Q.items()
    }

    result = {
        "task_id": TASK_ID,
        "artifact_version": ARTIFACT_VERSION,
        "scoring_version": SCORING_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "source_verification_status": SOURCE_VERIFICATION_STATUS,
        "generated_at": _now_iso(),
        "schema_version": ARTIFACT_VERSION,
        "scope": {
            "primary_lottery": PRIMARY_LOTTERY,
            "lotteries": list(LOTTERY_TYPES),
            "primary_windows": {WINDOW_LABELS[w]: w for w in PRIMARY_WINDOWS},
            "primary_fixed_ticket_budgets": [3, 5],
            "all_fixed_ticket_budgets": sorted({
                p["ticket_budget"] for p in BOUNDED_RETROSPECTIVE_PORTFOLIO_FAMILY
            }),
            "max_primary_portfolios": 6,
            "performs_unbounded_combination_search": False,
        },
        "safety_flags": {
            "prediction_success_claim": False,
            "strategy_promoted": False,
            "production_db_opened_read_only": True,
            "production_db_write_performed": False,
            "registry_mutated": False,
            "controlled_apply_performed": False,
            "activation_or_deployment_performed": False,
            "outcome_aware_ticket_backfill": False,
            "second_zone_manufactured": False,
            "prize_aware_and_m3plus_correction_families_separate": True,
        },
        "historical_analysis_contract": historical_contract,
        "input_provenance": {
            "source_main_commit_expected":
                "b9c70cc413969dd0c0b22b2c5b606ddb31980a6b",
            "committed_input_hashes": inputs["source_hashes"],
            "fingerprints_reverified": inputs["fingerprints_reverified"],
            "p275b_canonical_digest_verified": P275B_CANONICAL_DIGEST,
            "reused_helpers": [
                "lottery_api.prize_aware_scorer.score_prize_aware_ticket",
                "lottery_api.prize_aware_replay_adapter._check_eligibility",
            ],
        },
        "db_snapshot": {
            "path_identifier": db_meta_pre["path_identifier"],
            "sha256_pre": db_meta_pre["sha256"],
            "sha256_post": db_meta_post["sha256"],
            "sha256_unchanged": db_meta_pre["sha256"] == db_meta_post["sha256"],
            "size_bytes": db_meta_pre["size_bytes"],
            "modification_time_utc": db_meta_pre["modification_time_utc"],
            "read_only_evidence": ro_evidence,
            "draws_row_counts": db_tables_meta["draws_row_counts"],
            "latest_draw_in_db": db_tables_meta["latest_draw"],
            "db_open_mode": DB_OPEN_MODE,
        },
        "reconstruction": {
            "count_reproduction": reproduction,
            "per_draw_outcome_source": "draws table (read-only)",
            "ticket_source": "committed P273A distinct-ticket identities (frozen)",
            "outcomes_loaded": len(outcomes),
        },
        "baseline_specification": {
            "ordinary_random": ORDINARY_RANDOM_BASELINE["description"],
            "diversified_random": DIVERSIFIED_RANDOM_BASELINE["description"],
            "per_draw_union_win_probability_Q":
                "MC-estimated; per-draw union win is iid Bernoulli(Q) by "
                "outcome symmetry, so window null = Binomial(support, Q).",
            "mc_q_samples": mc_q_samples,
            "mc_replicates": mc_replicates,
            "diversified_overlap_not_worse_than_ordinary": overlap_ok,
            "overlap_report": overlap_report,
            "baseline_Q": serializable_baseline_Q,
        },
        "frozen_future_contract": future_contract,
        "multiple_testing_policy": {
            "historical_bonferroni_role": HISTORICAL_BONFERRONI_ROLE,
            "historical_descriptive_multiplicity_family_size":
                CONFIRMATORY_FAMILY_SIZE,
            "future_bonferroni_policy": "BONFERRONI",
            "future_confirmatory_family_size": CONFIRMATORY_FAMILY_SIZE,
            "descriptive_secondary_correction": "BH_FDR",
            "historical_family_changed_after_initial_outcome_run": True,
            "unbounded_combination_search_performed": False,
            "prize_aware_and_m3plus_separate_families": True,
            "short_50_excluded_from_future_confirmatory_family": True,
        },
        "promotion_boundary": {
            "max_classification": "GO_CANDIDATE_RESEARCH_ONLY",
            "strategy_promotion": False,
            "registry_mutation": False,
            "activation": False,
            "production_recommendation": False,
            "manual_verification_required_retained": True,
        },
        "portfolio_results": portfolio_metrics,
        "scientific_verdict": verdict,
        "limitations": [
            "Retrospective post-hoc bounded evidence only; not confirmatory and "
            "not a future-only result; no claim of improved future prediction "
            "success.",
            "Prize-tier semantics carry source_verification_status="
            "MANUAL_VERIFICATION_REQUIRED (P271B/P271C).",
            "50-draw (SHORT) windows are integrity guardrails and cannot support "
            "promotion.",
            "Tickets are the frozen committed P273A identities; portfolios reuse "
            "existing strategy tickets without any refitting.",
            "POWER second-zone-missing rows are excluded as missing eligibility, "
            "never imputed or counted as losses.",
            "Per-draw union-win probability Q is treated as constant across draws "
            "by combinatorial symmetry of the outcome; the window null is "
            "Binomial(support, Q).",
            "No monetary budget, EV, ROI, or betting recommendation is computed.",
            "BIG_LOTTO / POWER_LOTTO portfolios are secondary generalization "
            "checks (descriptive only, no promotion verdict).",
        ],
        "prediction_success_claim": False,
        "final_classification": "P276B_FIXED_N_COVERAGE_COMPLEMENTARITY_COMPLETE",
    }
    result["canonical_payload_digest"] = canonical_digest(result,
                                                          SELF_DIGEST_EXCLUDE)
    return result


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def render_markdown(result: dict) -> str:
    a = []
    a.append("# P276B — Fixed-N Cross-Strategy Coverage & Complementarity Study")
    a.append("")
    a.append("> **Read-only, bounded retrospective, post-hoc, "
             "non-confirmatory.** Reuses committed P273A ticket identities + "
             "read-only settled draw outcomes. `prediction_success_claim=false`; "
             "no strategy promotion, no registry mutation, no DB content write, "
             "no activation. True future confirmation begins only with "
             "prospectively generated committed tickets for draws strictly later "
             "than the corrected future-contract freeze and cutoff.")
    a.append("")
    a.append("## Run metadata")
    a.append(f"- task_id: `{result['task_id']}`")
    a.append(f"- artifact_version: `{result['artifact_version']}`")
    a.append(f"- scoring_version: `{result['scoring_version']}`")
    a.append(f"- generated_at: `{result['generated_at']}`")
    a.append(f"- **scientific_verdict: `{result['scientific_verdict']}`**")
    a.append(f"- canonical_payload_digest: "
             f"`{result['canonical_payload_digest']}`")
    a.append("")
    a.append("## Bounded retrospective exploratory analysis")
    hc = result["historical_analysis_contract"]
    a.append(f"- status_label: `{hc['status_label']}`")
    a.append("- chronology: first-N historical outcome scoring occurred before "
             "the final round-robin selector was selected; final round-robin "
             "historical results are post-hoc.")
    a.append(f"- bounded_family: {hc['bounded_family']}; "
             f"unbounded_combination_search_performed: "
             f"{result['multiple_testing_policy']['unbounded_combination_search_performed']}")
    a.append(f"- historical_preregistration_claim: "
             f"{hc['historical_preregistration_claim']}")
    a.append(f"- historical_bonferroni_role: "
             f"`{hc['historical_bonferroni_role']}`")
    a.append(f"- descriptive_multiplicity_family_size: "
             f"{hc['descriptive_multiplicity_family_size']} "
             f"(descriptive Bonferroni alpha "
             f"{hc['descriptive_bonferroni_per_test_alpha']:.5f})")
    a.append(f"- bounded_retrospective_analysis_sha256: "
             f"`{hc['bounded_retrospective_analysis_sha256']}`")
    a.append(f"- superseded_identity_only_family_sha256: "
             f"`{hc['superseded_identity_only_family_sha256']}`")
    a.append(f"- fixed_ticket_budgets: {hc['fixed_ticket_budgets']}")
    a.append("")
    a.append("## DB snapshot (read-only)")
    db = result["db_snapshot"]
    a.append(f"- path_identifier: `{db['path_identifier']}`")
    a.append(f"- sha256 (pre==post): `{db['sha256_pre']}` "
             f"(unchanged: {db['sha256_unchanged']})")
    a.append(f"- size_bytes: {db['size_bytes']}; query_only_enabled: "
             f"{db['read_only_evidence']['query_only_enabled']}; "
             f"write_denying_authorizer: "
             f"{db['read_only_evidence']['write_denying_authorizer_installed']}")
    a.append(f"- latest_draw_in_db: {db['latest_draw_in_db']}")
    a.append("")
    a.append("## Count reproduction (fail-closed gate)")
    rep = result["reconstruction"]["count_reproduction"]
    a.append(f"- reproduction_status: **{rep['reproduction_status']}** "
             f"({rep['p273a_primary_window_cells_checked']} primary-window "
             f"cells checked)")
    a.append("")
    a.append("## Prospectively frozen future contract")
    ff = result["frozen_future_contract"]
    a.append(f"- cutoff_target_draw_by_lottery: "
             f"`{ff['cutoff_target_draw_by_lottery']}`")
    a.append(f"- future_contract_sha256: "
             f"`{ff['future_contract_sha256']}`")
    a.append(f"- future_confirmatory_family_size: "
             f"{ff['future_confirmatory_family_size']} "
             f"(Bonferroni per-test alpha "
             f"{ff['bonferroni_per_test_alpha']:.5f})")
    a.append("- future evidence requires prospectively generated committed "
             "tickets; historical results are not future confirmation; any "
             "family, selector, baseline, seed, hypothesis, or correction change "
             "resets the future clock.")
    a.append(f"- future_confirmation_status: "
             f"**{ff['future_confirmation_status']}**")
    a.append("")
    a.append("## Portfolio results (prize-aware union, primary lottery)")
    a.append("")
    a.append("| portfolio | tier/kind | N | window | support | union_rate | "
             "best_constituent | Δ vs constituent | McNemar p | ord_excess | "
             "div_excess | div_p |")
    a.append("|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|")
    for m in result["portfolio_results"]:
        for w in m["windows"]:
            fam = w["prize_aware"]
            bec = fam["best_equal_budget_constituent"]
            ordn = fam["random_baselines"]["ordinary"]
            div = fam["random_baselines"]["diversified"]

            def _f(x, p=4):
                return "—" if x is None else (f"{x:.{p}f}"
                                              if isinstance(x, float) else str(x))
            a.append(
                f"| {m['portfolio_id']} | {m['tier']}/{m['kind']} | "
                f"{m['ticket_budget']} | {w['window_label']} | "
                f"{w['support_draws']} | {_f(fam['union_success_rate'])} | "
                f"{(bec['strategy_id'] if bec else '—')} | "
                f"{_f(bec['portfolio_minus_constituent_abs']) if bec else '—'} | "
                f"{_f(bec['mcnemar_p_value_exact']) if bec else '—'} | "
                f"{_f(ordn['absolute_excess'])} | {_f(div['absolute_excess'])} | "
                f"{_f(div['mc_p_value_one_sided_upper'])} |")
    a.append("")
    a.append("## Limitations")
    a.append("- The negative verdict applies only to this final evaluated "
             "round-robin family; it does not prove all possible combinations "
             "fail and does not prove future failure or success.")
    for lim in result["limitations"]:
        a.append(f"- {lim}")
    return "\n".join(a)


def write_artifacts(result: dict, out_json: str, out_md: str) -> None:
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    with open(out_md, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(result))
        fh.write("\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="P276B fixed-N coverage/complementarity study (read-only)")
    parser.add_argument("--db", default=CANONICAL_DB_PATH)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--mc-replicates", type=int, default=MC_REPLICATES)
    parser.add_argument("--mc-q-samples", type=int, default=MC_Q_SAMPLES)
    args = parser.parse_args(argv)
    result = run_study(db_path=args.db, mc_replicates=args.mc_replicates,
                       mc_q_samples=args.mc_q_samples)
    write_artifacts(result, args.out_json, args.out_md)
    print(json.dumps({
        "task_id": TASK_ID,
        "scientific_verdict": result["scientific_verdict"],
        "reproduction": result["reconstruction"]["count_reproduction"][
            "reproduction_status"],
        "canonical_payload_digest": result["canonical_payload_digest"],
        "out_json": args.out_json,
        "out_md": args.out_md,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
