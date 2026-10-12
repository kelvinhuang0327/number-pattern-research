"""
orchestrator/patch_validator.py
────────────────────────────────────────────────────────────────────────────────
MLB 模型補丁科學驗證引擎。

流程:
  1. 找到最新 COMPLETED model-patch-* 任務及對應 insight
  2. 從 research/trade_ledger.jsonl 載入真實結算紀錄（leakage-free）
  3. 計算 BEFORE / AFTER 基準指標（Brier Score, LogLoss, Accuracy, ROI, CLV）
  4. 執行統計顯著性檢驗（n >= 150 硬性門檻）
  5. 按 regime 分解評估一致性
  6. 決策：KEEP_PATCH / REJECT_PATCH / PARTIAL_KEEP / INSUFFICIENT_DATA
  7. 回寫 insight 狀態（VALIDATED / FAILED）
  8. 輸出 mlb_patch_validation_report.md

⚠️  安全規則
  - 不使用開賽後資訊作為特徵
  - 不接受小隨機提升（Brier 相對改善 < 0.5% → 標記 noise）
  - 不修改 live 下注邏輯（strategy/, telegram_bot/, live/）
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from orchestrator import training_memory

logger = logging.getLogger(__name__)

# ── 路徑常數 ─────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).parent.parent
TRADE_LEDGER_PATH = _REPO_ROOT / "research" / "trade_ledger.jsonl"
POSTGAME_PATH = _REPO_ROOT / "data" / "wbc_backend" / "reports" / "postgame_results.jsonl"
INSIGHTS_PATH = _REPO_ROOT / "runtime" / "agent_orchestrator" / "insights.json"
REPORT_OUTPUT_PATH = _REPO_ROOT / "research" / "mlb_patch_validation_report.md"
SNAPSHOTS_DIR = _REPO_ROOT / "research" / "patch_snapshots"

# ── 門檻常數 ─────────────────────────────────────────────────────────────────
MIN_SAMPLE_PREFERRED = 150    # 硬性統計顯著門檻
MIN_SAMPLE_ABSOLUTE  = 30     # 最低可接受門檻（標記 WEAK_SIGNAL）
BRIER_REL_IMPROVE_THRESHOLD  = 0.005   # 0.5% 相對改善
LOGLOSS_REL_IMPROVE_THRESHOLD = 0.005
ROI_ABSOLUTE_MIN_IMPROVE     = 0.005   # 0.5% 絕對 ROI 改善

# ── 安全封鎖前綴 ──────────────────────────────────────────────────────────────
_BLOCKED_PATHS = ("strategy/", "telegram_bot/", "live/", "data/tsl_crawler", "data/live_updater")


# ─────────────────────────────────────────────────────────────────────────────
# 公開介面
# ─────────────────────────────────────────────────────────────────────────────

def run_patch_validation(patch_task: dict, insight: dict) -> dict:
    """
    執行一次完整補丁驗證。回傳 ValidationResult dict。

    ValidationResult keys:
      decision       : KEEP_PATCH | REJECT_PATCH | PARTIAL_KEEP | INSUFFICIENT_DATA
      sample_size    : int
      before_metrics : dict
      after_metrics  : dict (stub worker 無實際程式碼變更時與 before 相同)
      regime_breakdown : dict[str, dict]
      statistical_note : str
      risk_notes     : list[str]
      patch_task_id  : int
      insight_id     : str
    """
    risk_notes: list[str] = []

    # 1. 安全檢查：target_files 不得觸及 live 路徑
    for tf in insight.get("target_files", []):
        if any(tf.startswith(p) for p in _BLOCKED_PATHS):
            risk_notes.append(f"BLOCKED: target_file '{tf}' is in a live-betting protected path")

    # 2. 載入結算紀錄（leakage-free: 僅使用 pregame predicted_prob）
    records = _load_settled_records()
    n = len(records)

    # 3. Try loading real prediction snapshots (produced by calibration_patch_runner)
    task_id = patch_task.get("id")
    snap_before, snap_after = _load_prediction_snapshots(task_id)

    if snap_before and snap_after:
        # Real before/after snapshots exist → compare directly
        before = _compute_metrics(snap_before)
        after  = _compute_metrics(snap_after)
        n_snap_b = len(snap_before)
        n_snap_a = len(snap_after)
        statistical_note = (
            f"SNAPSHOT_COMPARISON: {n_snap_b} before / {n_snap_a} after predictions "
            f"from calibration_patch_runner (task #{task_id}). "
            f"Method: {snap_after[0].get('calibration_method', 'unknown') if snap_after else 'unknown'}"
        )
        decision = _decide(before, after, max(n_snap_b, n_snap_a), risk_notes)
    else:
        # Fallback: no snapshots → check for stub / sample size
        before = _compute_metrics(records) if records else _empty_metrics()
        worker_is_stub = _detect_stub_completion(patch_task)
        if worker_is_stub:
            after = before.copy()
            after["note"] = "stub_worker_no_real_change"
            statistical_note = (
                "STUB_WORKER: patch task completed via fake worker — no code was actually changed. "
                "Before/After metrics are identical. Cannot assess improvement."
            )
            decision = "INSUFFICIENT_DATA"
        elif n < MIN_SAMPLE_ABSOLUTE:
            after = before.copy()
            statistical_note = f"SAMPLE_TOO_SMALL: only {n} settled records (minimum {MIN_SAMPLE_ABSOLUTE})"
            decision = "INSUFFICIENT_DATA"
        elif n < MIN_SAMPLE_PREFERRED:
            after = before.copy()  # no real split possible
            statistical_note = (
                f"WEAK_SIGNAL: {n} records available (preferred >= {MIN_SAMPLE_PREFERRED}). "
                "Metrics computed but may not generalise."
            )
            decision = _decide(before, after, n, risk_notes)
        else:
            # Split into pre/post by record order (walk-forward proxy)
            midpoint = n // 2
            before_records = records[:midpoint]
            after_records  = records[midpoint:]
            before = _compute_metrics(before_records)
            after  = _compute_metrics(after_records)
            statistical_note = f"WALK_FORWARD: {midpoint} baseline / {n - midpoint} evaluation records"
            decision = _decide(before, after, n, risk_notes)

    # 5. Regime breakdown（全量記錄）
    regime_breakdown = _regime_breakdown(records)

    result: dict = {
        "patch_task_id": patch_task.get("id"),
        "insight_id": insight.get("id"),
        "signal_state_type": insight.get("source_signal_state_type"),
        "category": insight.get("category"),
        "sample_size": n,
        "decision": decision,
        "before_metrics": before,
        "after_metrics": after,
        "regime_breakdown": regime_breakdown,
        "statistical_note": statistical_note,
        "risk_notes": risk_notes,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }

    # 6. 寫入報告
    _write_report(result, patch_task, insight)

    # 7. 回寫 insight 狀態
    _update_insight_state(insight["id"], decision, patch_task.get("id"))

    # 8. 記錄到訓練記憶（讓排程器學習哪些方法有效）
    try:
        brier_before = before.get("brier_score") or 0.0
        brier_after = after.get("brier_score") or brier_before
        logloss_before = before.get("log_loss") or 0.0
        logloss_after = after.get("log_loss") or logloss_before
        training_memory.record_patch_result(
            patch_task_id=patch_task.get("id") or 0,
            insight_id=insight.get("id") or "",
            category=insight.get("category") or insight.get("source_signal_state_type") or "unknown",
            method=insight.get("source_signal_state_type") or "unknown",
            decision=decision,
            brier_delta=brier_before - brier_after,
            logloss_delta=logloss_before - logloss_after,
            n_samples=n,
            regime_breakdown=regime_breakdown,
        )
    except Exception as _tm_exc:
        logger.warning("[PatchValidator] training_memory 記錄失敗（不影響主流程）: %s", _tm_exc)

    logger.info(
        "[PatchValidator] task #%s → decision=%s  n=%d  Brier_before=%.4f",
        patch_task.get("id"), decision, n, before.get("brier_score", float("nan")),
    )
    return result


def find_latest_completed_patch_task() -> Optional[dict]:
    """從 DB 找最新 COMPLETED model-patch-* 任務。"""
    from orchestrator import db
    tasks = db.list_tasks(limit=200)
    for t in tasks:
        sst = t.get("signal_state_type", "")
        if sst.startswith("model_patch_") and t.get("status") == "COMPLETED":
            return t
    return None


def find_insight_for_patch(patch_task: dict) -> Optional[dict]:
    """根據 patch_task 的 signal_state_type 反查 insight。"""
    if not INSIGHTS_PATH.exists():
        return None
    data = json.loads(INSIGHTS_PATH.read_text(encoding="utf-8"))
    # patch signal_state_type = "model_patch_calibration"
    # insight signal_state_type = "deep_research_calibration"
    # mapping: strip "model_patch_" → "deep_research_"
    sst = patch_task.get("signal_state_type", "")
    category = sst.removeprefix("model_patch_")
    for ins in reversed(data):  # newest first
        if ins.get("source_signal_state_type") == f"deep_research_{category}":
            return ins
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 內部函式
# ─────────────────────────────────────────────────────────────────────────────

def _load_settled_records() -> list[dict]:
    """
    載入 trade_ledger.jsonl 中的結算紀錄（event_type == settlement）。
    僅保留有 predicted_prob 的紀錄（pregame 預測，leakage-free）。
    不使用 closing_odds 或任何開賽後欄位作為特徵。
    """
    if not TRADE_LEDGER_PATH.exists():
        return []
    records = []
    for line in TRADE_LEDGER_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("event_type") != "settlement":
            continue
        # 確保有 pregame 預測機率及結果
        if r.get("predicted_prob") is None or r.get("result") is None:
            continue
        records.append(r)
    return records


def _load_prediction_snapshots(
    task_id: Optional[int],
) -> tuple[list[dict], list[dict]]:
    """
    嘗試從 research/patch_snapshots/ 載入 before/after prediction snapshots。
    若不存在，回傳 ([], [])。
    snapshot 格式由 calibration_patch_runner._write_snapshot() 產出。
    """
    if task_id is None:
        return [], []
    before_path = SNAPSHOTS_DIR / f"{task_id}_before.jsonl"
    after_path  = SNAPSHOTS_DIR / f"{task_id}_after.jsonl"
    if not before_path.exists() or not after_path.exists():
        return [], []

    def _read(p: Path) -> list[dict]:
        rows = []
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows

    before = _read(before_path)
    after  = _read(after_path)
    if not before or not after:
        return [], []
    logger.info("[PatchValidator] Loaded snapshots: %d before / %d after (task #%s)", len(before), len(after), task_id)
    return before, after


def _outcome(record: dict) -> int:
    """result='win' → 1 (預測方向勝出), 'loss' → 0"""
    return 1 if record.get("result") == "win" else 0


def _compute_metrics(records: list[dict]) -> dict:
    """
    計算 Brier Score, LogLoss, Accuracy, ROI, CLV。
    全部使用 pregame predicted_prob（leakage-free）。
    """
    if not records:
        return _empty_metrics()

    n = len(records)
    brier_sum = 0.0
    logloss_sum = 0.0
    correct = 0
    total_roi = 0.0
    clv_values: list[float] = []
    eps = 1e-7

    for r in records:
        p = float(r["predicted_prob"])
        y = _outcome(r)
        brier_sum   += (p - y) ** 2
        logloss_sum += -(y * math.log(p + eps) + (1 - y) * math.log(1 - p + eps))
        # Accuracy: bet placed on the side with p > 0.5
        predicted_win = 1 if p >= 0.5 else 0
        if predicted_win == y:
            correct += 1
        total_roi += float(r.get("roi") or r.get("pnl") or 0.0)
        clv = r.get("clv")
        if clv is not None:
            clv_values.append(float(clv))

    avg_clv = sum(clv_values) / len(clv_values) if clv_values else None

    return {
        "n": n,
        "brier_score":  round(brier_sum / n, 6),
        "log_loss":     round(logloss_sum / n, 6),
        "accuracy":     round(correct / n, 4),
        "avg_roi":      round(total_roi / n, 4),
        "avg_clv":      round(avg_clv, 4) if avg_clv is not None else None,
        "clv_available": len(clv_values),
    }


def _empty_metrics() -> dict:
    return {
        "n": 0,
        "brier_score": None,
        "log_loss": None,
        "accuracy": None,
        "avg_roi": None,
        "avg_clv": None,
        "clv_available": 0,
    }


def _regime_breakdown(records: list[dict]) -> dict:
    """
    按 regime 欄位分組計算指標。
    若 regime 為 WBC Pool label（Pool A/B/C/D），原樣使用；
    若包含 MLB regime label（small_edge / favorites / underdogs / etc.），亦原樣使用。
    """
    groups: dict[str, list[dict]] = {}
    for r in records:
        regime = str(r.get("regime") or "unknown")
        groups.setdefault(regime, []).append(r)

    return {
        regime: _compute_metrics(group)
        for regime, group in sorted(groups.items())
    }


def _decide(before: dict, after: dict, n: int, risk_notes: list[str]) -> str:
    """
    三種決策邏輯（僅在有 before/after 分割時調用）。
    """
    if not before.get("brier_score") or not after.get("brier_score"):
        return "INSUFFICIENT_DATA"

    brier_before = before["brier_score"]
    brier_after  = after["brier_score"]
    logloss_before = before.get("log_loss") or 0.0
    logloss_after  = after.get("log_loss") or 0.0

    brier_rel_improve = (brier_before - brier_after) / (brier_before + 1e-9)
    logloss_rel_improve = (logloss_before - logloss_after) / (logloss_before + 1e-9)

    # 迴歸：任一指標惡化
    if brier_after > brier_before * 1.01 or logloss_after > logloss_before * 1.01:
        return "REJECT_PATCH"

    # 噪音：改善不足門檻
    if brier_rel_improve < BRIER_REL_IMPROVE_THRESHOLD and logloss_rel_improve < LOGLOSS_REL_IMPROVE_THRESHOLD:
        return "REJECT_PATCH"  # noise — not meaningful improvement

    # 樣本過少：有訊號但不確定
    if n < MIN_SAMPLE_PREFERRED:
        return "PARTIAL_KEEP"

    return "KEEP_PATCH"


def _detect_stub_completion(patch_task: dict) -> bool:
    """
    判斷補丁任務是否由 stub worker 完成（未真實變更程式碼）。
    標誌：completed_text 包含固定範本字串。
    """
    text = patch_task.get("completed_text") or ""
    stub_markers = [
        "程式碼自動生成",
        "copilot-daemon",
        "fake_completion",
        "智能建議整合\n- 測試案例產生",
    ]
    return any(marker in text for marker in stub_markers)


def _update_insight_state(insight_id: str, decision: str, validation_task_id: Optional[int]) -> None:
    """根據決策更新 insights.json 中對應 insight 的狀態。"""
    if not INSIGHTS_PATH.exists():
        return
    data = json.loads(INSIGHTS_PATH.read_text(encoding="utf-8"))
    for ins in data:
        if ins["id"] != insight_id:
            continue
        if decision == "KEEP_PATCH":
            ins["status"] = "VALIDATED"
            ins["validation_task_id"] = validation_task_id
            ins["validated_at"] = datetime.now(timezone.utc).isoformat()
        elif decision == "REJECT_PATCH":
            ins["status"] = "FAILED"
            ins["failed_at"] = datetime.now(timezone.utc).isoformat()
            ins["failure_reason"] = "no_statistically_significant_improvement"
        elif decision in ("PARTIAL_KEEP", "INSUFFICIENT_DATA"):
            ins["status"] = "PARTIAL"
            ins["partial_at"] = datetime.now(timezone.utc).isoformat()
            ins["partial_reason"] = decision
        break
    INSIGHTS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("[PatchValidator] insight %s → status updated (%s)", insight_id, decision)


def _write_report(result: dict, patch_task: dict, insight: dict) -> None:
    """產出 research/mlb_patch_validation_report.md。"""
    bm = result["before_metrics"]
    am = result["after_metrics"]
    rb = result["regime_breakdown"]
    decision = result["decision"]

    def fmt(v) -> str:
        if v is None:
            return "N/A"
        if isinstance(v, float):
            return f"{v:.4f}"
        return str(v)

    def decision_badge(d: str) -> str:
        badges = {
            "KEEP_PATCH":        "✅ KEEP_PATCH",
            "REJECT_PATCH":      "❌ REJECT_PATCH",
            "PARTIAL_KEEP":      "⚠️  PARTIAL_KEEP",
            "INSUFFICIENT_DATA": "🔲 INSUFFICIENT_DATA",
        }
        return badges.get(d, d)

    regime_rows = ""
    for regime, m in rb.items():
        regime_rows += (
            f"| {regime} | {m['n']} | {fmt(m.get('brier_score'))} | "
            f"{fmt(m.get('log_loss'))} | {fmt(m.get('accuracy'))} | {fmt(m.get('avg_roi'))} |\n"
        )

    risk_section = "\n".join(f"- {r}" for r in result["risk_notes"]) or "_None identified_"

    # Determine whether improvement is real
    stub_note = ""
    if am.get("note") == "stub_worker_no_real_change":
        stub_note = (
            "\n> ⚠️  **NOTICE**: This patch was executed by a stub worker that does not "
            "actually modify code. Before/After metrics are identical. "
            "A real improvement assessment requires a genuine code-executing worker.\n"
        )

    md = f"""# MLB 模型補丁驗證報告

**生成時間**: {result['evaluated_at']}
**決策**: {decision_badge(decision)}

---

## 1. 補丁描述

| 欄位 | 值 |
|------|-----|
| Patch Task ID | #{patch_task.get('id')} |
| 任務名稱 | {patch_task.get('title', 'N/A')} |
| Signal State Type | `{result.get('signal_state_type')}` |
| 類別 | `{result.get('category')}` |
| Target Files | {', '.join(f'`{f}`' for f in insight.get('target_files', []))} |
| Expected Metric | {insight.get('expected_metric', 'N/A')} |
| Insight ID | `{insight.get('id')}` |
| Weakness | {insight.get('weakness', 'N/A')} |
{stub_note}
---

## 2. 統計說明

**樣本數**: {result['sample_size']} 筆結算紀錄

**注意**: {result['statistical_note']}

> 統計顯著門檻：樣本 ≥ {MIN_SAMPLE_PREFERRED}，Brier 相對改善 ≥ {BRIER_REL_IMPROVE_THRESHOLD*100:.1f}%

---

## 3. BEFORE vs AFTER 指標

| 指標 | BEFORE | AFTER | 變化 |
|------|--------|-------|------|
| 樣本數 | {fmt(bm.get('n'))} | {fmt(am.get('n'))} | — |
| Brier Score ↓ | {fmt(bm.get('brier_score'))} | {fmt(am.get('brier_score'))} | {_delta_str(bm.get('brier_score'), am.get('brier_score'), lower_is_better=True)} |
| LogLoss ↓ | {fmt(bm.get('log_loss'))} | {fmt(am.get('log_loss'))} | {_delta_str(bm.get('log_loss'), am.get('log_loss'), lower_is_better=True)} |
| Accuracy ↑ | {fmt(bm.get('accuracy'))} | {fmt(am.get('accuracy'))} | {_delta_str(bm.get('accuracy'), am.get('accuracy'), lower_is_better=False)} |
| Avg ROI | {fmt(bm.get('avg_roi'))} | {fmt(am.get('avg_roi'))} | {_delta_str(bm.get('avg_roi'), am.get('avg_roi'), lower_is_better=False)} |
| Avg CLV | {fmt(bm.get('avg_clv'))} | {fmt(am.get('avg_clv'))} | — |
| CLV Records | {fmt(bm.get('clv_available'))} | {fmt(am.get('clv_available'))} | — |

---

## 4. Regime 分解評估

| Regime | n | Brier ↓ | LogLoss ↓ | Accuracy ↑ | Avg ROI |
|--------|---|---------|-----------|------------|---------|
{regime_rows}
---

## 5. 統計顯著性評估

| 條件 | 狀態 |
|------|------|
| 樣本數 ≥ {MIN_SAMPLE_PREFERRED} | {'✅' if result['sample_size'] >= MIN_SAMPLE_PREFERRED else f'❌ (actual: {result["sample_size"]})'} |
| Brier 相對改善 ≥ {BRIER_REL_IMPROVE_THRESHOLD*100:.1f}% | {_check_improve(bm.get('brier_score'), am.get('brier_score'), BRIER_REL_IMPROVE_THRESHOLD, lower_is_better=True)} |
| LogLoss 相對改善 ≥ {LOGLOSS_REL_IMPROVE_THRESHOLD*100:.1f}% | {_check_improve(bm.get('log_loss'), am.get('log_loss'), LOGLOSS_REL_IMPROVE_THRESHOLD, lower_is_better=True)} |
| Stub Worker（未真實變更） | {'⚠️  YES — 指標無意義' if am.get('note') == 'stub_worker_no_real_change' else '✅ 無'} |

---

## 6. 風險評估

{risk_section}

---

## 7. 最終決策

### {decision_badge(decision)}

**決策理由**:

{_decision_rationale(decision, result)}

---

## 8. 後續行動

{_next_steps(decision)}

---

_此報告由 `orchestrator/patch_validator.py` 自動生成。請勿手動修改。_
"""

    REPORT_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUTPUT_PATH.write_text(md, encoding="utf-8")
    logger.info("[PatchValidator] Report written → %s", REPORT_OUTPUT_PATH)


def _delta_str(before, after, lower_is_better: bool) -> str:
    if before is None or after is None:
        return "N/A"
    delta = after - before
    if lower_is_better:
        symbol = "↓" if delta < 0 else ("↑" if delta > 0 else "—")
        colour = "✅" if delta < 0 else ("❌" if delta > 0 else "")
    else:
        symbol = "↑" if delta > 0 else ("↓" if delta < 0 else "—")
        colour = "✅" if delta > 0 else ("❌" if delta < 0 else "")
    return f"{colour} {delta:+.4f} {symbol}"


def _check_improve(before, after, threshold: float, lower_is_better: bool) -> str:
    if before is None or after is None:
        return "N/A"
    rel = (before - after) / (before + 1e-9) if lower_is_better else (after - before) / (before + 1e-9)
    return "✅" if rel >= threshold else f"❌ ({rel*100:+.2f}%)"


def _decision_rationale(decision: str, result: dict) -> str:
    n = result["sample_size"]
    if decision == "INSUFFICIENT_DATA":
        stub = result["after_metrics"].get("note") == "stub_worker_no_real_change"
        if stub:
            return (
                "補丁任務由 stub worker 執行，未真實變更任何程式碼。"
                "無法評估實際改善效果。需要真實的程式碼執行工作器後才能重新驗證。"
            )
        return f"結算紀錄數量（{n}）不足最低門檻（{MIN_SAMPLE_ABSOLUTE}），無法進行統計評估。"
    if decision == "REJECT_PATCH":
        return "補丁未達到統計顯著的改善門檻，或指標出現迴歸。標記為 FAILED 以防止類似補丁重複生成。"
    if decision == "PARTIAL_KEEP":
        return f"有部分改善訊號，但樣本數（{n}）低於推薦門檻（{MIN_SAMPLE_PREFERRED}）。建議累積更多數據後重新驗證。"
    if decision == "KEEP_PATCH":
        return "所有指標達到統計顯著改善門檻，且樣本量充足。補丁通過驗證。"
    return "未知決策。"


def _next_steps(decision: str) -> str:
    steps = {
        "KEEP_PATCH": (
            "1. Insight 狀態已更新為 `VALIDATED`\n"
            "2. 允許生成同類別的下一輪補丁\n"
            "3. 將改善結果納入下次系統審計基準"
        ),
        "REJECT_PATCH": (
            "1. Insight 狀態已更新為 `FAILED`\n"
            "2. 同類別補丁暫停生成（避免重複無效嘗試）\n"
            "3. 建議重新審查 insight 中的 weakness 描述是否準確"
        ),
        "PARTIAL_KEEP": (
            "1. Insight 狀態已更新為 `PARTIAL`\n"
            "2. 建議累積 ≥ 150 筆新數據後重新執行驗證\n"
            "3. 可在特定 regime 內謹慎應用"
        ),
        "INSUFFICIENT_DATA": (
            "1. Insight 狀態已更新為 `PARTIAL`\n"
            "2. 需要真實執行的 worker（非 stub）重新運行補丁\n"
            "3. 或等待更多結算紀錄累積後重試"
        ),
    }
    return steps.get(decision, "請人工審查。")
