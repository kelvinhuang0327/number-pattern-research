"""
P280AW — BIG 6/49 Private Ticket Decision Runner

SAFETY NOTICE: This runner produces local private reference packs only.
- No edge claim. No publication. No official target. No official deadline.
- P280AT result: NULL — no strategy beats diversified random at k>=3.
- Default recommendation: use diversified_random_pack for any budget k>=3.
- Strategy tickets are observation/tracking reference only.
- Never commits live/current private ticket numbers to the repo.

Usage:
    python3 tools/p280aw_big649_private_ticket_decision_runner.py [--mode MODE] [--budget K] [--seed S] [--db PATH]

Modes: strategy_reference_pack | diversified_random_pack | hybrid_pack |
       contribution_report | summary_recommendation | all
"""

import argparse
import hashlib
import itertools
import json
import math
import os
import random
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Constants ──────────────────────────────────────────────────────────────────

TASK_ID = "P280AW"
SCHEMA_VERSION = "1.0.0"

NULL_WARNING = (
    "P280AT_NULL: No BIG 6/49 strategy has demonstrated reliable edge over "
    "equal-budget diversified random (Bonferroni-corrected, k>=3). "
    "Strategy tickets are included for observation/tracking ONLY. "
    "This runner does NOT claim improved winning probability."
)

ADAPTER_DIGEST_EXPECTED = (
    "b8ceac657f081bbf2be6ae0fabe6adbce564ea3a4b4cb77ab610035d0e4a800a"
)

P280AT_ARTIFACT = (
    "outputs/research/p280at_big649_strategy_ranking_replay_20260619.json"
)

DB_DEFAULT = "lottery_api/data/lottery_v2.db"
CANONICAL_VIEW = "draws_big_lotto_canonical_main"
BIG_POOL = list(range(1, 50))  # 1..49
TICKET_SIZE = 6

# Conservative hybrid defaults (P280AT NULL: random dominates at k>=3)
HYBRID_STRATEGY_COUNTS = {3: 0, 5: 1, 7: 1, 11: 2}


# ── Frozen strategy adapter pack (from P280AQ, digest-pinned) ──────────────────

FROZEN_STRATEGY_PACK = [
    {"strategy_id": "bet2_fourier_expansion_biglotto",  "ticket": [8, 12, 37, 38, 44, 46]},
    {"strategy_id": "biglotto_deviation_2bet",           "ticket": [6, 16, 20, 22, 47, 48]},
    {"strategy_id": "biglotto_echo_aware_3bet",          "ticket": [6, 16, 20, 25, 28, 37]},
    {"strategy_id": "biglotto_triple_strike",            "ticket": [8, 12, 37, 38, 44, 47]},
    {"strategy_id": "biglotto_ts3_markov_4bet_w30",      "ticket": [2, 29, 30, 31, 34, 42]},
    {"strategy_id": "cold_complement_biglotto",          "ticket": [16, 20, 22, 25, 39, 47]},
    {"strategy_id": "coldpool15_biglotto",               "ticket": [6,  7, 11, 12, 18, 41]},
    {"strategy_id": "fourier30_markov30_biglotto",       "ticket": [12, 14, 15, 25, 32, 40]},
    {"strategy_id": "markov_2bet_biglotto",              "ticket": [16, 19, 20, 36, 45, 47]},
    {"strategy_id": "markov_single_biglotto",            "ticket": [11, 14, 18, 22, 25, 39]},
    {"strategy_id": "ts3_regime_3bet",                   "ticket": [3,  9, 21, 30, 31, 34]},
]

# P280AT contribution ranking order (rank 1 = most marginal coverage)
AT_CONTRIBUTION_RANK_ORDER = [
    "biglotto_ts3_markov_4bet_w30",
    "ts3_regime_3bet",
    "fourier30_markov30_biglotto",
    "markov_2bet_biglotto",
    "coldpool15_biglotto",
    "cold_complement_biglotto",
    "markov_single_biglotto",
    "biglotto_deviation_2bet",
    "biglotto_echo_aware_3bet",
    "bet2_fourier_expansion_biglotto",
    "biglotto_triple_strike",
]


_BET_INDEX = 1


def _compute_pack_digest(pack: List[dict]) -> str:
    # Canonical format matches big649_no_db_strategy_output_adapter.compute_strategy_output_digest:
    # fields: bet_index, predicted_main_numbers, strategy_id; sort_keys=True; trailing newline
    by_id = {t["strategy_id"]: sorted(t["ticket"]) for t in pack}
    canonical = [
        {"bet_index": _BET_INDEX, "predicted_main_numbers": by_id[sid], "strategy_id": sid}
        for sid in AT_CONTRIBUTION_RANK_ORDER
        if sid in by_id
    ]
    # Use frozen strategy order (BIG649_FROZEN_STRATEGY_IDS order from FROZEN_STRATEGY_PACK)
    order = [t["strategy_id"] for t in FROZEN_STRATEGY_PACK]
    canonical = [
        {"bet_index": _BET_INDEX, "predicted_main_numbers": by_id[sid], "strategy_id": sid}
        for sid in order
    ]
    rendered = json.dumps(
        canonical,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256((rendered + "\n").encode("utf-8")).hexdigest()


def verify_adapter_digest(pack: List[dict]) -> bool:
    return _compute_pack_digest(pack) == ADAPTER_DIGEST_EXPECTED


# ── DB helpers ─────────────────────────────────────────────────────────────────

def open_ro_db(db_path: str):
    uri = f"file://{os.path.abspath(db_path)}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.execute("PRAGMA query_only=ON")
    return conn


def db_stat(db_path: str) -> dict:
    p = Path(db_path)
    if not p.exists():
        return {"exists": False}
    s = p.stat()
    return {
        "exists": True,
        "size_bytes": s.st_size,
        "mtime": s.st_mtime,
    }


def get_latest_local_draw(conn) -> dict:
    cur = conn.cursor()
    cur.execute(
        f"SELECT draw, date, numbers, special FROM {CANONICAL_VIEW} "
        f"ORDER BY CAST(draw AS INTEGER) DESC LIMIT 1"
    )
    row = cur.fetchone()
    if row is None:
        return {}
    draw_id, date, numbers_raw, special = row
    numbers = json.loads(numbers_raw) if isinstance(numbers_raw, str) else numbers_raw
    return {"draw_id": draw_id, "date": date, "numbers": numbers, "special": special}


def get_private_local_ref_id(latest_draw_id: str) -> str:
    """Synthetic local reference only — NOT official target, NOT official deadline."""
    return str(int(latest_draw_id) + 1)


# ── Coverage / overlap metrics ─────────────────────────────────────────────────

def pair_overlap(t1: list, t2: list) -> int:
    return len(set(t1) & set(t2))


def coverage_metrics(tickets: list[list]) -> dict:
    if not tickets:
        return {}
    n = len(tickets)
    all_numbers = set()
    for t in tickets:
        all_numbers.update(t)
    overlaps = [
        pair_overlap(tickets[i], tickets[j])
        for i in range(n) for j in range(i + 1, n)
    ]
    duplicates = sum(
        1 for i in range(n) for j in range(i + 1, n)
        if sorted(tickets[i]) == sorted(tickets[j])
    )
    return {
        "ticket_count": n,
        "unique_numbers_covered": len(all_numbers),
        "coverage_fraction": round(len(all_numbers) / len(BIG_POOL), 4),
        "max_pair_overlap": max(overlaps) if overlaps else 0,
        "mean_pair_overlap": round(sum(overlaps) / len(overlaps), 4) if overlaps else 0,
        "duplicate_ticket_count": duplicates,
        "high_overlap_pairs": sum(1 for o in overlaps if o >= 4),
    }


def marginal_coverage(tickets: list[list]) -> list[dict]:
    seen: set = set()
    result = []
    for i, t in enumerate(tickets):
        new_nums = set(t) - seen
        seen.update(t)
        result.append({"index": i, "marginal_new_numbers": len(new_nums)})
    return result


# ── Diversified random pack ────────────────────────────────────────────────────

def _random_ticket(rng: random.Random) -> list[int]:
    return sorted(rng.sample(BIG_POOL, TICKET_SIZE))


def diversified_random_pack(k: int, seed: int, existing_tickets: Optional[List[List[int]]] = None) -> List[List[int]]:
    """Generate k low-overlap random tickets using deterministic seed."""
    rng = random.Random(seed)
    tickets: list[list] = list(existing_tickets) if existing_tickets else []
    attempts = 0
    max_attempts = k * 500

    while len(tickets) < (len(existing_tickets or []) + k) and attempts < max_attempts:
        attempts += 1
        candidate = _random_ticket(rng)
        # Require max pair overlap <= 3 with any existing ticket
        if all(pair_overlap(candidate, t) <= 3 for t in tickets):
            if sorted(candidate) not in [sorted(t) for t in tickets]:
                tickets.append(candidate)

    # Fallback: just fill without strict overlap
    while len(tickets) < (len(existing_tickets or []) + k):
        candidate = _random_ticket(rng)
        if sorted(candidate) not in [sorted(t) for t in tickets]:
            tickets.append(candidate)

    return tickets[len(existing_tickets or []):]


# ── Runner modes ───────────────────────────────────────────────────────────────

def mode_strategy_reference_pack() -> dict:
    digest_ok = verify_adapter_digest(FROZEN_STRATEGY_PACK)
    tickets = [t["ticket"] for t in FROZEN_STRATEGY_PACK]
    metrics = coverage_metrics(tickets)
    return {
        "mode": "strategy_reference_pack",
        "p280at_null_warning": NULL_WARNING,
        "adapter_digest": ADAPTER_DIGEST_EXPECTED,
        "adapter_digest_verified": digest_ok,
        "label": "OBSERVATION_TRACKING_ONLY_NO_EDGE_CLAIM",
        "ticket_count": len(FROZEN_STRATEGY_PACK),
        "tickets": FROZEN_STRATEGY_PACK,
        "coverage_metrics": metrics,
    }


def mode_diversified_random_pack(k: int, seed: int) -> dict:
    tickets = diversified_random_pack(k, seed)
    metrics = coverage_metrics(tickets)
    return {
        "mode": "diversified_random_pack",
        "p280at_null_warning": NULL_WARNING,
        "label": "LOW_OVERLAP_COVERAGE_NO_EDGE_CLAIM",
        "budget_k": k,
        "seed": seed,
        "tickets": [{"index": i, "ticket": t} for i, t in enumerate(tickets)],
        "coverage_metrics": metrics,
        "note": (
            "P280AT shows diversified random outperforms the strategy pack at k>=3. "
            "This is the recommended practical default for budget k>=3."
        ),
    }


def mode_hybrid_pack(k: int, seed: int) -> dict:
    n_strategy = HYBRID_STRATEGY_COUNTS.get(k, min(2, k))
    n_random = k - n_strategy

    # Pick top-ranked strategy tickets by AT contribution rank
    strategy_slots = [
        t for sid in AT_CONTRIBUTION_RANK_ORDER
        for t in FROZEN_STRATEGY_PACK if t["strategy_id"] == sid
    ][:n_strategy]

    strategy_tickets = [t["ticket"] for t in strategy_slots]
    random_tickets = diversified_random_pack(n_random, seed, existing_tickets=strategy_tickets)
    all_tickets = strategy_tickets + random_tickets
    metrics = coverage_metrics(all_tickets)

    return {
        "mode": "hybrid_pack",
        "p280at_null_warning": NULL_WARNING,
        "label": "HYBRID_CONSERVATIVE_NO_EDGE_CLAIM",
        "budget_k": k,
        "seed": seed,
        "strategy_ticket_count": n_strategy,
        "random_ticket_count": n_random,
        "strategy_tickets": [
            {"strategy_id": t["strategy_id"], "ticket": t["ticket"], "role": "observation_tracking"}
            for t in strategy_slots
        ],
        "random_tickets": [
            {"index": i, "ticket": t, "role": "diversified_coverage"}
            for i, t in enumerate(random_tickets)
        ],
        "coverage_metrics": metrics,
        "conservative_default_note": (
            f"k={k}: {n_strategy} strategy (tracking only) + {n_random} diversified random. "
            "P280AT NULL: random dominates at k>=3. Strategy slots are reference only."
        ),
    }


def mode_contribution_report() -> dict:
    ranked_tickets = [
        t["ticket"] for sid in AT_CONTRIBUTION_RANK_ORDER
        for t in FROZEN_STRATEGY_PACK if t["strategy_id"] == sid
    ]
    marginal = marginal_coverage(ranked_tickets)
    all_metrics = coverage_metrics(ranked_tickets)

    high_overlap_warnings = []
    for i in range(len(ranked_tickets)):
        for j in range(i + 1, len(ranked_tickets)):
            ov = pair_overlap(ranked_tickets[i], ranked_tickets[j])
            if ov >= 4:
                high_overlap_warnings.append({
                    "ticket_a_index": i,
                    "ticket_b_index": j,
                    "strategy_a": AT_CONTRIBUTION_RANK_ORDER[i],
                    "strategy_b": AT_CONTRIBUTION_RANK_ORDER[j],
                    "overlap_count": ov,
                })

    return {
        "mode": "contribution_report",
        "p280at_null_warning": NULL_WARNING,
        "strategy_count": len(FROZEN_STRATEGY_PACK),
        "coverage_metrics": all_metrics,
        "marginal_coverage_by_at_rank": [
            {
                "rank": i + 1,
                "strategy_id": AT_CONTRIBUTION_RANK_ORDER[i],
                "marginal_new_numbers": marginal[i]["marginal_new_numbers"],
            }
            for i in range(len(marginal))
        ],
        "high_overlap_warnings": high_overlap_warnings,
        "internal_redundancy_note": (
            "P280AT: the frozen primaries are internally redundant; "
            "the strategy pack produces lower distinct-number coverage "
            "than independent random tickets at k>=3."
        ),
    }


def mode_summary_recommendation(k: int, seed: int) -> dict:
    n_strategy = HYBRID_STRATEGY_COUNTS.get(k, min(2, k))
    return {
        "mode": "summary_recommendation",
        "p280at_null_warning": NULL_WARNING,
        "budget_k": k,
        "seed": seed,
        "default_recommendation": "diversified_random_pack",
        "reasoning": (
            "P280AT proved NULL: no strategy combination beats equal-budget diversified "
            f"random at k>={min(3, k)}. Use diversified_random_pack as the default. "
            "Strategy tickets may be included for personal observation/tracking only."
        ),
        "practical_guide": {
            "k_3":  "0 strategy + 3 diversified random (recommended)",
            "k_5":  "1 strategy (rank-1 by AT contribution) + 4 diversified random",
            "k_7":  "1 strategy + 6 diversified random",
            "k_11": "label all as diversified_random; strategy pack = optional tracking overlay",
        },
        "what_not_to_claim": [
            "improved winning probability",
            "strategy edge over random",
            "official target or deadline",
            "publication readiness",
        ],
    }


# ── Main CLI ────────────────────────────────────────────────────────────────────

def parse_args(argv=None):
    p = argparse.ArgumentParser(description="P280AW BIG 6/49 Private Ticket Decision Runner")
    p.add_argument("--mode", default="summary_recommendation",
                   choices=["strategy_reference_pack", "diversified_random_pack",
                            "hybrid_pack", "contribution_report",
                            "summary_recommendation", "all"])
    p.add_argument("--budget", type=int, default=5, choices=[3, 5, 7, 11])
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--db", default=None)
    p.add_argument("--json", action="store_true", help="Output JSON")
    return p.parse_args(argv)


def run(argv=None) -> dict:
    args = parse_args(argv)

    # Locate repo root relative to this script
    repo_root = Path(__file__).resolve().parent.parent
    db_path = args.db or str(repo_root / DB_DEFAULT)

    # DB stat before read
    stat_before = db_stat(db_path)

    # Read latest local draw (read-only)
    latest_draw: dict = {}
    db_opened = False
    if Path(db_path).exists():
        try:
            conn = open_ro_db(db_path)
            db_opened = True
            latest_draw = get_latest_local_draw(conn)
            conn.close()
        except Exception as exc:
            latest_draw = {"error": str(exc)}
    else:
        latest_draw = {"error": f"DB not found: {db_path}"}

    # Synthetic private local reference id — NOT official target
    private_local_ref_id = None
    if latest_draw.get("draw_id"):
        private_local_ref_id = get_private_local_ref_id(latest_draw["draw_id"])

    # DB stat after read
    stat_after = db_stat(db_path)

    # Verify no DB drift
    db_drift = (stat_before.get("size_bytes") != stat_after.get("size_bytes"))

    # Verify adapter digest
    digest_ok = verify_adapter_digest(FROZEN_STRATEGY_PACK)

    # Build outputs
    modes_to_run = (
        ["strategy_reference_pack", "diversified_random_pack",
         "hybrid_pack", "contribution_report", "summary_recommendation"]
        if args.mode == "all" else [args.mode]
    )

    results: Dict[str, Any] = {}
    for mode in modes_to_run:
        if mode == "strategy_reference_pack":
            results[mode] = mode_strategy_reference_pack()
        elif mode == "diversified_random_pack":
            results[mode] = mode_diversified_random_pack(args.budget, args.seed)
        elif mode == "hybrid_pack":
            results[mode] = mode_hybrid_pack(args.budget, args.seed)
        elif mode == "contribution_report":
            results[mode] = mode_contribution_report()
        elif mode == "summary_recommendation":
            results[mode] = mode_summary_recommendation(args.budget, args.seed)

    output = {
        "task_id": TASK_ID,
        "schema_version": SCHEMA_VERSION,
        "final_classification": "P280AW_PRIVATE_TICKET_DECISION_RUNNER_PR_OPEN_NO_PUBLICATION_NO_CLAIM",
        "p280at_null_warning": NULL_WARNING,
        "adapter_digest_expected": ADAPTER_DIGEST_EXPECTED,
        "adapter_digest_verified": digest_ok,
        "database_access": {
            "opened": db_opened,
            "queried": db_opened,
            "copied": False,
            "written": False,
            "db_path": db_path,
            "stat_before": stat_before,
            "stat_after": stat_after,
            "drift_detected": db_drift,
        },
        "latest_local_draw_source": "local_db_read_only",
        "latest_local_draw": latest_draw,
        "private_local_ref_id": private_local_ref_id,
        "private_local_ref_id_note": "NOT official target. NOT official deadline. Synthetic local id only.",
        "official_target_lookup_performed": False,
        "official_deadline_lookup_performed": False,
        "current_live_ticket_numbers_committed": False,
        "prediction_success_claim": False,
        "strategy_promoted": False,
        "activation": False,
        "real_publication_performed": False,
        "pre_draw_manifest_created": False,
        "publication_pr_created": False,
        "results": results,
    }

    if args.json:
        print(json.dumps(output, indent=2))
    else:
        _print_human(output, args)

    return output


def _print_human(output: dict, args) -> None:
    print("=" * 70)
    print(f"P280AW BIG 6/49 Private Ticket Decision Runner")
    print("=" * 70)
    print(f"WARNING: {NULL_WARNING}")
    print()

    ld = output.get("latest_local_draw", {})
    if ld.get("draw_id"):
        print(f"Latest local draw:    {ld['draw_id']} ({ld['date']})")
        print(f"Private local ref id: {output['private_local_ref_id']} [NOT official target]")
    print(f"Adapter digest OK:    {output['adapter_digest_verified']}")
    print(f"DB opened/queried:    {output['database_access']['opened']}/{output['database_access']['queried']}")
    print(f"DB copied/written:    False/False")
    print()

    for mode_name, result in output["results"].items():
        print(f"── {mode_name} ──")
        if mode_name == "strategy_reference_pack":
            for t in result["tickets"]:
                print(f"  {t['strategy_id']}: {t['ticket']}")
        elif mode_name in ("diversified_random_pack",):
            for t in result["tickets"]:
                print(f"  [{t['index']}]: {t['ticket']}")
        elif mode_name == "hybrid_pack":
            for t in result.get("strategy_tickets", []):
                print(f"  [strategy] {t['strategy_id']}: {t['ticket']}")
            for t in result.get("random_tickets", []):
                print(f"  [random  ] {t['ticket']}")
        elif mode_name == "contribution_report":
            cm = result["coverage_metrics"]
            print(f"  Coverage: {cm['unique_numbers_covered']}/{len(BIG_POOL)} "
                  f"({cm['coverage_fraction']*100:.1f}%)")
            print(f"  Max pair overlap: {cm['max_pair_overlap']}")
            print(f"  Duplicates: {cm['duplicate_ticket_count']}")
            print(f"  High-overlap pairs (>=4): {cm['high_overlap_pairs']}")
        elif mode_name == "summary_recommendation":
            print(f"  Default: {result['default_recommendation']}")
            print(f"  {result['reasoning']}")
        print()


if __name__ == "__main__":
    run()
