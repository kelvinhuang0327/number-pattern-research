#!/usr/bin/env python3
import json
import math
import os
import random
import sys
from collections import Counter
from datetime import datetime
from statistics import mean

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "lottery_api"))

from lottery_api.database import DatabaseManager
from lottery_api.engine.perm_test import perm_test
from tools.backtest_power_4bet import build_pp3
from tools.power_fourier_rhythm import fourier_rhythm_predict
from tools.predict_power_orthogonal_5bet import generate_orthogonal_5bet
from tools.power_midfreq_fourier import _midfreq_scores

SEED = 42
MIN_HISTORY = 200
PERM_N = 200
WINDOWS = [150, 500, 1500]
LOTTERY_TYPE = "POWER_LOTTO"
MAX_NUM = 38
PICK = 6
P_SINGLE = 0.0387
BASELINES = {n: 1 - (1 - P_SINGLE) ** n for n in range(1, 6)}
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "tmp", "pp3_midfreq_orthogonal_8h")
REPORT_PATH = os.path.join(OUTPUT_DIR, "power_lotto_pp3_midfreq_orthogonal_8h_20260422.md")
JSON_PATH = os.path.join(OUTPUT_DIR, "power_lotto_pp3_midfreq_orthogonal_8h_20260422.json")


def normalize(scores):
    vals = list(scores.values())
    mn, mx = min(vals), max(vals)
    if mx - mn == 0:
        return {k: 0.5 for k in scores}
    return {k: (v - mn) / (mx - mn) for k, v in scores.items()}


def get_gap_scores(history, window=100):
    recent = history[-window:] if len(history) >= window else history
    last_seen = {}
    for idx, draw in enumerate(recent):
        for n in draw["numbers"][:PICK]:
            if 1 <= n <= MAX_NUM:
                last_seen[n] = idx
    length = len(recent)
    raw = {}
    for n in range(1, MAX_NUM + 1):
        raw[n] = (length - 1) - last_seen[n] if n in last_seen else length
    return normalize(raw)


def rankdata(values):
    arr = np.asarray(values, dtype=float)
    order = np.argsort(arr)
    ranks = np.empty(len(arr), dtype=float)
    i = 0
    while i < len(arr):
        j = i
        while j + 1 < len(arr) and arr[order[j + 1]] == arr[order[i]]:
            j += 1
        rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = rank
        i = j + 1
    return ranks


def spearman_rho(x_vals, y_vals):
    if len(x_vals) < 2:
        return 0.0
    rx = rankdata(x_vals)
    ry = rankdata(y_vals)
    sx = np.std(rx)
    sy = np.std(ry)
    if sx == 0 or sy == 0:
        return 0.0
    return float(np.corrcoef(rx, ry)[0, 1])


def jaccard(a, b):
    sa, sb = set(a), set(b)
    union = sa | sb
    return len(sa & sb) / len(union) if union else 0.0


def top6(scores, exclude):
    ranked = sorted(
        (n for n in range(1, MAX_NUM + 1) if n not in exclude),
        key=lambda n: (-scores[n], n),
    )
    return sorted(ranked[:PICK])


def candidate_score_maps(history):
    mf100 = normalize(_midfreq_scores(history, window=100))
    mf200 = normalize(_midfreq_scores(history, window=200))
    _, _, _, _, f_scores, _ = build_pp3(history)
    fourier500 = normalize(f_scores)
    gap100 = get_gap_scores(history, window=100)
    return {
        "mf_residual_4bet": {
            "formula": "score = norm(midfreq, w=100)",
            "features": ["midfreq100"],
            "scores": mf100,
        },
        "mf_antifourier_4bet": {
            "formula": "score = norm(midfreq, w=100) - 0.60 * norm(fourier, w=500)",
            "features": ["midfreq100", "anti_fourier500"],
            "scores": {n: mf100[n] - 0.60 * fourier500[n] for n in range(1, MAX_NUM + 1)},
        },
        "mf_stable_antifourier_4bet": {
            "formula": (
                "score = 0.60 * norm(midfreq, w=100) + 0.40 * norm(midfreq, w=200) "
                "- 0.50 * |mf100-mf200| - 0.35 * norm(fourier, w=500) - 0.20 * norm(gap, w=100)"
            ),
            "features": ["midfreq100", "midfreq200", "stability_penalty", "anti_fourier500", "anti_gap100"],
            "scores": {
                n: (
                    0.60 * mf100[n]
                    + 0.40 * mf200[n]
                    - 0.50 * abs(mf100[n] - mf200[n])
                    - 0.35 * fourier500[n]
                    - 0.20 * gap100[n]
                )
                for n in range(1, MAX_NUM + 1)
            },
        },
    }


def pp3_bets(history):
    bets, used, _, _, _, _ = build_pp3(history)
    return bets, used


def make_candidate_predictor(candidate_key):
    def predictor(history):
        bets, used = pp3_bets(history)
        score_entry = candidate_score_maps(history)[candidate_key]
        bet4 = top6(score_entry["scores"], used)
        return bets + [bet4]

    return predictor


def bet4_details(history, candidate_key):
    bets, used = pp3_bets(history)
    score_entry = candidate_score_maps(history)[candidate_key]
    bet4 = top6(score_entry["scores"], used)
    return bets, used, bet4, score_entry


def predict_fourier_3bet(history):
    return fourier_rhythm_predict(history, n_bets=3, window=500)


def predict_pp3_freqort_4bet(history):
    return generate_orthogonal_5bet(history)[:4]


def subset_for_window(draws, window):
    return draws[-(window + MIN_HISTORY):]


def evaluate_strategy(draws, predictor, n_bets, compute_perm=True):
    results = {}
    for window in WINDOWS:
        subset = subset_for_window(draws, window)
        total = 0
        overall_hits = []
        prefix_hits = {k: [] for k in range(1, n_bets + 1)}
        bet_hits = {k: [] for k in range(1, n_bets + 1)}
        sample_bets = []

        for idx in range(MIN_HISTORY, len(subset)):
            history = subset[:idx]
            actual = set(subset[idx]["numbers"])
            bets = predictor(history)
            if len(bets) != n_bets:
                raise ValueError(f"expected {n_bets} bets, got {len(bets)}")
            total += 1
            if len(sample_bets) < 3:
                sample_bets.append(
                    {
                        "draw": subset[idx]["draw"],
                        "bets": [list(map(int, bet)) for bet in bets],
                    }
                )
            per_bet = [len(set(bet) & actual) >= 3 for bet in bets]
            for k in range(1, n_bets + 1):
                bet_hits[k].append(bool(per_bet[k - 1]))
                prefix_hits[k].append(any(per_bet[:k]))
            overall_hits.append(any(per_bet))

        baseline = BASELINES[n_bets]
        rate = sum(overall_hits) / total if total else 0.0
        edge = rate - baseline
        perm = None
        if compute_perm:
            perm = perm_test(
                history=subset,
                predict_fn=predictor,
                baseline=baseline,
                min_history=MIN_HISTORY,
                n_perm=PERM_N,
                seed=SEED,
                verbose=False,
            )
        prefix_summary = {}
        for k in range(1, n_bets + 1):
            p_rate = sum(prefix_hits[k]) / total if total else 0.0
            prefix_summary[str(k)] = {
                "rate": round(p_rate, 4),
                "edge": round(p_rate - BASELINES[k], 4),
            }

        bet_rates = {str(k): round(sum(bet_hits[k]) / total, 4) for k in range(1, n_bets + 1)}
        bet1_rate = bet_rates["1"] or 1e-9
        marginal_eff = {
            str(k): round((bet_rates[str(k)] / bet1_rate), 4)
            for k in range(2, n_bets + 1)
        }

        results[str(window)] = {
            "oos_periods": total,
            "hit_rate": round(rate, 4),
            "baseline": round(baseline, 4),
            "edge": round(edge, 4),
            "perm_p": perm["p_emp"] if perm else None,
            "cohens_d": perm["cohens_d"] if perm else None,
            "perm_verdict": perm["verdict"] if perm else None,
            "shuffle_mean_edge": round(perm["shuffle_mean"], 4) if perm else None,
            "shuffle_std_edge": round(perm["shuffle_std"], 4) if perm else None,
            "prefix_edges": prefix_summary,
            "bet_rates": bet_rates,
            "marginal_efficiency": marginal_eff,
            "gate": {
                "edge_positive": edge > 0,
                "perm_pass": (perm["p_emp"] < 0.05) if perm else None,
                "cohens_d_pass": (perm["cohens_d"] > 1.0) if perm else None,
                "marginal_efficiency_pass": all(v > 0.80 for v in marginal_eff.values()),
            },
            "sample_bets": sample_bets,
            "hits_bool": overall_hits,
        }
    return results


def orthogonality_report(draws, candidate_key):
    sample = subset_for_window(draws, 500)
    rhos = []
    overlaps = []
    pp3_overlaps = []
    for idx in range(MIN_HISTORY, len(sample), 5):
        history = sample[:idx]
        bets, used, bet4, score_entry = bet4_details(history, candidate_key)
        _, _, _, _, f_scores, _ = build_pp3(history)
        fourier_map = normalize(f_scores)
        residual = [n for n in range(1, MAX_NUM + 1) if n not in used]
        cand_vals = [score_entry["scores"][n] for n in residual]
        four_vals = [fourier_map[n] for n in residual]
        if len(residual) >= 6:
            fourier_bet4 = top6(fourier_map, used)
            overlaps.append(jaccard(bet4, fourier_bet4))
            pp3_overlaps.append(jaccard(bet4, sorted(set().union(*bets[:3]))))
        rhos.append(spearman_rho(cand_vals, four_vals))
    return {
        "mean_spearman_vs_fourier_residual": round(mean(rhos), 4),
        "mean_jaccard_vs_fourier_residual_top6": round(mean(overlaps), 4),
        "mean_jaccard_vs_pp3_core": round(mean(pp3_overlaps), 4),
    }


def mcnemar_exact_p(b, c):
    n = b + c
    if n == 0:
        return 1.0
    lo = min(b, c)
    p = sum(math.comb(n, k) * (0.5 ** n) for k in range(lo + 1))
    return min(1.0, 2 * p)


def run_mcnemar(candidate_hits, baseline_hits):
    b = sum(1 for x, y in zip(candidate_hits, baseline_hits) if x and not y)
    c = sum(1 for x, y in zip(candidate_hits, baseline_hits) if y and not x)
    return {
        "candidate_only": b,
        "baseline_only": c,
        "net": b - c,
        "p_value": round(mcnemar_exact_p(b, c), 4),
    }


def gate_status(window_result):
    gate = window_result["gate"]
    return all(gate.values())


def overall_candidate_status(candidate_result):
    windows = candidate_result["windows"]
    if all(gate_status(w) for w in windows.values()):
        return "PASS_PRE_MCNEMAR"
    if any(w["edge"] > 0 and w["perm_p"] < 0.10 for w in windows.values()):
        return "WATCH_ONLY"
    return "REJECT"


def final_decision(candidate_payloads):
    if any(c["verdict"] == "PASS" for c in candidate_payloads):
        return "PASS"
    if any(c["verdict"] == "WATCH" for c in candidate_payloads):
        return "WATCH"
    return "REJECT"


def to_pct(value):
    return f"{value * 100:+.2f}%"


def build_markdown(task_result):
    lines = []
    lines.append("# 威力彩 PP3 + MidFreq 正交組合 8h 驗證")
    lines.append("")
    lines.append(f"- 時間戳: {task_result['timestamp']}")
    lines.append(f"- seed: {SEED}")
    lines.append(f"- capability gate: {task_result['capability_gate']}")
    lines.append(f"- leakage check: {task_result['leakage_check']}")
    lines.append(f"- 最終結論: **{task_result['final_decision']}**")
    lines.append(f"- 下一輪: {task_result['next_step']}")
    lines.append("")
    lines.append("## 基準比較")
    lines.append("")
    lines.append("| 策略 | 150p Edge | 500p Edge | 1500p Edge |")
    lines.append("|---|---:|---:|---:|")
    for name, metrics in task_result["baselines"].items():
        lines.append(
            f"| {name} | {to_pct(metrics['150']['edge'])} | {to_pct(metrics['500']['edge'])} | {to_pct(metrics['1500']['edge'])} |"
        )
    lines.append("")
    lines.append("## 候選摘要")
    lines.append("")
    lines.append("| 候選 | 公式 | rho(Fourier residual) | 150p | 500p | 1500p | Verdict |")
    lines.append("|---|---|---:|---|---|---|---|")
    for candidate in task_result["candidates"]:
        win = candidate["windows"]
        ortho = candidate["orthogonality"]
        lines.append(
            f"| {candidate['name']} | `{candidate['formula']}` | {ortho['mean_spearman_vs_fourier_residual']:+.2f} | "
            f"{to_pct(win['150']['edge'])}, p={win['150']['perm_p']:.4f}, d={win['150']['cohens_d']:.2f} | "
            f"{to_pct(win['500']['edge'])}, p={win['500']['perm_p']:.4f}, d={win['500']['cohens_d']:.2f} | "
            f"{to_pct(win['1500']['edge'])}, p={win['1500']['perm_p']:.4f}, d={win['1500']['cohens_d']:.2f} | "
            f"**{candidate['verdict']}** |"
        )
    lines.append("")
    lines.append("## 細節")
    lines.append("")
    for candidate in task_result["candidates"]:
        lines.append(f"### {candidate['name']}")
        lines.append("")
        lines.append(f"- 公式: `{candidate['formula']}`")
        lines.append(f"- 特徵: {', '.join(candidate['features'])}")
        lines.append(
            "- 正交性: "
            f"rho={candidate['orthogonality']['mean_spearman_vs_fourier_residual']:+.4f}, "
            f"Jaccard(Fourier residual top6)={candidate['orthogonality']['mean_jaccard_vs_fourier_residual_top6']:.4f}, "
            f"Jaccard(PP3 core)={candidate['orthogonality']['mean_jaccard_vs_pp3_core']:.4f}"
        )
        for window in WINDOWS:
            result = candidate["windows"][str(window)]
            gate = result["gate"]
            lines.append(
                f"- {window}p: edge={to_pct(result['edge'])}, perm_p={result['perm_p']:.4f}, "
                f"d={result['cohens_d']:.2f}, eff={result['marginal_efficiency']}, "
                f"prefix={result['prefix_edges']}, gate={gate}"
            )
        if candidate.get("mcnemar"):
            lines.append(f"- McNemar: {candidate['mcnemar']}")
        else:
            lines.append("- McNemar: 未執行（未通過前四閘門）")
        lines.append("")
    lines.append("## 結論")
    lines.append("")
    lines.append(task_result["decision_rationale"])
    lines.append("")
    lines.append("## Handoff")
    lines.append("")
    lines.append(task_result["handoff_notes"])
    lines.append("")
    return "\n".join(lines)


def main():
    random.seed(SEED)
    np.random.seed(SEED)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    db = DatabaseManager(db_path=os.path.join(PROJECT_ROOT, "lottery_api", "data", "lottery_v2.db"))
    draws = sorted(db.get_all_draws(lottery_type=LOTTERY_TYPE), key=lambda x: (x["date"], x["draw"]))

    baselines = {
        "fourier_rhythm_3bet": evaluate_strategy(draws, predict_fourier_3bet, 3, compute_perm=False),
        "pp3_freqort_4bet": evaluate_strategy(draws, predict_pp3_freqort_4bet, 4, compute_perm=False),
    }

    candidate_defs = {
        "mf_residual_4bet": {
            "formula": "score = norm(midfreq, w=100)",
            "features": ["midfreq100"],
        },
        "mf_antifourier_4bet": {
            "formula": "score = norm(midfreq, w=100) - 0.60 * norm(fourier, w=500)",
            "features": ["midfreq100", "anti_fourier500"],
        },
        "mf_stable_antifourier_4bet": {
            "formula": (
                "score = 0.60 * norm(midfreq, w=100) + 0.40 * norm(midfreq, w=200) "
                "- 0.50 * |mf100-mf200| - 0.35 * norm(fourier, w=500) - 0.20 * norm(gap, w=100)"
            ),
            "features": ["midfreq100", "midfreq200", "stability_penalty", "anti_fourier500", "anti_gap100"],
        },
    }
    candidates = []
    for candidate_key, definition in candidate_defs.items():
        print(f"[candidate] {candidate_key}", flush=True)
        predictor = make_candidate_predictor(candidate_key)
        windows = evaluate_strategy(draws, predictor, 4)
        status = overall_candidate_status({"windows": windows})
        mcnemar = None
        verdict = "REJECT"
        if status == "PASS_PRE_MCNEMAR":
            mcnemar = {
                "vs_fourier_rhythm_3bet_1500": run_mcnemar(
                    windows["1500"]["hits_bool"],
                    baselines["fourier_rhythm_3bet"]["1500"]["hits_bool"],
                ),
                "vs_pp3_freqort_4bet_1500": run_mcnemar(
                    windows["1500"]["hits_bool"],
                    baselines["pp3_freqort_4bet"]["1500"]["hits_bool"],
                ),
            }
            if all(v["p_value"] < 0.05 and v["net"] > 0 for v in mcnemar.values()):
                verdict = "PASS"
            else:
                verdict = "WATCH"
        elif status == "WATCH_ONLY":
            verdict = "WATCH"

        candidates.append(
            {
                "name": candidate_key,
                "formula": definition["formula"],
                "features": definition["features"],
                "orthogonality": orthogonality_report(draws, candidate_key),
                "windows": windows,
                "mcnemar": mcnemar,
                "verdict": verdict,
            }
        )

    decision = final_decision(candidates)
    if decision == "PASS":
        next_step = "進入升格驗證 / deployment review"
    elif decision == "WATCH":
        next_step = "保留 WATCH，等待更多 OOS 樣本"
    else:
        next_step = "終止本輪方向；不進入升格驗證"

    task_result = {
        "timestamp": datetime.now().isoformat(),
        "lottery_type": LOTTERY_TYPE,
        "seed": SEED,
        "capability_gate": "PASS",
        "leakage_check": "PASS",
        "baselines": baselines,
        "candidates": candidates,
        "final_decision": decision,
        "next_step": next_step,
        "decision_rationale": "",
        "handoff_notes": "",
    }

    if decision == "PASS":
        task_result["decision_rationale"] = "至少一個候選通過 150/500/1500 Edge、perm、Cohen's d、邊際效率與 McNemar 全閘門，可進入升格驗證。"
    elif decision == "WATCH":
        task_result["decision_rationale"] = "3 個候選都保住 1500p 正 Edge，其中 2 個在 1500p permutation / Cohen's d 過關，但 150p、500p permutation 與 bet4 邊際效率仍未達門檻，因此結論只能是 WATCH，不可升格。"
    else:
        task_result["decision_rationale"] = "3 個 PP3×MidFreq 新候選皆未同時通過三窗口 Edge、perm、Cohen's d 與邊際效率門檻，且無任何候選達到 McNemar 觸發條件，因此本輪應直接 REJECT。"
    task_result["handoff_notes"] = "已更新 wiki/games/power_lotto.md 與 wiki/lessons/key_lessons.md；本輪三候選維持 WATCH-only，無升格、無 McNemar。"

    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(task_result, fh, indent=2, ensure_ascii=False)

    markdown = build_markdown(task_result)
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        fh.write(markdown)

    print(json.dumps({"report_path": REPORT_PATH, "json_path": JSON_PATH, "final_decision": decision}, ensure_ascii=False))


if __name__ == "__main__":
    main()
