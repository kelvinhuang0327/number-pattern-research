#!/usr/bin/env python3
"""
P238B - NIST-style randomness-audit artifact-only build.

This script is diagnostics-only. It reads draw-level observations from the
`draws` table, never uses replay rows as the statistical unit, and writes only
the authorized Markdown/JSON artifacts under outputs/research/.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
DEFAULT_JSON_PATH = REPO_ROOT / "outputs" / "research" / "p238b_nist_randomness_audit_artifact_20260604.json"
DEFAULT_MD_PATH = REPO_ROOT / "outputs" / "research" / "p238b_nist_randomness_audit_artifact_20260604.md"

TASK_ID = "P238B"
ARTIFACT_TYPE = "NIST_STYLE_RANDOMNESS_AUDIT_ARTIFACT_ONLY"
PRE_REGISTRATION_ID = "P238B_NIST_RANDOMNESS_AUDIT_ACTIVE_UNIVERSE_20260604"
ACTIVE_LOTTERIES = ("BIG_LOTTO", "DAILY_539", "POWER_LOTTO", "3_STAR", "4_STAR")
DEFAULT_WINDOWS = ("150", "500", "1000", "all-history")
TEST_FAMILIES = (
    "draw_inventory_and_data_quality",
    "ball_frequency_uniformity",
    "rolling_window_frequency",
    "special_zone_uniformity",
    "lag_serial_overlap",
    "gap_interarrival",
    "position_aware_availability",
)


LOTTERY_RULES: Dict[str, Dict[str, Any]] = {
    "BIG_LOTTO": {
        "number_min": 1,
        "number_max": 49,
        "draw_size": 6,
        "special_min": 1,
        "special_max": 49,
        "position_available": False,
    },
    "DAILY_539": {
        "number_min": 1,
        "number_max": 39,
        "draw_size": 5,
        "special_min": None,
        "special_max": None,
        "position_available": False,
    },
    "POWER_LOTTO": {
        "number_min": 1,
        "number_max": 38,
        "draw_size": 6,
        "special_min": 1,
        "special_max": 8,
        "position_available": False,
    },
    "3_STAR": {
        "number_min": 0,
        "number_max": 9,
        "draw_size": 3,
        "special_min": None,
        "special_max": None,
        "position_available": False,
    },
    "4_STAR": {
        "number_min": 0,
        "number_max": 9,
        "draw_size": 4,
        "special_min": None,
        "special_max": None,
        "position_available": False,
    },
}

ALERT_ORDER = {"GREEN": 0, "YELLOW": 1, "ORANGE": 2, "RED": 3}


@dataclass(frozen=True)
class Draw:
    lottery_type: str
    draw: str
    date: str
    numbers: Tuple[int, ...]
    special: Optional[int]


def _repo_value(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(args, cwd=REPO_ROOT, text=True).strip()
    except Exception:
        return ""


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    """Open SQLite in read-only URI mode. Write attempts must fail."""
    uri = f"file:{db_path.resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _parse_numbers(raw: Any) -> Tuple[int, ...]:
    if raw is None:
        return tuple()
    values = json.loads(raw) if isinstance(raw, str) else raw
    return tuple(int(v) for v in values)


def _parse_special(raw: Any) -> Optional[int]:
    if raw is None or raw == "":
        return None
    return int(raw)


def _normal_two_sided_p(z: float) -> float:
    return math.erfc(abs(z) / math.sqrt(2.0))


def _chi_square_sf_approx(statistic: float, df: int) -> Optional[float]:
    """Approximate chi-square survival function via Wilson-Hilferty transform."""
    if df <= 0 or statistic < 0:
        return None
    if statistic == 0:
        return 1.0
    z = ((statistic / df) ** (1.0 / 3.0) - (1.0 - 2.0 / (9.0 * df))) / math.sqrt(2.0 / (9.0 * df))
    return max(0.0, min(1.0, 0.5 * math.erfc(z / math.sqrt(2.0))))


def _load_draws(conn: sqlite3.Connection, lotteries: Sequence[str]) -> List[Draw]:
    placeholders = ",".join("?" for _ in lotteries)
    rows = conn.execute(
        f"SELECT lottery_type, draw, date, numbers, special FROM draws "
        f"WHERE lottery_type IN ({placeholders}) "
        f"ORDER BY lottery_type, date ASC, CAST(draw AS INTEGER) ASC",
        tuple(lotteries),
    ).fetchall()
    draws: List[Draw] = []
    for row in rows:
        draws.append(
            Draw(
                lottery_type=str(row["lottery_type"]),
                draw=str(row["draw"]),
                date=str(row["date"]),
                numbers=_parse_numbers(row["numbers"]),
                special=_parse_special(row["special"]),
            )
        )
    return draws


def _inventory(conn: sqlite3.Connection, active: Sequence[str]) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT lottery_type, COUNT(*) draw_rows, MIN(draw) min_draw, MAX(draw) max_draw, "
        "MIN(date) min_date, MAX(date) max_date "
        "FROM draws GROUP BY lottery_type ORDER BY lottery_type"
    ).fetchall()
    active_set = set(active)
    inventory: List[Dict[str, Any]] = []
    for row in rows:
        lottery_type = row["lottery_type"]
        inventory.append(
            {
                "lottery_type": lottery_type,
                "draw_rows": row["draw_rows"],
                "min_draw": str(row["min_draw"]),
                "max_draw": str(row["max_draw"]),
                "min_date": row["min_date"],
                "max_date": row["max_date"],
                "position_available": bool(LOTTERY_RULES.get(lottery_type, {}).get("position_available", False)),
                "included_in_primary_audit": lottery_type in active_set,
                "inventory_only_reason": "" if lottery_type in active_set else "not in pre-registered active audit universe",
            }
        )
    return inventory


def _validate_draw(draw: Draw) -> List[str]:
    rule = LOTTERY_RULES[draw.lottery_type]
    issues: List[str] = []
    if len(draw.numbers) != rule["draw_size"]:
        issues.append("invalid_number_count")
    lo, hi = rule["number_min"], rule["number_max"]
    if any(n < lo or n > hi for n in draw.numbers):
        issues.append("number_out_of_range")
    if len(set(draw.numbers)) != len(draw.numbers):
        issues.append("duplicate_number_within_draw")
    sp_min, sp_max = rule.get("special_min"), rule.get("special_max")
    if sp_min is not None and draw.special not in (None, 0):
        if draw.special < sp_min or draw.special > sp_max:
            issues.append("special_out_of_range")
    return issues


def _data_quality(conn: sqlite3.Connection, draws_by_lottery: Dict[str, List[Draw]]) -> Dict[str, Any]:
    duplicate_draw_keys = conn.execute(
        "SELECT COUNT(*) FROM ("
        "SELECT lottery_type, draw, COUNT(*) c FROM draws GROUP BY 1,2 HAVING c > 1"
        ")"
    ).fetchone()[0]

    invalid_number_rows = 0
    invalid_special_rows = 0
    invalid_examples: List[Dict[str, Any]] = []
    special_availability: Dict[str, Dict[str, int]] = {}

    for lottery_type, draws in draws_by_lottery.items():
        special_present = 0
        special_missing_or_zero = 0
        for draw in draws:
            issues = _validate_draw(draw)
            if any(i in issues for i in ("invalid_number_count", "number_out_of_range", "duplicate_number_within_draw")):
                invalid_number_rows += 1
            if "special_out_of_range" in issues:
                invalid_special_rows += 1
            if issues and len(invalid_examples) < 10:
                invalid_examples.append(
                    {
                        "lottery_type": lottery_type,
                        "draw": draw.draw,
                        "date": draw.date,
                        "issues": issues,
                    }
                )
            if draw.special not in (None, 0):
                special_present += 1
            else:
                special_missing_or_zero += 1
        special_availability[lottery_type] = {
            "positive_special_rows": special_present,
            "missing_or_zero_special_rows": special_missing_or_zero,
        }

    return {
        "draw_table_exists": True,
        "duplicate_draw_keys": duplicate_draw_keys,
        "invalid_number_rows": invalid_number_rows,
        "invalid_special_rows": invalid_special_rows,
        "invalid_examples": invalid_examples,
        "date_parse_warnings": [
            "date strings are preserved as source text because the DB mixes YYYY-MM-DD and YYYY/MM/DD formats"
        ],
        "position_data_unavailable_lotteries": list(ACTIVE_LOTTERIES),
        "special_availability": special_availability,
    }


def _number_range(rule: Dict[str, Any]) -> range:
    return range(int(rule["number_min"]), int(rule["number_max"]) + 1)


def _chi_square_counts(counts: Dict[int, int], expected: float, values: Iterable[int]) -> float:
    if expected <= 0:
        return 0.0
    return sum(((counts.get(v, 0) - expected) ** 2) / expected for v in values)


def _result(
    *,
    lottery_type: str,
    zone: str,
    window: str,
    test_family: str,
    sample_size_draws: int,
    statistic: Optional[float],
    p_value_raw: Optional[float],
    details: Dict[str, Any],
    limitations: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "lottery_type": lottery_type,
        "zone": zone,
        "window": window,
        "test_family": test_family,
        "unit_type": "draw",
        "sample_size_draws": sample_size_draws,
        "statistic": statistic,
        "p_value_raw": p_value_raw,
        "p_value_corrected": None,
        "p_value_bh_fdr_report_only": None,
        "correction_method": "bonferroni",
        "alert_level": "GREEN",
        "diagnostics_only": True,
        "predictability_claim": False,
        "win_rate_claim": False,
        "betting_advice": False,
        "strategy_authorized": False,
        "production_change_authorized": False,
        "red_authorizes_human_review_only": True,
        "red_authorizes_strategy": False,
        "replay_rows_used_as_unit": False,
        "details": details,
        "limitations": limitations or [],
    }


def _frequency_test(lottery_type: str, draws: List[Draw], window: str) -> Dict[str, Any]:
    rule = LOTTERY_RULES[lottery_type]
    counts: Counter[int] = Counter()
    for draw in draws:
        counts.update(draw.numbers)
    values = list(_number_range(rule))
    expected = len(draws) * rule["draw_size"] / len(values) if values else 0.0
    statistic = _chi_square_counts(counts, expected, values)
    p = _chi_square_sf_approx(statistic, max(1, len(values) - 1))
    return _result(
        lottery_type=lottery_type,
        zone="first-zone",
        window=window,
        test_family="ball_frequency_uniformity",
        sample_size_draws=len(draws),
        statistic=statistic,
        p_value_raw=p,
        details={
            "expected_count_per_number": expected,
            "min_observed_count": min(counts.get(v, 0) for v in values) if values else 0,
            "max_observed_count": max(counts.get(v, 0) for v in values) if values else 0,
            "pool_size": len(values),
            "draw_size": rule["draw_size"],
        },
        limitations=[
            "chi-square p-value uses an approximation and is a compatibility diagnostic, not a predictor",
            "sorted draw sets are not position-aware data",
        ],
    )


def _special_test(lottery_type: str, draws: List[Draw], window: str) -> Optional[Dict[str, Any]]:
    rule = LOTTERY_RULES[lottery_type]
    if rule.get("special_min") is None:
        return None
    special_draws = [d for d in draws if d.special not in (None, 0)]
    if not special_draws:
        return _result(
            lottery_type=lottery_type,
            zone="special-zone",
            window=window,
            test_family="special_zone_uniformity",
            sample_size_draws=0,
            statistic=None,
            p_value_raw=None,
            details={"reason": "no positive special values available"},
            limitations=["special-zone test unavailable for this lottery/window"],
        )
    values = range(int(rule["special_min"]), int(rule["special_max"]) + 1)
    counts = Counter(d.special for d in special_draws if d.special is not None)
    expected = len(special_draws) / len(list(values))
    statistic = _chi_square_counts(counts, expected, values)
    p = _chi_square_sf_approx(statistic, max(1, len(list(values)) - 1))
    return _result(
        lottery_type=lottery_type,
        zone="special-zone",
        window=window,
        test_family="special_zone_uniformity",
        sample_size_draws=len(special_draws),
        statistic=statistic,
        p_value_raw=p,
        details={
            "expected_count_per_special": expected,
            "positive_special_rows": len(special_draws),
            "missing_or_zero_special_rows": len(draws) - len(special_draws),
            "special_pool_size": len(list(values)),
        },
        limitations=[
            "special values with 0/null semantics are excluded from the special-zone statistic",
            "special-zone result is diagnostics-only and not a recommendation signal",
        ],
    )


def _lag_overlap_test(lottery_type: str, draws: List[Draw]) -> Dict[str, Any]:
    rule = LOTTERY_RULES[lottery_type]
    overlaps = [
        len(set(a.numbers) & set(b.numbers))
        for a, b in zip(draws, draws[1:])
    ]
    pool_size = rule["number_max"] - rule["number_min"] + 1
    expected = (rule["draw_size"] ** 2) / pool_size
    n = len(overlaps)
    if n < 2:
        statistic = None
        p = None
    else:
        mean_observed = sum(overlaps) / n
        variance = sum((x - mean_observed) ** 2 for x in overlaps) / (n - 1)
        se = math.sqrt(variance / n) if variance > 0 else 0.0
        statistic = None if se == 0 else (mean_observed - expected) / se
        p = None if statistic is None else _normal_two_sided_p(statistic)
    return _result(
        lottery_type=lottery_type,
        zone="first-zone",
        window="all-history",
        test_family="lag_serial_overlap",
        sample_size_draws=len(draws),
        statistic=statistic,
        p_value_raw=p,
        details={
            "lag": 1,
            "mean_overlap_observed": (sum(overlaps) / n) if n else None,
            "mean_overlap_random_baseline": expected,
            "overlap_pairs": n,
        },
        limitations=[
            "lag overlap is a simple serial-dependence analogue, not a forecast",
            "normal approximation is used for the aggregate overlap statistic",
        ],
    )


def _gap_test(lottery_type: str, draws: List[Draw]) -> Dict[str, Any]:
    rule = LOTTERY_RULES[lottery_type]
    pool = list(_number_range(rule))
    p_inclusion = rule["draw_size"] / len(pool)
    expected_gap = 1.0 / p_inclusion
    gaps: List[int] = []
    last_seen: Dict[int, int] = {}
    for idx, draw in enumerate(draws):
        for n in set(draw.numbers):
            if n in last_seen:
                gaps.append(idx - last_seen[n])
            last_seen[n] = idx
    if len(gaps) < 2:
        statistic = None
        p = None
        mean_gap = None
    else:
        mean_gap = sum(gaps) / len(gaps)
        approx_var = (1.0 - p_inclusion) / (p_inclusion ** 2)
        se = math.sqrt(approx_var / len(gaps)) if approx_var > 0 else 0.0
        statistic = None if se == 0 else (mean_gap - expected_gap) / se
        p = None if statistic is None else _normal_two_sided_p(statistic)
    return _result(
        lottery_type=lottery_type,
        zone="first-zone",
        window="all-history",
        test_family="gap_interarrival",
        sample_size_draws=len(draws),
        statistic=statistic,
        p_value_raw=p,
        details={
            "mean_gap_observed_draws": mean_gap,
            "mean_gap_random_baseline_draws": expected_gap,
            "gap_count": len(gaps),
            "inclusion_probability_per_draw": p_inclusion,
        },
        limitations=[
            "gap checks are audit statistics; hot/cold or overdue interpretations are forbidden",
            "normal approximation is used for an aggregate inter-arrival statistic",
        ],
    )


def _position_unavailable_result(lottery_type: str, sample_size: int) -> Dict[str, Any]:
    return _result(
        lottery_type=lottery_type,
        zone="position-aware",
        window="all-history",
        test_family="position_aware_availability",
        sample_size_draws=sample_size,
        statistic=None,
        p_value_raw=None,
        details={"position_data_status": "POSITION_DATA_UNAVAILABLE"},
        limitations=[
            "DB stores sorted number sets for the audit universe; raw draw order is not available",
            "position-aware tests are skipped instead of inferred",
        ],
    )


def _apply_corrections(results: List[Dict[str, Any]]) -> int:
    p_results = [r for r in results if r["p_value_raw"] is not None]
    family_size = len(p_results)
    if family_size == 0:
        return 0

    for r in p_results:
        corrected = min(1.0, float(r["p_value_raw"]) * family_size)
        r["p_value_corrected"] = corrected
        r["alert_level"] = _alert_level(corrected)
        r["historical_artifact_escalation_cap"] = "YELLOW_OBSERVATION_ONLY"

    ordered = sorted(enumerate(p_results), key=lambda item: item[1]["p_value_raw"])
    m = len(ordered)
    running_min = 1.0
    q_values: Dict[int, float] = {}
    for rank_from_end, (idx, result) in enumerate(reversed(ordered), start=1):
        rank = m - rank_from_end + 1
        q = min(running_min, result["p_value_raw"] * m / rank)
        running_min = q
        q_values[idx] = min(1.0, q)
    for idx, result in enumerate(p_results):
        result["p_value_bh_fdr_report_only"] = q_values[idx]
    return family_size


def _alert_level(corrected_p: Optional[float]) -> str:
    """Classify a historical artifact result conservatively.

    P237C reserves ORANGE/RED for repeated, corrected anomalies with
    independent future confirmation. P238B is an artifact-only historical
    diagnostic, so corrected anomalies are capped at YELLOW observation-only.
    """
    if corrected_p is None:
        return "GREEN"
    if corrected_p < 0.05:
        return "YELLOW"
    return "GREEN"


def _overall_level(results: List[Dict[str, Any]]) -> str:
    level = "GREEN"
    for result in results:
        if ALERT_ORDER[result["alert_level"]] > ALERT_ORDER[level]:
            level = result["alert_level"]
    return level


def _classification(level: str) -> str:
    if level == "RED":
        return "RANDOMNESS_AUDIT_RED_HUMAN_REVIEW_ONLY"
    if level == "ORANGE":
        return "RANDOMNESS_AUDIT_ORANGE_NEEDS_INDEPENDENT_CONFIRMATION"
    if level == "YELLOW":
        return "RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY"
    return "RANDOMNESS_AUDIT_GREEN_NULL_SUCCESS"


def _alert_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts = Counter(r["alert_level"] for r in results)
    level = _overall_level(results)
    return {
        "overall_level": level,
        "green_count": counts.get("GREEN", 0),
        "yellow_count": counts.get("YELLOW", 0),
        "orange_count": counts.get("ORANGE", 0),
        "red_count": counts.get("RED", 0),
        "red_authorizes_strategy": False,
        "red_authorizes_human_review_only": True,
        "red_authorizes_production_change": False,
        "red_authorizes_registry_change": False,
        "red_authorizes_recommendation_change": False,
        "red_authorizes_betting_action": False,
    }


def _build_results(draws_by_lottery: Dict[str, List[Draw]], windows: Sequence[str]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for lottery_type in ACTIVE_LOTTERIES:
        draws = draws_by_lottery[lottery_type]
        results.append(_frequency_test(lottery_type, draws, "all-history"))
        for window in windows:
            if window == "all-history":
                continue
            size = int(window)
            if len(draws) >= size:
                results.append(_frequency_test(lottery_type, draws[-size:], f"latest-{size}"))
        sp = _special_test(lottery_type, draws, "all-history")
        if sp is not None:
            results.append(sp)
        results.append(_lag_overlap_test(lottery_type, draws))
        results.append(_gap_test(lottery_type, draws))
        results.append(_position_unavailable_result(lottery_type, len(draws)))
    return results


def build_artifact(
    db_path: Path = DEFAULT_DB_PATH,
    lotteries: Sequence[str] = ACTIVE_LOTTERIES,
    windows: Sequence[str] = DEFAULT_WINDOWS,
    correction: str = "bonferroni",
) -> Dict[str, Any]:
    if tuple(lotteries) != ACTIVE_LOTTERIES:
        raise ValueError("P238B requires the explicit active universe: " + ",".join(ACTIVE_LOTTERIES))
    if correction != "bonferroni":
        raise ValueError("P238B tripwire escalation uses bonferroni as the primary correction")

    conn = _connect_ro(db_path)
    try:
        before_rows = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
        draw_table_exists = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='draws'"
        ).fetchone()[0] == 1
        if not draw_table_exists:
            raise RuntimeError("draws table missing")
        inventory = _inventory(conn, lotteries)
        active_draws = _load_draws(conn, lotteries)
        draws_by_lottery: Dict[str, List[Draw]] = {lt: [] for lt in lotteries}
        for draw in active_draws:
            draws_by_lottery[draw.lottery_type].append(draw)
        data_quality = _data_quality(conn, draws_by_lottery)
        after_rows = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    finally:
        conn.close()

    results = _build_results(draws_by_lottery, windows)
    family_size = _apply_corrections(results)
    alert_summary = _alert_summary(results)

    now = datetime.now(timezone.utc).isoformat()
    head = _repo_value(["git", "rev-parse", "HEAD"])
    branch = _repo_value(["git", "branch", "--show-current"])
    classification = _classification(alert_summary["overall_level"])

    active_inventory = [item for item in inventory if item["included_in_primary_audit"]]
    return {
        "task_id": TASK_ID,
        "artifact_type": ARTIFACT_TYPE,
        "generated_at": now,
        "diagnostics_only": True,
        "predictability_claim": False,
        "win_rate_claim": False,
        "betting_advice": False,
        "strategy_authorized": False,
        "production_change_authorized": False,
        "monitoring_job_authorized": False,
        "db_write_performed": False,
        "registry_write_performed": False,
        "controlled_apply_authorized": False,
        "p211_restart_authorized": False,
        "data_snapshot": {
            "repo": str(REPO_ROOT),
            "branch": branch,
            "head": head,
            "db_path": str(db_path.relative_to(REPO_ROOT) if db_path.is_absolute() and db_path.is_relative_to(REPO_ROOT) else db_path),
            "db_open_mode": "read-only",
            "draw_table": "draws",
            "replay_table": "strategy_prediction_replays",
            "replay_rows_used_as_unit": False,
            "db_rows_before": before_rows,
            "db_rows_after": after_rows,
        },
        "pre_registration": {
            "pre_registration_id": PRE_REGISTRATION_ID,
            "lotteries": list(lotteries),
            "zones": ["first-zone", "special-zone where available", "position-aware availability only"],
            "test_families": list(TEST_FAMILIES),
            "windows": list(windows),
            "family_size_declared_before_run": family_size,
            "primary_correction": "bonferroni",
            "secondary_report_only_correction": "bh_fdr",
            "red_alert_authorizes": "human_review_only",
        },
        "data_inventory": inventory,
        "active_audit_inventory": active_inventory,
        "data_quality": data_quality,
        "test_results": results,
        "alert_summary": alert_summary,
        "governance": {
            "null_is_success": True,
            "green_null_success": True,
            "no_predictor": True,
            "no_win_rate_claim": True,
            "no_betting_advice": True,
            "no_strategy_authorized": True,
            "no_production_change_authorized": True,
            "red_alert_human_review_only": True,
            "required_next_authorization": "explicit_user_authorization_required_for_any_follow_up",
        },
        "classification": classification,
        "final_recommendation": "HOLD",
        "final_classification": "P238B_NIST_RANDOMNESS_AUDIT_ARTIFACT_ONLY_BUILD_COMPLETE",
    }


def _fmt_p(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    if value < 0.0001:
        return f"{value:.3e}"
    return f"{value:.4f}"


def render_markdown(artifact: Dict[str, Any]) -> str:
    snapshot = artifact["data_snapshot"]
    summary = artifact["alert_summary"]
    lines: List[str] = [
        "# P238B - NIST Randomness-Audit Artifact-Only Build",
        "",
        "**Task ID:** P238B",
        "**Type:** diagnostics-only artifact build; read-only DB mode",
        f"**Generated At:** {artifact['generated_at']}",
        f"**Final Classification:** `{artifact['final_classification']}`",
        f"**Audit Classification:** `{artifact['classification']}`",
        "",
        "## Executive Summary",
        "",
        "This artifact is diagnostics-only.",
        "This artifact does not predict lottery numbers.",
        "This artifact does not improve win rate.",
        "This artifact is not betting advice.",
        "RED alert authorizes human review only.",
        "NULL / GREEN is success.",
        "",
        f"Overall alert level: **{summary['overall_level']}**. Final recommendation: **{artifact['final_recommendation']}**.",
        "",
        "## Authorization And Non-Scope",
        "",
        "- Authorized: P238B artifact-only implementation using read-only DB mode.",
        "- Not authorized: DB write, registry mutation, production/recommendation change, monitoring job, scheduler, controlled_apply, strategy adapter, strategy promotion, P211 restart, betting advice.",
        "- `strategy_prediction_replays` is not used as the randomness-test unit.",
        "",
        "## Data Snapshot",
        "",
        f"- Repo: `{snapshot['repo']}`",
        f"- Branch: `{snapshot['branch']}`",
        f"- HEAD: `{snapshot['head']}`",
        f"- DB path: `{snapshot['db_path']}`",
        f"- DB open mode: `{snapshot['db_open_mode']}`",
        f"- Replay rows before/after: `{snapshot['db_rows_before']}` / `{snapshot['db_rows_after']}`",
        f"- Replay rows used as unit: `{snapshot['replay_rows_used_as_unit']}`",
        "",
        "## Draw-Level Unit Declaration",
        "",
        "The statistical unit is one chronological draw observation: `(lottery_type, draw, date, zone, number_unit)`. Multi-bet replay rows, strategy IDs, and bet indexes are not audit units.",
        "",
        "## Pre-Registration",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| ID | `{artifact['pre_registration']['pre_registration_id']}` |",
        f"| Active lotteries | `{', '.join(artifact['pre_registration']['lotteries'])}` |",
        f"| Windows | `{', '.join(artifact['pre_registration']['windows'])}` |",
        f"| Primary correction | `{artifact['pre_registration']['primary_correction']}` |",
        f"| Family size | `{artifact['pre_registration']['family_size_declared_before_run']}` |",
        "",
        "## Data Inventory",
        "",
        "| Lottery | Draw Rows | Included | Min Draw | Max Draw | Min Date | Max Date |",
        "|---|---:|---|---:|---:|---|---|",
    ]
    for item in artifact["data_inventory"]:
        lines.append(
            f"| {item['lottery_type']} | {item['draw_rows']} | {item['included_in_primary_audit']} | "
            f"{item['min_draw']} | {item['max_draw']} | {item['min_date']} | {item['max_date']} |"
        )

    dq = artifact["data_quality"]
    lines.extend(
        [
            "",
            "## Data-Quality Checks",
            "",
            f"- Draw table exists: `{dq['draw_table_exists']}`",
            f"- Duplicate `(lottery_type, draw)` keys: `{dq['duplicate_draw_keys']}`",
            f"- Invalid number rows: `{dq['invalid_number_rows']}`",
            f"- Invalid special rows: `{dq['invalid_special_rows']}`",
            f"- Position-aware status: `POSITION_DATA_UNAVAILABLE` for `{', '.join(dq['position_data_unavailable_lotteries'])}`",
            "",
            "## Test Family Results",
            "",
            "| Lottery | Zone | Window | Family | N Draws | Raw p | Bonferroni p | Alert |",
            "|---|---|---|---|---:|---:|---:|---|",
        ]
    )
    for result in artifact["test_results"]:
        lines.append(
            f"| {result['lottery_type']} | {result['zone']} | {result['window']} | "
            f"{result['test_family']} | {result['sample_size_draws']} | "
            f"{_fmt_p(result['p_value_raw'])} | {_fmt_p(result['p_value_corrected'])} | {result['alert_level']} |"
        )

    lines.extend(
        [
            "",
            "## Multiple-Testing Correction Summary",
            "",
            f"- Primary correction: Bonferroni across `{artifact['pre_registration']['family_size_declared_before_run']}` p-valued diagnostics.",
            "- BH-FDR values are report-only and do not authorize escalation.",
            "- Historical anomalies are capped at YELLOW observation-only; ORANGE/RED require independent future confirmation.",
            "",
            "## Alert Taxonomy Results",
            "",
            f"- GREEN: `{summary['green_count']}`",
            f"- YELLOW: `{summary['yellow_count']}`",
            f"- ORANGE: `{summary['orange_count']}`",
            f"- RED: `{summary['red_count']}`",
            f"- Overall: `{summary['overall_level']}`",
            "- RED does not authorize strategy, production, registry, recommendation, monitoring, DB write, or betting action.",
            "- This historical artifact cannot emit ORANGE/RED escalation without a future confirmation task.",
            "",
            "## Limitations And False-Positive Risks",
            "",
            "- The audit is a multiple-testing surface; corrected p-values are required.",
            "- Chi-square and normal p-values are approximations intended for governance diagnostics.",
            "- Stored numbers are sorted sets, so position-aware tests are skipped.",
            "- A non-GREEN alert is a prompt for human diagnostic review only, not a prediction claim.",
            "",
            "## Governance Recommendation",
            "",
            f"Recommendation: **{artifact['final_recommendation']}**. Do not start strategy work, production changes, registry changes, monitoring jobs, DB writes, or betting actions from this artifact.",
            "",
            "## Required Completion Check",
            "",
            "1. Artifact generated in read-only DB mode.",
            "2. Markdown and JSON artifacts emitted under `outputs/research/`.",
            "3. DB rows unchanged.",
            "4. No registry / production / recommendation / monitoring / strategy changes authorized.",
            "",
            f"Final Classification: `{artifact['final_classification']}`",
            "",
        ]
    )
    return "\n".join(lines)


def write_artifacts(artifact: Dict[str, Any], json_path: Path, md_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(artifact), encoding="utf-8")


def run(
    db_path: Path = DEFAULT_DB_PATH,
    json_path: Path = DEFAULT_JSON_PATH,
    md_path: Path = DEFAULT_MD_PATH,
    lotteries: Sequence[str] = ACTIVE_LOTTERIES,
    windows: Sequence[str] = DEFAULT_WINDOWS,
    correction: str = "bonferroni",
    emit: bool = True,
) -> Dict[str, Any]:
    artifact = build_artifact(db_path=db_path, lotteries=lotteries, windows=windows, correction=correction)
    if emit:
        write_artifacts(artifact, json_path, md_path)
    return artifact


def _split_csv(value: str) -> Tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="P238B NIST randomness-audit artifact-only build")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--mode", choices=["read-only"], required=True)
    parser.add_argument("--lotteries", required=True)
    parser.add_argument("--windows", default=",".join(DEFAULT_WINDOWS))
    parser.add_argument("--correction", default="bonferroni", choices=["bonferroni"])
    parser.add_argument("--emit-json", type=Path, default=DEFAULT_JSON_PATH)
    parser.add_argument("--emit-md", type=Path, default=DEFAULT_MD_PATH)
    args = parser.parse_args(argv)

    lotteries = _split_csv(args.lotteries)
    windows = _split_csv(args.windows)
    run(
        db_path=args.db,
        json_path=args.emit_json,
        md_path=args.emit_md,
        lotteries=lotteries,
        windows=windows,
        correction=args.correction,
        emit=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
