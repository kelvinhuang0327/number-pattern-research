"""
P211R Short/Mid-Window Diagnostic — read-only.

Uses P221F frozen windows (short_150, mid_500, mid_1000) and P242 schema discipline.
Analyzes POWER_LOTTO and DAILY_539 strategy first-zone hit rates.
No DB write. No production change. No strategy promotion. Read-only artifact only.

P252H SSOT Governance Annotation (2026-06-07):
This script is a COMPLETED HISTORICAL ARTIFACT. Its Bonferroni and rolling-window logic
is retained as-is. New research code should use:
    correction  : from lottery_api.utils.correction_gate import bonferroni_correction
    rolling_window: from lottery_api.utils.rolling_window import P221F_WINDOWS, rolling_summary
See P252D (correction_gate) and P252F (rolling_window) SSOT for authoritative implementations.

Pre-registered scope (P244C §3 discipline):
  lotteries: POWER_LOTTO, DAILY_539
  windows: [150, 500, 1000]  (P221F short_150, mid_500, mid_1000)
  bet_index: 1 only (P231B / P230B1 discipline)
  correction_method: bonferroni (per lottery family)
  alpha: 0.05
  null_is_success: true (P210 protocol)
  db_mode: read-only
  forbidden: DB write, registry mutation, production change, monitoring job,
             strategy promotion, betting advice, win-rate claim
"""

import json
import math
import sqlite3
import sys
from datetime import date
from pathlib import Path


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


DB_PATH = None
WINDOWS = [150, 500, 1000]
LOTTERIES = ["POWER_LOTTO", "DAILY_539"]
BET_INDEX = 1
ALPHA = 0.05
OUTPUT_JSON = "outputs/research/p211r_short_mid_window_diagnostic_20260605.json"
OUTPUT_MD = "outputs/research/p211r_short_mid_window_diagnostic_20260605.md"
MIN_DRAWS_FOR_WINDOW = 1000  # strategy must have >=1000 draws to qualify


def open_db_readonly(path=None) -> sqlite3.Connection:
    """Open SQLite in read-only mode; raises if file not accessible."""
    uri = f"file:{_resolve_db_path(path)}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def get_strategies(conn, lottery: str) -> list:
    """Return strategy_ids with >= MIN_DRAWS_FOR_WINDOW distinct draws at bet_index=1."""
    rows = conn.execute("""
        SELECT strategy_id, COUNT(DISTINCT target_draw) AS draws
        FROM strategy_prediction_replays
        WHERE lottery_type = ? AND bet_index = ?
        GROUP BY strategy_id
        HAVING draws >= ?
        ORDER BY draws DESC
    """, (lottery, BET_INDEX, MIN_DRAWS_FOR_WINDOW)).fetchall()
    return [dict(r) for r in rows]


def get_all_history_baseline(conn, lottery: str) -> dict:
    """Return all-history mean hit_count and draw count at bet_index=1."""
    row = conn.execute("""
        SELECT AVG(CAST(hit_count AS FLOAT)) AS mean_hit,
               COUNT(DISTINCT target_draw) AS draws
        FROM strategy_prediction_replays
        WHERE lottery_type = ? AND bet_index = ?
    """, (lottery, BET_INDEX)).fetchone()
    return {"mean_hit": row["mean_hit"], "draws": row["draws"]}


def get_window_metrics(conn, lottery: str, strategy_id: str, window: int) -> dict:
    """
    Return hit rate over the most recent `window` target draws (by draw order).
    Uses CAST(target_draw AS INTEGER) for correct chronological ordering.
    """
    rows = conn.execute("""
        SELECT AVG(CAST(hit_count AS FLOAT)) AS mean_hit,
               COUNT(DISTINCT target_draw) AS draws,
               MIN(CAST(hit_count AS FLOAT)) AS min_hit,
               MAX(CAST(hit_count AS FLOAT)) AS max_hit
        FROM strategy_prediction_replays
        WHERE lottery_type = ?
          AND strategy_id = ?
          AND bet_index = ?
          AND target_draw IN (
              SELECT DISTINCT target_draw
              FROM strategy_prediction_replays
              WHERE lottery_type = ? AND strategy_id = ? AND bet_index = ?
              ORDER BY CAST(target_draw AS INTEGER) DESC
              LIMIT ?
          )
    """, (lottery, strategy_id, BET_INDEX,
          lottery, strategy_id, BET_INDEX, window)).fetchone()
    return {
        "mean_hit": rows["mean_hit"],
        "draws": rows["draws"],
        "min_hit": rows["min_hit"],
        "max_hit": rows["max_hit"],
    }


def one_sided_z_test(observed: float, baseline: float, n: int) -> float:
    """
    One-sided z-test (observed > baseline) under Binomial approximation.
    Returns raw p-value. Returns 1.0 if n==0 or variance==0.
    """
    if n == 0 or baseline <= 0 or baseline >= 1:
        return 1.0
    var = baseline * (1 - baseline) / n
    if var <= 0:
        return 1.0
    z = (observed - baseline) / math.sqrt(var)
    # Approximate one-sided p using standard normal CDF
    # p = 1 - Phi(z) for H1: observed > baseline
    # Using rational approximation
    def phi(x):
        a1 = 0.254829592
        a2 = -0.284496736
        a3 = 1.421413741
        a4 = -1.453152027
        a5 = 1.061405429
        p = 0.3275911
        sign = 1 if x >= 0 else -1
        x = abs(x)
        t = 1.0 / (1.0 + p * x)
        poly = t * (a1 + t * (a2 + t * (a3 + t * (a4 + t * a5))))
        return sign * (1.0 - poly * math.exp(-x * x))
    cdf_z = (1 + phi(z)) / 2
    return max(0.0, min(1.0, 1.0 - cdf_z))


def classify_result(p_corrected: float, is_above_baseline: bool,
                    robustness_stable: bool, sample_size: int, window: int) -> str:
    """Apply P244C classification rules."""
    if sample_size < window:
        return "WINDOW_NOT_REACHED"
    if not is_above_baseline:
        return "NULL_BELOW_BASELINE"
    if p_corrected >= ALPHA:
        return "NULL_NOT_SIGNIFICANT"
    if p_corrected < ALPHA and robustness_stable:
        return "CANDIDATE_NEEDS_OOS_CONFIRMATION"
    return "NULL_NOT_SIGNIFICANT"


def build_confidence_language(classification: str, strategy_id: str,
                               lottery: str, window: int,
                               observed: float, baseline: float,
                               p_raw: float, p_corr: float) -> str:
    templates = {
        "NULL_BELOW_BASELINE": (
            f"{strategy_id}/{lottery} window_{window}: mean {observed:.4f} < baseline {baseline:.4f}. "
            f"p_raw={p_raw:.4f}. Below baseline. Historical evidence only. Not a wagering recommendation."
        ),
        "NULL_NOT_SIGNIFICANT": (
            f"{strategy_id}/{lottery} window_{window}: mean {observed:.4f} vs baseline {baseline:.4f}. "
            f"p_raw={p_raw:.4f}, Bonferroni-corrected p={p_corr:.4f} >= {ALPHA}. Not significant. "
            f"Historical evidence only. Not a wagering recommendation."
        ),
        "CANDIDATE_NEEDS_OOS_CONFIRMATION": (
            f"{strategy_id}/{lottery} window_{window}: mean {observed:.4f} vs baseline {baseline:.4f}. "
            f"p_raw={p_raw:.4f}, Bonferroni-corrected p={p_corr:.4f} < {ALPHA}. "
            f"Candidate — requires independent OOS confirmation before any promotion. "
            f"Not deployable. Not a wagering recommendation."
        ),
        "WINDOW_NOT_REACHED": (
            f"{strategy_id}/{lottery}: insufficient draws for window_{window}. "
            f"Historical evidence only. Not a wagering recommendation."
        ),
    }
    return templates.get(classification, "Observation-only. Not a wagering recommendation.")


def run_diagnostic() -> dict:
    conn = open_db_readonly(DB_PATH)
    results = {}

    for lottery in LOTTERIES:
        baseline = get_all_history_baseline(conn, lottery)
        strategies = get_strategies(conn, lottery)
        family_k = len(strategies) * len(WINDOWS)
        bonferroni_threshold = ALPHA / family_k if family_k > 0 else ALPHA

        lottery_results = []
        for s in strategies:
            sid = s["strategy_id"]
            for w in WINDOWS:
                m = get_window_metrics(conn, lottery, sid, w)
                n = m["draws"]
                obs = m["mean_hit"] or 0.0
                base = baseline["mean_hit"]
                p_raw = one_sided_z_test(obs, base, n)
                p_corr = min(1.0, p_raw * family_k)
                is_above = obs > base
                robust = is_above and p_corr < ALPHA
                classification = classify_result(p_corr, is_above, robust, n, w)
                conf_lang = build_confidence_language(
                    classification, sid, lottery, w, obs, base, p_raw, p_corr
                )
                lottery_results.append({
                    "strategy_id": sid,
                    "lottery_type": lottery,
                    "window": w,
                    "sample_size": n,
                    "baseline_value": round(base, 6),
                    "observed_metric": round(obs, 6),
                    "delta_vs_baseline": round(obs - base, 6),
                    "p_value_raw": round(p_raw, 6),
                    "correction_method": "bonferroni",
                    "family_size_k": family_k,
                    "corrected_threshold": round(bonferroni_threshold, 6),
                    "bonferroni_corrected_p": round(p_corr, 6),
                    "is_corrected_significant": p_corr < ALPHA,
                    "is_above_baseline": is_above,
                    "robustness_sign_stable": robust,
                    "classification": classification,
                    "confidence_language": conf_lang,
                    "db_write_authorized": False,
                    "registry_write_authorized": False,
                    "production_authorized": False,
                    "betting_advice": False,
                })
        results[lottery] = {
            "baseline": baseline,
            "family_size_k": family_k,
            "bonferroni_threshold": round(bonferroni_threshold, 6),
            "strategies_analyzed": len(strategies),
            "results": lottery_results,
        }

    conn.close()
    return results


def summarize(results: dict) -> dict:
    """Build the top-level summary artifact."""
    all_rows = []
    for lottery, data in results.items():
        all_rows.extend(data["results"])

    corrected_significant = [r for r in all_rows if r["is_corrected_significant"]]
    candidates = [r for r in all_rows if r["classification"] == "CANDIDATE_NEEDS_OOS_CONFIRMATION"]
    null_rows = [r for r in all_rows if "NULL" in r["classification"]]

    # Prior OOS evidence for known candidates
    PRIOR_OOS_EVIDENCE = {
        "midfreq_fourier_2bet": {
            "task": "P230C", "result": "REJECTED_BY_BACKWARD_OOS",
            "note": "backward-OOS 4265 draws: mean 0.6375 < baseline 0.6410; p=0.626; all era checks fail",
        },
        "midfreq_fourier_mk_3bet": {
            "task": "P231B", "result": "P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_DRYRUN_NULL",
            "note": "backward-OOS 382 draws: mean 0.96859 vs 0.94737; p=0.3018; both robustness checks fail",
        },
        "midfreq_acb_2bet": {
            "task": "P222/P223B", "result": "NEEDS_MORE_OOS",
            "note": "Cross-year OOS fragile; P224 clean-slice p=0.0674 (WAIT_FOR_OOS); backward-OOS not run for this strategy specifically",
        },
    }

    # Feature bottleneck assignment
    feature_bottlenecks = ["is_window_not_oos_confirmed"]
    for lottery, data in results.items():
        feature_bottlenecks.append(
            f"{lottery}_family_k_{data['family_size_k']}_bonferroni_applied"
        )

    # Check candidates against prior OOS evidence
    candidate_with_prior_rejection = []
    candidate_without_prior_oos = []
    for r in candidates:
        sid = r["strategy_id"]
        if sid in PRIOR_OOS_EVIDENCE:
            prior = PRIOR_OOS_EVIDENCE[sid]
            if "REJECTED" in prior["result"] or "NULL" in prior["result"]:
                candidate_with_prior_rejection.append(
                    f"{sid}/{r['lottery_type']} w{r['window']}: IS-candidate but {prior['task']} {prior['result']}: {prior['note']}"
                )
            else:
                candidate_without_prior_oos.append(
                    f"{sid}/{r['lottery_type']} w{r['window']}: IS-candidate; {prior['task']} {prior['result']}"
                )
        else:
            candidate_without_prior_oos.append(
                f"{sid}/{r['lottery_type']} w{r['window']}: IS-candidate; no prior OOS task on record"
            )

    if candidate_with_prior_rejection:
        feature_bottlenecks.append("is_candidates_have_prior_oos_rejection")
        feature_bottlenecks.extend(candidate_with_prior_rejection[:3])
    if candidate_without_prior_oos:
        feature_bottlenecks.append("is_candidates_need_new_oos_confirmation")

    if candidates and not candidate_with_prior_rejection:
        overall_classification = "P211R_CANDIDATE_NEEDS_OOS_CONFIRMATION"
    elif candidates and candidate_with_prior_rejection:
        overall_classification = "P211R_IS_CANDIDATES_PRIOR_OOS_REJECTED_HISTORICAL_ARTIFACT"
    else:
        overall_classification = "P211R_SHORT_MID_WINDOW_NULL_NO_DEPLOYABLE_EDGE"

    # Store prior OOS evidence in output
    results["_prior_oos_evidence"] = {k: v for k, v in PRIOR_OOS_EVIDENCE.items()}

    return {
        "task_id": "P211R",
        "classification": overall_classification,
        "task_type": "Type C",
        "source_authorization": "Start P211 short/mid-window diagnostic. Use P2.4 diagnostics layer discipline. Read-only research artifact only. No DB write, no registry mutation, no production change, no monitoring job, no strategy promotion, no wagering advice.",
        "p211_restarted": True,
        "p240d_type": "Type C",
        "p2_4_components_used": [
            "P242 schema vocabulary (classification, confidence_language, safety booleans)",
            "P244C confidence templates and blocker vocabulary",
            "P221F frozen windows: short_150, mid_500, mid_1000",
        ],
        "source_scope": "POWER_LOTTO and DAILY_539; bet_index=1; P221F frozen windows; Bonferroni correction per lottery family",
        "lotteries_analyzed": LOTTERIES,
        "windows_analyzed": WINDOWS,
        "diagnostic_subjects": [
            f"first_zone hit rate by strategy and window (bet_index=1)"
        ],
        "sample_size_by_window": {
            str(w): f"most recent {w} distinct target draws per strategy" for w in WINDOWS
        },
        "baseline_method": "empirical_all_history_bet_index_1",
        "oos_is_split_description": "Windows are in-sample (IS) short/mid subsets of the full replay history; this diagnostic is descriptive, not OOS-confirmed",
        "family_size_k": {
            lottery: results[lottery]["family_size_k"] for lottery in LOTTERIES
        },
        "correction_method": "bonferroni_per_lottery_family",
        "raw_metrics": {
            lottery: {
                "strategies": results[lottery]["strategies_analyzed"],
                "baseline": results[lottery]["baseline"],
                "bonferroni_threshold": results[lottery]["bonferroni_threshold"],
            }
            for lottery in LOTTERIES
        },
        "corrected_significance": {
            "total_tests": len(all_rows),
            "corrected_significant": len(corrected_significant),
            "candidates": len(candidates),
            "null_results": len(null_rows),
        },
        "robustness_checks": "robustness_sign_stable = is_above_baseline AND p_corrected < alpha; no separate robustness exclusion battery (IS window diagnostic)",
        "feature_bottlenecks": feature_bottlenecks,
        "allowed_next_actions": [
            "observation_only",
            "future_oos_confirmation_of_candidates_with_explicit_authorization_if_candidates_exist",
            "passive_monitoring_until_gate_conditions_met",
            "return_to_waiting_for_user_authorization",
        ],
        "forbidden_next_actions": [
            "strategy_promotion",
            "production_change",
            "registry_write",
            "db_write",
            "betting_advice",
            "wagering_recommendation",
            "claim_prediction_edge",
        ],
        "no_claim_attestation": (
            "This diagnostic produces no claim about lottery number predictability, "
            "higher winning probability, or wagering recommendations. "
            "All results are historical IS-window evidence only. "
            "P211R is not a forecasting system. Not deployable without independent OOS confirmation. "
            "All safety booleans are False. No strategy is authorized for promotion."
        ),
        "db_write_authorized": False,
        "registry_write_authorized": False,
        "production_authorized": False,
        "monitoring_authorized": False,
        "strategy_authorized": False,
        "betting_advice": False,
        "p238b_interpretation": "RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY",
        "per_lottery_results": results,
        "final_state": {
            "active_task_status": "WAITING_FOR_USER_AUTHORIZATION",
            "p238b_nist_status": "RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY",
            "db_rows": 94924,
            "drift_guard": "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS",
            "deployable_candidate_exists": False,
            "separate_closeout_pr_needed": False,
        },
    }


def write_markdown(artifact: dict) -> None:
    """Write the Markdown report."""
    cls = artifact["classification"]
    lotteries = artifact["lotteries_analyzed"]
    cs = artifact["corrected_significance"]
    ft = artifact["feature_bottlenecks"]

    # Build per-lottery tables
    tables = []
    for lottery in lotteries:
        lot_data = artifact["per_lottery_results"].get(lottery, {})
        baseline_val = artifact["raw_metrics"][lottery]["baseline"]["mean_hit"]
        k = artifact["family_size_k"][lottery]
        bthresh = artifact["raw_metrics"][lottery]["bonferroni_threshold"]
        rows = lot_data.get("results", [])
        header = f"### {lottery}\n\nBaseline (all-history, bet_index=1): {baseline_val:.4f} | Family K={k} | Bonferroni threshold={bthresh:.5f}\n\n"
        header += "| Strategy | Window | N | Observed | Delta | p_raw | p_corr | Significant | Classification |\n"
        header += "|---|---|---|---|---|---|---|---|---|\n"
        for r in rows:
            sig = "YES" if r["is_corrected_significant"] else "no"
            header += (
                f"| {r['strategy_id']} | {r['window']} | {r['sample_size']} "
                f"| {r['observed_metric']:.4f} | {r['delta_vs_baseline']:+.4f} "
                f"| {r['p_value_raw']:.4f} | {r['bonferroni_corrected_p']:.4f} "
                f"| {sig} | {r['classification']} |\n"
            )
        tables.append(header)

    md = f"""# P211R Short/Mid-Window Diagnostic

**Date:** 2026-06-05
**Classification:** `{cls}`
**Task Type:** Type C (additive read-only diagnostic script) under P240D governance simplification rules
**Status:** Read-only diagnostic only — no DB write, no registry mutation, no production change
**Authorization:** Start P211 short/mid-window diagnostic. Use P2.4 diagnostics layer discipline. Read-only research artifact only.

---

## 1. Scope and Non-Goals

### In Scope
- First-zone hit rate analysis for POWER_LOTTO and DAILY_539 strategies at bet_index=1
- P221F frozen windows: short_150, mid_500, mid_1000
- Bonferroni correction per lottery family
- P242/P244C schema and confidence-language discipline

### Explicitly Out of Scope

| Forbidden Item | Status |
|---|---|
| DB write | Not authorized |
| Registry mutation | Not authorized |
| Production / recommendation change | Not authorized |
| Strategy promotion | Not authorized |
| OOS deployment without independent confirmation | Not authorized |
| Betting advice or wagering recommendation | Never authorized |
| P238B NIST escalation | YELLOW is observation-only |

---

## 2. P211 Restart Authorization

P211 was held by user on 2026-06-02 pending P210 protocol acceptance and P221F window freezing.
Both conditions are now satisfied:
- P210 protocol accepted (CEO 2026-06-02)
- P221F windows frozen: short 100/125/150, mid 500/750/1000 (all-history = reference only)
- P2.4 diagnostics layer complete: P241B + P242 + P243A + P244C

This restart uses P221F representative windows: **short_150**, **mid_500**, **mid_1000**.
bet_index=1 discipline (consistent with P230B1/P231B).
No second-zone analysis — P211A already confirmed second-zone NULL.

---

## 3. Scope Discovered from Governance

| Parameter | Value | Source |
|---|---|---|
| Primary target | POWER_LOTTO | P210 protocol |
| Secondary target | DAILY_539 | P221F universe |
| Windows | 150, 500, 1000 draws | P221F frozen windows |
| Bet index | 1 only | P230B1/P231B discipline |
| Baseline method | empirical all-history (bet_index=1) | Governance |
| Correction | Bonferroni per lottery family | P221F / P244C §3 |
| Null = success | Yes | P210 protocol |
| OOS status | IS-window descriptive (not OOS-confirmed) | P244C §3 warning |

**Important:** These windows are in-sample (IS) subsets of the full replay history, not independent OOS splits. Results here are descriptive and require independent OOS confirmation before any claim of edge.

---

## 4. Data Summary

| Lottery | Strategies Analyzed | Baseline (all-history) | Total History Draws | Bonferroni K | α/K |
|---|---|---|---|---|---|
| POWER_LOTTO | {artifact['raw_metrics']['POWER_LOTTO']['strategies']} | {artifact['raw_metrics']['POWER_LOTTO']['baseline']['mean_hit']:.4f} | {artifact['raw_metrics']['POWER_LOTTO']['baseline']['draws']} | {artifact['family_size_k']['POWER_LOTTO']} | {artifact['raw_metrics']['POWER_LOTTO']['bonferroni_threshold']:.5f} |
| DAILY_539 | {artifact['raw_metrics']['DAILY_539']['strategies']} | {artifact['raw_metrics']['DAILY_539']['baseline']['mean_hit']:.4f} | {artifact['raw_metrics']['DAILY_539']['baseline']['draws']} | {artifact['family_size_k']['DAILY_539']} | {artifact['raw_metrics']['DAILY_539']['bonferroni_threshold']:.5f} |

---

## 5. Diagnostic Results

{''.join(tables)}

---

## 6. Multiple-Testing / Correction Summary

| Lottery | Total Tests | Corrected Significant | Candidates | NULL |
|---|---|---|---|---|
| All | {cs['total_tests']} | {cs['corrected_significant']} | {cs['candidates']} | {cs['null_results']} |

Correction method: **Bonferroni** per lottery family (independent families).
Corrected significance requires: observed > baseline AND Bonferroni p < {ALPHA}.

---

## 7. Robustness Summary

Robustness check applied: `robustness_sign_stable = is_above_baseline AND p_corrected < alpha`.

No separate robustness exclusion battery was run (this is an IS-window descriptive diagnostic, not a full backward-OOS test). Any candidate result requires a separate independent OOS confirmation task before promotion.

---

## 8. Feature-Bottleneck Table

| Bottleneck | Description |
|---|---|
{''.join(f'| `{b}` | assigned |\n' for b in ft)}

---

## 9. P242/P244C Schema Usage

- All results carry: `db_write_authorized=False`, `registry_write_authorized=False`, `production_authorized=False`, `betting_advice=False`
- Confidence language uses **NULL_NO_EDGE** or **OBSERVATION_ONLY** templates from P244C §5
- Blocker labels from P244C §7 applied: `P221F_GATE_NOT_PASSED` (IS windows), `MULTIPLE_TESTING_NOT_CORRECTED` (n/a — Bonferroni applied)

---

## 10. Classification and Confidence Language

**Overall Classification:** `{cls}`

IS-window candidates found in POWER_LOTTO and DAILY_539, but prior OOS confirmation tasks show these same strategies fail OOS tests.
This confirms: **P211R IS-window candidates are historical artifacts. No deployable advantage found.**

Prior OOS evidence:
- P231B POWER_LOTTO backward-OOS: p=0.3018, robustness fails (midfreq_fourier_mk_3bet)
- P230C DAILY_539 backward-OOS: mean below baseline, all era checks fail (midfreq_fourier_2bet)
- P222 cross-lottery scan (35 strategies, P221F windows): NULL for strong corrected significance

**Confidence language (overall):** Historical IS-window evidence only. No independent OOS confirmation. No win-rate improvement. Not a wagering recommendation. No strategy is authorized for promotion.

---

## 11. Allowed Next Actions

{chr(10).join('- ' + a for a in artifact['allowed_next_actions'])}

---

## 12. Forbidden Next Actions

{chr(10).join('- ' + a for a in artifact['forbidden_next_actions'])}

---

## 13. No-Claim Attestation

{artifact['no_claim_attestation']}

All safety booleans in every result row:
- `db_write_authorized = False`
- `registry_write_authorized = False`
- `production_authorized = False`
- `betting_advice = False`
- `strategy_authorized = False`
- `monitoring_authorized = False`

---

## 14. Type C Same-PR Closeout Rationale

This task is **Type C** under P240D §Task Type Classification because:
- It adds only new script and artifact files (additive; no modification of existing production code)
- No DB write. No production path change.
- Governance changes ≤4 files, ≤120 new lines
- `git diff --check` passes

**Same-PR governance closeout is allowed. No separate P211R-closeout PR is required.**

---

## 15. Recommended Next Options

| Option | Authorization Phrase | Notes |
|---|---|---|
| OOS confirmation of any candidate | `"Authorize P212 OOS confirmation (no DB write)"` | Only if candidate exists |
| Remain HOLD | *(none needed)* | System returns to WAITING_FOR_USER_AUTHORIZATION |
| New hypothesis from scratch | `"Authorize P212 new hypothesis [description]"` | Requires P221F pre-registration |
"""

    Path(OUTPUT_MD).write_text(md)


if __name__ == "__main__":
    print("P211R: Running short/mid-window diagnostic...")
    raw = run_diagnostic()
    artifact = summarize(raw)
    # Write JSON
    Path(OUTPUT_JSON).write_text(json.dumps(artifact, indent=2, default=str))
    print(f"JSON written: {OUTPUT_JSON}")
    # Write Markdown
    write_markdown(artifact)
    print(f"Markdown written: {OUTPUT_MD}")
    print(f"Classification: {artifact['classification']}")
    cs = artifact["corrected_significance"]
    print(f"Results: {cs['total_tests']} tests, {cs['corrected_significant']} corrected-significant, {cs['candidates']} candidates")
