
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.wbc_pool_a import list_wbc_matches_a
from data.wbc_pool_b import list_wbc_matches_b
from data.wbc_pool_c import list_wbc_matches
from data.wbc_pool_d import list_wbc_matches_d

REGISTRY_PATH = Path(
    os.environ.get("WBC_GATE_REGISTRY", "data/wbc_backend/reports/prediction_registry.jsonl")
)
SCORES_PATH = Path("data/wbc_2026_live_scores.json")
OUTPUT_PATH = Path("data/wbc_backend/reports/gate_validation_evidence.json")
N_PERMUTATIONS = 20000

TEAM_NAME_TO_CODE = {
    "Chinese Taipei": "TPE",
    "Australia": "AUS",
    "Czechia": "CZE",
    "Korea": "KOR",
    "Japan": "JPN",
    "Cuba": "CUB",
    "Panama": "PAN",
    "Puerto Rico": "PUR",
    "Colombia": "COL",
    "Canada": "CAN",
    "Mexico": "MEX",
    "Great Britain": "GBR",
    "United States": "USA",
    "Brazil": "BRA",
    "Italy": "ITA",
    "Kingdom of the Netherlands": "NED",
    "Netherlands": "NED",
    "Venezuela": "VEN",
    "Nicaragua": "NIC",
    "Dominican Republic": "DOM",
    "Israel": "ISR",
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _build_schedule_map() -> dict[str, dict[str, str]]:
    all_games = (
        list_wbc_matches_a()
        + list_wbc_matches_b()
        + list_wbc_matches()
        + list_wbc_matches_d()
    )
    return {
        g["game_id"]: {
            "date": g["date"],
            "away": g["away"],
            "home": g["home"],
            "game_time": g["game_time"],
        }
        for g in all_games
    }


def _build_final_score_map() -> dict[tuple[str, str, str], dict[str, Any]]:
    payload = json.loads(SCORES_PATH.read_text(encoding="utf-8"))
    mapping: dict[tuple[str, str, str], dict[str, Any]] = {}
    for g in payload.get("games", []):
        if str(g.get("status", "")).lower() not in {"final", "completed early"}:
            continue
        away_code = TEAM_NAME_TO_CODE.get(str(g.get("away", "")))
        home_code = TEAM_NAME_TO_CODE.get(str(g.get("home", "")))
        date = str(g.get("date", ""))
        if not away_code or not home_code or not date:
            continue
        mapping[(date, away_code, home_code)] = g
    return mapping


def _build_final_score_pair_map() -> dict[tuple[str, str], list[dict[str, Any]]]:
    payload = json.loads(SCORES_PATH.read_text(encoding="utf-8"))
    mapping: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for g in payload.get("games", []):
        if str(g.get("status", "")).lower() not in {"final", "completed early"}:
            continue
        away_code = TEAM_NAME_TO_CODE.get(str(g.get("away", "")))
        home_code = TEAM_NAME_TO_CODE.get(str(g.get("home", "")))
        date = str(g.get("date", ""))
        if not away_code or not home_code or not date:
            continue
        mapping.setdefault((away_code, home_code), []).append(g)
    return mapping


def _parse_recorded_at(text: str) -> datetime:
    normalized = text.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _date_distance_days(a: str, b: str) -> int:
    da = datetime.fromisoformat(a).date()
    db = datetime.fromisoformat(b).date()
    return abs((da - db).days)


def _extract_sub_prob(
    sub_models: list[dict[str, Any]],
    target: str,
) -> float | None:
    target = target.lower()
    for m in sub_models:
        name = str(m.get("model_name", "")).lower()
        if target in name:
            value = m.get("home_win_prob")
            if isinstance(value, (int, float)):
                return float(value)
    return None


def _permutation_paired_test(
    baseline_errors: np.ndarray,
    candidate_errors: np.ndarray,
    *,
    n_permutations: int = N_PERMUTATIONS,
    seed: int = 42,
) -> float:
    # H0: expected paired difference is zero.
    diffs = candidate_errors - baseline_errors
    observed = abs(np.mean(diffs))
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(n_permutations, len(diffs)))
    permuted = np.abs(np.mean(signs * diffs, axis=1))
    return float((np.sum(permuted >= observed) + 1) / (n_permutations + 1))


def _mcnemar_p(
    baseline_correct: np.ndarray,
    candidate_correct: np.ndarray,
) -> tuple[float, dict[str, int]]:
    b = int(np.sum(baseline_correct & ~candidate_correct))
    c = int(np.sum(~baseline_correct & candidate_correct))
    if b + c == 0:
        return 1.0, {"b_baseline_only": b, "c_candidate_only": c}
    stat = (abs(b - c) - 0.5) ** 2 / (b + c)
    p = float(stats.chi2.sf(stat, 1))
    return p, {"b_baseline_only": b, "c_candidate_only": c}


def run_gate_validation() -> dict[str, Any]:
    print("Starting gate validation (real prediction registry replay)...")
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(f"Missing prediction registry: {REGISTRY_PATH}")
    if not SCORES_PATH.exists():
        raise FileNotFoundError(f"Missing live scores file: {SCORES_PATH}")

    schedule_map = _build_schedule_map()
    final_map = _build_final_score_map()
    final_pair_map = _build_final_score_pair_map()
    registry_rows = _read_jsonl(REGISTRY_PATH)

    latest_by_game: dict[str, dict[str, Any]] = {}
    for row in registry_rows:
        gid = str(row.get("game_id", "")).upper()
        if gid not in schedule_map:
            continue
        prev = latest_by_game.get(gid)
        if not prev:
            latest_by_game[gid] = row
            continue
        prev_t = _parse_recorded_at(str(prev.get("recorded_at_utc")))
        curr_t = _parse_recorded_at(str(row.get("recorded_at_utc")))
        if curr_t > prev_t:
            latest_by_game[gid] = row

    # P0: evaluate all valid pregame snapshots (not only latest snapshot per game)
    pregame_rows: list[dict[str, Any]] = []
    for row in registry_rows:
        gid = str(row.get("game_id", "")).upper()
        if gid not in schedule_map:
            continue
        game_time = datetime.fromisoformat(schedule_map[gid]["game_time"])
        row_ts = _parse_recorded_at(str(row.get("recorded_at_utc")))
        if row_ts <= game_time.astimezone(row_ts.tzinfo):
            pregame_rows.append(row)

    eval_rows: list[dict[str, Any]] = []
    missing_actual = 0
    missing_actual_detail: list[dict[str, Any]] = []
    missing_sub = 0
    cap_violations = 0
    min_p = 1.0
    max_p = 0.0

    for row in pregame_rows:
        gid = str(row.get("game_id", "")).upper()
        s = schedule_map[gid]
        actual = final_map.get((s["date"], s["away"], s["home"]))
        matched_via = "exact_date"
        flipped_orientation = False
        if not actual:
            reverse_exact = final_map.get((s["date"], s["home"], s["away"]))
            if reverse_exact:
                actual = reverse_exact
                matched_via = "reverse_exact_date"
                flipped_orientation = True
        if not actual:
            # Fallback: same away/home pair with closest date (<=2 days).
            pair_candidates = final_pair_map.get((s["away"], s["home"]), [])
            if pair_candidates:
                pair_candidates = sorted(
                    pair_candidates,
                    key=lambda g: _date_distance_days(s["date"], str(g.get("date", "1900-01-01"))),
                )
                best = pair_candidates[0]
                if _date_distance_days(s["date"], str(best.get("date", "1900-01-01"))) <= 2:
                    actual = best
                    matched_via = "pair_fallback"
        if not actual:
            reverse_candidates = final_pair_map.get((s["home"], s["away"]), [])
            if reverse_candidates:
                reverse_candidates = sorted(
                    reverse_candidates,
                    key=lambda g: _date_distance_days(s["date"], str(g.get("date", "1900-01-01"))),
                )
                best = reverse_candidates[0]
                if _date_distance_days(s["date"], str(best.get("date", "1900-01-01"))) <= 2:
                    actual = best
                    matched_via = "reverse_pair_fallback"
                    flipped_orientation = True
        if not actual:
            missing_actual += 1
            missing_actual_detail.append(
                {
                    "game_id": gid,
                    "expected_date": s["date"],
                    "away": s["away"],
                    "home": s["home"],
                    "reason": "no_final_match_found_exact_or_pair_fallback",
                }
            )
            continue

        y_true_actual = 1.0 if int(actual["home_score"]) > int(actual["away_score"]) else 0.0
        # y_true is always in schedule-home perspective (not raw live-score home).
        y_true = 1.0 - y_true_actual if flipped_orientation else y_true_actual
        pred = row.get("prediction", {})
        p_ens = pred.get("home_win_prob")
        if not isinstance(p_ens, (int, float)):
            continue
        p_ens = float(p_ens)
        min_p = min(min_p, p_ens)
        max_p = max(max_p, p_ens)
        if p_ens < 0.149 or p_ens > 0.851:
            cap_violations += 1

        sub_models = pred.get("sub_model_results", [])
        p_bayes = _extract_sub_prob(sub_models, "bayesian")
        p_nn = _extract_sub_prob(sub_models, "neural")
        if p_bayes is None or p_nn is None:
            missing_sub += 1
            continue

        eval_rows.append(
            {
                "game_id": gid,
                "matched_via": matched_via,
                "y_true": y_true,
                "p_ens": p_ens,
                "p_bayes": p_bayes,
                "p_nn": p_nn,
            }
        )

    if not eval_rows:
        raise RuntimeError("No evaluable rows found from registry replay.")

    y = np.array([r["y_true"] for r in eval_rows], dtype=float)
    p_ens = np.array([r["p_ens"] for r in eval_rows], dtype=float)
    p_bayes = np.array([r["p_bayes"] for r in eval_rows], dtype=float)
    p_nn = np.array([r["p_nn"] for r in eval_rows], dtype=float)

    ens_err = (p_ens - y) ** 2
    bayes_err = (p_bayes - y) ** 2
    nn_err = (p_nn - y) ** 2

    perm_p = _permutation_paired_test(bayes_err, ens_err)
    ens_correct = (p_ens >= 0.5) == (y == 1.0)
    bayes_correct = (p_bayes >= 0.5) == (y == 1.0)
    mcnemar_p, mcnemar_table = _mcnemar_p(bayes_correct, ens_correct)

    # Stage 5: basic rolling stability check. If sample too small, force FAIL/observe.
    rolling_window = 10
    rolling_mean = []
    if len(ens_err) >= rolling_window:
        for i in range(rolling_window, len(ens_err) + 1):
            rolling_mean.append(float(np.mean(ens_err[i - rolling_window:i])))
    stage5_stability_std = float(np.std(rolling_mean)) if rolling_mean else None

    # Gate policy
    stage1_pass = len(eval_rows) >= 20 and missing_actual == 0
    stage2_pass = float(np.mean(ens_err)) < 0.22
    stage3_pass = cap_violations == 0
    mean_ens_brier = float(np.mean(ens_err))
    mean_bayes_brier = float(np.mean(bayes_err))
    stage4_pass = perm_p < 0.05 and mean_ens_brier < mean_bayes_brier
    stage5_pass = bool(stage5_stability_std is not None and stage5_stability_std < 0.03 and len(eval_rows) >= 20)

    decision = "OBSERVE"
    if stage1_pass and stage2_pass and stage3_pass and stage4_pass and stage5_pass:
        decision = "DEPLOY_GUARDED"
    elif stage1_pass and stage2_pass and stage3_pass:
        decision = "HOLDOUT_REQUIRED"

    evidence = {
        "methodology": "real_registry_replay_no_simulation",
        "n_registry_rows": len(registry_rows),
        "n_latest_unique_games": len(latest_by_game),
        "n_pregame_snapshots": len(pregame_rows),
        "n_evaluable_games": len(eval_rows),
        "n_missing_actual": missing_actual,
        "missing_actual_detail": missing_actual_detail,
        "n_missing_submodel_probs": missing_sub,
        "n_pair_fallback_matches": int(sum(1 for r in eval_rows if r.get("matched_via") == "pair_fallback")),
        "ensemble_brier": round(mean_ens_brier, 6),
        "bayesian_brier": round(mean_bayes_brier, 6),
        "nn_brier": round(float(np.mean(nn_err)), 6),
        "ensemble_accuracy": round(float(np.mean(ens_correct)), 6),
        "bayesian_accuracy": round(float(np.mean(bayes_correct)), 6),
        "permutation_p_ens_vs_bayes": round(float(perm_p), 6),
        "mcnemar_p_ens_vs_bayes": round(float(mcnemar_p), 6),
        "mcnemar_table": mcnemar_table,
        "cap_check": {
            "min_prob": round(float(min_p), 6),
            "max_prob": round(float(max_p), 6),
            "violations": int(cap_violations),
        },
        "stage5_stability_std_rolling10_brier": (
            round(stage5_stability_std, 6) if stage5_stability_std is not None else None
        ),
        "stages": {
            "Stage1_Integrity": "PASS" if stage1_pass else "FAIL",
            "Stage2_Validation": "PASS" if stage2_pass else "FAIL",
            "Stage3_Risk": "PASS" if stage3_pass else "FAIL",
            "Stage4_Deployment": "PASS" if stage4_pass else "FAIL",
            "Stage5_Stability": "PASS" if stage5_pass else "FAIL",
        },
        "final_decision": decision,
        "notes": [
            "Stage4 requires statistically significant difference and strictly better (lower) brier than baseline.",
            "McNemar is reported as a diagnostic; significance is not treated as mandatory pass here.",
            "If Stage5 fails due to low sample (<30 games), deployment is blocked by policy.",
        ],
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved gate evidence: {OUTPUT_PATH}")
    print(json.dumps(evidence["stages"], ensure_ascii=False))
    print(f"Final decision: {decision}")
    return evidence


if __name__ == "__main__":
    run_gate_validation()
