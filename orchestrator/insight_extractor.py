"""
MLB Prediction Insight Extractor
=============================
讀取已完成的 MLB 審計任務 → 提取結構化改善洞見 → 存入 insights.json。
洞見驅動 patch_task_generator 生成「模型修補任務」，形成閉迴圈：

    audit → insight → patch → validation → archive

Hard rules:
- 只讀 COMPLETED 任務，不修改任何 live 投注邏輯
- 同一 focus_area 同一狀態不重複發出洞見（idempotent）
- insights.json 最多保留 50 筆，避免無限成長
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from orchestrator import db

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
INSIGHTS_PATH = _REPO_ROOT / "runtime" / "agent_orchestrator" / "insights.json"

# ── signal_state_type → 洞見模板 ────────────────────────────────────────────
# 每個審計類別對應一個標準洞見：包含弱點描述、證據來源、目標程式碼、預期指標。
# target_files 只允許 research/ evaluation/ data/（非 live 檔案）。
# KEY：使用 signal_state_type（實際儲存在 DB 欄位），非 focus_area（未儲存在 DB）。
AUDIT_TO_INSIGHT: dict[str, dict] = {
    "deep_research_calibration": {
        "category": "calibration",
        "weakness": "各 regime 的 Brier score / LogLoss 基線未量化，校準器（Platt vs Isotonic）尚未對比",
        "evidence_files": [
            "data/wbc_backend/reports/mlb_decision_quality_report.json",
            "data/wbc_backend/reports/mlb_regime_paper_report.json",
        ],
        "target_files": [
            "wbc_backend/research/mlb_model_rebuild.py",
            "wbc_backend/evaluation/mlb_decision_quality.py",
        ],
        "expected_metric": "小 regime Brier score 改善 >= 2%",
        "priority": 1,
    },
    "deep_research_feature": {
        "category": "feature_quality",
        "weakness": "先發 / 牛棚特徵的 look-ahead leakage 風險未驗證，predictive power 未排名",
        "evidence_files": [
            "data/wbc_backend/reports/mlb_regime_paper_report.json",
            "data/wbc_backend/reports/mlb_decision_quality_report.json",
        ],
        "target_files": [
            "wbc_backend/research/mlb_regime_feature_redesign.py",
            "wbc_backend/evaluation/mlb_decision_quality.py",
        ],
        "expected_metric": "leakage 特徵清零，移除後 Brier delta < -1%",
        "priority": 2,
    },
    "deep_research_regime": {
        "category": "regime_detection",
        "weakness": "small_edge / weak_starter_mismatch 邊界誤分類率未量化，regime precision < 75%",
        "evidence_files": [
            "data/wbc_backend/reports/mlb_regime_paper_report.json",
            "data/wbc_backend/reports/mlb_decision_quality_report.json",
        ],
        "target_files": [
            "wbc_backend/research/mlb_model_rebuild.py",
            "wbc_backend/research/mlb_regime_feature_redesign.py",
        ],
        "expected_metric": "regime precision >= 75%，誤分類率 < 20%",
        "priority": 2,
    },
    "deep_research_odds_quality": {
        "category": "clv_odds_quality",
        "weakness": "外部收盤賠率覆蓋率不足，CLV 計算有系統性缺口（staleness / timestamp gap）",
        "evidence_files": [
            "data/mlb_context/odds_timeline.jsonl",
            "data/mlb_context/external_closing_state.json",
        ],
        "target_files": [
            "data/odds_api_client.py",
            "data/mlb_live_pipeline.py",
        ],
        "expected_metric": "外部收盤覆蓋率 >= 85%，median CLV 誤差 < 0.02",
        "priority": 3,
    },
    "deep_research_feedback": {
        "category": "feedback_loop",
        "weakness": "結算注入完整性未驗證，GOOD_BET / BAD_BET 標籤可靠性與按 regime 的 ROI 未追蹤",
        "evidence_files": [
            "research/trade_ledger.jsonl",
            "research/roi_tracking.json",
            "data/wbc_backend/reports/mlb_decision_quality_report.json",
        ],
        "target_files": [
            "wbc_backend/evaluation/mlb_decision_quality.py",
        ],
        "expected_metric": "結算率 >= 95%，GOOD_BET 標籤準確率 >= 90%",
        "priority": 3,
    },
    "deep_research_backtest_validity": {
        "category": "backtest_validity",
        "weakness": "walk-forward 切割完整性與開賽後賠率污染率未驗證",
        "evidence_files": [
            "data/mlb_context/odds_timeline.jsonl",
            "data/wbc_backend/reports/mlb_regime_paper_report.json",
        ],
        "target_files": [
            "wbc_backend/research/mlb_model_rebuild.py",
            "wbc_backend/evaluation/mlb_decision_quality.py",
        ],
        "expected_metric": "split leakage < 2%，所有 pregame 特徵使用開賽前 timestamp",
        "priority": 1,
    },
}

# ── Lifecycle states ──────────────────────────────────────────────────────────
# PENDING       → 洞見已提取，等待 patch task 生成
# PATCH_QUEUED  → patch task 已建立（有 patch_task_id）
# VALIDATED     → validation task 已建立（閉迴圈完成一輪）
# ARCHIVED      → 超過 max 或手動清除


def _load_insights() -> list[dict]:
    if not INSIGHTS_PATH.exists():
        return []
    try:
        return json.loads(INSIGHTS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("[InsightExtractor] Failed to load insights.json, starting fresh.")
        return []


def _save_insights(insights: list[dict]) -> None:
    INSIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    INSIGHTS_PATH.write_text(
        json.dumps(insights, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def extract_insights_from_completed_tasks() -> list[dict]:
    """
    掃描最近 COMPLETED 的 MLB 審計任務 → 為新完成的審計發出洞見記錄。
    每個 signal_state_type 全域最多一筆 PENDING / PATCH_QUEUED（cross-run dedup）。
    同一次呼叫內同 signal_state_type 也只發出一次（within-run dedup）。
    回傳本次新增的洞見清單。
    """
    existing = _load_insights()

    # ── Cross-run dedup：已有 PENDING 或 PATCH_QUEUED 的 signal_state_type 不再重複 ──
    active_keys: set[str] = {
        ins["source_signal_state_type"]
        for ins in existing
        if ins.get("status") in ("PENDING", "PATCH_QUEUED")
    }

    # 取最近 30 個 COMPLETED 的 MLB 審計任務
    # NOTE: focus_area 未儲存至 DB；改用 signal_state_type（實際欄位）作為 key
    completed = [
        t for t in db.list_tasks(limit=30)
        if t.get("status") == "COMPLETED"
        and t.get("signal_state_type") in AUDIT_TO_INSIGHT
        and t.get("signal_state_type") not in active_keys
    ]

    new_insights: list[dict] = []
    seen: set[str] = set()  # within-run dedup
    for task in completed:
        signal_state_type = task["signal_state_type"]

        # ── Within-run dedup ──
        if signal_state_type in seen:
            logger.debug(
                "[InsightExtractor] duplicate insight skipped (signal=%s, task_id=%s)",
                signal_state_type, task["id"],
            )
            continue
        seen.add(signal_state_type)

        mapping = AUDIT_TO_INSIGHT[signal_state_type]
        insight = {
            "id": str(uuid.uuid4())[:8],
            "source_task_id": task["id"],
            "source_signal_state_type": signal_state_type,
            "source_title": task.get("title", ""),
            "category": mapping["category"],
            "weakness": mapping["weakness"],
            "evidence_files": mapping["evidence_files"],
            "target_files": mapping["target_files"],
            "expected_metric": mapping["expected_metric"],
            "priority": mapping["priority"],
            "status": "PENDING",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        new_insights.append(insight)
        logger.info(
            "[InsightExtractor] New insight from task #%s (signal=%s): %s",
            task["id"], signal_state_type, mapping["weakness"],
        )

    if new_insights:
        all_insights = existing + new_insights
        # 保留最新 50 筆
        _save_insights(all_insights[-50:])

    return new_insights


def get_pending_insights() -> list[dict]:
    """回傳 status=PENDING 的洞見，按 priority 升序排列（數字小 = 優先度高）。"""
    return sorted(
        [ins for ins in _load_insights() if ins.get("status") == "PENDING"],
        key=lambda x: x.get("priority", 9),
    )


def get_patch_queued_insights() -> list[dict]:
    """回傳 status=PATCH_QUEUED 的洞見（patch task 已建立，等待 validation）。"""
    return [ins for ins in _load_insights() if ins.get("status") == "PATCH_QUEUED"]


def mark_insight_patch_queued(insight_id: str, patch_task_id: int) -> None:
    """patch task 建立後呼叫，更新洞見狀態為 PATCH_QUEUED。"""
    insights = _load_insights()
    for ins in insights:
        if ins["id"] == insight_id:
            ins["status"] = "PATCH_QUEUED"
            ins["patch_task_id"] = patch_task_id
            ins["patched_at"] = datetime.now(timezone.utc).isoformat()
            break
    _save_insights(insights)
    logger.info("[InsightExtractor] Insight %s → PATCH_QUEUED (patch_task_id=%s)", insight_id, patch_task_id)


def mark_insight_validated(insight_id: str, validation_task_id: int) -> None:
    """validation task 建立後呼叫，更新洞見狀態為 VALIDATED。"""
    insights = _load_insights()
    for ins in insights:
        if ins["id"] == insight_id:
            ins["status"] = "VALIDATED"
            ins["validation_task_id"] = validation_task_id
            ins["validated_at"] = datetime.now(timezone.utc).isoformat()
            break
    _save_insights(insights)
    logger.info("[InsightExtractor] Insight %s → VALIDATED (validation_task_id=%s)", insight_id, validation_task_id)
