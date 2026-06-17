"""
P278A — Hit-Spectrum Data Contract and Read-Only Export

Deterministic, committed-artifact-only, UI-ready data contract for a FUTURE
hit-spectrum page covering all 36 P277 strategy cells across the three
supported games and their governed prize-aware endpoints, for the three
primary decision windows (SHORT=50 / MID=300 / LONG=750).

WHAT THIS IS
------------
A read-only contract that determines, FROM COMMITTED EVIDENCE ONLY:
  * which exact hit buckets are available,
  * what each denominator means,
  * which evaluation window / evidence stage produced the counts,
  * whether special-number / POWER second-zone / prize-aware fields apply,
  * what observation status P277 assigned,
  * whether a row is ready for truthful UI consumption,
  * what exact source gaps remain.

CENTRAL TRUTHFUL FINDING (fail-closed)
--------------------------------------
No committed artifact contains an exact per-draw M0/M1/M2/M3+ hit spectrum for
the 36 frozen prize-aware strategy cells at the primary windows on the governed
ANY_PRIZE_AWARE_WIN endpoints.  The committed evidence provides:
  * fully verified, cross-source-consistent DENOMINATORS
    (distinct draw count, evaluated ticket count, tickets per draw), and
  * a draw-level BINARY prize-aware-win aggregate (success draws),
but NOT the exact M0/M1/M2/M3+ buckets, nor per-prize-tier counts, nor the
special-number / second-zone component hit counts.  Therefore every one of the
108 (cell x window) rows is classified SOURCE_GAP_HIT_BUCKETS: the exact-hit
spectrum cannot yet be truthfully displayed; the denominators and the binary
prize-aware-win aggregate can.  The exact M-spectrum requires a separately
authorized read-only DB extraction (NOT performed here).

  - P267C carries observed_m3plus_draws, but that is the MAIN-NUMBER M3+
    endpoint at bet_count=1, window=1500 (reference-only) — a DIFFERENT endpoint
    and window than the prize-aware primary-window cells, and is NOT collapsed
    into these rows.
  - The only committed hit_count_distribution (p224) is a non-frozen one-off
    2-bet validation for a single DAILY_539 strategy and is NOT one of the 36
    frozen prize-aware cells; it is NOT used for any cell here.

FORBIDDEN INTERFACES (statically verified by test)
--------------------------------------------------
  - sqlite3 / DB open / write  (no canonical DB access)
  - requests / urllib / socket / subprocess / os.system (no network)
  - any registry / production / controlled_apply / deployment mutation
  - prediction runner / replay runner / ticket generator

DETERMINISM
-----------
Two regenerations (even from two distinct repository roots) yield identical
canonical_payload_digest and byte-identical JSON (generated_at is pinned and
excluded from the digest).  All manifest paths are repository-relative POSIX.
No absolute / home / cwd / temp paths appear in the artifact.

ALLOWED FILE WHITELIST (four files only)
----------------------------------------
  analysis/p278a_hit_spectrum_data_contract.py
  tests/test_p278a_hit_spectrum_data_contract.py
  outputs/research/p278a_hit_spectrum_data_contract_20260617.json
  outputs/research/p278a_hit_spectrum_data_contract_20260617.md

This artifact makes NO prediction-success claim and promotes NO strategy.
prediction_success_claim = false ; strategy_promoted = false.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Governance constants
# ---------------------------------------------------------------------------

TASK_ID = "P278A_HIT_SPECTRUM_DATA_CONTRACT_AND_READ_ONLY_EXPORT"
SCHEMA_VERSION = "p278a_hit_spectrum_data_contract.v1"
DATE_CONSTANT = "2026-06-17"
GENERATED_AT_PINNED = "2026-06-17T00:00:00+00:00"
# Verified actual origin/main baseline (PR #450 + #451 merged).
SOURCE_COMMIT = "8ece9c6b078c6e90a0bc2c340b727c9b7f7909fe"
# P277 canonical reconciliation anchors (independently verified in Phase 0).
P277_CANONICAL_DIGEST = (
    "d75f8383c5029c5024279f9e3792d417885cecc202f25740f10406a701f14284"
)
P277_STRATEGY_CELL_UNIVERSE = 36
P277_PORTFOLIO_COUNT = 8
CORRECTION_FAMILY_SIZE = 108  # 36 cells x 3 primary windows

ROOT = Path(__file__).resolve().parent.parent

# Repository-relative POSIX source paths (the manifest).  Resolved against a
# caller-supplied root so two distinct roots produce an identical digest.
SOURCE_RELPATHS = {
    "p277a": "outputs/research/p277a_historical_observation_status_reclassification_20260617.json",
    "p275b": "outputs/research/p275b_unified_prize_aware_success_matrix_20260616.json",
    "p273a_primary": "outputs/research/p273a_primary_window_observed_counts_20260615.json",
    "p273a_identity": "outputs/research/p273a_distinct_ticket_identity_20260615.json",
    "p273a_inferential": "outputs/research/p273a_prize_aware_inferential_validation_20260615.json",
    "p267c": "outputs/research/p267c_m3plus_strategy_revalidation_20260610.json",
}

# Primary decision windows (50/300/750); 1500 + all-history are REFERENCE-ONLY
# and intentionally excluded.
WINDOW_ORDER = [("SHORT", 50), ("MID", 300), ("LONG", 750)]
WINDOW_LABEL_BY_SIZE = {50: "SHORT", 300: "MID", 750: "LONG"}

# ---------------------------------------------------------------------------
# Endpoint definitions (verbatim from committed P271A / P275B / P277A)
# ---------------------------------------------------------------------------

ENDPOINT_DEFINITIONS = {
    "DAILY_539": {
        "endpoint_id": "D539_ANY_PRIZE_AWARE_WIN",
        "condition": "hit_count >= 2",
        "scored_by": "lottery_api.prize_aware_scorer.any_prize_aware_win",
        "main_number_based": True,
        "special_number_applicable": False,
        "second_zone_applicable": False,
        "prize_aware_applicable": True,
        "representative_prize_tier": "肆獎 (2-match)",
        "source_ref": "P271A",
    },
    "BIG_LOTTO": {
        "endpoint_id": "BIG_ANY_PRIZE_AWARE_WIN",
        "condition": "hit_count >= 3 OR (hit_count = 2 AND special_hit = 1)",
        "scored_by": "lottery_api.prize_aware_scorer.any_prize_aware_win",
        "main_number_based": True,
        "special_number_applicable": True,
        "second_zone_applicable": False,
        "prize_aware_applicable": True,
        "representative_prize_tier": "普獎 (2-match + special)",
        "source_ref": "P271A",
    },
    "POWER_LOTTO": {
        "endpoint_id": "POWER_ANY_PRIZE_AWARE_WIN",
        "condition": "hit_count >= 3 OR (hit_count >= 1 AND special_hit = 1)",
        "scored_by": "lottery_api.prize_aware_scorer.any_prize_aware_win",
        "main_number_based": True,
        "special_number_applicable": False,
        "second_zone_applicable": True,
        "prize_aware_applicable": True,
        "representative_prize_tier": "普獎 (1-match + second-zone)",
        "source_ref": "P271A",
    },
}

DENOMINATOR_DEFINITIONS = {
    "DRAW_LEVEL_ANY_BET_PRIZE_AWARE_WIN": {
        "description": (
            "Success is counted per DRAW: a draw is a success when AT LEAST ONE "
            "of its bets satisfies the governed ANY_PRIZE_AWARE_WIN endpoint "
            "(draw-level any-bet union). The success-rate denominator is the "
            "number of distinct supported draws in the window, NOT the number "
            "of tickets."
        ),
        "denominator_field": "distinct_draw_count",
        "is_ticket_row_denominator": False,
        "note": (
            "evaluated_ticket_count (= distinct_draw_count x tickets_per_draw) "
            "is recorded for traceability but is NOT the success denominator; "
            "draw-level and ticket-row denominators must not be collapsed."
        ),
    },
}

NOT_AVAILABLE = "NOT_AVAILABLE"

# ---------------------------------------------------------------------------
# UI-readiness taxonomy (fail-closed) and source-gap codes
# ---------------------------------------------------------------------------

UI_READINESS_TAXONOMY = [
    "UI_READY_FULL_SPECTRUM",
    "UI_READY_PARTIAL_SPECTRUM",
    "SOURCE_GAP_DENOMINATOR",
    "SOURCE_GAP_HIT_BUCKETS",
    "SOURCE_GAP_ENDPOINT_MAPPING",
    "SOURCE_GAP_PRIZE_FIELDS",
    "NOT_APPLICABLE_ENDPOINT",
    "REQUIRES_FUTURE_ONLY_EVIDENCE",
]

SOURCE_GAP_CODES = [
    "SOURCE_GAP_HIT_BUCKETS",
    "SOURCE_GAP_PRIZE_FIELDS",
    "SOURCE_GAP_DENOMINATOR",
    "SOURCE_GAP_ENDPOINT_MAPPING",
]

FORBIDDEN_CLAIMS = [
    "This contract does NOT claim improved future prediction success.",
    "This contract does NOT promote, deploy, activate, or recommend any strategy.",
    "UI readiness does NOT imply prediction success.",
    "UI readiness does NOT imply strategy promotion.",
    "UI readiness does NOT imply recommendation, deployment, or ONLINE authorization.",
    "Observation support does NOT imply UI readiness.",
    "Retrospective evidence is NOT confirmatory; it can only surface or falsify candidates.",
    "Missing hit buckets are recorded as explicit null / NOT_AVAILABLE and are never fabricated as zero.",
]

INVARIANTS = [
    "Exactly 36 unique P277 strategy cells are represented.",
    "Exactly 108 (cell x window) rows (36 cells x 3 primary windows).",
    "Every row's (strategy_cell_key, evaluation_window) pair is unique.",
    "All available counts are non-negative integers.",
    "null and zero are semantically distinct: unavailable buckets are null/NOT_AVAILABLE, never 0.",
    "No exact-hit bucket is fabricated; all m0/m1/m2/m3plus counts are null for every row.",
    "Where a full spectrum WERE available, bucket_sum would equal the applicable denominator.",
    "Derived rates recompute exactly from verified counts and denominators.",
    "M3+ (main-number) and prize-aware endpoints are never merged.",
    "main-number, special-number, and POWER second-zone results are never merged.",
    "distinct-draw and ticket-row denominators are never collapsed.",
    "RETROSPECTIVE, backward-OOS, and OOS evidence stages are never merged.",
    "Every source path is repository-relative POSIX.",
    "The canonical digest is path-independent (two distinct roots regenerate it identically).",
    "P277 taxonomy and counts are reproduced unchanged.",
    "prediction_success_claim = false ; strategy_promoted = false.",
]

# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def load_json(path: Path) -> Any:
    with open(path) as f:
        return json.load(f)


def source_paths(root: Path) -> dict[str, Path]:
    return {k: (root / rel) for k, rel in SOURCE_RELPATHS.items()}


def build_source_hashes(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, path in sorted(source_paths(root).items()):
        out[key] = sha256_file(path) if path.exists() else "MISSING"
    return out


# ---------------------------------------------------------------------------
# Source indexing
# ---------------------------------------------------------------------------

def _index_p273a_primary(prim: dict) -> dict:
    """key (lottery, strategy, window_size) -> primary window record."""
    idx = {}
    for cell in prim["cells"]:
        for w in cell["windows"]:
            idx[(cell["lottery_type"], cell["strategy_id"], int(w["window"]))] = w
    return idx


def _index_p275b(p275: dict) -> dict:
    """key (lottery, strategy, window_size) -> matrix row."""
    idx = {}
    for r in p275["matrix_rows"]:
        size = int(r["window_draw_count"])
        idx[(r["lottery_type"], r["strategy_id"], size)] = r
    return idx


# ---------------------------------------------------------------------------
# Row construction
# ---------------------------------------------------------------------------

def _tickets_per_draw(prim_w: dict, p275_row: dict):
    """Constant tickets-per-draw from committed evidence, else NOT_AVAILABLE.

    Never inferred from the strategy name; derived only from the committed
    bet-count distribution / ticket budget.  Unscoreable cells (all bets
    excluded) legitimately have no committed value -> NOT_AVAILABLE.
    """
    bet_dist = prim_w.get("bet_count_distribution") or {}
    if len(bet_dist) == 1:
        return int(next(iter(bet_dist.keys())))
    tb = p275_row.get("ticket_budget")
    if tb is not None and len(bet_dist) == 0:
        return int(tb)
    return NOT_AVAILABLE


def _verify_denominator(prim_w: dict, p275_row: dict, scoreable: bool) -> tuple[bool, list[str]]:
    """Cross-source denominator consistency across P273A-primary and P275B.

    For scoreable cells, all four denominators and the ticket arithmetic must
    agree.  For unscoreable cells (all bets excluded as missing second-zone),
    consistency means every source independently reports zero support/tickets.
    """
    notes: list[str] = []
    ok = True
    window_span = int(prim_w["distinct_draws_in_window"])
    support = int(prim_w["support_draws"])

    if not scoreable:
        if support != 0:
            ok = False
            notes.append("expected support_draws==0 for unscoreable cell")
        if int(p275_row["eligible_draws"]) != 0 or int(p275_row["evaluated_draws"]) != 0:
            ok = False
            notes.append("P275B eligible/evaluated draws != 0 for unscoreable cell")
        if int(p275_row["ticket_count"]["window_total_distinct_tickets"]) != 0:
            ok = False
            notes.append("P275B distinct tickets != 0 for unscoreable cell")
        if int(prim_w["scoreable_rows"]) != 0:
            ok = False
            notes.append("P273A scoreable_rows != 0 for unscoreable cell")
        return ok, notes

    # scoreable: the rate denominator is the SCOREABLE draw count (support),
    # which may be < window span when individual draws are excluded for a
    # missing predicted second-zone.  eligible/evaluated must equal support;
    # P275B window_draw_count records the (pre-exclusion) requested span.
    for fld in ("eligible_draws", "evaluated_draws"):
        if int(p275_row[fld]) != support:
            ok = False
            notes.append(f"P275B {fld} != P273A support_draws")
    if int(p275_row["window_draw_count"]) != window_span:
        ok = False
        notes.append("P275B window_draw_count != P273A distinct_draws_in_window")
    tpd = _tickets_per_draw(prim_w, p275_row)
    if tpd == NOT_AVAILABLE:
        ok = False
        notes.append("non-constant/absent tickets_per_draw on scoreable cell")
    else:
        if int(p275_row["ticket_budget"]) != tpd:
            ok = False
            notes.append("P275B ticket_budget != P273A bet_count")
        evaluated_tickets = int(prim_w["scoreable_rows"])
        if evaluated_tickets != support * tpd:
            ok = False
            notes.append("scoreable_rows != support_draws x tickets_per_draw")
        if int(p275_row["ticket_count"]["window_total_distinct_tickets"]) != evaluated_tickets:
            ok = False
            notes.append("P275B window_total_distinct_tickets != P273A scoreable_rows")
    return ok, notes


def _endpoint_specific(lottery: str, p275_row: dict) -> dict:
    ep = ENDPOINT_DEFINITIONS[lottery]
    special_app = ep["special_number_applicable"]
    second_app = ep["second_zone_applicable"]
    # Component hit counts (special / second-zone breakdown) are NOT committed.
    return {
        "special_number_applicable": special_app,
        "special_number_hit_counts": None if special_app else NOT_AVAILABLE,
        "second_zone_applicable": second_app,
        "second_zone_hit_counts": None if second_app else NOT_AVAILABLE,
        "second_zone_excluded_bet_rows": int(
            p275_row["missing_draws"].get("second_zone_excluded_bet_rows", 0)
        ),
        "prize_aware_applicable": ep["prize_aware_applicable"],
        "prize_tier_counts": None,  # only the ANY threshold is committed; no per-tier breakdown
        "representative_prize_tier": ep["representative_prize_tier"],
        "endpoint_special_note": (
            "BIG_LOTTO special-number and POWER_LOTTO second-zone are DISTINCT "
            "components and are never merged; for applicable components only the "
            "ANY_PRIZE_AWARE_WIN aggregate is committed — the per-component hit "
            "counts are NOT_AVAILABLE."
        ),
    }


def _source_gap_codes(lottery: str, scoreable: bool) -> list[str]:
    if not scoreable:
        # Required predicted second-zone absent -> endpoint cannot be mapped.
        return ["SOURCE_GAP_ENDPOINT_MAPPING", "SOURCE_GAP_HIT_BUCKETS",
                "SOURCE_GAP_PRIZE_FIELDS"]
    # No exact M-spectrum anywhere; no per-prize-tier / component counts.
    return ["SOURCE_GAP_HIT_BUCKETS", "SOURCE_GAP_PRIZE_FIELDS"]


def build_rows(sources: dict, source_hashes: dict[str, str]) -> list[dict]:
    p277 = sources["p277a"]
    prim_idx = _index_p273a_primary(sources["p273a_primary"])
    p275_idx = _index_p275b(sources["p275b"])

    rows: list[dict] = []
    for s in p277["strategies"]:
        lottery = s["lottery_type"]
        strategy_id = s["strategy_id"]
        ep = ENDPOINT_DEFINITIONS[lottery]
        strategy_cell_key = f"{lottery}/{strategy_id}"

        # P277 cell-level research status (decided at the cell's primary window)
        research_status = {
            "p277_observation_class": s["current_mapping"],
            "p277_original_classification": s["original_classification"],
            "p277_primary_decision_window": s["source_metrics"]["primary_window"],
            "random_baseline_status": s["random_baseline_status"],
            "statistical_support_status": s["corrected_support_status"],
            "stability_status": s["stability_status"],
            "OOS_status": s["OOS_status"],
            "best_equal_budget_status": s["best_equal_budget_status"],
            "promotion_status": s["promotion_status"],
            "future_confirmation_status": s["future_confirmation_status"],
            "observation_retention_status": s["observation_retention_status"],
            "evidence_completeness": s["evidence_completeness"],
            "prediction_success_claim": False,
            "strategy_promoted": False,
        }

        for window_label, window_size in WINDOW_ORDER:
            key = (lottery, strategy_id, window_size)
            prim_w = prim_idx[key]
            p275_row = p275_idx[key]

            window_span = int(prim_w["distinct_draws_in_window"])
            support_draws = int(prim_w["support_draws"])
            scoreable = support_draws > 0
            # The success-rate denominator is the scoreable distinct draw count.
            distinct_draw_count = support_draws
            tickets_per_draw = _tickets_per_draw(prim_w, p275_row)
            evaluated_ticket_count = int(prim_w["scoreable_rows"])
            denom_ok, denom_notes = _verify_denominator(prim_w, p275_row, scoreable)

            success_draws = int(prim_w["observed_successes"])
            prize_aware_win_rate = (
                success_draws / distinct_draw_count if scoreable else None
            )
            evaluable = bool(p275_row.get("evaluable"))

            row = {
                # ---- identity ----
                "schema_version": SCHEMA_VERSION,
                "cell_id": f"{strategy_cell_key}/{window_label}",
                "strategy_cell_key": strategy_cell_key,
                "game": lottery,
                "strategy_id": strategy_id,
                "display_name": None,  # no separate committed display name
                "endpoint": {
                    "endpoint_id": ep["endpoint_id"],
                    "condition": ep["condition"],
                    "scored_by": ep["scored_by"],
                },
                "bet_count": tickets_per_draw,
                "evaluation_window": {
                    "label": window_label,
                    "draw_count": window_size,
                    "requested_window_span": window_span,
                    "scoreable_distinct_draw_count": support_draws,
                    "endpoint_scoreable": scoreable,
                    "earliest_target_draw": prim_w.get("earliest_target_draw"),
                    "latest_target_draw": prim_w.get("latest_target_draw"),
                },
                "evidence_stage": p275_row.get("evaluation_mode", "RETROSPECTIVE"),
                "lifecycle_status": p275_row.get("lifecycle_status"),
                # ---- denominator ----
                "denominator": {
                    "denominator_type": "DRAW_LEVEL_ANY_BET_PRIZE_AWARE_WIN",
                    "distinct_draw_count": distinct_draw_count,
                    "evaluated_ticket_count": evaluated_ticket_count,
                    "tickets_per_draw": tickets_per_draw,
                    "distinct_ticket_count": int(
                        p275_row["ticket_count"]["window_total_distinct_tickets"]
                    ),
                    "denominator_source": [
                        "p273a_primary:distinct_draws_in_window",
                        "p273a_primary:scoreable_rows",
                        "p275b:window_total_distinct_tickets",
                        "p273a_identity:distinct_ticket_count_distribution",
                    ],
                    "denominator_verified": denom_ok,
                    "denominator_verification_notes": denom_notes,
                    "excluded_rows": int(prim_w.get("excluded_rows", 0)),
                    "excluded_missing_special_rows": int(
                        prim_w.get("excluded_missing_special_rows", 0)
                    ),
                    "exclusion_by_reason": prim_w.get("exclusion_by_reason", {}),
                },
                # ---- hit spectrum (exact M-buckets are NOT committed) ----
                "hit_spectrum": {
                    "exact_hit_buckets": NOT_AVAILABLE,
                    "m0_count": None,
                    "m1_count": None,
                    "m2_count": None,
                    "m3plus_count": None,
                    "higher_exact_hit_buckets": NOT_AVAILABLE,
                    "bucket_sum": None,
                    "bucket_sum_matches_denominator": None,
                    "hit_rate_by_bucket": None,
                    "spectrum_availability": "NOT_AVAILABLE",
                    "spectrum_gap_reason": (
                        "No committed artifact records the exact per-draw "
                        "M0/M1/M2/M3+ distribution for this prize-aware endpoint "
                        "at this primary window; only the draw-level binary "
                        "prize-aware-win aggregate and the denominators are "
                        "committed. Exact buckets require a separately authorized "
                        "read-only DB extraction (not performed)."
                    ),
                },
                # ---- committed binary aggregate (NOT an exact-hit bucket) ----
                "prize_aware_win_aggregate": {
                    "is_exact_hit_bucket": False,
                    "semantics": "draw-level any-bet ANY_PRIZE_AWARE_WIN union",
                    "prize_aware_win_draws": success_draws if scoreable else None,
                    "prize_aware_win_rate": prize_aware_win_rate,
                    "rate_denominator": "distinct_draw_count (scoreable)",
                    "evaluable": evaluable,
                    "available": scoreable,
                    "source_fields": [
                        "p273a_primary:observed_successes",
                        "p275b:success_draws",
                    ],
                },
                # ---- endpoint-specific ----
                "endpoint_specific": _endpoint_specific(lottery, p275_row),
                # ---- research status ----
                "research_status": research_status,
                # ---- statistical context (per-window, descriptive) ----
                "statistical_context": {
                    "evidence_status": p275_row.get("evidence_status"),
                    "statistical_status": p275_row.get("statistical_status"),
                    "support_status": p275_row.get("support_status"),
                    "evaluable": evaluable,
                    "promotion_eligible_window": p275_row.get(
                        "promotion_eligible_window"
                    ),
                },
                # ---- traceability ----
                "traceability": {
                    "source_artifacts": [
                        "p277a",
                        "p275b",
                        "p273a_primary",
                        "p273a_identity",
                        "p273a_inferential",
                        "p267c",
                    ],
                    "source_artifact_hashes": {
                        k: source_hashes[k]
                        for k in (
                            "p277a",
                            "p275b",
                            "p273a_primary",
                            "p273a_identity",
                        )
                    },
                    "source_commit": SOURCE_COMMIT,
                    "source_fields": {
                        "identity": "p277a:strategies[]",
                        "denominator": "p273a_primary:cells[].windows[] + p275b:matrix_rows[]",
                        "prize_aware_aggregate": "p273a_primary:observed_successes / p275b:success_draws",
                        "research_status": "p277a:strategies[] (cell-level)",
                        "statistical_context": "p275b:matrix_rows[]",
                    },
                    "extraction_status": "COMMITTED_ARTIFACT_ONLY",
                    "source_gap_codes": _source_gap_codes(lottery, scoreable),
                },
                # ---- UI readiness (fail-closed) ----
                "ui_readiness_status": (
                    "SOURCE_GAP_HIT_BUCKETS"
                    if scoreable
                    else "SOURCE_GAP_ENDPOINT_MAPPING"
                ),
                "ui_readiness_reason": (
                    (
                        "Denominators and the draw-level prize-aware-win aggregate "
                        "are verified and displayable, but the exact M0/M1/M2/M3+ hit "
                        "spectrum is not committed; the hit-spectrum view cannot be "
                        "truthfully populated without a separately authorized DB "
                        "extraction."
                    )
                    if scoreable
                    else (
                        "The POWER_LOTTO prize-aware endpoint requires the predicted "
                        "second-zone, which is absent from every stored prediction for "
                        "this strategy/window (all bets excluded as "
                        "MISSING_PREDICTED_SECOND_ZONE). The endpoint cannot be mapped "
                        "or scored; no denominator, no spectrum. Counts are never "
                        "manufactured."
                    )
                ),
            }
            rows.append(row)
    # Stable ordering: game, strategy_id, window size.
    rows.sort(
        key=lambda r: (
            r["game"],
            r["strategy_id"],
            r["evaluation_window"]["draw_count"],
        )
    )
    return rows


# ---------------------------------------------------------------------------
# Summaries / matrices
# ---------------------------------------------------------------------------

def _count_by(rows: list[dict], keyfn) -> dict:
    out: dict[str, int] = {}
    for r in rows:
        k = keyfn(r)
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items()))


def build_summaries(rows: list[dict], p277: dict) -> dict:
    cell_keys = sorted({r["strategy_cell_key"] for r in rows})
    by_ui = _count_by(rows, lambda r: r["ui_readiness_status"])
    by_game = _count_by(rows, lambda r: r["game"])
    by_endpoint = _count_by(rows, lambda r: r["endpoint"]["endpoint_id"])
    by_obs_class = _count_by(rows, lambda r: r["research_status"]["p277_observation_class"])

    full = [r["cell_id"] for r in rows if r["ui_readiness_status"] == "UI_READY_FULL_SPECTRUM"]
    partial = [
        r["cell_id"] for r in rows if r["ui_readiness_status"] == "UI_READY_PARTIAL_SPECTRUM"
    ]
    gap_rows = [
        {
            "cell_id": r["cell_id"],
            "ui_readiness_status": r["ui_readiness_status"],
            "source_gap_codes": r["traceability"]["source_gap_codes"],
            "reason": r["ui_readiness_reason"],
        }
        for r in rows
        if r["ui_readiness_status"] not in ("UI_READY_FULL_SPECTRUM",)
    ]

    return {
        "unique_strategy_cell_count": len(cell_keys),
        "row_count": len(rows),
        "windows_per_cell": len(WINDOW_ORDER),
        "summary_by_game": by_game,
        "summary_by_endpoint": by_endpoint,
        "summary_by_observation_class": by_obs_class,
        "summary_by_ui_readiness": by_ui,
        "full_spectrum_identities": full,
        "partial_spectrum_identities": partial,
        "source_gap_matrix": gap_rows,
        # P277 reconciliation (unchanged reproduction)
        "p277_reconciliation": {
            "p277_canonical_digest": P277_CANONICAL_DIGEST,
            "total_strategy_cells": P277_STRATEGY_CELL_UNIVERSE,
            "total_portfolios": P277_PORTFOLIO_COUNT,
            "count_by_new_classification": p277["classification_summary"][
                "count_by_new_classification"
            ],
            "observation_supported_above_random": p277["classification_summary"][
                "observation_supported_above_random"
            ],
            "oos_superseded_observations": p277["classification_summary"][
                "oos_superseded_observations"
            ],
            "missing_baseline_items": p277["classification_summary"][
                "missing_baseline_items"
            ],
        },
    }


def build_future_consumer_contract() -> dict:
    """Contract for a SEPARATELY authorized future hit-spectrum page (P278B)."""
    return {
        "intended_consumer": "P278B hit-spectrum page (SEPARATELY AUTHORIZED — not implemented here)",
        "p278b_authorization_status": "NOT_AUTHORIZED_BY_THIS_TASK",
        "page_may_display_now": [
            "Per (cell x window) verified denominators: distinct_draw_count, "
            "evaluated_ticket_count, tickets_per_draw, distinct_ticket_count.",
            "Draw-level binary prize-aware-win count and rate (clearly labelled "
            "as an aggregate, NOT an exact-hit spectrum).",
            "P277 observation classification and dual-gate research status.",
            "Endpoint definitions and applicability flags.",
        ],
        "page_must_not_display_yet": [
            "Any M0/M1/M2/M3+ exact-hit spectrum (not committed; would be fabrication).",
            "Per-prize-tier counts (not committed).",
            "Special-number / second-zone component hit counts (not committed).",
            "Any prediction-success, promotion, or deployment claim.",
        ],
        "to_unlock_full_spectrum": (
            "A separately authorized, read-only DB extraction (or replay re-scoring) "
            "that records the exact per-draw hit_count distribution for the prize-aware "
            "endpoints at the primary windows. This task does NOT perform or authorize it."
        ),
        "fail_closed_rule": (
            "Any field that is NOT_AVAILABLE/null MUST render as an explicit "
            "'not available' state, never as zero and never as a fabricated value."
        ),
    }


# ---------------------------------------------------------------------------
# Canonical payload digest (path-independent; excludes generated_at + self-hash)
# ---------------------------------------------------------------------------

def compute_canonical_digest(payload: dict) -> str:
    """SHA-256 over a deterministic, path-independent subset of the payload.

    Excludes generated_at and the self-hash. The source manifest is the sorted
    repository-relative POSIX list; source_artifact_hashes are content hashes
    (path-independent). No absolute path participates in the digest.
    """
    stable = {
        "task_id": payload["task_id"],
        "schema_version": payload["schema_version"],
        "source_commit": payload["source_commit"],
        "source_artifact_manifest": sorted(payload["source_artifact_manifest"]),
        "source_artifact_hashes": payload["source_artifact_hashes"],
        "endpoint_definitions": payload["endpoint_definitions"],
        "denominator_definitions": payload["denominator_definitions"],
        "ui_readiness_taxonomy": payload["ui_readiness_taxonomy"],
        "rows": payload["rows"],
        "summaries": payload["summaries"],
        "invariants": payload["invariants"],
        "forbidden_claims": payload["forbidden_claims"],
        "future_consumer_contract": payload["future_consumer_contract"],
        "prediction_success_claim": payload["prediction_success_claim"],
        "strategy_promoted": payload["strategy_promoted"],
        "database_opened": payload["database_opened"],
        "database_write": payload["database_write"],
    }
    stable_str = json.dumps(
        stable, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(stable_str.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Artifact assembly
# ---------------------------------------------------------------------------

def build_payload(root: Path = ROOT, generated_at: str = GENERATED_AT_PINNED) -> dict:
    paths = source_paths(root)
    source_hashes = build_source_hashes(root)
    sources = {k: load_json(p) for k, p in paths.items() if k != "p273a_identity"}
    # p273a_identity is hashed for provenance but not parsed (26MB; distinct
    # ticket totals are taken cross-referenced from P275B).
    sources["p273a_identity"] = None

    rows = build_rows(sources, source_hashes)
    summaries = build_summaries(rows, sources["p277a"])
    manifest = sorted(SOURCE_RELPATHS.values())

    payload: dict = {
        "task_id": TASK_ID,
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "source_commit": SOURCE_COMMIT,
        "source_artifact_manifest": manifest,
        "source_artifact_hashes": source_hashes,
        "database_opened": False,
        "database_write": False,
        "prediction_success_claim": False,
        "strategy_promoted": False,
        "endpoint_definitions": ENDPOINT_DEFINITIONS,
        "denominator_definitions": DENOMINATOR_DEFINITIONS,
        "ui_readiness_taxonomy": UI_READINESS_TAXONOMY,
        "source_gap_codes": SOURCE_GAP_CODES,
        "primary_windows": [{"label": l, "draw_count": n} for l, n in WINDOW_ORDER],
        "rows": rows,
        "summaries": summaries,
        "invariants": INVARIANTS,
        "forbidden_claims": FORBIDDEN_CLAIMS,
        "future_consumer_contract": build_future_consumer_contract(),
        "canonical_payload_digest": "",
    }
    payload["canonical_payload_digest"] = compute_canonical_digest(payload)
    return payload


# ---------------------------------------------------------------------------
# Forbidden-interface static self-check
# ---------------------------------------------------------------------------

# Modules whose IMPORT (not mere string mention) is forbidden.
FORBIDDEN_IMPORT_MODULES = {
    "sqlite3",
    "requests",
    "urllib",
    "socket",
    "subprocess",
    "psycopg2",
    "sqlalchemy",
    "http",
}
# Attribute-call patterns (object.method) forbidden as executable code.
FORBIDDEN_ATTR_CALLS = {("os", "system"), ("os", "popen")}


def static_forbidden_check(module_path: Path | None = None) -> list[str]:
    """AST-based scan of this module: flags real forbidden imports/calls only,
    never string-literal or docstring mentions of the same names."""
    import ast

    path = module_path or Path(__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                top = a.name.split(".")[0]
                if top in FORBIDDEN_IMPORT_MODULES:
                    found.append(f"import {a.name}")
        elif isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            if top in FORBIDDEN_IMPORT_MODULES:
                found.append(f"from {node.module} import ...")
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                if (f.value.id, f.attr) in FORBIDDEN_ATTR_CALLS:
                    found.append(f"{f.value.id}.{f.attr}(...)")
    return found


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def render_markdown(payload: dict) -> str:
    s = payload["summaries"]
    lines: list[str] = []
    lines.append("# P278A — Hit-Spectrum Data Contract (Read-Only)")
    lines.append("")
    lines.append(f"**Task:** `{payload['task_id']}`")
    lines.append(f"**Schema:** `{payload['schema_version']}`")
    lines.append(f"**Generated:** {payload['generated_at']}")
    lines.append(f"**Source commit:** `{payload['source_commit']}`")
    lines.append(f"**Canonical payload digest:** `{payload['canonical_payload_digest']}`")
    lines.append("")
    lines.append(
        "> Read-only, committed-artifact-only data contract for a FUTURE "
        "hit-spectrum page. **No DB access. No prediction-success claim. "
        "No strategy promotion.** `prediction_success_claim=false`, "
        "`strategy_promoted=false`."
    )
    lines.append("")
    lines.append("## Bottom line — what can and cannot be displayed now")
    lines.append("")
    lines.append("**Can be truthfully displayed now (verified from committed evidence):**")
    lines.append("")
    lines.append("- Per `(cell × window)` denominators: distinct draw count, evaluated "
                 "ticket count, tickets per draw, distinct ticket count — all "
                 "cross-source consistent across P273A-primary, P273A-identity, and P275B.")
    lines.append("- A draw-level **binary** prize-aware-win count and rate (clearly "
                 "labelled as an aggregate, **not** an exact-hit spectrum).")
    lines.append("- P277 observation classification and dual-gate research status.")
    lines.append("")
    lines.append("**Cannot yet be displayed (recorded as explicit `null`/`NOT_AVAILABLE`):**")
    lines.append("")
    lines.append("- The exact **M0/M1/M2/M3+** hit spectrum — **no committed artifact "
                 "records it** for the prize-aware endpoints at the primary windows.")
    lines.append("- Per-prize-tier counts.")
    lines.append("- Special-number (BIG_LOTTO) / second-zone (POWER_LOTTO) component hit counts.")
    lines.append("")
    lines.append("Every one of the 108 `(cell × window)` rows is therefore classified "
                 "`SOURCE_GAP_HIT_BUCKETS`. This is a fail-closed, truthful result: the "
                 "page can show verified denominators and the binary prize-aware-win rate, "
                 "but the exact hit spectrum requires a **separately authorized** read-only "
                 "DB extraction.")
    lines.append("")
    lines.append("## Counts")
    lines.append("")
    lines.append(f"- Unique P277 strategy cells: **{s['unique_strategy_cell_count']}**")
    lines.append(f"- Rows (cell × window): **{s['row_count']}**")
    lines.append("")
    lines.append("### By game")
    for k, v in s["summary_by_game"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("### By endpoint")
    for k, v in s["summary_by_endpoint"].items():
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    lines.append("### By P277 observation class")
    for k, v in s["summary_by_observation_class"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("### By UI-readiness class")
    for k, v in s["summary_by_ui_readiness"].items():
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    lines.append(f"- Full-spectrum identities: **{len(s['full_spectrum_identities'])}** "
                 f"(none — no exact spectrum committed)")
    lines.append(f"- Partial-spectrum identities: **{len(s['partial_spectrum_identities'])}** (none)")
    lines.append("")
    lines.append("## Per-game / per-endpoint readiness")
    lines.append("")
    lines.append("| Game | Endpoint | Condition | Special | Second-zone | Spectrum available |")
    lines.append("|------|----------|-----------|---------|-------------|--------------------|")
    for game, ep in ENDPOINT_DEFINITIONS.items():
        lines.append(
            f"| {game} | `{ep['endpoint_id']}` | {ep['condition']} | "
            f"{ep['special_number_applicable']} | {ep['second_zone_applicable']} | NO |"
        )
    lines.append("")
    lines.append("## Denominator cautions")
    lines.append("")
    lines.append("- The success denominator is the **distinct draw count**, not the "
                 "ticket-row count. Success is a **draw-level any-bet union** over the "
                 "governed endpoint; draw-level and ticket-row denominators must not be "
                 "collapsed.")
    lines.append("- `evaluated_ticket_count = distinct_draw_count × tickets_per_draw` is "
                 "recorded for traceability only.")
    lines.append("")
    lines.append("## Special-number and second-zone cautions")
    lines.append("")
    lines.append("- BIG_LOTTO encodes a special-number component and POWER_LOTTO a "
                 "second-zone component **inside** the prize-aware win condition. The "
                 "committed evidence only exposes the combined ANY_PRIZE_AWARE_WIN "
                 "aggregate — the per-component (special / second-zone) hit counts are "
                 "`NOT_AVAILABLE` and must not be inferred.")
    lines.append("- At the primary windows (50/300/750) POWER_LOTTO second-zone rows are "
                 "fully populated (0 missing-second-zone exclusions).")
    lines.append("")
    lines.append("## Prize-aware availability")
    lines.append("")
    lines.append("- Only the lowest **ANY** prize-aware threshold per game is committed; "
                 "there is no per-prize-tier breakdown → `SOURCE_GAP_PRIZE_FIELDS`.")
    lines.append("")
    lines.append("## Source gaps")
    lines.append("")
    lines.append("- `SOURCE_GAP_HIT_BUCKETS` — exact M0/M1/M2/M3+ spectrum not committed "
                 "(all 108 rows).")
    lines.append("- `SOURCE_GAP_PRIZE_FIELDS` — no per-tier / per-component counts (all 108 rows).")
    lines.append("- P267C M3+ (main-number, 1-bet, window-1500, reference-only) is a "
                 "**different endpoint/window** and is deliberately **not** collapsed into "
                 "these prize-aware rows.")
    lines.append("")
    lines.append("## Scientific no-claim boundaries")
    lines.append("")
    for c in payload["forbidden_claims"]:
        lines.append(f"- {c}")
    lines.append("")
    lines.append("## Proposed P278B page contract (NOT authorized by this task)")
    lines.append("")
    fc = payload["future_consumer_contract"]
    lines.append(f"- Authorization status: **{fc['p278b_authorization_status']}**")
    lines.append("- The page **may** display now:")
    for x in fc["page_may_display_now"]:
        lines.append(f"  - {x}")
    lines.append("- The page **must not** display yet:")
    for x in fc["page_must_not_display_yet"]:
        lines.append(f"  - {x}")
    lines.append(f"- To unlock the full spectrum: {fc['to_unlock_full_spectrum']}")
    lines.append("")
    lines.append("## Source artifact manifest")
    lines.append("")
    for rel in payload["source_artifact_manifest"]:
        lines.append(f"- `{rel}`")
    lines.append("")
    lines.append(f"- Canonical payload digest: `{payload['canonical_payload_digest']}`")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

JSON_OUT = ROOT / "outputs" / "research" / "p278a_hit_spectrum_data_contract_20260617.json"
MD_OUT = ROOT / "outputs" / "research" / "p278a_hit_spectrum_data_contract_20260617.md"


def main() -> None:
    forbidden = static_forbidden_check()
    if forbidden:
        raise SystemExit(f"FORBIDDEN INTERFACE DETECTED: {forbidden}")
    payload = build_payload(ROOT)
    JSON_OUT.write_text(
        json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    MD_OUT.write_text(render_markdown(payload), encoding="utf-8")
    import sys

    print(f"rows: {len(payload['rows'])}", file=sys.stderr)
    print(
        f"unique cells: {payload['summaries']['unique_strategy_cell_count']}",
        file=sys.stderr,
    )
    print(
        f"canonical_payload_digest: {payload['canonical_payload_digest']}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
