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
    聚合三彩種的「最佳 CP 值策略總覽」。
    CP 值定義：300P 成功率 / 投注注數。
    返回最佳策略及所有可用策略列表（依 CP 排序）。
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
            
            strategies = []
            for sid, s in states.items():
                rate_300 = s.get("rate_300p")
                bets = s.get("num_bets") or 1
                if bets <= 0: continue
                
                # 計算 CPScore
                cp_score = 0
                if rate_300 is not None:
                    cp_score = (float(rate_300) * 100.0) / float(bets)
                
                from routes.prediction import _derive_strategy_status
                
                strat = {
                    "strategy_name": sid,
                    "bet_count": bets,
                    "success_rate_300": round(float(rate_300)*100, 2) if rate_300 is not None else None,
                    "success_rate_500": None,
                    "success_rate_1500": None,
                    "cp_score": round(float(cp_score), 3),
                    "status": _derive_strategy_status(s),
                    "edge": round(float(s.get("edge_300p") or 0)*100, 2)
                }

                # 嘗試補充 500p, 1500p
                sim_folder = STRATEGY_SIM_MAP.get(sid)
                if sim_folder:
                    sim_file = os.path.join(_ROOT, "strategies", sim_folder, "sim_result.json")
                    if os.path.exists(sim_file):
                        try:
                            with open(sim_file, "r", encoding="utf-8") as sf:
                                sim_data = json.load(sf)
                                bt = sim_data.get("backtest", {})
                                r500 = bt.get("500p", {}).get("m3_rate_pct") or bt.get("500p", {}).get("win_rate_pct")
                                if r500: strat["success_rate_500"] = round(float(r500), 2)
                                r1500 = bt.get("1500p", {}).get("m3_rate_pct") or bt.get("1500p", {}).get("win_rate_pct")
                                if r1500: strat["success_rate_1500"] = round(float(r1500), 2)
                        except Exception: pass
                
                strategies.append(strat)

            # 2. 排序 (CP 降序)
            strategies.sort(key=lambda x: x["cp_score"], reverse=True)
            
            game_entry["all_strategies"] = strategies
            if strategies:
                game_entry["best_strategy"] = strategies[0]
                
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
            results[lt] = {
                "lottery_label":     LOTTERY_LABELS[lt],
                "n_bets":            d["n_bets"],
                "strategy_name":     d["strategy_name"],
                "final_confidence":  round(float(d["final_confidence"]), 3),
                "risk_class":        risk_class,
                "risk_label":        RISK_LABELS.get(risk_class, risk_class),
                "exposure_weight":   round(float(d["exposure_weight"]), 3),
            }
        except Exception as e:
            results[lt] = {"error": str(e)}

    return {"decisions": results}
