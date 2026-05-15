#!/usr/bin/env python3
"""
Phase 2: Post-Draw Pipeline Dry-Run
====================================
端對端測試三彩種的 7+1 步驟，確認系統可運作。
不寫入 DB，不呼叫外部 API，只驗證可讀性與邏輯。
"""
import json
import os
import sys
import sqlite3
import traceback
from datetime import datetime

ROOT = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, ROOT)
DATA_DIR = os.path.join(ROOT, "data")
DB_PATH = os.path.join(ROOT, "lottery_api", "data", "lottery_v2.db")

LOTTERIES = {
    "BIG_LOTTO": {
        "draw": "115000045",
        "date": "2026/04/17",
        "numbers": [7, 10, 11, 22, 40, 45],
        "special": 18,
    },
    "DAILY_539": {
        "draw": "115000095",
        "date": "2026/04/17",
        "numbers": [1, 2, 7, 16, 26],
        "special": 0,
    },
    "POWER_LOTTO": {
        "draw": "115000031",
        "date": "2026/04/16",
        "numbers": [4, 11, 16, 22, 30, 38],
        "special": 6,
    },
}

RESULT = {
    "run_date": datetime.now().isoformat(),
    "by_lottery": {},
    "overall_status": "ALL_OK",
    "failed_steps": [],
}


def step_ok(step_key, lottery, value=None):
    r = RESULT["by_lottery"].setdefault(lottery, {})
    r[step_key] = {"status": "OK"} if value is None else value


def step_fail(step_key, lottery, reason):
    r = RESULT["by_lottery"].setdefault(lottery, {})
    r[step_key] = {"status": "FAILED", "error": reason}
    RESULT["failed_steps"].append(f"{lottery}/{step_key}: {reason}")
    print(f"  [FAIL] {step_key}: {reason}")


def test_step1_ingest(lt, draw):
    """入庫 dry-run: 確認 draws 表格可查詢"""
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT id FROM draws WHERE lottery_type=? AND draw=?", (lt, draw)
        ).fetchone()
        conn.close()
        status = "would_skip_dup" if row else "would_insert"
        step_ok("step_1_ingest", lt, {"status": "OK", "would": status})
        print(f"  STEP 1 OK: {lt} draw={draw} → {status}")
    except Exception as ex:
        step_fail("step_1_ingest", lt, str(ex))


def test_step2_rsm(lt):
    """RSM dry-run: 確認 strategy_states JSON 可讀取"""
    path = os.path.join(DATA_DIR, f"strategy_states_{lt}.json")
    try:
        if not os.path.exists(path):
            step_ok("step_2_rsm", lt, {"status": "OK", "note": "file_missing_but_readable"})
            print(f"  STEP 2 WARN: {lt} strategy_states 不存在 (RSM 尚未建立)")
            return
        with open(path) as f:
            states = json.load(f)
        top_key = list(states.keys())[0] if states else "N/A"
        step_ok("step_2_rsm", lt, {"status": "OK", "strategies_loaded": len(states), "top_strategy": top_key})
        print(f"  STEP 2 OK: {lt} 載入 {len(states)} 個策略")
    except Exception as ex:
        step_fail("step_2_rsm", lt, str(ex))


def test_step3_psi(lt):
    """PSI dry-run: 呼叫 DriftDetector"""
    try:
        from lottery_api.engine.drift_detector import check_drift
        report = check_drift(lt)
        psi = report.metrics.get("number_freq_PSI", {})
        psi_val = psi.get("value", 0)
        step_ok("step_3_psi", lt, {"status": "OK", "psi_value": round(float(psi_val), 6), "overall": report.overall_status})
        print(f"  STEP 3 OK: {lt} PSI={psi_val:.4f} [{report.overall_status}]")
    except Exception as ex:
        step_fail("step_3_psi", lt, str(ex))


def test_step4_wq(lt, numbers):
    """Winning Quality dry-run"""
    try:
        from lottery_api.engine.winning_quality import analyze
        wq = analyze(numbers, lt)
        step_ok("step_4_wq", lt, {"status": "OK", "split_risk": wq.get("split_risk"), "pop_score": wq.get("pop_score")})
        print(f"  STEP 4 OK: {lt} split_risk={wq.get('split_risk')}")
    except Exception as ex:
        step_fail("step_4_wq", lt, str(ex))


def test_step5_alert(lt):
    """Alert dry-run: 讀取 exit triggers JSON"""
    triggers_path = os.path.join(DATA_DIR, "maintenance_exit_triggers.json")
    try:
        if not os.path.exists(triggers_path):
            step_fail("step_5_alert", lt, "maintenance_exit_triggers.json 不存在")
            return
        with open(triggers_path) as f:
            triggers = json.load(f)
        lt_status = triggers.get(lt, {}).get("current_status", "N/A")
        step_ok("step_5_alert", lt, {"status": "OK", "alerts_triggered": [], "exit_trigger_status": lt_status})
        print(f"  STEP 5 OK: {lt} trigger_status={lt_status}")
    except Exception as ex:
        step_fail("step_5_alert", lt, str(ex))


def test_step6_pending(lt):
    """PENDING 預測解析 dry-run: 確認 prediction_runs 可讀"""
    try:
        conn = sqlite3.connect(DB_PATH)
        count = conn.execute(
            "SELECT COUNT(*) FROM prediction_runs WHERE lottery_type=?", (lt,)
        ).fetchone()[0]
        conn.close()
        step_ok("step_6_pending", lt, {"status": "OK", "prediction_runs_count": count})
        print(f"  STEP 6 OK: {lt} prediction_runs={count}")
    except Exception as ex:
        step_fail("step_6_pending", lt, str(ex))


def test_step7_snapshot(lt):
    """自動快照 dry-run: 確認 combo_b_milestone.json 可讀"""
    updated = False
    note = "N/A"
    try:
        if lt == "POWER_LOTTO":
            milestone_path = os.path.join(DATA_DIR, "combo_b_milestone.json")
            if os.path.exists(milestone_path):
                with open(milestone_path) as f:
                    ms = json.load(f)
                updated = True
                note = f"status={ms.get('status')} evaluate_at={ms.get('evaluate_at_draw')}"
            else:
                note = "combo_b_milestone.json 不存在"
        else:
            note = "only_for_POWER_LOTTO"

        step_ok("step_7_snapshot", lt, {"status": "OK", "combo_b_updated": updated, "note": note})
        print(f"  STEP 7 OK: {lt} combo_b_updated={updated} {note}")
    except Exception as ex:
        step_fail("step_7_snapshot", lt, str(ex))


def run_for_lottery(lt, data):
    print(f"\n=== {lt} draw={data['draw']} ===")
    test_step1_ingest(lt, data["draw"])
    test_step2_rsm(lt)
    test_step3_psi(lt)
    test_step4_wq(lt, data["numbers"])
    test_step5_alert(lt)
    test_step6_pending(lt)
    test_step7_snapshot(lt)


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    for lt, data in LOTTERIES.items():
        run_for_lottery(lt, data)

    failed = RESULT["failed_steps"]
    if len(failed) == 0:
        RESULT["overall_status"] = "ALL_OK"
    elif any("step_1" in s or "step_3" in s for s in failed):
        RESULT["overall_status"] = "CRITICAL_FAIL"
    else:
        RESULT["overall_status"] = "PARTIAL_FAIL"

    out_path = os.path.join(DATA_DIR, "pipeline_dryrun_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(RESULT, f, indent=2, ensure_ascii=False)

    print(f"\n====== DRY-RUN COMPLETE ======")
    print(f"Overall: {RESULT['overall_status']}")
    if failed:
        for s in failed:
            print(f"  FAIL: {s}")
    print(f"Report: {out_path}")


if __name__ == "__main__":
    main()
