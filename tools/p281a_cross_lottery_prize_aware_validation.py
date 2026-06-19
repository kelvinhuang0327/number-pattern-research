"""
P281A — Cross-Lottery Prize-Aware Success Definition and Inferential Validation
(read-only research / replay validation only).

Goal
----
Define, verify, and statistically validate the prize-aware "success" definition
for each lottery type, then add the inferential layer (random baseline, p-value,
correction) that the prior P273A 100/500/1500 *observed-counts* artifact left
out. (P273A computed full inference only for its owner-approved PRIMARY windows
50/300/750; its 100/500/1500 export is observed-count-only / reference-only.
P281A fills that gap on 100/500/1500 and reframes it as a cross-lottery
success-definition study, without re-deriving the methodology.)

This is LOCAL research and replay validation ONLY. It does NOT:
  - create any real publication, pre-draw manifest, or publication PR;
  - look up any official target draw or official deadline;
  - promote, activate, or rank-for-deployment any strategy;
  - mutate registry / production / deployment / controlled_apply;
  - write or copy the database, or change any scorer / adapter / strategy source.

Reuse contract (no rewrite, no fork)
-------------------------------------
This tool IMPORTS and REUSES committed, already-reviewed modules verbatim:
  - lottery_api.prize_aware_scorer            (P271C pure scorer)
  - lottery_api.prize_aware_replay_adapter    (P271E read-only eligibility/mapping)
  - analysis.p273a_prizeaware_replay_export   (read-only DB read + window aggregate)
  - analysis.p273a_prize_aware_inferential_validation
        (exact distinct-ticket baselines, exact binomial / Poisson-binomial
         p-values, Wilson + Clopper-Pearson CIs, Bonferroni, BH-FDR,
         evaluate_window / stability / decision logic)
The ONLY new behaviour is: (a) the 100/500/1500 (+ all_available) window grid,
(b) per-row prize-tier capture for cross-lottery contribution decomposition,
(c) a support-status audit, (d) a deterministic Monte-Carlo cross-check of the
analytic baseline, and (e) the cross-lottery summary. No scorer / adapter /
endpoint definition is redefined here — only verified and reused.

Governance invariants
----------------------
  - Import-safe: no DB open, no file write, no network/subprocess at import.
  - Canonical DB opened strictly read-only (URI mode=ro + PRAGMA query_only=ON),
    one connection, one read transaction (one consistent snapshot).
  - Permitted tables only: strategy_prediction_replays, draws.
  - POWER_LOTTO rows with a missing stored second-zone prediction are excluded
    and NEVER filled, defaulted, inferred, or replaced by the actual value.
  - No prize-money / EV / ROI / betting-advice / prediction-success claim.

artifact_version = "p281a_cross_lottery_prize_aware_validation_v1"
scoring_version  = delegated to lottery_api.prize_aware_scorer.SCORING_VERSION
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from collections import Counter

# --------------------------------------------------------------------------- #
# Import-safe path bootstrap (resolves whether run as a script or via pytest    #
# with pythonpath=.). Manipulates sys.path only; opens no DB and writes no file.#
# --------------------------------------------------------------------------- #
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Reuse the committed read-only exporter helpers + constants (no fork).
from analysis.p273a_prizeaware_replay_export import (  # noqa: E402
    ADAPTER_VERSION,
    CANONICAL_DB_PATH,
    CELL_QUERY,
    DB_OPEN_MODE,
    EXPECTED_FROZEN_CELL_COUNT,
    GOVERNED_ENDPOINT,
    LOTTERY_TYPES,
    P267C_JSON_PATH,
    P271A_JSON_PATH,
    P271C_SOURCE_PATH,
    P271E_SOURCE_PATH,
    REQUIRED_COLUMNS,
    SCORING_VERSION,
    SOURCE_VERIFICATION_STATUS,
    _now_iso,
    _row_dict,
    aggregate_window,
    compute_payload_digest,
    load_frozen_cells,
    open_readonly_connection,
    sha256_file,
    verify_endpoints_against_p271a,
    verify_schema,
)
from lottery_api.prize_aware_replay_adapter import (  # noqa: E402
    ALL_EXCLUSION_REASONS,
    EXCLUSION_AMBIGUOUS_DRAW_JOIN,
    EXCLUSION_INVALID_ACTUAL_AUXILIARY,
    EXCLUSION_MISSING_DRAW_JOIN,
    EXCLUSION_MISSING_PREDICTED_SECOND_ZONE,
    _check_eligibility,
    map_replay_row_to_scorer_input,
)
from lottery_api.prize_aware_scorer import (  # noqa: E402
    classify_tier,
    is_any_prize_aware_win,
    score_prize_aware_ticket,
    score_replay_row,
)
# Reuse the frozen statistical engine verbatim.
from analysis.p273a_prize_aware_inferential_validation import (  # noqa: E402
    BH_FDR_Q,
    FAMILY_ALPHA,
    MIN_EXPECTED_SUCCESSES,
    MIN_SUPPORT_DRAWS,
    analytic_ticket_baseline,
    benjamini_hochberg,
    bonferroni_pvalue,
    evaluate_stability,
    evaluate_window,
    exact_distinct_draw_baseline,
    finalize_window_decision,
    main_hit_distribution,
    overall_group_decision,
    ticket_universe,
)

# --------------------------------------------------------------------------- #
# Frozen P281A constants                                                       #
# --------------------------------------------------------------------------- #

TASK_ID = "P281A_CROSS_LOTTERY_PRIZE_AWARE_SUCCESS_DEFINITION_AND_INFERENTIAL_VALIDATION"
ARTIFACT_VERSION = "p281a_cross_lottery_prize_aware_validation_v1"
GENERATED_DATE = "2026-06-19"  # fixed (not a live clock) -> deterministic content
BRANCH = "task/p281a-cross-lottery-prize-aware-validation"
ORIGIN_MAIN = "3fdc07fd2e27e64460c134acc433b5cfe0dd2da3"

# Inferential windows for this task. SHORT/MID/LONG are P281A horizon labels for
# 100/500/1500 (NOT the owner-approved 50/300/750 PRIMARY decision windows).
P281A_WINDOWS = (100, 500, 1500)
WINDOW_LABELS = {100: "SHORT", 500: "MID", 1500: "LONG"}
WINDOW_ORDER = ("SHORT", "MID", "LONG")
ALL_AVAILABLE_LABEL = "ALL_AVAILABLE"  # supplementary/descriptive; NOT in family

# Bonferroni correction family = lottery x strategy x endpoint x window.
# One governed prize-aware endpoint per lottery; 36 cells x 3 windows = 108.
# This matches analysis.p273a...CORRECTION_FAMILY_M (bonferroni_pvalue default),
# so we reuse that default. all_available is supplementary and NOT counted.
CORRECTION_FAMILY_M = EXPECTED_FROZEN_CELL_COUNT * len(P281A_WINDOWS)  # 108

# The prior P273A 100/500/1500 observed-counts artifact this task reconciles with
# and now adds inference on top of (immutable; not modified, not depended on).
PRIOR_REFERENCE_OBSERVED_COUNTS = (
    "outputs/research/p273a_prizeaware_observed_counts_20260614.json"
)
PRIOR_PRIMARY_INFERENCE = (
    "outputs/research/p273a_prize_aware_inferential_validation_20260615.json"
)

DEFAULT_OUT_JSON = (
    "outputs/research/p281a_cross_lottery_prize_aware_validation_20260619.json"
)
DEFAULT_OUT_MD = (
    "outputs/research/p281a_cross_lottery_prize_aware_validation_20260619.md"
)

# Deterministic Monte-Carlo cross-check config (analytic baseline is primary;
# MC is only a confirmation that the exact baseline is reproduced empirically).
MONTE_CARLO_SEED = 42
MONTE_CARLO_TRIALS = 40000
MONTE_CARLO_CELLS = (
    ("DAILY_539", 5),
    ("BIG_LOTTO", 3),
    ("POWER_LOTTO", 2),
)

# Support-status vocabulary (Task B).
SUPPORT_ENOUGH = "ENOUGH_SUPPORT"
SUPPORT_LOW = "LOW_SUPPORT"
SUPPORT_NO_SPECIAL = "NO_SPECIAL_SUPPORT"
SUPPORT_NO_SECOND_ZONE = "NO_SECOND_ZONE_SUPPORT"
SUPPORT_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
SUPPORT_BLOCKED_JOIN = "BLOCKED_JOIN"

# Per-group inferential verdict vocabulary (Task D).
VERDICT_NULL = "NULL"
VERDICT_OBSERVATION_CANDIDATE = "OBSERVATION_CANDIDATE"
VERDICT_BLOCKED_SUPPORT = "BLOCKED_SUPPORT"
VERDICT_BLOCKED_SCHEMA = "BLOCKED_SCHEMA"


class P281AValidationError(RuntimeError):
    """Raised when an invariant is violated -> STOP, no artifact write."""


def _r(x, nd: int = 12):
    return round(x, nd) if isinstance(x, float) else x


# --------------------------------------------------------------------------- #
# Task A — prize-aware rule verification + truth tables + tier exhaustiveness  #
# --------------------------------------------------------------------------- #

# Canonical truth-table fixtures exercising the discriminating rule edges.
# Each fixture: (hit_count, special_hit, expected_any_prize_win, note).
TRUTH_TABLE_FIXTURES = {
    "DAILY_539": [
        (5, 0, True, "M5 first prize"),
        (3, 0, True, "M3 wins"),
        (2, 0, True, "M2 lowest prize wins"),
        (1, 0, False, "M1 loses"),
        (0, 0, False, "M0 loses"),
    ],
    "BIG_LOTTO": [
        (6, 0, True, "M6 first prize (special irrelevant)"),
        (3, 0, True, "M3 wins"),
        (2, 1, True, "M2+special wins (consolation)"),
        (2, 0, False, "M2 without special loses"),
        (1, 1, False, "M1+special loses"),
    ],
    "POWER_LOTTO": [
        (6, 1, True, "M6+second first prize"),
        (3, 0, True, "M3 wins"),
        (2, 1, True, "M2+second wins"),
        (1, 1, True, "M1+second wins (consolation)"),
        (1, 0, False, "M1 without second loses"),
        (2, 0, False, "M2 without second loses"),
        (0, 1, False, "0+second loses (needs >=1 first-zone hit)"),
    ],
}

# Expected number of distinct prize (non-NO_PRIZE) tiers per lottery.
EXPECTED_PRIZE_TIER_COUNT = {"DAILY_539": 4, "BIG_LOTTO": 8, "POWER_LOTTO": 10}
# Maximum main-hit count per lottery (for enumerating the tier truth table).
_MAIN_PICK = {"DAILY_539": 5, "BIG_LOTTO": 6, "POWER_LOTTO": 6}


def verify_prize_rules_and_truth_tables() -> dict:
    """Verify the actual P271C scorer matches the expected per-lottery rule and
    build the discriminating truth-table examples. Verifies via the real scorer
    (no rule is redefined here)."""
    out = {}
    for lt in LOTTERY_TYPES:
        fixtures = []
        for hit, special, expected_win, note in TRUTH_TABLE_FIXTURES[lt]:
            row = score_replay_row(lt, hit, special)
            actual_win = bool(row["any_prize_aware_win"])
            if actual_win != expected_win:
                raise P281AValidationError(
                    f"{lt} truth-table mismatch hit={hit} special={special}: "
                    f"scorer={actual_win} expected={expected_win}"
                )
            fixtures.append({
                "main_hit_count": hit,
                "special_hit": special,
                "tier_class": row["tier_class"],
                "any_prize_aware_win": actual_win,
                "is_m3_plus": bool(row["is_m3_plus"]),
                "note": note,
            })
        out[lt] = {
            "endpoint_id": GOVERNED_ENDPOINT[lt]["endpoint_id"],
            "rule_shorthand": GOVERNED_ENDPOINT[lt]["task_shorthand"],
            "rule_condition": GOVERNED_ENDPOINT[lt]["expected_condition_sql"],
            "min_qualifying_tier": GOVERNED_ENDPOINT[lt]["min_qualifying_tier"],
            "truth_table": fixtures,
        }
    return out


def verify_tier_exclusivity_exhaustiveness() -> dict:
    """Enumerate every (hit_count, special_hit) combination per lottery and
    confirm each maps to exactly one tier (mutual exclusivity), that the full
    integer grid is covered (exhaustiveness), and that the distinct prize-tier
    count matches the official structure."""
    out = {}
    for lt in LOTTERY_TYPES:
        max_hit = _MAIN_PICK[lt]
        specials = (0,) if lt == "DAILY_539" else (0, 1)
        grid = []
        prize_tiers = set()
        no_prize_combos = []
        for hit in range(0, max_hit + 1):
            for special in specials:
                tier = classify_tier(lt, hit, special)  # one string => exclusive
                win = is_any_prize_aware_win(lt, hit, special)
                if not isinstance(tier, str) or not tier:
                    raise P281AValidationError(
                        f"{lt} hit={hit} special={special}: invalid tier {tier!r}")
                if win == tier.endswith("_NO_PRIZE"):
                    raise P281AValidationError(
                        f"{lt} hit={hit} special={special}: win/tier inconsistent")
                if win:
                    prize_tiers.add(tier)
                else:
                    no_prize_combos.append({"main_hit_count": hit,
                                            "special_hit": special})
                grid.append({"main_hit_count": hit, "special_hit": special,
                             "tier_class": tier, "any_prize_aware_win": win})
        if len(prize_tiers) != EXPECTED_PRIZE_TIER_COUNT[lt]:
            raise P281AValidationError(
                f"{lt} distinct prize tiers {len(prize_tiers)} != "
                f"{EXPECTED_PRIZE_TIER_COUNT[lt]}")
        out[lt] = {
            "combinations_enumerated": len(grid),
            "distinct_prize_tiers": len(prize_tiers),
            "expected_prize_tiers": EXPECTED_PRIZE_TIER_COUNT[lt],
            "no_prize_combinations": no_prize_combos,
            "mutually_exclusive": True,
            "exhaustive_over_integer_grid": True,
        }
    return out


# --------------------------------------------------------------------------- #
# Task B/C — richer per-row processing (prize-tier + distinct-ticket capture)  #
# --------------------------------------------------------------------------- #

def _ticket_key(scorer_input: dict):
    """Canonical content key for distinct-ticket counting: the sorted predicted
    main numbers plus the predicted second-zone (POWER only)."""
    return (
        tuple(sorted(scorer_input["predicted_main_numbers"])),
        scorer_input["predicted_second_zone"],
    )


def process_cell_rows(rows) -> tuple:
    """Deduplicate by (target_draw, bet_index) and classify each row with full
    prize-tier detail. No leakage: scoring uses prediction + actual target only
    AFTER the ticket exists; eligibility enforces history_cutoff_draw < target.

    Returns (processed, distinct_draws_desc). processed rows keep the original
    CAST-DESC order (no pseudo-replication)."""
    processed = []
    distinct_draws_desc = []
    seen_draw = set()
    seen_bet = set()
    for raw in rows:
        row = _row_dict(raw)
        td, bi = row["target_draw"], row["bet_index"]
        if (td, bi) in seen_bet:
            continue
        seen_bet.add((td, bi))
        eligible, reason = _check_eligibility(row)
        rec = {
            "target_draw": td, "bet_index": bi,
            "eligible": eligible, "reason": reason,
            "win": False, "m3plus": False,
            "main_hit_count": None, "special_hit": None,
            "tier": None, "ticket_key": None,
        }
        if eligible:
            scorer_input = map_replay_row_to_scorer_input(row)
            result = score_prize_aware_ticket(**scorer_input)
            rec.update({
                "win": bool(result["any_prize_aware_win"]),
                "m3plus": bool(result["is_m3_plus"]),
                "main_hit_count": int(result["main_hit_count"]),
                "special_hit": int(result["special_hit"]),
                "tier": result["tier_class"],
                "ticket_key": _ticket_key(scorer_input),
            })
        processed.append(rec)
        if td not in seen_draw:
            seen_draw.add(td)
            distinct_draws_desc.append(td)
    return processed, distinct_draws_desc


def aggregate_prize_aware_window(processed, distinct_draws_desc, window,
                                 lottery, strategy) -> dict:
    """Compute draw-level observed counts AND the prize-tier contribution
    decomposition for one strategy x lottery x window, plus the inputs needed to
    call the reused evaluate_window (support draws + per-supported-draw distinct
    ticket counts)."""
    window_draws = distinct_draws_desc[:window]
    window_set = set(window_draws)
    by_draw = {}
    for pr in processed:
        if pr["target_draw"] not in window_set:
            continue
        d = by_draw.setdefault(pr["target_draw"], {
            "bets": set(), "tickets": set(), "any_win": False,
            "any_m3plus": False, "tiers": [], "main_hits": [],
            "special_hits": [], "excluded": [],
        })
        if pr["eligible"]:
            d["bets"].add(pr["bet_index"])
            d["tickets"].add(pr["ticket_key"])
            d["tiers"].append(pr["tier"])
            d["main_hits"].append(pr["main_hit_count"])
            d["special_hits"].append(pr["special_hit"])
            if pr["win"]:
                d["any_win"] = True
            if pr["m3plus"]:
                d["any_m3plus"] = True
        else:
            d["excluded"].append(pr["reason"])

    support_draws = 0
    observed_successes = 0
    m3plus_successes = 0
    low_tier_only_successes = 0
    scoreable_rows = 0
    excluded_rows = 0
    exclusion_by_reason = Counter()
    tier_counter = Counter()
    main_hit_counter = Counter()
    special_hit_bets = 0
    bet_counts = []
    distinct_ticket_counts = []
    identity_draws = []  # one entry per SUPPORTED draw (evaluate_window contract)

    for td in window_draws:
        d = by_draw.get(td)
        if d is None:
            continue
        scoreable_rows += len(d["bets"])
        excluded_rows += len(d["excluded"])
        exclusion_by_reason.update(d["excluded"])
        if len(d["bets"]) < 1:
            continue
        support_draws += 1
        n_distinct = len(d["tickets"])
        bet_counts.append(len(d["bets"]))
        distinct_ticket_counts.append(n_distinct)
        identity_draws.append({"target_draw": td, "distinct_ticket_count": n_distinct})
        tier_counter.update(d["tiers"])
        main_hit_counter.update(d["main_hits"])
        special_hit_bets += sum(d["special_hits"])
        if d["any_win"]:
            observed_successes += 1
            if d["any_m3plus"]:
                m3plus_successes += 1
            else:
                low_tier_only_successes += 1

    excluded_missing_special = exclusion_by_reason.get(
        EXCLUSION_MISSING_PREDICTED_SECOND_ZONE, 0)
    bet_count_distribution = {str(k): v for k, v in sorted(Counter(bet_counts).items())}
    obs_rate = observed_successes / support_draws if support_draws else None
    m3_rate = m3plus_successes / support_draws if support_draws else None
    return {
        "lottery_type": lottery,
        "strategy_id": strategy,
        "window": window,
        "window_label": WINDOW_LABELS.get(window, ALL_AVAILABLE_LABEL),
        "distinct_draws_in_window": len(window_draws),
        "support_draws": support_draws,
        "observed_successes": observed_successes,
        "observed_success_rate": _r(obs_rate) if obs_rate is not None else None,
        "legacy_m3plus_successes": m3plus_successes,
        "legacy_m3plus_success_rate": _r(m3_rate) if m3_rate is not None else None,
        "prize_aware_minus_legacy_delta": (
            _r(obs_rate - m3_rate) if obs_rate is not None else None),
        "low_tier_only_successes": low_tier_only_successes,
        "scoreable_rows": scoreable_rows,
        "excluded_rows": excluded_rows,
        "excluded_missing_second_zone_rows": excluded_missing_special,
        "exclusion_by_reason": dict(sorted(exclusion_by_reason.items())),
        "bet_count_distribution": bet_count_distribution,
        "tier_distribution_bet_level": dict(sorted(tier_counter.items())),
        "main_hit_distribution_bet_level": {
            str(k): v for k, v in sorted(main_hit_counter.items())},
        "special_or_second_zone_hit_bets": special_hit_bets,
        "_identity_draws": identity_draws,  # internal; stripped before persisting
    }


def contribution_block(lottery: str, win_rec: dict) -> dict:
    """Per-lottery decomposition of any-prize-aware wins into the legacy-M3+
    component and the lower-tier component the prize-aware definition adds."""
    total = win_rec["observed_successes"]
    m3 = win_rec["legacy_m3plus_successes"]
    low = win_rec["low_tier_only_successes"]
    base = {
        "any_prize_aware_total_success_draws": total,
        "m3plus_attributable_success_draws": m3,
    }
    if lottery == "BIG_LOTTO":
        base["m2_plus_special_only_success_draws"] = low
        base["contribution_note"] = (
            "draws won ONLY via M2+special (no bet reached M3+); the incremental "
            "win the prize-aware definition adds over legacy M3+")
    elif lottery == "POWER_LOTTO":
        base["m1_or_m2_plus_second_zone_only_success_draws"] = low
        base["support_loss_missing_second_zone_rows"] = (
            win_rec["excluded_missing_second_zone_rows"])
        base["contribution_note"] = (
            "draws won ONLY via (M1 or M2)+second-zone (no bet reached M3+); plus "
            "rows lost to missing predicted second-zone (never backfilled)")
    else:  # DAILY_539
        base["m2_only_success_draws"] = low
        base["contribution_note"] = (
            "draws won ONLY via exactly-M2 (肆獎); the incremental win the "
            "prize-aware definition adds over legacy M3+")
    return base


# --------------------------------------------------------------------------- #
# Task B — support classification                                              #
# --------------------------------------------------------------------------- #

def classify_support(lottery: str, windows_by_label: dict, all_window: dict) -> dict:
    """Classify support for a cell from its family windows + widest evidence.

    Cell-level status reflects how testable the cell is across the three family
    windows, distinguishing data-level blocks (no scoreable rows: missing
    second-zone / special / draw-join) from mere low effective support (e.g. the
    100-draw window being under-powered for a rare prize-aware event). The
    `evaluable` gate (support >= 30 AND expected >= 5) is read from the reused
    evaluate_window output already attached to each family window."""
    excl = all_window["exclusion_by_reason"]
    scoreable = all_window["scoreable_rows"]
    miss2z = excl.get(EXCLUSION_MISSING_PREDICTED_SECOND_ZONE, 0)
    join_excl = (excl.get(EXCLUSION_MISSING_DRAW_JOIN, 0)
                 + excl.get(EXCLUSION_AMBIGUOUS_DRAW_JOIN, 0))

    per_window = {}
    family_windows_evaluable = 0
    for label in WINDOW_ORDER:
        w = windows_by_label[label]
        if w["support_draws"] == 0:
            if join_excl > 0:
                per_window[label] = SUPPORT_BLOCKED_JOIN
            elif lottery == "POWER_LOTTO" and miss2z > 0:
                per_window[label] = SUPPORT_NO_SECOND_ZONE
            else:
                per_window[label] = SUPPORT_LOW
        elif w.get("inference", {}).get("evaluable"):
            per_window[label] = SUPPORT_ENOUGH
            family_windows_evaluable += 1
        else:
            per_window[label] = SUPPORT_LOW

    if scoreable == 0:
        if lottery == "POWER_LOTTO" and miss2z > 0:
            cell_status = SUPPORT_NO_SECOND_ZONE
        elif lottery == "BIG_LOTTO" and excl.get(
                EXCLUSION_INVALID_ACTUAL_AUXILIARY, 0) > 0:
            cell_status = SUPPORT_NO_SPECIAL
        elif join_excl > 0:
            cell_status = SUPPORT_BLOCKED_JOIN
        else:
            cell_status = SUPPORT_LOW
    elif family_windows_evaluable == len(WINDOW_ORDER):
        cell_status = SUPPORT_ENOUGH
    else:
        # Has scoreable data but not every family window is inferentially
        # evaluable (typically the 100-draw window under-powered): LOW, not blocked.
        cell_status = SUPPORT_LOW
    return {
        "cell_support_status": cell_status,
        "per_window_support_status": per_window,
        "family_windows_evaluable": family_windows_evaluable,
        "widest_support_draws": all_window["support_draws"],
        "widest_scoreable_rows": scoreable,
        "missing_second_zone_rows": miss2z,
    }


# --------------------------------------------------------------------------- #
# Task D — deterministic Monte-Carlo cross-check of the analytic baseline      #
# --------------------------------------------------------------------------- #

def monte_carlo_draw_baseline(total: int, winning: int, n_tickets: int,
                              trials: int, seed: int) -> float:
    """Deterministic MC estimate of P(>=1 of n distinct tickets wins), sampling
    n distinct ticket-ids without replacement from [0,total); the first
    `winning` ids are designated winners (tickets are exchangeable). Seeded =>
    bit-for-bit reproducible. Used only to confirm the exact analytic baseline."""
    rng = random.Random(seed)
    hits = 0
    for _ in range(trials):
        picks = rng.sample(range(total), n_tickets)
        if any(p < winning for p in picks):
            hits += 1
    return hits / trials


def monte_carlo_crosscheck() -> dict:
    checks = []
    for lottery, n in MONTE_CARLO_CELLS:
        total, winning = ticket_universe(lottery)
        analytic = exact_distinct_draw_baseline(total, winning, n)
        mc = monte_carlo_draw_baseline(total, winning, n,
                                       MONTE_CARLO_TRIALS, MONTE_CARLO_SEED)
        checks.append({
            "lottery_type": lottery,
            "n_tickets": n,
            "analytic_exact_q": _r(analytic),
            "monte_carlo_q": _r(mc),
            "absolute_difference": _r(abs(mc - analytic)),
            "within_tolerance_0_02": abs(mc - analytic) < 0.02,
        })
    return {
        "purpose": "confirm exact analytic distinct-ticket baseline empirically",
        "primary_baseline": "analytic_exact_without_replacement",
        "monte_carlo_used_for_inference": False,
        "seed": MONTE_CARLO_SEED,
        "trials": MONTE_CARLO_TRIALS,
        "checks": checks,
        "all_within_tolerance": all(c["within_tolerance_0_02"] for c in checks),
    }


# --------------------------------------------------------------------------- #
# Inference per cell (reuses evaluate_window / stability / decision verbatim)  #
# --------------------------------------------------------------------------- #

def _strip_inference_trace(inf: dict) -> dict:
    """Drop the verbose per-draw distinct-ticket trace (kept compact via the
    distribution) so the artifact stays readable; keeps every statistic."""
    out = dict(inf)
    out.pop("per_draw_distinct_ticket_trace", None)
    out.pop("null_probability_diagnostics", None)
    return out


def run_window_inference(lottery: str, strategy: str, win_rec: dict) -> dict:
    """Build the evaluate_window inputs from our richer aggregate and call the
    reused exact-distinct-ticket inference engine."""
    window_record = {
        "window": win_rec["window"],
        "window_label": win_rec["window_label"],
        "support_draws": win_rec["support_draws"],
        "observed_successes": win_rec["observed_successes"],
        "bet_count_distribution": win_rec["bet_count_distribution"],
    }
    inf = evaluate_window(lottery, strategy, window_record, win_rec["_identity_draws"])
    return _strip_inference_trace(inf)


def cell_verdict(cell_support_status: str, family_windows_evaluable: int,
                 overall_decision: str) -> str:
    """P281A per-group verdict (presentation over the reused frozen decision).

    BLOCKED_SUPPORT is reserved for cells with a data-level support block (no
    scoreable rows: POWER missing-second-zone / BIG missing-special / draw-join)
    or with zero inferentially-evaluable family windows. A cell that is evaluable
    on at least one family window but shows no corrected, cross-window-stable
    edge is NULL — even if the 100-draw window alone is under-powered."""
    if cell_support_status in (SUPPORT_NO_SECOND_ZONE, SUPPORT_NO_SPECIAL,
                               SUPPORT_BLOCKED_JOIN, SUPPORT_BLOCKED_SCHEMA):
        return VERDICT_BLOCKED_SUPPORT
    if family_windows_evaluable == 0:
        return VERDICT_BLOCKED_SUPPORT
    if overall_decision == "GO_CANDIDATE_RESEARCH_ONLY":
        return VERDICT_OBSERVATION_CANDIDATE
    return VERDICT_NULL


def evaluate_cell(conn, lottery: str, strategy: str) -> dict:
    """Full P281A evaluation for one strategy x lottery cell across windows."""
    rows = conn.execute(CELL_QUERY, (lottery, strategy)).fetchall()
    processed, distinct_draws_desc = process_cell_rows(rows)
    distinct_available = len(distinct_draws_desc)

    # Consistency cross-check: our prize-aware aggregate must match the committed
    # base exporter aggregate_window (same endpoint, same dedupe) for each window.
    base_processed = [{
        "target_draw": p["target_draw"], "bet_index": p["bet_index"],
        "eligible": p["eligible"], "reason": p["reason"], "win": p["win"],
    } for p in processed]

    windows_by_label = {}
    window_metrics = []
    for w in P281A_WINDOWS:
        wm = aggregate_prize_aware_window(processed, distinct_draws_desc, w,
                                          lottery, strategy)
        base = aggregate_window(base_processed, distinct_draws_desc, w,
                                lottery, strategy)
        if (base["support_draws"] != wm["support_draws"]
                or base["observed_successes"] != wm["observed_successes"]):
            raise P281AValidationError(
                f"{lottery}/{strategy} w{w}: prize-aware aggregate disagrees with "
                f"committed exporter (support/observed); endpoint inconsistency")
        wm["inference"] = run_window_inference(lottery, strategy, wm)
        wm["consistency_with_committed_exporter"] = True
        label = wm["window_label"]
        windows_by_label[label] = wm
        identity = wm.pop("_identity_draws")
        wm["distinct_ticket_count_distribution"] = {
            str(k): v for k, v in sorted(
                Counter(d["distinct_ticket_count"] for d in identity).items())}
        wm["contribution"] = contribution_block(lottery, wm)
        window_metrics.append(wm)

    # Supplementary all_available window (descriptive; NOT in correction family).
    all_wm = aggregate_prize_aware_window(processed, distinct_draws_desc,
                                          distinct_available, lottery, strategy)
    all_wm["window_label"] = ALL_AVAILABLE_LABEL
    all_wm["inference"] = run_window_inference(lottery, strategy, all_wm)
    all_identity = all_wm.pop("_identity_draws")
    all_wm["distinct_ticket_count_distribution"] = {
        str(k): v for k, v in sorted(
            Counter(d["distinct_ticket_count"] for d in all_identity).items())}
    all_wm["contribution"] = contribution_block(lottery, all_wm)
    all_wm["family_member"] = False
    all_wm["note"] = "supplementary descriptive window; excluded from Bonferroni family"

    # Group-level stability + decision via the reused frozen logic.
    inf_by_label = {label: windows_by_label[label]["inference"]
                    for label in WINDOW_ORDER}
    stability = evaluate_stability(inf_by_label)
    for label in WINDOW_ORDER:
        inf = inf_by_label[label]
        inf["window_decision"] = finalize_window_decision(label, inf, stability)
    overall = overall_group_decision(inf_by_label, stability)
    support = classify_support(lottery, windows_by_label, all_wm)
    verdict = cell_verdict(support["cell_support_status"],
                           support["family_windows_evaluable"], overall)

    # Uncorrected-only positive observation: an evaluable family window beats the
    # random baseline at raw alpha but the cell is not a corrected candidate.
    # Reported for transparency; never a prediction-success claim.
    uncorrected_positive = verdict == VERDICT_NULL and any(
        w["inference"].get("evaluable")
        and float(w["inference"].get("absolute_excess", 0.0)) > 0.0
        and float(w["inference"].get("raw_p_value_one_sided_upper", 1.0)) <= FAMILY_ALPHA
        for w in windows_by_label.values())

    return {
        "lottery_type": lottery,
        "strategy_id": strategy,
        "distinct_draws_available": distinct_available,
        "support": support,
        "windows": window_metrics,
        "supplementary_all_available": all_wm,
        "stability": stability,
        "overall_group_decision": overall,
        "p281a_verdict": verdict,
        "uncorrected_positive_observation": uncorrected_positive,
    }


# --------------------------------------------------------------------------- #
# Task E — cross-lottery comparison                                           #
# --------------------------------------------------------------------------- #

def _long_window(cell: dict) -> dict:
    for w in cell["windows"]:
        if w["window_label"] == "LONG":
            return w
    return cell["windows"][-1]


def cross_lottery_summary(cells: list) -> dict:
    by_lottery = {lt: [c for c in cells if c["lottery_type"] == lt]
                  for lt in LOTTERY_TYPES}
    per_lottery = {}
    for lt, group in by_lottery.items():
        deltas = []
        missing_second_zone = 0
        rank_prize = []
        rank_legacy = []
        for c in group:
            lw = _long_window(c)
            if lw["observed_success_rate"] is not None:
                if lw["prize_aware_minus_legacy_delta"] is not None:
                    deltas.append(lw["prize_aware_minus_legacy_delta"])
                rank_prize.append((lw["observed_success_rate"], c["strategy_id"]))
                rank_legacy.append((lw["legacy_m3plus_success_rate"], c["strategy_id"]))
            missing_second_zone += c["support"]["missing_second_zone_rows"]
        order_prize = [s for _, s in sorted(rank_prize, reverse=True)]
        order_legacy = [s for _, s in sorted(rank_legacy, reverse=True)]
        per_lottery[lt] = {
            "cells": len(group),
            "mean_prize_aware_minus_legacy_delta_long": (
                _r(sum(deltas) / len(deltas)) if deltas else None),
            "max_prize_aware_minus_legacy_delta_long": (
                _r(max(deltas)) if deltas else None),
            "total_missing_second_zone_rows": missing_second_zone,
            "ranking_top_changes_prize_vs_legacy": order_prize != order_legacy,
            "ranking_top_strategy_prize_aware": order_prize[0] if order_prize else None,
            "ranking_top_strategy_legacy_m3plus": order_legacy[0] if order_legacy else None,
        }
    deltas_named = [(per_lottery[lt]["mean_prize_aware_minus_legacy_delta_long"], lt)
                    for lt in LOTTERY_TYPES
                    if per_lottery[lt]["mean_prize_aware_minus_legacy_delta_long"] is not None]
    most_diff = max(deltas_named)[1] if deltas_named else None
    second_zone_named = [(per_lottery[lt]["total_missing_second_zone_rows"], lt)
                         for lt in LOTTERY_TYPES]
    most_second_zone_loss = max(second_zone_named)[1]
    return {
        "per_lottery": per_lottery,
        "lottery_success_def_differs_most_from_m3plus": most_diff,
        "lottery_most_affected_by_missing_second_zone": most_second_zone_loss,
        "ranking_staleness_note": (
            "A cell's prize-aware ranking can differ from its legacy M3+ ranking "
            "where lower-tier wins (M2+special / M1+second / M2) are material; any "
            "prior ranking built on M3+-only scoring is potentially stale for that "
            "lottery. This is descriptive only — no strategy is re-ranked for "
            "deployment here."),
        "big_runner_note": (
            "BIG already uses M2+special (P280AT). P281A does not change the BIG "
            "NULL/no-edge conclusion; the BIG runner remains no-edge / no-claim."),
        "power_runner_note": (
            "POWER ranking should be treated as BLOCKED pending adequate predicted "
            "second-zone support wherever NO_SECOND_ZONE_SUPPORT / heavy "
            "missing-second-zone exclusion is observed."),
        "daily539_note": (
            "DAILY_539 is validatable with the M2+ (>=2 main) baseline; it carries "
            "the most lower-tier contribution."),
    }


# --------------------------------------------------------------------------- #
# Orchestration                                                                #
# --------------------------------------------------------------------------- #

def _final_classification(cells: list) -> tuple:
    verdicts = [c["p281a_verdict"] for c in cells]
    n_candidates = sum(v == VERDICT_OBSERVATION_CANDIDATE for v in verdicts)
    n_blocked = sum(v == VERDICT_BLOCKED_SUPPORT for v in verdicts)
    n_null = sum(v == VERDICT_NULL for v in verdicts)
    if n_candidates > 0:
        analytical = "OBSERVATION_CANDIDATES_FOUND"
        final = ("P281A_CROSS_LOTTERY_PRIZE_AWARE_VALIDATION_PR_OPEN_"
                 "OBSERVATION_CANDIDATES_NO_PUBLICATION")
    elif n_null == 0 and n_blocked > 0:
        analytical = "SUPPORT_BLOCKED"
        final = ("P281A_CROSS_LOTTERY_PRIZE_AWARE_VALIDATION_PR_OPEN_"
                 "SUPPORT_BLOCKED_NO_PUBLICATION")
    else:
        analytical = "NULL_NO_CORRECTED_CANDIDATES"
        final = ("P281A_CROSS_LOTTERY_PRIZE_AWARE_VALIDATION_PR_OPEN_"
                 "NULL_NO_PUBLICATION")
    return analytical, final, {"observation_candidate": n_candidates,
                               "null": n_null, "blocked_support": n_blocked}


def build_result(db_path: str = CANONICAL_DB_PATH,
                 p267c_path: str = P267C_JSON_PATH,
                 p271a_path: str = P271A_JSON_PATH,
                 scorer_path: str = P271C_SOURCE_PATH,
                 adapter_path: str = P271E_SOURCE_PATH) -> dict:
    """Run the full read-only cross-lottery prize-aware validation. Owns exactly
    one mode=ro connection and one read transaction (one snapshot)."""
    rules = verify_prize_rules_and_truth_tables()
    tier_check = verify_tier_exclusivity_exhaustiveness()
    mc = monte_carlo_crosscheck()
    if not mc["all_within_tolerance"]:
        raise P281AValidationError("Monte-Carlo cross-check exceeded tolerance")

    frozen_cells = load_frozen_cells(p267c_path)
    committed_conditions = verify_endpoints_against_p271a(p271a_path)
    source_hashes = {
        "p271a_json_sha256": sha256_file(p271a_path),
        "p267c_json_sha256": sha256_file(p267c_path),
        "p271c_source_sha256": sha256_file(scorer_path),
        "p271e_source_sha256": sha256_file(adapter_path),
    }

    conn, query_only_evidence = open_readonly_connection(db_path)
    transaction_start_at = _now_iso()
    try:
        conn.execute("BEGIN")  # one explicit read transaction => one snapshot
        schema = verify_schema(conn)
        cells = [evaluate_cell(conn, c["lottery_type"], c["strategy_id"])
                 for c in frozen_cells]
        conn.execute("ROLLBACK")  # end read transaction; no write performed
    finally:
        conn.close()
    transaction_end_at = _now_iso()

    analytical_outcome, final_classification, verdict_counts = _final_classification(cells)

    # Correction family: descriptive BH-FDR over evaluable (cell,window) raw p's.
    family_raw_p = []
    for c in cells:
        for w in c["windows"]:
            inf = w["inference"]
            if inf.get("evaluable"):
                family_raw_p.append(inf["raw_p_value_one_sided_upper"])
    bh_flags = benjamini_hochberg(family_raw_p) if family_raw_p else []
    any_corrected = any(
        w["inference"].get("significant_positive")
        and float(w["inference"].get("absolute_excess", 0.0)) > 0.0
        for c in cells for w in c["windows"])

    ticket_universes = {lt: dict(zip(("total", "winning"), ticket_universe(lt)))
                        for lt in LOTTERY_TYPES}
    analytic_baselines = {lt: {
        "ticket_baseline": _r(analytic_ticket_baseline(lt)["ticket_baseline"]),
        "main_hit_distribution": [_r(p) for p in main_hit_distribution(lt)],
    } for lt in LOTTERY_TYPES}

    result = {
        "meta": {
            "task_id": TASK_ID,
            "artifact_version": ARTIFACT_VERSION,
            "scoring_version": SCORING_VERSION,
            "adapter_version": ADAPTER_VERSION,
            "source_verification_status": SOURCE_VERIFICATION_STATUS,
            "generated_at": _now_iso(),
            "generated_date_fixed": GENERATED_DATE,
            "branch": BRANCH,
            "origin_main": ORIGIN_MAIN,
            "frozen_strategy_cell_count": len(frozen_cells),
            "lotteries": list(LOTTERY_TYPES),
            "inferential_windows": list(P281A_WINDOWS),
            "supplementary_window": ALL_AVAILABLE_LABEL,
            "analysis_unit": "distinct target_draw (draw-level any-bet)",
        },
        "final_classification": final_classification,
        "analytical_outcome": analytical_outcome,
        "verdict_counts": verdict_counts,
        "reconciliation_with_p273a": {
            "p273a_primary_windows": [50, 300, 750],
            "p273a_primary_did_full_inference": True,
            "p273a_100_500_1500_was_observed_counts_only": True,
            "p281a_adds": (
                "the inferential layer (random baseline, p-value, Bonferroni, "
                "BH-FDR, CIs) on the 100/500/1500 windows P273A left as "
                "observed-count-only, plus cross-lottery success-definition "
                "verification, contribution decomposition, and support audit"),
            "prior_reference_observed_counts": PRIOR_REFERENCE_OBSERVED_COUNTS,
            "prior_primary_inference": PRIOR_PRIMARY_INFERENCE,
            "methodology_reused_verbatim": True,
        },
        "safety_flags": {
            "db_read_only": True,
            "db_opened": True,
            "db_queried": True,
            "db_copied": False,
            "db_written": False,
            "production_write": False,
            "services_controlled": False,
            "registry_mutation": False,
            "scorer_source_changed": False,
            "adapter_source_changed": False,
            "strategy_source_changed": False,
            "prediction_success_claim": False,
            "strategy_promoted": False,
            "activation": False,
            "real_publication": False,
            "official_target_lookup": False,
            "official_deadline_lookup": False,
            "pre_draw_manifest_created": False,
            "publication_pr_created": False,
            "second_zone_manufactured": False,
            "monte_carlo_used_for_inference": False,
        },
        "lottery_success_definitions": {
            lt: {
                "endpoint_id": GOVERNED_ENDPOINT[lt]["endpoint_id"],
                "committed_condition_sql": committed_conditions[lt],
                "rule_shorthand": GOVERNED_ENDPOINT[lt]["task_shorthand"],
                "min_qualifying_tier": GOVERNED_ENDPOINT[lt]["min_qualifying_tier"],
                "scored_by": "lottery_api.prize_aware_scorer.any_prize_aware_win",
            } for lt in LOTTERY_TYPES
        },
        "rule_verification": rules,
        "tier_exclusivity_exhaustiveness": tier_check,
        "random_baseline_config": {
            "method": "analytic exact distinct-ticket without-replacement "
                      "q_N = 1 - C(T-W,N)/C(T,N) per draw; aggregated via exact "
                      "binomial (constant N) or exact Poisson-binomial (varying N)",
            "ticket_universes": ticket_universes,
            "analytic_baselines": analytic_baselines,
            "same_budget_rule": "N = distinct predicted ticket contents per draw "
                                "(the strategy's own per-draw budget)",
            "confidence_intervals": "Wilson + Clopper-Pearson 95% (reused)",
            "min_support_draws": MIN_SUPPORT_DRAWS,
            "min_expected_successes": MIN_EXPECTED_SUCCESSES,
        },
        "monte_carlo_crosscheck": mc,
        "correction": {
            "family_definition": "lottery x strategy x endpoint x window",
            "family_windows": list(P281A_WINDOWS),
            "family_size_m": CORRECTION_FAMILY_M,
            "family_alpha": FAMILY_ALPHA,
            "bonferroni_applied": True,
            "bh_fdr_q": BH_FDR_Q,
            "bh_fdr_descriptive_only": True,
            "evaluable_tested_cells_windows": len(family_raw_p),
            "bh_fdr_rejections_descriptive": int(sum(bh_flags)),
            "any_cell_beats_random_uncorrected": any(
                w["inference"].get("evaluable")
                and float(w["inference"].get("absolute_excess", 0.0)) > 0.0
                and float(w["inference"].get("raw_p_value_one_sided_upper", 1.0)) <= FAMILY_ALPHA
                for c in cells for w in c["windows"]),
            "any_cell_survives_bonferroni": any_corrected,
            "supplementary_all_available_in_family": False,
        },
        "provenance": {
            "source_db_path": db_path,
            "db_open_mode": DB_OPEN_MODE,
            "query_only_evidence": query_only_evidence,
            "single_snapshot": True,
            "single_connection": True,
            "transaction_start_at": transaction_start_at,
            "transaction_end_at": transaction_end_at,
            "permitted_tables": sorted(REQUIRED_COLUMNS.keys()),
            "normalized_cell_query": CELL_QUERY,
            "schema": schema,
            "source_hashes": source_hashes,
            "reused_modules": [
                "lottery_api/prize_aware_scorer.py",
                "lottery_api/prize_aware_replay_adapter.py",
                "analysis/p273a_prizeaware_replay_export.py",
                "analysis/p273a_prize_aware_inferential_validation.py",
            ],
            "frozen_cells": frozen_cells,
        },
        "cells": cells,
        "cross_lottery_summary": cross_lottery_summary(cells),
        "limitations": [
            "Backward replay over already-drawn historical data; not prospective "
            "and not out-of-sample for live deployment.",
            "source_verification_status = MANUAL_VERIFICATION_REQUIRED: official "
            "prize-table pages were not machine-verified (carried from P271B/C).",
            "POWER_LOTTO support is reduced by missing-predicted-second-zone "
            "exclusions; missing values are NEVER backfilled.",
            "Observation candidates (if any) are research-only and require a "
            "separate, separately-authorized future-only / OOS validation before "
            "any promotion; none is performed or implied here.",
            "all_available window is descriptive only and excluded from the "
            "Bonferroni family.",
        ],
        "next_recommended_research_step": (
            "Independent audit of this validation PR; then, only if observation "
            "candidates exist, a separately-authorized prospective / out-of-sample "
            "validation. POWER strategy ranking should remain blocked pending a "
            "separate predicted-second-zone data-support task. No promotion, "
            "activation, or publication without explicit Owner authorization."),
    }
    result["canonical_payload_digest"] = compute_payload_digest(result)
    return result


# --------------------------------------------------------------------------- #
# Markdown rendering (deterministic; derived from the one canonical result)   #
# --------------------------------------------------------------------------- #

def render_markdown(result: dict) -> str:
    meta = result["meta"]
    lines = []
    A = lines.append
    A("# P281A — Cross-Lottery Prize-Aware Success Definition and Inferential Validation")
    A("")
    A("> **Local research / replay validation only.** No real publication, no "
      "pre-draw manifest, no publication PR, no official target/deadline lookup, "
      "no strategy promotion or activation, no registry/production/DB write. "
      "`prediction_success_claim = false`.")
    A("")
    A(f"- **final_classification:** `{result['final_classification']}`")
    A(f"- **analytical_outcome:** `{result['analytical_outcome']}` "
      f"(candidates={result['verdict_counts']['observation_candidate']}, "
      f"null={result['verdict_counts']['null']}, "
      f"blocked_support={result['verdict_counts']['blocked_support']})")
    A(f"- task_id: `{meta['task_id']}`")
    A(f"- origin_main: `{meta['origin_main']}`")
    A(f"- scoring_version: `{meta['scoring_version']}` / "
      f"source_verification_status: `{meta['source_verification_status']}`")
    A(f"- frozen cells: **{meta['frozen_strategy_cell_count']}** "
      f"({', '.join(meta['lotteries'])}); inferential windows: "
      f"{', '.join(str(w) for w in meta['inferential_windows'])} (+ "
      f"{meta['supplementary_window']} supplementary)")
    A(f"- canonical_payload_digest: `{result['canonical_payload_digest']}`")
    A("")
    A("## Reconciliation with P273A")
    rec = result["reconciliation_with_p273a"]
    A("")
    A(f"- P273A PRIMARY windows {rec['p273a_primary_windows']} received full "
      f"inference; its **100/500/1500 export was observed-count-only**.")
    A(f"- P281A adds: {rec['p281a_adds']}")
    A(f"- methodology reused verbatim: `{str(rec['methodology_reused_verbatim']).lower()}`")
    A("")
    A("## Lottery success definitions (verified against the committed scorer)")
    A("")
    A("| lottery | endpoint | condition | min tier |")
    A("|---|---|---|---|")
    for lt in result["meta"]["lotteries"]:
        d = result["lottery_success_definitions"][lt]
        A(f"| {lt} | `{d['endpoint_id']}` | `{d['committed_condition_sql']}` | "
          f"{d['min_qualifying_tier']} |")
    A("")
    A("### Truth-table edges (via the real P271C scorer)")
    for lt in result["meta"]["lotteries"]:
        A("")
        A(f"**{lt}**")
        A("")
        A("| main_hits | special | tier | any_prize_win | is_m3_plus | note |")
        A("|---:|---:|---|:--:|:--:|---|")
        for f in result["rule_verification"][lt]["truth_table"]:
            A(f"| {f['main_hit_count']} | {f['special_hit']} | `{f['tier_class']}` | "
              f"{'✅' if f['any_prize_aware_win'] else '❌'} | "
              f"{'✓' if f['is_m3_plus'] else '·'} | {f['note']} |")
    A("")
    A("## Random baseline + correction config")
    cfg = result["random_baseline_config"]
    cor = result["correction"]
    A("")
    A(f"- baseline: {cfg['method']}")
    A(f"- CIs: {cfg['confidence_intervals']}; gates: support >= "
      f"{cfg['min_support_draws']} AND expected >= {cfg['min_expected_successes']}")
    A(f"- correction family: {cor['family_definition']} = **m={cor['family_size_m']}** "
      f"(windows {cor['family_windows']}); alpha={cor['family_alpha']}")
    A(f"- evaluable tested (cell,window): **{cor['evaluable_tested_cells_windows']}**; "
      f"any beats random uncorrected: `{str(cor['any_cell_beats_random_uncorrected']).lower()}`; "
      f"any survives Bonferroni: `{str(cor['any_cell_survives_bonferroni']).lower()}`")
    A(f"- BH-FDR (descriptive only) rejections: {cor['bh_fdr_rejections_descriptive']}")
    mc = result["monte_carlo_crosscheck"]
    A(f"- Monte-Carlo cross-check (seed={mc['seed']}, trials={mc['trials']}, "
      f"NOT used for inference): all_within_tolerance="
      f"`{str(mc['all_within_tolerance']).lower()}`")
    A("")
    A("## Per-cell verdicts (windows 100 / 500 / 1500)")
    A("")
    A("| lottery | strategy | support | verdict | overall | LONG obs_rate | "
      "LONG baseline | LONG Δpp | LONG bonf_p | prize−legacy Δ |")
    A("|---|---|---|---|---|---:|---:|---:|---:|---:|")
    for c in result["cells"]:
        lw = _long_window(c)
        inf = lw["inference"]
        obs = f"{inf['observed_rate']:.5f}" if inf.get("evaluable") else "—"
        base = f"{inf['mean_baseline_rate']:.5f}" if inf.get("evaluable") else "—"
        dpp = f"{inf['absolute_excess_pp']:+.4f}" if inf.get("evaluable") else "—"
        bp = f"{inf['bonferroni_p_value']:.4f}" if inf.get("evaluable") else "—"
        delta = (f"{lw['prize_aware_minus_legacy_delta']:+.5f}"
                 if lw["prize_aware_minus_legacy_delta"] is not None else "—")
        A(f"| {c['lottery_type']} | {c['strategy_id']} | "
          f"{c['support']['cell_support_status']} | **{c['p281a_verdict']}** | "
          f"{c['overall_group_decision']} | {obs} | {base} | {dpp} | {bp} | {delta} |")
    A("")
    A("## Observation candidates (research-only; NOT promoted, NOT activated)")
    A("")
    cands = [c for c in result["cells"]
             if c["p281a_verdict"] == VERDICT_OBSERVATION_CANDIDATE]
    if not cands:
        A("- None. No cell beats the appropriate random baseline and survives "
          "Bonferroni correction with cross-window stability.")
    else:
        for c in cands:
            lw = _long_window(c)
            A(f"- `{c['lottery_type']}/{c['strategy_id']}` — research-only "
              f"observation candidate (stability={c['stability']['status']}, "
              f"LONG Δpp={lw['inference']['absolute_excess_pp']:+.4f}, "
              f"bonf_p={lw['inference']['bonferroni_p_value']:.4f}). Requires "
              f"separate future-only/OOS authorization before any promotion.")
    A("")
    A("## Cross-lottery summary")
    cs = result["cross_lottery_summary"]
    A("")
    A("| lottery | cells | mean prize−legacy Δ (LONG) | missing 2nd-zone rows | "
      "ranking changes |")
    A("|---|---:|---:|---:|:--:|")
    for lt in result["meta"]["lotteries"]:
        p = cs["per_lottery"][lt]
        md = (f"{p['mean_prize_aware_minus_legacy_delta_long']:+.5f}"
              if p["mean_prize_aware_minus_legacy_delta_long"] is not None else "—")
        A(f"| {lt} | {p['cells']} | {md} | {p['total_missing_second_zone_rows']} | "
          f"{'yes' if p['ranking_top_changes_prize_vs_legacy'] else 'no'} |")
    A("")
    A(f"- success-def differs most from M3+: **{cs['lottery_success_def_differs_most_from_m3plus']}**")
    A(f"- most affected by missing second-zone: **{cs['lottery_most_affected_by_missing_second_zone']}**")
    A(f"- {cs['big_runner_note']}")
    A(f"- {cs['power_runner_note']}")
    A(f"- {cs['daily539_note']}")
    A("")
    A("## Limitations")
    A("")
    for lim in result["limitations"]:
        A(f"- {lim}")
    A("")
    A("## Next recommended research step")
    A("")
    A(result["next_recommended_research_step"])
    return "\n".join(lines)


def write_artifacts(result: dict, out_json: str, out_md: str) -> None:
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    with open(out_md, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(result))
        fh.write("\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="P281A read-only cross-lottery prize-aware success-definition "
                    "verification + inferential validation (windows 100/500/1500)")
    parser.add_argument("--db", default=CANONICAL_DB_PATH,
                        help="path to the canonical SQLite DB (opened mode=ro)")
    parser.add_argument("--p267c", default=P267C_JSON_PATH)
    parser.add_argument("--p271a", default=P271A_JSON_PATH)
    parser.add_argument("--scorer-src", default=P271C_SOURCE_PATH)
    parser.add_argument("--adapter-src", default=P271E_SOURCE_PATH)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--print-only", action="store_true",
                        help="compute and print summary without writing artifacts")
    args = parser.parse_args(argv)

    result = build_result(db_path=args.db, p267c_path=args.p267c,
                          p271a_path=args.p271a, scorer_path=args.scorer_src,
                          adapter_path=args.adapter_src)
    if not args.print_only:
        write_artifacts(result, args.out_json, args.out_md)
    print(json.dumps({
        "task_id": TASK_ID,
        "final_classification": result["final_classification"],
        "analytical_outcome": result["analytical_outcome"],
        "verdict_counts": result["verdict_counts"],
        "frozen_strategy_cell_count": result["meta"]["frozen_strategy_cell_count"],
        "correction_family_size_m": CORRECTION_FAMILY_M,
        "evaluable_tested_cells_windows": result["correction"]["evaluable_tested_cells_windows"],
        "any_survives_bonferroni": result["correction"]["any_cell_survives_bonferroni"],
        "canonical_payload_digest": result["canonical_payload_digest"],
        "out_json": None if args.print_only else args.out_json,
        "out_md": None if args.print_only else args.out_md,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
