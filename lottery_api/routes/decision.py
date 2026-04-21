"""
Decision Layer V3 API Routes
GET /api/decision/{lottery_type}  — 取得下期決策建議（注數/風險/信心）
"""
import os
import sys
import json
from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict, Any

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.dirname(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tools.ev_gate import evaluate_jackpot_gate, evaluate_stage2_gate

router = APIRouter(prefix="/api/decision", tags=["Decision"])

_engine = None

def _get_engine():
    global _engine
    if _engine is None:
        try:
            from analysis.decision_engine_v3 import DecisionEngineV3
            _engine = DecisionEngineV3(mode="decision_v3")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Decision engine init failed: {e}")
    return _engine


def _build_v31_gate(lottery_type: str) -> Dict[str, Any]:
    gate = evaluate_jackpot_gate(lottery_type)
    gate["stage2_gate"] = evaluate_stage2_gate(lottery_type)
    return gate


LOTTERY_LABELS = {
    "DAILY_539":   "今彩539",
    "BIG_LOTTO":   "大樂透",
    "POWER_LOTTO": "威力彩",
}

RISK_LABELS = {
    "LOW_RISK": "低風險 (穩定期)",
    "STABLE": "穩健期",
    "WATCH": "需留意外插 (WATCH)",
    "VOLATILE": "高波動 (小心預期)",
    "REJECT": "高維度異常 (暫停推薦)",
    "UNKNOWN": "未知風險"
}

# 策略與開發資料夾對應 (用於 500p/1500p 回測數據)
STRATEGY_SIM_MAP = {
    "f4cold_5bet": "daily_539/5bet_fourier4_cold",
    "p1_dev_sum5bet": "big_lotto/5bet_ts3_markov_freq",
    "acb_markov_midfreq_3bet": "daily_539/3bet_acb_markov",
}


@router.get("/best-strategy-summary")
async def get_best_strategy_summary():
    """
    聚合三彩種的「最佳策略總覽」(Phase V — composite_score 排名)。
    選擇優先級: VALIDATED > WATCH > REJECTED
    排名公式: composite_score = 0.5*edge_1500p + 0.3*sharpe - 0.2*max_drawdown_rate
    返回最佳策略及所有可用策略列表（依 composite_score 或 cp_score 排序）。
    """
    results = []
    GAMES = ["DAILY_539", "BIG_LOTTO", "POWER_LOTTO"]

    for lt in GAMES:
        label = LOTTERY_LABELS.get(lt, lt)
        game_entry: Dict[str, Any] = {
            "game": label,
            "game_id": lt,
            "best_strategy": None,
            "all_strategies": []
        }

        # 1. 讀取 strategy_states_{lt}.json
        state_file = os.path.join(_HERE, "..", "data", f"strategy_states_{lt}.json")
        if not os.path.exists(state_file):
            results.append(game_entry)
            continue

        try:
            with open(state_file, "r", encoding="utf-8") as f:
                states = json.load(f)

            from routes.prediction import _derive_strategy_status

            strategies = []
            for sid, s in states.items():
                rate_300 = s.get("rate_300p")
                bets = s.get("num_bets") or 1
                if bets <= 0: continue

                # 舊版 CP score（向下相容）
                cp_score = 0
                if rate_300 is not None:
                    cp_score = (float(rate_300) * 100.0) / float(bets)

                # Phase V: validated fields
                vs = s.get("validated_status")
                cs = s.get("composite_score")

                # derive_strategy_status uses validated_status when available
                status = _derive_strategy_status(s)

                strat = {
                    "strategy_name": sid,
                    "bet_count": bets,
                    # legacy fields
                    "success_rate_300": round(float(rate_300)*100, 2) if rate_300 is not None else None,
                    "cp_score": round(float(cp_score), 3),
                    "edge": round(float(s.get("edge_300p") or 0)*100, 2),
                    # Phase V fields
                    "validated_status": vs,
                    "composite_score": round(float(cs), 6) if cs is not None else None,
                    "edge_150p": round(float(s["edge_150p"])*100, 3) if s.get("edge_150p") is not None else None,
                    "edge_500p": round(float(s["edge_500p"])*100, 3) if s.get("edge_500p") is not None else None,
                    "edge_1500p": round(float(s["edge_1500p"])*100, 3) if s.get("edge_1500p") is not None else None,
                    "perm_p": s.get("perm_p"),
                    "mcnemar_p": s.get("mcnemar_p"),
                    "sharpe": s.get("sharpe"),
                    "max_drawdown_rate": s.get("max_drawdown_rate"),
                    "validation_notes": s.get("validation_notes"),
                    "status": status,
                }
                strategies.append(strat)

            # 2. Best strategy ranking:
            #    - Prefer formal validation status when available.
            #    - If no formal status exists, fall back to derived status and CP-aware ranking.
            #    - This avoids a false N/A when strategy_states has been regenerated without
            #      validated_status metadata.
            def _rank_key(x):
                vs = (x.get("validated_status") or "").upper()
                derived = (x.get("status") or "").upper()
                cp = x.get("cp_score") or 0
                sr300 = x.get("success_rate_300") or 0
                cs = x.get("composite_score") or 0
                e1500 = x.get("edge_1500p") or 0
                sharpe = x.get("sharpe") or 0
                dd = x.get("max_drawdown_rate") or 0

                if vs == "VALIDATED":
                    status_priority = 4
                elif vs == "WATCH":
                    status_priority = 3
                elif derived == "PRODUCTION":
                    status_priority = 2
                elif derived == "WATCH":
                    status_priority = 1
                elif derived == "MAINTENANCE":
                    status_priority = 0
                else:
                    status_priority = -1

                # cp_score is primary when we no longer have formal validation markers.
                return (status_priority, cp, sr300, cs, e1500 / 100.0, sharpe, -dd)

            strategies.sort(key=_rank_key, reverse=True)

            game_entry["all_strategies"] = strategies

            # 3. Best strategy selection:
            #    - If we have formal validation markers, the ranking above will surface them first.
            #    - Otherwise, pick the highest CP-aware formal strategy rather than showing N/A.
            best = strategies[0] if strategies else None
            if best:
                if (best.get("validated_status") or "").upper() not in ("VALIDATED", "WATCH"):
                    if best.get("status") in ("PRODUCTION", "WATCH"):
                        best["validation_warning"] = "NO_FORMAL_VALIDATION — ranked by CP-aware fallback"
                    else:
                        best["validation_warning"] = "NO_FORMAL_VALIDATION — ranked by derived status fallback"
            game_entry["best_strategy"] = best

        except Exception as e:
            print(f"Error processing {lt}: {e}")
            pass

        results.append(game_entry)

    return results


@router.get("/{lottery_type}")
async def get_decision(lottery_type: str, mode: Optional[str] = "decision_v3"):
    """取得指定彩種的下期決策建議。"""
    lt = lottery_type.upper()
    if lt not in LOTTERY_LABELS:
        raise HTTPException(status_code=400, detail=f"Unknown lottery_type: {lottery_type}")

    try:
        engine = _get_engine()
        eng = engine
        if mode and mode != engine.mode:
            from analysis.decision_engine_v3 import DecisionEngineV3
            eng = DecisionEngineV3(mode=mode)

        result = eng.decide(lt)
        d = result.to_dict()
        risk_class = d.get("risk_profile", {}).get("risk_class", "UNKNOWN")
        gate = _build_v31_gate(lt)

        return {
            "lottery_type":      lt,
            "lottery_label":     LOTTERY_LABELS[lt],
            "n_bets":            d["n_bets"],
            "strategy_name":     d["strategy_name"],
            "final_confidence":  round(float(d["final_confidence"]), 3),
            "risk_class":        risk_class,
            "risk_label":        RISK_LABELS.get(risk_class, risk_class),
            "exposure_weight":   round(float(d["exposure_weight"]), 3),
            "policy_id":         d["policy_id"],
            "mode":              d["mode"],
            "notes":             d["notes"],
            "confidence_vector": d["confidence_vector"],
            "bankroll_snapshot": d.get("bankroll_snapshot"),
            "ev_gate_open":      gate["ev_gate_open"],
            "current_jackpot":   gate["current_jackpot"],
            "breakeven_jackpot": gate["breakeven_jackpot"],
            "ev_gap":            gate["ev_gap"],
            "recommended_bet_count": gate["recommended_bet_count"],
            "n_bets_after_gate": gate["n_bets_after_gate"],
            "monthly_budget_after_gate": gate["monthly_budget_after_gate"],
            "kelly_fraction":    gate["kelly_fraction"],
            "exposure_weight_after_gate": gate["exposure_weight_after_gate"],
            "jackpot_source":    gate["current_jackpot_source"],
            "gate_confidence":   gate["confidence"],
            "stage2_gate":       gate["stage2_gate"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def get_all_decisions(mode: Optional[str] = "decision_v3"):
    """取得三彩種的決策建議摘要"""
    results = {}
    for lt in ["DAILY_539", "BIG_LOTTO", "POWER_LOTTO"]:
        try:
            engine = _get_engine()
            eng = engine
            if mode and mode != engine.mode:
                from analysis.decision_engine_v3 import DecisionEngineV3
                eng = DecisionEngineV3(mode=mode)

            result = eng.decide(lt)
            d = result.to_dict()
            risk_class = d.get("risk_profile", {}).get("risk_class", "UNKNOWN")
            gate = _build_v31_gate(lt)
            results[lt] = {
                "lottery_label":     LOTTERY_LABELS[lt],
                "n_bets":            d["n_bets"],
                "strategy_name":     d["strategy_name"],
                "final_confidence":  round(float(d["final_confidence"]), 3),
                "risk_class":        risk_class,
                "risk_label":        RISK_LABELS.get(risk_class, risk_class),
                "exposure_weight":   round(float(d["exposure_weight"]), 3),
                "ev_gate_open":      gate["ev_gate_open"],
                "breakeven_jackpot": gate["breakeven_jackpot"],
                "recommended_bet_count": gate["recommended_bet_count"],
                "n_bets_after_gate": gate["n_bets_after_gate"],
                "stage2_gate":       gate["stage2_gate"],
            }
        except Exception as e:
            results[lt] = {"error": str(e)}

    return {"decisions": results}
