#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BIG649 Measurement Export — deterministic, read-only repository generator.
=========================================================================
Task: BIG649_MEASUREMENT_EXPORT_API_UI_IMPLEMENTATION (2026-06-21)

PURPOSE (measurement & schema surfacing ONLY):
  Re-derive — directly from the canonical production DB — the *supported* fields
  of the frozen ``BIG649_HIT_DISTRIBUTION_REDUNDANCY_MEASUREMENT_CONTRACT``
  (canonical payload digest
  ``0f4c417902dedb8882d23edad1ca16152c660656e08bc64ee22f7832c472ba2a``)
  and emit ONE canonical artifact for a read-only API/UI to consume:

      outputs/research/big649_measurement_export_20260621.json

  The nine measurement sub-payloads are reproduced byte-for-byte (canonically)
  from the DB so that the embedded ``canonical_payload_digest`` equals the frozen
  contract digest; the generator raises if it does not.

EXPLICIT NON-GOALS (this generator NEVER does any of these):
  - No predictive-edge search, no best-strategy / best-combination ranking.
  - No portfolio selection, no random baseline, no p-value, no candidate class.
  - No ticket creation, no recommendation, no payout / EV / ROI, no official prize.
  - Strategy and pair rows are emitted in LEXICAL order only.

SAFETY:
  - Read-only DB access (SQLite URI ``mode=ro`` + ``PRAGMA query_only=ON`` asserted
    == 1). DB SHA-256 / size / -wal verified before and after; aborts on any drift.
  - Standard library only. No third-party imports. No /tmp read. The only file
    written is the single artifact. Deterministic: no wall-clock, no randomness.
"""

import hashlib
import json
import os
import sqlite3

# --------------------------------------------------------------------------
# Frozen configuration (Phase 0B verified anchors). These strings are part of
# the digest-bearing payload and MUST match the frozen contract verbatim.
# --------------------------------------------------------------------------
DB_PATH = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db"
LOTTERY = "BIG_LOTTO"
CANONICAL_VIEW = "draws_big_lotto_canonical_main"
REPLAY_TABLE = "strategy_prediction_replays"

MAIN_PICK = 6          # BIG649: each ticket is 6 main numbers
NUM_LO, NUM_HI = 1, 49 # BIG649 number range

SCHEMA_VERSION = "big649_measurement_contract_v1"
EXPECTED_DB_SHA256 = "539efda5874b08f7b7e25b36cd0c70e4d4d582c8df9541eec73eaa0e373650d2"
EXPECTED_CANONICAL_PAYLOAD_DIGEST = (
    "0f4c417902dedb8882d23edad1ca16152c660656e08bc64ee22f7832c472ba2a"
)

EXPECTED_ANCHORS = {
    "db_sha256": EXPECTED_DB_SHA256,
    "canonical_draws": 2117,
    "eligible_targets": 1531,
    "big_replay_rows": 24140,
    "strategy_family_size": 11,
    "causality_violations": 0,
}

# Window order is FROZEN. (name, newest_n or None==all)
WINDOW_DEFS = [
    ("REFERENCE_ALL_ELIGIBLE", None),
    ("RECENT_750", 750),
    ("RECENT_300", 300),
    ("RECENT_50", 50),
]
WINDOW_ORDER = [w[0] for w in WINDOW_DEFS]

# API query-parameter window name -> internal frozen window name.
API_WINDOW_TO_INTERNAL = {
    "all_reference": "REFERENCE_ALL_ELIGIBLE",
    "recent_750": "RECENT_750",
    "recent_300": "RECENT_300",
    "recent_50": "RECENT_50",
}

# Nine measurement sub-payloads, in the FROZEN order the canonical digest uses.
OUTPUT_FILES = [
    "frozen_strategy_family",
    "canonical_target_windows",
    "per_strategy_ticket_level_distribution",
    "per_strategy_target_level_distribution",
    "per_strategy_prize_aware_distribution",
    "per_strategy_redundancy_diagnostics",
    "pairwise_ticket_overlap_diagnostics",
    "frozen_measurement_contract",
    "big649_measurement_export_schema",
]

MEASUREMENT_ONLY_NOTICE = (
    "MEASUREMENT_AND_SCHEMA_FEASIBILITY_ONLY. Not a ranking, portfolio, random "
    "baseline, p-value, candidate classification, recommendation, prediction-success "
    "claim, payout, ROI, or official-prize statement. Rows are lexical and unranked."
)

LOCAL_HISTORICAL_MEASUREMENT_DISCLAIMER = (
    "本資料為本地歷史回放量測 (local historical replay measurement)。"
    "非預測、非推薦、非排名、非下注建議；全部歷史窗格 (REFERENCE_ALL_ELIGIBLE) 僅供參考，"
    "不得用於策略晉級、挑選或部署。"
)


# --------------------------------------------------------------------------
# Deterministic serialization helpers
# --------------------------------------------------------------------------
def _canon(obj):
    """Canonical JSON string: sorted keys, compact, utf-8 preserved."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def digest_obj(obj):
    return _sha256_text(_canon(obj))


def _rate(num, den):
    """Rate as float or None when denominator is 0 (never impute 0)."""
    return (num / den) if den else None


def _neumaier_sum(values):
    """Compensated (Kahan-Babuska-Neumaier) float summation.

    Reproduces CPython 3.12+ ``sum()`` of floats bit-for-bit so the result is
    identical across Python versions (naive ``sum`` on Python <= 3.11 differs by
    last-ULP rounding). This keeps the jaccard means — the only float summation in
    the payload; all other sums are over integers — equal to the frozen contract on
    every interpreter. It does NOT change any value relative to that contract.
    """
    f = 0.0
    c = 0.0
    for v in values:
        x = float(v)
        t = f + x
        if abs(f) >= abs(x):
            c += (f - t) + x
        else:
            c += (x - t) + f
        f = t
    return f + c


# --------------------------------------------------------------------------
# Read-only DB access
# --------------------------------------------------------------------------
def connect_ro(db_path=DB_PATH):
    con = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    con.execute("PRAGMA query_only=ON")
    qo = con.execute("PRAGMA query_only").fetchone()[0]
    if int(qo) != 1:
        con.close()
        raise RuntimeError("query_only not enabled (got %r)" % (qo,))
    return con


def verify_anchors(con):
    """Re-verify the five Phase-0B data anchors. Returns observed dict; raises on mismatch."""
    observed = {}
    observed["canonical_draws"] = con.execute(
        "SELECT COUNT(*) FROM %s" % CANONICAL_VIEW).fetchone()[0]
    observed["big_replay_rows"] = con.execute(
        "SELECT COUNT(*) FROM %s WHERE lottery_type=?" % REPLAY_TABLE, (LOTTERY,)).fetchone()[0]
    observed["strategy_family_size"] = con.execute(
        "SELECT COUNT(DISTINCT strategy_id) FROM %s WHERE lottery_type=?" % REPLAY_TABLE,
        (LOTTERY,)).fetchone()[0]
    observed["eligible_targets"] = con.execute(
        "SELECT COUNT(DISTINCT target_draw) FROM %s r WHERE r.lottery_type=? "
        "AND r.target_draw IN (SELECT draw FROM %s)" % (REPLAY_TABLE, CANONICAL_VIEW),
        (LOTTERY,)).fetchone()[0]
    observed["causality_violations"] = con.execute(
        "SELECT COUNT(*) FROM %s WHERE lottery_type=? AND "
        "(history_cutoff_draw IS NULL OR CAST(history_cutoff_draw AS INTEGER) "
        ">= CAST(target_draw AS INTEGER))" % REPLAY_TABLE, (LOTTERY,)).fetchone()[0]
    for key in ("canonical_draws", "big_replay_rows", "strategy_family_size",
                "eligible_targets", "causality_violations"):
        if observed[key] != EXPECTED_ANCHORS[key]:
            raise RuntimeError("ANCHOR MISMATCH %s: expected %r observed %r"
                               % (key, EXPECTED_ANCHORS[key], observed[key]))
    return observed


# --------------------------------------------------------------------------
# Source load + outcome re-derivation
# --------------------------------------------------------------------------
def load_source(con):
    """Load canonical outcomes and BIG_LOTTO replay rows (read-only)."""
    canonical = {}
    for draw, numbers, special in con.execute(
            "SELECT draw, numbers, special FROM %s" % CANONICAL_VIEW):
        mains = [int(x) for x in json.loads(numbers)]
        canonical[str(draw)] = {"main": frozenset(mains), "special": int(special)}

    rows = []
    for td, sid, bi, pred, cutoff in con.execute(
            "SELECT target_draw, strategy_id, bet_index, predicted_numbers, "
            "history_cutoff_draw FROM %s WHERE lottery_type=?" % REPLAY_TABLE, (LOTTERY,)):
        rows.append((str(td), str(sid), int(bi), pred, cutoff))
    # Deterministic processing order.
    rows.sort(key=lambda r: (r[1], int(r[0]), r[2]))
    return canonical, rows


def parse_ticket(pred):
    """Return frozenset of 6 distinct ints in [1,49], or None if invalid."""
    try:
        arr = json.loads(pred)
    except (TypeError, ValueError):
        return None
    if not isinstance(arr, list) or len(arr) != MAIN_PICK:
        return None
    try:
        ints = [int(x) for x in arr]
    except (TypeError, ValueError):
        return None
    if any(x < NUM_LO or x > NUM_HI for x in ints):
        return None
    if len(set(ints)) != MAIN_PICK:
        return None
    return frozenset(ints)


def _causal_ok(cutoff, target):
    if cutoff is None:
        return False
    s = str(cutoff)
    if not s.lstrip("-").isdigit():
        return False
    return int(s) < int(target)


# --------------------------------------------------------------------------
# Index construction (the single shared structural index)
# --------------------------------------------------------------------------
class SourceIndex(object):
    """
    Holds the re-derived, validated measurement substrate.

      slot_tickets[sid][td]  -> list[frozenset]   (NUMBERS ONLY; used by redundancy + pairwise)
      slot_outcomes[sid][td] -> list[(main_hit, special_hit)]  (OUTCOMES; never used by pairwise)
    """
    def __init__(self, canonical, rows):
        self.canonical = canonical
        self.strategy_ids = sorted({r[1] for r in rows})
        # eligible target ids = distinct replay targets present in canonical view
        elig = {r[0] for r in rows if r[0] in canonical}
        self.eligible_targets_asc = sorted(elig, key=lambda x: int(x))  # chronological asc
        self.eligible_targets_desc = sorted(elig, key=lambda x: int(x), reverse=True)

        self.slot_tickets = {s: {} for s in self.strategy_ids}
        self.slot_outcomes = {s: {} for s in self.strategy_ids}
        self.invalid_slots = {s: 0 for s in self.strategy_ids}
        self.noncanonical_rows = 0
        self.eligible_valid_rows = 0

        for td, sid, _bi, pred, cutoff in rows:
            if td not in canonical:
                self.noncanonical_rows += 1
                continue
            fs = parse_ticket(pred)
            if fs is None or not _causal_ok(cutoff, td):
                self.invalid_slots[sid] += 1
                continue
            actual = canonical[td]
            mh = len(fs & actual["main"])
            sh = 1 if actual["special"] in fs else 0
            self.slot_tickets[sid].setdefault(td, []).append(fs)
            self.slot_outcomes[sid].setdefault(td, []).append((mh, sh))
            self.eligible_valid_rows += 1

    def windows(self):
        out = {}
        for name, n in WINDOW_DEFS:
            sel = self.eligible_targets_desc if n is None else self.eligible_targets_desc[:n]
            ids_asc = sorted(sel, key=lambda x: int(x))
            out[name] = {
                "ids_asc": ids_asc,
                "set": set(ids_asc),
            }
        return out


# --------------------------------------------------------------------------
# Metric families
# --------------------------------------------------------------------------
def ticket_level_cell(idx, sid, win_set):
    m = [0] * 7
    special_hits = 0
    m2_and_special = 0       # main_hit_count == 2 AND special_hit == 1 (prize tier)
    main_ge2_and_special = 0 # diagnostic: main_hit_count >= 2 AND special_hit == 1
    prize_any = 0
    denom = 0
    for td, outs in idx.slot_outcomes[sid].items():
        if td not in win_set:
            continue
        for mh, sh in outs:
            m[mh] += 1
            denom += 1
            if sh:
                special_hits += 1
                if mh == 2:
                    m2_and_special += 1
                if mh >= 2:
                    main_ge2_and_special += 1
            if mh >= 3 or (mh == 2 and sh == 1):
                prize_any += 1
    cum = {}
    for k in range(1, 7):
        cum["m%d_plus_count" % k] = sum(m[k:])
        cum["m%d_plus_rate" % k] = _rate(sum(m[k:]), denom)
    cell = {
        "level": "TICKET_SLOT",
        "denominator_kind": "VALID_SUBMITTED_TICKET_SLOTS",
        "submitted_valid_ticket_slots": denom,
    }
    for k in range(0, 7):
        cell["m%d_count" % k] = m[k]
        cell["m%d_rate" % k] = _rate(m[k], denom)
    cell.update(cum)
    cell["special_hit_count"] = special_hits
    cell["special_hit_rate"] = _rate(special_hits, denom)
    cell["m2_and_special_count"] = m2_and_special
    cell["m2_and_special_rate"] = _rate(m2_and_special, denom)
    cell["main_ge2_and_special_count"] = main_ge2_and_special
    cell["main_ge2_and_special_rate"] = _rate(main_ge2_and_special, denom)
    cell["local_prize_aware_v1_any_win_count"] = prize_any
    cell["local_prize_aware_v1_any_win_rate"] = _rate(prize_any, denom)
    return cell


def target_level_cell(idx, sid, win_ids_asc, win_set):
    covered = [td for td in win_ids_asc if td in idx.slot_outcomes[sid]]
    denom = len(covered)
    maxm = [0] * 7
    tgt_special = 0
    tgt_m2_special = 0
    tgt_prize = 0
    anyk = {k: 0 for k in range(1, 7)}
    for td in covered:
        outs = idx.slot_outcomes[sid][td]
        max_main = max(o[0] for o in outs)
        maxm[max_main] += 1
        for k in range(1, 7):
            if max_main >= k:
                anyk[k] += 1
        has_special = any(o[1] == 1 for o in outs)
        has_m2_special = any(o[0] == 2 and o[1] == 1 for o in outs)
        has_prize = any(o[0] >= 3 or (o[0] == 2 and o[1] == 1) for o in outs)
        if has_special:
            tgt_special += 1
        if has_m2_special:
            tgt_m2_special += 1
        if has_prize:
            tgt_prize += 1
    window_target_count = len(win_ids_asc)
    cell = {
        "level": "TARGET_ANY_TICKET",
        "denominator_kind": "COVERED_TARGETS_ONLY",
        "window_target_count": window_target_count,
        "covered_target_count": denom,
        "missing_target_count": window_target_count - denom,
        "coverage_status": "COMPLETE" if denom == window_target_count else "PARTIAL",
    }
    for k in range(0, 7):
        cell["max_m%d_count" % k] = maxm[k]
        cell["max_m%d_rate" % k] = _rate(maxm[k], denom)
    for k in range(1, 7):
        cell["any_ticket_m%d_plus_count" % k] = anyk[k]
        cell["any_ticket_m%d_plus_rate" % k] = _rate(anyk[k], denom)
    cell["target_special_hit_any_ticket_count"] = tgt_special
    cell["target_special_hit_any_ticket_rate"] = _rate(tgt_special, denom)
    cell["target_m2_and_special_any_ticket_count"] = tgt_m2_special
    cell["target_m2_and_special_any_ticket_rate"] = _rate(tgt_m2_special, denom)
    cell["target_local_prize_aware_v1_any_win_count"] = tgt_prize
    cell["target_local_prize_aware_v1_any_win_rate"] = _rate(tgt_prize, denom)
    return cell


def redundancy_cell(idx, sid, win_ids_asc, win_set):
    """Structural diagnostics only — NUMBERS ONLY, no outcome fields touched."""
    submitted = 0
    within_unique = 0
    targets_with_dup = 0
    global_set = set()
    covered = 0
    for td in win_ids_asc:
        tickets = idx.slot_tickets[sid].get(td)
        if not tickets:
            continue
        covered += 1
        submitted += len(tickets)
        uniq = set(tickets)
        within_unique += len(uniq)
        global_set |= uniq
        if len(tickets) > len(uniq):
            targets_with_dup += 1
    dup_slots = submitted - within_unique
    return {
        "level": "STRUCTURAL_DIAGNOSTIC",
        "note": "Structural redundancy only; NOT predictive evidence.",
        "window_target_count": len(win_ids_asc),
        "covered_target_count": covered,
        "submitted_ticket_slot_count": submitted,
        "within_target_unique_ticket_count": within_unique,
        "duplicate_ticket_slot_count": dup_slots,
        "duplicate_slot_ratio": _rate(dup_slots, submitted),
        "targets_with_one_or_more_duplicate_slots": targets_with_dup,
        "global_unique_exact_ticket_count": len(global_set),
    }


def pairwise_cell(idx, a, b, win_ids_asc, win_set):
    """Pairwise overlap — NUMBERS ONLY. No outcome fields are read here."""
    a_cov = {td for td in win_ids_asc if td in idx.slot_tickets[a]}
    b_cov = {td for td in win_ids_asc if td in idx.slot_tickets[b]}
    shared = sorted(a_cov & b_cov, key=lambda x: int(x))
    a_only = a_cov - b_cov
    b_only = b_cov - a_cov

    a_slots = 0
    b_slots = 0
    exact_overlap = 0
    union_tickets = 0
    jacc_vals = []
    for td in shared:
        at = idx.slot_tickets[a][td]
        bt = idx.slot_tickets[b][td]
        a_slots += len(at)
        b_slots += len(bt)
        aset = set(at)
        bset = set(bt)
        exact_overlap += len(aset & bset)
        union_tickets += len(aset | bset)
        a_nums = set().union(*at) if at else set()
        b_nums = set().union(*bt) if bt else set()
        union_nums = a_nums | b_nums
        if union_nums:
            jacc_vals.append(len(a_nums & b_nums) / len(union_nums))
    sc = len(shared)
    jacc_mean = (_neumaier_sum(jacc_vals) / len(jacc_vals)) if jacc_vals else None
    return {
        "strategy_a": a,
        "strategy_b": b,
        "level": "STRUCTURAL_DIAGNOSTIC_PAIRWISE",
        "uses_outcome_fields": False,
        "window_target_count": len(win_ids_asc),
        "a_covered_target_count": len(a_cov),
        "b_covered_target_count": len(b_cov),
        "shared_covered_target_count": sc,
        "a_only_covered_target_count": len(a_only),
        "b_only_covered_target_count": len(b_only),
        "neither_covered_target_count": len(win_ids_asc) - (sc + len(a_only) + len(b_only)),
        "a_submitted_slots_on_shared": a_slots,
        "b_submitted_slots_on_shared": b_slots,
        "exact_cross_strategy_duplicate_ticket_count": exact_overlap,
        "pairwise_unique_ticket_union_count": union_tickets,
        "mean_per_target_ticket_union_size": _rate(union_tickets, sc),
        "mean_per_target_exact_ticket_overlap_count": _rate(exact_overlap, sc),
        "main_number_set_jaccard_mean": jacc_mean,
        "main_number_set_jaccard_min": (min(jacc_vals) if jacc_vals else None),
        "main_number_set_jaccard_max": (max(jacc_vals) if jacc_vals else None),
        "main_number_set_jaccard_shared_target_basis": len(jacc_vals),
    }


# --------------------------------------------------------------------------
# Measurement payload assembly (nine sub-payloads; matches the frozen contract)
# --------------------------------------------------------------------------
def _window_meta(idx):
    wins = idx.windows()
    meta = {}
    for name, n in WINDOW_DEFS:
        ids = wins[name]["ids_asc"]
        meta[name] = {
            "window_name": name,
            "selection_rule": "ALL_ELIGIBLE" if n is None else ("NEWEST_%d_BY_DRAW_ID_DESC" % n),
            "is_reference_only": (n is None),
            "target_count": len(ids),
            "oldest_target": ids[0] if ids else None,
            "newest_target": ids[-1] if ids else None,
            "target_ids_chronological_asc": ids,
            "digest_sha256": digest_obj(ids),
        }
    return wins, meta


def _endpoint_support_status():
    return {
        "MAIN_HIT_DISTRIBUTION_M0_M6": "SUPPORTED",
        "CUMULATIVE_M1_PLUS_TO_M6_PLUS": "SUPPORTED",
        "SPECIAL_HIT": "SUPPORTED",
        "M2_AND_SPECIAL": "SUPPORTED",
        "LOCAL_PRIZE_AWARE_V1_ANY_WIN": "SUPPORTED",
        "EXACT_PRIZE_TIER": "PARTIALLY_SUPPORTED",
        "PAYOUT_EV_ROI": "UNSUPPORTED",
        "_notes": {
            "EXACT_PRIZE_TIER": ("Structural tier is derivable from (main_hit_count, special_hit), "
                                 "but the committed prize-tier scorer semantics and an exact "
                                 "monetary tier mapping are NOT re-derived here; treat as partial."),
            "PAYOUT_EV_ROI": ("No payout/odds/pool/ROI data is read or computed. A local scorer "
                              "endpoint must never be converted into an official prize, payout, or ROI."),
        },
    }


def _frozen_contract(observed_anchors, idx, win_meta):
    return {
        "schema_version": "big649_measurement_contract_v1",
        "task": "BIG649_HIT_DISTRIBUTION_REDUNDANCY_MEASUREMENT_CONTRACT",
        "lottery_type": LOTTERY,
        "measurement_only_notice": MEASUREMENT_ONLY_NOTICE,
        "source": {
            "db_path": DB_PATH,
            "db_sha256_expected": EXPECTED_ANCHORS["db_sha256"],
            "canonical_view": CANONICAL_VIEW,
            "replay_table": REPLAY_TABLE,
            "access_mode": "sqlite mode=ro + PRAGMA query_only=ON (read-only)",
        },
        "frozen_anchors_expected": EXPECTED_ANCHORS,
        "frozen_anchors_observed": observed_anchors,
        "number_space": {"pick": MAIN_PICK, "low": NUM_LO, "high": NUM_HI},
        "ticket_validity_rule": (
            "A ticket slot is VALID iff predicted_numbers parses to exactly 6 distinct "
            "integers in [1,49] AND history_cutoff_draw is strictly earlier (integer-less-than) "
            "than target_draw. Invalid slots are excluded from denominators and reported."),
        "outcome_rederivation": {
            "source_of_truth": "canonical draw numbers + actual special from %s" % CANONICAL_VIEW,
            "main_hit_count": "size of intersection(predicted 6 main, actual 6 main)",
            "special_hit": "1 if actual special number is in predicted 6 main numbers else 0",
            "local_prize_aware_v1_any_win": "main_hit_count >= 3 OR (main_hit_count == 2 AND special_hit == 1)",
            "stored_special_hit_trusted": False,
            "stored_hit_count_trusted": False,
        },
        "windows": {name: {
            "selection_rule": meta["selection_rule"],
            "is_reference_only": meta["is_reference_only"],
            "target_count": meta["target_count"],
            "digest_sha256": meta["digest_sha256"],
            "oldest_target": meta["oldest_target"],
            "newest_target": meta["newest_target"],
        } for name, meta in win_meta.items()},
        "window_order": WINDOW_ORDER,
        "reference_only_constraint": (
            "REFERENCE_ALL_ELIGIBLE is descriptive reference only and cannot support "
            "strategy promotion or selection."),
        "denominator_contract": {
            "ticket_slot_level": "denominator = valid submitted ticket slots whose target is in the window",
            "target_any_ticket_level": "denominator = covered targets only (targets in window with >=1 valid slot)",
            "never_mix": "ticket-slot-level and target-level denominators are never mixed",
        },
        "missing_coverage_rule": (
            "Missing target coverage stays missing: not imputed as zero-hit, not backfilled, "
            "not substituted; coverage denominator is published separately."),
        "redundancy_rule": "Structural diagnostics only; duplicate slots remain counted in ticket-slot metrics.",
        "pairwise_rule": "Pairwise overlap uses numbers only; no outcome fields; lexical unranked.",
        "endpoint_support_status": _endpoint_support_status(),
        "forbidden_in_this_contract": [
            "edge search", "best-strategy ranking", "best-combination/portfolio selection",
            "random baseline", "p-value", "candidate classification", "recommendation",
            "prediction-success claim", "payout", "ROI", "official prize claim",
        ],
    }


def _export_schema():
    return {
        "schema_version": "big649_measurement_contract_v1",
        "purpose": ("Field guide for a FUTURE read-only BIG649 strategy-analysis UI/API. "
                    "This schema defines fields only; it does not authorize implementation."),
        "measurement_only_notice": MEASUREMENT_ONLY_NOTICE,
        "level_distinction": {
            "TICKET_SLOT": "Per submitted ticket slot; denominator = valid submitted ticket slots.",
            "TARGET_ANY_TICKET": "Per target via best ticket; denominator = covered targets only.",
            "WARNING": "A UI must never mix ticket-slot-level and target-level denominators.",
        },
        "files": {
            "frozen_strategy_family.json": "11 strategies (lexical) + realized-budget structural diagnostics.",
            "canonical_target_windows.json": "Frozen 50/300/750/all windows: target ids (asc) + sha256 digests.",
            "per_strategy_ticket_level_distribution.json": "Ticket-slot M0..M6, M1+..M6+, special, prize-aware.",
            "per_strategy_target_level_distribution.json": "Target max-M0..M6, any-ticket M1+..M6+, coverage.",
            "per_strategy_prize_aware_distribution.json": "Special / m2_and_special / prize-aware at both levels + support status.",
            "per_strategy_redundancy_diagnostics.json": "Duplicate/unique ticket diagnostics (structural).",
            "pairwise_ticket_overlap_diagnostics.json": "C(11,2)=55 pairs x 4 windows; numbers-only overlap.",
        },
        "ticket_slot_level_fields": {
            "submitted_valid_ticket_slots": "int denominator",
            "m0_count..m6_count": "int counts; sum == submitted_valid_ticket_slots",
            "m0_rate..m6_rate": "float = count/denominator (null if denominator 0)",
            "m1_plus_count..m6_plus_count": "cumulative counts; mK_plus = sum(mK..m6)",
            "m1_plus_rate..m6_plus_rate": "cumulative rates",
            "special_hit_count/rate": "actual special in predicted 6 main",
            "m2_and_special_count/rate": "main==2 AND special (prize tier)",
            "main_ge2_and_special_count/rate": "main>=2 AND special (diagnostic)",
            "local_prize_aware_v1_any_win_count/rate": "main>=3 OR (main==2 AND special)",
        },
        "target_level_fields": {
            "window_target_count": "int targets in window",
            "covered_target_count": "int covered (denominator)",
            "missing_target_count": "int = window_target_count - covered_target_count (never imputed)",
            "coverage_status": "COMPLETE or PARTIAL",
            "max_m0_count..max_m6_count": "targets whose best ticket has exactly K main hits; sum==covered",
            "max_m0_rate..max_m6_rate": "float = count/covered",
            "any_ticket_m1_plus_count..any_ticket_m6_plus_count": "targets with >=1 ticket main>=K",
            "any_ticket_m1_plus_rate..any_ticket_m6_plus_rate": "rates over covered",
            "target_special_hit_any_ticket_count/rate": "targets with >=1 special-hit ticket",
            "target_m2_and_special_any_ticket_count/rate": "targets with >=1 (main==2 AND special) ticket",
            "target_local_prize_aware_v1_any_win_count/rate": "targets with >=1 prize-aware-win ticket",
        },
        "redundancy_fields": {
            "submitted_ticket_slot_count": "int valid slots in window",
            "within_target_unique_ticket_count": "sum over covered targets of distinct ticket-sets",
            "duplicate_ticket_slot_count": "submitted - within_target_unique (within-target redundancy)",
            "duplicate_slot_ratio": "duplicate/submitted (null if submitted 0)",
            "targets_with_one_or_more_duplicate_slots": "count of targets with within-target duplicates",
            "global_unique_exact_ticket_count": "distinct 6-number sets across the whole window (diversity)",
        },
        "pairwise_fields": {
            "shared_covered_target_count": "targets both cover (basis for overlap)",
            "a_only/b_only/neither_covered_target_count": "coverage decomposition over window",
            "a_submitted_slots_on_shared/b_submitted_slots_on_shared": "slot counts on shared targets",
            "exact_cross_strategy_duplicate_ticket_count": "sum over shared targets of |ticketsA & ticketsB|",
            "pairwise_unique_ticket_union_count": "sum over shared targets of |ticketsA | ticketsB|",
            "mean_per_target_ticket_union_size": "union/shared",
            "mean_per_target_exact_ticket_overlap_count": "exact_overlap/shared",
            "main_number_set_jaccard_mean/min/max": "Jaccard of per-target union of main numbers",
            "uses_outcome_fields": "always false (numbers only)",
        },
        "endpoint_support_status": _endpoint_support_status(),
    }


def build_payload(con):
    observed_anchors = verify_anchors(con)
    canonical, rows = load_source(con)
    idx = SourceIndex(canonical, rows)
    wins, win_meta = _window_meta(idx)

    # cross-check observed eligible target count vs index
    if len(idx.eligible_targets_asc) != EXPECTED_ANCHORS["eligible_targets"]:
        raise RuntimeError("eligible target index size %d != anchor %d"
                           % (len(idx.eligible_targets_asc), EXPECTED_ANCHORS["eligible_targets"]))

    strategies = idx.strategy_ids
    pair_list = [(strategies[i], strategies[j])
                 for i in range(len(strategies)) for j in range(i + 1, len(strategies))]

    # ---- frozen strategy family (lexical; realized-budget structural diagnostics only)
    family_rows = []
    for sid in strategies:
        covered = sum(1 for td in idx.eligible_targets_asc if td in idx.slot_tickets[sid])
        submitted = sum(len(v) for v in idx.slot_tickets[sid].values())
        max_bet = 0
        for v in idx.slot_tickets[sid].values():
            if len(v) > max_bet:
                max_bet = len(v)
        family_rows.append({
            "strategy_id": sid,
            "eligible_covered_target_count": covered,
            "eligible_submitted_ticket_slot_count": submitted,
            "eligible_invalid_slot_count": idx.invalid_slots[sid],
            "max_realized_tickets_per_target": max_bet,
            "note": "Realized budget is name-independent; structural only; not a ranking.",
        })
    frozen_strategy_family = {
        "schema_version": "big649_measurement_contract_v1",
        "lottery_type": LOTTERY,
        "measurement_only_notice": MEASUREMENT_ONLY_NOTICE,
        "strategy_order_lexical": strategies,
        "strategy_family_size": len(strategies),
        "strategy_family_digest_sha256": digest_obj(strategies),
        "strategies": family_rows,
    }

    # ---- canonical target windows
    canonical_target_windows = {
        "schema_version": "big649_measurement_contract_v1",
        "lottery_type": LOTTERY,
        "measurement_only_notice": MEASUREMENT_ONLY_NOTICE,
        "window_order": WINDOW_ORDER,
        "reference_only_windows": ["REFERENCE_ALL_ELIGIBLE"],
        "eligible_target_universe_count": len(idx.eligible_targets_asc),
        "windows": win_meta,
        "nesting_assertion": "RECENT_50 subset RECENT_300 subset RECENT_750 subset REFERENCE_ALL_ELIGIBLE",
    }

    # ---- distributions (lexical strategy -> frozen window order)
    ticket_dist = {}
    target_dist = {}
    prize_dist = {}
    redundancy = {}
    for sid in strategies:
        ticket_dist[sid] = {}
        target_dist[sid] = {}
        prize_dist[sid] = {}
        redundancy[sid] = {}
        for name in WINDOW_ORDER:
            ids_asc = wins[name]["ids_asc"]
            win_set = wins[name]["set"]
            tcell = ticket_level_cell(idx, sid, win_set)
            gcell = target_level_cell(idx, sid, ids_asc, win_set)
            ticket_dist[sid][name] = tcell
            target_dist[sid][name] = gcell
            redundancy[sid][name] = redundancy_cell(idx, sid, ids_asc, win_set)
            prize_dist[sid][name] = {
                "ticket_slot_level": {
                    "denominator_kind": "VALID_SUBMITTED_TICKET_SLOTS",
                    "submitted_valid_ticket_slots": tcell["submitted_valid_ticket_slots"],
                    "special_hit_count": tcell["special_hit_count"],
                    "special_hit_rate": tcell["special_hit_rate"],
                    "m2_and_special_count": tcell["m2_and_special_count"],
                    "m2_and_special_rate": tcell["m2_and_special_rate"],
                    "main_ge2_and_special_count": tcell["main_ge2_and_special_count"],
                    "main_ge2_and_special_rate": tcell["main_ge2_and_special_rate"],
                    "local_prize_aware_v1_any_win_count": tcell["local_prize_aware_v1_any_win_count"],
                    "local_prize_aware_v1_any_win_rate": tcell["local_prize_aware_v1_any_win_rate"],
                },
                "target_any_ticket_level": {
                    "denominator_kind": "COVERED_TARGETS_ONLY",
                    "covered_target_count": gcell["covered_target_count"],
                    "missing_target_count": gcell["missing_target_count"],
                    "coverage_status": gcell["coverage_status"],
                    "target_special_hit_any_ticket_count": gcell["target_special_hit_any_ticket_count"],
                    "target_special_hit_any_ticket_rate": gcell["target_special_hit_any_ticket_rate"],
                    "target_m2_and_special_any_ticket_count": gcell["target_m2_and_special_any_ticket_count"],
                    "target_m2_and_special_any_ticket_rate": gcell["target_m2_and_special_any_ticket_rate"],
                    "target_local_prize_aware_v1_any_win_count": gcell["target_local_prize_aware_v1_any_win_count"],
                    "target_local_prize_aware_v1_any_win_rate": gcell["target_local_prize_aware_v1_any_win_rate"],
                },
            }

    per_strategy_ticket_level_distribution = {
        "schema_version": "big649_measurement_contract_v1",
        "lottery_type": LOTTERY,
        "measurement_only_notice": MEASUREMENT_ONLY_NOTICE,
        "level": "TICKET_SLOT",
        "denominator_kind": "VALID_SUBMITTED_TICKET_SLOTS",
        "strategy_order_lexical": strategies,
        "window_order": WINDOW_ORDER,
        "by_strategy": ticket_dist,
    }
    per_strategy_target_level_distribution = {
        "schema_version": "big649_measurement_contract_v1",
        "lottery_type": LOTTERY,
        "measurement_only_notice": MEASUREMENT_ONLY_NOTICE,
        "level": "TARGET_ANY_TICKET",
        "denominator_kind": "COVERED_TARGETS_ONLY",
        "strategy_order_lexical": strategies,
        "window_order": WINDOW_ORDER,
        "by_strategy": target_dist,
    }
    per_strategy_prize_aware_distribution = {
        "schema_version": "big649_measurement_contract_v1",
        "lottery_type": LOTTERY,
        "measurement_only_notice": MEASUREMENT_ONLY_NOTICE,
        "strategy_order_lexical": strategies,
        "window_order": WINDOW_ORDER,
        "endpoint_definitions": {
            "special_hit": "actual special number is an element of the predicted 6 main numbers",
            "m2_and_special": "main_hit_count == 2 AND special_hit == 1 (BIG649 '2 mains + special' prize tier)",
            "main_ge2_and_special": "main_hit_count >= 2 AND special_hit == 1 (diagnostic superset)",
            "local_prize_aware_v1_any_win": "main_hit_count >= 3 OR (main_hit_count == 2 AND special_hit == 1)",
        },
        "endpoint_support_status": _endpoint_support_status(),
        "by_strategy": prize_dist,
    }
    per_strategy_redundancy_diagnostics = {
        "schema_version": "big649_measurement_contract_v1",
        "lottery_type": LOTTERY,
        "measurement_only_notice": MEASUREMENT_ONLY_NOTICE,
        "note": "All redundancy measures are STRUCTURAL diagnostics only, not predictive evidence.",
        "strategy_order_lexical": strategies,
        "window_order": WINDOW_ORDER,
        "by_strategy": redundancy,
    }

    # ---- pairwise overlap (lexical pairs, frozen window order, NO outcomes)
    pairwise = []
    for a, b in pair_list:
        row = {"pair_key": "%s|%s" % (a, b), "by_window": {}}
        for name in WINDOW_ORDER:
            row["by_window"][name] = pairwise_cell(idx, a, b, wins[name]["ids_asc"], wins[name]["set"])
        pairwise.append(row)
    pairwise_ticket_overlap_diagnostics = {
        "schema_version": "big649_measurement_contract_v1",
        "lottery_type": LOTTERY,
        "measurement_only_notice": MEASUREMENT_ONLY_NOTICE,
        "note": "Pairwise overlap uses NUMBERS ONLY; no outcome field is read. Lexical unranked.",
        "pair_count": len(pair_list),
        "window_order": WINDOW_ORDER,
        "pairs_lexical": ["%s|%s" % (a, b) for a, b in pair_list],
        "pairs": pairwise,
    }

    # ---- frozen measurement contract (machine-readable definitions)
    frozen_measurement_contract = _frozen_contract(observed_anchors, idx, win_meta)

    # ---- export schema (UI field guide)
    big649_measurement_export_schema = _export_schema()

    payload = {
        "frozen_strategy_family": frozen_strategy_family,
        "canonical_target_windows": canonical_target_windows,
        "per_strategy_ticket_level_distribution": per_strategy_ticket_level_distribution,
        "per_strategy_target_level_distribution": per_strategy_target_level_distribution,
        "per_strategy_prize_aware_distribution": per_strategy_prize_aware_distribution,
        "per_strategy_redundancy_diagnostics": per_strategy_redundancy_diagnostics,
        "pairwise_ticket_overlap_diagnostics": pairwise_ticket_overlap_diagnostics,
        "frozen_measurement_contract": frozen_measurement_contract,
        "big649_measurement_export_schema": big649_measurement_export_schema,
    }
    return payload


def canonical_digest(payload):
    """Deterministic digest over the nine measurement sub-payloads (no wall-clock present)."""
    ordered = {k: payload[k] for k in OUTPUT_FILES}
    return digest_obj(ordered)


# --------------------------------------------------------------------------
# DB anchor stat + single-artifact assembly + writer
# --------------------------------------------------------------------------
def _file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _db_stat(path):
    st = os.stat(path)
    wal = path + "-wal"
    wal_size = os.path.getsize(wal) if os.path.exists(wal) else 0
    return {
        "sha256": _file_sha256(path),
        "size_bytes": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "wal_size_bytes": wal_size,
    }


def _window_definitions_summary(payload):
    """Lean per-window summary for the API/UI (full target-id lists stay in the payload)."""
    out = {}
    for name, meta in payload["canonical_target_windows"]["windows"].items():
        out[name] = {
            "selection_rule": meta["selection_rule"],
            "is_reference_only": meta["is_reference_only"],
            "target_count": meta["target_count"],
            "oldest_target": meta["oldest_target"],
            "newest_target": meta["newest_target"],
            "digest_sha256": meta["digest_sha256"],
        }
    return out


def build_export(db_path=DB_PATH):
    """Open the canonical DB read-only, re-derive the measurement, and return
    (export_dict, canonical_payload_digest). Raises (STOP) on any anchor drift."""
    if not os.path.exists(db_path):
        raise RuntimeError("canonical DB not found: %s" % db_path)
    stat_before = _db_stat(db_path)
    if stat_before["sha256"] != EXPECTED_DB_SHA256:
        raise RuntimeError("DB sha256 mismatch: expected %s got %s"
                           % (EXPECTED_DB_SHA256, stat_before["sha256"]))
    if stat_before["wal_size_bytes"] != 0:
        raise RuntimeError("DB -wal must be 0 bytes, got %d" % stat_before["wal_size_bytes"])

    con = connect_ro(db_path)
    try:
        qc = con.execute("PRAGMA quick_check").fetchone()[0]
        if str(qc) != "ok":
            raise RuntimeError("quick_check != ok: %r" % (qc,))
        payload = build_payload(con)
    finally:
        con.close()

    stat_after = _db_stat(db_path)
    if stat_after != stat_before:
        raise RuntimeError("DB changed during read: %r != %r" % (stat_after, stat_before))

    digest = canonical_digest(payload)
    if digest != EXPECTED_CANONICAL_PAYLOAD_DIGEST:
        raise RuntimeError(
            "canonical_payload_digest mismatch (field-parity STOP): expected %s got %s"
            % (EXPECTED_CANONICAL_PAYLOAD_DIGEST, digest))

    notes = _endpoint_support_status()["_notes"]
    export = {
        "schema_version": SCHEMA_VERSION,
        "lottery_type": LOTTERY,
        "task": "BIG649_MEASUREMENT_EXPORT_API_UI_IMPLEMENTATION",
        "source_contract_task": "BIG649_HIT_DISTRIBUTION_REDUNDANCY_MEASUREMENT_CONTRACT",
        "measurement_only_notice": MEASUREMENT_ONLY_NOTICE,
        "local_historical_measurement_disclaimer": LOCAL_HISTORICAL_MEASUREMENT_DISCLAIMER,
        "endpoint_support_status": _endpoint_support_status(),
        "window_order": WINDOW_ORDER,
        "api_window_to_internal": API_WINDOW_TO_INTERNAL,
        "metric_scopes": [
            "ticket_slot", "target_level", "prize_aware", "redundancy", "pairwise_overlap",
        ],
        "window_definitions": _window_definitions_summary(payload),
        "coverage_denominators": {
            "ticket_slot_level": "VALID_SUBMITTED_TICKET_SLOTS (valid submitted ticket slots whose target is in the window)",
            "target_any_ticket_level": "COVERED_TARGETS_ONLY (targets in window with >=1 valid slot)",
            "never_mix": "ticket-slot-level and target-level denominators are never mixed",
            "missing_coverage_rule": (
                "Missing target coverage stays missing: never imputed as zero-hit, "
                "backfilled, or substituted; rates are null when the denominator is 0."),
        },
        "safety_limitations": {
            "EXACT_PRIZE_TIER": "PARTIALLY_SUPPORTED",
            "PAYOUT_EV_ROI": "UNSUPPORTED",
            "reference_only_constraint": (
                "REFERENCE_ALL_ELIGIBLE is descriptive reference only and cannot support "
                "strategy promotion or selection."),
            "notes": notes,
        },
        "source_anchor": {
            "db_path": DB_PATH,
            "db_sha256": EXPECTED_DB_SHA256,
            "size_bytes": stat_before["size_bytes"],
            "wal_size_bytes": stat_before["wal_size_bytes"],
            "quick_check": "ok",
            "access_mode": "sqlite mode=ro + PRAGMA query_only=ON (read-only)",
            "canonical_view": CANONICAL_VIEW,
            "replay_table": REPLAY_TABLE,
        },
        "payload": payload,
        "canonical_payload_digest": digest,
    }
    return export, digest


# Default committed artifact location (repo-root relative to this file).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUTPUT = os.path.join(
    _REPO_ROOT, "outputs", "research", "big649_measurement_export_20260621.json")


def write_export(export, outpath=DEFAULT_OUTPUT):
    """Write the export canonically (sorted keys, indent=2, utf-8) + trailing newline.
    Byte-identical across two unchanged runs."""
    outdir = os.path.dirname(outpath)
    if outdir and not os.path.isdir(outdir):
        os.makedirs(outdir, exist_ok=True)
    with open(outpath, "w", encoding="utf-8") as fh:
        json.dump(export, fh, sort_keys=True, ensure_ascii=False, indent=2)
        fh.write("\n")
    return outpath


def main(argv):
    outpath = argv[1] if len(argv) > 1 else DEFAULT_OUTPUT
    export, digest = build_export()
    write_export(export, outpath)
    print("CANONICAL_PAYLOAD_DIGEST=%s" % digest)
    print("PAYLOAD_SUBOBJECTS=%d" % len(export["payload"]))
    print("OUTPUT=%s" % outpath)
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
