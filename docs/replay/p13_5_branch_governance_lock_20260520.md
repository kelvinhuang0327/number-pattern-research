# P13.5 Branch Governance Lock — 單一 active branch 政策

**Phase**: P13.5  
**Date**: 2025-05-20  
**Author**: Replay Governance System  
**Classification**: BRANCH_GOVERNANCE_PASS

---

## 1. 為何鎖單一 Active Branch

多 agent 並發環境下（15 claude/* worktrees、4 /private/tmp worktree、1 LotteryNew-clean worktree），分支爆炸（branch sprawl）已成系統性風險：

- 109 本地分支、80 遠端非 merged 分支 → PR context 碎片化
- 15 個 claude/* worktree 各自持有 HEAD → agent 交接時難以確認「目前在哪」
- 無 merged/ 命名空間 → 已完成分支與進行中分支混雜，難以 audit
- 多 agent 同時 commit 到不同分支 → 互相覆蓋、合併地獄

**鎖定原則**：整合後唯一的 active branch 為 `main`。所有其他分支歸入 `merged/` 命名空間，保留歷史但不再主動開發。

---

## 2. 合併後唯一 Active Branch = main

```
整合前：feat/p0-single-repo-stabilization-p1-catalog-plan-20260519 (canonical)
整合後：main
```

- Canonical branch（14 commits ahead of origin/main）→ merge commit 進 main
- 所有 agent 交接後首先執行 `git rev-parse --abbrev-ref HEAD` 確認在 main
- 新工作不允許直接在 main 開發，需明確授權後才可建立新分支

---

## 3. merged/ 命名空間說明

`merged/` 前綴代表「已完成或已歸檔」的分支。例如：

```
feat/p1-catalog-...  →  merged/feat/p1-catalog-...
claude/busy-leavitt  →  merged/claude/busy-leavitt
auto/inbox/20260424  →  merged/auto/inbox/20260424
```

命名規則：
- 本地：`git branch -m <name> merged/<name>`（rename，不刪除）
- 遠端：僅記錄，不刪除（spec 禁止 `-d`/`-D`/force-push）
- 可隨時還原：`git branch -m merged/<name> <name>`

整合後 merged/ 下預計有：
- **128** 本地分支
- **80** 遠端分支（記錄於 p13_6 audit JSON，未執行 rename）

---

## 4. Hard Rules（禁止操作）

以下操作在任何情況下均被禁止，不需用戶確認：

| 操作 | 原因 |
|------|------|
| `git branch -d <name>` | 本地分支刪除，歷史不可回溯 |
| `git branch -D <name>` | 強制刪除，更危險 |
| `git push --force` | 覆蓋遠端歷史 |
| `git push --force-with-lease` | 同上，即使有安全檢查 |
| `git reset --hard` | 不可逆丟棄 working tree |
| `git worktree remove` (active) | 損失 active worktree 未提交工作 |

---

## 5. Explicit Authorization（明確授權）

新增分支前，agent 必須等待用戶輸入以下確認短語（精確匹配）：

```
YES create new branch for <reason>
```

若無此短語，即使任務需要，也不得建立新分支。

同樣，新增 worktree 前需要：

```
YES create new worktree for <reason>
```

---

## 6. Merge-Back Policy（Canonical → main）

- 採用 **merge commit**（`--no-ff`），明確保留 P0-P13 的 commit 歷史
- 不允許 `--squash`（會丟失個別 commit 歷史）
- 不允許 `rebase`（改寫歷史）
- Merge commit message 格式：

```
Merge canonical P0-P13: feat/p0-single-repo-stabilization-p1-catalog-plan-20260519

P13.6 Branch Consolidation — merge 128 local branch histories into main.
Production rows before: 460 / after: 460 (no DB write).
Governance guard: BRANCH_GOVERNANCE_PASS.
```

---

## 7. 還原方法

若需要重新啟用某個已歸檔分支：

```bash
# 本地還原
git branch -m merged/<name> <name>

# 確認
git branch --list '<name>'

# 繼續工作...
# 完成後重新歸檔
git branch -m <name> merged/<name>
```

注意：遠端分支未執行 rename，仍在原始名稱下，可直接 fetch。

---

## 8. Agent 交接 SOP

每次 agent 重新接手任務時，必須先執行以下檢查序列（順序不可跳過）：

```
# Step 1 — 確認在 main
git rev-parse --abbrev-ref HEAD
# 若不在 main → STOP，不得繼續，必須回報給用戶

# Step 2 — 確認 DB 行數
python -c "import sqlite3; c=sqlite3.connect('lottery_api/data/lottery_v2.db'); print(c.execute('SELECT COUNT(*) FROM strategy_prediction_replays').fetchone()[0])"
# 必須 = 460，否則 STOP

# Step 3 — 確認測試通過
python -m pytest tests/ -q --no-header 2>/dev/null | tail -3
# 必須 passed >= 391，否則 STOP

# Step 4 — 執行 governance guard
python scripts/replay_branch_governance_guard.py \
  --expected-branch main \
  --expected-rows 460 \
  --json-out /tmp/gov_check.json
# 必須 BRANCH_GOVERNANCE_PASS，否則 STOP
```

只有全部 PASS，agent 才可開始工作。

---

*生成自：`scripts/replay_branch_governance_guard.py` — P13.5 Branch Governance Guard*  
*Audit JSON：`outputs/replay/p13_5_branch_audit_20260520.json`*
