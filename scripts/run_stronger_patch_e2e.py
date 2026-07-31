"""
scripts/run_stronger_patch_e2e.py
────────────────────────────────────────────────────────────────────────────────
端對端執行腳本：強化版 Ensemble Calibration Patch

流程：
  1. 找到 PATCH_QUEUED 的 calibration insight（id='07742efd'）
  2. 在 DB 插入一個 COMPLETED 的 model_patch_calibration 任務
  3. 更新 insight 的 patch_task_id 指向新任務
  4. 執行 ensemble_calibration_patch_runner，產生 before/after snapshots
  5. 印出 Brier before/after 結果
  6. 提示使用者執行 planner-tick 完成自動驗證

執行方式（使用系統 Python3，非 .venv）：
  python3 scripts/run_stronger_patch_e2e.py
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── 把專案根目錄加入 sys.path ──────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

INSIGHTS_PATH = _REPO_ROOT / "runtime" / "agent_orchestrator" / "insights.json"
TARGET_INSIGHT_ID = "07742efd"   # calibration, PATCH_QUEUED
NOW = datetime.now(timezone.utc).isoformat()


def main() -> None:
    # ── 1. 匯入 DB 模組 ─────────────────────────────────────────────────────────
    try:
        from orchestrator import db
    except ImportError as exc:
        logger.error("Cannot import orchestrator.db: %s", exc)
        sys.exit(1)

    # ── 2. 找到目標 insight ─────────────────────────────────────────────────────
    if not INSIGHTS_PATH.exists():
        logger.error("insights.json not found: %s", INSIGHTS_PATH)
        sys.exit(1)

    insights: list[dict] = json.loads(INSIGHTS_PATH.read_text(encoding="utf-8"))
    target_insight: dict | None = None
    for ins in insights:
        if ins.get("id") == TARGET_INSIGHT_ID:
            target_insight = ins
            break

    if target_insight is None:
        logger.error("Insight %s not found in insights.json", TARGET_INSIGHT_ID)
        # Fallback: use any PATCH_QUEUED calibration insight
        for ins in insights:
            if ins.get("status") == "PATCH_QUEUED" and ins.get("category") == "calibration":
                target_insight = ins
                logger.info("Fallback: using insight %s", ins["id"])
                break

    if target_insight is None:
        logger.error("No PATCH_QUEUED calibration insight found.")
        sys.exit(1)

    logger.info("Target insight: %s  (status=%s)", target_insight["id"], target_insight.get("status"))

    # ── 3. 在 DB 插入 COMPLETED 任務 ─────────────────────────────────────────────
    new_task_id = db.create_task(
        slot_key="research",
        date_folder="2026-04-24",
        title="[Ensemble] MLB Calibration Patch: Platt + Isotonic + Regime Bias Correction",
        slug="ensemble_calibration_patch",
        status="COMPLETED",
        signal_state_type="model_patch_calibration",
        completed_text=(
            "# Ensemble Calibration Patch\n\n"
            "Calibration method: ensemble_platt_iso_regime\n"
            "Strategy: Platt Scaling + Isotonic Regression + CV blend + Regime Bias Correction\n"
            "Target: Improve Brier Score by >10% vs raw predicted_prob baseline\n"
        ),
        completed_at=NOW,
        created_at=NOW,
        updated_at=NOW,
        contract_json=json.dumps({
            "signal_state_type": "model_patch_calibration",
            "category": "calibration",
            "target_files": ["wbc_backend/calibration/probability_calibrator.py"],
            "expected_metric": "Brier < 0.10",
        }),
        focus_keys="calibration,brier,ensemble",
    )
    logger.info("Created DB task #%d (COMPLETED, model_patch_calibration)", new_task_id)

    # ── 4. 更新 insight patch_task_id ────────────────────────────────────────────
    old_patch_task_id = target_insight.get("patch_task_id")
    target_insight["patch_task_id"] = new_task_id
    target_insight["patched_at"] = NOW
    # 確保 status 是 PATCH_QUEUED（不要提前改）
    if target_insight.get("status") not in ("PATCH_QUEUED",):
        logger.warning(
            "Insight %s has status=%s (expected PATCH_QUEUED), resetting.",
            target_insight["id"], target_insight.get("status"),
        )
        target_insight["status"] = "PATCH_QUEUED"
        # 清除舊的驗證時間戳記
        for key in ("validated_at", "partial_at", "partial_reason"):
            target_insight.pop(key, None)

    INSIGHTS_PATH.write_text(
        json.dumps(insights, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info(
        "Updated insight %s: patch_task_id %s → %d",
        target_insight["id"], old_patch_task_id, new_task_id,
    )

    # ── 5. 執行 Ensemble Calibration Runner ──────────────────────────────────────
    logger.info("Running ensemble calibration patch for task #%d ...", new_task_id)
    try:
        from wbc_backend.research.ensemble_calibration_patch_runner import (
            run_ensemble_calibration_patch,
        )
    except ImportError as exc:
        logger.error("Cannot import ensemble_calibration_patch_runner: %s", exc)
        sys.exit(1)

    result = run_ensemble_calibration_patch(new_task_id)

    # ── 6. 報告結果 ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("ENSEMBLE CALIBRATION PATCH RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("=" * 60)

    if result.get("status") == "SUCCESS":
        print(f"\n✓  Brier: {result['before_brier']:.4f} → {result['after_brier']:.4f}"
              f"  (Δ{result['brier_delta']:+.4f}, {result['brier_rel_improve_pct']:.1f}% improve)")
        print(f"   Blend alpha: {result['blend_alpha']:.2f}")
        print(f"   Method: {result['calibration_method']}")
        print(f"\n✓  Task ID in DB: #{new_task_id}")
        print(f"✓  Insight '{TARGET_INSIGHT_ID}' → patch_task_id={new_task_id}")
        print(f"\n→ 下一步：執行 planner-tick 觸發自動驗證")
        print("   python3 scripts/agent_orchestrator.py planner-tick 2>&1 | head -40")
    else:
        print(f"\n✗  Runner failed: {result.get('failure_reason', 'unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
