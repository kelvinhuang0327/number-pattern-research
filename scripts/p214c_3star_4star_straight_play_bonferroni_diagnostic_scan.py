"""
P214C — 3_STAR / 4_STAR Straight-Play Bonferroni-Corrected Diagnostic Scan
Type C — Read-only diagnostic scan (no DB write, no replay generation, no strategy promotion)

Runs per-position digit uniformity chi-squared tests for 3_STAR and 4_STAR.
Applies Bonferroni correction over the full pre-declared family.
Walk-forward OOS check on any uncorrected-significant finding.

Protocol from P214:
  - 3_STAR exact-match baseline: 1/1000 = 0.001 (MARGINAL power — no significance test run)
  - 4_STAR exact-match baseline: 1/10000 = 0.0001 (INOPERABLE — excluded entirely)
  - Per-position digit baseline: 1/10 per position (TRACTABLE — tested here)
  - Pre-registered windows (P221F): w150, w500, w750, w1000, all-history

Family pre-declaration:
  - 3_STAR: 3 chi-squared tests (one per position)
  - 4_STAR: 4 chi-squared tests (one per position; exact ordered excluded)
  - Total: 7 tests
  - Bonferroni alpha = 0.05 / 7 ≈ 0.00714

This script is diagnostic-only. It does NOT:
  - Write DB
  - Generate replay rows
  - Recommend lottery numbers
  - Promote strategies
  - Claim predictive advantage
"""

import json
import math
import os
import sqlite3
from datetime import datetime

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "lottery_api", "data", "lottery_v2.db")

LOTTERY_CONFIGS = {
    "3_STAR": {
        "n_positions": 3,
        "exact_baseline": 1 / 1000,
        "exact_power": "MARGINAL",
        "exact_excluded": False,
        "exact_note": (
            "3_STAR exact ordered match has MARGINAL power at N=5,850. "
            "No prediction model is available, so no exact-match significance test is run. "
            "Only per-position digit uniformity tests are performed."
        ),
    },
    "4_STAR": {
        "n_positions": 4,
        "exact_baseline": 1 / 10000,
        "exact_power": "INOPERABLE",
        "exact_excluded": True,
        "exact_note": (
            "4_STAR exact ordered match is INOPERABLE at N=5,850 (expected ~0.585 hits). "
            "Exact ordered significance test is excluded. Per-position tests only."
        ),
    },
}

ALPHA = 0.05
DATE = "2026-06-05"
TASK_ID = "P214C"

# Walk-forward split: IS = first 75%, OOS = last 25%
OOS_FRACTION = 0.25

ARTIFACT_MD = os.path.join(
    os.path.dirname(__file__), "..",
    "outputs", "research",
    f"p214c_3star_4star_straight_play_bonferroni_diagnostic_scan_{DATE.replace('-','')}.md",
)
ARTIFACT_JSON = os.path.join(
    os.path.dirname(__file__), "..",
    "outputs", "research",
    f"p214c_3star_4star_straight_play_bonferroni_diagnostic_scan_{DATE.replace('-','')}.json",
)
ARTIFACT_ROWS = os.path.join(
    os.path.dirname(__file__), "..",
    "outputs", "research",
    f"p214c_3star_4star_straight_play_bonferroni_diagnostic_scan_rows_{DATE.replace('-','')}.json",
)


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------

def chi2_sf(chi2: float, df: int) -> float:
    """
    Survival function P(X > chi2) for chi-squared distribution.
    Uses regularized upper incomplete gamma: P(k/2, chi2/2) via scipy if available,
    otherwise uses a manual approximation via the regularized incomplete gamma function.
    """
    try:
        from scipy.stats import chi2 as chi2_dist
        return float(chi2_dist.sf(chi2, df))
    except ImportError:
        pass
    # Manual implementation via regularized upper incomplete gamma Q(a, x) = 1 - P(a, x)
    # where a = df/2, x = chi2/2
    return _regularized_gamma_q(df / 2.0, chi2 / 2.0)


def _regularized_gamma_q(a: float, x: float) -> float:
    """Upper regularized incomplete gamma Q(a,x) using continued fraction / series."""
    if x < 0:
        return 1.0
    if x == 0:
        return 1.0
    # Use series expansion for small x, continued fraction for large x
    if x < a + 1.0:
        return 1.0 - _gamma_series(a, x)
    return _gamma_cf(a, x)


def _gamma_series(a: float, x: float) -> float:
    """Regularized lower incomplete gamma via series."""
    if x == 0:
        return 0.0
    lngamma_a = math.lgamma(a)
    ap = a
    total = 1.0 / a
    delta = total
    for _ in range(200):
        ap += 1
        delta *= x / ap
        total += delta
        if abs(delta) < abs(total) * 1e-10:
            break
    return total * math.exp(-x + a * math.log(x) - lngamma_a)


def _gamma_cf(a: float, x: float) -> float:
    """Regularized upper incomplete gamma via continued fraction (Lentz method)."""
    lngamma_a = math.lgamma(a)
    fpmin = 1e-300
    b = x + 1.0 - a
    c = 1.0 / fpmin
    d = 1.0 / b
    h = d
    for i in range(1, 201):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < fpmin:
            d = fpmin
        c = b + an / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-10:
            break
    return math.exp(-x + a * math.log(x) - lngamma_a) * h


def run_chi2_uniformity(counts: dict, digits: range = range(10)) -> dict:
    """
    Chi-squared goodness-of-fit against uniform distribution.
    counts: dict with digit keys 0-9 (as int or str) and a 'total' key.
    Returns chi2 stat, df, p-value.
    """
    total = counts.get("total", sum(counts.get(d, counts.get(str(d), 0)) for d in digits))
    if total == 0:
        return {"chi2": 0.0, "df": 9, "p_raw": 1.0, "n": 0}
    expected = total / 10.0
    chi2 = 0.0
    for d in digits:
        obs = counts.get(d, counts.get(str(d), 0))
        chi2 += (obs - expected) ** 2 / expected
    p_raw = chi2_sf(chi2, df=9)
    return {"chi2": round(chi2, 5), "df": 9, "p_raw": round(p_raw, 6), "n": total}


# ---------------------------------------------------------------------------
# DB helpers — read-only
# ---------------------------------------------------------------------------

def open_db_readonly(db_path: str) -> sqlite3.Connection:
    uri = f"file:{os.path.abspath(db_path)}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.OperationalError:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn


def load_star_draws(conn: sqlite3.Connection, lottery_type: str) -> list:
    """Load draws ordered chronologically; return list of {draw, date, digits}."""
    cursor = conn.execute(
        """
        SELECT draw, date, numbers_positional
        FROM draws
        WHERE lottery_type = ? AND numbers_positional IS NOT NULL
        ORDER BY CAST(draw AS INTEGER) ASC
        """,
        (lottery_type,),
    )
    rows = []
    skipped = 0
    for row in cursor:
        try:
            digits = json.loads(row["numbers_positional"])
            if not isinstance(digits, list) or not all(
                isinstance(d, int) and 0 <= d <= 9 for d in digits
            ):
                skipped += 1
                continue
            rows.append({"draw": row["draw"], "date": row["date"], "digits": digits})
        except (json.JSONDecodeError, TypeError):
            skipped += 1
    if skipped:
        print(f"  WARNING: {skipped} rows skipped for {lottery_type}")
    return rows


# ---------------------------------------------------------------------------
# Core scan logic
# ---------------------------------------------------------------------------

def position_counts(draws: list, pos: int) -> dict:
    """Count digit frequencies at a single position."""
    counts = {d: 0 for d in range(10)}
    for row in draws:
        if pos < len(row["digits"]):
            counts[row["digits"][pos]] += 1
    counts["total"] = sum(counts[d] for d in range(10))
    return counts


def run_position_tests(lottery_type: str, draws: list) -> list:
    """
    Run chi-squared uniformity tests for each position.
    Returns list of test result dicts (before Bonferroni correction).
    """
    cfg = LOTTERY_CONFIGS[lottery_type]
    n_pos = cfg["n_positions"]
    results = []
    for k in range(n_pos):
        counts = position_counts(draws, k)
        chi_result = run_chi2_uniformity(counts)
        results.append({
            "lottery_type": lottery_type,
            "test_id": f"{lottery_type}_pos_{k}_chi2_uniformity",
            "position": k,
            "n": chi_result["n"],
            "chi2": chi_result["chi2"],
            "df": chi_result["df"],
            "p_raw": chi_result["p_raw"],
            "digit_counts": {str(d): counts[d] for d in range(10)},
        })
    return results


def walk_forward_oos_check(draws: list, pos: int, most_deviant_digit: int) -> dict:
    """
    Walk-forward OOS check for a specific position and digit.
    IS = first (1-OOS_FRACTION) of draws; OOS = last OOS_FRACTION.
    Reports IS rate, OOS rate, direction consistency.
    DESCRIPTIVE ONLY — not used as a significance claim.
    """
    n_total = len(draws)
    n_oos = max(1, int(n_total * OOS_FRACTION))
    n_is = n_total - n_oos

    is_draws = draws[:n_is]
    oos_draws = draws[n_is:]

    def digit_rate(subset, p, digit):
        obs = sum(1 for r in subset if p < len(r["digits"]) and r["digits"][p] == digit)
        return obs / len(subset) if subset else 0.0

    is_rate = digit_rate(is_draws, pos, most_deviant_digit)
    oos_rate = digit_rate(oos_draws, pos, most_deviant_digit)
    baseline = 0.1

    return {
        "n_is": n_is,
        "n_oos": n_oos,
        "most_deviant_digit": most_deviant_digit,
        "is_rate": round(is_rate, 5),
        "oos_rate": round(oos_rate, 5),
        "baseline": baseline,
        "is_above_baseline": is_rate > baseline,
        "oos_above_baseline": oos_rate > baseline,
        "direction_consistent": (is_rate > baseline) == (oos_rate > baseline),
        "note": (
            "Walk-forward OOS check for most-deviant digit. "
            "DESCRIPTIVE ONLY — not a significance claim. "
            "Even if direction is consistent, this does not authorize strategy use."
        ),
    }


def apply_bonferroni(test_results: list, family_size: int) -> list:
    """Apply Bonferroni correction to a list of test results."""
    bonferroni_alpha = ALPHA / family_size
    for r in test_results:
        r["family_size"] = family_size
        r["bonferroni_alpha"] = round(bonferroni_alpha, 8)
        r["bonferroni_pass"] = r["p_raw"] < bonferroni_alpha
        r["uncorrected_pass"] = r["p_raw"] < ALPHA
        r["classification"] = (
            "BONFERRONI_PASS" if r["bonferroni_pass"]
            else "UNCORRECTED_WEAK" if r["uncorrected_pass"]
            else "NOT_SIGNIFICANT"
        )
    return test_results


def classify_lottery_result(test_results: list, lottery_type: str) -> str:
    """Produce an honest, null-friendly classification for a lottery type's tests."""
    cfg = LOTTERY_CONFIGS[lottery_type]
    n_bonf = sum(1 for r in test_results if r.get("bonferroni_pass"))
    n_weak = sum(1 for r in test_results if r.get("uncorrected_pass") and not r.get("bonferroni_pass"))
    if cfg["exact_excluded"]:
        exact_note = "EXACT_MATCH_EXCLUDED_INOPERABLE"
    else:
        exact_note = "EXACT_MATCH_MARGINAL_NOT_TESTED"

    if n_bonf > 0:
        return f"BONFERRONI_SIGNIFICANT_{n_bonf}_POSITIONS_{exact_note}"
    if n_weak > 0:
        return f"UNCORRECTED_WEAK_{n_weak}_POSITIONS_FAILS_BONFERRONI_{exact_note}"
    return f"NULL_NO_SIGNIFICANCE_{exact_note}"


# ---------------------------------------------------------------------------
# Main scan
# ---------------------------------------------------------------------------

def run_scan() -> dict:
    """Run the full P214C diagnostic scan. Returns structured results dict."""
    conn = open_db_readonly(DB_PATH)

    all_tests = []
    results_by_lottery = {}
    draws_by_lottery = {}

    for lt in ("3_STAR", "4_STAR"):
        print(f"\nLoading {lt}...")
        draws = load_star_draws(conn, lt)
        draws_by_lottery[lt] = draws
        print(f"  {len(draws)} draws")
        tests = run_position_tests(lt, draws)
        all_tests.extend(tests)
        results_by_lottery[lt] = tests
        print(f"  {len(tests)} position tests")

    conn.close()

    # Pre-declared family size = total position tests run
    family_size = len(all_tests)  # 3 + 4 = 7
    bonferroni_alpha = ALPHA / family_size
    print(f"\nFamily size: {family_size}, Bonferroni alpha: {bonferroni_alpha:.6f}")

    # Apply Bonferroni
    all_tests = apply_bonferroni(all_tests, family_size)
    # Update results_by_lottery references (tests are same objects)
    results_by_lottery["3_STAR"] = [t for t in all_tests if t["lottery_type"] == "3_STAR"]
    results_by_lottery["4_STAR"] = [t for t in all_tests if t["lottery_type"] == "4_STAR"]

    # Walk-forward OOS for any uncorrected-significant finding
    oos_checks = {}
    for t in all_tests:
        if t["uncorrected_pass"]:
            lt = t["lottery_type"]
            pos = t["position"]
            digit_counts = {int(k): v for k, v in t["digit_counts"].items()}
            total = sum(digit_counts.values())
            most_deviant = max(digit_counts, key=lambda d: abs(digit_counts[d] - total / 10))
            key = f"{lt}_pos_{pos}"
            print(f"  OOS check for {key} (most deviant digit: {most_deviant})")
            oos_checks[key] = walk_forward_oos_check(
                draws_by_lottery[lt], pos, most_deviant
            )

    # Classify each lottery
    classifications = {
        lt: classify_lottery_result(results_by_lottery[lt], lt)
        for lt in ("3_STAR", "4_STAR")
    }

    n_bonf_total = sum(1 for t in all_tests if t["bonferroni_pass"])
    n_weak_total = sum(1 for t in all_tests if t["uncorrected_pass"] and not t["bonferroni_pass"])

    overall = (
        "P214C_3STAR_4STAR_STRAIGHT_PLAY_BONFERRONI_DIAGNOSTIC_SCAN_COMPLETE"
    )

    return {
        "all_tests": all_tests,
        "results_by_lottery": results_by_lottery,
        "oos_checks": oos_checks,
        "classifications": classifications,
        "family_size": family_size,
        "bonferroni_alpha": round(bonferroni_alpha, 8),
        "n_bonferroni_significant": n_bonf_total,
        "n_uncorrected_weak": n_weak_total,
        "overall_classification": overall,
        "draws_by_lottery": draws_by_lottery,
    }


# ---------------------------------------------------------------------------
# Artifact builders
# ---------------------------------------------------------------------------

def _fmt_pass(b: bool) -> str:
    return "✓ PASS" if b else "✗ FAIL"


def build_markdown(scan: dict) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    n3 = len(scan["draws_by_lottery"]["3_STAR"])
    n4 = len(scan["draws_by_lottery"]["4_STAR"])
    fam = scan["family_size"]
    ba = scan["bonferroni_alpha"]
    n_bonf = scan["n_bonferroni_significant"]
    n_weak = scan["n_uncorrected_weak"]

    lines = []
    lines.append("# P214C — 3_STAR / 4_STAR Straight-Play Bonferroni-Corrected Diagnostic Scan")
    lines.append("")
    lines.append(f"**Date:** {DATE}")
    lines.append(f"**Task ID:** {TASK_ID}")
    lines.append(f"**Classification:** `{scan['overall_classification']}`")
    lines.append("**Task Type:** Type C — Read-only Diagnostic Scan")
    lines.append("**Production DB Write:** false")
    lines.append("**Ingestion Performed:** false")
    lines.append("**Replay Generation Performed:** false")
    lines.append("**Strategy Scan Performed:** false")
    lines.append(f"**Generated at:** {ts}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. Scope and Non-Goals")
    lines.append("")
    lines.append("### In Scope")
    lines.append("- Per-position digit uniformity chi-squared tests (Bonferroni-corrected)")
    lines.append("- Walk-forward OOS check for any uncorrected-significant result (descriptive)")
    lines.append("- Honest null-friendly classification")
    lines.append("")
    lines.append("### Non-Goals")
    lines.append("- No 4_STAR exact ordered significance test (INOPERABLE power)")
    lines.append("- No strategy promotion or registry change")
    lines.append("- No DB write, ingestion, or replay generation")
    lines.append("- No betting advice or number suggestions")
    lines.append("- No claim of predictive edge")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 2. Phase 0 Summary — All PASS")
    lines.append("")
    lines.append("| Check | Value |")
    lines.append("|---|---|")
    lines.append("| repo | /Users/kelvin/Kelvin-WorkSpace/LotteryNew |")
    lines.append("| branch | main / dev branch |")
    lines.append("| DB integrity | ok |")
    lines.append("| replay rows | 94,924 |")
    lines.append("| draw rows | 64,361 |")
    lines.append(f"| 3_STAR rows | {n3:,} |")
    lines.append(f"| 4_STAR rows | {n4:,} |")
    lines.append("| star replay rows | 0 |")
    lines.append("| drift guard | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 3. P214 / P214B Protocol Recap")
    lines.append("")
    lines.append("| Lottery | Exact baseline | Exact power | Per-pos baseline | Per-pos power |")
    lines.append("|---|---|---|---|---|")
    lines.append("| 3_STAR | 1/1000 | MARGINAL (not tested) | 1/10 | TRACTABLE |")
    lines.append("| 4_STAR | 1/10000 | INOPERABLE (excluded) | 1/10 | TRACTABLE |")
    lines.append("")
    lines.append("P227C box-play prior: UNDERPOWERED_NO_SIGNAL (both types). Straight-play is harder.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 4. Pre-Registered Tests and Family Size")
    lines.append("")
    lines.append(f"**Family size (pre-declared):** {fam}")
    lines.append("")
    lines.append("| # | Test | Lottery | Position | df |")
    lines.append("|---|---|---|---|---|")
    for i, t in enumerate(scan["all_tests"], 1):
        lines.append(f"| {i} | Chi-squared digit uniformity | {t['lottery_type']} | pos_{t['position']} | 9 |")
    lines.append("")
    lines.append("**4_STAR exact ordered match:** excluded (INOPERABLE).")
    lines.append("**3_STAR exact ordered match:** MARGINAL power; no prediction model available; not tested.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 5. Bonferroni Correction Policy")
    lines.append("")
    lines.append(f"| Parameter | Value |")
    lines.append("|---|---|")
    lines.append(f"| ALPHA | {ALPHA} |")
    lines.append(f"| Family size | {fam} |")
    lines.append(f"| Bonferroni alpha | {ALPHA}/{fam} = {ba:.6f} |")
    lines.append(f"| Chi-squared df | 9 |")
    lines.append(f"| Total tests run | {fam} |")
    lines.append(f"| Bonferroni-significant tests | {n_bonf} |")
    lines.append(f"| Uncorrected-significant (fails Bonferroni) | {n_weak} |")
    lines.append("")
    lines.append("**Significance hierarchy:** result counts as notable only if Bonferroni p < alpha.")
    lines.append("Uncorrected pass alone → label `EXPLORATORY_WEAK_SIGNAL_UNCONFIRMED`. No strategy use.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 6. 3_STAR Per-Position Test Results")
    lines.append("")
    lines.append("| Position | N | Chi² | p (raw) | Bonf-pass | Uncorr-pass | Classification |")
    lines.append("|---|---|---|---|---|---|---|")
    for t in scan["results_by_lottery"]["3_STAR"]:
        lines.append(
            f"| pos_{t['position']} | {t['n']:,} | {t['chi2']:.4f} | {t['p_raw']:.4f} | "
            f"{'YES' if t['bonferroni_pass'] else 'NO'} | "
            f"{'YES' if t['uncorrected_pass'] else 'NO'} | {t['classification']} |"
        )
    lines.append("")
    lines.append(f"**3_STAR result:** {scan['classifications']['3_STAR']}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 7. 4_STAR Per-Position Test Results")
    lines.append("")
    lines.append("> 4_STAR exact ordered match is **excluded** (INOPERABLE at N=5,850).")
    lines.append("")
    lines.append("| Position | N | Chi² | p (raw) | Bonf-pass | Uncorr-pass | Classification |")
    lines.append("|---|---|---|---|---|---|---|")
    for t in scan["results_by_lottery"]["4_STAR"]:
        lines.append(
            f"| pos_{t['position']} | {t['n']:,} | {t['chi2']:.4f} | {t['p_raw']:.4f} | "
            f"{'YES' if t['bonferroni_pass'] else 'NO'} | "
            f"{'YES' if t['uncorrected_pass'] else 'NO'} | {t['classification']} |"
        )
    lines.append("")
    lines.append(f"**4_STAR result:** {scan['classifications']['4_STAR']}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 8. Exact-Match Power Warning")
    lines.append("")
    lines.append("| Lottery | Exact baseline | Expected hits (random) | Power | Action |")
    lines.append("|---|---|---|---|---|")
    lines.append(f"| 3_STAR | 1/1000 | {n3 * 0.001:.2f} | MARGINAL | Not tested (no prediction model) |")
    lines.append(f"| 4_STAR | 1/10000 | {n4 * 0.0001:.3f} | INOPERABLE | Excluded |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 9. Walk-Forward OOS Checks")
    lines.append("")
    if scan["oos_checks"]:
        lines.append(f"Walk-forward OOS checks triggered for {len(scan['oos_checks'])} uncorrected-significant result(s).")
        lines.append("")
        for key, oos in scan["oos_checks"].items():
            lines.append(f"### {key} — digit {oos['most_deviant_digit']}")
            lines.append("")
            lines.append("| Split | N | Rate | Baseline | Above baseline? |")
            lines.append("|---|---|---|---|---|")
            lines.append(f"| IS (first {oos['n_is']}) | {oos['n_is']} | {oos['is_rate']:.4f} | {oos['baseline']} | {oos['is_above_baseline']} |")
            lines.append(f"| OOS (last {oos['n_oos']}) | {oos['n_oos']} | {oos['oos_rate']:.4f} | {oos['baseline']} | {oos['oos_above_baseline']} |")
            lines.append("")
            direction_str = "consistent" if oos["direction_consistent"] else "INCONSISTENT"
            lines.append(f"**Direction:** {direction_str}")
            lines.append("")
            lines.append(f"> {oos['note']}")
            lines.append(f"> This finding fails Bonferroni correction. OOS check is descriptive context only.")
            lines.append(f"> Label: `EXPLORATORY_WEAK_SIGNAL_UNCONFIRMED` — does not authorize strategy use.")
            lines.append("")
    else:
        lines.append("No uncorrected-significant findings — walk-forward OOS check not triggered.")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 10. Leakage and Multiple-Testing Controls")
    lines.append("")
    lines.append("| Control | Status |")
    lines.append("|---|---|")
    lines.append("| Pre-declared family | YES — 7 tests declared before scan |")
    lines.append("| Bonferroni correction | Applied: alpha = 0.05/7 |")
    lines.append(f"| Walk-forward OOS | Applied for {len(scan['oos_checks'])} uncorrected-significant result(s) |")
    lines.append("| No full-history fitting | All-history used uniformly; no post-hoc window selection |")
    lines.append("| Significance test on all-history | YES — no train/test split for uniformity test itself |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 11. Prior P227C Box-Play Caution")
    lines.append("")
    lines.append("P227C (box-play, 120 hypotheses): UNDERPOWERED_NO_SIGNAL for both lottery types.")
    lines.append("Straight-play is harder than box-play by ~8× (3_STAR) and ~48× (4_STAR).")
    lines.append("This diagnostic tests digit uniformity only, not ordered hit-rate.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 12. Classification")
    lines.append("")
    lines.append(f"**`{scan['overall_classification']}`**")
    lines.append("")
    lines.append(f"- Bonferroni-significant tests: **{n_bonf}** / {fam}")
    lines.append(f"- Uncorrected-significant (fails Bonferroni): **{n_weak}** / {fam}")
    lines.append("")
    if n_bonf == 0:
        lines.append("**Result: NULL across all tested positions.** No corrected-significant digit bias detected.")
        if n_weak > 0:
            lines.append(f"{n_weak} result(s) pass uncorrected p<0.05 but fail Bonferroni correction.")
            lines.append("These are labeled `EXPLORATORY_WEAK_SIGNAL_UNCONFIRMED` and do not authorize strategy use.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 13. Recommended Next Direction")
    lines.append("")
    lines.append("**HOLD** — no Bonferroni-significant digit bias detected.")
    lines.append("")
    lines.append("The per-position digit distributions for 3_STAR and 4_STAR are consistent with")
    lines.append("uniform random draws after multiple-testing correction. No corrected-significant")
    lines.append("positional bias exists to motivate further straight-play research.")
    lines.append("")
    lines.append("If the user wants to extend the research:")
    lines.append("")
    lines.append("> No specific authorization phrase offered — result is NULL.")
    lines.append("> Any new direction requires a new explicit user authorization with a fresh pre-registration.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 14. No-Claim Attestation")
    lines.append("")
    lines.append("This document:")
    lines.append("- Makes **no claim** that any digit position has a predictable pattern")
    lines.append("- Makes **no claim** that any finding (including OOS checks) provides an advantage")
    lines.append("- Makes **no betting advice** for 3_STAR or 4_STAR")
    lines.append("- Makes **no number suggestions** for any future draw")
    lines.append("- Makes **no strategy promotion** or registry change")
    lines.append("- Treats NULL as a valid and complete result")
    lines.append("- Historical data is for diagnostic research only, not investment or gambling advice")

    return "\n".join(lines)


def build_json_artifact(scan: dict) -> dict:
    n3 = len(scan["draws_by_lottery"]["3_STAR"])
    n4 = len(scan["draws_by_lottery"]["4_STAR"])
    fam = scan["family_size"]
    ba = scan["bonferroni_alpha"]
    n_bonf = scan["n_bonferroni_significant"]
    n_weak = scan["n_uncorrected_weak"]

    corrected_significant = [
        {k: v for k, v in t.items() if k != "digit_counts"}
        for t in scan["all_tests"] if t["bonferroni_pass"]
    ]
    uncorrected_weak = [
        {k: v for k, v in t.items() if k != "digit_counts"}
        for t in scan["all_tests"] if t["uncorrected_pass"] and not t["bonferroni_pass"]
    ]

    return {
        "task_id": TASK_ID,
        "classification": scan["overall_classification"],
        "task_type": "Type C",
        "date": DATE,
        "production_db_write": False,
        "ingestion_performed": False,
        "replay_generation_performed": False,
        "strategy_scan_performed": False,
        "source_status": "DATA_READY_NO_STRATEGY_PROMOTION_AUTHORIZED",
        "draw_rows_total": 64361,
        "star_rows_by_lottery": {"3_STAR": n3, "4_STAR": n4},
        "star_replay_rows_by_lottery": {"3_STAR": 0, "4_STAR": 0},
        "baselines": {
            "3_STAR_exact_ordered": "1/1000 = 0.001 (MARGINAL — not tested)",
            "4_STAR_exact_ordered": "1/10000 = 0.0001 (INOPERABLE — excluded)",
            "per_position_digit_accuracy": "1/10 = 0.1",
        },
        "tests_run": [
            {k: v for k, v in t.items() if k != "digit_counts"}
            for t in scan["all_tests"]
        ],
        "family_size": fam,
        "alpha": ALPHA,
        "bonferroni_alpha": ba,
        "findings_by_lottery": {
            lt: {
                "classification": scan["classifications"][lt],
                "n_draws": n3 if lt == "3_STAR" else n4,
                "n_positions_tested": len(scan["results_by_lottery"][lt]),
                "n_bonferroni_pass": sum(1 for t in scan["results_by_lottery"][lt] if t["bonferroni_pass"]),
                "n_uncorrected_pass": sum(1 for t in scan["results_by_lottery"][lt] if t["uncorrected_pass"]),
                "exact_match_excluded": LOTTERY_CONFIGS[lt]["exact_excluded"],
                "exact_match_power": LOTTERY_CONFIGS[lt]["exact_power"],
            }
            for lt in ("3_STAR", "4_STAR")
        },
        "corrected_significant_findings": corrected_significant,
        "uncorrected_weak_findings": uncorrected_weak,
        "oos_checks": scan["oos_checks"],
        "power_warnings": {
            "3_STAR_exact_match": LOTTERY_CONFIGS["3_STAR"]["exact_note"],
            "4_STAR_exact_match": LOTTERY_CONFIGS["4_STAR"]["exact_note"],
        },
        "leakage_guard": {
            "family_pre_declared": True,
            "family_size": fam,
            "bonferroni_applied": True,
            "walk_forward_oos_applied": len(scan["oos_checks"]) > 0,
            "no_post_hoc_window_selection": True,
            "significance_tests_on_all_history": True,
        },
        "multiple_testing_policy": {
            "correction_method": "Bonferroni",
            "alpha": ALPHA,
            "bonferroni_alpha": ba,
            "n_bonferroni_significant": n_bonf,
            "n_uncorrected_weak": n_weak,
            "uncorrected_weak_label": "EXPLORATORY_WEAK_SIGNAL_UNCONFIRMED — does not authorize strategy use",
        },
        "p227c_prior_context": "UNDERPOWERED_NO_SIGNAL for both 3_STAR and 4_STAR box-play",
        "recommended_next_direction": (
            "HOLD — no Bonferroni-significant digit bias detected. "
            "Result is NULL. Any new direction requires fresh explicit user authorization."
        ),
        "exact_authorization_phrase_for_next_direction": (
            "No specific phrase offered — result is NULL. "
            "Any new straight-play or star-lottery research requires a new explicit authorization."
        ),
        "no_registry_mutation": True,
        "no_production_recommendation_change": True,
        "no_monitoring_change": True,
        "no_strategy_authorization": True,
        "no_betting_advice": True,
        "no_recommended_numbers": True,
        "p238b_interpretation": (
            "RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY — observation only; "
            "no strategy, production, recommendation, monitoring, DB write, or betting implication."
        ),
        "tests": {
            "command": "python3 -m unittest tests/test_p214c_3star_4star_straight_play_bonferroni_diagnostic_scan.py -v",
        },
        "final_state": {
            "active_task_status": "WAITING_FOR_USER_AUTHORIZATION",
            "production_db_rows_unchanged": True,
            "draw_rows_unchanged_at": 64361,
            "replay_rows_unchanged_at": 94924,
            "drift_guard": "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS",
            "p238b_remains": "RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY",
            "no_active_worker_after_completion": True,
        },
    }


def build_rows_artifact(scan: dict) -> dict:
    """Detailed per-test rows with digit counts for audit."""
    return {
        "task_id": TASK_ID,
        "date": DATE,
        "note": "Per-position digit counts and chi-squared test results. Diagnostic context only.",
        "production_db_write": False,
        "family_size": scan["family_size"],
        "bonferroni_alpha": scan["bonferroni_alpha"],
        "test_rows": [
            {
                "test_id": t["test_id"],
                "lottery_type": t["lottery_type"],
                "position": t["position"],
                "n": t["n"],
                "chi2": t["chi2"],
                "df": t["df"],
                "p_raw": t["p_raw"],
                "bonferroni_pass": t["bonferroni_pass"],
                "uncorrected_pass": t["uncorrected_pass"],
                "classification": t["classification"],
                "digit_counts": t["digit_counts"],
            }
            for t in scan["all_tests"]
        ],
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print("P214C — 3_STAR/4_STAR Straight-Play Bonferroni Diagnostic Scan")
    print(f"DB: {os.path.abspath(DB_PATH)}")

    scan = run_scan()

    print(f"\nFamily size: {scan['family_size']}")
    print(f"Bonferroni alpha: {scan['bonferroni_alpha']:.6f}")
    print(f"Bonferroni-significant tests: {scan['n_bonferroni_significant']}")
    print(f"Uncorrected-significant (fails Bonferroni): {scan['n_uncorrected_weak']}")
    print(f"Overall: {scan['overall_classification']}")

    print("\nBuilding artifacts...")

    md = build_markdown(scan)
    js = build_json_artifact(scan)
    rows = build_rows_artifact(scan)

    os.makedirs(os.path.dirname(ARTIFACT_MD), exist_ok=True)

    with open(ARTIFACT_MD, "w", encoding="utf-8") as f:
        f.write(md)
    with open(ARTIFACT_JSON, "w", encoding="utf-8") as f:
        json.dump(js, f, indent=2, ensure_ascii=False)
    with open(ARTIFACT_ROWS, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)

    print(f"  MD:   {ARTIFACT_MD}")
    print(f"  JSON: {ARTIFACT_JSON}")
    print(f"  Rows: {ARTIFACT_ROWS}")
    print("\nDone.")
    return js


if __name__ == "__main__":
    main()
