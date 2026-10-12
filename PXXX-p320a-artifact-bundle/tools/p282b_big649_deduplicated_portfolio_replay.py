#!/usr/bin/env python3
"""
P282B — BIG 6/49 Deduplicated Portfolio Replay and Diversified-Random Falsification
====================================================================================

Local, read-only historical replay research for BIG 6/49 (大樂透). RESEARCH ONLY.

Primary question
----------------
Does deduplicating deterministic strategy tickets reduce duplicate exposure and
improve draw-level prize-aware coverage or success compared with the appropriate
random baselines, WITHOUT leakage?

Four fixed ticket-construction groups are compared under an equal per-draw budget:

    A. INDEPENDENT_RANDOM            -- B_d i.i.d. uniform 6/49 tickets (dups allowed)
    B. DIVERSIFIED_RANDOM            -- B_d random tickets, pairwise overlap <= cap
    C. RAW_DETERMINISTIC_PORTFOLIO   -- the frozen per-draw strategy replay tickets
    D. DEDUPLICATED_DETERMINISTIC    -- C with exact-duplicate ticket contents removed

Frozen, source-grounded inputs (all resolvable at frozen main 8b62b358)
-----------------------------------------------------------------------
* Deterministic ticket source  : table ``strategy_prediction_replays`` (BIG_LOTTO,
  replay_status='PREDICTED'), 11 strategies, per-draw ``bet_index`` 1..4, with
  ``history_cutoff_draw`` < ``target_draw`` (causality, anti-leakage).
* Outcome source               : view ``draws_big_lotto_canonical_main`` (audited
  canonical 6/49 main draws + special number).
* Prize-aware endpoint          : the FROZEN scorer ``lottery_api.prize_aware_scorer``
  (P271C, unchanged): BIG win  <=>  main_hits >= 3  OR  (main_hits == 2 AND special hit),
  special_hit  <=>  actual special number is among the predicted six numbers.

Hard safety boundaries (this tool enforces / never does)
--------------------------------------------------------
* Opens the canonical DB ONLY read-only (URI ``mode=ro`` + ``PRAGMA query_only=ON``),
  single connection. NEVER writes, copies, snapshots, migrates, or backfills the DB.
* Random ticket construction reads ONLY (rng, budget) -- it has NO access to any draw
  outcome. Deduplication operates ONLY on canonical ticket contents -- it never reads
  outcomes, win status, or future data, and NEVER adds or replaces a ticket.
* Underfilled draws (Group D reduced by dedup, Group B reduced by diversity
  infeasibility) are reported explicitly and NEVER silently repaired.
* No official target/deadline lookup; no pre-draw manifest; no real publication; no
  strategy promotion/activation; no registry/production/controlled_apply change; no
  current/future live ticket is emitted or committed.
* No strategy-source / scorer-source / adapter-source modification.

Determinism
-----------
All stochastic elements use the Python standard-library ``random`` module seeded from
a fixed master seed and consumed in a fixed order, so two runs reproduce an identical
``deterministic_digest`` (which excludes wall-clock / absolute-path / environment
fields). No numpy dependency, so results do not depend on a numpy version.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import sqlite3
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

# --- frozen scorer (P271C) -------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lottery_api.prize_aware_scorer import score_prize_aware_ticket  # noqa: E402

# ---------------------------------------------------------------------------
# Frozen configuration (recorded verbatim in artifact metadata)
# ---------------------------------------------------------------------------
TASK_ID = "P282B"
TASK_NAME = "BIG649_DEDUPLICATED_PORTFOLIO_REPLAY_AND_DIVERSIFIED_RANDOM_FALSIFICATION"
SOURCE_MAIN_SHA = "8b62b358aef3e9fce8962054c166e80c1944d00c"
EXECUTION_BRANCH = "task/p282b-big649-deduplicated-portfolio-replay"

LOTTERY = "BIG_LOTTO"
POOL_LO, POOL_HI = 1, 49
PICK = 6

MASTER_SEED = 282
MC_ITERS = 2000                      # seed-fixed Monte Carlo iterations (primary inference)
DIVERSITY_OVERLAP_CAP = 2            # max shared main numbers between any two B tickets
DIVERSITY_MAX_ATTEMPTS = 4000        # rejection attempts per B ticket before UNDERFILL
DIVERSITY_PSUCCESS_RESAMPLES = 400   # per-draw resamples to estimate B success probability

# Most-recent-N eligible-draw windows (None == ALL_AVAILABLE, descriptive only)
WINDOWS = (("SHORT", 100), ("MID", 500), ("LONG", 1500), ("ALL", None))

GROUP_A = "A_INDEPENDENT_RANDOM"
GROUP_B = "B_DIVERSIFIED_RANDOM"
GROUP_C = "C_RAW_DETERMINISTIC_PORTFOLIO"
GROUP_D = "D_DEDUPLICATED_DETERMINISTIC_PORTFOLIO"
GROUPS = (GROUP_A, GROUP_B, GROUP_C, GROUP_D)

CANONICAL_VIEW = "draws_big_lotto_canonical_main"
REPLAY_TABLE = "strategy_prediction_replays"

DEFAULT_DB = str(_REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db")

ARTIFACT_STEM = "p282b_big649_deduplicated_portfolio_replay_20260620"


# ===========================================================================
# Pure helpers — ticket canonicalization, dedup, geometry
# ===========================================================================

def canonicalize_ticket(numbers):
    """Return a canonical ticket: a sorted tuple of PICK distinct ints in pool range.

    Raises ValueError on malformed tickets. Pure; reads no outcome data.
    """
    if isinstance(numbers, (str, bytes)) or numbers is None:
        raise ValueError(f"ticket must be a sequence of ints, got {numbers!r}")
    vals = list(numbers)
    if len(vals) != PICK:
        raise ValueError(f"ticket must contain exactly {PICK} numbers, got {len(vals)}")
    out = []
    for v in vals:
        if isinstance(v, bool) or not isinstance(v, int):
            raise ValueError(f"ticket entries must be ints, got {v!r}")
        if v < POOL_LO or v > POOL_HI:
            raise ValueError(f"ticket entries must be {POOL_LO}-{POOL_HI}, got {v!r}")
        out.append(v)
    if len(set(out)) != PICK:
        raise ValueError("ticket must not contain duplicate numbers")
    return tuple(sorted(out))


def deduplicate_tickets(tickets):
    """Remove EXACT-duplicate canonical ticket contents, preserving first-seen order.

    Returns (unique_tickets, duplicates_removed). NEVER adds or replaces a ticket and
    NEVER reads any outcome. ``duplicates_removed`` == len(tickets) - len(unique).
    """
    seen = set()
    unique = []
    for t in tickets:
        if t in seen:
            continue
        seen.add(t)
        unique.append(t)
    return unique, len(tickets) - len(unique)


def coverage_count(tickets):
    """Number of distinct main numbers covered by the portfolio (0..49)."""
    covered = set()
    for t in tickets:
        covered.update(t)
    return len(covered)


def pairwise_overlap_stats(tickets):
    """(max_overlap, mean_overlap) over all unordered ticket pairs.

    For identical tickets the overlap is PICK (6); for a single-ticket or empty
    portfolio both statistics are 0.0.
    """
    sets = [set(t) for t in tickets]
    n = len(sets)
    if n < 2:
        return 0, 0.0
    mx = 0
    total = 0
    pairs = 0
    for i in range(n):
        si = sets[i]
        for j in range(i + 1, n):
            ov = len(si & sets[j])
            if ov > mx:
                mx = ov
            total += ov
            pairs += 1
    return mx, (total / pairs if pairs else 0.0)


# ===========================================================================
# Prize-aware scoring (frozen scorer) + fast equivalent for Monte Carlo
# ===========================================================================

def fast_ticket_is_win(ticket_set, actual_main_set, actual_special):
    """Fast BIG prize-aware win predicate, equivalent to the frozen scorer.

    BIG win <=> main_hits >= 3 OR (main_hits == 2 AND special hit), where
    special hit <=> actual_special in the ticket. Verified equal to
    ``score_prize_aware_ticket(...)['any_prize_aware_win']`` (see tests).
    """
    hit = len(ticket_set & actual_main_set)
    if hit >= 3:
        return True
    if hit == 2 and actual_special in ticket_set:
        return True
    return False


def score_ticket_frozen(ticket, actual_main, actual_special):
    """Authoritative per-ticket score via the FROZEN P271C scorer.

    Returns (any_prize_aware_win: bool, is_m3_plus: bool, main_hit_count: int,
    special_hit: int). The scorer is the source of truth for descriptive metrics.
    """
    res = score_prize_aware_ticket(
        LOTTERY,
        list(ticket),
        list(actual_main),
        actual_special_number=actual_special,
    )
    return (
        bool(res["any_prize_aware_win"]),
        bool(res["is_m3_plus"]),
        int(res["main_hit_count"]),
        int(res["special_hit"]),
    )


def score_portfolio(tickets, actual_main, actual_special):
    """Draw-level prize-aware metrics for a portfolio, via the frozen scorer.

    Returns dict: prize_aware_success (any ticket wins), m3_plus_success (any ticket
    hit>=3), best_main_hit (max hit count), best_special_hit (special-hit status of
    the best ticket, broken by hit then special).
    """
    actual_main = tuple(actual_main)
    success = False
    m3 = False
    best = (-1, -1)  # (main_hit, special_hit)
    for t in tickets:
        win, is_m3, hit, sp = score_ticket_frozen(t, actual_main, actual_special)
        success = success or win
        m3 = m3 or is_m3
        if (hit, sp) > best:
            best = (hit, sp)
    if best == (-1, -1):
        best = (0, 0)
    return {
        "prize_aware_success": bool(success),
        "m3_plus_success": bool(m3),
        "best_main_hit": int(best[0]),
        "best_special_hit": int(best[1]),
    }


def single_ticket_win_prob(actual_main, actual_special):
    """EXACT probability that ONE uniform random 6/49 ticket achieves the BIG
    prize-aware endpoint for a given draw (hypergeometric, closed form).

    Pool of 49 partitions into 6 main winners + 1 special + 42 blanks (special is
    distinct from the six main numbers in canonical draws). A ticket of 6 wins iff
    a>=3 OR (a==2 AND b==1), where a = main hits, b = special hit (0/1).
    """
    assert len(set(actual_main)) == PICK
    assert actual_special not in set(actual_main)
    total = math.comb(POOL_HI, PICK)  # C(49,6)
    blanks = POOL_HI - PICK - 1       # 42
    wins = 0
    for a in range(PICK + 1):
        for b in (0, 1):
            rem = PICK - a - b
            if rem < 0 or rem > blanks:
                continue
            if a >= 3 or (a == 2 and b == 1):
                wins += math.comb(PICK, a) * math.comb(1, b) * math.comb(blanks, rem)
    return wins / total


def independent_portfolio_success_prob(p1, budget):
    """P(at least one win) for ``budget`` i.i.d. random tickets = 1-(1-p1)^budget."""
    return 1.0 - (1.0 - p1) ** budget


# ===========================================================================
# Random ticket construction (NO outcome access)
# ===========================================================================

def sample_independent_random(rng, budget):
    """``budget`` i.i.d. uniform 6/49 tickets; natural duplicates/overlap allowed."""
    return [tuple(sorted(rng.sample(range(POOL_LO, POOL_HI + 1), PICK))) for _ in range(budget)]


def sample_diversified_random(rng, budget, cap=DIVERSITY_OVERLAP_CAP,
                              max_attempts=DIVERSITY_MAX_ATTEMPTS):
    """``budget`` random tickets under a pairwise main-overlap cap.

    Rejection sampling: each new ticket must share <= ``cap`` numbers with every
    already-accepted ticket (this also forbids exact duplicates, overlap==6 > cap).
    If a ticket cannot be placed within ``max_attempts`` tries the draw is UNDERFILLED
    -- the rule is NEVER silently relaxed and no replacement ticket is invented.

    Returns (tickets, underfilled: bool, produced_count: int).
    """
    chosen = []          # list[frozenset]
    underfilled = False
    for _ in range(budget):
        placed = False
        for _ in range(max_attempts):
            cand = frozenset(rng.sample(range(POOL_LO, POOL_HI + 1), PICK))
            if all(len(cand & c) <= cap for c in chosen):
                chosen.append(cand)
                placed = True
                break
        if not placed:
            underfilled = True
            break
    tickets = [tuple(sorted(c)) for c in chosen]
    return tickets, underfilled, len(tickets)


# ===========================================================================
# Read-only DB layer
# ===========================================================================

def open_readonly(db_path):
    """Open the canonical DB strictly read-only (mode=ro + query_only=ON)."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"canonical DB not found at {db_path!r}; it is gitignored and absent in "
            f"fresh worktrees -- pass --db pointing to a real checkout"
        )
    uri = f"file:{db_path}?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=30)
    con.execute("PRAGMA query_only=ON")
    return con


def load_canonical_actuals(con):
    """draw(str) -> (actual_main: tuple[6], actual_special: int) from canonical view."""
    out = {}
    for draw, numbers, special in con.execute(
        f"SELECT draw, numbers, special FROM {CANONICAL_VIEW}"
    ):
        am = canonicalize_ticket(json.loads(numbers))
        out[str(draw)] = (am, int(special))
    return out


def load_deterministic_portfolios(con):
    """draw(str) -> list of {strategy, bet, ticket, cutoff} for BIG_LOTTO PREDICTED rows.

    Tickets are taken from ``predicted_numbers`` ONLY (no outcome columns). The
    per-row ``history_cutoff_draw`` is retained for the causality (anti-leakage) check.
    """
    portfolios = defaultdict(list)
    rows = con.execute(
        f"""SELECT target_draw, strategy_id, bet_index, predicted_numbers, history_cutoff_draw
            FROM {REPLAY_TABLE}
            WHERE lottery_type = ? AND replay_status = 'PREDICTED'
            ORDER BY CAST(target_draw AS INTEGER), strategy_id, bet_index""",
        (LOTTERY,),
    )
    for td, sid, bi, pred, cutoff in rows:
        portfolios[str(td)].append(
            {
                "strategy": sid,
                "bet": int(bi),
                "ticket": canonicalize_ticket(json.loads(pred)),
                "cutoff": (str(cutoff) if cutoff is not None else None),
            }
        )
    return portfolios


def db_file_sha256(db_path):
    h = hashlib.sha256()
    with open(db_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ===========================================================================
# Per-draw construction of all four groups (single seed-fixed realization)
# ===========================================================================

def build_realized_groups(eligible_draws_asc, det_portfolios, actuals, master_seed):
    """Build one seed-fixed realized portfolio per group per eligible draw.

    Random groups (A, B) consume a single ``random.Random(master_seed)`` stream in a
    fixed order (draws ascending; for each draw: A then B) so the realization is fully
    reproducible. Deterministic groups (C, D) come straight from the replay store.

    Returns per_draw: list of dicts (one per draw) with realized tickets + provenance
    for all four groups, ordered ascending by draw.
    """
    rng = random.Random(master_seed)
    per_draw = []
    for draw in eligible_draws_asc:
        entries = det_portfolios[draw]
        raw_tickets = [e["ticket"] for e in entries]               # Group C
        budget = len(raw_tickets)
        unique_tickets, removed = deduplicate_tickets(raw_tickets)  # Group D
        # Random groups at the SAME requested budget B_d:
        a_tickets = sample_independent_random(rng, budget)
        b_tickets, b_underfilled, b_produced = sample_diversified_random(rng, budget)
        per_draw.append(
            {
                "draw": draw,
                "budget": budget,
                "actual_main": actuals[draw][0],
                "actual_special": actuals[draw][1],
                "raw_entries": entries,
                GROUP_A: {"tickets": a_tickets, "underfilled": False},
                GROUP_B: {"tickets": b_tickets, "underfilled": b_underfilled,
                          "produced": b_produced},
                GROUP_C: {"tickets": raw_tickets, "underfilled": False},
                GROUP_D: {"tickets": unique_tickets, "underfilled": removed > 0,
                          "removed": removed},
            }
        )
    return per_draw


def per_draw_metrics(record):
    """Compute all Task-B per-draw, per-group metrics for one realized draw record."""
    draw = record["draw"]
    budget = record["budget"]
    am = record["actual_main"]
    asp = record["actual_special"]
    out = {"draw": draw, "requested_budget": budget, "groups": {}}
    for g in GROUPS:
        tickets = record[g]["tickets"]
        produced = len(tickets)
        unique = len(set(tickets))
        duplicates = produced - unique
        underfilled = max(0, budget - produced)
        mx, mean_ov = pairwise_overlap_stats(tickets)
        sc = score_portfolio(tickets, am, asp)
        digest = hashlib.sha256(
            json.dumps(sorted(tickets), separators=(",", ":")).encode()
        ).hexdigest()[:16]
        gm = {
            "requested_budget": budget,
            "produced_count": produced,
            "unique_count": unique,
            "duplicate_count": duplicates,
            "underfilled_count": underfilled,
            "main_coverage": coverage_count(tickets),
            "max_pairwise_overlap": mx,
            "mean_pairwise_overlap": round(mean_ov, 6),
            "prize_aware_success": sc["prize_aware_success"],
            "best_main_hit": sc["best_main_hit"],
            "best_special_hit": sc["best_special_hit"],
            "m3_plus_success": sc["m3_plus_success"],
            "ticket_digest": digest,
        }
        if g == GROUP_C:
            gm.update({
                "raw_strategy_ticket_source_count": produced,
                "duplicate_identities_present": duplicates,
            })
        if g == GROUP_D:
            removed = record[g]["removed"]
            gm.update({
                "raw_strategy_ticket_source_count": budget,
                "duplicate_identities_removed": removed,
                "retained_unique_tickets": produced,
                "no_replacement_count": 0,
                "budget_loss_from_deduplication": removed,
            })
        out["groups"][g] = gm
    return out


# ===========================================================================
# Group-level aggregation per window
# ===========================================================================

def _hist(values):
    return {str(k): v for k, v in sorted(Counter(values).items())}


def aggregate_group(window_records, group):
    """Aggregate Task-C group-level metrics over the per-draw metrics in a window."""
    n = len(window_records)
    gms = [r["groups"][group] for r in window_records]
    req = [m["requested_budget"] for m in gms]
    prod = [m["produced_count"] for m in gms]
    uniq = [m["unique_count"] for m in gms]
    dup = [m["duplicate_count"] for m in gms]
    under = [m["underfilled_count"] for m in gms]
    cov = [m["main_coverage"] for m in gms]
    mxo = [m["max_pairwise_overlap"] for m in gms]
    mno = [m["mean_pairwise_overlap"] for m in gms]
    succ = [1 if m["prize_aware_success"] else 0 for m in gms]
    m3 = [1 if m["m3_plus_success"] else 0 for m in gms]
    besth = [m["best_main_hit"] for m in gms]
    total_prod = sum(prod)
    total_dup = sum(dup)
    return {
        "draw_count": n,
        "mean_requested_budget": round(sum(req) / n, 6),
        "mean_produced_budget": round(sum(prod) / n, 6),
        "mean_unique_tickets": round(sum(uniq) / n, 6),
        "duplicate_rate": round(total_dup / total_prod, 6) if total_prod else 0.0,
        "underfilled_rate": round(sum(1 for u in under if u > 0) / n, 6),
        "total_underfilled_tickets": sum(under),
        "mean_main_coverage": round(sum(cov) / n, 6),
        "mean_max_overlap": round(sum(mxo) / n, 6),
        "mean_pairwise_overlap": round(sum(mno) / n, 6),
        "prize_aware_success_count": sum(succ),
        "prize_aware_success_rate": round(sum(succ) / n, 6),
        "m3_plus_success_count": sum(m3),
        "m3_plus_success_rate": round(sum(m3) / n, 6),
        "best_main_hit_distribution": _hist(besth),
    }


# ===========================================================================
# Inference — seed-fixed Bernoulli Monte Carlo + exact Poisson-binomial
# ===========================================================================

def bernoulli_mc_window_rates(probs_recent_first, window_sizes, iters, seed):
    """Seed-fixed Bernoulli Monte Carlo of a random group's per-window success rate.

    ``probs_recent_first[i]`` is the EXACT P(draw success) for the i-th most-recent
    eligible draw (independent across draws). Windows are nested by recency, so one
    MC pass yields every window's sampling distribution.

    Returns {window_name: [sr_1, ..., sr_iters]}.
    """
    rng = random.Random(seed)
    n = len(probs_recent_first)
    samples = {w: [] for w in window_sizes}
    for _ in range(iters):
        bits = [1 if rng.random() < probs_recent_first[i] else 0 for i in range(n)]
        running = 0
        # cumulative successes over the most-recent prefix
        prefix = [0] * (n + 1)
        for i in range(n):
            running += bits[i]
            prefix[i + 1] = running
        for w, size in window_sizes.items():
            samples[w].append(prefix[size] / size)
    return samples


def poisson_binomial_mean_std(probs):
    """Exact mean and std of the success RATE of independent Bernoulli(probs)."""
    n = len(probs)
    mean = sum(probs) / n
    var = sum(p * (1.0 - p) for p in probs) / (n * n)
    return mean, math.sqrt(var)


def _normal_sf(z):
    """Survival function P(Z>=z) for standard normal via erfc."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def paired_random_baseline_test(observed_success_bits_recent_first, probs_recent_first,
                                window_sizes, iters, seed, label):
    """One-sided paired test: is the FIXED group's success rate above the matched
    random baseline? Reports MC p-value and an exact Poisson-binomial cross-check.

    ``observed_success_bits_recent_first`` are the deterministic group's per-draw 0/1
    successes (recent-first); ``probs_recent_first`` are the matched random group's
    exact per-draw success probabilities.
    """
    mc = bernoulli_mc_window_rates(probs_recent_first, window_sizes, iters, seed)
    result = {}
    for w, size in window_sizes.items():
        obs_rate = sum(observed_success_bits_recent_first[:size]) / size
        sr_samples = mc[w]
        rnd_mean = sum(sr_samples) / len(sr_samples)
        ge = sum(1 for s in sr_samples if s >= obs_rate - 1e-12)
        p_mc = (1 + ge) / (iters + 1)
        srt = sorted(sr_samples)
        lo = srt[max(0, int(0.025 * len(srt)) - 1)]
        hi = srt[min(len(srt) - 1, int(0.975 * len(srt)))]
        # exact Poisson-binomial cross-check
        pmean, pstd = poisson_binomial_mean_std(probs_recent_first[:size])
        z = (obs_rate - pmean) / pstd if pstd > 0 else float("inf")
        p_exact = _normal_sf(z)
        result[w] = {
            "window_draws": size,
            "fixed_success_rate": round(obs_rate, 6),
            "random_baseline_mean_rate": round(rnd_mean, 6),
            "random_baseline_exact_mean_rate": round(pmean, 6),
            "observed_difference": round(obs_rate - rnd_mean, 6),
            "random_baseline_ci95": [round(lo, 6), round(hi, 6)],
            "mc_iterations": iters,
            "mc_seed": seed,
            "p_value_mc_one_sided_fixed_better": round(p_mc, 6),
            "p_value_exact_poisson_binomial": round(p_exact, 8),
            "effect_direction": (
                "fixed_above_random" if obs_rate > rnd_mean
                else ("fixed_below_random" if obs_rate < rnd_mean else "equal")
            ),
            "comparison_label": label,
        }
    return result


def estimate_diversified_success_probs(eligible_draws_recent_first, det_portfolios,
                                       actuals, budgets, resamples, seed):
    """Estimate per-draw P(success) for the DIVERSIFIED-random group by resampling.

    No closed form exists (the diversity cap correlates tickets), so each draw's
    success probability is estimated from ``resamples`` independent diversified
    portfolios using the fast win predicate (verified equal to the frozen scorer).
    Seed-fixed and consumed in a fixed order.
    """
    rng = random.Random(seed)
    probs = []
    for draw in eligible_draws_recent_first:
        am_set = set(actuals[draw][0])
        asp = actuals[draw][1]
        budget = budgets[draw]
        wins = 0
        for _ in range(resamples):
            tickets, _underfilled, _produced = sample_diversified_random(rng, budget)
            if any(fast_ticket_is_win(set(t), am_set, asp) for t in tickets):
                wins += 1
        probs.append(wins / resamples)
    return probs


# ===========================================================================
# Anti-leakage / falsification evidence
# ===========================================================================

def collect_anti_leakage_evidence(det_portfolios, actuals, eligible_draws):
    """Structural anti-leakage / safety evidence (Task D)."""
    causality_violations = 0
    null_cutoffs = 0
    checked = 0
    for draw in eligible_draws:
        for e in det_portfolios[draw]:
            checked += 1
            if e["cutoff"] is None:
                null_cutoffs += 1
                continue
            try:
                if int(e["cutoff"]) >= int(draw):
                    causality_violations += 1
            except (TypeError, ValueError):
                causality_violations += 1
    return {
        "deterministic_rows_checked": checked,
        "causality_violations_cutoff_ge_target": causality_violations,
        "null_history_cutoff_rows": null_cutoffs,
        "random_construction_reads_outcomes": False,
        "random_construction_signature": "sample_*(rng, budget) -- no actuals argument",
        "deduplication_reads_outcomes": False,
        "deduplication_adds_or_replaces_tickets": False,
        "deduplication_basis": "exact canonical ticket-content identity only",
        "outcome_source": CANONICAL_VIEW,
        "outcome_used_only_for_scoring": True,
        "ticket_replacement_count": 0,
        "live_or_future_tickets_emitted": False,
    }


# ===========================================================================
# Deterministic digest
# ===========================================================================

# Fields excluded from the deterministic digest (wall-clock / environment / absolute
# paths) so two runs on the same data reproduce an identical digest.
_DIGEST_EXCLUDED_TOP_KEYS = {
    "generated_at_utc", "deterministic_digest", "db_path_basename",
    "db_sha256_pre", "db_sha256_post", "db_drift", "db_stat", "execution_root",
    "canonical_db_path_policy",
}


def compute_deterministic_digest(results):
    payload = {k: v for k, v in results.items() if k not in _DIGEST_EXCLUDED_TOP_KEYS}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ===========================================================================
# Orchestration
# ===========================================================================

def run_research(db_path, iters=MC_ITERS, master_seed=MASTER_SEED,
                 diversity_resamples=DIVERSITY_PSUCCESS_RESAMPLES):
    con = open_readonly(db_path)
    db_opened = True
    db_queried = False
    try:
        actuals = load_canonical_actuals(con)
        det_portfolios = load_deterministic_portfolios(con)
        db_queried = True
    finally:
        con.close()

    replay_draws = set(det_portfolios)
    canonical_draws = set(actuals)
    eligible = sorted(replay_draws & canonical_draws, key=lambda d: int(d))
    excluded = sorted(replay_draws - canonical_draws, key=lambda d: int(d))

    eligible_desc = list(reversed(eligible))  # most-recent first
    budgets = {d: len(det_portfolios[d]) for d in eligible}

    # window sizes (most-recent N), clamped to available eligible draws
    n_elig = len(eligible)
    window_sizes = {}
    for name, size in WINDOWS:
        sz = n_elig if size is None else min(size, n_elig)
        window_sizes[name] = sz

    # ---- realized portfolios + per-draw metrics (seed-fixed) ----
    realized = build_realized_groups(eligible, det_portfolios, actuals, master_seed)
    pdm = [per_draw_metrics(r) for r in realized]
    pdm_by_draw = {m["draw"]: m for m in pdm}

    # recent-first deterministic success bits (Groups C and D are identical sets)
    succ_bits_D = [1 if pdm_by_draw[d]["groups"][GROUP_D]["prize_aware_success"] else 0
                   for d in eligible_desc]
    succ_bits_C = [1 if pdm_by_draw[d]["groups"][GROUP_C]["prize_aware_success"] else 0
                   for d in eligible_desc]

    # ---- per-window group aggregates ----
    group_window = {g: {} for g in GROUPS}
    for name, size in window_sizes.items():
        window_records = [pdm_by_draw[d] for d in eligible_desc[:size]]
        for g in GROUPS:
            group_window[g][name] = aggregate_group(window_records, g)

    # ---- exact per-draw random success probabilities (recent-first) ----
    p1 = {d: single_ticket_win_prob(actuals[d][0], actuals[d][1]) for d in eligible}
    uniq_budget = {d: pdm_by_draw[d]["groups"][GROUP_D]["produced_count"] for d in eligible}
    probs_A_full = [independent_portfolio_success_prob(p1[d], budgets[d]) for d in eligible_desc]
    probs_A_matched = [independent_portfolio_success_prob(p1[d], uniq_budget[d]) for d in eligible_desc]

    # ---- PRIMARY: D vs A (budget-matched at U_d) ----
    d_vs_a = paired_random_baseline_test(
        succ_bits_D, probs_A_matched, window_sizes, iters,
        seed=master_seed + 1, label="D_DEDUP vs A_INDEPENDENT_RANDOM (budget-matched U_d)")

    # ---- C vs A (full budget B_d) ----
    c_vs_a = paired_random_baseline_test(
        succ_bits_C, probs_A_full, window_sizes, iters,
        seed=master_seed + 2, label="C_RAW vs A_INDEPENDENT_RANDOM (full budget B_d)")

    # ---- diversified-random success probabilities (estimated) ----
    probs_B_matched = estimate_diversified_success_probs(
        eligible_desc, det_portfolios, actuals, uniq_budget, diversity_resamples,
        seed=master_seed + 10)
    probs_B_full = estimate_diversified_success_probs(
        eligible_desc, det_portfolios, actuals, budgets, diversity_resamples,
        seed=master_seed + 11)

    # ---- D vs B (matched) and C vs B (full) ----
    d_vs_b = paired_random_baseline_test(
        succ_bits_D, probs_B_matched, window_sizes, iters,
        seed=master_seed + 3, label="D_DEDUP vs B_DIVERSIFIED_RANDOM (budget-matched U_d)")
    c_vs_b = paired_random_baseline_test(
        succ_bits_C, probs_B_full, window_sizes, iters,
        seed=master_seed + 4, label="C_RAW vs B_DIVERSIFIED_RANDOM (full budget B_d)")

    # ---- D vs C (both deterministic; success identical by construction) ----
    d_vs_c = {}
    for name, size in window_sizes.items():
        sd = sum(succ_bits_D[:size]) / size
        sc = sum(succ_bits_C[:size]) / size
        identical = succ_bits_D[:size] == succ_bits_C[:size]
        gD = group_window[GROUP_D][name]
        gC = group_window[GROUP_C][name]
        d_vs_c[name] = {
            "window_draws": size,
            "D_success_rate": round(sd, 6),
            "C_success_rate": round(sc, 6),
            "success_rate_difference": round(sd - sc, 6),
            "success_identical_by_construction": identical,
            "C_duplicate_rate": gC["duplicate_rate"],
            "D_duplicate_rate": gD["duplicate_rate"],
            "C_mean_produced_budget": gC["mean_produced_budget"],
            "D_mean_produced_budget": gD["mean_produced_budget"],
            "mean_budget_saved_by_dedup": round(
                gC["mean_produced_budget"] - gD["mean_produced_budget"], 6),
            "method": "descriptive (D is the unique subset of C; removing exact "
                      "duplicates cannot change the winning set)",
        }

    # ---- duplicate / unique / coverage / overlap summary (ALL window) ----
    det_total_tickets = sum(budgets[d] for d in eligible)
    det_total_unique = sum(uniq_budget[d] for d in eligible)
    det_total_dup = det_total_tickets - det_total_unique
    draws_with_dup = sum(1 for d in eligible if budgets[d] - uniq_budget[d] > 0)

    # ---- per-draw aggregate metrics (distributions, not every draw) ----
    per_draw_aggregate = {
        "eligible_draw_count": n_elig,
        "budget_distribution": _hist([budgets[d] for d in eligible]),
        "unique_count_distribution": _hist([uniq_budget[d] for d in eligible]),
        "duplicates_removed_distribution": _hist(
            [budgets[d] - uniq_budget[d] for d in eligible]),
        "sample_per_draw_records_recent": [pdm_by_draw[d] for d in eligible_desc[:8]],
    }

    # ---- assemble results ----
    results = {
        "task_id": TASK_ID,
        "task_name": TASK_NAME,
        "lottery": LOTTERY,
        "source_main_sha": SOURCE_MAIN_SHA,
        "execution_branch": EXECUTION_BRANCH,
        "research_only": True,

        "canonical_db_path_policy": (
            "canonical lottery_api/data/lottery_v2.db (gitignored, absent in worktrees) "
            "opened read-only mode=ro + PRAGMA query_only=ON, single connection"),
        "db_opened": db_opened,
        "db_queried": db_queried,
        "db_copied": False,
        "db_written": False,

        "target_draw_universe": {
            "definition": "BIG_LOTTO strategy_prediction_replays target_draws that join "
                          "to draws_big_lotto_canonical_main (canonical 6/49 main draws)",
            "deterministic_source_table": REPLAY_TABLE,
            "outcome_source_view": CANONICAL_VIEW,
            "replay_distinct_target_draws": len(replay_draws),
            "canonical_view_draws": len(canonical_draws),
            "eligible_draw_count": n_elig,
            "excluded_non_canonical_count": len(excluded),
            "excluded_non_canonical_sample": excluded[:15],
            "exclusion_reason": "NON_CANONICAL_OUTCOME_UNRESOLVABLE (target_draw not in "
                                "draws_big_lotto_canonical_main)",
        },
        "eligibility_and_exclusion_rules": {
            "include": "replay_status='PREDICTED' AND target_draw in canonical view",
            "exclude": "target_draw absent from canonical view (no canonical outcome)",
            "all_loaded_rows_status": "PREDICTED",
        },
        "frozen_seeds": {
            "master_seed": master_seed,
            "realized_portfolio_seed": master_seed,
            "mc_seed_d_vs_a": master_seed + 1,
            "mc_seed_c_vs_a": master_seed + 2,
            "mc_seed_d_vs_b": master_seed + 3,
            "mc_seed_c_vs_b": master_seed + 4,
            "diversified_psuccess_seed_matched": master_seed + 10,
            "diversified_psuccess_seed_full": master_seed + 11,
        },
        "frozen_windows": {name: window_sizes[name] for name, _ in WINDOWS},
        "window_definition": "most-recent N eligible draws (by CAST(draw AS INTEGER) DESC)",
        "group_definitions": {
            GROUP_A: "B_d i.i.d. uniform 6/49 tickets; natural duplicates/overlap allowed",
            GROUP_B: f"B_d random tickets with pairwise main-overlap <= {DIVERSITY_OVERLAP_CAP}; "
                     f"rejection sampling (<= {DIVERSITY_MAX_ATTEMPTS} attempts/ticket); "
                     f"UNDERFILLED rather than relaxing the constraint",
            GROUP_C: "frozen per-draw strategy replay tickets, as stored (no outcome-based "
                     "re-rank or selection)",
            GROUP_D: "Group C with exact-duplicate canonical ticket contents removed; no "
                     "replacement; reduced-budget draws marked UNDERFILLED",
        },
        "ticket_canonicalization_rules": (
            f"sorted tuple of {PICK} distinct ints in [{POOL_LO},{POOL_HI}]; malformed "
            f"tickets raise; identity = canonical content"),
        "diversity_constraint": {
            "max_pairwise_main_overlap": DIVERSITY_OVERLAP_CAP,
            "max_attempts_per_ticket": DIVERSITY_MAX_ATTEMPTS,
            "on_infeasible": "mark draw UNDERFILLED (never relax, never replace)",
        },
        "underfilled_policy": (
            "Group D underfilled by removed exact duplicates; Group B underfilled if the "
            "diversity constraint cannot be satisfied within max_attempts. Underfilled "
            "draws are reported and never silently repaired or backfilled."),
        "prize_aware_endpoint": {
            "definition": "BIG draw-level success: any portfolio ticket with "
                          "main_hits>=3 OR (main_hits==2 AND special_hit)",
            "special_hit_definition": "actual special number present in the predicted six",
            "scorer": "lottery_api.prize_aware_scorer.score_prize_aware_ticket (P271C, frozen)",
            "scoring_version": "prize_aware_v1",
        },

        "duplicate_unique_coverage_overlap_summary": {
            "deterministic_total_tickets": det_total_tickets,
            "deterministic_total_unique": det_total_unique,
            "deterministic_total_duplicates_removed": det_total_dup,
            "deterministic_overall_duplicate_rate": round(det_total_dup / det_total_tickets, 6),
            "draws_with_at_least_one_duplicate": draws_with_dup,
            "draws_with_duplicate_fraction": round(draws_with_dup / n_elig, 6),
        },

        "group_window_metrics": group_window,
        "per_draw_aggregate_metrics": per_draw_aggregate,

        "primary_comparison_d_vs_a": {
            "method": "paired same-draw observations; D fixed (U_d unique deterministic "
                      "tickets) vs A budget-matched at U_d i.i.d. random; seed-fixed "
                      "Bernoulli Monte Carlo over EXACT per-draw success probabilities, "
                      "with an exact Poisson-binomial normal-approximation cross-check; "
                      "one-sided test for D above the random baseline",
            "budget_policy": "EQUAL budget U_d for both D and the A baseline",
            "results_by_window": d_vs_a,
        },
        "secondary_comparisons": {
            "d_vs_b": {"method": "paired; D vs diversified-random baseline matched at U_d "
                                 "(B success prob estimated by resampling)",
                       "results_by_window": d_vs_b},
            "d_vs_c": {"method": "descriptive; success identical by construction",
                       "results_by_window": d_vs_c},
            "c_vs_a": {"method": "paired; C (=D success) vs full-budget B_d random baseline",
                       "results_by_window": c_vs_a},
            "c_vs_b": {"method": "paired; C vs full-budget diversified-random baseline",
                       "results_by_window": c_vs_b},
        },

        "statistical_method_and_limitations": {
            "primary_test": "seed-fixed Bernoulli Monte Carlo (paired by draw) + exact "
                            "Poisson-binomial cross-check; one-sided (fixed > random)",
            "mc_iterations": iters,
            "diversified_success_resamples_per_draw": diversity_resamples,
            "limitations": [
                "Retrospective replay over historical draws; NOT prospective / out-of-sample.",
                "Deduplication cannot raise draw-level success vs the raw portfolio "
                "(D's winning set equals C's); any gain is budget/duplicate-exposure only.",
                "Diversified-random success probability is estimated (resampling), not "
                "closed-form; D-vs-B / C-vs-B are secondary.",
                "Source prize-tier mapping is MANUAL_VERIFICATION_REQUIRED (P271B/C).",
                "21 replay target_draws excluded as non-canonical (no canonical outcome).",
            ],
            "not_a_betting_recommendation": True,
        },
        "anti_leakage_evidence": collect_anti_leakage_evidence(
            det_portfolios, actuals, eligible),

        "ticket_replacement_count": 0,
        "current_or_future_live_tickets_output": False,
        "no_prediction_success_claim": True,
        "no_strategy_promoted": True,
        "no_activation": True,
        "no_real_publication": True,
        "no_official_target_or_deadline_lookup": True,
        "no_pre_draw_manifest": True,
        "no_db_write_or_copy": True,
    }

    # classification + recommendation are deterministic functions of the computed
    # research data, so they are part of the digest-covered payload.
    results["final_classification"] = classify(results)
    results["recommendation_next_research_step"] = recommend_next(results)
    results["deterministic_digest"] = compute_deterministic_digest(results)
    return results


def classify(results):
    """Derive the single final classification per Task E."""
    n_elig = results["target_draw_universe"]["eligible_draw_count"]
    dup_rate = results["duplicate_unique_coverage_overlap_summary"][
        "deterministic_overall_duplicate_rate"]
    # support check: enough eligible draws and a non-trivial amount to deduplicate
    if n_elig < 100 or dup_rate <= 0.0:
        return "P282B_BIG649_DEDUP_REPLAY_PR_OPEN_UNDERFILLED_OR_SUPPORT_BLOCKED_NO_PUBLICATION"
    # primary D vs A advantage on MID and LONG where feasible
    dva = results["primary_comparison_d_vs_a"]["results_by_window"]
    feasible = [w for w in ("MID", "LONG") if w in dva]
    advantage = all(
        dva[w]["effect_direction"] == "fixed_above_random"
        and dva[w]["p_value_mc_one_sided_fixed_better"] < 0.05
        for w in feasible
    ) and len(feasible) > 0
    if advantage:
        return "P282B_BIG649_DEDUP_REPLAY_PR_OPEN_OBSERVATION_CANDIDATE_NO_PUBLICATION"
    return "P282B_BIG649_DEDUP_REPLAY_PR_OPEN_NULL_NO_PUBLICATION"


def recommend_next(results):
    cls = results["final_classification"]
    if cls.endswith("OBSERVATION_CANDIDATE_NO_PUBLICATION"):
        return ("Independent audit, then separately authorized future-only/OOS validation "
                "before any promotion; no live use.")
    if cls.endswith("NULL_NO_PUBLICATION"):
        return ("No edge: deduplication reduces duplicate exposure / wasted budget but does "
                "not beat the matched random baseline. Treat dedup as a budget-efficiency "
                "control only; HOLD per maintenance mode (L90/L91). No further mining "
                "without a new external data source or explicit authorization.")
    return ("Budget/support insufficient for a fair dedup comparison; revisit only with a "
            "richer deterministic portfolio or more eligible canonical draws.")


# ===========================================================================
# Markdown rendering
# ===========================================================================

def render_markdown(results):
    R = results
    tu = R["target_draw_universe"]
    summ = R["duplicate_unique_coverage_overlap_summary"]
    L = []
    L.append(f"# {R['task_id']} — BIG 6/49 Deduplicated Portfolio Replay & "
             f"Diversified-Random Falsification")
    L.append("")
    L.append(f"- **Final classification:** `{R['final_classification']}`")
    L.append(f"- **Deterministic digest:** `{R['deterministic_digest']}`")
    L.append(f"- **Source main SHA:** `{R['source_main_sha']}`")
    L.append(f"- **Branch:** `{R['execution_branch']}`")
    L.append("")
    L.append("**Research only — not a betting recommendation. "
             "No prediction-success claim, promotion, activation, or publication.**")
    L.append("")
    L.append("## Primary question")
    L.append("Does deduplicating deterministic strategy tickets reduce duplicate exposure "
             "and improve draw-level prize-aware coverage/success vs the appropriate random "
             "baselines, without leakage?")
    L.append("")
    L.append("## Headline answer")
    dva_long = R["primary_comparison_d_vs_a"]["results_by_window"].get("LONG")
    dvc_long = R["secondary_comparisons"]["d_vs_c"]["results_by_window"].get("LONG")
    L.append(f"- **Duplicate exposure:** the raw deterministic portfolio has an overall "
             f"duplicate rate of **{summ['deterministic_overall_duplicate_rate']:.4f}** "
             f"({summ['deterministic_total_duplicates_removed']} of "
             f"{summ['deterministic_total_tickets']} tickets); "
             f"{summ['draws_with_at_least_one_duplicate']}/{tu['eligible_draw_count']} "
             f"draws carry >=1 duplicate. Deduplication removes all of it (D duplicate "
             f"rate 0).")
    if dvc_long:
        L.append(f"- **Dedup vs raw success (D vs C):** success rates are "
                 f"{'identical' if dvc_long['success_identical_by_construction'] else 'NOT identical'} "
                 f"by construction (LONG: D={dvc_long['D_success_rate']:.4f}, "
                 f"C={dvc_long['C_success_rate']:.4f}); dedup saves on average "
                 f"{dvc_long['mean_budget_saved_by_dedup']:.3f} tickets/draw without "
                 f"changing coverage.")
    if dva_long:
        L.append(f"- **Dedup vs random (D vs A, budget-matched, LONG):** D success "
                 f"{dva_long['fixed_success_rate']:.4f} vs random "
                 f"{dva_long['random_baseline_mean_rate']:.4f} "
                 f"(diff {dva_long['observed_difference']:+.4f}, "
                 f"MC p={dva_long['p_value_mc_one_sided_fixed_better']:.4f}, "
                 f"exact p={dva_long['p_value_exact_poisson_binomial']:.4g}, "
                 f"{dva_long['effect_direction']}).")
    L.append("")
    L.append("## Target draw universe")
    L.append(f"- Deterministic source: `{tu['deterministic_source_table']}` "
             f"({LOTTERY}, all PREDICTED).")
    L.append(f"- Outcome source: `{tu['outcome_source_view']}`.")
    L.append(f"- Replay distinct target draws: {tu['replay_distinct_target_draws']}; "
             f"canonical view draws: {tu['canonical_view_draws']}.")
    L.append(f"- **Eligible draws: {tu['eligible_draw_count']}** "
             f"(excluded {tu['excluded_non_canonical_count']} non-canonical: "
             f"`{tu['exclusion_reason']}`).")
    L.append("")
    L.append("## Groups")
    for g in GROUPS:
        L.append(f"- **{g}** — {R['group_definitions'][g]}")
    L.append("")
    L.append(f"Budget rule: every group requested the same per-draw budget B_d (the raw "
             f"deterministic portfolio size). Seed = {R['frozen_seeds']['master_seed']}. "
             f"MC iterations = {R['statistical_method_and_limitations']['mc_iterations']}.")
    L.append("")
    L.append("## Group-level metrics by window")
    for name, _ in WINDOWS:
        if name not in R["frozen_windows"]:
            continue
        size = R["frozen_windows"][name]
        L.append(f"### {name} (most-recent {size} eligible draws)")
        L.append("")
        L.append("| Group | prod | uniq | dup rate | underfill rate | coverage | "
                 "max ov | prize-aware win | M3+ win |")
        L.append("|---|--:|--:|--:|--:|--:|--:|--:|--:|")
        for g in GROUPS:
            m = R["group_window_metrics"][g][name]
            L.append(f"| {g.split('_')[0]} | {m['mean_produced_budget']:.2f} | "
                     f"{m['mean_unique_tickets']:.2f} | {m['duplicate_rate']:.4f} | "
                     f"{m['underfilled_rate']:.4f} | {m['mean_main_coverage']:.2f} | "
                     f"{m['mean_max_overlap']:.2f} | "
                     f"{m['prize_aware_success_rate']:.4f} "
                     f"({m['prize_aware_success_count']}) | "
                     f"{m['m3_plus_success_rate']:.4f} |")
        L.append("")
    L.append("## Primary comparison — D (dedup) vs A (independent random), budget-matched")
    L.append("")
    L.append(R["primary_comparison_d_vs_a"]["method"])
    L.append("")
    L.append("| Window | D rate | random rate | diff | MC p (D>rand) | exact p | direction |")
    L.append("|---|--:|--:|--:|--:|--:|---|")
    for name, _ in WINDOWS:
        r = R["primary_comparison_d_vs_a"]["results_by_window"].get(name)
        if not r:
            continue
        L.append(f"| {name} | {r['fixed_success_rate']:.4f} | "
                 f"{r['random_baseline_mean_rate']:.4f} | "
                 f"{r['observed_difference']:+.4f} | "
                 f"{r['p_value_mc_one_sided_fixed_better']:.4f} | "
                 f"{r['p_value_exact_poisson_binomial']:.4g} | {r['effect_direction']} |")
    L.append("")
    L.append("## Secondary comparisons")
    for key, lbl in (("d_vs_b", "D vs B (diversified random, matched)"),
                     ("c_vs_a", "C vs A (full budget)"),
                     ("c_vs_b", "C vs B (full budget)")):
        block = R["secondary_comparisons"][key]
        L.append(f"### {lbl}")
        L.append("| Window | fixed rate | random rate | diff | MC p | direction |")
        L.append("|---|--:|--:|--:|--:|---|")
        for name, _ in WINDOWS:
            r = block["results_by_window"].get(name)
            if not r:
                continue
            L.append(f"| {name} | {r['fixed_success_rate']:.4f} | "
                     f"{r['random_baseline_mean_rate']:.4f} | "
                     f"{r['observed_difference']:+.4f} | "
                     f"{r['p_value_mc_one_sided_fixed_better']:.4f} | "
                     f"{r['effect_direction']} |")
        L.append("")
    L.append("### D vs C (dedup vs raw; descriptive)")
    L.append("| Window | D rate | C rate | identical | budget saved/draw |")
    L.append("|---|--:|--:|:-:|--:|")
    for name, _ in WINDOWS:
        r = R["secondary_comparisons"]["d_vs_c"]["results_by_window"].get(name)
        if not r:
            continue
        L.append(f"| {name} | {r['D_success_rate']:.4f} | {r['C_success_rate']:.4f} | "
                 f"{'yes' if r['success_identical_by_construction'] else 'NO'} | "
                 f"{r['mean_budget_saved_by_dedup']:.3f} |")
    L.append("")
    L.append("## Anti-leakage evidence")
    ale = R["anti_leakage_evidence"]
    L.append(f"- Deterministic rows checked: {ale['deterministic_rows_checked']}; "
             f"causality violations (cutoff>=target): "
             f"{ale['causality_violations_cutoff_ge_target']}; "
             f"null cutoffs: {ale['null_history_cutoff_rows']}.")
    L.append(f"- Random construction reads outcomes: "
             f"{ale['random_construction_reads_outcomes']}; "
             f"dedup reads outcomes: {ale['deduplication_reads_outcomes']}; "
             f"ticket replacements: {ale['ticket_replacement_count']}; "
             f"live/future tickets emitted: {ale['live_or_future_tickets_emitted']}.")
    L.append("")
    L.append("## Statistical method & limitations")
    for lim in R["statistical_method_and_limitations"]["limitations"]:
        L.append(f"- {lim}")
    L.append("")
    L.append("## Recommendation")
    L.append(R["recommendation_next_research_step"])
    L.append("")
    L.append("## Safety flags")
    for k in ("db_opened", "db_queried", "db_copied", "db_written",
              "no_prediction_success_claim", "no_strategy_promoted", "no_activation",
              "no_real_publication", "no_official_target_or_deadline_lookup",
              "no_pre_draw_manifest", "no_db_write_or_copy",
              "current_or_future_live_tickets_output"):
        L.append(f"- `{k}` = {R[k]}")
    # strip trailing whitespace per line and collapse to exactly one EOF newline
    # (keeps `git diff --check` clean: no trailing whitespace, no blank line at EOF)
    text = "\n".join(line.rstrip() for line in L)
    return text.rstrip("\n") + "\n"


# ===========================================================================
# CLI
# ===========================================================================

def main(argv=None):
    parser = argparse.ArgumentParser(description="P282B BIG649 deduplicated portfolio replay")
    parser.add_argument("--db", default=DEFAULT_DB,
                        help="path to canonical lottery_v2.db (gitignored; pass a real checkout)")
    parser.add_argument("--iters", type=int, default=MC_ITERS)
    parser.add_argument("--seed", type=int, default=MASTER_SEED)
    parser.add_argument("--diversity-resamples", type=int, default=DIVERSITY_PSUCCESS_RESAMPLES)
    parser.add_argument("--out-json", default=None)
    parser.add_argument("--out-md", default=None)
    parser.add_argument("--record-db-hash", action="store_true",
                        help="record sha256 of the DB file (environment field, excluded from digest)")
    args = parser.parse_args(argv)

    db_pre = None
    if args.record_db_hash and os.path.exists(args.db):
        db_pre = db_file_sha256(args.db)  # raw byte read before any SQLite open

    results = run_research(args.db, iters=args.iters, master_seed=args.seed,
                           diversity_resamples=args.diversity_resamples)

    # environment fields (excluded from deterministic digest)
    results["db_path_basename"] = os.path.basename(args.db)
    if args.record_db_hash and os.path.exists(args.db):
        st = os.stat(args.db)
        db_post = db_file_sha256(args.db)  # after read-only access + connection close
        results["db_sha256_pre"] = db_pre
        results["db_sha256_post"] = db_post
        results["db_drift"] = (db_pre != db_post)
        results["db_stat"] = {"size": st.st_size, "mtime": int(st.st_mtime)}

    out_json = args.out_json or str(_REPO_ROOT / "outputs" / "research" / f"{ARTIFACT_STEM}.json")
    out_md = args.out_md or str(_REPO_ROOT / "outputs" / "research" / f"{ARTIFACT_STEM}.md")
    Path(out_json).parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
    with open(out_md, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(results))

    print(f"final_classification = {results['final_classification']}")
    print(f"deterministic_digest = {results['deterministic_digest']}")
    print(f"eligible_draws = {results['target_draw_universe']['eligible_draw_count']}")
    print(f"overall_duplicate_rate = "
          f"{results['duplicate_unique_coverage_overlap_summary']['deterministic_overall_duplicate_rate']}")
    dva = results["primary_comparison_d_vs_a"]["results_by_window"].get("LONG", {})
    print(f"D_vs_A LONG: D={dva.get('fixed_success_rate')} rand={dva.get('random_baseline_mean_rate')} "
          f"p_mc={dva.get('p_value_mc_one_sided_fixed_better')} dir={dva.get('effect_direction')}")
    print(f"wrote {out_json}")
    print(f"wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
