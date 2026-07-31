from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.wbc_pool_a import list_wbc_matches_a
from data.wbc_pool_b import list_wbc_matches_b
from data.wbc_pool_c import list_wbc_matches
from data.wbc_pool_d import list_wbc_matches_d

REPLAY_PATH = Path("data/wbc_backend/reports/prediction_registry_replay.jsonl")
SCORES_PATH = Path("data/wbc_2026_live_scores.json")
OUT_PATH = Path("data/wbc_backend/reports/gate_blend_search.json")

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


def _date_dist_days(a: str, b: str) -> int:
    da = datetime.fromisoformat(a).date()
    db = datetime.fromisoformat(b).date()
    return abs((da - db).days)


def _paired_perm_p(diff: np.ndarray, *, n: int = 5000, seed: int = 42) -> float:
    obs = abs(float(np.mean(diff)))
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(n, len(diff)))
    perm = np.abs(np.mean(signs * diff, axis=1))
    return float((np.sum(perm >= obs) + 1) / (n + 1))


def main() -> int:
    replay_rows = [
        json.loads(line)
        for line in REPLAY_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    schedule_rows = list_wbc_matches_a() + list_wbc_matches_b() + list_wbc_matches() + list_wbc_matches_d()
    schedule = {g["game_id"]: {"date": g["date"], "away": g["away"], "home": g["home"]} for g in schedule_rows}

    scores = json.loads(SCORES_PATH.read_text(encoding="utf-8"))
    final: dict[tuple[str, str, str], float] = {}
    for g in scores.get("games", []):
        if str(g.get("status", "")).lower() not in {"final", "completed early"}:
            continue
        away = TEAM_NAME_TO_CODE.get(str(g.get("away", "")))
        home = TEAM_NAME_TO_CODE.get(str(g.get("home", "")))
        if not away or not home:
            continue
        final[(str(g.get("date", "")), away, home)] = 1.0 if int(g["home_score"]) > int(g["away_score"]) else 0.0

    y: list[float] = []
    p_ens: list[float] = []
    p_bayes: list[float] = []
    unresolved: list[str] = []

    for row in replay_rows:
        gid = str(row.get("game_id", "")).upper()
        s = schedule.get(gid)
        if not s:
            continue
        key = (s["date"], s["away"], s["home"])
        target = final.get(key)
        if target is None:
            rev = final.get((s["date"], s["home"], s["away"]))
            if rev is not None:
                target = 1.0 - rev
        if target is None:
            pair = [(k, v) for k, v in final.items() if k[1] == s["away"] and k[2] == s["home"]]
            if pair:
                k, v = sorted(pair, key=lambda item: _date_dist_days(s["date"], item[0][0]))[0]
                if _date_dist_days(s["date"], k[0]) <= 2:
                    target = v
        if target is None:
            rev_pair = [(k, v) for k, v in final.items() if k[1] == s["home"] and k[2] == s["away"]]
            if rev_pair:
                k, v = sorted(rev_pair, key=lambda item: _date_dist_days(s["date"], item[0][0]))[0]
                if _date_dist_days(s["date"], k[0]) <= 2:
                    target = 1.0 - v
        if target is None:
            unresolved.append(gid)
            continue

        bayes_candidates = [
            float(m.get("home_win_prob"))
            for m in row.get("prediction", {}).get("sub_model_results", [])
            if "bayesian" in str(m.get("model_name", "")).lower()
        ]
        if not bayes_candidates:
            unresolved.append(gid)
            continue

        y.append(float(target))
        p_ens.append(float(row["prediction"]["home_win_prob"]))
        p_bayes.append(float(bayes_candidates[0]))

    y_arr = np.array(y, dtype=float)
    ens_arr = np.array(p_ens, dtype=float)
    bayes_arr = np.array(p_bayes, dtype=float)

    candidates = []
    for lam in np.linspace(0.0, 1.0, 41):
        combo = np.clip((lam * ens_arr) + ((1.0 - lam) * bayes_arr), 0.15, 0.85)
        combo_err = (combo - y_arr) ** 2
        bayes_err = (bayes_arr - y_arr) ** 2
        combo_brier = float(np.mean(combo_err))
        bayes_brier = float(np.mean(bayes_err))
        p_value = _paired_perm_p(combo_err - bayes_err)
        rolling = [float(np.mean(combo_err[i - 10:i])) for i in range(10, len(combo_err) + 1)]
        stability_std = float(np.std(rolling)) if rolling else None
        stage4_pass = bool(p_value < 0.05 and combo_brier < bayes_brier)
        stage5_pass = bool(stability_std is not None and stability_std < 0.03)
        candidates.append(
            {
                "lambda_ensemble": round(float(lam), 3),
                "brier": round(combo_brier, 6),
                "bayesian_brier": round(bayes_brier, 6),
                "perm_p": round(p_value, 6),
                "stability_std": round(stability_std, 6) if stability_std is not None else None,
                "stage4_pass": stage4_pass,
                "stage5_pass": stage5_pass,
            }
        )

    best = min(candidates, key=lambda r: r["brier"])
    output = {
        "n_samples": int(len(y_arr)),
        "unresolved_games": unresolved,
        "best_by_brier": best,
        "any_stage4_pass": any(c["stage4_pass"] for c in candidates),
        "any_stage5_pass": any(c["stage5_pass"] for c in candidates),
        "candidates": candidates,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved blend search: {OUT_PATH}")
    print(json.dumps(output["best_by_brier"], ensure_ascii=False))
    print(json.dumps({"any_stage4_pass": output["any_stage4_pass"], "any_stage5_pass": output["any_stage5_pass"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
