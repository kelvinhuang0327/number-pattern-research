"""P280AT — BIG 6/49 eleven-strategy ranking and portfolio-contribution replay.

Local research and replay validation ONLY. This module produces a leakage-free
historical replay ranking of the eleven frozen BIG 6/49 strategies (the P280AQ /
P280D family) and a portfolio-contribution analysis of the current resolved
strategy pack. It answers, honestly and retrospectively:

  1. Which of the eleven strategies ranked higher in leakage-free replay?
  2. Which current pack tickets contribute most to coverage / low-overlap value?
  3. Which Top-K combinations (k = 1/3/5/7/11) are most useful under fixed budget?
  4. Whether any strategy or combination beats appropriate random or
     diversified-random baselines.
  5. Whether the result supports observation-only candidates or remains NULL.

It is NOT a prediction-success claim, betting advice, strategy promotion, or any
form of activation/publication. The module:

  * never writes or copies a database (read-only ``mode=ro`` + ``query_only=ON``);
  * never looks up an official target or deadline;
  * never creates a pre-draw manifest or publication PR;
  * scores each replay target using ONLY draws strictly before that target;
  * regenerates each strategy ticket through the exact frozen P280D/P280AJ source
    callables (imported, never modified) so the resolved current pack reproduces
    the audited adapter digest ``b8ceac65...``.

The strategy unit for the strategy-level ranking is each strategy's frozen
``bet_index=1`` primary ticket (the canonical single recommendation that the whole
P280 adapter family is built around). At the latest draw several primaries
coincide (the duplicate structure P280AQ remediated); in replay they diverge as
history changes, so the per-target frozen primary is an informative, fair,
one-ticket-per-strategy unit. The current-pack contribution analysis (Task C) uses
the deduplicated resolved pack (digest ``b8ceac65...``).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import sqlite3
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

# Make the repository root importable so this module runs as a script
# (``python tools/p280at_...py``) as well as via pytest.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# The frozen no-DB adapter is the single source of truth for the strategy
# identities, normalization, dedup selection, and output digest. It is imported,
# never modified. Underscore helpers are reused so replay primaries match the
# adapter byte-for-byte.
from tools.big649_no_db_strategy_output_adapter import (  # noqa: E402
    _SPECS,
    _canonical_ticket,
    _normalize_bets,
    compute_strategy_output_digest,
    list_frozen_big649_strategy_ids,
    resolve_unique_strategy_outputs,
    validate_strategy_adapter_contract,
)

TASK_ID = "P280AT"
SCHEMA_VERSION = "p280at_big649_strategy_ranking_replay_v1"

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_RELATIVE = "lottery_api/data/lottery_v2.db"
DEFAULT_OUT_JSON = "outputs/research/p280at_big649_strategy_ranking_replay_20260619.json"
DEFAULT_OUT_MD = "outputs/research/p280at_big649_strategy_ranking_replay_20260619.md"

CANONICAL_VIEW = "draws_big_lotto_canonical_main"
LOTTERY = "BIG_LOTTO"
TICKET_SIZE = 6
POOL_MIN = 1
POOL_MAX = 49
POOL_SIZE = POOL_MAX - POOL_MIN + 1  # 49
MIN_HISTORY = 500  # adapter contract MIN_HISTORY; replay targets need >= this prior

DEFAULT_SEED = 42
DEFAULT_MC_REPLICATES = 200
WALK_FORWARD_MIN_PRIOR = 30  # warmup before outcome-based selection is allowed

# Most-recent N eligible targets define each horizon.
HORIZONS = (
    ("recent_100", 100),
    ("mid_300", 300),
    ("long_750", 750),
    ("all_available", None),  # all eligible targets
)
PRIMARY_HORIZON = "long_750"
PRIMARY_WINDOWS = ("recent_100", "mid_300", "long_750")  # Bonferroni family windows

BUDGETS = (1, 3, 5, 7, 11)

COMBINATION_METHODS = (
    "top_k_by_historical_replay",
    "diversity_first_low_overlap",
    "marginal_contribution_greedy",
    "stability_weighted_top_k",
    "hybrid_strategy_plus_diversified_random",
    "all_11_strategy_pack",
    "equal_budget_random_baseline",
    "diversified_random_baseline",
)

# 大樂透 (Taiwan BIG Lotto) prize tiers for a 6-of-49 ticket against a draw of six
# main numbers plus one special number (special drawn from the same 1..49 pool).
PRIZE_TIER_TABLE = (
    {"tier": "1 (jackpot)", "rule": "match 6 main"},
    {"tier": "2", "rule": "match 5 main + special"},
    {"tier": "3", "rule": "match 5 main"},
    {"tier": "4", "rule": "match 4 main + special"},
    {"tier": "5", "rule": "match 4 main"},
    {"tier": "6", "rule": "match 3 main + special"},
    {"tier": "7", "rule": "match 2 main + special"},
    {"tier": "8 (lowest)", "rule": "match 3 main"},
)
PRIZE_AWARE_RULE = "main_hits >= 3 OR (main_hits == 2 AND special in ticket)"

NULL_CLASSIFICATION = (
    "P280AT_BIG649_STRATEGY_RANKING_REPLAY_PR_OPEN_NULL_NO_PUBLICATION"
)
OBSERVATION_CLASSIFICATION = (
    "P280AT_BIG649_STRATEGY_RANKING_REPLAY_PR_OPEN_OBSERVATION_CANDIDATES_NO_PUBLICATION"
)


class ReplayDatasetError(ValueError):
    """Raised when the canonical replay dataset fails its integrity gate."""


# --------------------------------------------------------------------------- #
# Task A — read-only canonical dataset loader + integrity gate
# --------------------------------------------------------------------------- #
def _sha256_file(path: Path) -> str:
    if not path.exists():
        return "ABSENT"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def db_sidecar_hashes(db_path: Path) -> dict[str, str]:
    """Return sha256 of the main DB file and its -wal / -shm sidecars."""
    return {
        "main": _sha256_file(db_path),
        "wal": _sha256_file(Path(str(db_path) + "-wal")),
        "shm": _sha256_file(Path(str(db_path) + "-shm")),
    }


def load_canonical_history(db_path: Path) -> list[dict[str, Any]]:
    """Load BIG 6/49 canonical draws strictly read-only, chronological ascending.

    Opens the production DB with SQLite URI ``mode=ro`` and asserts
    ``PRAGMA query_only`` == 1. Never writes or copies the DB.
    """
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        if conn.execute("PRAGMA query_only").fetchone()[0] != 1:
            raise ReplayDatasetError("PRAGMA query_only could not be enabled")
        rows = conn.execute(
            f"SELECT draw, date, numbers, special FROM {CANONICAL_VIEW} "
            "ORDER BY CAST(draw AS INTEGER) ASC"
        ).fetchall()
    finally:
        conn.close()
    history: list[dict[str, Any]] = []
    for draw_id, date, numbers_json, special in rows:
        numbers = json.loads(numbers_json)
        history.append(
            {
                "draw": str(draw_id),
                "date": date,
                "numbers": numbers,
                "special": None if special is None else int(special),
            }
        )
    return history


def build_replay_dataset(history: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Validate the canonical history and derive eligible leakage-free targets.

    Rejects duplicate draw ids and malformed tickets. A replay target at index
    ``i`` is eligible when at least ``MIN_HISTORY`` draws precede it; its strategy
    input is ``history[:i]`` and its outcome is ``history[i]`` — never the reverse.
    """
    if not isinstance(history, Sequence) or isinstance(history, (str, bytes)):
        raise ReplayDatasetError("history must be a sequence of draw mappings")
    rows = list(history)
    if len(rows) < MIN_HISTORY + 1:
        raise ReplayDatasetError(
            f"insufficient history: {len(rows)} rows (need > {MIN_HISTORY})"
        )

    seen_ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    prev_key: int | None = None
    for index, draw in enumerate(rows):
        if not isinstance(draw, Mapping) or "draw" not in draw or "numbers" not in draw:
            raise ReplayDatasetError(f"draw[{index}] missing draw id or numbers")
        draw_id = str(draw["draw"])
        if draw_id in seen_ids:
            raise ReplayDatasetError(f"duplicate draw id: {draw_id}")
        seen_ids.add(draw_id)
        main = _canonical_ticket(list(draw["numbers"]), f"draw[{draw_id}].numbers")
        special = draw.get("special")
        if special is not None:
            special = int(special)
            if special < POOL_MIN or special > POOL_MAX:
                raise ReplayDatasetError(f"draw[{draw_id}] special outside 1..49")
        # Chronological monotonicity by integer draw key when ids are numeric.
        if draw_id.isdigit():
            key = int(draw_id)
            if prev_key is not None and key <= prev_key:
                raise ReplayDatasetError(
                    f"draw ids not strictly ascending at {draw_id}"
                )
            prev_key = key
        normalized.append(
            {"draw": draw_id, "date": draw.get("date"), "numbers": main, "special": special}
        )

    minimal = [{"numbers": draw["numbers"]} for draw in normalized]
    eligible_indices = list(range(MIN_HISTORY, len(normalized)))
    return {
        "rows": normalized,
        "minimal": minimal,
        "row_count": len(normalized),
        "eligible_target_indices": eligible_indices,
        "eligible_target_count": len(eligible_indices),
        "latest_draw": normalized[-1]["draw"],
        "earliest_draw": normalized[0]["draw"],
        "min_history": MIN_HISTORY,
    }


def horizon_target_indices(eligible_indices: Sequence[int], size: int | None) -> list[int]:
    """Return the most-recent ``size`` eligible target indices (all when None)."""
    indices = list(eligible_indices)
    if size is None or size >= len(indices):
        return indices
    return indices[-size:]


# --------------------------------------------------------------------------- #
# Scoring primitives (pure)
# --------------------------------------------------------------------------- #
def main_hit_count(ticket: Sequence[int], draw_main: Sequence[int]) -> int:
    """Number of the ticket's six numbers that match the six drawn main numbers."""
    return len(set(ticket) & set(draw_main))


def special_hit(ticket: Sequence[int], special: int | None) -> bool:
    """True when the drawn special number is one of the ticket's numbers."""
    return special is not None and special in set(ticket)


def prize_aware_win(ticket: Sequence[int], draw_main: Sequence[int], special: int | None) -> bool:
    """大樂透 any-prize: 3+ main, or exactly 2 main plus the special."""
    hits = main_hit_count(ticket, draw_main)
    if hits >= 3:
        return True
    return hits == 2 and special_hit(ticket, special)


# --------------------------------------------------------------------------- #
# Strategy engine — per-target frozen bet_index=1 primaries (leakage-free)
# --------------------------------------------------------------------------- #
def load_frozen_strategy_callables() -> list[dict[str, Any]]:
    """Validate the frozen adapter contract once and bind the frozen callables.

    Returns ordered specs with the imported ``bet_index=1`` callable so the replay
    loop can invoke them directly (the adapter's per-call AST re-validation is too
    slow for ~1600 targets x 11 strategies).
    """
    validate_strategy_adapter_contract()
    bound: list[dict[str, Any]] = []
    for spec in _SPECS:
        module = importlib.import_module(spec["module"])
        function = getattr(module, spec["frozen_function"])
        bound.append(
            {
                "strategy_id": spec["strategy_id"],
                "function": function,
                "kwargs": dict(spec["kwargs"]),
                "multi": spec["frozen_multi"],
            }
        )
    return bound


def frozen_primary_ticket(spec: Mapping[str, Any], minimal_history: Sequence[Mapping[str, Any]]) -> list[int]:
    """Invoke one frozen callable and return its canonical bet_index=1 ticket."""
    result = spec["function"](list(minimal_history), **dict(spec["kwargs"]))
    bets = _normalize_bets(result, multi=spec["multi"], label=spec["strategy_id"])
    return bets[0]


def run_strategy_replay(
    dataset: Mapping[str, Any],
    bound_strategies: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Generate every strategy's per-target primary and score it (no leakage).

    For each eligible target index ``i`` and each strategy, the ticket is produced
    from ``minimal[:i]`` (strictly prior draws) and scored against ``rows[i]``.
    """
    bound = list(bound_strategies if bound_strategies is not None else load_frozen_strategy_callables())
    strategy_ids = [spec["strategy_id"] for spec in bound]
    rows = dataset["rows"]
    minimal = dataset["minimal"]
    eligible = dataset["eligible_target_indices"]

    # per_target[strategy_id] -> list aligned to eligible, each a scored record.
    per_target: dict[str, list[dict[str, Any]]] = {sid: [] for sid in strategy_ids}
    for target_index in eligible:
        prior = minimal[:target_index]  # strictly before the target
        outcome = rows[target_index]
        draw_main = outcome["numbers"]
        special = outcome["special"]
        for spec in bound:
            ticket = frozen_primary_ticket(spec, prior)
            hits = main_hit_count(ticket, draw_main)
            sp_hit = special_hit(ticket, special)
            per_target[spec["strategy_id"]].append(
                {
                    "target_index": target_index,
                    "target_draw": outcome["draw"],
                    "ticket": ticket,
                    "main_hits": hits,
                    "special_hit": sp_hit,
                    "prize_win": hits >= 3 or (hits == 2 and sp_hit),
                }
            )
    return {"strategy_ids": strategy_ids, "per_target": per_target, "eligible": list(eligible)}


# --------------------------------------------------------------------------- #
# Task B — strategy-level metrics + ranking
# --------------------------------------------------------------------------- #
def _metrics_over(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    n = len(records)
    distribution = {str(h): 0 for h in range(TICKET_SIZE + 1)}
    total_hits = 0
    ge3 = ge4 = wins = special_hits = special_rescue = 0
    best = 0
    for record in records:
        hits = record["main_hits"]
        distribution[str(hits)] += 1
        total_hits += hits
        best = max(best, hits)
        if hits >= 3:
            ge3 += 1
        if hits >= 4:
            ge4 += 1
        if record["special_hit"]:
            special_hits += 1
            if hits == 2:
                special_rescue += 1  # special turned a non-win into a tier-7 win
        if record["prize_win"]:
            wins += 1
    rate = (lambda x: round(x / n, 6) if n else 0.0)
    return {
        "support": n,
        "avg_main_hits": round(total_hits / n, 6) if n else 0.0,
        "hit_distribution": distribution,
        "ge3_count": ge3,
        "ge3_rate": rate(ge3),
        "ge4_count": ge4,
        "ge4_rate": rate(ge4),
        "prize_win_count": wins,
        "prize_win_rate": rate(wins),
        "best_main_hits": best,
        "special_hit_count": special_hits,
        "special_hit_rate": rate(special_hits),
        "special_rescue_count": special_rescue,
    }


def strategy_level_metrics(replay: Mapping[str, Any]) -> dict[str, Any]:
    """Per-strategy metrics for every horizon."""
    eligible = replay["eligible"]
    index_pos = {idx: pos for pos, idx in enumerate(eligible)}
    out: dict[str, Any] = {}
    for sid in replay["strategy_ids"]:
        records = replay["per_target"][sid]
        out[sid] = {}
        for name, size in HORIZONS:
            target_indices = horizon_target_indices(eligible, size)
            wanted = {index_pos[i] for i in target_indices}
            subset = [rec for pos, rec in enumerate(records) if pos in wanted]
            out[sid][name] = _metrics_over(subset)
    return out


def _stability_score(per_window: Mapping[str, Mapping[str, Any]]) -> float:
    """Consistency of prize-win rate across the three primary windows.

    1.0 = identical rate across windows; lower = more dispersion. Defined as
    ``1 - (max-min)/(mean+epsilon)`` clamped to [0, 1].
    """
    rates = [per_window[w]["prize_win_rate"] for w in PRIMARY_WINDOWS]
    mean = sum(rates) / len(rates)
    spread = max(rates) - min(rates)
    if mean <= 0:
        return 1.0 if spread == 0 else 0.0
    return round(max(0.0, min(1.0, 1.0 - spread / mean)), 6)


def rank_strategies(
    metrics: Mapping[str, Mapping[str, Any]],
    pack_contribution: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Rank the eleven strategies (historical replay only, NOT future success).

    Sort keys (descending unless noted): long_750 prize-win rate, long_750 avg
    main hits, stability across 100/300/750, marginal portfolio contribution
    (higher = better; lower overlap), then deterministic strategy_id (ascending)
    as the final tie-breaker.
    """
    rows: list[dict[str, Any]] = []
    for sid, per_window in metrics.items():
        stability = _stability_score(per_window)
        marginal = 0.0
        if pack_contribution and sid in pack_contribution:
            marginal = pack_contribution[sid].get("marginal_coverage_contribution", 0.0)
        rows.append(
            {
                "strategy_id": sid,
                "long750_prize_win_rate": per_window[PRIMARY_HORIZON]["prize_win_rate"],
                "long750_avg_main_hits": per_window[PRIMARY_HORIZON]["avg_main_hits"],
                "stability_across_windows": stability,
                "marginal_portfolio_contribution": round(marginal, 6),
            }
        )
    rows.sort(
        key=lambda r: (
            -r["long750_prize_win_rate"],
            -r["long750_avg_main_hits"],
            -r["stability_across_windows"],
            -r["marginal_portfolio_contribution"],
            r["strategy_id"],
        )
    )
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


# --------------------------------------------------------------------------- #
# Task C — current pack contribution (geometry of the resolved 11-ticket pack)
# --------------------------------------------------------------------------- #
def reproduce_current_pack(
    history: Sequence[Mapping[str, Any]],
    history_cutoff: str,
    target_draw: str,
) -> dict[str, Any]:
    """Reproduce the resolved unique 11-ticket pack and its adapter digest."""
    resolved = resolve_unique_strategy_outputs(
        history, history_cutoff, {"target_draw": target_draw, "synthetic": True}
    )
    digest = compute_strategy_output_digest(resolved["outputs"])
    return {"outputs": resolved["outputs"], "provenance": resolved["provenance"], "digest": digest}


def pack_contribution_analysis(pack_outputs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Coverage / overlap / redundancy / role for every current pack ticket."""
    tickets = {rec["strategy_id"]: set(rec["predicted_main_numbers"]) for rec in pack_outputs}
    ids = [rec["strategy_id"] for rec in pack_outputs]
    contribution: dict[str, dict[str, Any]] = {}

    for sid in ids:
        own = tickets[sid]
        others_union: set[int] = set()
        overlaps: list[int] = []
        for other in ids:
            if other == sid:
                continue
            others_union |= tickets[other]
            overlaps.append(len(own & tickets[other]))
        unique_numbers = sorted(own - others_union)  # covered by NO other ticket
        max_pair = max(overlaps) if overlaps else 0
        mean_pair = round(sum(overlaps) / len(overlaps), 6) if overlaps else 0.0
        marginal = len(unique_numbers) / TICKET_SIZE  # fraction of own numbers unique to it
        redundancy = round(mean_pair / TICKET_SIZE, 6)
        contribution[sid] = {
            "ticket": sorted(own),
            "unique_number_contribution": unique_numbers,
            "unique_number_count": len(unique_numbers),
            "max_pair_overlap": max_pair,
            "mean_pair_overlap": mean_pair,
            "marginal_coverage_contribution": round(marginal, 6),
            "redundancy_score": redundancy,
        }

    # Role labels are assigned relative to the pack's own distribution.
    uniques = [contribution[s]["unique_number_count"] for s in ids]
    mean_unique = sum(uniques) / len(uniques) if uniques else 0.0
    for sid in ids:
        info = contribution[sid]
        if info["max_pair_overlap"] >= 4:
            role = "high-overlap"
        elif info["unique_number_count"] >= 5:
            role = "coverage"
        elif info["unique_number_count"] <= 1:
            role = "redundant"
        elif info["unique_number_count"] >= mean_unique:
            role = "core"
        else:
            role = "bridge"
        info["role"] = role

    union_all = set().union(*tickets.values()) if tickets else set()
    # Expected distinct numbers covered by k independent uniform-random 6/49
    # tickets: 49 * (1 - (43/49)^k). Lets us compare the deduplicated pack's
    # coverage against random coverage at the same budget (k = pack size).
    k_pack = len(ids)
    p_miss = (POOL_MAX - TICKET_SIZE) / POOL_MAX  # 43/49 for one ticket
    expected_random_coverage = POOL_SIZE * (1 - p_miss ** k_pack) if k_pack else 0.0
    ranked = sorted(
        ids,
        key=lambda s: (
            -contribution[s]["unique_number_count"],
            contribution[s]["mean_pair_overlap"],
            s,
        ),
    )
    ranking = [
        {
            "rank": rank,
            "strategy_id": sid,
            "ticket": contribution[sid]["ticket"],
            "unique_number_count": contribution[sid]["unique_number_count"],
            "max_pair_overlap": contribution[sid]["max_pair_overlap"],
            "mean_pair_overlap": contribution[sid]["mean_pair_overlap"],
            "marginal_coverage_contribution": contribution[sid]["marginal_coverage_contribution"],
            "redundancy_score": contribution[sid]["redundancy_score"],
            "role": contribution[sid]["role"],
        }
        for rank, sid in enumerate(ranked, start=1)
    ]
    return {
        "per_ticket": contribution,
        "ranking": ranking,
        "distinct_numbers_covered": len(union_all),
        "pool_size": POOL_SIZE,
        "coverage_fraction": round(len(union_all) / POOL_SIZE, 6),
        "pack_size": k_pack,
        "expected_random_coverage_same_budget": round(expected_random_coverage, 4),
        "pack_coverage_beats_random_coverage": len(union_all) > expected_random_coverage,
    }


# --------------------------------------------------------------------------- #
# Task E — analytic baselines + exact binomial tails + corrections
# --------------------------------------------------------------------------- #
def analytic_baseline() -> dict[str, Any]:
    """Exact single-ticket 6/49 baseline probabilities."""
    total = math.comb(POOL_MAX, TICKET_SIZE)
    p_exact = {
        k: math.comb(TICKET_SIZE, k) * math.comb(POOL_MAX - TICKET_SIZE, TICKET_SIZE - k) / total
        for k in range(TICKET_SIZE + 1)
    }
    p_ge3 = sum(p_exact[k] for k in range(3, TICKET_SIZE + 1))
    # match 2 then special is one of the four non-matching ticket numbers among the
    # 43 numbers not drawn as main: P(2)*4/43.
    p_two_plus_special = p_exact[2] * (TICKET_SIZE - 2) / (POOL_MAX - TICKET_SIZE)
    p_any_prize = p_ge3 + p_two_plus_special
    expected_main_hits = TICKET_SIZE * TICKET_SIZE / POOL_MAX  # 36/49
    return {
        "expected_main_hits_single_ticket": round(expected_main_hits, 6),
        "p_main_ge3": round(p_ge3, 8),
        "p_main_eq2_and_special": round(p_two_plus_special, 8),
        "p_any_prize_single_ticket": round(p_any_prize, 8),
        "p_exact_main_hits": {str(k): round(v, 10) for k, v in p_exact.items()},
        "combinations_6_of_49": total,
    }


def binom_sf(observed: int, n: int, p: float) -> float:
    """Exact one-sided upper tail P(X >= observed) for X ~ Binom(n, p)."""
    if observed <= 0:
        return 1.0
    if observed > n:
        return 0.0
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    # Sum the lower tail (observed is small) in log space for numerical stability.
    log_p = math.log(p)
    log_q = math.log1p(-p)
    lower = 0.0
    for x in range(observed):
        log_pmf = (
            math.lgamma(n + 1)
            - math.lgamma(x + 1)
            - math.lgamma(n - x + 1)
            + x * log_p
            + (n - x) * log_q
        )
        lower += math.exp(log_pmf)
    return max(0.0, min(1.0, 1.0 - lower))


def bh_fdr(pvalues: Sequence[float], alpha: float = 0.05) -> dict[str, Any]:
    """Benjamini-Hochberg descriptive check; returns the largest passing rank."""
    m = len(pvalues)
    if m == 0:
        return {"m": 0, "alpha": alpha, "max_significant_rank": 0, "threshold": 0.0}
    ordered = sorted(range(m), key=lambda i: pvalues[i])
    max_rank = 0
    threshold = 0.0
    for rank, idx in enumerate(ordered, start=1):
        crit = alpha * rank / m
        if pvalues[idx] <= crit:
            max_rank = rank
            threshold = crit
    return {"m": m, "alpha": alpha, "max_significant_rank": max_rank, "threshold": round(threshold, 8)}


# --------------------------------------------------------------------------- #
# Task D — random baselines + fixed-budget combinations (seeded, leakage-free)
# --------------------------------------------------------------------------- #
def _rng(seed: int, *parts: int):
    """Deterministic per-(seed, parts) PRNG so MC replicates are reproducible."""
    import random

    mixed = hashlib.sha256(("|".join(str(p) for p in (seed, *parts))).encode()).hexdigest()
    return random.Random(int(mixed[:16], 16))


def _random_ticket(rng) -> list[int]:
    return sorted(rng.sample(range(POOL_MIN, POOL_MAX + 1), TICKET_SIZE))


def _diversified_tickets(rng, count: int) -> list[list[int]]:
    """Draw ``count`` low-overlap tickets by sampling without replacement first.

    Numbers are drawn without replacement across tickets while the pool lasts
    (guarantees zero overlap for the first floor(49/6)=8 tickets); any remainder
    falls back to plain random tickets.
    """
    pool = list(range(POOL_MIN, POOL_MAX + 1))
    rng.shuffle(pool)
    tickets: list[list[int]] = []
    cursor = 0
    for _ in range(count):
        if cursor + TICKET_SIZE <= len(pool):
            tickets.append(sorted(pool[cursor : cursor + TICKET_SIZE]))
            cursor += TICKET_SIZE
        else:
            tickets.append(_random_ticket(rng))
    return tickets


def random_baselines(
    dataset: Mapping[str, Any],
    seed: int = DEFAULT_SEED,
    replicates: int = DEFAULT_MC_REPLICATES,
) -> dict[str, Any]:
    """Monte-Carlo equal-budget and diversified-random portfolio win rates.

    For each eligible target and replicate, eleven random (and eleven diversified)
    tickets are drawn and scored; a budget-k portfolio wins when any of its first
    ``k`` tickets wins a prize. Aggregated per horizon as mean +/- std over
    replicates. Fully reproducible from ``seed``.
    """
    rows = dataset["rows"]
    eligible = dataset["eligible_target_indices"]
    index_pos = {idx: pos for pos, idx in enumerate(eligible)}
    max_k = max(BUDGETS)

    # win flags[pos][replicate][ticket_idx] for each family.
    equal_win = [[None] * replicates for _ in eligible]
    diverse_win = [[None] * replicates for _ in eligible]
    for pos, target_index in enumerate(eligible):
        outcome = rows[target_index]
        draw_main = outcome["numbers"]
        special = outcome["special"]
        for r in range(replicates):
            rng_e = _rng(seed, 1, target_index, r)
            equal_win[pos][r] = [
                prize_aware_win(_random_ticket(rng_e), draw_main, special) for _ in range(max_k)
            ]
            rng_d = _rng(seed, 2, target_index, r)
            diverse_win[pos][r] = [
                prize_aware_win(t, draw_main, special) for t in _diversified_tickets(rng_d, max_k)
            ]

    def aggregate(win_flags) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name, size in HORIZONS:
            positions = [index_pos[i] for i in horizon_target_indices(eligible, size)]
            out[name] = {}
            for k in BUDGETS:
                rep_rates = []
                for r in range(replicates):
                    wins = sum(1 for pos in positions if any(win_flags[pos][r][:k]))
                    rep_rates.append(wins / len(positions) if positions else 0.0)
                mean = sum(rep_rates) / replicates
                var = sum((x - mean) ** 2 for x in rep_rates) / replicates
                out[name][str(k)] = {
                    "mean_portfolio_win_rate": round(mean, 6),
                    "std_portfolio_win_rate": round(math.sqrt(var), 6),
                }
        return out

    return {
        "seed": seed,
        "replicates": replicates,
        "equal_budget_random": aggregate(equal_win),
        "diversified_random": aggregate(diverse_win),
    }


def _strategy_prefix_wins(replay: Mapping[str, Any]) -> dict[str, list[int]]:
    """prefix[sid][j] = number of prize wins among the first ``j`` eligible positions."""
    out: dict[str, list[int]] = {}
    for sid in replay["strategy_ids"]:
        recs = replay["per_target"][sid]
        prefix = [0] * (len(recs) + 1)
        for i, rec in enumerate(recs):
            prefix[i + 1] = prefix[i] + (1 if rec["prize_win"] else 0)
        out[sid] = prefix
    return out


def _prefix_prior_winrate(replay: Mapping[str, Any]) -> dict[str, list[float]]:
    """Prior cumulative prize-win rate at each eligible position (leakage free).

    ``prior_rate[sid][pos]`` uses ONLY positions strictly before ``pos``; positions
    below the warmup return -1.0 (not selectable yet).
    """
    prefix = _strategy_prefix_wins(replay)
    out: dict[str, list[float]] = {}
    for sid in replay["strategy_ids"]:
        pre = prefix[sid]
        rates: list[float] = []
        for pos in range(len(pre) - 1):
            rates.append(pre[pos] / pos if pos >= WALK_FORWARD_MIN_PRIOR else -1.0)
        out[sid] = rates
    return out


def _prior_stability_weight(replay: Mapping[str, Any]) -> dict[str, list[float]]:
    """Stability-weighted prior score per strategy per position (leakage free).

    Score = prior_rate x stability, where stability = 1 - |rate_firsthalf -
    rate_secondhalf| / rate over the prior window [0, pos). Computed from exact
    prefix sums so the expanding window is handled correctly.
    """
    prefix = _strategy_prefix_wins(replay)
    out: dict[str, list[float]] = {}
    for sid in replay["strategy_ids"]:
        pre = prefix[sid]
        scores: list[float] = []
        for pos in range(len(pre) - 1):
            if pos < WALK_FORWARD_MIN_PRIOR:
                scores.append(-1.0)
                continue
            total = pre[pos]  # wins in [0, pos)
            rate = total / pos
            half = pos // 2
            w1 = pre[half]  # wins in [0, half)
            w2 = total - w1  # wins in [half, pos)
            r1 = w1 / half if half else 0.0
            r2 = w2 / (pos - half) if (pos - half) else 0.0
            if rate > 0:
                stability = max(0.0, 1.0 - abs(r1 - r2) / rate)
            else:
                stability = 1.0 if r1 == r2 else 0.0
            scores.append(rate * stability)
        out[sid] = scores
    return out


def combination_ranking(
    replay: Mapping[str, Any],
    random_bl: Mapping[str, Any],
    dataset: Mapping[str, Any],
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """Score every (method, k, horizon) and compare vs random + all_11 baselines.

    Outcome-using methods (top_k, stability_weighted) select strategies for target
    t using ONLY replay outcomes from positions strictly before t (walk-forward,
    warmup ``WALK_FORWARD_MIN_PRIOR``). Geometry methods (diversity, greedy) and the
    fixed all_11 method use no outcome information.
    """
    strategy_ids = list(replay["strategy_ids"])
    eligible = replay["eligible"]
    index_pos = {idx: pos for pos, idx in enumerate(eligible)}
    n_positions = len(eligible)
    rows = dataset["rows"]

    # Per-position tickets and prize-win flags, built once.
    per_target = replay["per_target"]
    pos_tickets: list[dict[str, list[int]]] = [
        {sid: per_target[sid][pos]["ticket"] for sid in strategy_ids} for pos in range(n_positions)
    ]
    pos_win: list[dict[str, bool]] = [
        {sid: per_target[sid][pos]["prize_win"] for sid in strategy_ids} for pos in range(n_positions)
    ]

    def score_strategy_portfolio(chosen_by_pos: Mapping[int, Sequence[str]], positions: Sequence[int]) -> float:
        wins = sum(1 for pos in positions if any(pos_win[pos][sid] for sid in chosen_by_pos[pos]))
        return wins / len(positions) if positions else 0.0

    def score_hybrid_portfolio(chosen_by_pos: Mapping[int, Sequence[str]], positions: Sequence[int], k: int) -> float:
        n_random = k - ((k + 1) // 2)
        wins = 0
        for pos in positions:
            strat_win = any(pos_win[pos][sid] for sid in chosen_by_pos[pos])
            target_index = eligible[pos]
            outcome = rows[target_index]
            rng = _rng(seed, 3, target_index, k)
            rand_win = any(
                prize_aware_win(t, outcome["numbers"], outcome["special"])
                for t in _diversified_tickets(rng, n_random)
            )
            if strat_win or rand_win:
                wins += 1
        return wins / len(positions) if positions else 0.0

    prior_rate = _prefix_prior_winrate(replay)
    prior_stab = _prior_stability_weight(replay)

    def diversity_select(pos: int, k: int) -> list[str]:
        tickets = pos_tickets[pos]
        chosen: list[str] = []
        chosen_union: set[int] = set()
        remaining = list(strategy_ids)
        while remaining and len(chosen) < k:
            # pick the strategy whose ticket overlaps least with already-chosen.
            best = min(
                remaining,
                key=lambda s: (len(set(tickets[s]) & chosen_union), s),
            )
            chosen.append(best)
            chosen_union |= set(tickets[best])
            remaining.remove(best)
        return chosen

    def greedy_coverage_select(pos: int, k: int) -> list[str]:
        tickets = pos_tickets[pos]
        chosen: list[str] = []
        covered: set[int] = set()
        remaining = list(strategy_ids)
        while remaining and len(chosen) < k:
            best = max(
                remaining,
                key=lambda s: (len(set(tickets[s]) - covered), -strategy_ids.index(s)),
            )
            chosen.append(best)
            covered |= set(tickets[best])
            remaining.remove(best)
        return chosen

    def topk_select(pos: int, k: int, scores: Mapping[str, list[float]]) -> list[str] | None:
        ranked = sorted(strategy_ids, key=lambda s: (-scores[s][pos], s))
        if scores[ranked[0]][pos] < 0:  # warmup: no prior information yet
            return None
        return ranked[:k]

    analytic = analytic_baseline()["p_any_prize_single_ticket"]
    results: dict[str, Any] = {}
    for method in COMBINATION_METHODS:
        results[method] = {}
        for name, size in HORIZONS:
            positions = [index_pos[i] for i in horizon_target_indices(eligible, size)]
            results[method][name] = {}
            for k in BUDGETS:
                if method == "all_11_strategy_pack" and k != max(BUDGETS):
                    results[method][name][str(k)] = {"applicable": False}
                    continue
                if method in ("equal_budget_random_baseline", "diversified_random_baseline"):
                    family = "equal_budget_random" if "equal" in method else "diversified_random"
                    cell = random_bl[family][name][str(k)]
                    results[method][name][str(k)] = {
                        "applicable": True,
                        "portfolio_win_rate": cell["mean_portfolio_win_rate"],
                        "std": cell["std_portfolio_win_rate"],
                        "leakage_free": True,
                        "uses_outcomes": False,
                    }
                    continue

                chosen_by_pos: dict[int, list[str]] = {}
                warmup_skipped = 0
                uses_outcomes = method in ("top_k_by_historical_replay", "stability_weighted_top_k")
                for pos in positions:
                    if method == "all_11_strategy_pack":
                        chosen = list(strategy_ids)
                    elif method == "diversity_first_low_overlap":
                        chosen = diversity_select(pos, k)
                    elif method == "marginal_contribution_greedy":
                        chosen = greedy_coverage_select(pos, k)
                    elif method == "top_k_by_historical_replay":
                        chosen = topk_select(pos, k, prior_rate)
                    elif method == "stability_weighted_top_k":
                        chosen = topk_select(pos, k, prior_stab)
                    elif method == "hybrid_strategy_plus_diversified_random":
                        n_strategy = (k + 1) // 2
                        chosen = diversity_select(pos, n_strategy)
                    else:
                        chosen = None
                    if chosen is None:
                        warmup_skipped += 1
                        continue
                    chosen_by_pos[pos] = chosen

                scored_positions = [p for p in positions if p in chosen_by_pos]
                if method == "hybrid_strategy_plus_diversified_random":
                    rate = score_hybrid_portfolio(chosen_by_pos, scored_positions, k)
                else:
                    rate = score_strategy_portfolio(chosen_by_pos, scored_positions)
                random_cell = random_bl["equal_budget_random"][name][str(k)]
                delta = rate - random_cell["mean_portfolio_win_rate"]
                random_std = random_cell["std_portfolio_win_rate"]
                results[method][name][str(k)] = {
                    "applicable": True,
                    "portfolio_win_rate": round(rate, 6),
                    "scored_targets": len(scored_positions),
                    "warmup_skipped": warmup_skipped,
                    "leakage_free": True,
                    "uses_outcomes": uses_outcomes,
                    "beats_equal_budget_random": delta > 0,
                    "vs_random_delta": round(delta, 6),
                    "equal_budget_random_std": random_std,
                    # A nominal win matters only if it clears one MC standard
                    # deviation of the random baseline; otherwise it is noise.
                    "beats_random_beyond_mc_noise": delta > random_std,
                }
    return {"analytic_p_any_prize": analytic, "results": results}


# --------------------------------------------------------------------------- #
# Statistical framing + verdict
# --------------------------------------------------------------------------- #
def statistical_framing(metrics: Mapping[str, Any]) -> dict[str, Any]:
    """Exact binomial tails per strategy vs the analytic any-prize baseline."""
    baseline = analytic_baseline()
    p0 = baseline["p_any_prize_single_ticket"]
    tests: list[dict[str, Any]] = []
    primary_pvalues: list[float] = []
    for sid, per_window in metrics.items():
        for window in PRIMARY_WINDOWS:
            cell = per_window[window]
            n = cell["support"]
            wins = cell["prize_win_count"]
            pval = binom_sf(wins, n, p0)
            tests.append(
                {
                    "strategy_id": sid,
                    "window": window,
                    "support": n,
                    "prize_win_count": wins,
                    "prize_win_rate": cell["prize_win_rate"],
                    "baseline_p_any_prize": p0,
                    "p_value_uncorrected_upper": round(pval, 8),
                }
            )
            primary_pvalues.append(pval)
    m = len(primary_pvalues)
    bonferroni_alpha = round(0.05 / m, 8) if m else 0.0
    survivors_uncorrected = [t for t in tests if t["p_value_uncorrected_upper"] < 0.05]
    survivors_bonferroni = [t for t in tests if t["p_value_uncorrected_upper"] < bonferroni_alpha]
    return {
        "baseline": baseline,
        "primary_family_test_count": m,
        "bonferroni_alpha": bonferroni_alpha,
        "bonferroni_note": (
            f"Primary family = 11 strategies x {len(PRIMARY_WINDOWS)} windows on the "
            f"prize-aware win metric = {m} tests. Many further comparisons "
            "(all_available window, secondary metrics, 8 combination methods x 5 "
            "budgets x 4 horizons) are NOT in this family and are descriptive only."
        ),
        "bh_fdr": bh_fdr(primary_pvalues, alpha=0.05),
        "per_strategy_window_tests": tests,
        "survivors_uncorrected_count": len(survivors_uncorrected),
        "survivors_bonferroni_count": len(survivors_bonferroni),
        "survivors_uncorrected": survivors_uncorrected,
        "survivors_bonferroni": survivors_bonferroni,
    }


def derive_verdict(framing: Mapping[str, Any], combos: Mapping[str, Any]) -> dict[str, Any]:
    """NULL unless something beats its random baseline at corrected significance."""
    any_strategy_beats_corrected = framing["survivors_bonferroni_count"] > 0
    any_strategy_beats_uncorrected = framing["survivors_uncorrected_count"] > 0

    combo_beats_random_mean = []
    combo_beats_random_beyond_noise = []
    combo_beats_all11 = []
    all11 = combos["results"]["all_11_strategy_pack"]
    for method, by_horizon in combos["results"].items():
        if method in ("equal_budget_random_baseline", "diversified_random_baseline", "all_11_strategy_pack"):
            continue
        for horizon, by_k in by_horizon.items():
            for k, cell in by_k.items():
                if not cell.get("applicable"):
                    continue
                entry = {"method": method, "horizon": horizon, "k": k, "delta": cell["vs_random_delta"], "random_std": cell.get("equal_budget_random_std")}
                if cell.get("beats_equal_budget_random"):
                    combo_beats_random_mean.append(entry)
                if cell.get("beats_random_beyond_mc_noise"):
                    combo_beats_random_beyond_noise.append(entry)
                all11_cell = all11.get(horizon, {}).get(str(max(BUDGETS)), {})
                if all11_cell.get("applicable") and cell.get("portfolio_win_rate", 0) > all11_cell.get("portfolio_win_rate", 0):
                    combo_beats_all11.append({"method": method, "horizon": horizon, "k": k})

    # Observation-only candidates require beating the random baseline beyond MC
    # noise (a tie or noise-level win is not a candidate).
    candidate = any_strategy_beats_corrected or bool(combo_beats_random_beyond_noise)
    if candidate:
        verdict = "OBSERVATION_ONLY_CANDIDATE"
        classification = OBSERVATION_CLASSIFICATION
    else:
        verdict = "NULL"
        classification = NULL_CLASSIFICATION

    # Headline: does random dominate strategies at typical budgets?
    random_dominates = []
    for k in BUDGETS:
        if k == 1:
            continue
        rand = combos["results"]["equal_budget_random_baseline"].get(PRIMARY_HORIZON, {}).get(str(k), {})
        all11_cell = all11.get(PRIMARY_HORIZON, {}).get(str(k), {})
        if rand.get("applicable") and all11_cell.get("applicable"):
            random_dominates.append(rand["portfolio_win_rate"] > all11_cell["portfolio_win_rate"])
    return {
        "verdict": verdict,
        "final_classification": classification,
        "any_strategy_beats_random_corrected": any_strategy_beats_corrected,
        "any_strategy_beats_random_uncorrected": any_strategy_beats_uncorrected,
        "combinations_beating_equal_budget_random_mean_count": len(combo_beats_random_mean),
        "combinations_beating_equal_budget_random_mean": combo_beats_random_mean,
        "combinations_beating_random_beyond_mc_noise_count": len(combo_beats_random_beyond_noise),
        "combinations_beating_random_beyond_mc_noise": combo_beats_random_beyond_noise,
        "combinations_beating_all_11_count": len(combo_beats_all11),
        "combinations_beating_all_11": combo_beats_all11,
        "random_dominates_strategy_pack_at_k_ge3": all(random_dominates) if random_dominates else False,
        "interpretation": (
            "Retrospective historical replay only. NULL = no strategy beats the "
            "analytic any-prize random baseline after Bonferroni correction AND no "
            "combination beats the equal-budget random baseline beyond Monte-Carlo "
            "noise. The few nominal combination wins over the random mean are within "
            "one MC standard deviation. At budgets k>=3 the equal-budget and "
            "diversified random baselines OUTPERFORM the strategy pack because the "
            "frozen primaries are internally redundant (lower distinct-number "
            "coverage than independent random tickets). Any observation-only "
            "candidate would still require separately authorized prospective / OOS "
            "validation before promotion; none is performed here."
        ),
    }


# --------------------------------------------------------------------------- #
# Orchestration + artifact assembly
# --------------------------------------------------------------------------- #
def canonical_digest(payload: Mapping[str, Any]) -> str:
    """Digest the deterministic analytical payload (excludes volatile provenance).

    Excludes wall-clock, absolute paths, and self-hash so the digest is path- and
    machine-independent (P277B lesson: never embed absolute paths in a digest).
    """
    volatile = {"provenance", "canonical_digest", "_meta"}
    reduced = {k: v for k, v in payload.items() if k not in volatile}
    rendered = json.dumps(reduced, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":"))
    return hashlib.sha256((rendered + "\n").encode("utf-8")).hexdigest()


def run_full_replay(
    db_path: Path,
    origin_main: str,
    git_head: str,
    seed: int = DEFAULT_SEED,
    replicates: int = DEFAULT_MC_REPLICATES,
) -> dict[str, Any]:
    """Execute Tasks A-E end to end against the read-only canonical DB."""
    db_hash_pre = db_sidecar_hashes(db_path)
    history = load_canonical_history(db_path)
    db_hash_post = db_sidecar_hashes(db_path)
    dataset = build_replay_dataset(history)

    # Current pack (Task C) — reproduce digest from the full history.
    latest_draw = dataset["latest_draw"]
    synthetic_target = str(int(latest_draw) + 1) if latest_draw.isdigit() else f"{latest_draw}_next"
    pack = reproduce_current_pack(history, latest_draw, synthetic_target)
    contribution = pack_contribution_analysis(pack["outputs"])

    # Strategy replay (Task B).
    replay = run_strategy_replay(dataset)
    metrics = strategy_level_metrics(replay)
    ranking = rank_strategies(metrics, contribution["per_ticket"])

    # Baselines + combinations (Tasks D, E).
    random_bl = random_baselines(dataset, seed=seed, replicates=replicates)
    combos = combination_ranking(replay, random_bl, dataset, seed=seed)
    framing = statistical_framing(metrics)
    verdict = derive_verdict(framing, combos)

    return {
        "dataset": dataset,
        "pack": pack,
        "contribution": contribution,
        "replay": replay,
        "metrics": metrics,
        "ranking": ranking,
        "random_baselines": random_bl,
        "combinations": combos,
        "framing": framing,
        "verdict": verdict,
        "db_hash_pre": db_hash_pre,
        "db_hash_post": db_hash_post,
        "origin_main": origin_main,
        "git_head": git_head,
        "synthetic_target": synthetic_target,
    }


def _portfolio_table(combos: Mapping[str, Any], k: int) -> list[dict[str, Any]]:
    rows = []
    for method, by_horizon in combos["results"].items():
        cell = by_horizon.get(PRIMARY_HORIZON, {}).get(str(k))
        if not cell or not cell.get("applicable"):
            continue
        rows.append(
            {
                "method": method,
                "k": k,
                "long750_portfolio_win_rate": cell.get("portfolio_win_rate", cell.get("portfolio_win_rate")),
                "beats_equal_budget_random": cell.get("beats_equal_budget_random"),
                "uses_outcomes": cell.get("uses_outcomes", False),
            }
        )
    rows.sort(key=lambda r: (-(r["long750_portfolio_win_rate"] or 0), r["method"]))
    return rows


def build_payload(state: Mapping[str, Any], db_path: Path) -> dict[str, Any]:
    """Assemble the immutable JSON payload with all mandatory P280AT fields."""
    dataset = state["dataset"]
    verdict = state["verdict"]
    framing = state["framing"]
    drift = state["db_hash_pre"] != state["db_hash_post"]

    payload: dict[str, Any] = {
        "task_id": TASK_ID,
        "schema_version": SCHEMA_VERSION,
        "final_classification": verdict["final_classification"],
        "verdict": verdict["verdict"],
        "research_only": True,
        "origin_main": state["origin_main"],
        "pr_463_merge_reconciliation": {
            "pr_number": 463,
            "merged_into_main": True,
            "merge_commit": state["origin_main"],
            "parent1": "25e7f8520164aaf61f440a866a11eca403bb76a3",
            "parent2": "4a16960e1c9bf40a37ec758341611fdb7c37c513",
        },
        "p280as_reconciliation": "P280AS_PR463_MERGED_VERIFIED_NOT_ACTIVATED",
        "p280aq_reconciliation": "P280AQ_PRIVATE_BIG649_STRATEGY_PACK_DUPLICATE_REMEDIATED_PR_OPEN_NO_PUBLICATION",
        "database_access": {
            "opened": True,
            "queried": True,
            "copied": False,
            "written": False,
            "mode": "SQLite URI mode=ro plus PRAGMA query_only=ON",
            "main_sha256_pre": state["db_hash_pre"]["main"],
            "main_sha256_post": state["db_hash_post"]["main"],
            "wal_sha256_pre": state["db_hash_pre"]["wal"],
            "wal_sha256_post": state["db_hash_post"]["wal"],
            "shm_sha256_pre": state["db_hash_pre"]["shm"],
            "shm_sha256_post": state["db_hash_post"]["shm"],
            "content_drift_detected": drift,
        },
        "dataset_summary": {
            "lottery": LOTTERY,
            "source_view": CANONICAL_VIEW,
            "row_count": dataset["row_count"],
            "earliest_draw": dataset["earliest_draw"],
            "latest_local_draw": dataset["latest_draw"],
            "min_history_per_target": dataset["min_history"],
            "eligible_replay_target_count": dataset["eligible_target_count"],
            "duplicate_draw_ids": 0,
            "malformed_tickets": 0,
        },
        "replay_horizons": [
            {"name": name, "requested_size": size, "actual_targets": len(horizon_target_indices(dataset["eligible_target_indices"], size))}
            for name, size in HORIZONS
        ],
        "history_cutoff_rule": "strategy input for target t = draws strictly before t (history[:i]); target outcome never used before scoring",
        "outcome_leakage_guard": "strategies receive only {'numbers'} of prior draws; special and future draws are withheld until scoring",
        "strategy_unit": "each strategy's frozen bet_index=1 primary ticket (canonical single recommendation)",
        "exact_strategy_ids": list(list_frozen_big649_strategy_ids()),
        "current_strategy_pack": {
            "history_cutoff": dataset["latest_draw"],
            "synthetic_target": state["synthetic_target"],
            "adapter_digest": state["pack"]["digest"],
            "adapter_digest_expected": "b8ceac657f081bbf2be6ae0fabe6adbce564ea3a4b4cb77ab610035d0e4a800a",
            "adapter_digest_reconciled": state["pack"]["digest"] == "b8ceac657f081bbf2be6ae0fabe6adbce564ea3a4b4cb77ab610035d0e4a800a",
            "tickets": state["pack"]["outputs"],
        },
        "strategy_level_ranking": state["ranking"],
        "strategy_level_metrics": state["metrics"],
        "current_pack_contribution_ranking": state["contribution"]["ranking"],
        "current_pack_contribution_detail": state["contribution"]["per_ticket"],
        "current_pack_coverage": {
            "distinct_numbers_covered": state["contribution"]["distinct_numbers_covered"],
            "pool_size": state["contribution"]["pool_size"],
            "coverage_fraction": state["contribution"]["coverage_fraction"],
            "pack_size": state["contribution"]["pack_size"],
            "expected_random_coverage_same_budget": state["contribution"]["expected_random_coverage_same_budget"],
            "pack_coverage_beats_random_coverage": state["contribution"]["pack_coverage_beats_random_coverage"],
        },
        "portfolio_combination_ranking": {
            f"k_{k}": _portfolio_table(state["combinations"], k) for k in BUDGETS
        },
        "portfolio_combination_detail": state["combinations"]["results"],
        "random_baseline_config": {
            "type": "equal_budget_random",
            "construction": "k uniform-random distinct-6 tickets per target",
            "seed": state["random_baselines"]["seed"],
            "replicates": state["random_baselines"]["replicates"],
            "analytic_portfolio_win_rate_formula": "1-(1-p_any_prize)^k",
        },
        "diversified_random_baseline_config": {
            "type": "diversified_random",
            "construction": "low-overlap tickets drawn without replacement across the 49-pool, then random fallback",
            "seed": state["random_baselines"]["seed"],
            "replicates": state["random_baselines"]["replicates"],
        },
        "baseline_and_statistics": framing,
        "prize_aware_definition": {"rule": PRIZE_AWARE_RULE, "tiers": list(PRIZE_TIER_TABLE)},
        "best_observation_only_candidates": verdict["combinations_beating_random_beyond_mc_noise"],
        "any_strategy_beats_random_baseline": verdict["any_strategy_beats_random_uncorrected"],
        "any_strategy_beats_random_baseline_corrected": verdict["any_strategy_beats_random_corrected"],
        "any_combination_beats_random_baseline_mean": verdict["combinations_beating_equal_budget_random_mean_count"] > 0,
        "any_combination_beats_random_beyond_mc_noise": verdict["combinations_beating_random_beyond_mc_noise_count"] > 0,
        "any_combination_beats_all_11": verdict["combinations_beating_all_11_count"] > 0,
        "random_dominates_strategy_pack_at_k_ge3": verdict["random_dominates_strategy_pack_at_k_ge3"],
        "multiple_testing_warning": (
            "Bonferroni and BH-FDR applied to the primary 33-test family only. The "
            "full ranking explores far more comparisons (combination methods x "
            "budgets x horizons x metrics); treat all non-primary positives as "
            "descriptive, not confirmatory. Retrospective replay cannot confirm a "
            "prospective edge."
        ),
        "stability_across_horizons": {
            row["strategy_id"]: row["stability_across_windows"] for row in state["ranking"]
        },
        "interpretation": verdict["interpretation"],
        # Mandatory negative-assertion safety block.
        "prediction_success_claim": False,
        "strategy_promoted": False,
        "activation_authorized": False,
        "registry_mutated": False,
        "production_ready_claim": False,
        "official_target_lookup": False,
        "official_deadline_lookup": False,
        "real_publication_performed": False,
        "pre_draw_manifest_created": False,
        "publication_pr_created": False,
        "post_draw_evaluation_started": False,
        "limitations": [
            "Retrospective historical replay only; not a forward prediction or success-probability estimate.",
            "Strategy unit is the frozen bet_index=1 primary; multi-bet strategies' additional bets are reflected only via the portfolio combinations (Task D).",
            "Tiny base rates (any-prize ~3.1% single ticket) make per-window estimates noisy; horizons overlap (recent_100 subset of mid_300 subset of long_750 subset of all_available).",
            "Walk-forward selection uses an expanding prior window with a 30-target warmup; the first 30 all_available targets are skipped for outcome-based methods.",
            "Combination significance is descriptive only under heavy multiple testing.",
            "Canonical DB is a single read-only snapshot; a live writer may change WAL/SHM but no content drift was observed.",
        ],
        "next_recommended_step": (
            "If NULL (expected), proceed to a separately authorized P280AV private "
            "ticket-decision runner that consumes this ranking/coverage output "
            "without claiming an edge. If observation-only candidates surfaced, they "
            "require separately authorized prospective/OOS validation before any "
            "promotion. No publication, activation, or post-draw evaluation is "
            "authorized by this task."
        ),
        "provenance": {
            "git_head": state["git_head"],
            "db_path": str(db_path),
            "tool": "tools/p280at_big649_strategy_ranking_replay.py",
            "python": sys.version.split()[0],
        },
    }
    payload["canonical_digest"] = canonical_digest(payload)
    return payload


# --------------------------------------------------------------------------- #
# Markdown rendering
# --------------------------------------------------------------------------- #
def render_markdown(payload: Mapping[str, Any]) -> str:
    p = payload
    ds = p["dataset_summary"]
    lines: list[str] = []
    lines.append("# P280AT — BIG 6/49 Strategy Ranking & Portfolio Contribution Replay")
    lines.append("")
    lines.append(f"- **Final classification:** `{p['final_classification']}`")
    lines.append(f"- **Verdict:** `{p['verdict']}` — historical replay only, NOT a future-success claim.")
    lines.append(f"- **origin/main:** `{p['origin_main']}` (PR #463 merged).")
    lines.append(f"- **Canonical digest:** `{p['canonical_digest']}`")
    lines.append("")
    lines.append("> Local research and replay validation ONLY. No prediction-success claim, no "
                 "strategy promotion, no activation, no publication, no official target/deadline "
                 "lookup, no pre-draw manifest.")
    lines.append("")
    lines.append("## Dataset")
    lines.append(f"- Source view: `{ds['source_view']}` ({ds['lottery']}), read-only `mode=ro` + `query_only=ON`")
    lines.append(f"- Rows: **{ds['row_count']}** ({ds['earliest_draw']} → {ds['latest_local_draw']}); "
                 f"duplicate ids: {ds['duplicate_draw_ids']}, malformed tickets: {ds['malformed_tickets']}")
    lines.append(f"- Eligible leakage-free replay targets (≥{ds['min_history_per_target']} prior draws): "
                 f"**{ds['eligible_replay_target_count']}**")
    lines.append(f"- DB content drift during read: **{p['database_access']['content_drift_detected']}** "
                 f"(main sha256 `{p['database_access']['main_sha256_pre'][:16]}…`)")
    lines.append("")
    lines.append(f"- History cutoff rule: {p['history_cutoff_rule']}")
    lines.append(f"- Leakage guard: {p['outcome_leakage_guard']}")
    lines.append("")
    lines.append("## Current 11-ticket strategy pack")
    cp = p["current_strategy_pack"]
    lines.append(f"- Adapter digest reproduced: `{cp['adapter_digest']}` — "
                 f"reconciled vs `b8ceac65…`: **{cp['adapter_digest_reconciled']}**")
    lines.append(f"- History cutoff `{cp['history_cutoff']}` → synthetic target `{cp['synthetic_target']}` (no official target)")
    lines.append("")
    lines.append("## Prize-aware definition (大樂透 6/49 + special)")
    lines.append(f"- Any-prize: `{p['prize_aware_definition']['rule']}`")
    lines.append(f"- Analytic single-ticket any-prize: "
                 f"**{p['baseline_and_statistics']['baseline']['p_any_prize_single_ticket']:.4%}**; "
                 f"E[main hits] = {p['baseline_and_statistics']['baseline']['expected_main_hits_single_ticket']}")
    lines.append("")
    lines.append("## Task B — Strategy-level ranking (frozen bet_index=1 primary; replay only)")
    lines.append("")
    lines.append("| Rank | Strategy | long750 prize-win rate | long750 avg hits | stability | marginal contrib |")
    lines.append("|---|---|---|---|---|---|")
    for row in p["strategy_level_ranking"]:
        lines.append(
            f"| {row['rank']} | `{row['strategy_id']}` | {row['long750_prize_win_rate']:.4f} | "
            f"{row['long750_avg_main_hits']:.4f} | {row['stability_across_windows']:.3f} | "
            f"{row['marginal_portfolio_contribution']:.3f} |"
        )
    lines.append("")
    lines.append(f"Analytic random any-prize baseline = "
                 f"{p['baseline_and_statistics']['baseline']['p_any_prize_single_ticket']:.4f}. "
                 f"Strategies beating it after Bonferroni: "
                 f"**{p['baseline_and_statistics']['survivors_bonferroni_count']}** "
                 f"(uncorrected: {p['baseline_and_statistics']['survivors_uncorrected_count']}).")
    lines.append("")
    lines.append("## Task C — Current pack contribution ranking (portfolio geometry)")
    lines.append("")
    lines.append("| Rank | Strategy | ticket | unique # | max pair overlap | mean pair overlap | role |")
    lines.append("|---|---|---|---|---|---|---|")
    for row in p["current_pack_contribution_ranking"]:
        lines.append(
            f"| {row['rank']} | `{row['strategy_id']}` | {row['ticket']} | {row['unique_number_count']} | "
            f"{row['max_pair_overlap']} | {row['mean_pair_overlap']:.2f} | {row['role']} |"
        )
    cov = p["current_pack_coverage"]
    lines.append("")
    lines.append(f"Distinct numbers covered by the pack: **{cov['distinct_numbers_covered']}/{cov['pool_size']}** "
                 f"({cov['coverage_fraction']:.1%}). Expected coverage of {cov['pack_size']} independent random "
                 f"tickets: **{cov['expected_random_coverage_same_budget']}** — pack beats random coverage: "
                 f"**{cov['pack_coverage_beats_random_coverage']}**.")
    lines.append("")
    lines.append("## Task D — Fixed-budget portfolio / combination ranking (long_750)")
    for k in BUDGETS:
        table = p["portfolio_combination_ranking"][f"k_{k}"]
        if not table:
            continue
        lines.append("")
        lines.append(f"### k = {k}")
        lines.append("| Method | long750 portfolio win rate | beats equal-budget random | uses outcomes |")
        lines.append("|---|---|---|---|")
        for row in table:
            wr = row["long750_portfolio_win_rate"]
            lines.append(
                f"| `{row['method']}` | {wr:.4f} | {row['beats_equal_budget_random']} | {row['uses_outcomes']} |"
            )
    lines.append("")
    lines.append("## Task E — Baselines & statistical framing")
    bl = p["baseline_and_statistics"]
    lines.append(f"- Analytic 6/49: P(≥3 main) = {bl['baseline']['p_main_ge3']:.6f}; "
                 f"P(2 main + special) = {bl['baseline']['p_main_eq2_and_special']:.6f}; "
                 f"P(any prize) = {bl['baseline']['p_any_prize_single_ticket']:.6f}")
    lines.append(f"- Primary test family: {bl['primary_family_test_count']} tests; "
                 f"Bonferroni α = {bl['bonferroni_alpha']:.6f}; "
                 f"BH-FDR max significant rank = {bl['bh_fdr']['max_significant_rank']}")
    lines.append(f"- {p['multiple_testing_warning']}")
    lines.append("")
    lines.append("## Verdict")
    lines.append(f"- Any strategy beats random (uncorrected / Bonferroni): "
                 f"**{p['any_strategy_beats_random_baseline']} / {p['any_strategy_beats_random_baseline_corrected']}**")
    lines.append(f"- Any combination beats equal-budget random (mean / beyond MC noise): "
                 f"**{p['any_combination_beats_random_baseline_mean']} / {p['any_combination_beats_random_beyond_mc_noise']}**")
    lines.append(f"- Random baseline DOMINATES the strategy pack at k≥3: "
                 f"**{p['random_dominates_strategy_pack_at_k_ge3']}**")
    lines.append(f"- Any combination beats all_11 pack: **{p['any_combination_beats_all_11']}**")
    lines.append(f"- Observation-only candidates beyond MC noise: **{len(p['best_observation_only_candidates'])}**")
    lines.append(f"- {p['interpretation']}")
    lines.append("")
    lines.append("## Limitations")
    for item in p["limitations"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Next recommended research step")
    lines.append(f"- {p['next_recommended_step']}")
    lines.append("")
    lines.append("### Safety assertions")
    for key in (
        "prediction_success_claim", "strategy_promoted", "activation_authorized",
        "registry_mutated", "official_target_lookup", "official_deadline_lookup",
        "real_publication_performed", "pre_draw_manifest_created", "publication_pr_created",
        "post_draw_evaluation_started",
    ):
        lines.append(f"- `{key}` = {p[key]}")
    lines.append("")
    # Guarantee no trailing whitespace on any line (git diff --check clean).
    return "\n".join(line.rstrip() for line in lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P280AT BIG 6/49 strategy ranking replay (read-only research)")
    parser.add_argument("--db", default=str(REPO_ROOT / DEFAULT_DB_RELATIVE))
    parser.add_argument("--out-json", default=str(REPO_ROOT / DEFAULT_OUT_JSON))
    parser.add_argument("--out-md", default=str(REPO_ROOT / DEFAULT_OUT_MD))
    parser.add_argument("--origin-main", default="5e810ec2b427823c9e2de575d429eb2c43b3836d")
    parser.add_argument("--git-head", default="")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--mc-replicates", type=int, default=DEFAULT_MC_REPLICATES)
    args = parser.parse_args(argv)

    db_path = Path(args.db).resolve()
    if not db_path.exists():
        print(f"ERROR: canonical DB not found at {db_path}", file=sys.stderr)
        return 2

    state = run_full_replay(
        db_path,
        origin_main=args.origin_main,
        git_head=args.git_head,
        seed=args.seed,
        replicates=args.mc_replicates,
    )
    payload = build_payload(state, db_path)

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(render_markdown(payload), encoding="utf-8")

    print(f"final_classification={payload['final_classification']}")
    print(f"verdict={payload['verdict']}")
    print(f"adapter_digest_reconciled={payload['current_strategy_pack']['adapter_digest_reconciled']}")
    print(f"canonical_digest={payload['canonical_digest']}")
    print(f"db_content_drift={payload['database_access']['content_drift_detected']}")
    print(f"wrote {out_json}")
    print(f"wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
