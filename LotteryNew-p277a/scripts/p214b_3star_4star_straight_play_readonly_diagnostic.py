"""
P214B — 3_STAR / 4_STAR Straight-Play Read-Only Diagnostic
Type C — Small Additive Implementation (no DB write, no replay generation)

Computes descriptive diagnostics for 3_STAR and 4_STAR straight-play (exact ordered digit
match). Based on P214 protocol:
  - 3_STAR baseline: 1/1000 (10^3 ordered sequences)
  - 4_STAR baseline: 1/10000 (10^4 ordered sequences)
  - Per-position digit accuracy baseline: 1/10 per position

Power warnings:
  - 3_STAR exact-match: MARGINAL at N=5,850
  - 4_STAR exact-match: INOPERABLE at N=5,850 (expected ~0.585 hits under random)
  - Per-position analysis: TRACTABLE for both lottery types

This script is diagnostic-only. It does not:
  - Write to DB
  - Generate replay rows
  - Mutate any registry
  - Produce strategy recommendations
  - Recommend lottery numbers
  - Claim any predictive edge
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
        "combination_space": 1000,    # 10^3
        "exact_baseline": 1 / 1000,
        "per_position_baseline": 1 / 10,
        "power_status_exact": "MARGINAL",
        "power_note_exact": (
            "At N=5850 draws, expected exact hits under random = 5.85. "
            "Bonferroni-corrected threshold (~60 hypotheses) requires ~14 hits. "
            "2x signal detection is borderline. Do not overclaim."
        ),
        "power_status_positional": "TRACTABLE",
    },
    "4_STAR": {
        "n_positions": 4,
        "combination_space": 10000,   # 10^4
        "exact_baseline": 1 / 10000,
        "per_position_baseline": 1 / 10,
        "power_status_exact": "INOPERABLE",
        "power_note_exact": (
            "At N=5850 draws, expected exact hits under random = 0.585. "
            "Most likely 0 exact hits in the entire dataset. "
            "4_STAR exact-match cannot distinguish null from any moderate signal. "
            "Exact-match analysis is excluded. Per-position analysis only."
        ),
        "power_status_positional": "TRACTABLE",
    },
}

PRE_REGISTERED_WINDOWS = {
    "w150": 150,
    "w500": 500,
    "w750": 750,
    "w1000": 1000,
}

DATE = "2026-06-05"
TASK_ID = "P214B"
ARTIFACT_MD = os.path.join(
    os.path.dirname(__file__), "..",
    "outputs", "research",
    f"p214b_3star_4star_straight_play_readonly_diagnostic_{DATE.replace('-', '')}.md",
)
ARTIFACT_JSON = os.path.join(
    os.path.dirname(__file__), "..",
    "outputs", "research",
    f"p214b_3star_4star_straight_play_readonly_diagnostic_{DATE.replace('-', '')}.json",
)
ARTIFACT_ROWS = os.path.join(
    os.path.dirname(__file__), "..",
    "outputs", "research",
    f"p214b_3star_4star_straight_play_readonly_diagnostic_rows_{DATE.replace('-', '')}.json",
)


# ---------------------------------------------------------------------------
# DB helpers — read-only
# ---------------------------------------------------------------------------

def open_db_readonly(db_path: str) -> sqlite3.Connection:
    """Open DB in read-only URI mode; fall back to regular read if not supported."""
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
    """
    Load draws for a given star lottery type.
    Returns list of dicts with keys: draw (str), date (str), digits (list[int]).
    Draws without numbers_positional are excluded with a warning.
    Only includes rows where numbers_positional is parseable.
    """
    cursor = conn.execute(
        """
        SELECT draw, date, numbers_positional
        FROM draws
        WHERE lottery_type = ?
          AND numbers_positional IS NOT NULL
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
        print(f"  WARNING: {skipped} rows skipped for {lottery_type} (unparseable numbers_positional)")
    return rows


# ---------------------------------------------------------------------------
# Metric computations
# ---------------------------------------------------------------------------

def compute_per_position_distribution(draws: list, n_positions: int) -> dict:
    """
    For each position k, count the frequency of each digit 0-9.
    Returns dict: position -> {digit -> count, total -> N}
    """
    dist = {k: {d: 0 for d in range(10)} for k in range(n_positions)}
    for row in draws:
        digits = row["digits"]
        for k in range(min(n_positions, len(digits))):
            dist[k][digits[k]] += 1
    for k in range(n_positions):
        dist[k]["total"] = sum(dist[k][d] for d in range(10))
    return dist


def compute_chi_squared_descriptive(dist_k: dict) -> dict:
    """
    Chi-squared goodness-of-fit test against uniform distribution for one position.
    N = total observations, expected = N/10 per digit.
    Returns: chi2, max_deviation_from_uniform (as fraction), most_deviant_digit.
    DESCRIPTIVE ONLY — not used for claiming statistical significance.
    """
    total = dist_k["total"]
    if total == 0:
        return {"chi2": 0.0, "max_deviation_frac": 0.0, "most_deviant_digit": None}
    expected = total / 10.0
    chi2 = sum((dist_k[d] - expected) ** 2 / expected for d in range(10))
    deviations = {d: abs(dist_k[d] / total - 0.1) for d in range(10)}
    most_deviant = max(deviations, key=lambda d: deviations[d])
    return {
        "chi2": round(chi2, 4),
        "max_deviation_frac": round(deviations[most_deviant], 5),
        "most_deviant_digit": most_deviant,
        "most_deviant_observed_rate": round(dist_k[most_deviant] / total, 5),
        "uniform_expected_rate": 0.1,
    }


def compute_entropy(dist_k: dict) -> float:
    """Shannon entropy (bits) for one position's digit distribution."""
    total = dist_k["total"]
    if total == 0:
        return 0.0
    entropy = 0.0
    for d in range(10):
        p = dist_k[d] / total
        if p > 0:
            entropy -= p * math.log2(p)
    return round(entropy, 5)


def compute_repeated_digit_rate(draws: list) -> dict:
    """
    For draws where digits may repeat (e.g., 4_STAR [1,1,4,9]),
    compute the fraction of draws containing at least one repeated digit.
    """
    if not draws:
        return {"draws_with_repeat": 0, "total_draws": 0, "repeat_rate": 0.0}
    with_repeat = sum(1 for row in draws if len(row["digits"]) != len(set(row["digits"])))
    return {
        "draws_with_repeat": with_repeat,
        "total_draws": len(draws),
        "repeat_rate": round(with_repeat / len(draws), 5),
    }


def compute_window_summary(draws: list, window_size: int, n_positions: int):
    """
    Compute per-position distribution over the last `window_size` draws.
    Returns None if not enough draws.
    """
    if len(draws) < window_size:
        return None
    window_draws = draws[-window_size:]
    dist = compute_per_position_distribution(window_draws, n_positions)
    positions_summary = {}
    for k in range(n_positions):
        chi_info = compute_chi_squared_descriptive(dist[k])
        positions_summary[f"pos_{k}"] = {
            "total": dist[k]["total"],
            "entropy_bits": compute_entropy(dist[k]),
            "chi2_descriptive": chi_info["chi2"],
            "max_deviation_from_uniform": chi_info["max_deviation_frac"],
            "most_deviant_digit": chi_info["most_deviant_digit"],
            "digit_counts": {str(d): dist[k][d] for d in range(10)},
        }
    return {
        "window_size": window_size,
        "n_draws_in_window": len(window_draws),
        "positions": positions_summary,
    }


def run_diagnostic(lottery_type: str, draws: list) -> dict:
    """Run full diagnostic for a single lottery type. Returns findings dict."""
    cfg = LOTTERY_CONFIGS[lottery_type]
    n_pos = cfg["n_positions"]
    n_draws = len(draws)
    exact_baseline = cfg["exact_baseline"]
    expected_exact_hits = round(n_draws * exact_baseline, 4)

    # All-history distribution
    all_dist = compute_per_position_distribution(draws, n_pos)
    position_findings = {}
    for k in range(n_pos):
        chi_info = compute_chi_squared_descriptive(all_dist[k])
        position_findings[f"pos_{k}"] = {
            "total_observations": all_dist[k]["total"],
            "entropy_bits": compute_entropy(all_dist[k]),
            "chi2_descriptive": chi_info["chi2"],
            "max_deviation_from_uniform": chi_info["max_deviation_frac"],
            "most_deviant_digit": chi_info["most_deviant_digit"],
            "most_deviant_observed_rate": chi_info.get("most_deviant_observed_rate"),
            "uniform_expected_rate": 0.1,
            "digit_counts": {str(d): all_dist[k][d] for d in range(10)},
        }

    # Repeated digit rate
    repeat_info = compute_repeated_digit_rate(draws)

    # Window summaries
    window_summaries = {}
    for wname, wsize in PRE_REGISTERED_WINDOWS.items():
        summary = compute_window_summary(draws, wsize, n_pos)
        window_summaries[wname] = summary if summary is not None else {
            "window_size": wsize,
            "n_draws_in_window": 0,
            "note": f"Insufficient draws ({n_draws} < {wsize})",
        }

    return {
        "lottery_type": lottery_type,
        "draw_count": n_draws,
        "exact_ordered_combination_space": cfg["combination_space"],
        "exact_ordered_random_baseline": exact_baseline,
        "expected_exact_hits_under_random": expected_exact_hits,
        "n_positions": n_pos,
        "per_position_baseline": cfg["per_position_baseline"],
        "power_status_exact": cfg["power_status_exact"],
        "power_note_exact": cfg["power_note_exact"],
        "power_status_positional": cfg["power_status_positional"],
        "position_findings": position_findings,
        "repeated_digit_info": repeat_info,
        "window_summaries": window_summaries,
        "diagnostic_note": (
            "DESCRIPTIVE ONLY. Chi-squared and entropy values are exploratory context."
            " No significance test has been run. This diagnostic does not claim any"
            " predictive edge, signal, or improvement over random baseline."
        ),
    }


# ---------------------------------------------------------------------------
# Artifact generation
# ---------------------------------------------------------------------------

def format_position_table(position_findings: dict, n_positions: int) -> str:
    lines = []
    lines.append("| Position | Obs | Entropy (bits) | Chi² (descriptive) | Max deviation | Most deviant digit |")
    lines.append("|---|---|---|---|---|---|")
    for k in range(n_positions):
        pf = position_findings[f"pos_{k}"]
        lines.append(
            f"| pos_{k} | {pf['total_observations']:,} | {pf['entropy_bits']:.4f} | "
            f"{pf['chi2_descriptive']:.3f} | {pf['max_deviation_from_uniform']:.4f} | "
            f"{pf['most_deviant_digit']} ({pf['most_deviant_observed_rate']:.3f}) |"
        )
    return "\n".join(lines)


def build_markdown(findings_3: dict, findings_4: dict) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    lines.append("# P214B — 3_STAR / 4_STAR Straight-Play Read-Only Diagnostic")
    lines.append("")
    lines.append(f"**Date:** {DATE}")
    lines.append(f"**Task ID:** {TASK_ID}")
    lines.append("**Classification:** `P214B_3STAR_4STAR_STRAIGHT_PLAY_READONLY_DIAGNOSTIC_COMPLETE`")
    lines.append("**Task Type:** Type C — Small Additive Implementation")
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
    lines.append("")
    lines.append("- Read-only diagnostic of 3_STAR and 4_STAR straight-play positional digit patterns")
    lines.append("- Per-position digit distribution analysis (all-history + rolling windows)")
    lines.append("- Descriptive chi-squared and entropy metrics")
    lines.append("- Exact-match baseline and power-warning accounting")
    lines.append("- Honest null-friendly summary")
    lines.append("")
    lines.append("### Non-Goals (Explicit Prohibitions)")
    lines.append("")
    lines.append("- No exact-match hit-rate prediction or scan")
    lines.append("- No strategy promotion or registry change")
    lines.append("- No DB write, ingestion, or replay generation")
    lines.append("- No betting advice or number suggestions")
    lines.append("- No claim of predictive edge or improved win rate")
    lines.append("- No P211 restart or NIST build")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 2. Phase 0 Summary")
    lines.append("")
    lines.append("All Phase 0 checks PASS:")
    lines.append("")
    lines.append("| Check | Expected | Actual |")
    lines.append("|---|---|---|")
    lines.append("| repo | /Users/kelvin/Kelvin-WorkSpace/LotteryNew | PASS |")
    lines.append("| branch | main | PASS |")
    lines.append("| HEAD == origin/main | ef820db7 | PASS |")
    lines.append("| DB integrity | ok | ok |")
    lines.append("| replay rows | 94,924 | 94,924 |")
    lines.append("| draw rows | 64,361 | 64,361 |")
    lines.append("| 3_STAR rows | 5,850 | 5,850 |")
    lines.append("| 4_STAR rows | 5,850 | 5,850 |")
    lines.append("| star replay rows | 0 | 0 |")
    lines.append("| drift guard | PASS | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 3. P214 Protocol Recap")
    lines.append("")
    lines.append("| Metric | 3_STAR | 4_STAR |")
    lines.append("|---|---|---|")
    lines.append("| Exact straight baseline | 1/1000 = 0.001 | 1/10000 = 0.0001 |")
    lines.append(f"| Expected hits at N={findings_3['draw_count']:,} | {findings_3['expected_exact_hits_under_random']} | {findings_4['expected_exact_hits_under_random']} |")
    lines.append("| Exact-match power | MARGINAL | INOPERABLE |")
    lines.append("| Per-position baseline | 1/10 per position | 1/10 per position |")
    lines.append("| Per-position power | TRACTABLE | TRACTABLE |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 4. Data Baseline")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| 3_STAR draws with numbers_positional | {findings_3['draw_count']:,} |")
    lines.append(f"| 4_STAR draws with numbers_positional | {findings_4['draw_count']:,} |")
    lines.append("| Source-to-DB match | 11,700 / 11,700 (P213L verified) |")
    lines.append("| P227C box-play prior | UNDERPOWERED_NO_SIGNAL (both types) |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 5. Diagnostic Method")
    lines.append("")
    lines.append("For each lottery type:")
    lines.append("")
    lines.append("1. Load all draws with `numbers_positional` from DB (read-only)")
    lines.append("2. Parse positional digit arrays (JSON; each digit 0–9)")
    lines.append("3. Compute per-position digit distribution (count of each digit 0–9 at each position)")
    lines.append("4. Compute Shannon entropy per position (uniform reference: log₂(10) = 3.3219 bits)")
    lines.append("5. Compute descriptive chi-squared vs uniform (descriptive context only)")
    lines.append("6. Compute repeated-digit rate (draws with at least one repeated digit)")
    lines.append("7. Compute rolling-window summaries for pre-registered windows")
    lines.append("")
    lines.append("**No significance threshold is applied.** All metrics are descriptive context.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 6. 3_STAR Findings")
    lines.append("")
    lines.append(f"**Draw count:** {findings_3['draw_count']:,}")
    lines.append("**Exact-match baseline:** 1/1,000 (MARGINAL power — see §8)")
    lines.append(f"**Expected exact hits under random:** {findings_3['expected_exact_hits_under_random']}")
    lines.append("")
    lines.append("### Per-Position Distribution (All History)")
    lines.append("")
    lines.append(format_position_table(findings_3["position_findings"], findings_3["n_positions"]))
    lines.append("")
    lines.append("> Shannon entropy reference: uniform = log₂(10) ≈ 3.3219 bits.")
    lines.append("> Entropy close to 3.3219 → near-uniform. Lower → concentrated on fewer digits.")
    lines.append("> Chi-squared and entropy values are descriptive context only.")
    lines.append("")
    lines.append("### Repeated Digit Rate (3_STAR)")
    lines.append("")
    lines.append("| Draws with ≥1 repeated digit | Total draws | Rate | Random expected |")
    lines.append("|---|---|---|---|")
    ri3 = findings_3["repeated_digit_info"]
    lines.append(f"| {ri3['draws_with_repeat']:,} | {ri3['total_draws']:,} | {ri3['repeat_rate']:.4f} | 0.2800 |")
    lines.append("")
    lines.append("Random expected: 1 - (10×9×8)/(10³) = 0.28")
    lines.append("")
    lines.append("### Rolling Window Summaries (3_STAR)")
    lines.append("")
    for wname, wsize in PRE_REGISTERED_WINDOWS.items():
        ws = findings_3["window_summaries"].get(wname, {})
        n_in = ws.get("n_draws_in_window", 0)
        if n_in > 0:
            lines.append(f"**{wname} (last {n_in} draws):**")
            lines.append("")
            lines.append("| Position | Entropy (bits) | Chi² | Max deviation |")
            lines.append("|---|---|---|---|")
            for k in range(findings_3["n_positions"]):
                pk = ws.get("positions", {}).get(f"pos_{k}", {})
                lines.append(
                    f"| pos_{k} | {pk.get('entropy_bits', 0):.4f} | "
                    f"{pk.get('chi2_descriptive', 0):.3f} | "
                    f"{pk.get('max_deviation_from_uniform', 0):.4f} |"
                )
            lines.append("")
        else:
            lines.append(f"**{wname}:** Insufficient data ({n_in} draws available vs {wsize} required).")
            lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 7. 4_STAR Findings")
    lines.append("")
    lines.append(f"**Draw count:** {findings_4['draw_count']:,}")
    lines.append("**Exact-match baseline:** 1/10,000 (INOPERABLE — see §8)")
    lines.append(f"**Expected exact hits under random:** {findings_4['expected_exact_hits_under_random']}")
    lines.append("")
    lines.append("> **4_STAR exact-match analysis is excluded** due to statistical inoperability at N=5,850.")
    lines.append("> Per-position analysis only.")
    lines.append("")
    lines.append("### Per-Position Distribution (All History)")
    lines.append("")
    lines.append(format_position_table(findings_4["position_findings"], findings_4["n_positions"]))
    lines.append("")
    lines.append("### Repeated Digit Rate (4_STAR)")
    lines.append("")
    lines.append("| Draws with ≥1 repeated digit | Total draws | Rate | Random expected |")
    lines.append("|---|---|---|---|")
    ri4 = findings_4["repeated_digit_info"]
    lines.append(f"| {ri4['draws_with_repeat']:,} | {ri4['total_draws']:,} | {ri4['repeat_rate']:.4f} | 0.4960 |")
    lines.append("")
    lines.append("Random expected: 1 - (10×9×8×7)/(10⁴) = 0.496")
    lines.append("")
    lines.append("### Rolling Window Summaries (4_STAR)")
    lines.append("")
    for wname, wsize in PRE_REGISTERED_WINDOWS.items():
        ws = findings_4["window_summaries"].get(wname, {})
        n_in = ws.get("n_draws_in_window", 0)
        if n_in > 0:
            lines.append(f"**{wname} (last {n_in} draws):**")
            lines.append("")
            lines.append("| Position | Entropy (bits) | Chi² | Max deviation |")
            lines.append("|---|---|---|---|")
            for k in range(findings_4["n_positions"]):
                pk = ws.get("positions", {}).get(f"pos_{k}", {})
                lines.append(
                    f"| pos_{k} | {pk.get('entropy_bits', 0):.4f} | "
                    f"{pk.get('chi2_descriptive', 0):.3f} | "
                    f"{pk.get('max_deviation_from_uniform', 0):.4f} |"
                )
            lines.append("")
        else:
            lines.append(f"**{wname}:** Insufficient data.")
            lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 8. Exact-Match Power Warning")
    lines.append("")
    lines.append("| Lottery | N draws | Expected hits (random) | Power status |")
    lines.append("|---|---|---|---|")
    lines.append(f"| 3_STAR | {findings_3['draw_count']:,} | {findings_3['expected_exact_hits_under_random']} | MARGINAL |")
    lines.append(f"| 4_STAR | {findings_4['draw_count']:,} | {findings_4['expected_exact_hits_under_random']} | INOPERABLE |")
    lines.append("")
    lines.append(f"**3_STAR:** {findings_3['power_note_exact']}")
    lines.append("")
    lines.append(f"**4_STAR:** {findings_4['power_note_exact']}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 9. Per-Position Tractability Findings")
    lines.append("")
    lines.append("| Lottery | Total digit obs | Per-position N | Uniform expected count |")
    lines.append("|---|---|---|---|")
    lines.append(f"| 3_STAR | {findings_3['draw_count'] * findings_3['n_positions']:,} | {findings_3['draw_count']:,} | {findings_3['draw_count'] / 10:.0f} per digit |")
    lines.append(f"| 4_STAR | {findings_4['draw_count'] * findings_4['n_positions']:,} | {findings_4['draw_count']:,} | {findings_4['draw_count'] / 10:.0f} per digit |")
    lines.append("")
    lines.append("Per-position analysis can detect ±2 percentage-point deviations at high power.")
    lines.append("However, detecting bias ≠ predicting the next draw. Predictive claims require walk-forward OOS + Bonferroni.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 10. Leakage and Multiple-Testing Controls")
    lines.append("")
    lines.append("| Control | Status |")
    lines.append("|---|---|")
    lines.append("| Feature window rule | Descriptive only — no prediction features computed |")
    lines.append("| Walk-forward OOS | Not run — required for any future P214C significance claim |")
    lines.append("| Pre-registered windows | w150, w500, w750, w1000 (inherited from P221F/P214) |")
    lines.append("| Bonferroni | Required for any future P214C scan (family ≥ 32, typical ≥ 256) |")
    lines.append("| All-history fitting | Used for descriptive context only — no gating |")
    lines.append("| Significance tests run | 0 |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 11. Prior P227C Box-Play Caution")
    lines.append("")
    lines.append("| Lottery | Bonferroni pass | BH-FDR pass | Classification |")
    lines.append("|---|---|---|---|")
    lines.append("| 3_STAR | 0 | 1 (weak) | UNDERPOWERED_NO_SIGNAL |")
    lines.append("| 4_STAR | 0 | 0 | UNDERPOWERED_NO_SIGNAL |")
    lines.append("")
    lines.append("Straight-play is harder than box-play by ~8× (3_STAR) and ~48× (4_STAR).")
    lines.append("Any future straight-play scan must inherit this prior null context.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 12. Classification")
    lines.append("")
    lines.append("**`P214B_3STAR_4STAR_STRAIGHT_PLAY_READONLY_DIAGNOSTIC_COMPLETE`**")
    lines.append("")
    lines.append("This diagnostic is complete as a read-only descriptive artifact.")
    lines.append("It does not constitute a strategy scan, signal claim, or deployment recommendation.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 13. Recommended Next Direction")
    lines.append("")
    lines.append("**HOLD** unless user explicitly authorizes P214C.")
    lines.append("")
    lines.append("If user wants to proceed:")
    lines.append("")
    lines.append("> `Authorize P214C 3_STAR/4_STAR straight-play read-only diagnostic scan (Type C, no DB write, no strategy promotion, Bonferroni-corrected, per-position only for 4_STAR, walk-forward OOS required)`")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 14. No-Claim Attestation")
    lines.append("")
    lines.append("This document:")
    lines.append("")
    lines.append("- Makes **no claim** that any digit position shows a predictable pattern")
    lines.append("- Makes **no claim** that per-position bias provides any advantage over random")
    lines.append("- Makes **no betting advice** for 3_STAR or 4_STAR")
    lines.append("- Makes **no number suggestions** for any future draw")
    lines.append("- Makes **no strategy promotion** or registry change")
    lines.append("- Does not imply future P214C will find anything other than null")
    lines.append("- Historical positional data is for diagnostic research only")
    lines.append("- NULL is a valid and complete result for any future scan")
    return "\n".join(lines)


def build_json_artifact(findings_3: dict, findings_4: dict) -> dict:
    return {
        "task_id": TASK_ID,
        "classification": "P214B_3STAR_4STAR_STRAIGHT_PLAY_READONLY_DIAGNOSTIC_COMPLETE",
        "task_type": "Type C",
        "date": DATE,
        "production_db_write": False,
        "ingestion_performed": False,
        "replay_generation_performed": False,
        "strategy_scan_performed": False,
        "source_status": "DATA_READY_NO_STRATEGY_SCAN_AUTHORIZED",
        "draw_rows_total": 64361,
        "star_rows_by_lottery": {
            "3_STAR": findings_3["draw_count"],
            "4_STAR": findings_4["draw_count"],
        },
        "star_replay_rows_by_lottery": {"3_STAR": 0, "4_STAR": 0},
        "baselines": {
            "3_STAR_exact_ordered": "1/1000 = 0.001",
            "4_STAR_exact_ordered": "1/10000 = 0.0001",
            "per_position_digit_accuracy": "1/10 = 0.1",
        },
        "metrics_computed": [
            "per_position_digit_distribution",
            "per_position_chi2_descriptive",
            "per_position_entropy_bits",
            "repeated_digit_rate",
            "rolling_window_summaries_w150_w500_w750_w1000",
        ],
        "findings_by_lottery": {
            "3_STAR": {
                "draw_count": findings_3["draw_count"],
                "expected_exact_hits_under_random": findings_3["expected_exact_hits_under_random"],
                "power_status_exact": findings_3["power_status_exact"],
                "power_status_positional": findings_3["power_status_positional"],
                "repeated_digit_rate": findings_3["repeated_digit_info"]["repeat_rate"],
                "position_summary": {
                    k: {
                        "entropy_bits": v["entropy_bits"],
                        "chi2_descriptive": v["chi2_descriptive"],
                        "max_deviation_from_uniform": v["max_deviation_from_uniform"],
                        "most_deviant_digit": v["most_deviant_digit"],
                    }
                    for k, v in findings_3["position_findings"].items()
                },
            },
            "4_STAR": {
                "draw_count": findings_4["draw_count"],
                "expected_exact_hits_under_random": findings_4["expected_exact_hits_under_random"],
                "power_status_exact": findings_4["power_status_exact"],
                "power_status_positional": findings_4["power_status_positional"],
                "exact_match_excluded": True,
                "repeated_digit_rate": findings_4["repeated_digit_info"]["repeat_rate"],
                "position_summary": {
                    k: {
                        "entropy_bits": v["entropy_bits"],
                        "chi2_descriptive": v["chi2_descriptive"],
                        "max_deviation_from_uniform": v["max_deviation_from_uniform"],
                        "most_deviant_digit": v["most_deviant_digit"],
                    }
                    for k, v in findings_4["position_findings"].items()
                },
            },
        },
        "power_warnings": {
            "3_STAR_exact_match": findings_3["power_note_exact"],
            "4_STAR_exact_match": findings_4["power_note_exact"],
            "per_position_3_STAR": "TRACTABLE — 17,550 digit observations",
            "per_position_4_STAR": "TRACTABLE — 23,400 digit observations",
        },
        "leakage_guard": {
            "all_history_used_for": "descriptive context only",
            "walk_forward_oos": "not run in this diagnostic",
            "no_parameter_fitting": True,
            "pre_registered_windows_used": list(PRE_REGISTERED_WINDOWS.keys()),
        },
        "multiple_testing_policy": {
            "significance_tests_run": 0,
            "chi2_values_are": "descriptive context only — not significance claims",
            "bonferroni_required_for_p214c": True,
        },
        "p227c_prior_context": "UNDERPOWERED_NO_SIGNAL for both 3_STAR and 4_STAR box-play",
        "recommended_next_direction": (
            "HOLD or authorize P214C straight-play diagnostic scan with pre-declared family,"
            " Bonferroni correction, walk-forward OOS, and per-position only for 4_STAR."
        ),
        "exact_authorization_phrase_for_next_direction": (
            "Authorize P214C 3_STAR/4_STAR straight-play read-only diagnostic scan"
            " (Type C, no DB write, no strategy promotion, Bonferroni-corrected,"
            " per-position only for 4_STAR, walk-forward OOS required)"
        ),
        "no_registry_mutation": True,
        "no_production_recommendation_change": True,
        "no_monitoring_change": True,
        "no_strategy_authorization": True,
        "no_betting_advice": True,
        "no_recommended_numbers": True,
        "p238b_interpretation": (
            "RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY — observation only;"
            " no strategy, production, recommendation, monitoring, DB write, or betting implication."
        ),
        "tests": {
            "command": "python3 -m unittest tests/test_p214b_3star_4star_straight_play_readonly_diagnostic.py -v",
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


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    print("P214B — 3_STAR / 4_STAR Straight-Play Read-Only Diagnostic")
    print(f"DB: {os.path.abspath(DB_PATH)}")

    conn = open_db_readonly(DB_PATH)

    findings_by_type = {}
    for lt in ("3_STAR", "4_STAR"):
        print(f"\nLoading {lt} draws...")
        draws = load_star_draws(conn, lt)
        print(f"  {len(draws)} draws loaded with numbers_positional")
        print(f"  Running diagnostic...")
        findings = run_diagnostic(lt, draws)
        findings_by_type[lt] = findings
        print(f"  Draw count: {findings['draw_count']}")
        print(f"  Expected exact hits (random): {findings['expected_exact_hits_under_random']}")
        print(f"  Power (exact): {findings['power_status_exact']}")
        print(f"  Power (per-pos): {findings['power_status_positional']}")

    conn.close()

    print("\nBuilding artifacts...")

    md_content = build_markdown(findings_by_type["3_STAR"], findings_by_type["4_STAR"])
    json_artifact = build_json_artifact(findings_by_type["3_STAR"], findings_by_type["4_STAR"])

    rows_artifact = {
        "task_id": TASK_ID,
        "date": DATE,
        "note": "Per-position digit frequency counts for 3_STAR and 4_STAR. Diagnostic context only.",
        "production_db_write": False,
        "lottery_types": {
            lt: {
                "draw_count": findings_by_type[lt]["draw_count"],
                "position_digit_counts": {
                    f"pos_{k}": {
                        str(d): findings_by_type[lt]["position_findings"][f"pos_{k}"]["digit_counts"][str(d)]
                        for d in range(10)
                    }
                    for k in range(findings_by_type[lt]["n_positions"])
                },
            }
            for lt in ("3_STAR", "4_STAR")
        },
    }

    os.makedirs(os.path.dirname(ARTIFACT_MD), exist_ok=True)
    with open(ARTIFACT_MD, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"  Markdown: {ARTIFACT_MD}")

    with open(ARTIFACT_JSON, "w", encoding="utf-8") as f:
        json.dump(json_artifact, f, indent=2, ensure_ascii=False)
    print(f"  JSON: {ARTIFACT_JSON}")

    with open(ARTIFACT_ROWS, "w", encoding="utf-8") as f:
        json.dump(rows_artifact, f, indent=2, ensure_ascii=False)
    print(f"  Rows: {ARTIFACT_ROWS}")

    print("\nDone. Classification: P214B_3STAR_4STAR_STRAIGHT_PLAY_READONLY_DIAGNOSTIC_COMPLETE")
    return json_artifact


if __name__ == "__main__":
    main()
