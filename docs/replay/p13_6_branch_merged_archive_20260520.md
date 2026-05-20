# P13.6 Branch Merged Archive — 分支整理計畫

**Phase**: P13.6  
**Date**: 2025-05-20  
**Policy**: RENAME_ONLY_NO_DELETION  
**Classification**: AUDIT_ONLY_NO_RENAME  
**Status**: ⚠️ AUDIT COMPLETE — 等待 GATE 1 用戶授權後執行

---

## 1. 審計摘要

| 類別 | 數量 | 行動 |
|------|------|------|
| 本地分支候選 (→ merged/) | **128** | `git branch -m <name> merged/<name>` (需 GATE 3 授權) |
| 已 merged 進 main 的本地分支 | **18** | 優先歸檔 |
| 未 merged 進 main 的本地分支 | **110** | 歸檔前需確認（GATE 4） |
| 遠端分支候選 | **80** | 僅記錄，不執行 rename（禁 force-push） |
| Worktree 候選 | **20** | 4 個 /private/tmp 建議移除（需確認） |
| 保護分支 | **1** (main) | 不得 rename、不得刪除 |

---

## 2. 本地分支按前綴分類

| 前綴 | 數量 | 說明 |
|------|------|------|
| `docs/` | 37 | 文件分支 |
| `codex/` | 27 | Codex 自動生成分支 |
| `claude/` | 15 | Claude worktree 分支（currently checked out） |
| `feat/` | 12 | 功能分支 |
| `auto/` | 11 | 自動化 inbox 分支 |
| `chore/` | 8 | 維護分支 |
| 其他 | 18 | backup, fix, replay, release, review, pr93-95... |

**特別注意**：
- `claude/*` 分支（15 個）目前都在 `.claude/worktrees/` worktree 中，**無法直接 rename**，需先移除 worktree 或確認 agent 不再使用
- `feat/p1-catalog-visibility-registry-expansion-20260518` 在 `LotteryNew-clean` worktree 中，**不在本次 rename 範圍**，需單獨協商
- `pr93`, `pr94`, `pr95` 在 `/private/tmp/` worktree 中，建議先移除 worktree

---

## 3. Worktree 清理計畫

### 建議移除（/private/tmp，非正式）
| Path | Branch | 說明 |
|------|--------|------|
| `/private/tmp/lottery-p3_1` | `codex/p3-1-artifact-normalization` | tmp worktree |
| `/private/tmp/lottery-pr93` | `pr93` | tmp worktree |
| `/private/tmp/lottery-pr94` | `pr94` | tmp worktree |
| `/private/tmp/lottery-pr95` | `pr95` | tmp worktree |

**移除方法**（需用戶確認，非本次 GATE 範圍）：
```bash
git worktree remove /private/tmp/lottery-p3_1
git worktree remove /private/tmp/lottery-pr93
git worktree remove /private/tmp/lottery-pr94
git worktree remove /private/tmp/lottery-pr95
```

### 保持不變
| Path | Branch | 說明 |
|------|--------|------|
| `LotteryNew-clean/` | `feat/p1-catalog-...` | 在用 worktree，不動 |
| `.claude/worktrees/*` (15) | `claude/*` | Agent worktrees，不動 |

---

## 4. 遠端分支政策

共 80 個遠端 `origin/*` 分支候選。

**本次不執行任何遠端操作**原因：
1. Spec 禁止 `git push --force`
2. 遠端分支 rename = push new + delete old → 需要 `git push origin :<old>` 即刪除操作
3. 刪除遠端分支屬於破壞性操作，需獨立 GATE

遠端分支將在後續版本中處理，或由 repo admin 在 GitHub 界面操作。
完整遠端分支清單見：`outputs/replay/p13_6_branch_merged_log_20260520.json`

---

## 5. 執行順序（GATE 授權後）

```
GATE 1  →  用戶: "YES proceed to merge canonical into main"
Step 4  →  merge canonical into main (--no-ff)
           驗證: 460 rows, 391 tests pass, drift PASS

GATE 2  →  用戶: "YES push main to origin"
Step 4b →  git push origin main

GATE 3  →  用戶: "YES archive merged-into-main branches"
Step 5a →  rename 18 個已 merged 本地分支 to merged/

GATE 4  →  用戶: "YES archive remaining local branches"
Step 5b →  rename 110 個未 merged 本地分支 to merged/
           (claude/* 15 個例外：active worktrees，跳過)

GATE 5  →  用戶: "YES commit and push merged namespace"
Step 6  →  commit + push
```

---

## 6. Hard Rules（再次確認）

- **禁止** `git branch -d <name>` — 改用 rename
- **禁止** `git branch -D <name>` — 改用 rename
- **禁止** `git push --force` — 任何情況均禁止
- **禁止** `git reset --hard` — 任何情況均禁止
- 所有 rename 均可逆：`git branch -m merged/<x> <x>`
- 若 merge 有衝突：STOP，不自動解決

---

## 7. 完整分支清單

詳細的每支 SHA、last commit date、ahead/behind main 資料見：

```
outputs/replay/p13_6_branch_merged_log_20260520.json
```

JSON schema:
```json
{
  "phase": "P13_6_BRANCH_MERGED_ARCHIVE",
  "policy": "RENAME_ONLY_NO_DELETION",
  "candidate_local_renames": [...],
  "candidate_remote_renames": [...],
  "candidate_worktrees_to_remove": [...],
  "renames_executed": [],
  "worktrees_removed": [],
  "deletions_executed": [],
  "classification": "AUDIT_ONLY_NO_RENAME"
}
```

---

*生成自：`scripts/_build_branch_audit.py` (read-only, one-shot)*  
*Governance Guard：`outputs/replay/p13_5_branch_audit_20260520.json` — BRANCH_GOVERNANCE_PASS*
