# Lottery Project Memory Index

⚠️ MEMORY IS SECONDARY

Memory is NOT a source of truth.

All memory-based conclusions MUST be validated against wiki.

If conflict exists:
→ wiki wins

Memory is used for:
- historical context
- lessons learned

NOT for:
- final decision making


## Wiki（詳細知識）

- [[wiki/games/big_lotto]] — 大樂透維護模式、策略表、PSI / Drift 摘要
- [[wiki/games/daily_539]] — 539 現役策略、信號窮盡與 MicroFish WATCH 條件
- [[wiki/games/power_lotto]] — 威力彩現役策略、WATCH / PROVISIONAL 摘要
- [[wiki/system/orchestrator]] — Agent Orchestrator 架構與狀態機
- [[wiki/system/decision_engine]] — Decision V3 / Stage 1-6 摘要
- [[wiki/lessons/key_lessons]] — L14~L107 教訓索引（含缺號說明）

## 近期 Project 狀態

- 2026-04-20：部署鍵收斂為 `DAILY_539: acb_1bet`、`POWER_LOTTO: midfreq_fourier_2bet`，`BIG_LOTTO` 維持監控。
- 2026-04-20：每週監控固定走 `tools/check_draw_status.sh`、`tools/weekly_health_report.py` 與 weekly LaunchAgent。
- 2026-04-20：一次性會話工具已歸檔至 `tools/archive/`，後續以可追溯、可重現為優先。