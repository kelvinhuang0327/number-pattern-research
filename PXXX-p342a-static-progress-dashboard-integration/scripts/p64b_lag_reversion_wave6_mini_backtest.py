#!/usr/bin/env python3
"""
P64b: lag_reversion_2bet Wave 6 Mini-Backtest
==============================================
Runs in-memory mini-backtest for lag_reversion_2bet at 3 windows (150/500/1500).
Evidence gate: M3+/draw >= 3.87% (theoretical baseline) in at least one window.
Decision: BUILD_ADAPTER_P64C or DEFER_ADAPTER_BUILD.

Algorithm (mirrors tools/power_lag_reversion.py):
  score(n) = current_lag(n) / (median_interval(n) + 0.1)
  Bet-0: top 6 numbers by overdue score (deterministic, no random.seed)

HARD RULES:
  - NO writes to production DB (43960 rows immutable)
  - NO temp DB — in-memory computation only
  - Strictly causal: history = all draws BEFORE target draw
  - Evidence gate determines conditional adapter build (P64c)

Outputs:
  outputs/replay/p64b_lag_reversion_wave6_mini_backtest_20260525.json
  docs/replay/p64b_lag_reversion_wave6_mini_backtest_20260525.md
"""
from __future__ import annotations

import json
import logging
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import List


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


REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

PROD_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUTPUT_DIR = REPO_ROOT / "outputs" / "replay"
OUTPUT_JSON = OUTPUT_DIR / "p64b_lag_reversion_wave6_mini_backtest_20260525.json"
OUTPUT_DOC = REPO_ROOT / "docs" / "replay" / "p64b_lag_reversion_wave6_mini_backtest_20260525.md"

EXPECTED_PROD_ROWS = 43960
BACKTEST_WINDOWS = [150, 500, 1500]
EVIDENCE_GATE_M3PLUS_PCT = 3.87  # theoretical baseline for POWER_LOTTO pick-6

_POOL = 38          # first-zone pool 1..38
_PICK = 6           # numbers per bet
_SPECIAL_POOL = 8   # second-zone pool 1..8
_LAG_WINDOW = 500   # interval calc window (mirrors tools/power_lag_reversion.py)
MIN_HISTORY = 10    # minimum draws before prediction is attempted

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RUN_ID = "p64b_lag_reversion_wave6_mini_backtest_20260525"
MARKER = "P64B_LAG_REVERSION_WAVE6_MINI_BACKTEST_20260525"


# ─── Production guard ─────────────────────────────────────────────────────────

def _assert_prod_rows(expected: int = EXPECTED_PROD_ROWS, phase: str = "") -> int:
    """Assert production replay row count equals expected. Returns count."""
    _p291u_db_path = _p291u_resolve_db_path()
    conn = _p291u_connect_resolved(_p291u_db_path)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()
    if count != expected:
        raise RuntimeError(
            f"PROD INVARIANT VIOLATED [{phase}]: expected {expected}, got {count}"
        )
    logger.info(f"[{phase}] Production rows: {count} \u2713")
    return count


# ─── Draw loader ──────────────────────────────────────────────────────────────

def _load_powerlotto_draws() -> List[dict]:
    """Load all POWER_LOTTO draws sorted ASC by draw number. Read-only."""
    _p291u_db_path = _p291u_resolve_db_path()
    conn = _p291u_connect_resolved(_p291u_db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT draw, date, numbers, special FROM draws "
            "WHERE lottery_type = 'POWER_LOTTO' "
            "ORDER BY CAST(draw AS INTEGER) ASC"
        ).fetchall()
    finally:
        conn.close()

    draws = []
    for row in rows:
        nums = (
            json.loads(row["numbers"])
            if isinstance(row["numbers"], str)
            else row["numbers"]
        )
        draws.append({
            "draw": row["draw"],
            "date": row["date"],
            "numbers": [int(n) for n in nums],
            "special": int(row["special"]) if row["special"] is not None else None,
        })
    return draws


# ─── Prediction (lag-reversion median interval overdue) ───────────────────────

def predict_lag_reversion_bet0(
    history: List[dict],
    lag_window: int = _LAG_WINDOW,
) -> List[int]:
    """
    Bet-0 of lag_reversion_2bet.

    Per-ball median interval overdue ranking:
      score(n) = current_lag(n) / (median_interval(n) + 0.1)
    Bet-0: top 6 by score. Tie-break: lower number preferred.

    Mirrors tools/power_lag_reversion.py::lag_reversion_predict() exactly.
    Deterministic — no random.seed().
    """
    h_slice = history[-lag_window:] if len(history) >= lag_window else history
    n_draws = len(h_slice)
    if n_draws == 0:
        return list(range(1, _PICK + 1))

    last_seen: dict = {n: -1 for n in range(1, _POOL + 1)}
    intervals: dict = {n: [] for n in range(1, _POOL + 1)}

    for idx, draw in enumerate(h_slice):
        for num in draw["numbers"]:
            if 1 <= num <= _POOL:
                if last_seen[num] != -1:
                    intervals[num].append(idx - last_seen[num])
                last_seen[num] = idx

    expected_interval = _POOL / _PICK  # 38/6 ≈ 6.333 — fallback for unseen numbers
    scores: dict = {}
    for n in range(1, _POOL + 1):
        med_int = median(intervals[n]) if intervals[n] else expected_interval
        current_lag = n_draws - last_seen[n]  # n_draws if never seen
        scores[n] = current_lag / (med_int + 0.1)

    # Sort by score DESC, number ASC as stable tie-breaker
    sorted_nums = sorted(range(1, _POOL + 1), key=lambda n: (-scores[n], n))
    return sorted(sorted_nums[:_PICK])


def _special_predict(history: List[dict], window: int = 100) -> int:
    """
    Special number prediction (1..8) via frequency mean-reversion.
    Identical to p56_wave5_powerlotto_adapters._special_predict().
    """
    recent = history[-window:] if len(history) >= window else history
    if not recent:
        return 1
    freq: Counter = Counter()
    for d in recent:
        sp = d.get("special")
        if sp is not None and 1 <= sp <= _SPECIAL_POOL:
            freq[sp] += 1
    w = len(recent)
    expected = w / _SPECIAL_POOL
    return min(range(1, _SPECIAL_POOL + 1), key=lambda n: abs(freq.get(n, 0) - expected))


# ─── Window backtest ──────────────────────────────────────────────────────────

def _run_window_backtest(all_draws: List[dict], window: int) -> dict:
    """
    In-memory mini-backtest for the last `window` POWER_LOTTO draws.
    Strictly causal: for target at index j, history = all_draws[:j].
    Returns metrics dict.
    """
    total = len(all_draws)
    actual_window = min(window, total)
    start_idx = total - actual_window

    hit_dist: dict = {k: 0 for k in range(_PICK + 1)}
    m3plus_count = 0
    special_hit_count = 0
    predicted_count = 0
    skipped_count = 0

    for offset, target in enumerate(all_draws[start_idx:]):
        target_idx = start_idx + offset
        if target_idx < MIN_HISTORY:
            skipped_count += 1
            continue

        history = all_draws[:target_idx]  # strictly causal
        try:
            pred_nums = predict_lag_reversion_bet0(history)
            pred_spec = _special_predict(history)
        except Exception as exc:
            logger.warning(f"Prediction error draw {target.get('draw')}: {exc}")
            skipped_count += 1
            continue

        actual_nums = set(target["numbers"])
        hit_count = len(set(pred_nums) & actual_nums)
        special_hit = 1 if pred_spec == target.get("special") else 0

        hit_dist[hit_count] = hit_dist.get(hit_count, 0) + 1
        if hit_count >= 3:
            m3plus_count += 1
        special_hit_count += special_hit
        predicted_count += 1

    if predicted_count == 0:
        m3plus_rate = special_hit_rate = avg_hit = 0.0
    else:
        m3plus_rate = round(100.0 * m3plus_count / predicted_count, 4)
        special_hit_rate = round(100.0 * special_hit_count / predicted_count, 4)
        avg_hit = round(sum(k * v for k, v in hit_dist.items()) / predicted_count, 4)

    return {
        "window": window,
        "actual_window": actual_window,
        "predicted_count": predicted_count,
        "skipped_count": skipped_count,
        "hit_distribution": hit_dist,
        "m3plus_count": m3plus_count,
        "m3plus_rate_pct": m3plus_rate,
        "theoretical_baseline_pct": EVIDENCE_GATE_M3PLUS_PCT,
        "vs_baseline_pp": round(m3plus_rate - EVIDENCE_GATE_M3PLUS_PCT, 4),
        "special_hit_count": special_hit_count,
        "special_hit_rate_pct": special_hit_rate,
        "avg_hit_count": avg_hit,
        "gate_pass": m3plus_rate >= EVIDENCE_GATE_M3PLUS_PCT,
    }


# ─── Evidence gate ────────────────────────────────────────────────────────────

def _decide_adapter(window_results: dict) -> dict:
    """
    Evidence gate: M3+ >= 3.87% in AT LEAST ONE window.
    Returns: gate decision + adapter build decision.
    """
    gate_pass_windows = [
        r["window"] for r in window_results.values() if r["gate_pass"]
    ]
    gate_passed = len(gate_pass_windows) > 0

    best = max(window_results.values(), key=lambda r: r["m3plus_rate_pct"])

    if gate_passed:
        rationale = (
            f"M3+={best['m3plus_rate_pct']:.2f}% >= {EVIDENCE_GATE_M3PLUS_PCT}% "
            f"(baseline) in window(s) {gate_pass_windows}. Adapter build authorised."
        )
        adapter_decision = "BUILD_ADAPTER_P64C"
    else:
        rationale = (
            f"M3+ < {EVIDENCE_GATE_M3PLUS_PCT}% in all windows. "
            f"Best: {best['m3plus_rate_pct']:.2f}% in window-{best['window']} "
            f"({best['vs_baseline_pp']:+.2f}pp). Adapter build deferred."
        )
        adapter_decision = "DEFER_ADAPTER_BUILD"

    return {
        "threshold_m3plus_pct": EVIDENCE_GATE_M3PLUS_PCT,
        "gate_passed": gate_passed,
        "gate_pass_windows": gate_pass_windows,
        "best_window": best["window"],
        "best_m3plus_pct": best["m3plus_rate_pct"],
        "best_vs_baseline_pp": best["vs_baseline_pp"],
        "adapter_decision": adapter_decision,
        "rationale": rationale,
    }


# ─── Doc generator ────────────────────────────────────────────────────────────

def _write_doc(output: dict) -> None:
    """Write markdown report doc."""
    ev = output["evidence_gate"]
    wr = output["window_results"]
    gate_str = "✅ GATE PASS" if ev["gate_passed"] else "❌ GATE FAIL"
    decision = ev["adapter_decision"]

    lines = [
        f"# P64b: lag_reversion_2bet Wave 6 Mini-Backtest",
        f"",
        f"**Classification**: `{output['classification']}`",
        f"**Marker**: `{output['marker']}`",
        f"**Generated**: {output['generated_at']}",
        f"",
        f"---",
        f"",
        f"## Executive Summary",
        f"",
        f"Mini-backtest for `lag_reversion_2bet` (Wave 6 candidate, rank 2, score 80/100).",
        f"Algorithm: per-ball median interval overdue ranking.",
        f"",
        f"| Evidence Gate | Result |",
        f"|---|---|",
        f"| Threshold M3+ | {EVIDENCE_GATE_M3PLUS_PCT}% |",
        f"| Gate Result | {gate_str} |",
        f"| Best M3+ | {ev['best_m3plus_pct']:.2f}% (window-{ev['best_window']}) |",
        f"| Best vs Baseline | {ev['best_vs_baseline_pp']:+.2f}pp |",
        f"| Adapter Decision | `{decision}` |",
        f"",
        f"---",
        f"",
        f"## Algorithm",
        f"",
        f"```",
        f"score(n) = current_lag(n) / (median_interval(n) + 0.1)",
        f"Bet-0: top 6 numbers by score",
        f"Lag window: {_LAG_WINDOW} draws (mirrors tools/power_lag_reversion.py)",
        f"Special: frequency mean-reversion over 100 draws",
        f"```",
        f"",
        f"- **Source model**: `lottery_api/models/lag_reversion.py`",
        f"- **Source tool**: `tools/power_lag_reversion.py`",
        f"- **Deterministic**: Yes (no random.seed)",
        f"- **Pool**: 1–38 (first zone), pick 6",
        f"- **Special pool**: 1–8",
        f"",
        f"---",
        f"",
        f"## Window Results",
        f"",
        f"| Window | Predicted | M3+ Count | M3+ Rate | Baseline | vs Baseline | Special Hit | Gate |",
        f"|---|---|---|---|---|---|---|---|",
    ]

    for w_str in ["150", "500", "1500"]:
        r = wr[w_str]
        gate_icon = "✅" if r["gate_pass"] else "❌"
        lines.append(
            f"| {r['window']:>6} | {r['predicted_count']:>9} "
            f"| {r['m3plus_count']:>9} | {r['m3plus_rate_pct']:.2f}% "
            f"| {EVIDENCE_GATE_M3PLUS_PCT:.2f}% | {r['vs_baseline_pp']:+.2f}pp "
            f"| {r['special_hit_rate_pct']:.2f}% | {gate_icon} |"
        )

    lines += [
        f"",
        f"### Hit Distributions",
        f"",
    ]

    for w_str in ["150", "500", "1500"]:
        r = wr[w_str]
        dist = r["hit_distribution"]
        lines.append(f"**Window {r['window']}** (n={r['predicted_count']}):")
        lines.append(f"")
        lines.append(f"| Hits | Count | % |")
        lines.append(f"|---|---|---|")
        for k in range(_PICK + 1):
            cnt = dist.get(k, 0)
            pct = 100.0 * cnt / r["predicted_count"] if r["predicted_count"] > 0 else 0.0
            lines.append(f"| {k} | {cnt} | {pct:.2f}% |")
        lines.append(f"")

    lines += [
        f"---",
        f"",
        f"## Evidence Gate Decision",
        f"",
        f"**Threshold**: M3+ >= {EVIDENCE_GATE_M3PLUS_PCT}% in at least one window",
        f"",
        f"**Result**: {gate_str}",
        f"",
        f"**Rationale**: {ev['rationale']}",
        f"",
        f"**Adapter Decision**: `{decision}`",
        f"",
    ]

    if ev["gate_passed"]:
        lines += [
            f"> Proceed to **P64c**: build `lag_reversion_2bet` Wave 6 adapter.",
            f"",
        ]
    else:
        lines += [
            f"> Adapter build deferred. Consider re-testing after parameter tuning or",
            f"> proceed to P64c (zonal_entropy_2bet determinism fix).",
            f"",
        ]

    lines += [
        f"---",
        f"",
        f"## Governance",
        f"",
        f"| Check | Value |",
        f"|---|---|",
        f"| DB writes | `false` |",
        f"| Temp DB | None (in-memory only) |",
        f"| Production rows before | {output['governance']['production_rows_before']} |",
        f"| Production rows after | {output['governance']['production_rows_after']} |",
        f"| Drift guard | Not run (no DB writes) |",
        f"",
        f"---",
        f"",
        f"## Artifacts",
        f"",
        f"| Artifact | Path |",
        f"|---|---|",
        f"| Script | `scripts/p64b_lag_reversion_wave6_mini_backtest.py` |",
        f"| JSON output | `outputs/replay/p64b_lag_reversion_wave6_mini_backtest_20260525.json` |",
        f"| This doc | `docs/replay/p64b_lag_reversion_wave6_mini_backtest_20260525.md` |",
        f"| Tests | `tests/test_p64b_lag_reversion_wave6_mini_backtest.py` |",
        f"",
        f"---",
        f"",
        f"## Sequencing",
        f"",
        f"| Task | Description | Status |",
        f"|---|---|---|",
        f"| P64a | cold_complement_2bet dry-run rehearsal | ✅ COMPLETE |",
        f"| **P64b** | **lag_reversion_2bet mini-backtest** | **THIS TASK** |",
        f"| P64c | Adapter build (conditional on gate) | {'Authorised' if ev['gate_passed'] else 'Deferred'} |",
        f"",
        f"**Preceding task**: P64a (commit `80611f3`)",
        f"**Next task**: {output['next_task']}",
        f"**Base commit**: `{output['base_commit']}`",
        f"",
        f"---",
        f"",
        f"*Classification: `{output['classification']}`*",
        f"*NOT staged: no DB changes, no production writes*",
    ]

    OUTPUT_DOC.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_DOC.write_text("\n".join(lines))
    logger.info(f"Doc: {OUTPUT_DOC}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> dict:
    logger.info("=" * 60)
    logger.info("P64b: lag_reversion_2bet Wave 6 Mini-Backtest")
    logger.info("=" * 60)

    rows_before = _assert_prod_rows(phase="pre")

    all_draws = _load_powerlotto_draws()
    logger.info(f"Loaded {len(all_draws)} POWER_LOTTO draws")

    window_results: dict = {}
    for w in BACKTEST_WINDOWS:
        result = _run_window_backtest(all_draws, w)
        window_results[str(w)] = result
        gate_str = "\u2713 GATE PASS" if result["gate_pass"] else "\u2717 GATE FAIL"
        logger.info(
            f"Window {w:>4}: M3+={result['m3plus_rate_pct']:.2f}% "
            f"(vs {EVIDENCE_GATE_M3PLUS_PCT}%, {result['vs_baseline_pp']:+.2f}pp) "
            f"special={result['special_hit_rate_pct']:.2f}% {gate_str}"
        )

    evidence = _decide_adapter(window_results)
    rows_after = _assert_prod_rows(phase="post")

    classification = (
        "P64B_LAG_REVERSION_WAVE6_MINI_BACKTEST_GATE_PASS"
        if evidence["gate_passed"]
        else "P64B_LAG_REVERSION_WAVE6_MINI_BACKTEST_GATE_FAIL"
    )

    output = {
        "schema_version": "1.0",
        "task_id": "P64b",
        "strategy_id": "lag_reversion_2bet",
        "run_id": RUN_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "marker": MARKER,
        "governance": {
            "db_writes": False,
            "online_promotions": False,
            "champion_replacement": False,
            "registry_mutation": False,
            "production_apply": False,
            "production_rows_before": rows_before,
            "production_rows_after": rows_after,
            "temp_db": None,
        },
        "algorithm": {
            "name": "lag_reversion_median_interval_overdue",
            "lag_window": _LAG_WINDOW,
            "mechanism": (
                "Per-ball median interval overdue ranking — "
                "score = current_lag / (median_interval + 0.1)"
            ),
            "bet0_selection": "Top 6 numbers by overdue score",
            "special_method": "frequency_mean_reversion_100w",
            "deterministic": True,
            "no_random_seed": True,
            "source_model": "lottery_api/models/lag_reversion.py",
            "source_tool": "tools/power_lag_reversion.py",
            "pool": _POOL,
            "pick": _PICK,
            "special_pool": _SPECIAL_POOL,
        },
        "backtest_config": {
            "windows": BACKTEST_WINDOWS,
            "evidence_gate_threshold_m3plus_pct": EVIDENCE_GATE_M3PLUS_PCT,
            "min_history": MIN_HISTORY,
            "in_memory_only": True,
            "no_db_writes": True,
        },
        "window_results": window_results,
        "evidence_gate": evidence,
        "preceding_task": "P64a",
        "next_task": (
            "P64c (lag_reversion_2bet adapter build)"
            if evidence["gate_passed"]
            else "P64c (zonal_entropy_2bet determinism fix or defer)"
        ),
        "base_commit": "80611f3",
        "classification": classification,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2)
    logger.info(f"JSON: {OUTPUT_JSON}")

    _write_doc(output)

    logger.info("=" * 60)
    logger.info(f"FINAL CLASSIFICATION: {classification}")
    logger.info(
        f"Best M3+: {evidence['best_m3plus_pct']:.2f}% in window-{evidence['best_window']}"
    )
    logger.info(f"Adapter decision: {evidence['adapter_decision']}")
    logger.info("=" * 60)

    return output


if __name__ == "__main__":
    main()
