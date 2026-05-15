from pathlib import Path

path = Path('/Users/kelvin/Kelvin-WorkSpace/LotteryNew/MEMORY.md')
lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
marker = '- `data/weekly_health_20260419.json`'
idx = next(i for i, line in enumerate(lines) if line.startswith(marker))
clean_tail = [
    '- `data/weekly_health_20260419.json` — 健康週報快照',
    '- `data/trigger_validation_tests.json` — exit trigger mock tests (all_pass: true)',
    '- `data/system_readiness_2026_04_19.json` — 整合驗證報告',
    '- `tools/weekly_health_report.py` — 新增獨立工具，可每週手動執行',
    '',
    '### 已知設計注意事項',
    '- `psi_is_valid_trigger=False` 是 BIG_LOTTO 目前實際狀態（PSI 歷史 p75=0.572，遠超現值 0.107，系統認為 PSI 不是有效觸發器）',
    '- Mock tests 需要 `force_psi_valid=True` 才能測試 Level 1/2 純邏輯',
    '- Case 3（GREEN 狀態）需傳入 `consecutive_psi=[stable values]` 覆蓋 `psi_gt_0_2_3x=True` 的持久旗標',
]
path.write_text('\n'.join(lines[:idx] + clean_tail) + '\n', encoding='utf-8')
print('repaired MEMORY.md tail at line', idx + 1)
