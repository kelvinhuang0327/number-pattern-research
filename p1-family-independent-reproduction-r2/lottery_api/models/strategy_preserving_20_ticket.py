"""Deterministic strategy-preserving 20-ticket constructor.

``strategy_preserving_20_ticket/v1`` is an outcome-blind adapter contract for
BIG_LOTTO strategies whose native interface emits fewer than 20 tickets.  The
constructor receives strategy output and cutoff identity, never winning
numbers, a database handle, or an unrestricted context object.

Material changes to the constants or selection algorithm require a new
constructor version.  The v1 constants are intentionally public so parity
tests and evidence manifests can pin the exact behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping, Sequence, Tuple, Union


CONSTRUCTOR_NAME = "strategy_preserving_20_ticket"
CONSTRUCTOR_VERSION = "v1"
CONSTRUCTOR_IDENTIFIER = f"{CONSTRUCTOR_NAME}/{CONSTRUCTOR_VERSION}"
SHORT_IDENTIFIER = "sp20_v1"
DEFAULT_TARGET_TICKET_COUNT = 20

# Versioned v1 objective constants.  These values were fixed before the P20C
# historical validation run and must not be tuned against its M4+ outcomes.
CANDIDATE_POOL_SIZE = 80
MAX_CANDIDATE_ATTEMPTS = 4096
SIGNAL_SCORE_WEIGHT = 100.0
MAX_OVERLAP_PENALTY = 12.0
NUMBER_CONCENTRATION_PENALTY = 2.0
V1_PARITY_PORTFOLIO_SHA256 = (
    "8f756025c8818987101b2b61f7c296d0341d7fea52ffa95f7272ca121c9b30d6"
)

Ticket = Tuple[int, int, int, int, int, int]


class ConstructorFailureReason(str, Enum):
    """Typed fail-closed outcomes for constructor requests."""

    NO_VALID_STRATEGY_SIGNAL = "NO_VALID_STRATEGY_SIGNAL"
    INVALID_NATIVE_OUTPUT = "INVALID_NATIVE_OUTPUT"
    INSUFFICIENT_CONSTRUCTION_UNIVERSE = "INSUFFICIENT_CONSTRUCTION_UNIVERSE"
    CANNOT_REACH_UNIQUE_TARGET = "CANNOT_REACH_UNIQUE_TARGET"
    INVALID_CUTOFF = "INVALID_CUTOFF"
    INTERNAL_CONSTRUCTOR_ERROR = "INTERNAL_CONSTRUCTOR_ERROR"
    UNSUPPORTED_TARGET_TICKET_COUNT = "UNSUPPORTED_TARGET_TICKET_COUNT"


class ConstructionTier(str, Enum):
    """The strongest strategy-owned signal used for a successful result."""

    NATIVE_COMPLETE = "native_complete"
    STRATEGY_RANKED_SIGNAL = "strategy_ranked_signal"
    NATIVE_TICKET_DERIVED_SIGNAL = "native_ticket_derived_signal"


@dataclass(frozen=True)
class ConstructorRequest:
    """Outcome-free constructor input.

    ``historical_cutoff_identity`` names the newest draw visible to the native
    strategy.  Numeric draw identities are required to be strictly earlier
    than ``draw_id``.  ``ranked_numbers`` is ordered by the strategy and is
    therefore intentionally order-sensitive; mappings and ticket collections
    are canonicalized internally.
    """

    strategy_id: str
    draw_id: str
    replicate_id: int
    raw_tickets: Sequence[Sequence[int]]
    historical_cutoff_identity: str
    user_seed: str | int = "default"
    target_ticket_count: int = DEFAULT_TARGET_TICKET_COUNT
    number_scores: Mapping[int, float] | None = None
    ranked_numbers: Sequence[int] | None = None
    strategy_metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ConstructorMetadata:
    constructor_name: str
    constructor_version: str
    base_strategy_id: str
    effective_strategy_id: str
    strategy_id: str
    draw_id: str
    replicate_id: int
    historical_cutoff_identity: str
    seed_material: str
    seed_digest: str
    native_input_count: int
    native_valid_count: int
    native_duplicate_count: int
    native_invalid_count: int
    native_retained_count: int
    constructed_ticket_count: int
    final_ticket_count: int
    native_ticket_share: float
    signal_source: str
    construction_tier: str
    relaxation_level: int
    warnings: tuple[str, ...]
    portfolio_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConstructorSuccess:
    tickets: tuple[Ticket, ...]
    metadata: ConstructorMetadata
    ok: bool = True


@dataclass(frozen=True)
class ConstructorFailure:
    reason: ConstructorFailureReason
    message: str
    constructor_name: str
    constructor_version: str
    strategy_id: str
    draw_id: str
    replicate_id: int
    native_input_count: int
    native_valid_count: int
    native_duplicate_count: int
    native_invalid_count: int
    warnings: tuple[str, ...] = ()
    ok: bool = False

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["reason"] = self.reason.value
        return value


ConstructorResult = Union[ConstructorSuccess, ConstructorFailure]


def objective_constants() -> dict[str, int | float | str]:
    """Return the immutable public constants for evidence manifests."""

    return {
        "constructor_identifier": CONSTRUCTOR_IDENTIFIER,
        "candidate_pool_size": CANDIDATE_POOL_SIZE,
        "max_candidate_attempts": MAX_CANDIDATE_ATTEMPTS,
        "signal_score_weight": SIGNAL_SCORE_WEIGHT,
        "max_overlap_penalty": MAX_OVERLAP_PENALTY,
        "number_concentration_penalty": NUMBER_CONCENTRATION_PENALTY,
        "parity_portfolio_sha256": V1_PARITY_PORTFOLIO_SHA256,
    }


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _portfolio_sha256(tickets: Sequence[Ticket]) -> str:
    canonical = [list(ticket) for ticket in sorted(tickets)]
    return hashlib.sha256(_canonical_json_bytes(canonical)).hexdigest()


def _normalise_ticket(raw: Sequence[int]) -> Ticket:
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise ValueError("ticket must be a sequence")
    if len(raw) != 6:
        raise ValueError("ticket must contain exactly six numbers")
    if not all(type(number) is int for number in raw):
        raise ValueError("ticket numbers must be exact integers")
    values = tuple(sorted(raw))
    if len(set(values)) != 6:
        raise ValueError("ticket numbers must be distinct")
    if any(number < 1 or number > 49 for number in values):
        raise ValueError("ticket number outside 1..49")
    return values  # type: ignore[return-value]


def _normalise_native_tickets(
    raw_tickets: Sequence[Sequence[int]],
) -> tuple[list[Ticket], int, int]:
    unique: set[Ticket] = set()
    invalid_count = 0
    duplicate_count = 0
    for raw in raw_tickets:
        try:
            ticket = _normalise_ticket(raw)
        except (TypeError, ValueError):
            invalid_count += 1
            continue
        if ticket in unique:
            duplicate_count += 1
            continue
        unique.add(ticket)
    return sorted(unique), duplicate_count, invalid_count


def _cutoff_is_valid(draw_id: str, cutoff: str) -> bool:
    if type(draw_id) is not str or not draw_id.strip():
        return False
    if type(cutoff) is not str or not cutoff.strip():
        return False
    draw_value = draw_id.strip()
    cutoff_value = cutoff.strip()
    if draw_value.isdecimal() and cutoff_value.isdecimal():
        return int(cutoff_value) < int(draw_value)
    return cutoff_value != draw_value


def _normalise_explicit_signal(
    number_scores: Mapping[int, float] | None,
    ranked_numbers: Sequence[int] | None,
) -> tuple[dict[int, float], str | None, tuple[str, ...]]:
    raw_scores: dict[int, float] = {}
    warnings: list[str] = []
    if number_scores is not None:
        for raw_number, raw_score in sorted(number_scores.items(), key=lambda item: str(item[0])):
            if type(raw_number) is not int or not 1 <= raw_number <= 49:
                warnings.append("ignored invalid number_scores key")
                continue
            if type(raw_score) not in (int, float) or not math.isfinite(float(raw_score)):
                warnings.append(f"ignored invalid score for number {raw_number}")
                continue
            raw_scores[raw_number] = float(raw_score)

    ranked: list[int] = []
    seen_ranked: set[int] = set()
    if ranked_numbers is not None:
        for raw_number in ranked_numbers:
            if type(raw_number) is not int or not 1 <= raw_number <= 49:
                warnings.append("ignored invalid ranked number")
                continue
            if raw_number not in seen_ranked:
                seen_ranked.add(raw_number)
                ranked.append(raw_number)

    source: str | None = None
    if raw_scores:
        source = "strategy_number_scores"
        low = min(raw_scores.values())
        high = max(raw_scores.values())
        if high == low:
            scores = {number: 1.0 for number in raw_scores}
        else:
            scores = {
                number: (score - low) / (high - low)
                for number, score in raw_scores.items()
            }
        if ranked:
            source = "strategy_number_scores_and_ranked_numbers"
            denominator = max(1, len(ranked) - 1)
            for index, number in enumerate(ranked):
                rank_score = 1.0 - (index / denominator)
                scores[number] = max(scores.get(number, 0.0), rank_score)
        return dict(sorted(scores.items())), source, tuple(sorted(set(warnings)))

    if ranked:
        source = "strategy_ranked_numbers"
        denominator = max(1, len(ranked) - 1)
        return (
            {
                number: 1.0 - (index / denominator)
                for index, number in enumerate(ranked)
            },
            source,
            tuple(sorted(set(warnings))),
        )
    return {}, source, tuple(sorted(set(warnings)))


def _native_signal(tickets: Sequence[Ticket]) -> dict[int, float]:
    counts = Counter(number for ticket in tickets for number in ticket)
    if not counts:
        return {}
    maximum = max(counts.values())
    return {
        number: count / maximum
        for number, count in sorted(counts.items())
    }


def _minimum_signal_numbers(signal_pool_size: int) -> int:
    if signal_pool_size <= 0:
        return 0
    if signal_pool_size < 6:
        return signal_pool_size
    if signal_pool_size <= 8:
        return 3
    if signal_pool_size <= 14:
        return 4
    return 5


def _construction_universe_size(signal_pool_size: int, minimum_signal: int) -> int:
    neutral_size = 49 - signal_pool_size
    total = 0
    for signal_count in range(minimum_signal, min(6, signal_pool_size) + 1):
        neutral_count = 6 - signal_count
        if neutral_count <= neutral_size:
            total += math.comb(signal_pool_size, signal_count) * math.comb(
                neutral_size, neutral_count
            )
    return total


class _Sha256Stream:
    """Small deterministic byte stream backed only by SHA-256."""

    def __init__(self, key: bytes):
        self._key = key
        self._counter = 0
        self._buffer = bytearray()

    def _fill(self) -> None:
        counter_bytes = self._counter.to_bytes(16, "big", signed=False)
        self._buffer.extend(hashlib.sha256(self._key + counter_bytes).digest())
        self._counter += 1

    def uint64(self) -> int:
        while len(self._buffer) < 8:
            self._fill()
        raw = bytes(self._buffer[:8])
        del self._buffer[:8]
        return int.from_bytes(raw, "big", signed=False)

    def randbelow(self, upper: int) -> int:
        if upper <= 0:
            raise ValueError("upper must be positive")
        modulus = 1 << 64
        limit = modulus - (modulus % upper)
        while True:
            value = self.uint64()
            if value < limit:
                return value % upper


def _sample(values: Sequence[int], count: int, stream: _Sha256Stream) -> list[int]:
    if count < 0 or count > len(values):
        raise ValueError("sample count outside population")
    selected_indexes: set[int] = set()
    for upper in range(len(values) - count, len(values)):
        candidate = stream.randbelow(upper + 1)
        selected_indexes.add(upper if candidate in selected_indexes else candidate)
    return [values[index] for index in sorted(selected_indexes)]


def _candidate_pool(
    *,
    seed_digest: str,
    signal_scores: Mapping[int, float],
    existing: Sequence[Ticket],
    required_count: int,
) -> list[Ticket]:
    signal_pool = sorted(signal_scores)
    minimum_signal = _minimum_signal_numbers(len(signal_pool))
    maximum_signal = min(6, len(signal_pool))
    stream = _Sha256Stream(bytes.fromhex(seed_digest) + b"|candidate-pool")
    existing_set = set(existing)
    candidates: set[Ticket] = set()
    desired = max(CANDIDATE_POOL_SIZE, required_count * 4)
    universe = tuple(range(1, 50))

    attempts = 0
    while len(candidates) < desired and attempts < MAX_CANDIDATE_ATTEMPTS:
        attempts += 1
        signal_count = minimum_signal
        if maximum_signal > minimum_signal:
            signal_count += stream.randbelow(maximum_signal - minimum_signal + 1)
        selected_signal = _sample(signal_pool, signal_count, stream)
        selected_set = set(selected_signal)
        remaining_pool = [number for number in universe if number not in selected_set]
        selected_neutral = _sample(remaining_pool, 6 - signal_count, stream)
        ticket = tuple(sorted(selected_signal + selected_neutral))
        if ticket not in existing_set:
            candidates.add(ticket)  # type: ignore[arg-type]
    return sorted(candidates)


def _ticket_mask(ticket: Ticket) -> int:
    mask = 0
    for number in ticket:
        mask |= 1 << (number - 1)
    return mask


def _overlap_count(left_mask: int, right_mask: int) -> int:
    """Python 3.9-compatible population count for a 49-bit intersection."""

    return bin(left_mask & right_mask).count("1")


def _select_with_diversity(
    *,
    candidates: Sequence[Ticket],
    retained: Sequence[Ticket],
    signal_scores: Mapping[int, float],
    seed_digest: str,
    count: int,
) -> list[Ticket]:
    remaining = list(candidates)
    selected = list(retained)
    selected_masks = [_ticket_mask(ticket) for ticket in selected]
    usage = Counter(number for ticket in selected for number in ticket)
    chosen: list[Ticket] = []

    for _ in range(count):
        if not remaining:
            break
        scored: list[tuple[tuple[float, int, int, int], Ticket]] = []
        for ticket in remaining:
            mask = _ticket_mask(ticket)
            maximum_overlap = max(
                (_overlap_count(mask, other_mask) for other_mask in selected_masks),
                default=0,
            )
            concentration = sum(usage[number] for number in ticket)
            signal_score = sum(signal_scores.get(number, 0.0) for number in ticket)
            objective = (
                SIGNAL_SCORE_WEIGHT * signal_score
                - MAX_OVERLAP_PENALTY * (maximum_overlap**2)
                - NUMBER_CONCENTRATION_PENALTY * concentration
            )
            tie_digest = hashlib.sha256(
                bytes.fromhex(seed_digest) + _canonical_json_bytes(ticket)
            ).digest()
            tie_value = int.from_bytes(tie_digest, "big", signed=False)
            scored.append(
                (
                    (objective, -maximum_overlap, -concentration, -tie_value),
                    ticket,
                )
            )
        _, winner = max(scored, key=lambda item: item[0])
        remaining.remove(winner)
        chosen.append(winner)
        selected.append(winner)
        selected_masks.append(_ticket_mask(winner))
        usage.update(winner)
    return chosen


def _failure(
    request: ConstructorRequest,
    reason: ConstructorFailureReason,
    message: str,
    *,
    native_input_count: int = 0,
    native_valid_count: int = 0,
    native_duplicate_count: int = 0,
    native_invalid_count: int = 0,
    warnings: Sequence[str] = (),
) -> ConstructorFailure:
    return ConstructorFailure(
        reason=reason,
        message=message,
        constructor_name=CONSTRUCTOR_NAME,
        constructor_version=CONSTRUCTOR_VERSION,
        strategy_id=request.strategy_id,
        draw_id=request.draw_id,
        replicate_id=request.replicate_id,
        native_input_count=native_input_count,
        native_valid_count=native_valid_count,
        native_duplicate_count=native_duplicate_count,
        native_invalid_count=native_invalid_count,
        warnings=tuple(warnings),
    )


def _construct(request: ConstructorRequest) -> ConstructorResult:
    if request.target_ticket_count != DEFAULT_TARGET_TICKET_COUNT:
        return _failure(
            request,
            ConstructorFailureReason.UNSUPPORTED_TARGET_TICKET_COUNT,
            "v1 supports exactly 20 final tickets",
        )
    if not _cutoff_is_valid(request.draw_id, request.historical_cutoff_identity):
        return _failure(
            request,
            ConstructorFailureReason.INVALID_CUTOFF,
            "historical cutoff must identify a draw strictly before the target",
        )
    if type(request.strategy_id) is not str or not request.strategy_id.strip():
        return _failure(
            request,
            ConstructorFailureReason.NO_VALID_STRATEGY_SIGNAL,
            "strategy_id must be a non-empty string",
        )
    if type(request.replicate_id) is not int or request.replicate_id < 0:
        return _failure(
            request,
            ConstructorFailureReason.INTERNAL_CONSTRUCTOR_ERROR,
            "replicate_id must be a non-negative integer",
        )
    if type(request.user_seed) not in (str, int):
        return _failure(
            request,
            ConstructorFailureReason.INTERNAL_CONSTRUCTOR_ERROR,
            "user_seed must be a string or integer",
        )
    if isinstance(request.raw_tickets, (str, bytes)) or not isinstance(
        request.raw_tickets, Sequence
    ):
        return _failure(
            request,
            ConstructorFailureReason.INVALID_NATIVE_OUTPUT,
            "raw_tickets must be a ticket sequence",
        )

    native_input_count = len(request.raw_tickets)
    native, duplicate_count, invalid_count = _normalise_native_tickets(
        request.raw_tickets
    )
    warnings: list[str] = []
    if duplicate_count:
        warnings.append(f"deduplicated {duplicate_count} native ticket(s)")
    if invalid_count:
        warnings.append(f"rejected {invalid_count} invalid native ticket(s)")

    seed_material = "|".join(
        (
            SHORT_IDENTIFIER,
            request.strategy_id.strip(),
            request.draw_id.strip(),
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    seed_digest = hashlib.sha256(seed_material.encode("utf-8")).hexdigest()

    if len(native) == DEFAULT_TARGET_TICKET_COUNT:
        tickets = tuple(native)
        metadata = ConstructorMetadata(
            constructor_name=CONSTRUCTOR_NAME,
            constructor_version=CONSTRUCTOR_VERSION,
            base_strategy_id=request.strategy_id,
            effective_strategy_id=request.strategy_id,
            strategy_id=request.strategy_id,
            draw_id=request.draw_id,
            replicate_id=request.replicate_id,
            historical_cutoff_identity=request.historical_cutoff_identity,
            seed_material=seed_material,
            seed_digest=seed_digest,
            native_input_count=native_input_count,
            native_valid_count=len(native),
            native_duplicate_count=duplicate_count,
            native_invalid_count=invalid_count,
            native_retained_count=len(native),
            constructed_ticket_count=0,
            final_ticket_count=len(tickets),
            native_ticket_share=1.0,
            signal_source="native_complete",
            construction_tier=ConstructionTier.NATIVE_COMPLETE.value,
            relaxation_level=0,
            warnings=tuple(warnings),
            portfolio_sha256=_portfolio_sha256(tickets),
        )
        return ConstructorSuccess(tickets=tickets, metadata=metadata)

    explicit_scores, explicit_source, signal_warnings = _normalise_explicit_signal(
        request.number_scores,
        request.ranked_numbers,
    )
    warnings.extend(signal_warnings)
    if explicit_scores:
        signal_scores = explicit_scores
        signal_source = explicit_source or "strategy_ranked_numbers"
        tier = ConstructionTier.STRATEGY_RANKED_SIGNAL
    elif native:
        signal_scores = _native_signal(native)
        signal_source = "native_ticket_frequency"
        tier = ConstructionTier.NATIVE_TICKET_DERIVED_SIGNAL
    else:
        reason = (
            ConstructorFailureReason.INVALID_NATIVE_OUTPUT
            if native_input_count and invalid_count == native_input_count
            else ConstructorFailureReason.NO_VALID_STRATEGY_SIGNAL
        )
        return _failure(
            request,
            reason,
            "no valid native ticket, ranked number, or number score is available",
            native_input_count=native_input_count,
            native_valid_count=0,
            native_duplicate_count=duplicate_count,
            native_invalid_count=invalid_count,
            warnings=warnings,
        )

    if len(native) > DEFAULT_TARGET_TICKET_COUNT:
        retained = _select_with_diversity(
            candidates=native,
            retained=(),
            signal_scores=signal_scores,
            seed_digest=seed_digest,
            count=DEFAULT_TARGET_TICKET_COUNT,
        )
        constructed: list[Ticket] = []
    else:
        retained = list(native)
        required = DEFAULT_TARGET_TICKET_COUNT - len(retained)
        minimum_signal = _minimum_signal_numbers(len(signal_scores))
        universe_size = _construction_universe_size(
            len(signal_scores), minimum_signal
        )
        if universe_size < required:
            return _failure(
                request,
                ConstructorFailureReason.INSUFFICIENT_CONSTRUCTION_UNIVERSE,
                "strategy signal cannot form enough legal unique tickets",
                native_input_count=native_input_count,
                native_valid_count=len(native),
                native_duplicate_count=duplicate_count,
                native_invalid_count=invalid_count,
                warnings=warnings,
            )
        candidates = _candidate_pool(
            seed_digest=seed_digest,
            signal_scores=signal_scores,
            existing=retained,
            required_count=required,
        )
        constructed = _select_with_diversity(
            candidates=candidates,
            retained=retained,
            signal_scores=signal_scores,
            seed_digest=seed_digest,
            count=required,
        )
        if len(constructed) != required:
            return _failure(
                request,
                ConstructorFailureReason.CANNOT_REACH_UNIQUE_TARGET,
                "candidate selection could not reach 20 unique tickets",
                native_input_count=native_input_count,
                native_valid_count=len(native),
                native_duplicate_count=duplicate_count,
                native_invalid_count=invalid_count,
                warnings=warnings,
            )

    tickets = tuple(retained + constructed)
    if len(tickets) != DEFAULT_TARGET_TICKET_COUNT or len(set(tickets)) != len(tickets):
        return _failure(
            request,
            ConstructorFailureReason.CANNOT_REACH_UNIQUE_TARGET,
            "final portfolio is not exactly 20 unique tickets",
            native_input_count=native_input_count,
            native_valid_count=len(native),
            native_duplicate_count=duplicate_count,
            native_invalid_count=invalid_count,
            warnings=warnings,
        )

    if constructed:
        warnings.append(
            "constructed tickets use a deterministic neutral 1..49 universe for non-signal positions"
        )
    metadata = ConstructorMetadata(
        constructor_name=CONSTRUCTOR_NAME,
        constructor_version=CONSTRUCTOR_VERSION,
        base_strategy_id=request.strategy_id,
        effective_strategy_id=f"{request.strategy_id}@{SHORT_IDENTIFIER}",
        strategy_id=request.strategy_id,
        draw_id=request.draw_id,
        replicate_id=request.replicate_id,
        historical_cutoff_identity=request.historical_cutoff_identity,
        seed_material=seed_material,
        seed_digest=seed_digest,
        native_input_count=native_input_count,
        native_valid_count=len(native),
        native_duplicate_count=duplicate_count,
        native_invalid_count=invalid_count,
        native_retained_count=len(retained),
        constructed_ticket_count=len(constructed),
        final_ticket_count=len(tickets),
        native_ticket_share=len(retained) / DEFAULT_TARGET_TICKET_COUNT,
        signal_source=signal_source,
        construction_tier=tier.value,
        relaxation_level=0,
        warnings=tuple(sorted(set(warnings))),
        portfolio_sha256=_portfolio_sha256(tickets),
    )
    return ConstructorSuccess(tickets=tickets, metadata=metadata)


def construct_strategy_preserving_20_ticket(
    request: ConstructorRequest,
) -> ConstructorResult:
    """Construct a typed v1 result without ever returning partial success."""

    try:
        return _construct(request)
    except Exception as exc:  # fail closed at the public contract boundary
        return _failure(
            request,
            ConstructorFailureReason.INTERNAL_CONSTRUCTOR_ERROR,
            f"unexpected {type(exc).__name__}",
        )


__all__ = [
    "CANDIDATE_POOL_SIZE",
    "CONSTRUCTOR_IDENTIFIER",
    "CONSTRUCTOR_NAME",
    "CONSTRUCTOR_VERSION",
    "ConstructionTier",
    "ConstructorFailure",
    "ConstructorFailureReason",
    "ConstructorMetadata",
    "ConstructorRequest",
    "ConstructorResult",
    "ConstructorSuccess",
    "DEFAULT_TARGET_TICKET_COUNT",
    "MAX_CANDIDATE_ATTEMPTS",
    "MAX_OVERLAP_PENALTY",
    "NUMBER_CONCENTRATION_PENALTY",
    "SHORT_IDENTIFIER",
    "SIGNAL_SCORE_WEIGHT",
    "V1_PARITY_PORTFOLIO_SHA256",
    "construct_strategy_preserving_20_ticket",
    "objective_constants",
]
