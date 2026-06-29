#!/usr/bin/env python3
"""
P269C: Calendar Regime Formal H1 Test (pre-registered, single-shot).

Executes the P269B-designed primary H1 ONLY:
  DAILY_539 Saturday vs Mon-Fri M3+ rate, two-tailed permutation test,
  T=10,000, seed=42, alpha=0.01, temporal OOS = last 1,765 eligible draws.

Hard ordering guarantee: the Hypothesis Registry entry is appended BEFORE
any M3+ outcome is read. Phase A touches draw ids/dates and replay coverage
(target_draw only); Phase B is the only place hit_count is queried.

Governance:
  - Read-only DB access (SQLite URI mode=ro).
  - Registry append-only, guarded (duplicate-identical -> skip, conflict -> abort).
  - C06 NOT run. No weekday/threshold scan. No strategy. No betting advice.
"""
import json
import math
import random
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def _p291u_repo_root():
    current = Path(__file__)
    if not current.is_absolute():
        raise FileNotFoundError(f"Source file path is not absolute: {current}")
    for parent in (current.parent, *current.parents):
        if (parent / "lottery_api").is_dir():
            return parent
    raise FileNotFoundError(f"Unable to locate repository root from source file: {current}")


def _p291u_default_db_path():
    db_path = _p291u_repo_root() / "lottery_api" / "data" / "lottery_v2.db"
    if not db_path.is_file():
        raise FileNotFoundError(f"Default lottery DB path is missing or non-regular: {db_path}")
    return db_path


def _p291u_resolve_db_path(db_path=None):
    if db_path is None:
        return _p291u_default_db_path()
    path = Path(db_path)
    if not path.is_absolute():
        raise ValueError(f"Explicit DB path must be absolute: {db_path}")
    if not path.is_file():
        raise FileNotFoundError(f"Explicit DB path is missing or non-regular: {path}")
    return path


def _p291u_connect_resolved(db_path, *, uri=False):
    if uri:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    return sqlite3.connect(str(db_path))


REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
REGISTRY_PATH = REPO_ROOT / "lottery_api" / "data" / "hypothesis_registry.jsonl"
OUT_JSON = REPO_ROOT / "outputs" / "research" / "p269c_calendar_regime_formal_h1_test_20260611.json"
OUT_MD = REPO_ROOT / "outputs" / "research" / "p269c_calendar_regime_formal_h1_test_20260611.md"
P269B_DESIGN = "outputs/research/p269b_calendar_regime_pre_registration_design_20260611.json"

HYPOTHESIS_ID = "HR-P269C-H1-DAILY539-SATURDAY-M3PLUS-001"
LOTTERY = "DAILY_539"
OOS_N = 1765
PERMUTATIONS = 10_000
SEED = 42
ALPHA = 0.01
# P269B strategy_selection_rule: highest in-OOS replay coverage, NOT performance.
# All 15 DAILY_539 strategies tie at 1,494 in-OOS draws; tie broken by the
# P269B design artifact's pre-named recommended primary candidate (declared in
# the merged P269B JSON before any P269C data look).
STRATEGY_ID = "acb_markov_midfreq_3bet"


def connect_ro():
    _p291u_db_path = _p291u_resolve_db_path()
    return _p291u_connect_resolved(_p291u_db_path, uri=True)


def phase_a_lock_endpoint(conn):
    """Eligibility, OOS window, regime labels, coverage. NO hit outcomes read."""
    cur = conn.cursor()
    cur.execute(
        "SELECT draw, date FROM draws WHERE lottery_type=? AND date IS NOT NULL "
        "AND numbers IS NOT NULL ORDER BY CAST(draw AS INTEGER) ASC",
        (LOTTERY,),
    )
    rows = cur.fetchall()
    first_draw = rows[0][0]
    eligible = []  # (draw, weekday) — weekday: Mon=0..Sun=6
    for draw, date in rows:
        wd = datetime.strptime(date, "%Y/%m/%d").weekday()
        if draw == first_draw:
            continue  # P269B exclusion: first draw in DB
        if wd == 6:
            continue  # P269B exclusion: Sunday draws
        eligible.append((draw, wd))
    oos = eligible[-OOS_N:]
    oos_draws = {d: wd for d, wd in oos}

    cur.execute(
        "SELECT DISTINCT target_draw FROM strategy_prediction_replays "
        "WHERE lottery_type=? AND strategy_id=?",
        (LOTTERY, STRATEGY_ID),
    )
    coverage = {r[0] for r in cur.fetchall()}
    evaluable = sorted(set(oos_draws) & coverage, key=int)
    return {
        "eligible_total": len(eligible),
        "oos_cutoff_draw": oos[0][0],
        "oos_last_draw": oos[-1][0],
        "oos_n": len(oos),
        "oos_saturday_n": sum(1 for _, wd in oos if wd == 5),
        "oos_weekday_n": sum(1 for _, wd in oos if wd != 5),
        "oos_draws": oos_draws,
        "coverage_total": len(coverage),
        "evaluable_draws": evaluable,
        "evaluable_n": len(evaluable),
        "evaluable_saturday_n": sum(1 for d in evaluable if oos_draws[d] == 5),
        "evaluable_weekday_n": sum(1 for d in evaluable if oos_draws[d] != 5),
    }


def build_registry_entry(lock, registered_at):
    return {
        "hypothesis_id": HYPOTHESIS_ID,
        "task_id": "P269C",
        "name": "p269c_calendar_regime_c05_daily539_saturday_m3plus",
        "lottery": LOTTERY,
        "status": "PRE_REGISTERED_BEFORE_TEST",
        "source_design_artifact": P269B_DESIGN,
        "candidate": "C05 draw weekday / schedule regime",
        "primary_game": LOTTERY,
        "primary_h1": "Saturday vs Mon-Fri M3+ rate difference",
        "endpoint": (
            f"temporal OOS last {OOS_N} DAILY_539 eligible draws "
            f"(eligible = valid date + numbers, non-Sunday, first-draw excluded); "
            f"locked cutoff draw {lock['oos_cutoff_draw']}..{lock['oos_last_draw']}; "
            f"evaluable subset = OOS ∩ replay coverage of declared strategy "
            f"(N={lock['evaluable_n']}, Sat={lock['evaluable_saturday_n']}, "
            f"Mon-Fri={lock['evaluable_weekday_n']}) — declared before any outcome look"
        ),
        "strategy_id": STRATEGY_ID,
        "strategy_selection_rule": (
            "P269B rule: highest in-OOS replay coverage (not performance). All 15 "
            "DAILY_539 strategies tie at 1494; tie broken by P269B design artifact's "
            "pre-named recommended primary candidate acb_markov_midfreq_3bet."
        ),
        "m3plus_definition": (
            "P265A SSOT: draw-level any-bet success, MAX(hit_count>=3) per distinct "
            "target_draw, special_hit excluded, denominator = distinct target_draw"
        ),
        "statistical_test": "two-tailed permutation test",
        "permutations": PERMUTATIONS,
        "seed": SEED,
        "alpha": ALPHA,
        "null_model": (
            "weekday/Saturday labels exchangeable under fixed observed M3+ outcome "
            "vector within the locked OOS endpoint"
        ),
        "statistic": (
            "absolute difference in M3+ rate; Saturday minus Mon-Fri also reported"
        ),
        "pass_fail_gate": {
            "H1_PRIMARY_PASS_POSITIVE": "p < 0.01 and Saturday M3+ rate > Mon-Fri M3+ rate",
            "H1_PRIMARY_SIGNIFICANT_NEGATIVE": "p < 0.01 and Saturday M3+ rate < Mon-Fri M3+ rate",
            "H1_PRIMARY_FAIL": "otherwise",
        },
        "fisher_exact_backup": (
            "only if Saturday M3+ event count < 5; clearly labeled backup; "
            "does not override primary gate"
        ),
        "c06_secondary": "NOT_RUN",
        "no_db_write": True,
        "no_strategy": True,
        "no_hit_rate_improvement_claim": True,
        "registered_at": registered_at,
        "validated_at": None,
        "result_summary": None,
    }


def guarded_append(entry):
    """Append-only with duplicate/conflict guard. Returns action taken."""
    existing = []
    if REGISTRY_PATH.exists():
        with open(REGISTRY_PATH, encoding="utf-8") as f:
            existing = [json.loads(line) for line in f if line.strip()]
    matches = [e for e in existing if e.get("hypothesis_id") == HYPOTHESIS_ID]
    if matches:
        prior = dict(matches[0])
        candidate = dict(entry)
        # registered_at timing differs between runs; compare locked content only
        for k in ("registered_at",):
            prior.pop(k, None)
            candidate.pop(k, None)
        if prior == candidate:
            return "EXISTS_IDENTICAL_SKIPPED", matches[0]["registered_at"]
        print("FATAL: hypothesis_id exists with CONFLICTING content. STOP.", file=sys.stderr)
        sys.exit(2)
    with open(REGISTRY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return "APPENDED", entry["registered_at"]


def phase_b_outcomes(conn, lock):
    """First and only place M3+ outcomes are read (mirrors P265A SSOT SQL)."""
    cur = conn.cursor()
    cur.execute(
        "SELECT replay_status, dry_run, COUNT(*) FROM strategy_prediction_replays "
        "WHERE lottery_type=? AND strategy_id=? GROUP BY replay_status, dry_run",
        (LOTTERY, STRATEGY_ID),
    )
    status_rows = cur.fetchall()
    assert all(s == "PREDICTED" and d == 0 for s, d, _ in status_rows), (
        f"unexpected replay_status/dry_run rows: {status_rows}"
    )
    cur.execute(
        """
        SELECT target_draw, MAX(CASE WHEN hit_count >= 3 THEN 1 ELSE 0 END)
        FROM strategy_prediction_replays
        WHERE lottery_type=? AND strategy_id=?
        GROUP BY target_draw
        """,
        (LOTTERY, STRATEGY_ID),
    )
    success = dict(cur.fetchall())
    sat, weekday = [], []
    for d in lock["evaluable_draws"]:
        (sat if lock["oos_draws"][d] == 5 else weekday).append(int(success[d]))
    return sat, weekday


def permutation_test(sat, weekday):
    n_sat, n_wd = len(sat), len(weekday)
    s_sat, s_wd = sum(sat), sum(weekday)
    s_total = s_sat + s_wd
    pool = sat + weekday
    # integer-exact statistic: stat_int = s_sat*n_wd - s_wd*n_sat  (∝ rate diff)
    obs_int = abs(s_sat * n_wd - s_wd * n_sat)
    rng = random.Random(SEED)
    idx = list(range(n_sat + n_wd))
    ge = 0
    for _ in range(PERMUTATIONS):
        chosen = rng.sample(idx, n_sat)
        ps = sum(pool[i] for i in chosen)
        if abs(ps * n_wd - (s_total - ps) * n_sat) >= obs_int:
            ge += 1
    p_value = ge / PERMUTATIONS  # plain fraction, as pre-registered in P269B
    return {
        "n_saturday": n_sat,
        "n_weekday": n_wd,
        "m3plus_events_saturday": s_sat,
        "m3plus_events_weekday": s_wd,
        "saturday_rate": s_sat / n_sat,
        "weekday_rate": s_wd / n_wd,
        "rate_diff_sat_minus_weekday": s_sat / n_sat - s_wd / n_wd,
        "abs_statistic": abs(s_sat / n_sat - s_wd / n_wd),
        "permutations": PERMUTATIONS,
        "seed": SEED,
        "perm_ge_count": ge,
        "p_value": p_value,
    }


def fisher_exact_two_tailed(s_sat, n_sat, s_wd, n_wd):
    """Exact two-tailed Fisher via hypergeometric, math.comb (no scipy)."""
    n = n_sat + n_wd
    k = s_sat + s_wd
    denom = math.comb(n, n_sat)

    def prob(x):
        return math.comb(k, x) * math.comb(n - k, n_sat - x) / denom

    p_obs = prob(s_sat)
    lo, hi = max(0, k - n_wd), min(k, n_sat)
    return sum(prob(x) for x in range(lo, hi + 1) if prob(x) <= p_obs * (1 + 1e-9))


def main():
    conn = connect_ro()

    # ---- Phase A: lock endpoint, append registry BEFORE any outcome look ----
    lock = phase_a_lock_endpoint(conn)
    registered_at = datetime.now().isoformat()
    entry = build_registry_entry(lock, registered_at)
    action, effective_registered_at = guarded_append(entry)
    print(f"registry: {action} ({HYPOTHESIS_ID}) at {effective_registered_at}")

    # ---- Phase B: outcomes + permutation test ----
    sat, weekday = phase_b_outcomes(conn, lock)
    conn.close()
    result = permutation_test(sat, weekday)

    fisher = None
    if result["m3plus_events_saturday"] < 5:
        fisher = {
            "label": "BACKUP_ONLY_does_not_override_primary_gate",
            "p_value": fisher_exact_two_tailed(
                result["m3plus_events_saturday"], result["n_saturday"],
                result["m3plus_events_weekday"], result["n_weekday"],
            ),
        }

    if result["p_value"] < ALPHA and result["saturday_rate"] > result["weekday_rate"]:
        h1 = "H1_PRIMARY_PASS_POSITIVE"
        final = "P269C_CALENDAR_REGIME_FORMAL_H1_COMPLETE_PRIMARY_PASS_POSITIVE"
        next_task = "P269D strong audit / confirmation design (NOT strategy)"
    elif result["p_value"] < ALPHA:
        h1 = "H1_PRIMARY_SIGNIFICANT_NEGATIVE"
        final = "P269C_CALENDAR_REGIME_FORMAL_H1_COMPLETE_SIGNIFICANT_NEGATIVE"
        next_task = "P269D closeout / diagnostics-only NULL"
    else:
        h1 = "H1_PRIMARY_FAIL"
        final = "P269C_CALENDAR_REGIME_FORMAL_H1_COMPLETE_PRIMARY_FAIL"
        next_task = "P269D closeout / diagnostics-only NULL"

    computed_at = datetime.now().isoformat()
    artifact = {
        "task_id": "P269C_CALENDAR_REGIME_REGISTRY_AND_FORMAL_H1_TEST",
        "generated_at": computed_at,
        "schema_version": "1.0",
        "registry_append": {
            "hypothesis_id": HYPOTHESIS_ID,
            "action": action,
            "registered_at": effective_registered_at,
            "registered_before_computation": effective_registered_at < computed_at,
            "registry_path": "lottery_api/data/hypothesis_registry.jsonl",
        },
        "inherited_boundaries": {
            "p269a_lite_no_go": {
                "status": "NO_GO",
                "note": "P269A-Lite top recommendation was NO_GO; C05/C06 are LOW-plausibility WATCHLIST; user explicitly accepted this pathway.",
            },
            "p269b_ready_for_registry": {
                "classification": "P269B_CALENDAR_REGIME_PRE_REGISTRATION_DESIGN_PR414_MERGED",
                "design_artifact": P269B_DESIGN,
            },
            "p268_draw_order": "ALREADY_NULL — not reopened (H2/H3 stay closed)",
        },
        "low_plausibility_warning": (
            "LOW hit-rate plausibility pathway. Expected result was null "
            "(L82 signal space exhaustion). Single-shot test: if null, C05/C06 "
            "are permanently CLOSED."
        ),
        "h1_method": {
            "candidate": "C05 draw weekday / schedule regime",
            "primary_game": LOTTERY,
            "hypothesis": "Saturday vs Mon-Fri M3+ rate difference",
            "metric": "M3+ (P265A SSOT: draw-level any-bet hit_count>=3, special_hit excluded)",
            "strategy_id": STRATEGY_ID,
            "test": "two-tailed permutation, regime labels exchangeable",
            "permutations": PERMUTATIONS,
            "seed": SEED,
            "alpha": ALPHA,
            "p_value_formula": "plain fraction of |perm_stat| >= |observed_stat| (P269B pre-registered)",
        },
        "endpoint": {
            "definition": f"temporal OOS last {OOS_N} eligible DAILY_539 draws",
            "eligible_total": lock["eligible_total"],
            "oos_cutoff_draw": lock["oos_cutoff_draw"],
            "oos_last_draw": lock["oos_last_draw"],
            "oos_n": lock["oos_n"],
            "oos_saturday_n": lock["oos_saturday_n"],
            "oos_weekday_n": lock["oos_weekday_n"],
            "replay_coverage_total": lock["coverage_total"],
            "evaluable_n": lock["evaluable_n"],
            "evaluable_saturday_n": lock["evaluable_saturday_n"],
            "evaluable_weekday_n": lock["evaluable_weekday_n"],
            "coverage_note": (
                "Replay store covers the most-recent 1,500 distinct draws; 6 of "
                "those are Sundays (excluded by pre-registered rule), leaving "
                "1,494 evaluable OOS draws. Subset is purely temporal/structural, "
                "declared in the registry entry before any outcome look."
            ),
        },
        "result": result,
        "fisher_exact_backup": fisher if fisher else {
            "label": "NOT_TRIGGERED (Saturday M3+ events >= 5)",
        },
        "h1_classification": h1,
        "c06_secondary": "NOT_RUN",
        "scans_performed": "NONE — single pre-registered boundary, no weekday/threshold/lottery scan",
        "explicit_non_claims": {
            "no_db_write": True,
            "no_strategy": True,
            "no_picks": True,
            "no_numbers_generated": True,
            "no_betting_recommendation": True,
            "no_hit_rate_improvement_claim": True,
            "statement": (
                "This is a pre-registered statistical test result only. It does not "
                "improve win rate, does not predict lottery numbers, does not authorize "
                "betting advice, and does not constitute a strategy recommendation."
            ),
        },
        "recommended_next_task": next_task,
        "final_classification": final,
    }
    OUT_JSON.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    r = result
    md = f"""# P269C: Calendar Regime Formal H1 Test

**Date:** 2026-06-11 Asia/Taipei
**Classification:** `{final}`
**Task Type:** Type D (Hypothesis Registry append + pre-registered statistical test)
**H1 verdict:** `{h1}`

**No-Claim Statement:** This artifact does not improve win rate, does not predict
lottery numbers, does not authorize betting advice, and does not constitute a
strategy recommendation.

---

## 0. Inherited Boundaries

- **P268 draw-order:** ALREADY_NULL — H2/H3 stay closed, not reopened.
- **P269A-Lite:** top recommendation NO_GO; C05/C06 = LOW-plausibility WATCHLIST only.
- **P269B:** READY_FOR_REGISTRY design (PR #414 merged). This task executes that design verbatim.
- **Low plausibility warning:** expected result was null (L82). Single-shot test —
  a null permanently closes C05/C06.

## 1. Pre-Registration (before any outcome look)

- Registry entry: `{HYPOTHESIS_ID}` ({action})
- Status: `PRE_REGISTERED_BEFORE_TEST`, registered_at `{effective_registered_at}`
- Artifact computed_at `{computed_at}` (registry append strictly first)
- Strategy: `{STRATEGY_ID}` — P269B coverage rule; 15-way tie at 1,494 in-OOS
  draws broken by the P269B pre-named recommended primary candidate.

## 2. Method

- C05 only: DAILY_539 Saturday vs Mon-Fri, M3+ (P265A SSOT, special_hit excluded)
- Two-tailed permutation test, T={PERMUTATIONS:,}, seed={SEED}, alpha={ALPHA}
- Endpoint: temporal OOS last {OOS_N:,} eligible draws
  ({lock['oos_cutoff_draw']}..{lock['oos_last_draw']});
  evaluable = OOS ∩ replay coverage = {lock['evaluable_n']:,} draws
  (Sat {lock['evaluable_saturday_n']}, Mon-Fri {lock['evaluable_weekday_n']})
- C06 secondary: **NOT_RUN**. No weekday/threshold/lottery scans.

## 3. Result

| Quantity | Value |
|---|---|
| Saturday draws (evaluable) | {r['n_saturday']} |
| Mon-Fri draws (evaluable) | {r['n_weekday']} |
| Saturday M3+ events | {r['m3plus_events_saturday']} |
| Mon-Fri M3+ events | {r['m3plus_events_weekday']} |
| Saturday M3+ rate | {r['saturday_rate']:.4%} |
| Mon-Fri M3+ rate | {r['weekday_rate']:.4%} |
| Rate diff (Sat − Mon-Fri) | {r['rate_diff_sat_minus_weekday']:+.4%} |
| Permutations | {r['permutations']:,} (seed={r['seed']}) |
| Permuted \\|stat\\| ≥ observed | {r['perm_ge_count']:,} |
| **p-value (two-tailed)** | **{r['p_value']:.4f}** |
| Alpha | {ALPHA} |
| Fisher backup | {('p=%.4f (backup only)' % fisher['p_value']) if fisher else 'not triggered (events >= 5)'} |

## 4. Classification

**`{h1}`** → final classification **`{final}`**

Gate (pre-registered): PASS_POSITIVE iff p < {ALPHA} AND Saturday rate > Mon-Fri rate;
SIGNIFICANT_NEGATIVE iff p < {ALPHA} with Saturday < Mon-Fri; FAIL otherwise.

## 5. Recommended Next Task

{next_task}

## 6. Governance

- DB write: NO (read-only URI mode)
- Hypothesis Registry: append-only, one entry, before computation
- C06: NOT_RUN · scans: NONE · strategy: NONE · picks: NONE
- No hit-rate improvement claim. Not betting advice.
"""
    OUT_MD.write_text(md, encoding="utf-8")

    print(json.dumps({k: artifact[k] for k in ("h1_classification", "final_classification")}, indent=2))
    print(f"Sat {r['m3plus_events_saturday']}/{r['n_saturday']} = {r['saturday_rate']:.4%} | "
          f"Mon-Fri {r['m3plus_events_weekday']}/{r['n_weekday']} = {r['weekday_rate']:.4%} | "
          f"p={r['p_value']:.4f}")


if __name__ == "__main__":
    main()
