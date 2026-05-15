"""
今彩539 第115000076期 LLM Research Board 檢討報告
自動寫入 DB
"""
import json
import requests

API_BASE = "http://localhost:8002"
RUN_ID = 57  # prediction_runs row for latest 539 that targets 115000076

# ============================================================
# Structured Review Data
# ============================================================
review = {
    "version": "2.0",
    "review_date": "2026-03-27",
    "lottery_type": "DAILY_539",
    "target_draw": "115000076",
    "actual_numbers": [14, 17, 20, 24, 37],
    "actual_date": "2026/03/26",
    
    # ── 1. 資料一致性 ──
    "data_consistency": {
        "draw_continuity": "PASS",
        "note": "期號連續 114000067~115000075 (325期), gap僅在年度交界 114000316→115000001",
        "date_alignment": "PASS",
        "missing_data": "115000076 尚未同步到 rolling monitor, JSONL 115000075 actual=None",
        "confidence": "DATA"
    },
    
    # ── 2. 特徵分析 ──
    "feature_analysis": {
        "actual": {
            "numbers": [14, 17, 20, 24, 37],
            "sum": 112,
            "odd_even": "2O/3E",
            "high_low": "3H/2L",
            "gaps": [3, 3, 4, 13],
            "tail_digits": [4, 7, 0, 4, 7],
            "zones": {"Z1": 0, "Z2": 3, "Z3": 1, "Z4": 1},
            "consecutive_pairs": 0
        },
        "deviation_from_mean": {
            "sum_note": "sum=112, 近10期均值=109.7, 偏差+2.1%",
            "confidence": "DATA"
        }
    },
    
    # ── 3. 方法比較 Top3 ──
    "method_comparison": {
        "top3_closest": [
            {
                "rank": 1,
                "method": "f4cold_5bet",
                "bet_count": 5,
                "best_hit": 2,
                "best_bet": [14, 20, 29, 31, 33],
                "matched": [14, 20],
                "note": "bet4 命中 14,20 (2/5), 其他注各0~1",
                "confidence": "DATA"
            },
            {
                "rank": 2,
                "method": "acb_markov_midfreq_3bet",
                "bet_count": 3,
                "best_hit": 2,
                "best_bet": [6, 17, 18, 24, 34],
                "matched": [17, 24],
                "note": "bet3 命中 17,24 (2/5), 來自 115000075 rolling monitor",
                "confidence": "DATA"
            },
            {
                "rank": 3,
                "method": "Coordinator-Direct (7 agents)",
                "bet_count": 3,
                "best_hit": 1,
                "best_bet": [6, 17, 19, 21, 34],
                "matched": [17],
                "note": "JSONL 預測 (115000075 target), 最高僅1中",
                "confidence": "DATA"
            }
        ],
        "overall_best_hit": 2,
        "note": "所有方法最高命中2, 距離3中獎門檻仍差1球",
        "confidence": "DATA"
    },
    
    # ── 4. 未命中原因分析 ──
    "miss_analysis": {
        "missed_numbers": [14, 17, 20, 24, 37],
        "correctable": [
            "14, 20: 出現在 f4cold_5bet 的 bet4, 但該注同時含 29,31,33 (過度集中高區)",
            "17: 被多個策略捕獲但與其他號碼組合不佳",
            "24: 僅 acb_markov_midfreq 的 bet3 捕獲",
            "Zone分布 Z2=3, Z1=0 — 策略偏好 Z1 zone, 本期Z1全空"
        ],
        "uncontrollable": [
            "37: 高區尾數7, 僅少數策略覆蓋, 為低頻號",
            "540+ 組合空間下, 5中仍為 1/575757 概率事件",
            "本期 Z2 集中(3球)是低概率分布, 不可預見"
        ],
        "confidence": "INFER"
    },
    
    # ── 5. Winning Quality 分析 ──
    "winning_quality": {
        "popularity_score": "LOW",
        "birthday_range": "4/5 (高, 14/17/20/24 皆≤31)",
        "popular_overlap": 0,
        "split_risk": "HIGH",
        "split_risk_note": "4/5球在生日範圍(1-31), 容易與手選玩家重疊",
        "payout_quality": "LOW",
        "expected_winners_5match": 0.52,
        "payout_note": "若中頭獎, 分獎風險高; 但本組合無熱門號, 實際分獎可能中等",
        "recommendation": "未來選號應考慮迴避全生日範圍組合",
        "confidence": "INFER"
    },
    
    # ── 6. 多窗口量化 ──
    "quantitative": {
        "strategy_gates": {
            "f4cold_5bet": {
                "num_bets": 5, "total_draws": 325,
                "stage1_edge": "+0.31%", "stage1": "PASS",
                "stage2_perm_p": 0.4239, "stage2": "FAIL",
                "stage3_binom_p": 0.4332, "stage3": "FAIL",
                "stage4_sharpe": -3.5079, "stage4": "FAIL",
                "stage5_oos_edge": "+4.26%", "stage5": "PASS",
                "gates_passed": "2/5", "verdict": "WATCH",
                "windows": {
                    "30": {"m3_rate": "6.67%", "edge": "+1.75%", "sharpe": -3.07},
                    "100": {"m3_rate": "9.00%", "edge": "+4.08%", "sharpe": -2.60},
                    "300": {"m3_rate": "5.33%", "edge": "+0.41%", "sharpe": -3.47}
                }
            },
            "acb_markov_midfreq_3bet": {
                "num_bets": 3, "total_draws": 325,
                "stage1_edge": "+0.40%", "stage1": "PASS",
                "stage2_perm_p": 0.3778, "stage2": "FAIL",
                "stage3_binom_p": 0.3779, "stage3": "FAIL",
                "stage4_sharpe": -2.5778, "stage4": "FAIL",
                "stage5_oos_edge": "+1.10%", "stage5": "PASS",
                "gates_passed": "2/5", "verdict": "WATCH",
                "windows": {
                    "30": {"m3_rate": "3.33%", "edge": "+0.35%", "sharpe": -2.60},
                    "100": {"m3_rate": "4.00%", "edge": "+1.02%", "sharpe": -2.35},
                    "300": {"m3_rate": "3.33%", "edge": "+0.35%", "sharpe": -2.60}
                }
            },
            "f4cold_3bet": {
                "num_bets": 3, "total_draws": 325,
                "stage1_edge": "+0.10%", "stage1": "PASS",
                "stage2_perm_p": 0.4993, "stage2": "FAIL",
                "stage3_binom_p": 0.5043, "stage3": "FAIL",
                "stage4_sharpe": -2.7172, "stage4": "FAIL",
                "stage5_oos_edge": "+2.12%", "stage5": "PASS",
                "gates_passed": "2/5", "verdict": "WATCH"
            },
            "acb_1bet": {
                "num_bets": 1, "total_draws": 325,
                "stage1_edge": "-0.70%", "stage1": "FAIL",
                "gates_passed": "0/5", "verdict": "REJECT"
            },
            "midfreq_acb_2bet": {
                "num_bets": 2, "total_draws": 325,
                "stage1_edge": "-0.46%", "stage1": "FAIL",
                "gates_passed": "1/5", "verdict": "REJECT"
            },
            "acb_markov_fourier_3bet": {
                "num_bets": 3, "total_draws": 325,
                "stage1_edge": "-0.21%", "stage1": "FAIL",
                "gates_passed": "1/5", "verdict": "REJECT"
            }
        },
        "baseline": {
            "539_total_combinations": 575757,
            "p_match3_1bet": "1.004%",
            "p_match3_3bet": "2.982%",
            "p_match2_3bet": "30.443%"
        },
        "confidence": "DATA"
    },
    
    # ── 7. 反證檢查 ──
    "counter_evidence": [
        {
            "claim": "所有策略 edge 可能只是隨機波動",
            "evidence": "Permutation test p > 0.37 for ALL strategies — 無法拒絕隨機假說",
            "severity": "HIGH",
            "confidence": "DATA"
        },
        {
            "claim": "OOS edge 可能是過擬合倖存者偏差",
            "evidence": "OOS window (後30%) 的 edge 比全樣本高, 但窗口重疊度高, 不足以確認穩定性",
            "severity": "MED",
            "confidence": "INFER"
        },
        {
            "claim": "325期數據不足以確認小 edge",
            "evidence": "要檢測 +0.4% edge 在 p<0.05, 需約 2000+ 期數據",
            "severity": "MED",
            "confidence": "INFER"
        }
    ],
    
    # ── 8. 專家意見 ──
    "expert_opinions": {
        "theorist": {
            "role": "方法理論專家（統計/AI理論）",
            "points": [
                "所有策略未通過 Stage2-3 (Permutation/Binomial), 統計顯著性不足 — 不可宣稱有預測能力",
                "Sharpe ratio 全為負數(-2.5~-3.5), 表示在現有獎金結構下, 任何策略的期望報酬都是負的",
                "建議方向: 從 Track A (命中率) 轉向 Track B (Winning Quality), 因為 prediction signal ceiling 已確認",
                "M3+ baseline=2.98% (3bet), 最佳策略=3.38%, edge 僅 0.4% — 接近 noise floor"
            ]
        },
        "pragmatist": {
            "role": "技術務實專家（可行性/實驗設計）",
            "points": [
                "f4cold_5bet 的 window-100 m3+=9.0% (vs baseline 4.92%) 是值得追蹤的信號, 但需更多數據確認",
                "acb_markov_midfreq_3bet 在各窗口表現最一致 (30/100/300 都有正 edge), 適合作為主力策略",
                "建議增加 rolling monitor 到 1500 期後再做最終判定",
                "本期 Zone 分布異常 (Z2=3球), 可加入 Zone-balance filter 作為後處理"
            ]
        },
        "architect": {
            "role": "程式架構專家（實作成本/優先級）",
            "points": [
                "現有 rolling monitor + JSONL 系統運作正常, 但 DB 追蹤表為空 — 需要同步機制",
                "建議 P0: 將 review_json 結構化寫入 DB, 讓前端可顯示歷史檢討",
                "建議 P1: 加入 Winning Quality 後處理 (split risk filter), 成本低、impact 可測量",
                "建議 P2: 擴充策略到 1500 期, 自動化檢討報告產生流程"
            ]
        }
    },
    
    # ── 9. 行動清單 ──
    "action_items": {
        "P0": [
            {
                "action": "維持 acb_markov_midfreq_3bet 為 DAILY_539 主力策略 (WATCH 狀態)",
                "expected_lift": "0%",
                "cost": "零, 維持現狀",
                "risk": "LOW",
                "validation": "持續 rolling monitor 追蹤",
                "stop_condition": "連續 50 期 edge < 0 → 降級為 ADVISORY"
            },
            {
                "action": "將結構化檢討報告 (review_json) 寫入 DB 並在前端顯示",
                "expected_lift": "N/A (治理改善)",
                "cost": "2 hrs 實作",
                "risk": "LOW",
                "validation": "API 回傳 review_json 欄位, 前端可展開檢視",
                "stop_condition": "N/A"
            }
        ],
        "P1": [
            {
                "action": "加入 Winning Quality 後處理: 對預測結果計算 split_risk score, 過濾高分獎組合",
                "expected_lift": "中獎時 payout +10~30% (estimated)",
                "cost": "4 hrs 實作 + 驗證",
                "risk": "MED — 可能排除部分有效組合",
                "validation": "回測 300 期, 比較過濾前後的 expected value",
                "stop_condition": "過濾後 m3+ rate 下降 > 20% → 回退"
            },
            {
                "action": "Zone-balance filter: 排除 Z1=0 或單區 ≥3 的組合",
                "expected_lift": "未知, 需回測",
                "cost": "2 hrs",
                "risk": "LOW",
                "validation": "回測 300 期 zone 分布 vs hit rate",
                "stop_condition": "無顯著改善 → 不採用"
            }
        ],
        "P2": [
            {
                "action": "擴充 rolling monitor 到 1500 期後重新進行 Stage1-5 gate validation",
                "expected_lift": "更可靠的統計結論",
                "cost": "時間成本 (等待數據累積)",
                "risk": "LOW",
                "validation": "1500 期完成後自動觸發全策略重驗",
                "stop_condition": "N/A"
            },
            {
                "action": "玩家偏好模型: 收集台彩每期銷售/得獎人數資料, 建立 popularity scoring",
                "expected_lift": "payout 優化 potential +20%",
                "cost": "8 hrs (資料收集 + 建模)",
                "risk": "MED — 資料取得困難",
                "validation": "歷史數據中 得獎人數 vs 號碼特徵 相關性分析",
                "stop_condition": "相關性 < 0.1 → 暫停"
            }
        ]
    },
    
    # ── 10. 最終決策 ──
    "final_decision": {
        "verdict": "觀察",
        "confidence": "中",
        "reasoning": "所有策略未通過統計顯著性門檻 (Stage2-3), 但部分策略(acb_markov_midfreq_3bet, f4cold_5bet)在OOS窗口顯示正edge。維持WATCH狀態, 等待更多數據。",
        "next_review_trigger": "數據累積至 500 期 或 連續 10 期 m3+ 命中 或 連續 50 期 edge < 0"
    },
    
    # ── 11. 方法族假設 ──
    "method_hypotheses": {
        "temporal": {
            "testable": "Markov chain transition matrix stability test (window 100 vs 300)",
            "status": "IMPLEMENTED (acb_markov_midfreq)",
            "confidence": "INFER"
        },
        "distributional": {
            "testable": "Zone-balance filter (Z1/Z2/Z3/Z4 均衡度 vs hit rate)",
            "status": "PROPOSED",
            "confidence": "UNSURE"
        },
        "frequency": {
            "testable": "Fourier cycle detection on recent 100-period window",
            "status": "IMPLEMENTED (acb_markov_fourier), underperforming",
            "confidence": "DATA"
        },
        "combinatorial": {
            "testable": "5-bet portfolio diversity maximization vs 3-bet focused",
            "status": "IMPLEMENTED (f4cold_5bet vs f4cold_3bet)",
            "confidence": "DATA"
        },
        "governance": {
            "testable": "Automated gate-based strategy promotion/demotion",
            "status": "PROPOSED (P2)",
            "confidence": "UNSURE"
        },
        "behavioral": {
            "testable": "Player preference model + split risk filter",
            "status": "PROPOSED (P1)",
            "confidence": "UNSURE"
        }
    }
}

# ============================================================
# Build analysis note (human-readable summary)
# ============================================================
analysis_note = """【LLM Research Board 檢討報告】第115000076期 今彩539
開獎號碼: 14, 17, 20, 24, 37 | sum=112 | 2O/3E | Z2×3

■ 最接近方法 Top3:
1. f4cold_5bet: 2中(14,20) — 5注中bet4最佳
2. acb_markov_midfreq_3bet: 2中(17,24) — 3注中bet3最佳  
3. Coordinator-Direct: 1中(17) — JSONL預測

■ 關鍵發現:
- 全策略最高命中=2, 距3中門檻差1球
- 所有策略未通過 Permutation test (p>0.37)
- Sharpe 全為負 (-2.5~-3.5)
- acb_markov_midfreq_3bet edge=+0.40% (最高), 但統計不顯著

■ Winning Quality:
- Split risk: HIGH (4/5球在生日範圍)
- Payout quality: LOW
- 建議: 加入 split risk 後處理 filter

■ 決策: 觀察 (信心:中)
- 維持 WATCH, 等待 500 期重驗
- P0: 結構化報告寫入DB + 維持現策略
- P1: Split risk filter + Zone balance
- P2: 1500期重驗 + 玩家偏好模型"""

# ============================================================
# Submit to DB via API
# ============================================================
url = f"{API_BASE}/api/tracking/run/{RUN_ID}/review"
payload = {
    "note": analysis_note,
    "review_json": json.dumps(review, ensure_ascii=False)
}

resp = requests.post(url, json=payload)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.json()}")

# Verify
verify = requests.get(f"{API_BASE}/api/tracking/run/{RUN_ID}")
data = verify.json()
print(f"\nVerification:")
print(f"  analyzed: {data.get('analyzed')}")
print(f"  analysis_note length: {len(data.get('analysis_note', ''))}")
print(f"  review_json present: {data.get('review_json') is not None}")
if data.get('review_json'):
    rj = data['review_json']
    if isinstance(rj, dict):
        print(f"  review_json keys: {list(rj.keys())}")
        print(f"  verdict: {rj.get('final_decision', {}).get('verdict')}")
        print(f"  confidence: {rj.get('final_decision', {}).get('confidence')}")
