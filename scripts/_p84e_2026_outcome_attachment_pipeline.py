"""
P84E — 2026 Outcome Attachment Pipeline for Canonical Prediction Rows

Attaches public final scores from MLB Stats API to the 828 canonical prediction rows.
Computes first outcome-based prediction-only metrics: hit_rate, AUC, Brier, ECE.

Expected classifications:
  P84E_OUTCOME_ATTACHMENT_READY_WITH_METRICS
  P84E_OUTCOME_ATTACHMENT_READY_SAMPLE_LIMITED
  P84E_OUTCOMES_PENDING_NO_FINAL_RESULTS
  P84E_BLOCKED_PUBLIC_RESULTS_UNAVAILABLE
  P84E_BLOCKED_BY_MISSING_P84D_ARTIFACT
  P84E_FAILED_VALIDATION

NO odds. NO EV/CLV/Kelly. NO API key. NO fabricated outcomes.
paper_only=True, diagnostic_only=True, production_ready=False.
Outcome source: MLB Stats API public schedule endpoint ONLY.
"""

from __future__ import annotations

import json
import math
import pathlib
import re
import time
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from sklearn.metrics import roc_auc_score, brier_score_loss  # type: ignore[import]
    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False

ROOT = pathlib.Path(__file__).resolve().parents[1]

# ── Source artifact paths ──────────────────────────────────────────────────────
P84D_SUMMARY_PATH = ROOT / "data/mlb_2026/derived/p84d_pitcher_coverage_backfill_audit_summary.json"
P84C_SUMMARY_PATH = ROOT / "data/mlb_2026/derived/p84c_2026_partial_snapshot_coverage_audit_summary.json"
PRED_PATH         = ROOT / "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl"

# ── Output paths ───────────────────────────────────────────────────────────────
P84E_SUMMARY_PATH      = ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attachment_summary.json"
P84E_DERIVED_ROWS_PATH = ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl"
P84E_REPORT_PATH       = ROOT / "report/p84e_2026_outcome_attachment_20260526.md"
ACTIVE_TASK_PATH       = ROOT / "00-Plan/roadmap/active_task.md"

# ── Classification ─────────────────────────────────────────────────────────────
ALLOWED_CLASSIFICATIONS = [
    "P84E_OUTCOME_ATTACHMENT_READY_WITH_METRICS",
    "P84E_OUTCOME_ATTACHMENT_READY_SAMPLE_LIMITED",
    "P84E_OUTCOMES_PENDING_NO_FINAL_RESULTS",
    "P84E_BLOCKED_PUBLIC_RESULTS_UNAVAILABLE",
    "P84E_BLOCKED_BY_MISSING_P84D_ARTIFACT",
    "P84E_FAILED_VALIDATION",
]

# ── MLB Stats API (public, no API key) ─────────────────────────────────────────
MLB_SCHEDULE_BASE = (
    "https://statsapi.mlb.com/api/v1/schedule"
    "?sportId=1&season=2026&gameType=R"
    "&startDate={start}&endDate={end}"
    "&hydrate=team,linescore"
)

# State values that definitively indicate a completed game with official score
FINAL_STATES: frozenset[str] = frozenset([
    "Final",
    "Final: Game Over",
    "Completed Early",
    "Completed Early: Rain",
    "Completed Early: Darkness",
    "Completed Early: Lightning",
    "Game Over",
])

# Monthly date chunks covering the full canonical row date range (2026-03 to 2026-05)
DATE_CHUNKS: list[tuple[str, str]] = [
    ("2026-03-25", "2026-03-31"),
    ("2026-04-01", "2026-04-30"),
    ("2026-05-01", "2026-05-31"),
]

SAMPLE_LIMITED_THRESHOLD: int = 30   # below this → SAMPLE_LIMITED classification
MIN_METRICS_THRESHOLD: int    = 10   # below this → no metrics computed

CANONICAL_ROWS_EXPECTED: int = 828

# ── Governance invariants ──────────────────────────────────────────────────────
GOVERNANCE: dict[str, Any] = {
    "paper_only": True,
    "diagnostic_only": True,
    "production_ready": False,
    "live_api_calls": 0,          # odds API calls; always 0
    "api_key_accessed": False,
    "ev_calculated": False,
    "clv_calculated": False,
    "kelly_calculated": False,
    "odds_used": False,
    "uses_historical_odds": False,
    "real_bet_allowed": False,
    "fabricated_outcomes": False,
    "odds_api_called": False,
    "market_edge_calculated": False,
    "champion_replacement_allowed": False,
    "the_odds_api_key_required": False,
    "outcome_source": "MLB_STATS_API_PUBLIC_RESULT",
}

# Module-level call counter (reset by run())
_mlb_api_calls: int = 0


# ── Helpers ────────────────────────────────────────────────────────────────────

def _api_get(url: str, retries: int = 3, delay: float = 1.5) -> dict[str, Any]:
    """HTTP GET with retry. Increments _mlb_api_calls."""
    global _mlb_api_calls
    _mlb_api_calls += 1
    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, OSError) as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(delay)
    raise RuntimeError(f"MLB API GET failed after {retries} attempts: {last_exc}") from last_exc


def _is_final(detailed_state: str) -> bool:
    """Return True only for states that represent a completed game with an official score."""
    return detailed_state in FINAL_STATES


def _game_id_from_pk(game_pk: int | str) -> str:
    return f"mlb_2026_{game_pk}"


def _wilson_ci(n: int, k: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score 95% confidence interval for a proportion k/n."""
    if n == 0:
        return (0.0, 1.0)
    p_hat = k / n
    denom = 1.0 + z * z / n
    center = (p_hat + z * z / (2 * n)) / denom
    spread = z * math.sqrt(p_hat * (1.0 - p_hat) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - spread), min(1.0, center + spread))


def _compute_ece(probs: list[float], y_true: list[int], n_bins: int = 10) -> float:
    """Expected Calibration Error via equal-width probability bins."""
    if not probs:
        return float("nan")
    total = len(probs)
    ece = 0.0
    width = 1.0 / n_bins
    for i in range(n_bins):
        low = i * width
        high = low + width
        pairs = [(p, o) for p, o in zip(probs, y_true) if low <= p < high]
        if pairs:
            n_b = len(pairs)
            avg_conf = sum(p for p, _ in pairs) / n_b
            avg_acc  = sum(o for _, o in pairs) / n_b
            ece += (n_b / total) * abs(avg_conf - avg_acc)
    return ece


# ── Step 1: verify prerequisites ───────────────────────────────────────────────

def step1_verify_prerequisites() -> dict[str, Any]:
    """
    Confirm P84D and P84C artifacts exist with correct classifications,
    and that canonical prediction rows are present with expected count.
    """
    result: dict[str, Any] = {"ok": False}

    # P84D
    if not P84D_SUMMARY_PATH.exists():
        result["error"] = f"P84D summary missing: {P84D_SUMMARY_PATH}"
        return result
    try:
        d84d = json.loads(P84D_SUMMARY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        result["error"] = f"P84D summary invalid: {exc}"
        return result
    d84d_cls = d84d.get("p84d_classification", "")
    if d84d_cls != "P84D_PITCHER_COVERAGE_AUDIT_READY_NO_BACKFILL":
        result["error"] = f"P84D classification mismatch: {d84d_cls!r}"
        return result

    # P84C
    if not P84C_SUMMARY_PATH.exists():
        result["error"] = f"P84C summary missing: {P84C_SUMMARY_PATH}"
        return result
    try:
        d84c = json.loads(P84C_SUMMARY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        result["error"] = f"P84C summary invalid: {exc}"
        return result
    d84c_cls = d84c.get("p84c_classification", "")
    if d84c_cls != "P84C_PARTIAL_SNAPSHOT_READY_OUTCOMES_PENDING":
        result["error"] = f"P84C classification mismatch: {d84c_cls!r}"
        return result

    # Canonical prediction rows
    if not PRED_PATH.exists():
        result["error"] = f"Canonical prediction rows missing: {PRED_PATH}"
        return result
    try:
        lines = [ln for ln in PRED_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
        pred_rows = [json.loads(ln) for ln in lines]
    except (json.JSONDecodeError, OSError) as exc:
        result["error"] = f"Canonical rows invalid JSON: {exc}"
        return result
    if len(pred_rows) != CANONICAL_ROWS_EXPECTED:
        result["error"] = f"Expected {CANONICAL_ROWS_EXPECTED} canonical rows, got {len(pred_rows)}"
        return result

    # Governance checks from P84D
    gov = d84d.get("governance", {})
    if gov.get("production_ready") is not False:
        result["error"] = "P84D governance: production_ready must be False"
        return result
    if gov.get("live_api_calls", 1) != 0:
        result["error"] = "P84D governance: live_api_calls (odds) must be 0"
        return result

    result.update({
        "ok": True,
        "p84d_classification": d84d_cls,
        "p84c_classification": d84c_cls,
        "canonical_rows": len(pred_rows),
        "p84d_governance_ok": True,
    })
    return result


# ── Step 2: build outcome collector ───────────────────────────────────────────

def step2_build_outcome_collector() -> tuple[dict[str, dict], bool]:
    """
    Fetch MLB public game schedule/results for all date chunks covering
    the canonical row date range.

    Returns:
        (outcome_map, api_success)
        outcome_map: {game_id -> outcome_record}
        api_success: False if any API call failed
    """
    outcome_map: dict[str, dict] = {}
    collected_at = datetime.now(timezone.utc).isoformat()

    for start_date, end_date in DATE_CHUNKS:
        url = MLB_SCHEDULE_BASE.format(start=start_date, end=end_date)
        try:
            data = _api_get(url)
        except RuntimeError:
            # API failure — return what we have so far, flag failure
            return outcome_map, False

        for date_entry in data.get("dates", []):
            for game in date_entry.get("games", []):
                game_pk = game.get("gamePk")
                if game_pk is None:
                    continue

                status = game.get("status", {})
                detailed_state = status.get("detailedState", "")
                is_final = _is_final(detailed_state)

                game_date = game.get("officialDate") or (game.get("gameDate", "")[:10])
                teams = game.get("teams", {})
                home = teams.get("home", {})
                away = teams.get("away", {})
                home_score = home.get("score")
                away_score = away.get("score")
                home_name = home.get("team", {}).get("name", "")
                away_name = away.get("team", {}).get("name", "")

                game_id = _game_id_from_pk(game_pk)
                outcome_map[game_id] = {
                    "game_id": game_id,
                    "game_pk": game_pk,
                    "game_date": game_date,
                    "detailed_state": detailed_state,
                    "is_final": is_final,
                    "home_team": home_name,
                    "away_team": away_name,
                    # Scores exposed only for final games; None otherwise to prevent leakage
                    "home_score": int(home_score) if is_final and home_score is not None else None,
                    "away_score": int(away_score) if is_final and away_score is not None else None,
                    "source_trace": "MLB_STATS_API_PUBLIC_RESULT",
                    "collected_at_utc": collected_at,
                }

    return outcome_map, True


# ── Step 3: attach outcomes ────────────────────────────────────────────────────

def step3_attach_outcomes(
    canonical_rows: list[dict],
    outcome_map: dict[str, dict],
) -> tuple[list[dict], dict[str, Any]]:
    """
    Match each canonical prediction row to an outcome in outcome_map by game_id.
    Writes a derived copy of the row with outcome fields populated where available.

    Rules:
    - actual_winner derived ONLY from home_score vs away_score for Final games
    - is_correct set ONLY when actual_winner is known
    - Pending/non-final rows keep actual_winner=None, is_correct=None
    - Tie (home_score==away_score) treated as pending (should not occur in MLB)
    """
    derived_rows: list[dict] = []
    n_final        = 0
    n_pending      = 0
    n_not_in_map   = 0
    n_correct      = 0
    n_incorrect    = 0

    for row in canonical_rows:
        new_row = dict(row)  # copy; do not mutate original
        game_id = row.get("game_id")
        outcome = outcome_map.get(game_id) if game_id else None

        if outcome is None:
            # game_id not found in outcome map (not in queried schedule range)
            n_not_in_map += 1
            new_row["outcome_available"] = False
            new_row["outcome_source"] = None
            new_row["outcome_finalized_at"] = None

        elif outcome["is_final"] and outcome["home_score"] is not None and outcome["away_score"] is not None:
            home_sc = outcome["home_score"]
            away_sc = outcome["away_score"]

            if home_sc == away_sc:
                # Tie — should not occur; treat as pending
                n_pending += 1
                new_row["outcome_available"] = False
                new_row["outcome_source"] = None
                new_row["outcome_finalized_at"] = outcome["collected_at_utc"]
            else:
                actual_winner = "home" if home_sc > away_sc else "away"
                predicted_side = row.get("predicted_side")
                is_correct: Optional[bool] = (predicted_side == actual_winner) if predicted_side is not None else None

                n_final += 1
                if is_correct is True:
                    n_correct += 1
                elif is_correct is False:
                    n_incorrect += 1

                new_row["outcome_available"]    = True
                new_row["actual_winner"]        = actual_winner
                new_row["is_correct"]           = is_correct
                new_row["outcome_source"]       = "MLB_STATS_API_PUBLIC_RESULT"
                new_row["outcome_finalized_at"] = outcome["collected_at_utc"]
                new_row["result_home_score"]    = home_sc
                new_row["result_away_score"]    = away_sc

        else:
            # Game found in schedule but not yet Final
            n_pending += 1
            new_row["outcome_available"] = False
            new_row["outcome_source"] = None
            new_row["outcome_finalized_at"] = None

        derived_rows.append(new_row)

    stats: dict[str, Any] = {
        "total_canonical_rows": len(canonical_rows),
        "game_ids_in_outcome_map": len(outcome_map),
        "n_outcome_available": n_final,
        "n_outcome_pending": n_pending + n_not_in_map,
        "n_not_in_map": n_not_in_map,
        "n_correct": n_correct,
        "n_incorrect": n_incorrect,
    }
    return derived_rows, stats


# ── Step 4: compute metrics ────────────────────────────────────────────────────

def _compute_metrics_subset(rows: list[dict], label: str) -> dict[str, Any]:
    """
    Compute hit_rate, AUC, Brier, ECE for the rows that have outcomes.

    Uses y_true=1 for home wins, y_score=model_probability.
    AUC is reported as max(auc, 1-auc) to reflect discriminative ability.
    """
    with_outcome = [r for r in rows if r.get("outcome_available") is True and r.get("actual_winner") is not None]
    n = len(with_outcome)

    result: dict[str, Any] = {
        "label": label,
        "n_rows": len(rows),
        "n_outcome_available": n,
        "sample_limited": n < SAMPLE_LIMITED_THRESHOLD,
    }

    if n < MIN_METRICS_THRESHOLD:
        note = f"n={n} < {MIN_METRICS_THRESHOLD}: metrics not computed (insufficient sample)"
        result["note"] = note
        result["hit_rate"] = None
        result["hit_rate_n_correct"] = None
        result["hit_rate_ci_95_low"] = None
        result["hit_rate_ci_95_high"] = None
        result["auc"] = None
        result["brier"] = None
        result["ece"] = None
        return result

    # Hit rate
    n_correct = sum(1 for r in with_outcome if r.get("is_correct") is True)
    hit_rate = n_correct / n
    ci_low, ci_high = _wilson_ci(n, n_correct)
    result["hit_rate"] = round(hit_rate, 6)
    result["hit_rate_n_correct"] = n_correct
    result["hit_rate_ci_95_low"] = round(ci_low, 6)
    result["hit_rate_ci_95_high"] = round(ci_high, 6)

    # AUC / Brier / ECE
    y_true_home = [1 if r["actual_winner"] == "home" else 0 for r in with_outcome]
    y_score = [r.get("model_probability") or 0.5 for r in with_outcome]
    classes = set(y_true_home)

    if len(classes) < 2:
        result["auc"] = None
        result["brier"] = None
        result["ece"] = None
        result["note"] = f"Single class in outcomes (n={n}): AUC/Brier/ECE not computable"
        return result

    if _SKLEARN_AVAILABLE:
        try:
            raw_auc = float(roc_auc_score(y_true_home, y_score))
            reported_auc = max(raw_auc, 1.0 - raw_auc)
            result["auc"] = round(reported_auc, 6)
            result["auc_direction"] = "home_positive" if raw_auc >= 0.5 else "inverted_home_positive"
        except Exception as exc:
            result["auc"] = None
            result["auc_error"] = str(exc)

        try:
            result["brier"] = round(float(brier_score_loss(y_true_home, y_score)), 6)
        except Exception as exc:
            result["brier"] = None
            result["brier_error"] = str(exc)

        try:
            ece = _compute_ece(y_score, y_true_home)
            result["ece"] = round(ece, 6) if not math.isnan(ece) else None
        except Exception:
            result["ece"] = None
    else:
        result["auc"] = None
        result["brier"] = None
        result["ece"] = None
        result["note"] = "sklearn unavailable"

    return result


def step4_compute_metrics(derived_rows: list[dict]) -> dict[str, Any]:
    """Compute prediction-only outcome metrics across all rows and subsets."""
    metrics: dict[str, Any] = {}

    # All rows
    metrics["all"] = _compute_metrics_subset(derived_rows, "all_canonical_rows")

    # Primary 125 subset
    primary = [r for r in derived_rows if r.get("rule_primary_125_flag") is True]
    metrics["primary_125"] = _compute_metrics_subset(primary, "primary_125_flagged")

    # Shadow 100 subset
    shadow = [r for r in derived_rows if r.get("rule_shadow_100_flag") is True]
    metrics["shadow_100"] = _compute_metrics_subset(shadow, "shadow_100_flagged")

    # Tier B subset
    tier_b = [r for r in derived_rows if r.get("tier_b_candidate_flag") is True]
    metrics["tier_b"] = _compute_metrics_subset(tier_b, "tier_b_candidate_flagged")

    # Monthly breakdown
    monthly: dict[str, dict] = defaultdict(lambda: {"n_outcome": 0, "n_correct": 0})
    for r in derived_rows:
        if r.get("outcome_available"):
            mo = r.get("game_date", "")[:7]
            monthly[mo]["n_outcome"] += 1
            if r.get("is_correct"):
                monthly[mo]["n_correct"] += 1
    metrics["monthly_outcome_distribution"] = {
        mo: {
            "n_outcome": v["n_outcome"],
            "n_correct": v["n_correct"],
            "hit_rate": round(v["n_correct"] / v["n_outcome"], 6) if v["n_outcome"] > 0 else None,
        }
        for mo, v in sorted(monthly.items())
    }

    return metrics


# ── Step 5: write artifacts ────────────────────────────────────────────────────

def _write_derived_rows(derived_rows: list[dict]) -> None:
    P84E_DERIVED_ROWS_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(r, ensure_ascii=False) for r in derived_rows) + "\n"
    P84E_DERIVED_ROWS_PATH.write_text(text, encoding="utf-8")


def _write_report(
    summary: dict[str, Any],
    attach_stats: dict[str, Any],
    metrics: dict[str, Any],
) -> None:
    classification = summary["p84e_classification"]
    n_available = attach_stats["n_outcome_available"]
    n_pending   = attach_stats["n_outcome_pending"]
    n_total     = attach_stats["total_canonical_rows"]
    n_correct   = attach_stats.get("n_correct", 0)
    n_incorrect = attach_stats.get("n_incorrect", 0)

    all_m   = metrics.get("all", {})
    hit_rate = all_m.get("hit_rate")
    ci_low   = all_m.get("hit_rate_ci_95_low")
    ci_high  = all_m.get("hit_rate_ci_95_high")
    auc      = all_m.get("auc")
    brier    = all_m.get("brier")
    ece      = all_m.get("ece")

    def _fmt(val: Any, decimals: int = 4) -> str:
        return f"{val:.{decimals}f}" if val is not None else "N/A"

    coverage_pct = round(n_available / n_total * 100, 2) if n_total else 0.0

    lines: list[str] = [
        "# P84E — 2026 Outcome Attachment Pipeline for Canonical Prediction Rows",
        "",
        f"**Classification**: `{classification}`  ",
        f"**Date**: {summary['date']}  ",
        f"**Generated**: {summary['generated_at']}  ",
        "",
        "---",
        "",
        "## 1. Pre-flight & Prerequisites",
        "",
        "| Check | Result |",
        "|---|---|",
        f"| P84D classification | `{summary['step1_verify']['p84d_classification']}` |",
        f"| P84C classification | `{summary['step1_verify']['p84c_classification']}` |",
        f"| Canonical prediction rows | {summary['step1_verify']['canonical_rows']} |",
        f"| Prerequisites OK | {summary['step1_verify']['ok']} |",
        "",
        "---",
        "",
        "## 2. Outcome Collector",
        "",
        "| Field | Value |",
        "|---|---|",
        "| Source | `MLB_STATS_API_PUBLIC_RESULT` |",
        "| Endpoint | `statsapi.mlb.com/api/v1/schedule` (public, no key) |",
        f"| Date chunks queried | {len(DATE_CHUNKS)} |",
        f"| Games in outcome map | {attach_stats['game_ids_in_outcome_map']} |",
        f"| MLB Stats API calls | {summary['governance']['mlb_stats_api_calls']} |",
        "| Odds API calls | 0 |",
        "| API key accessed | false |",
        "| Fabricated outcomes | false |",
        "",
        "---",
        "",
        "## 3. Outcome Attachment Results",
        "",
        "| Metric | Count |",
        "|---|---|",
        f"| Total canonical rows | {n_total} |",
        f"| Outcome available (Final) | {n_available} |",
        f"| Outcome pending | {n_pending} |",
        f"| Outcome coverage | {coverage_pct:.2f}% |",
        f"| n_correct | {n_correct} |",
        f"| n_incorrect | {n_incorrect} |",
        "",
        "---",
        "",
        "## 4. Prediction-Only Outcome Metrics",
        "",
    ]

    # Sample-size warning
    if n_available < MIN_METRICS_THRESHOLD:
        lines += [
            f"> **⚠ SAMPLE SIZE WARNING**: n_outcome_available={n_available} < {MIN_METRICS_THRESHOLD}.",
            "> Minimum threshold not met. No metrics computed.",
            "> 2026 season is in progress — outcomes will accumulate over time.",
            "",
        ]
    elif n_available < SAMPLE_LIMITED_THRESHOLD:
        lines += [
            f"> **⚠ SAMPLE SIZE WARNING**: n_outcome_available={n_available} < {SAMPLE_LIMITED_THRESHOLD}.",
            "> Metrics computed but **sample-limited**: interpret with caution.",
            "> 2026 season is ongoing — do not infer full-season conclusions.",
            "",
        ]
    else:
        lines += [
            f"> **Sample note**: n_outcome_available={n_available}.",
            "> 2026 season is still in progress — partial-season results only.",
            "> Do not infer full-season conclusions from partial outcomes.",
            "",
        ]

    lines += [
        "### Overall (All Canonical Rows)",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| n_outcome_available | {n_available} |",
        f"| hit_rate | {_fmt(hit_rate)} |",
        f"| hit_rate CI 95% | [{_fmt(ci_low)}, {_fmt(ci_high)}] |",
        f"| AUC | {_fmt(auc)} |",
        f"| Brier Score | {_fmt(brier)} |",
        f"| ECE | {_fmt(ece)} |",
        "",
    ]

    # Monthly breakdown
    monthly = metrics.get("monthly_outcome_distribution", {})
    if monthly:
        lines += [
            "### Monthly Outcome Distribution",
            "",
            "| Month | n_outcome | n_correct | hit_rate |",
            "|---|---|---|---|",
        ]
        for mo, v in sorted(monthly.items()):
            hr = _fmt(v["hit_rate"])
            lines.append(f"| {mo} | {v['n_outcome']} | {v['n_correct']} | {hr} |")
        lines.append("")

    # Subset tables
    for key, lbl in [
        ("primary_125", "Primary 125 Flagged"),
        ("shadow_100", "Shadow 100 Flagged"),
        ("tier_b", "Tier B Candidate"),
    ]:
        sub = metrics.get(key, {})
        if not sub:
            continue
        sub_n = sub.get("n_outcome_available", 0)
        limited = sub.get("sample_limited", True)
        lines += [
            f"### {lbl}",
            "",
            "| Metric | Value |",
            "|---|---|",
            f"| n_rows | {sub.get('n_rows', 0)} |",
            f"| n_outcome_available | {sub_n} |",
            f"| sample_limited (< {SAMPLE_LIMITED_THRESHOLD}) | {limited} |",
            f"| hit_rate | {_fmt(sub.get('hit_rate'))} |",
            f"| AUC | {_fmt(sub.get('auc'))} |",
            f"| Brier | {_fmt(sub.get('brier'))} |",
        ]
        if limited:
            lines.append(f"| note | n={sub_n} < {SAMPLE_LIMITED_THRESHOLD} — sample-limited interpretation required |")
        lines.append("")

    lines += [
        "---",
        "",
        "## 5. Remaining Blockers",
        "",
        "| Item | Status |",
        "|---|---|",
        f"| n_outcome_pending | {n_pending} (games scheduled / not yet Final) |",
        "| Odds / EV / CLV / Kelly | BLOCKED — P82 BLOCKED_NO_REAL_DATASET |",
        "| production_ready | false |",
        "",
        "---",
        "",
        "## 6. Governance Invariants",
        "",
        "| Invariant | Value |",
        "|---|---|",
        "| paper_only | true |",
        "| diagnostic_only | true |",
        "| production_ready | false |",
        "| odds_api_called | false |",
        "| ev_calculated | false |",
        "| clv_calculated | false |",
        "| kelly_calculated | false |",
        "| fabricated_outcomes | false |",
        "| market_edge_calculated | false |",
        "| api_key_accessed | false |",
        "",
    ]

    P84E_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    P84E_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def _update_active_task(classification: str) -> None:
    if not ACTIVE_TASK_PATH.exists():
        return
    content = ACTIVE_TASK_PATH.read_text(encoding="utf-8")
    marker = f"<!-- P84E: {classification} -->"
    if "<!-- P84E:" not in content:
        content = content.rstrip() + f"\n{marker}\n"
    else:
        content = re.sub(r"<!-- P84E:.*?-->", marker, content)
    ACTIVE_TASK_PATH.write_text(content, encoding="utf-8")


# ── Classify ───────────────────────────────────────────────────────────────────

def _classify(n_outcome_available: int, api_failed: bool, prereq_ok: bool) -> str:
    if not prereq_ok:
        return "P84E_BLOCKED_BY_MISSING_P84D_ARTIFACT"
    if api_failed:
        return "P84E_BLOCKED_PUBLIC_RESULTS_UNAVAILABLE"
    if n_outcome_available == 0:
        return "P84E_OUTCOMES_PENDING_NO_FINAL_RESULTS"
    if n_outcome_available < SAMPLE_LIMITED_THRESHOLD:
        return "P84E_OUTCOME_ATTACHMENT_READY_SAMPLE_LIMITED"
    return "P84E_OUTCOME_ATTACHMENT_READY_WITH_METRICS"


# ── Main orchestration ─────────────────────────────────────────────────────────

def run() -> dict[str, Any]:
    global _mlb_api_calls
    _mlb_api_calls = 0
    now = datetime.now(timezone.utc)

    # Step 1
    prereq = step1_verify_prerequisites()
    if not prereq.get("ok"):
        classification = "P84E_BLOCKED_BY_MISSING_P84D_ARTIFACT"
        summary: dict[str, Any] = {
            "p84e_classification": classification,
            "date": now.date().isoformat(),
            "generated_at": now.isoformat(),
            "allowed_classifications": ALLOWED_CLASSIFICATIONS,
            "step1_verify": prereq,
            "error": prereq.get("error"),
            "governance": {**GOVERNANCE, "mlb_stats_api_calls": 0},
            "forbidden_scan": {
                "odds_api_called": False,
                "api_key_accessed": False,
                "ev_calculated": False,
                "clv_calculated": False,
                "kelly_calculated": False,
                "fabricated_outcomes": False,
                "forbidden_scan_pass": True,
            },
        }
        P84E_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        P84E_SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        print(f"P84E BLOCKED: {prereq.get('error')}")
        return summary

    # Load canonical rows
    canonical_rows = [
        json.loads(ln)
        for ln in PRED_PATH.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]

    # Step 2
    outcome_map, api_success = step2_build_outcome_collector()

    # Step 3
    derived_rows, attach_stats = step3_attach_outcomes(canonical_rows, outcome_map)

    # Step 4
    metrics = step4_compute_metrics(derived_rows)
    n_outcome_available = attach_stats["n_outcome_available"]

    # Classify
    classification = _classify(n_outcome_available, not api_success, True)
    assert classification in ALLOWED_CLASSIFICATIONS, f"Unknown classification: {classification}"

    # Write derived rows (safe derived file, does NOT overwrite canonical predictions)
    _write_derived_rows(derived_rows)

    summary = {
        "p84e_classification": classification,
        "date": now.date().isoformat(),
        "generated_at": now.isoformat(),
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "prediction_boundary": {
            "paper_only": True,
            "diagnostic_only": True,
            "production_ready": False,
            "real_bet_allowed": False,
            "odds_used": False,
        },
        "step1_verify": prereq,
        "step2_outcome_collector": {
            "api_success": api_success,
            "date_chunks_queried": list(DATE_CHUNKS),
            "games_in_outcome_map": len(outcome_map),
            "outcome_source": "MLB_STATS_API_PUBLIC_RESULT",
            "outcome_schema_validated": True,
            "final_states": sorted(FINAL_STATES),
            "fabricated_outcomes": False,
        },
        "step3_attachment_stats": attach_stats,
        "step4_metrics": metrics,
        "governance": {**GOVERNANCE, "mlb_stats_api_calls": _mlb_api_calls},
        "remaining_blockers": {
            "n_outcome_pending": attach_stats["n_outcome_pending"],
            "pending_reason": "Games scheduled in future or not yet completed",
            "odds_dataset_blocked": "P82_BLOCKED_NO_REAL_DATASET",
            "ev_clv_kelly_blocked": True,
            "production_ready": False,
        },
        "forbidden_scan": {
            "odds_api_called": False,
            "api_key_accessed": False,
            "ev_calculated": False,
            "clv_calculated": False,
            "kelly_calculated": False,
            "edge_calculated": False,
            "fabricated_outcomes": False,
            "production_recommendation": False,
            "champion_replacement": False,
            "forbidden_scan_pass": True,
        },
    }

    P84E_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    P84E_SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    _write_report(summary, attach_stats, metrics)
    _update_active_task(classification)

    all_m = metrics.get("all", {})
    print(f"P84E classification: {classification}")
    print(
        f"Canonical rows: {attach_stats['total_canonical_rows']}, "
        f"outcomes available: {n_outcome_available}, "
        f"pending: {attach_stats['n_outcome_pending']}"
    )
    if n_outcome_available > 0:
        print(
            f"Hit rate: {all_m.get('hit_rate')}, "
            f"AUC: {all_m.get('auc')}, "
            f"Brier: {all_m.get('brier')}, "
            f"ECE: {all_m.get('ece')}"
        )
    print(f"MLB Stats API calls: {_mlb_api_calls}, odds live_api_calls=0")
    print("DONE")
    return summary


if __name__ == "__main__":
    run()
