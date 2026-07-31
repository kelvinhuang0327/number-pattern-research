"""P280AM-R BIG 6/49 local historical-replay research (research-only).

This module replays the exact eleven frozen BIG 6/49 strategy outputs over real
historical 大樂透 draws using the merged P280AJ no-DB strategy-output adapter. It
measures replay performance, quantifies duplicate-ticket reduction (frozen
``bet_index=1`` primaries vs. remediated candidate selection), evaluates
fixed-budget strategy combinations, and compares every combination against
equal-budget and diversified-random baselines under appropriate leakage
guards.

Hard scope (research-only):

* Read-only access to the canonical production DB via a SQLite ``mode=ro`` URI
  plus ``PRAGMA query_only=ON``; one connection, one read snapshot. The DB is
  never written, copied, or mutated.
* For every replay target draw the strategy input history contains only draws
  strictly before that draw. The target outcome is used only for post-generation
  scoring and is never fed to the adapter.
* No real publication, no pre-draw manifest, no official target/deadline lookup,
  no publication PR, no post-draw evaluation of a real publication, no strategy
  promotion, no activation, no registry mutation, no production write.

Layering note (P280AJ reconciliation): the adapter's per-strategy candidate
selection is deterministic canonical-order first-unclaimed selection and is NOT
outcome-aware or historical-best. This module never changes that. The research
``top_k_by_historical_training_only`` combination is a *separate observation
layer* that selects a SUBSET of strategies using walk-forward (expanding-window)
training on draws strictly before each evaluation target; it never feeds back
into the adapter, registry, or any production path.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sqlite3
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.big649_no_db_strategy_output_adapter import (  # noqa: E402
    MIN_HISTORY,
    enumerate_strategy_candidates,
    frozen_primary_outputs,
    frozen_primary_duplicate_groups,
    generate_strategy_outputs_no_db,
    list_frozen_big649_strategy_ids,
)

TASK_ID = "P280AM-R"
ORIGIN_MAIN = "25e7f8520164aaf61f440a866a11eca403bb76a3"
SCHEMA_VERSION = "p280amr_big649_local_replay_research_v1"

TICKET_SIZE = 6
NUMBER_MIN = 1
NUMBER_MAX = 49
UNIVERSE = NUMBER_MAX - NUMBER_MIN + 1

CANONICAL_VIEW = "draws_big_lotto_canonical_main"
LOTTERY_TYPE = "BIG_LOTTO"

# Decision windows expressed as the number of most-recent eligible target draws.
DEFAULT_HORIZONS: tuple[tuple[str, int], ...] = (
    ("short", 100),
    ("medium", 300),
    ("long", 750),
)

RANDOM_SEED = 42
RANDOM_REPLICATES = 200
K_VALUES: tuple[int, ...] = (1, 3, 5, 7, 11)
DIVERSITY_K: tuple[int, ...] = (3, 5, 7, 11)
FAMILY_CAP = 1
BOOTSTRAP_RESAMPLES = 2000

# Derived (NOT authoritative) family keywords, in priority order. Used only for
# the exploratory per-family-cap combination, which is explicitly labelled as a
# keyword-derived heuristic.
FAMILY_KEYWORDS: tuple[str, ...] = (
    "ts3",
    "fourier",
    "echo",
    "cold",
    "coldpool",
    "markov",
    "deviation",
    "triple",
)


class ReplayDatasetError(RuntimeError):
    """Raised when the replay dataset gate fails closed."""


# ---------------------------------------------------------------------------
# Read-only dataset loader + gate
# ---------------------------------------------------------------------------
def default_db_path() -> Path:
    """Resolve the canonical read-only DB path.

    Prefers a DB inside this worktree (absent for an isolated worktree because
    the file is git-ignored), then falls back to the canonical repository DB.
    """
    local = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
    if local.exists():
        return local
    canonical = Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db")
    return canonical


def _parse_numbers(raw: str) -> list[int]:
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ReplayDatasetError("numbers payload is not a list")
    return [int(value) for value in parsed]


def load_canonical_big649_draws(db_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load canonical BIG 6/49 draws strictly read-only.

    Returns the chronologically-sorted draws and a DB-access record. Uses a
    ``mode=ro`` URI, asserts ``PRAGMA query_only`` is enabled, and reads the
    production-blessed canonical view inside one deferred read transaction.
    """
    uri = f"file:{db_path}?mode=ro"
    access = {
        "db_path": str(db_path),
        "uri": uri,
        "mode_ro": True,
        "query_only_enabled": None,
        "opened": True,
        "queried": True,
        "copied": False,
        "written": False,
        "source_object": CANONICAL_VIEW,
    }
    con = sqlite3.connect(uri, uri=True)
    try:
        cur = con.cursor()
        cur.execute("PRAGMA query_only=ON")
        cur.execute("PRAGMA query_only")
        access["query_only_enabled"] = bool(cur.fetchone()[0])
        if not access["query_only_enabled"]:
            raise ReplayDatasetError("query_only could not be enabled; refusing to proceed")
        cur.execute("BEGIN")  # one consistent read snapshot
        cur.execute(
            f"SELECT draw, date, numbers, special FROM {CANONICAL_VIEW}"
        )
        rows = cur.fetchall()
        con.rollback()
    finally:
        con.close()

    draws: list[dict[str, Any]] = []
    for draw, date, numbers, special in rows:
        draws.append(
            {
                "draw": str(draw),
                "draw_int": int(draw),
                "date": str(date),
                "numbers": sorted(_parse_numbers(numbers)),
                "special": int(special),
            }
        )
    draws.sort(key=lambda row: (row["date"], row["draw_int"]))
    return draws, access


def validate_dataset(draws: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Fail-closed dataset gate: ordering, uniqueness, and ticket validity."""
    if len(draws) < MIN_HISTORY + 1:
        raise ReplayDatasetError(
            f"insufficient history: {len(draws)} draws < MIN_HISTORY+1 ({MIN_HISTORY + 1})"
        )
    draw_ids = [row["draw"] for row in draws]
    dates = [row["date"] for row in draws]
    if len(set(draw_ids)) != len(draw_ids):
        raise ReplayDatasetError("duplicate draw IDs present")
    if len(set(dates)) != len(dates):
        raise ReplayDatasetError("duplicate draw dates present")

    # Ordering must be unambiguous: chronological date order must agree with the
    # ROC draw-id integer order. Otherwise replay history is ill-defined -> STOP.
    by_draw_int = sorted(draws, key=lambda row: row["draw_int"])
    if [row["draw"] for row in by_draw_int] != draw_ids:
        raise ReplayDatasetError("draw-id integer order disagrees with date order; ordering ambiguous")

    special_in_main = 0
    for index, row in enumerate(draws):
        nums = row["numbers"]
        if len(nums) != TICKET_SIZE or len(set(nums)) != TICKET_SIZE:
            raise ReplayDatasetError(f"draw[{index}] {row['draw']} is not six distinct numbers")
        if min(nums) < NUMBER_MIN or max(nums) > NUMBER_MAX:
            raise ReplayDatasetError(f"draw[{index}] {row['draw']} numbers outside 1..49")
        if not (NUMBER_MIN <= row["special"] <= NUMBER_MAX):
            raise ReplayDatasetError(f"draw[{index}] {row['draw']} special outside 1..49")
        if row["special"] in set(nums):
            special_in_main += 1

    return {
        "row_count": len(draws),
        "first_draw": draws[0]["draw"],
        "first_date": draws[0]["date"],
        "last_draw": draws[-1]["draw"],
        "last_date": draws[-1]["date"],
        "duplicate_draw_ids": 0,
        "duplicate_dates": 0,
        "ordering": "DATE_ORDER_EQUALS_DRAW_INT_ORDER",
        "invalid_tickets": 0,
        "special_in_main_count": special_in_main,
        "min_history": MIN_HISTORY,
        "eligible_target_count": len(draws) - MIN_HISTORY,
    }


def resolve_horizons(eligible_count: int) -> list[dict[str, Any]]:
    """Resolve replay horizons, capping each to available eligible targets."""
    resolved: list[dict[str, Any]] = []
    for name, requested in DEFAULT_HORIZONS:
        applied = min(requested, eligible_count)
        resolved.append(
            {
                "name": name,
                "requested_targets": requested,
                "applied_targets": applied,
                "capped": applied < requested,
            }
        )
    return resolved


# ---------------------------------------------------------------------------
# Scoring (BIG prize-aware endpoint)
# ---------------------------------------------------------------------------
def score_ticket(ticket: Sequence[int], actual_main: Sequence[int], special: int) -> dict[str, Any]:
    """Score one ticket against an actual draw under the BIG prize-aware rule."""
    ticket_set = set(ticket)
    hit_count = len(ticket_set & set(actual_main))
    special_hit = 1 if special in ticket_set else 0
    prize_win = hit_count >= 3 or (hit_count == 2 and special_hit == 1)
    return {"hit_count": hit_count, "special_hit": special_hit, "prize_aware_win": prize_win}


RESOLVED_STATUS = "RESOLVED_11_UNIQUE"
UNRESOLVED_STATUS = "UNRESOLVED_DUPLICATE_BEST_EFFORT"


def _selection_rule_remediated(
    enumerated: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], str, int]:
    """Best-effort canonical-order first-unclaimed candidate selection.

    Mirrors the adapter's ``resolve_unique_strategy_outputs`` rule (first source
    candidate whose complete ticket is unclaimed by an earlier strategy). When a
    strategy exhausts its candidates without an unclaimed ticket, this replay
    instrument falls back to that strategy's own first candidate as a forced
    duplicate and flags the target ``UNRESOLVED_DUPLICATE_BEST_EFFORT`` (the
    publication adapter would instead ``UNRESOLVED_DUPLICATE_STOP`` here).

    When all eleven resolve to distinct tickets, the output is byte-identical to
    the adapter's ``generate_strategy_outputs_no_db`` (asserted in tests).
    Returns ``(outputs, status, resolved_unique_count)``.
    """
    claimed: set[tuple[int, ...]] = set()
    outputs: list[dict[str, Any]] = []
    forced = 0
    for record in enumerated:
        chosen = None
        for candidate in record["candidates"]:
            key = tuple(candidate)
            if key not in claimed:
                claimed.add(key)
                chosen = candidate
                break
        if chosen is None:
            chosen = list(record["candidates"][0])  # forced duplicate fallback
            forced += 1
        outputs.append({"strategy_id": record["strategy_id"], "predicted_main_numbers": chosen})
    unique = len({tuple(o["predicted_main_numbers"]) for o in outputs})
    status = RESOLVED_STATUS if forced == 0 and unique == len(outputs) else UNRESOLVED_STATUS
    return outputs, status, unique


# ---------------------------------------------------------------------------
# Replay engine (leakage-free)
# ---------------------------------------------------------------------------
def replay_one_target(
    draws: Sequence[Mapping[str, Any]],
    target_index: int,
) -> dict[str, Any]:
    """Replay all eleven strategies for one target using strictly-prior history."""
    if target_index < MIN_HISTORY:
        raise ReplayDatasetError(f"target_index {target_index} has < {MIN_HISTORY} prior draws")
    target = draws[target_index]
    history = draws[:target_index]

    target_id = target["draw"]
    history_ids = {row["draw"] for row in history}
    if target_id in history_ids:  # defensive outcome-leakage guard
        raise ReplayDatasetError("target draw present in history input")

    adapter_history = [{"draw": row["draw"], "numbers": list(row["numbers"])} for row in history]
    cutoff = history[-1]["draw"]
    target_metadata = {"target_draw": str(target_id), "synthetic": True}

    enumerated = enumerate_strategy_candidates(adapter_history, cutoff, target_metadata)
    frozen_primary = [
        {"strategy_id": rec["strategy_id"], "predicted_main_numbers": rec["frozen_primary_ticket"]}
        for rec in enumerated
    ]
    remediated, remediated_status, remediated_unique = _selection_rule_remediated(enumerated)

    actual_main = target["numbers"]
    special = target["special"]

    def _score_block(outputs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        scored = []
        for rec in outputs:
            sc = score_ticket(rec["predicted_main_numbers"], actual_main, special)
            scored.append(
                {
                    "strategy_id": rec["strategy_id"],
                    "ticket": list(rec["predicted_main_numbers"]),
                    **sc,
                }
            )
        return scored

    frozen_scored = _score_block(frozen_primary)
    remediated_scored = _score_block(remediated)

    frozen_tickets = [tuple(rec["predicted_main_numbers"]) for rec in frozen_primary]
    remediated_tickets = [tuple(rec["predicted_main_numbers"]) for rec in remediated]

    return {
        "target_index": target_index,
        "target_draw": target_id,
        "target_date": target["date"],
        "history_cutoff": cutoff,
        "history_len": len(history),
        "actual_main": list(actual_main),
        "actual_special": special,
        "frozen": frozen_scored,
        "remediated": remediated_scored,
        "remediated_resolution_status": remediated_status,
        "frozen_unique_ticket_count": len(set(frozen_tickets)),
        "remediated_unique_ticket_count": len(set(remediated_tickets)),
        "frozen_duplicate_group_count": sum(
            1
            for group in _group_duplicates(frozen_primary)
        ),
        "frozen_duplicate_groups": _group_duplicates(frozen_primary),
    }


def _group_duplicates(outputs: Sequence[Mapping[str, Any]]) -> list[list[str]]:
    ticket_to_ids: dict[tuple[int, ...], list[str]] = {}
    for rec in outputs:
        ticket_to_ids.setdefault(tuple(rec["predicted_main_numbers"]), []).append(rec["strategy_id"])
    return sorted(
        (sorted(ids) for ids in ticket_to_ids.values() if len(ids) > 1),
        key=lambda ids: ids[0],
    )


def run_replay(
    draws: Sequence[Mapping[str, Any]],
    target_indices: Sequence[int],
    progress: bool = False,
) -> list[dict[str, Any]]:
    """Replay every requested target index (chronological order)."""
    records: list[dict[str, Any]] = []
    total = len(target_indices)
    for position, target_index in enumerate(target_indices):
        records.append(replay_one_target(draws, target_index))
        if progress and (position % 50 == 0 or position == total - 1):
            print(f"  replay {position + 1}/{total}", file=sys.stderr)
    return records


# ---------------------------------------------------------------------------
# Portfolio scoring + combinations
# ---------------------------------------------------------------------------
def score_portfolio(
    tickets: Sequence[Sequence[int]],
    actual_main: Sequence[int],
    special: int,
) -> dict[str, Any]:
    """Fixed-budget portfolio metrics for a draw (draw-level any-win)."""
    if not tickets:
        return {
            "prize_aware_win": False,
            "best_hit_count": 0,
            "mean_hit_count": 0.0,
            "coverage": 0,
            "duplicate_ticket_count": 0,
            "budget": 0,
        }
    per = [score_ticket(t, actual_main, special) for t in tickets]
    union: set[int] = set()
    for t in tickets:
        union |= set(t)
    keys = [tuple(sorted(t)) for t in tickets]
    duplicate_ticket_count = len(keys) - len(set(keys))
    return {
        "prize_aware_win": any(p["prize_aware_win"] for p in per),
        "best_hit_count": max(p["hit_count"] for p in per),
        "mean_hit_count": sum(p["hit_count"] for p in per) / len(per),
        "coverage": len(union),
        "duplicate_ticket_count": duplicate_ticket_count,
        "budget": len(tickets),
    }


def diversity_greedy_order(tickets: Sequence[Sequence[int]]) -> list[int]:
    """Greedy overlap-minimizing selection order over ticket indices (deterministic).

    Seeded by canonical index 0; each step appends the not-yet-selected ticket
    with the smallest summed pairwise number overlap to the already-selected set.
    Ties resolve to the lowest index (ascending scan, strict-improve replacement).
    """
    pool = [list(t) for t in tickets]
    if not pool:
        return []
    order = [0]
    selected = {0}
    while len(order) < len(pool):
        best_idx = None
        best_overlap = None
        for idx in range(len(pool)):
            if idx in selected:
                continue
            overlap = sum(len(set(pool[idx]) & set(pool[s])) for s in order)
            if best_overlap is None or overlap < best_overlap:
                best_overlap = overlap
                best_idx = idx
        order.append(best_idx)
        selected.add(best_idx)
    return order


def diversity_greedy_select(tickets: Sequence[Sequence[int]], k: int) -> list[list[int]]:
    """Greedily select k tickets minimizing pairwise number overlap (deterministic)."""
    pool = [list(t) for t in tickets]
    order = diversity_greedy_order(pool)
    return [pool[i] for i in order[:k]]


def assign_family(strategy_id: str) -> str:
    lowered = strategy_id.lower()
    for keyword in FAMILY_KEYWORDS:
        if keyword in lowered:
            return keyword
    return "other"


def per_family_cap_select(
    remediated: Sequence[Mapping[str, Any]], cap: int = FAMILY_CAP
) -> list[list[int]]:
    """Select tickets honouring a derived per-family cap, canonical order."""
    counts: dict[str, int] = {}
    chosen: list[list[int]] = []
    for rec in remediated:
        family = assign_family(rec["strategy_id"])
        if counts.get(family, 0) < cap:
            counts[family] = counts.get(family, 0) + 1
            chosen.append(list(rec["ticket"]))
    return chosen


def _uniform_ticket(rng: random.Random) -> list[int]:
    return sorted(rng.sample(range(NUMBER_MIN, NUMBER_MAX + 1), TICKET_SIZE))


def equal_budget_random_tickets(target_draw: str, replicate: int, k: int) -> list[list[int]]:
    """k uniform 6/49 tickets, deterministic per (seed, target, replicate)."""
    rng = random.Random(f"{RANDOM_SEED}:equal:{target_draw}:{replicate}")
    return [_uniform_ticket(rng) for _ in range(k)]


def diversified_random_tickets(target_draw: str, replicate: int, k: int) -> list[list[int]]:
    """k low-overlap random tickets via seeded shuffle-and-chunk.

    Shuffling 1..49 and chunking into sixes yields up to eight pairwise-disjoint
    (zero-overlap) tickets; additional reshuffles supply more when ``k > 8``. This
    is a true maximally-diversified random baseline and is generated in the same
    deterministic order for every k (so ``diversified_random_tickets(...,K)[:k]``
    equals ``diversified_random_tickets(...,k)``).
    """
    rng = random.Random(f"{RANDOM_SEED}:diverse:{target_draw}:{replicate}")
    tickets: list[list[int]] = []
    while len(tickets) < k:
        pool = list(range(NUMBER_MIN, NUMBER_MAX + 1))
        rng.shuffle(pool)
        for start in range(0, len(pool) - TICKET_SIZE + 1, TICKET_SIZE):
            if len(tickets) >= k:
                break
            tickets.append(sorted(pool[start:start + TICKET_SIZE]))
    return tickets[:k]


# ---------------------------------------------------------------------------
# Aggregation + statistics
# ---------------------------------------------------------------------------
def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _percentile(sorted_values: Sequence[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = pct / 100.0 * (len(sorted_values) - 1)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return float(sorted_values[low])
    frac = rank - low
    return float(sorted_values[low] * (1 - frac) + sorted_values[high] * frac)


def bootstrap_ci(
    outcomes: Sequence[int], stream: str, resamples: int = BOOTSTRAP_RESAMPLES
) -> dict[str, float]:
    """Percentile bootstrap 95% CI for a mean of 0/1 outcomes (deterministic)."""
    n = len(outcomes)
    if n == 0:
        return {"low": 0.0, "high": 0.0}
    rng = random.Random(f"{RANDOM_SEED}:bootstrap:{stream}")
    means = []
    for _ in range(resamples):
        total = 0
        for _ in range(n):
            total += outcomes[rng.randrange(n)]
        means.append(total / n)
    means.sort()
    return {"low": _percentile(means, 2.5), "high": _percentile(means, 97.5)}


def analytic_single_ticket_prize_prob() -> dict[str, float]:
    """Analytic prize-aware win probability of one uniform 6/49 ticket."""
    total = math.comb(UNIVERSE, TICKET_SIZE)
    p_hit = {m: math.comb(6, m) * math.comb(43, 6 - m) / total for m in range(0, 7)}
    p_ge3 = sum(p_hit[m] for m in range(3, 7))
    # exactly two main + the single special among the remaining 42 non-main non-special
    p_two_plus_special = math.comb(6, 2) * math.comb(1, 1) * math.comb(42, 3) / total
    return {
        "p_hit_ge_3": p_ge3,
        "p_two_plus_special": p_two_plus_special,
        "p_prize_aware_win": p_ge3 + p_two_plus_special,
    }


def expanding_topk_all_positions(
    replay_records: Sequence[Mapping[str, Any]],
    strategy_ids: Sequence[str],
) -> list[dict[int, list[str]]]:
    """Walk-forward (expanding) top-k strategy ranking at every replay position.

    The ranking at a position uses only the remediated prize-aware win history of
    records strictly before it, so it is horizon-independent. Returns a list
    aligned with ``replay_records`` of ``{k: [strategy_id, ...]}`` rankings.
    """
    cumulative = {sid: 0 for sid in strategy_ids}
    idx_of = {sid: i for i, sid in enumerate(strategy_ids)}
    ranking: list[dict[int, list[str]]] = []
    for record in replay_records:
        order = sorted(strategy_ids, key=lambda sid: (-cumulative[sid], idx_of[sid]))
        ranking.append({k: order[:k] for k in K_VALUES})
        win_by_sid = {row["strategy_id"]: row["prize_aware_win"] for row in record["remediated"]}
        for sid in strategy_ids:
            cumulative[sid] += 1 if win_by_sid.get(sid) else 0  # update AFTER ranking
    return ranking


def compute_per_draw_metrics(
    replay_records: Sequence[Mapping[str, Any]],
    strategy_ids: Sequence[str],
    eval_span: int,
) -> list[dict[str, Any]]:
    """Compute every combination + baseline outcome per draw (horizon-independent).

    Only the most recent ``eval_span`` draws (the longest horizon) are scored;
    expanding top-k training still spans all prior records. Random baselines are
    generated once per (draw, replicate) and sliced across nested k.
    """
    topk = expanding_topk_all_positions(replay_records, strategy_ids)
    start = max(0, len(replay_records) - eval_span)
    eq_k_max = max(K_VALUES)
    div_k_max = max(DIVERSITY_K)
    per_draw: list[dict[str, Any]] = []
    for pos in range(start, len(replay_records)):
        record = replay_records[pos]
        actual = record["actual_main"]
        special = record["actual_special"]
        remediated = record["remediated"]
        tmap = {row["strategy_id"]: row["ticket"] for row in remediated}
        rem_tickets = [row["ticket"] for row in remediated]

        det: dict[tuple[str, int], dict[str, Any]] = {}
        det[("all_11_adapter_unique", 11)] = score_portfolio(rem_tickets, actual, special)
        for k in K_VALUES:
            chosen = [tmap[sid] for sid in topk[pos][k]]
            det[("top_k_by_historical_training_only", k)] = score_portfolio(chosen, actual, special)
        div_order = diversity_greedy_order(rem_tickets)
        for k in DIVERSITY_K:
            chosen = [rem_tickets[i] for i in div_order[:k]]
            det[("diversity_greedy_overlap_minimized", k)] = score_portfolio(chosen, actual, special)
        fam = per_family_cap_select(remediated)
        det[("per_family_cap_derived_heuristic", len(fam))] = score_portfolio(fam, actual, special)

        rnd: dict[tuple[str, int], dict[str, Any]] = {}
        for k in K_VALUES:
            rnd[("equal_budget_random", k)] = {"win_bits": [], "sum_best": 0.0, "sum_cov": 0.0, "sum_dup": 0.0}
        for k in DIVERSITY_K:
            rnd[("diversified_random", k)] = {"win_bits": [], "sum_best": 0.0, "sum_cov": 0.0, "sum_dup": 0.0}
        for replicate in range(RANDOM_REPLICATES):
            eq_tickets = equal_budget_random_tickets(record["target_draw"], replicate, eq_k_max)
            for k in K_VALUES:
                sc = score_portfolio(eq_tickets[:k], actual, special)
                cell = rnd[("equal_budget_random", k)]
                cell["win_bits"].append(1 if sc["prize_aware_win"] else 0)
                cell["sum_best"] += sc["best_hit_count"]
                cell["sum_cov"] += sc["coverage"]
                cell["sum_dup"] += sc["duplicate_ticket_count"]
            div_tickets = diversified_random_tickets(record["target_draw"], replicate, div_k_max)
            for k in DIVERSITY_K:
                sc = score_portfolio(div_tickets[:k], actual, special)
                cell = rnd[("diversified_random", k)]
                cell["win_bits"].append(1 if sc["prize_aware_win"] else 0)
                cell["sum_best"] += sc["best_hit_count"]
                cell["sum_cov"] += sc["coverage"]
                cell["sum_dup"] += sc["duplicate_ticket_count"]
        per_draw.append({"target_draw": record["target_draw"], "det": det, "rnd": rnd})
    return per_draw


def aggregate_from_per_draw(per_draw: Sequence[Mapping[str, Any]], horizon_targets: int) -> dict[str, Any]:
    """Aggregate per-draw metrics over the trailing ``horizon_targets`` draws."""
    eval_slice = per_draw[-horizon_targets:]
    n = len(eval_slice)

    combos: dict[str, dict[int, Any]] = {}
    for (name, k) in eval_slice[0]["det"]:
        outcomes = [1 if d["det"][(name, k)]["prize_aware_win"] else 0 for d in eval_slice]
        combos.setdefault(name, {})[k] = {
            "k": k,
            "prize_aware_win_rate": _mean(outcomes),
            "wins": sum(outcomes),
            "n": n,
            "ci95": bootstrap_ci(outcomes, f"{name}:{k}:{horizon_targets}"),
            "avg_best_hit": _mean([d["det"][(name, k)]["best_hit_count"] for d in eval_slice]),
            "avg_mean_hit": _mean([d["det"][(name, k)]["mean_hit_count"] for d in eval_slice]),
            "avg_coverage": _mean([d["det"][(name, k)]["coverage"] for d in eval_slice]),
            "avg_duplicate_tickets": _mean([d["det"][(name, k)]["duplicate_ticket_count"] for d in eval_slice]),
        }

    randoms: dict[str, dict[int, Any]] = {}
    for (rname, k) in eval_slice[0]["rnd"]:
        rates = []
        for replicate in range(RANDOM_REPLICATES):
            wins = sum(d["rnd"][(rname, k)]["win_bits"][replicate] for d in eval_slice)
            rates.append(wins / n)
        rates.sort()
        total = n * RANDOM_REPLICATES
        randoms.setdefault(rname, {})[k] = {
            "k": k,
            "replicates": RANDOM_REPLICATES,
            "mean_prize_aware_win_rate": _mean(rates),
            "p2_5": _percentile(rates, 2.5),
            "p97_5": _percentile(rates, 97.5),
            "max_rate": rates[-1],
            "avg_best_hit": sum(d["rnd"][(rname, k)]["sum_best"] for d in eval_slice) / total,
            "avg_coverage": sum(d["rnd"][(rname, k)]["sum_cov"] for d in eval_slice) / total,
            "avg_duplicate_tickets": sum(d["rnd"][(rname, k)]["sum_dup"] for d in eval_slice) / total,
            "_dist": rates,
        }

    return {
        "horizon_targets": horizon_targets,
        "n": n,
        "eval_first_draw": eval_slice[0]["target_draw"],
        "eval_last_draw": eval_slice[-1]["target_draw"],
        "combinations": combos,
        "random_baselines": randoms,
    }


def _mc_pvalue(candidate_rate: float, dist: Sequence[float]) -> float:
    ge = sum(1 for value in dist if value >= candidate_rate)
    return (1 + ge) / (1 + len(dist))


def compare_candidates(horizon_agg: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Compare every candidate combination vs equal-budget random + all_11."""
    combos = horizon_agg["combinations"]
    randoms = horizon_agg["random_baselines"]["equal_budget_random"]
    all11 = combos["all_11_adapter_unique"].get(11, {})
    all11_rate = all11.get("prize_aware_win_rate", 0.0)

    comparisons: list[dict[str, Any]] = []
    for name, by_k in combos.items():
        for k, metrics in by_k.items():
            rate = metrics["prize_aware_win_rate"]
            rnd = randoms.get(k)
            if rnd is not None:
                p_vs_random = _mc_pvalue(rate, rnd["_dist"])
                random_mean = rnd["mean_prize_aware_win_rate"]
                beats_random = rate > rnd["p97_5"]
                effect_vs_random = rate - random_mean
            else:  # no equal-budget random at this k (e.g. variable family budget)
                p_vs_random = None
                random_mean = None
                beats_random = None
                effect_vs_random = None
            comparisons.append(
                {
                    "combination": name,
                    "k": k,
                    "prize_aware_win_rate": rate,
                    "ci95": metrics["ci95"],
                    "random_mean_rate": random_mean,
                    "p_value_vs_equal_budget_random": p_vs_random,
                    "beats_random_baseline": beats_random,
                    "effect_vs_random": effect_vs_random,
                    "beats_all_11_adapter_unique": rate > all11_rate if name != "all_11_adapter_unique" else None,
                    "effect_vs_all_11": (rate - all11_rate) if name != "all_11_adapter_unique" else None,
                }
            )
    return comparisons


# ---------------------------------------------------------------------------
# Top-level driver + artifact assembly
# ---------------------------------------------------------------------------
def _strip_internal(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: _strip_internal(v)
            for k, v in obj.items()
            if not (isinstance(k, str) and k.startswith("_"))
        }
    if isinstance(obj, list):
        return [_strip_internal(v) for v in obj]
    return obj


def build_report(
    db_path: Path,
    max_targets: int | None = None,
    progress: bool = False,
) -> dict[str, Any]:
    """Run the full replay research and assemble the (timestamp-free) report."""
    draws, db_access = load_canonical_big649_draws(db_path)
    dataset = validate_dataset(draws)
    strategy_ids = list(list_frozen_big649_strategy_ids())

    eligible_count = dataset["eligible_target_count"]
    horizons = resolve_horizons(eligible_count)

    # Replay every eligible target (history strictly before each). The expanding
    # top-k ranking needs prior eligible records, so the full eligible range from
    # MIN_HISTORY to the most recent draw is replayed.
    target_indices = list(range(MIN_HISTORY, len(draws)))
    if max_targets is not None:
        target_indices = target_indices[-max_targets:]
        horizons = resolve_horizons(len(target_indices))

    replay_records = run_replay(draws, target_indices, progress=progress)

    longest = max((h["applied_targets"] for h in horizons), default=0)
    per_draw = compute_per_draw_metrics(replay_records, strategy_ids, longest)

    horizon_results: list[dict[str, Any]] = []
    for horizon in horizons:
        applied = horizon["applied_targets"]
        if applied <= 0:
            continue
        agg = aggregate_from_per_draw(per_draw, applied)
        comparisons = compare_candidates(agg)
        horizon_results.append(
            {
                "name": horizon["name"],
                "requested_targets": horizon["requested_targets"],
                "applied_targets": applied,
                "capped": horizon["capped"],
                "aggregate": agg,
                "comparisons": comparisons,
            }
        )

    duplicate_findings = summarize_duplicates(replay_records, horizons)
    best_candidates = identify_best_candidates(horizon_results)

    report = {
        "task_id": TASK_ID,
        "schema_version": SCHEMA_VERSION,
        "origin_main": ORIGIN_MAIN,
        "research_only": True,
        "db_read_policy": "READ_ONLY_URI_MODE_RO_PLUS_QUERY_ONLY_ONE_SNAPSHOT",
        "database_access": db_access,
        "dataset": dataset,
        "dataset_source": f"{LOTTERY_TYPE} canonical view {CANONICAL_VIEW}",
        "history_cutoff_rule": "history strictly before target draw; cutoff = previous draw id",
        "outcome_leakage_guard": "target outcome never passed to adapter; adapter rejects target-in-history and forbidden metadata keys",
        "strategy_ids": strategy_ids,
        "strategy_count": len(strategy_ids),
        "exact_11_strategy_replay": len(strategy_ids) == 11,
        "replay_target_indices": [target_indices[0], target_indices[-1]],
        "replay_target_count": len(replay_records),
        "horizons": horizons,
        "analytic_single_ticket_random_prize_prob": analytic_single_ticket_prize_prob(),
        "random_baseline_config": {
            "seed": RANDOM_SEED,
            "replicates": RANDOM_REPLICATES,
            "equal_budget_k": list(K_VALUES),
            "diversified_random_k": list(DIVERSITY_K),
            "diversified_method": "seeded shuffle-and-chunk of 1..49 into disjoint sixes",
            "generation": "uniform 6-of-49 without replacement per ticket; deterministic per (seed,target,replicate)",
        },
        "combination_definitions": combination_definitions(),
        "duplicate_ticket_findings": duplicate_findings,
        "horizon_results": horizon_results,
        "best_observation_only_candidates": best_candidates,
        "multiple_testing_warning": (
            "Many combinations x k x horizons were compared. Monte-Carlo p-values are "
            "uncorrected; apply Bonferroni/BH before any inferential claim. Treat all "
            "results as observation-only research."
        ),
        "limitations": LIMITATIONS,
        "next_recommended_research_step": NEXT_STEP,
        "no_publication_statement": "No real publication, pre-draw manifest, or publication PR was created.",
        "no_official_target_or_deadline_statement": "No official target draw or deadline was looked up. No network access.",
        "prediction_success_claim": False,
        "strategy_promoted": False,
        "activation_authorized": False,
        "registry_mutated": False,
        "production_write": False,
        "real_publication_performed": False,
        "official_target_lookup": False,
        "official_deadline_lookup": False,
        "pre_draw_manifest_created": False,
        "publication_pr_created": False,
        "post_draw_evaluation_of_real_publication": False,
    }
    report["result_digest"] = compute_result_digest(report)
    return report


def summarize_duplicates(
    replay_records: Sequence[Mapping[str, Any]],
    horizons: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Quantify duplicate-ticket reduction across the full replay + per horizon."""
    def _block(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        if not records:
            return {}
        frozen_unique = [r["frozen_unique_ticket_count"] for r in records]
        remediated_unique = [r["remediated_unique_ticket_count"] for r in records]
        frozen_dupgroups = [r["frozen_duplicate_group_count"] for r in records]
        draws_with_frozen_dups = sum(1 for r in records if r["frozen_unique_ticket_count"] < 11)
        draws_with_remediated_dups = sum(1 for r in records if r["remediated_unique_ticket_count"] < 11)
        unresolved = sum(1 for r in records if r["remediated_resolution_status"] == UNRESOLVED_STATUS)
        return {
            "n": len(records),
            "avg_frozen_unique_tickets": _mean(frozen_unique),
            "avg_remediated_unique_tickets": _mean(remediated_unique),
            "min_frozen_unique_tickets": min(frozen_unique),
            "max_frozen_unique_tickets": max(frozen_unique),
            "avg_frozen_duplicate_groups": _mean(frozen_dupgroups),
            "draws_with_frozen_duplicates": draws_with_frozen_dups,
            "draws_with_remediated_duplicates": draws_with_remediated_dups,
            "remediated_resolved_11_unique": len(records) - unresolved,
            "remediated_unresolved_best_effort": unresolved,
            "avg_coverage_gain_unique_tickets": _mean(remediated_unique) - _mean(frozen_unique),
        }

    per_horizon = {}
    for horizon in horizons:
        applied = horizon["applied_targets"]
        if applied > 0:
            per_horizon[horizon["name"]] = _block(replay_records[-applied:])
    return {"full_replay": _block(replay_records), "per_horizon": per_horizon}


def identify_best_candidates(horizon_results: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Surface observation-only candidates that beat the equal-budget random baseline."""
    best: list[dict[str, Any]] = []
    for horizon in horizon_results:
        for comp in horizon["comparisons"]:
            if comp.get("beats_random_baseline"):
                best.append(
                    {
                        "horizon": horizon["name"],
                        "combination": comp["combination"],
                        "k": comp["k"],
                        "prize_aware_win_rate": comp["prize_aware_win_rate"],
                        "random_mean_rate": comp["random_mean_rate"],
                        "p_value_vs_equal_budget_random": comp["p_value_vs_equal_budget_random"],
                        "beats_all_11_adapter_unique": comp["beats_all_11_adapter_unique"],
                        "status": "OBSERVATION_ONLY_RESEARCH_CANDIDATE",
                    }
                )
    return best


def combination_definitions() -> dict[str, str]:
    return {
        "all_11_adapter_unique": "All eleven remediated (candidate-selected) tickets at bet_index=1.",
        "top_k_by_historical_training_only": (
            "Top-k strategies ranked by walk-forward expanding-window prize-aware win "
            "rate over draws strictly before each evaluation target (research observation "
            "layer; not adapter/registry selection)."
        ),
        "diversity_greedy_overlap_minimized": (
            "Greedy selection of k tickets minimizing pairwise number overlap; seeded by "
            "canonical-order strategy 0; no training, no outcome use."
        ),
        "per_family_cap_derived_heuristic": (
            f"Tickets capped at {FAMILY_CAP} per DERIVED keyword family (family metadata not "
            "authoritative); canonical order; variable budget."
        ),
        "equal_budget_random": "k uniform 6-of-49 tickets per draw (seeded replicate distribution).",
        "diversified_random": "k low-overlap random tickets greedily chosen from a seeded random pool.",
    }


LIMITATIONS = [
    "Retrospective replay against historical outcomes is not prospective/future-only validation.",
    "Multiple combinations x k x horizons were compared; p-values are uncorrected (multiple-testing risk).",
    "top_k_by_historical_training_only uses expanding-window training but remains susceptible to limited training tails.",
    "Random baselines estimate expected portfolio behaviour via 200 seeded replicates, not exhaustively.",
    "BIG 6/49 first-zone signal has prior NULL findings (L82/L90/L91); replay edges may be statistical noise.",
    "Adapter candidate selection is deterministic canonical-order, not outcome-aware; this is preserved unchanged.",
]

NEXT_STEP = (
    "If any observation-only candidate beats both the equal-budget random baseline and "
    "all_11_adapter_unique with stability across horizons, request separate Owner "
    "authorization for an independent leakage/multiple-testing audit before any "
    "future-only/OOS evaluation. No publication or activation is implied."
)


def compute_result_digest(report: Mapping[str, Any]) -> str:
    """Deterministic digest over the core results (excludes paths/timestamps/CI noise)."""
    import hashlib

    core = {
        "task_id": report["task_id"],
        "schema_version": report["schema_version"],
        "origin_main": report["origin_main"],
        "dataset_rows": report["dataset"]["row_count"],
        "first_draw": report["dataset"]["first_draw"],
        "last_draw": report["dataset"]["last_draw"],
        "strategy_ids": report["strategy_ids"],
        "replay_target_count": report["replay_target_count"],
        "horizons": [(h["name"], h["applied_targets"]) for h in report["horizons"]],
        "duplicate_findings": report["duplicate_ticket_findings"],
        "horizon_core": [
            {
                "name": h["name"],
                "comparisons": [
                    {
                        "combination": c["combination"],
                        "k": c["k"],
                        "rate": round(c["prize_aware_win_rate"], 6),
                        "p": (round(c["p_value_vs_equal_budget_random"], 6)
                              if c["p_value_vs_equal_budget_random"] is not None else None),
                    }
                    for c in h["comparisons"]
                ],
            }
            for h in report["horizon_results"]
        ],
    }
    rendered = json.dumps(_strip_internal(core), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((rendered + "\n").encode("utf-8")).hexdigest()


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render a human-readable Markdown summary of the report."""
    lines: list[str] = []
    a = lines.append
    a(f"# {report['task_id']} — BIG 6/49 Local Replay Research (Research-Only)")
    a("")
    a("> Retrospective historical replay. NOT prediction-success, production readiness, "
      "promotion, or activation. No real publication, pre-draw manifest, official "
      "target/deadline lookup, or publication PR was performed.")
    a("")
    a(f"- task_id: `{report['task_id']}`")
    a(f"- origin/main: `{report['origin_main']}`")
    a(f"- DB read policy: `{report['db_read_policy']}`")
    da = report["database_access"]
    a(f"- DB opened/queried/copied/written: "
      f"{da['opened']}/{da['queried']}/{da['copied']}/{da['written']} "
      f"(query_only={da['query_only_enabled']})")
    a(f"- result_digest: `{report['result_digest']}`")
    a("")
    ds = report["dataset"]
    a("## Dataset")
    a("")
    a(f"- source: {report['dataset_source']}")
    a(f"- rows: **{ds['row_count']}** ({ds['first_draw']} {ds['first_date']} → "
      f"{ds['last_draw']} {ds['last_date']})")
    a(f"- ordering: `{ds['ordering']}`; duplicate ids/dates: "
      f"{ds['duplicate_draw_ids']}/{ds['duplicate_dates']}; invalid tickets: {ds['invalid_tickets']}")
    a(f"- min history: {ds['min_history']}; eligible targets: {ds['eligible_target_count']}; "
      f"replayed: {report['replay_target_count']}")
    a(f"- history cutoff rule: {report['history_cutoff_rule']}")
    a(f"- outcome-leakage guard: {report['outcome_leakage_guard']}")
    a("")
    a("## Strategies (exact 11)")
    a("")
    for sid in report["strategy_ids"]:
        a(f"- `{sid}`")
    a("")
    a("## Duplicate-ticket reduction (frozen bet_index=1 vs remediated)")
    a("")
    full = report["duplicate_ticket_findings"]["full_replay"]
    a(f"- full replay (n={full['n']}): avg frozen unique tickets "
      f"**{full['avg_frozen_unique_tickets']:.2f}** → remediated "
      f"**{full['avg_remediated_unique_tickets']:.2f}** "
      f"(gain {full['avg_coverage_gain_unique_tickets']:.2f})")
    a(f"- draws with frozen duplicates: {full['draws_with_frozen_duplicates']}/{full['n']}; "
      f"with remediated duplicates: {full['draws_with_remediated_duplicates']}/{full['n']}")
    a(f"- adapter resolution: {full['remediated_resolved_11_unique']}/{full['n']} resolved to 11 unique; "
      f"{full['remediated_unresolved_best_effort']}/{full['n']} would `UNRESOLVED_DUPLICATE_STOP` "
      f"(best-effort forced duplicate in replay)")
    a(f"- avg frozen duplicate groups/draw: {full['avg_frozen_duplicate_groups']:.2f}")
    a("")
    ap = report["analytic_single_ticket_random_prize_prob"]
    a(f"Analytic single-ticket random prize-aware win probability: "
      f"**{ap['p_prize_aware_win']:.5f}** "
      f"(hit≥3 {ap['p_hit_ge_3']:.5f} + 2+special {ap['p_two_plus_special']:.5f}).")
    a("")
    a("## Horizon results")
    a("")
    for h in report["horizon_results"]:
        agg = h["aggregate"]
        a(f"### {h['name']} (n={h['applied_targets']}"
          f"{', CAPPED' if h['capped'] else ''}) "
          f"{agg['eval_first_draw']} → {agg['eval_last_draw']}")
        a("")
        a("| combination | k | prize-aware win rate | 95% CI | random mean | p vs random | beats random | beats all_11 |")
        a("|---|---|---|---|---|---|---|---|")
        for c in h["comparisons"]:
            ci = c["ci95"]
            rnd = "—" if c["random_mean_rate"] is None else f"{c['random_mean_rate']:.4f}"
            pv = "—" if c["p_value_vs_equal_budget_random"] is None else f"{c['p_value_vs_equal_budget_random']:.4f}"
            br = "—" if c["beats_random_baseline"] is None else ("YES" if c["beats_random_baseline"] else "no")
            ba = "—" if c["beats_all_11_adapter_unique"] is None else ("YES" if c["beats_all_11_adapter_unique"] else "no")
            a(f"| {c['combination']} | {c['k']} | {c['prize_aware_win_rate']:.4f} | "
              f"[{ci['low']:.4f},{ci['high']:.4f}] | {rnd} | {pv} | {br} | {ba} |")
        a("")
    a("## Best observation-only candidates (beat equal-budget random)")
    a("")
    if report["best_observation_only_candidates"]:
        for cand in report["best_observation_only_candidates"]:
            a(f"- [{cand['horizon']}] `{cand['combination']}` k={cand['k']}: rate "
              f"{cand['prize_aware_win_rate']:.4f} vs random {cand['random_mean_rate']:.4f} "
              f"(p={cand['p_value_vs_equal_budget_random']:.4f}, beats_all_11="
              f"{cand['beats_all_11_adapter_unique']}) — {cand['status']}")
    else:
        a("- None. No combination beat the equal-budget random baseline (above its 97.5 pct).")
    a("")
    a("## Multiple-testing warning")
    a("")
    a(report["multiple_testing_warning"])
    a("")
    a("## Limitations")
    a("")
    for lim in report["limitations"]:
        a(f"- {lim}")
    a("")
    a("## Next recommended research step")
    a("")
    a(report["next_recommended_research_step"])
    a("")
    a("## Governance flags")
    a("")
    for flag in (
        "prediction_success_claim",
        "strategy_promoted",
        "activation_authorized",
        "registry_mutated",
        "production_write",
        "real_publication_performed",
        "official_target_lookup",
        "official_deadline_lookup",
        "pre_draw_manifest_created",
        "publication_pr_created",
        "post_draw_evaluation_of_real_publication",
    ):
        a(f"- {flag}: {report[flag]}")
    a("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P280AM-R BIG 6/49 local replay research (research-only)")
    parser.add_argument("--db", type=Path, default=None, help="path to canonical lottery DB (read-only)")
    parser.add_argument("--max-targets", type=int, default=None, help="limit replay to the last N eligible targets (testing)")
    parser.add_argument("--out-json", type=Path, default=REPO_ROOT / "outputs/research/p280amr_big649_local_replay_research_20260619.json")
    parser.add_argument("--out-md", type=Path, default=REPO_ROOT / "outputs/research/p280amr_big649_local_replay_research_20260619.md")
    parser.add_argument("--progress", action="store_true", help="emit replay progress to stderr")
    args = parser.parse_args(argv)

    db_path = args.db or default_db_path()
    if not db_path.exists():
        print(f"DB not found: {db_path}", file=sys.stderr)
        return 2

    report = build_report(db_path, max_targets=args.max_targets, progress=args.progress)
    clean = _strip_internal(report)

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.out_md.write_text(render_markdown(report), encoding="utf-8")
    print(f"wrote {args.out_json}")
    print(f"wrote {args.out_md}")
    print(f"result_digest={report['result_digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
