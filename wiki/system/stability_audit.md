# 穩定性稽核規範（Stability Audit）

> Source-of-truth：本檔。詳細稽核報告見 `docs/` 中的 `optimization_log_stability_audit.md`；  
> 遊戲別舊報告已歸檔至 `docs/archive/`。

---

## 稽核目的

確保已部署策略在新資料流入後仍維持效能，並偵測異常漂移。

---

## 稽核觸發條件

| 觸發 | 說明 |
|------|------|
| 定期 | 每 50 期新資料 |
| 手動 | 任何策略升降級前 |
| 異常 | ROI 窗口偏離 > 2σ |

---

## 稽核指標

| 指標 | 通過標準 |
|------|----------|
| 三窗口 ROI | 皆 > baseline（見 `wiki/system/validation_gates.md`）|
| Hit Rate 標準差 | < 30% of mean |
| Sharpe Ratio | > 0 |
| Drawdown | < 25% |

---

## 稽核結果分類

- **PASS**：三指標全過，維持部署
- **WATCH**：1 項偏弱，列入觀察，下次稽核複查
- **ADVISORY_ONLY**：只保留分析參考，不作為下注依據
- **SUSPENDED**：多項失敗，移回 `provisional/` 重新驗證

---

## 三款遊戲現況摘要

> 詳細數字請查閱 `docs/optimization_log_stability_audit.md`

- **BIG_LOTTO**：ADVISORY_ONLY（Stage 3 Anti-Crowd ROI Δ+1.04%，perm p=0.257，不顯著）
- **DAILY_539**：ADVISORY_ONLY
- **POWER_LOTTO**：ADVISORY_ONLY

---

## 相關連結

- 驗證閘規則：`wiki/system/validation_gates.md`
- 決策引擎結論：`wiki/system/decision_engine.md`
- 舊報告（歸檔）：`docs/archive/INDEX.md`

## Deployment & Implementation Checklist (extracted)

- Deployment pre-check: configuration version, `lottery_types.json` sync, and `verify_id_unification` must pass before rollout.
- Runtime health: expose `GET /health` and `GET /api/strategy-states/{lottery_type}`; ensure strategy state fields (`edge_300p`, `trend`, `alert`, `sharpe_300p`) exist and are populated.
- Strategy status derivation: implement `_derive_strategy_status()` rules in code and document thresholds in `docs/IMPLEMENTATION_STATUS.md` (wiki keeps rule, not numeric claims).
- Predictor method presence: verify required predictor methods exist in `unified_predictor` (see `governance.md` checklist) as part of CI.
- Backtest-to-deploy gate: only strategies that pass validation gates and robustness checks (permutation, noise robustness, WF) proceed to `validated/` deployment stage.
