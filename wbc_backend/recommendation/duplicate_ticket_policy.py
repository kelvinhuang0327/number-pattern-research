"""Local replay duplicate-ticket dry-run policy.

P206A is descriptive only.  It does not mutate recommendation rows, evaluator
state, leaderboard state, scheduler behavior, registries, databases, or live
paths.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from wbc_backend.recommendation.learning_outcome_join import (
    evaluate_learning_outcome_join,
    stable_game_identity,
)


UNGROUPABLE_MISSING_IDENTITY = "ungroupable_missing_identity"
UNGROUPABLE_MISSING_SELECTED_SIDE = "ungroupable_missing_selected_side"
UNGROUPABLE_MISSING_MARKET = "ungroupable_missing_market"
KEEP_FIRST_IN_DUPLICATE_SET = "keep_first_in_duplicate_set"
KEEP_UNIQUE_TICKET = "keep_unique_ticket"
KEEP_OVERLAP_DIFFERENT_STRATEGY = "keep_overlap_different_strategy_attribution"
SUPPRESS_EXACT_DUPLICATE = "suppress_exact_duplicate_same_identity_side_market_strategy"

SIDE_FIELDS: tuple[str, ...] = (
    "tsl_side",
    "selected_side",
    "side",
    "paper_selection",
)
MARKET_FIELDS: tuple[str, ...] = (
    "tsl_market",
    "market",
    "market_type",
    "bet_type",
)
STRATEGY_ROW_FIELDS: tuple[str, ...] = (
    "strategy_id",
    "strategy_name",
    "model_ensemble_version",
)
STRATEGY_TRACE_FIELDS: tuple[str, ...] = (
    "strategy_id",
    "strategy_name",
    "prediction_source",
    "prediction_source_id",
    "model_version",
    "feature_fingerprint",
    "selected_side_method",
)


@dataclass(frozen=True)
class DuplicateTicketDecision:
    """One row's local replay duplicate-ticket dry-run decision."""

    row_index: int
    group_key: str
    duplicate_key: str
    status: str
    keep_reason: str
    suppress_reason: str
    ungroupable_reason: str
    game_identity: str
    selected_side: str
    market: str
    strategy_attribution: str
    provenance_contract_version: str
    learning_guard_status: str


def _first_text(row: Mapping[str, Any], fields: Iterable[str]) -> str:
    for field in fields:
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _normalized_token(value: str) -> str:
    return value.strip().lower()


def selected_side(row: Mapping[str, Any]) -> str:
    return _normalized_token(_first_text(row, SIDE_FIELDS))


def market_type(row: Mapping[str, Any]) -> str:
    return _normalized_token(_first_text(row, MARKET_FIELDS))


def strategy_attribution(row: Mapping[str, Any]) -> str:
    """Return deterministic exact strategy attribution without inference.

    Direct row strategy fields are preferred.  If absent, exact model/provenance
    identifiers are used.  Missing attribution is still explicit and may only
    match other rows with the same available model identifiers.
    """
    parts: list[str] = []
    for field in STRATEGY_ROW_FIELDS:
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            parts.append(f"{field}={value.strip()}")

    source_trace = row.get("source_trace")
    if isinstance(source_trace, Mapping):
        for field in STRATEGY_TRACE_FIELDS:
            value = source_trace.get(field)
            if isinstance(value, str) and value.strip():
                parts.append(f"source_trace.{field}={value.strip()}")

    return "|".join(parts) if parts else "UNATTRIBUTED"


def group_key_for_parts(game_identity: str, side: str, market: str) -> str:
    return f"game={game_identity}|side={side}|market={market}"


def duplicate_key_for_parts(
    game_identity: str,
    side: str,
    market: str,
    attribution: str,
) -> str:
    return f"{group_key_for_parts(game_identity, side, market)}|strategy={attribution}"


def provenance_contract_version(row: Mapping[str, Any]) -> str:
    source_trace = row.get("source_trace")
    if isinstance(source_trace, Mapping):
        version = source_trace.get("provenance_contract_version")
        if isinstance(version, str) and version.strip():
            return version.strip()
    return ""


def learning_guard_status(row: Mapping[str, Any]) -> str:
    decision = evaluate_learning_outcome_join(row, [])
    if decision.learning_eligible:
        return "learning_eligible"
    return decision.block_reason or "learning_ineligible"


def analyze_duplicate_tickets(
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Analyze duplicate/overlapping recommendation tickets without mutation."""
    materialized = list(rows)
    decisions: list[DuplicateTicketDecision] = []
    duplicate_first_seen: dict[str, int] = {}
    group_counts: dict[str, int] = {}
    group_strategy_sets: dict[str, set[str]] = {}
    ungroupable_counts = {
        UNGROUPABLE_MISSING_IDENTITY: 0,
        UNGROUPABLE_MISSING_SELECTED_SIDE: 0,
        UNGROUPABLE_MISSING_MARKET: 0,
    }

    for row_index, row in enumerate(materialized):
        identity = stable_game_identity(row)
        side = selected_side(row)
        market = market_type(row)
        attribution = strategy_attribution(row)
        version = provenance_contract_version(row)
        guard_status = learning_guard_status(row)

        ungroupable_reason = ""
        if not identity:
            ungroupable_reason = UNGROUPABLE_MISSING_IDENTITY
        elif not side:
            ungroupable_reason = UNGROUPABLE_MISSING_SELECTED_SIDE
        elif not market:
            ungroupable_reason = UNGROUPABLE_MISSING_MARKET

        if ungroupable_reason:
            ungroupable_counts[ungroupable_reason] += 1
            decisions.append(
                DuplicateTicketDecision(
                    row_index=row_index,
                    group_key="",
                    duplicate_key="",
                    status="kept",
                    keep_reason=ungroupable_reason,
                    suppress_reason="",
                    ungroupable_reason=ungroupable_reason,
                    game_identity=identity,
                    selected_side=side,
                    market=market,
                    strategy_attribution=attribution,
                    provenance_contract_version=version,
                    learning_guard_status=guard_status,
                )
            )
            continue

        group_key = group_key_for_parts(identity, side, market)
        duplicate_key = duplicate_key_for_parts(identity, side, market, attribution)
        group_counts[group_key] = group_counts.get(group_key, 0) + 1
        group_strategy_sets.setdefault(group_key, set()).add(attribution)

        if duplicate_key in duplicate_first_seen:
            decisions.append(
                DuplicateTicketDecision(
                    row_index=row_index,
                    group_key=group_key,
                    duplicate_key=duplicate_key,
                    status="suppressed",
                    keep_reason="",
                    suppress_reason=SUPPRESS_EXACT_DUPLICATE,
                    ungroupable_reason="",
                    game_identity=identity,
                    selected_side=side,
                    market=market,
                    strategy_attribution=attribution,
                    provenance_contract_version=version,
                    learning_guard_status=guard_status,
                )
            )
        else:
            duplicate_first_seen[duplicate_key] = row_index
            decisions.append(
                DuplicateTicketDecision(
                    row_index=row_index,
                    group_key=group_key,
                    duplicate_key=duplicate_key,
                    status="kept",
                    keep_reason=KEEP_UNIQUE_TICKET,
                    suppress_reason="",
                    ungroupable_reason="",
                    game_identity=identity,
                    selected_side=side,
                    market=market,
                    strategy_attribution=attribution,
                    provenance_contract_version=version,
                    learning_guard_status=guard_status,
                )
            )

    for decision_index, decision in enumerate(decisions):
        if decision.status != "kept" or not decision.group_key:
            continue
        if group_counts.get(decision.group_key, 0) <= 1:
            continue
        reason = (
            KEEP_OVERLAP_DIFFERENT_STRATEGY
            if len(group_strategy_sets.get(decision.group_key, set())) > 1
            else KEEP_FIRST_IN_DUPLICATE_SET
        )
        decisions[decision_index] = DuplicateTicketDecision(
            row_index=decision.row_index,
            group_key=decision.group_key,
            duplicate_key=decision.duplicate_key,
            status=decision.status,
            keep_reason=reason,
            suppress_reason=decision.suppress_reason,
            ungroupable_reason=decision.ungroupable_reason,
            game_identity=decision.game_identity,
            selected_side=decision.selected_side,
            market=decision.market,
            strategy_attribution=decision.strategy_attribution,
            provenance_contract_version=decision.provenance_contract_version,
            learning_guard_status=decision.learning_guard_status,
        )

    kept_rows = sum(1 for decision in decisions if decision.status == "kept")
    suppressed_rows = sum(1 for decision in decisions if decision.status == "suppressed")
    total_input_rows = len(materialized)
    group_details = [
        {
            "group_key": group_key,
            "row_count": group_counts[group_key],
            "strategy_attribution_count": len(group_strategy_sets[group_key]),
            "suppressed_rows": sum(
                1
                for decision in decisions
                if decision.group_key == group_key and decision.status == "suppressed"
            ),
        }
        for group_key in sorted(group_counts)
    ]

    return {
        "policy_version": "p206a.duplicate_ticket_policy.v1",
        "policy_scope": "local_historical_replay_only",
        "total_input_rows": total_input_rows,
        "total_groups": len(group_counts),
        "kept_rows": kept_rows,
        "suppressed_rows": suppressed_rows,
        "suppression_rate": (suppressed_rows / total_input_rows) if total_input_rows else 0.0,
        "ungroupable_counts": ungroupable_counts,
        "group_details": group_details,
        "decisions": [decision.__dict__ for decision in decisions],
        "non_claims": {
            "future_prediction": False,
            "betting_recommendation": False,
            "ev_roi_payout_kelly": False,
            "activation_or_live_market": False,
            "production_or_db_mutation": False,
            "future_ticket_mutation": False,
        },
    }
