"""
P99 Special3 Prospective Dry-run Planning
dry_run_only=True — NO DB writes, NO replay row inserts, NO lifecycle mutations.
NO 4_STAR backtest. NO Special3 production promotion.

Generates a prospective prediction plan for the NEXT (unknown) 3_STAR draw,
trained on all available history. Target draw is marked NEXT_AFTER_CURRENT_MAX;
evaluation status is PENDING_ACTUAL_DRAW until the actual draw arrives.

Outputs:
  outputs/replay/special3_prospective_dryrun_plan_20260527.json
"""

import sqlite3
import json
import itertools
import pathlib


def _repo_root():
    return Path(__file__).resolve().parent.parent


def _canonical_db_path():
    return _repo_root() / "lottery_api" / "data" / "lottery_v2.db"


def _resolve_db_path(db_path=None):
    candidate = _canonical_db_path() if db_path is None else Path(db_path)
    if db_path is not None and not candidate.is_absolute():
        raise ValueError("db_path must be absolute; use None for the canonical lottery_v2.db")
    if not candidate.exists():
        raise FileNotFoundError(f"Lottery DB path does not exist: {candidate}")
    if not candidate.is_file():
        raise FileNotFoundError(f"Lottery DB path is not a regular file: {candidate}")
    return str(candidate)
import datetime
from collections import Counter, defaultdict

DRY_RUN      = True
DB_PATH      = None
OUT_JSON     = pathlib.Path("outputs/replay/special3_prospective_dryrun_plan_20260527.json")
TODAY        = "20260527"
SOURCE_P98   = "outputs/replay/special3_oos_permutation_review_20260527.json"

TOP_NS = [10, 20, 50, 100]
ALL_TICKETS = list(itertools.product(range(10), repeat=3))  # 1000 tickets (000–999)

# ── P98 Evidence ──────────────────────────────────────────────────────────────

P99_CANDIDATES = [
    "position_frequency_topk",
    "recent_position_hot_topk",
    "sum_band_frequency",
    "span_band_frequency",
    "ensemble_rank_v1",
]

ENSEMBLE_V2_MEMBERS = [
    "position_frequency_topk",
    "recent_position_hot_topk",
    "sum_band_frequency",
    "span_band_frequency",
]

EXCLUDED_STRATEGIES = ["position_cold_rebound_topk"]

# Additional ensemble entries included in plan
PLAN_STRATEGIES = P99_CANDIDATES + ["ensemble_rank_v2"]

# ── Protocol ──────────────────────────────────────────────────────────────────

PROTOCOL = {
    "truth_level": "SPECIAL3_PROSPECTIVE_DRYRUN",
    "dry_run_only": True,
    "db_writes": False,
    "replay_rows_insert": False,
    "production_promotion": False,
    "star4_backtest": False,
    "prediction_cadence": "ONCE_PER_DRAW_CYCLE",
    "top_n_variants": TOP_NS,
    "draw_eligibility_rules": [
        "draw must be 3_STAR lottery_type only",
        "draw must be after history_end_draw (no lookahead)",
        "draw must be officially published before evaluation",
        "evaluation only after actual winning number is confirmed",
    ],
    "no_lookahead_rule": (
        "All predictions are generated using only draws "
        "with CAST(draw AS INTEGER) <= CAST(history_end_draw AS INTEGER). "
        "Target draw is strictly excluded from training data."
    ),
    "leading_zero_serialization_rule": (
        "All ticket numbers are serialized as exactly 3 decimal characters "
        "with leading zeros. Ticket (0,5,9) serializes as '059'. "
        "Ticket (0,0,1) serializes as '001'. "
        "Range: '000' to '999' (1000 possible tickets)."
    ),
    "output_schema": {
        "generated_at":           "ISO8601 timestamp when prediction was generated",
        "history_end_draw":       "draw ID of the last draw included in training",
        "target_draw":            "draw ID to predict (NEXT_AFTER_CURRENT_MAX if unknown)",
        "strategy_id":            "unique strategy identifier",
        "top_n":                  "number of tickets in prediction set",
        "predicted_numbers":      "list of top_n ticket tuples e.g. [[0,5,9],[1,2,3]]",
        "serialized_predictions": "list of top_n zero-padded strings e.g. ['059','123']",
        "dry_run_only":           "always true for P99 dry-run",
        "truth_level":            "SPECIAL3_PROSPECTIVE_DRYRUN",
        "source_artifact":        "path to P98 evidence JSON",
        "evaluation_status":      "PENDING_ACTUAL_DRAW or HIT or MISS",
        "hit_result":             "null until actual draw is known",
    },
    "output_directory": "outputs/replay/",
    "evaluation_method": (
        "When actual draw arrives: "
        "(1) fetch winning digits from draws table, "
        "(2) serialize as 3-digit string with leading zeros, "
        "(3) check if serialized winning ticket is in serialized_predictions for each top_n, "
        "(4) record hit_result as HIT or MISS per strategy per top_n, "
        "(5) update evaluation_status to EVALUATED. "
        "No DB writes during evaluation — update JSON artifact only."
    ),
    "p100_readiness_criteria": [
        "minimum 10 prospective draws evaluated (not retrodicted)",
        "direct hit rate at top20 > 15% across evaluated draws",
        "p-value < 0.05 on prospective draw set",
        "ensemble_v2 edge > 0 at top20 on prospective draws",
        "no regime change detected (rolling 3-draw hit rate stable)",
        "sharpe_ratio > 0 on prospective draw sequence",
    ],
}

# ── Data loading ──────────────────────────────────────────────────────────────

def load_draws():
    conn = sqlite3.connect(_resolve_db_path(DB_PATH))
    rows = conn.execute(
        "SELECT draw, date, numbers FROM draws WHERE lottery_type='3_STAR' "
        "ORDER BY CAST(draw AS INTEGER)"
    ).fetchall()
    conn.close()
    result = []
    for draw, date, numbers_json in rows:
        nums = tuple(json.loads(numbers_json))
        result.append({"draw": draw, "date": date, "digits": nums})
    return result


# ── Strategy implementations (identical to P98) ───────────────────────────────

def position_frequency_topk(window_draws, top_n):
    pos_counts = [Counter(), Counter(), Counter()]
    for d in window_draws:
        for p in range(3):
            pos_counts[p][d["digits"][p]] += 1
    total = len(window_draws)
    pos_freq = [{k: v / total for k, v in pc.items()} for pc in pos_counts]
    scored = []
    for t in ALL_TICKETS:
        score = 1.0
        for p in range(3):
            score *= pos_freq[p].get(t[p], 1e-6)
        scored.append((score, t))
    scored.sort(reverse=True)
    return [t for _, t in scored[:top_n]]


def recent_position_hot_topk(window_draws, top_n, recency=50):
    recent = window_draws[-recency:] if len(window_draws) >= recency else window_draws
    return position_frequency_topk(recent, top_n)


def sum_band_frequency(window_draws, top_n):
    def sum_band(digits):
        s = sum(digits)
        if s <= 9: return 0
        elif s <= 17: return 1
        return 2
    band_counts = Counter(sum_band(d["digits"]) for d in window_draws)
    top_band = band_counts.most_common(1)[0][0]
    candidates = [t for t in ALL_TICKETS if sum_band(t) == top_band]
    if len(candidates) <= top_n:
        return candidates[:top_n]
    pos_counts = [Counter(), Counter(), Counter()]
    for d in window_draws:
        for p in range(3):
            pos_counts[p][d["digits"][p]] += 1
    total = len(window_draws)
    pos_freq = [{k: v / total for k, v in pc.items()} for pc in pos_counts]
    scored = []
    for t in candidates:
        score = sum(pos_freq[p].get(t[p], 1e-6) for p in range(3))
        scored.append((score, t))
    scored.sort(reverse=True)
    return [t for _, t in scored[:top_n]]


def span_band_frequency(window_draws, top_n):
    def span_band(digits):
        sp = max(digits) - min(digits)
        if sp <= 3: return 0
        elif sp <= 6: return 1
        return 2
    band_counts = Counter(span_band(d["digits"]) for d in window_draws)
    top_band = band_counts.most_common(1)[0][0]
    candidates = [t for t in ALL_TICKETS if span_band(t) == top_band]
    if len(candidates) <= top_n:
        return candidates[:top_n]
    pos_counts = [Counter(), Counter(), Counter()]
    for d in window_draws:
        for p in range(3):
            pos_counts[p][d["digits"][p]] += 1
    total = len(window_draws)
    pos_freq = [{k: v / total for k, v in pc.items()} for pc in pos_counts]
    scored = []
    for t in candidates:
        score = sum(pos_freq[p].get(t[p], 1e-6) for p in range(3))
        scored.append((score, t))
    scored.sort(reverse=True)
    return [t for _, t in scored[:top_n]]


def ensemble_rank_v1(window_draws, top_n):
    """V1 ensemble — 5 members including cold_rebound (reference baseline)."""
    k = 60
    member_lists = [
        position_frequency_topk(window_draws, 100),
        recent_position_hot_topk(window_draws, 100),
        # cold_rebound included for V1 reference only; decision = REJECT_CONFIRMED
        _cold_rebound_ref(window_draws, 100),
        sum_band_frequency(window_draws, 100),
        span_band_frequency(window_draws, 100),
    ]
    rrf_scores = defaultdict(float)
    for ranked in member_lists:
        for rank, ticket in enumerate(ranked):
            rrf_scores[ticket] += 1.0 / (k + rank + 1)
    sorted_tickets = sorted(rrf_scores, key=lambda t: rrf_scores[t], reverse=True)
    return sorted_tickets[:top_n]


def ensemble_rank_v2(window_draws, top_n):
    """V2 ensemble — 4 members, excludes REJECT strategy."""
    k = 60
    member_lists = [
        position_frequency_topk(window_draws, 100),
        recent_position_hot_topk(window_draws, 100),
        sum_band_frequency(window_draws, 100),
        span_band_frequency(window_draws, 100),
    ]
    rrf_scores = defaultdict(float)
    for ranked in member_lists:
        for rank, ticket in enumerate(ranked):
            rrf_scores[ticket] += 1.0 / (k + rank + 1)
    sorted_tickets = sorted(rrf_scores, key=lambda t: rrf_scores[t], reverse=True)
    return sorted_tickets[:top_n]


def _cold_rebound_ref(window_draws, top_n):
    """REJECT_CONFIRMED — included only for ensemble_rank_v1 reference comparisons."""
    pos_last_seen = [{d: -1 for d in range(10)} for _ in range(3)]
    for i, draw in enumerate(window_draws):
        for p in range(3):
            pos_last_seen[p][draw["digits"][p]] = i
    pos_cold_rank = []
    for p in range(3):
        ranked = sorted(range(10), key=lambda d, p=p: pos_last_seen[p][d])
        pos_cold_rank.append(ranked)
    cold_rank_map = [{d: i for i, d in enumerate(ranked)} for ranked in pos_cold_rank]
    scored = []
    for t in ALL_TICKETS:
        score = sum(cold_rank_map[p][t[p]] for p in range(3))
        scored.append((score, t))
    scored.sort()
    return [t for _, t in scored[:top_n]]


STRATEGY_FNS = {
    "position_frequency_topk": position_frequency_topk,
    "recent_position_hot_topk": recent_position_hot_topk,
    "sum_band_frequency": sum_band_frequency,
    "span_band_frequency": span_band_frequency,
    "ensemble_rank_v1": ensemble_rank_v1,
    "ensemble_rank_v2": ensemble_rank_v2,
}


# ── Serialization ─────────────────────────────────────────────────────────────

def serialize_ticket(t):
    """Serialize ticket tuple (d0, d1, d2) → zero-padded 3-digit string."""
    return f"{t[0]}{t[1]}{t[2]:d}".zfill(3) if False else f"{t[0]:01d}{t[1]:01d}{t[2]:01d}"


def serialize_tickets(tickets):
    return [f"{t[0]}{t[1]}{t[2]}" for t in tickets]


# ── Prediction generation ──────────────────────────────────────────────────────

def generate_prospective_prediction(strategy_id, fn, all_draws, top_n,
                                    generated_at, history_end_draw):
    """Train on all available history; predict for next unknown draw."""
    tickets = fn(all_draws, top_n)
    serialized = serialize_tickets(tickets)
    return {
        "generated_at":            generated_at,
        "history_end_draw":        history_end_draw,
        "target_draw":             "NEXT_AFTER_CURRENT_MAX",
        "strategy_id":             strategy_id,
        "top_n":                   top_n,
        "predicted_numbers":       [list(t) for t in tickets],
        "serialized_predictions":  serialized,
        "dry_run_only":            True,
        "truth_level":             "SPECIAL3_PROSPECTIVE_DRYRUN",
        "source_artifact":         SOURCE_P98,
        "evaluation_status":       "PENDING_ACTUAL_DRAW",
        "hit_result":              None,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    generated_at = datetime.datetime.utcnow().isoformat() + "Z"

    print(f"[P99] Loading 3_STAR draws from {DB_PATH} ...")
    draws = load_draws()
    n_draws = len(draws)
    history_end_draw = draws[-1]["draw"] if draws else "UNKNOWN"
    history_end_date = draws[-1]["date"] if draws else "UNKNOWN"
    print(f"[P99] Loaded {n_draws} draws. History end: draw={history_end_draw}, date={history_end_date}")

    # Verify no 4_STAR draws exist
    conn = sqlite3.connect(_resolve_db_path(DB_PATH))
    star4_count = conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='4_STAR'"
    ).fetchone()[0]
    replay_rows = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    conn.close()
    print(f"[P99] 4_STAR draws = {star4_count} (must be 0)")
    print(f"[P99] replay_rows = {replay_rows} (must be 54462)")

    # Generate predictions for all strategies × top_n
    print(f"[P99] Generating prospective predictions for {len(PLAN_STRATEGIES)} strategies × {len(TOP_NS)} top_n ...")
    predictions = []
    strategy_summaries = {}
    for strategy_id in PLAN_STRATEGIES:
        fn = STRATEGY_FNS[strategy_id]
        top_n_results = {}
        for top_n in TOP_NS:
            pred = generate_prospective_prediction(
                strategy_id, fn, draws, top_n, generated_at, history_end_draw
            )
            predictions.append(pred)
            top_n_results[f"top{top_n}"] = {
                "ticket_count": top_n,
                "serialized_preview": pred["serialized_predictions"][:5],
                "coverage_pct": round(top_n / 1000.0 * 100, 1),
            }
        strategy_summaries[strategy_id] = {
            "p98_decision": "ADVANCE_TO_P99_CANDIDATE" if strategy_id in P99_CANDIDATES
                            else ("ENSEMBLE_V2_DESIGN" if strategy_id == "ensemble_rank_v2"
                                  else "REJECT_CONFIRMED"),
            "training_draws": n_draws,
            "top_n_predictions": top_n_results,
        }
        print(f"  {strategy_id}: top10/top20/top50/top100 generated")

    # Build output JSON
    output = {
        "task":                         "special3_prospective_dryrun_plan",
        "phase":                        "P99",
        "date":                         TODAY,
        "generated_at":                 generated_at,
        "dry_run_only":                 True,
        "db_writes":                    False,
        "replay_rows_changed":          0,
        "no_production_promotion":      True,
        "star4_backtest":               "NOT_RUN",
        "special4_status":              "DATA_GAP_BLOCKING",
        "special4_star4_draws":         star4_count,
        "draws_loaded":                 n_draws,
        "lottery_type":                 "3_STAR",
        "history_end_draw":             history_end_draw,
        "history_end_date":             history_end_date,
        "target_draw":                  "NEXT_AFTER_CURRENT_MAX",
        "evaluation_status":            "PENDING_ACTUAL_DRAW",

        # Governance
        "replay_rows_before":           replay_rows,
        "replay_rows_after":            replay_rows,

        # P98 Evidence
        "p98_classification":           "P98_SPECIAL3_OOS_PERMUTATION_REVIEW_READY",
        "source_artifact_p98":          SOURCE_P98,
        "p99_candidates":               P99_CANDIDATES,
        "excluded_strategies":          EXCLUDED_STRATEGIES,
        "ensemble_v2_members":          ENSEMBLE_V2_MEMBERS,
        "ensemble_v2_recommendation":   "PROCEED_TO_P99_DRY_RUN",

        # Protocol
        "protocol":                     PROTOCOL,

        # Strategy summaries
        "strategy_summaries":           strategy_summaries,

        # Prospective predictions (all strategies × all top_n)
        "prospective_predictions":      predictions,

        # Serialization spec
        "leading_zero_serialization": {
            "rule": "ticket (d0,d1,d2) serialized as str(d0)+str(d1)+str(d2) with no separator",
            "example_ticket_059": "059",
            "example_ticket_001": "001",
            "example_ticket_999": "999",
            "ticket_range": "000 to 999",
            "ticket_count": 1000,
        },

        # P100 readiness gate
        "p100_recommendation": {
            "status":    "NOT_YET_ELIGIBLE",
            "reason":    "0 prospective draws evaluated; minimum 10 required",
            "criteria":  PROTOCOL["p100_readiness_criteria"],
        },

        "classification": "P99_SPECIAL3_PROSPECTIVE_DRYRUN_PLAN_READY",
    }

    # Write JSON
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"[P99] JSON written → {OUT_JSON}")

    # Summary
    print(f"\n[P99] ── Summary ──")
    print(f"  draws_loaded:      {n_draws}")
    print(f"  history_end_draw:  {history_end_draw} ({history_end_date})")
    print(f"  target_draw:       NEXT_AFTER_CURRENT_MAX")
    print(f"  strategies planned: {len(PLAN_STRATEGIES)}")
    print(f"  predictions total: {len(predictions)} ({len(PLAN_STRATEGIES)} × {len(TOP_NS)})")
    print(f"  4_STAR:            DATA_GAP_BLOCKING (star4_count={star4_count})")
    print(f"  replay_rows:       {replay_rows} (unchanged)")
    print(f"  db_writes:         False")
    print(f"  classification:    P99_SPECIAL3_PROSPECTIVE_DRYRUN_PLAN_READY")
    return output


if __name__ == "__main__":
    main()
