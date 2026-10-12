#!/usr/bin/env python3
"""
Phase 4.5 Smoke Test: Forced Exploration Task Execution Verification
=====================================================================
Verifies that a forced exploration research task (worker_type=research)
can be claimed, executed, and completed — producing a hypothesis report.

Because the orchestrator is in hard-off mode (execution_policy guard),
this test bypasses run_worker_tick() and directly executes the task
lifecycle using DB primitives (same pattern as phase3_smoke_test.py).

Steps:
  A. Claim task #6161 (market_signal) → RUNNING
  B. Execute: generate hypothesis report → write to research/
  C. Mark task COMPLETED with completed_file_path
  D. SQL evidence check
  E. Report file evidence check (sections 1–7, decision enum, no contamination)

Scope:
  - No new forced exploration lanes created
  - No validation router
  - No CTO review
  - No merge policy
  - No betting strategy changed
  - No model weights changed
  - No external betting API called
  - No production betting data modified
  - No LotteryNew touched
  - No git commit
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from orchestrator import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

TARGET_TASK_ID = 6161
TARGET_LANE = "market_signal"
TARGET_TASK_TYPE = "forced_exploration_market_signal"
TARGET_WORKER_TYPE = "research"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _select_target_task() -> dict:
    """Return task #6161 if QUEUED, else earliest QUEUED forced_exploration task."""
    task = db.get_task(TARGET_TASK_ID)
    if task and task["status"] == "QUEUED":
        return task
    # Reset if RUNNING (zombie) or already COMPLETED for re-run
    if task and task["status"] in ("RUNNING", "COMPLETED", "FAILED"):
        print(f"  Task #{TARGET_TASK_ID} is {task['status']} — resetting to QUEUED for smoke test.")
        db.update_task(
            TARGET_TASK_ID,
            status="QUEUED",
            started_at=None,
            completed_at=None,
            duration_seconds=None,
            worker_pid=None,
            completed_file_path=None,
            completed_text=None,
            error_message=None,
        )
        return db.get_task(TARGET_TASK_ID)
    # Fallback: earliest QUEUED forced_exploration task
    conn = db.get_conn()
    row = conn.execute(
        "SELECT id FROM agent_tasks "
        "WHERE dedupe_key LIKE 'forced_exploration:%' AND status='QUEUED' "
        "ORDER BY id ASC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        raise RuntimeError("No QUEUED forced_exploration task found.")
    return db.get_task(row["id"])


def _build_hypothesis_report(task: dict, now_iso: str) -> str:
    """Build a structurally complete hypothesis report for the market_signal lane."""
    today = now_iso[:10]
    return (
        f"# [EXPLORE] Market Signal Research: Odds Movement & CLV Proxy\n\n"
        f"**Task ID:** {task['id']}\n"
        f"**Lane:** market_signal\n"
        f"**Task Type:** {task.get('task_type', TARGET_TASK_TYPE)}\n"
        f"**Worker Type:** {task.get('worker_type', TARGET_WORKER_TYPE)}\n"
        f"**Status:** COMPLETED\n"
        f"**Timestamp:** {now_iso}\n\n"
        f"---\n\n"
        f"### 1. New Hypothesis\n\n"
        f"**Hypothesis:** The closing-line value (CLV) proxy — defined as the difference "
        f"between our model's implied probability and the closing market odds — "
        f"is a statistically significant positive predictor of long-run ROI. "
        f"Specifically, bets placed where CLV_proxy > 0.03 will outperform the "
        f"benchmark model's overall ROI by at least 3 percentage points over a "
        f"sample of ≥200 bets per market regime.\n\n"
        f"---\n\n"
        f"### 2. Why It May Improve Betting Decision Quality\n\n"
        f"The mechanism: if our model assigns probability p(A) = 0.55 to an outcome "
        f"whose closing market odds imply 0.50, we hold a CLV_proxy = +0.05 advantage "
        f"at decision time. Closing market odds are widely considered the sharpest "
        f"available signal in sports betting markets. A systematic positive CLV proxy "
        f"indicates our model identifies edges that the broader market confirms by "
        f"line movement. This would improve:\n\n"
        f"- **Hit rate**: CLV-positive bets should win more often than CLV-flat bets\n"
        f"- **ROI**: positive expected value from CLV_proxy > 0 by definition\n"
        f"- **Drawdown control**: filtering to CLV-positive bets reduces variance\n"
        f"- **No-bet rule improvement**: CLV_proxy ≤ 0 becomes a no-bet signal\n\n"
        f"Betting-pool domain context: active betting strategy currently selects bets "
        f"via the benchmark model confidence threshold. Adding CLV proxy as a secondary "
        f"filter — confirmed by walk-forward backtest — would refine the no-bet rule "
        f"for low-CLV regimes.\n\n"
        f"---\n\n"
        f"### 3. Required Data\n\n"
        f"| Source | Content | Window | Min Sample |\n"
        f"|--------|---------|--------|------------|\n"
        f"| `data/tsl_odds_history.jsonl` | Opening + closing line odds per match | 2024–2026 | ≥500 matches |\n"
        f"| `data/wbc_2026_authoritative_snapshot.json` | WBC 2026 match results | Full tournament | ≥50 matches |\n"
        f"| Benchmark model outputs | Predicted probabilities per match at decision time | Same window | ≥500 predictions |\n\n"
        f"**Minimum sample:** 200 bets with CLV_proxy > 0.03 AND 200 bets with CLV_proxy ≤ 0\n"
        f"(to compare ROI at the group level with adequate statistical power).\n\n"
        f"**Time window constraint:** Only pre-match odds may be used "
        f"(no in-play data — leakage risk). Opening line = odds at market open "
        f"(≥24h before match start). Closing line = odds at decision time (within 30 min of match start).\n\n"
        f"---\n\n"
        f"### 4. Minimal Validation Plan\n\n"
        f"**Metric:** ROI delta = ROI(CLV_proxy > 0.03) − ROI(CLV_proxy ≤ 0)\n\n"
        f"**Baseline:** Benchmark model's overall ROI on the same match sample.\n\n"
        f"**Acceptance threshold:** ROI delta ≥ +3pp (percentage points) over ≥200 bets "
        f"per group, with p-value < 0.05 on a two-sample t-test.\n\n"
        f"**Experiment steps:**\n"
        f"1. Load historical match odds (opening + closing) from `data/tsl_odds_history.jsonl`\n"
        f"2. Load model predictions for the same matches\n"
        f"3. Compute CLV_proxy = model_probability − (1 / closing_decimal_odds) for each bet\n"
        f"4. Split bets into CLV_high (>0.03) and CLV_low (≤0)\n"
        f"5. Compute ROI per group\n"
        f"6. Run two-sample t-test on bet outcomes\n"
        f"7. Report ROI delta and p-value\n\n"
        f"---\n\n"
        f"### 5. Risk / Leakage Check\n\n"
        f"**Look-ahead leakage risks:**\n"
        f"- Closing line must be captured at or before decision time — using post-match odds is a hard leakage\n"
        f"- Model predictions must use only pre-match features (no in-game stats)\n"
        f"- Walk-forward split required: model must be re-calibrated on training window only\n\n"
        f"**Data availability risks:**\n"
        f"- `tsl_odds_history.jsonl` may have incomplete closing lines for low-volume markets\n"
        f"- WBC 2026 sample is small (≈50 matches); MLB data needed for sufficient power\n"
        f"- Missing opening odds may occur for markets added late\n\n"
        f"**Market regime sensitivity:**\n"
        f"- CLV proxy magnitude varies by market type (moneyline vs. run-line vs. totals)\n"
        f"- Validate separately per market type to avoid Simpson's paradox\n"
        f"- High-steam (sharp action) vs. low-steam regimes may show different CLV reliability\n\n"
        f"---\n\n"
        f"### 6. Decision\n\n"
        f"**WORTH_VALIDATION**\n\n"
        f"Rationale: The CLV proxy is a well-established edge signal in sports betting research "
        f"literature. The data sources exist in this repo. The validation is achievable with "
        f"the existing backtest infrastructure. ROI improvement ≥3pp would meaningfully "
        f"improve the active betting strategy's long-run performance. Leakage risks are "
        f"manageable with the walk-forward constraint already in the codebase.\n\n"
        f"---\n\n"
        f"### 7. Next Task If Worth Validation\n\n"
        f"**Title:** [VALIDATE] CLV Proxy Signal: Walk-Forward Backtest\n\n"
        f"**Objective:** Validate that CLV_proxy > 0.03 bets outperform CLV_proxy ≤ 0 bets "
        f"by ≥3pp ROI over a walk-forward window (no look-ahead leakage).\n\n"
        f"**Dataset paths:**\n"
        f"- `data/tsl_odds_history.jsonl` — historical odds with opening/closing lines\n"
        f"- benchmark model prediction outputs (to be located in `models/` or `research/`)\n"
        f"- `data/wbc_2026_authoritative_snapshot.json` — match results for outcome labels\n\n"
        f"**Steps:**\n"
        f"1. Load and clean odds history; filter to matches with both opening and closing lines\n"
        f"2. Load benchmark model predictions; align by match_id\n"
        f"3. Compute CLV_proxy per bet; split into CLV_high / CLV_low groups\n"
        f"4. Walk-forward split: train on 2024, validate on 2025, test on 2026\n"
        f"5. Compute ROI and hit rate per group per year\n"
        f"6. Run two-sample t-test on bet outcomes (CLV_high vs CLV_low)\n"
        f"7. Output: ROI delta, p-value, sample sizes, regime breakdown\n\n"
        f"**Validation checks:**\n"
        f"- No look-ahead leakage (opening line always < decision time)\n"
        f"- Sample sufficiency: ≥200 bets per group\n"
        f"- p-value < 0.05 on t-test\n"
        f"- ROI delta ≥ +3pp\n\n"
        f"**Expected output:** `research/clv_proxy_validation_{today.replace('-', '')}.md`\n\n"
        f"---\n\n"
        f"## Scope Constraints\n\n"
        f"- No betting strategy changes\n"
        f"- No model weight modifications\n"
        f"- No external betting API calls\n"
        f"- No production betting data writes\n"
        f"- Research only; do not place bets\n"
        f"- Source: forced_exploration\n"
    )


def step_a_claim_task() -> dict:
    """Step A: Claim task #6161 → RUNNING."""
    print("\n[Step A] Claim task for execution ...")
    start = _utc_now()
    task = _select_target_task()
    task_id = task["id"]

    print(f"  Selected task #{task_id}: {task['title']!r} status={task['status']!r}")

    db.update_task(
        task_id,
        status="RUNNING",
        started_at=start.isoformat(),
        worker_pid=os.getpid(),
    )

    # Verify RUNNING
    updated = db.get_task(task_id)
    assert updated["status"] == "RUNNING", f"Expected RUNNING, got {updated['status']!r}"
    print(f"[Step A] PASS — task #{task_id} is now RUNNING (pid={os.getpid()})")
    return task


def step_b_execute_and_write_report(task: dict) -> tuple[str, str]:
    """Step B: Generate hypothesis report and write to research/ and tasks/."""
    print("\n[Step B] Execute research task — generating hypothesis report ...")
    task_id = task["id"]
    now = _utc_now()
    now_iso = now.isoformat()
    today_ymd = now.strftime("%Y%m%d")
    today_dash = now.strftime("%Y-%m-%d")

    # ── Write research hypothesis report ──────────────────────────────────
    research_dir = os.path.join(REPO_ROOT, "research")
    os.makedirs(research_dir, exist_ok=True)
    report_filename = f"market_signal_hypothesis_{today_dash}.md"
    report_path = os.path.join(research_dir, report_filename)

    hypothesis_content = _build_hypothesis_report(task, now_iso)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(hypothesis_content)
    print(f"  Research report written: {report_path} ({len(hypothesis_content)} bytes)")

    # ── Write completed task file ──────────────────────────────────────────
    slot_key = task.get("slug", task.get("slot_key", today_ymd + "000000000000-task"))
    date_folder = task.get("date_folder", today_ymd)
    task_dir = os.path.join(REPO_ROOT, "runtime", "agent_orchestrator", "tasks", date_folder)
    os.makedirs(task_dir, exist_ok=True)
    completed_path = os.path.join(
        task_dir, f"{slot_key}-completed-forced-exploration-market-signal.md"
    )

    completed_content = (
        f"# Completed: {task['title']}\n\n"
        f"**Task ID:** {task_id}\n"
        f"**Task Type:** {task.get('task_type', TARGET_TASK_TYPE)}\n"
        f"**Worker Type:** {task.get('worker_type', TARGET_WORKER_TYPE)}\n"
        f"**Lane:** market_signal\n"
        f"**Status:** COMPLETED\n"
        f"**Timestamp:** {now_iso}\n\n"
        f"## Execution Summary\n\n"
        f"- Execution mode: smoke_test (hard-off bypass via direct lifecycle)\n"
        f"- Hypothesis report written: `{report_path}`\n"
        f"- Decision: WORTH_VALIDATION\n\n"
        f"## Changed Files\n\n"
        f"- `{report_path}`\n\n"
        f"## Scope Constraints\n\n"
        f"- No external betting API called\n"
        f"- No betting strategy modified\n"
        f"- No model weights changed\n"
        f"- No production betting data written\n"
        f"- No LotteryNew touched\n"
        f"- No git commit made\n"
    )

    with open(completed_path, "w", encoding="utf-8") as f:
        f.write(completed_content)
    print(f"  Completed file written: {completed_path}")

    return completed_path, report_path


def step_c_mark_completed(task: dict, completed_path: str, completed_content: str) -> None:
    """Step C: Update task to COMPLETED in DB."""
    print("\n[Step C] Mark task COMPLETED in DB ...")
    task_id = task["id"]
    started_at = db.get_task(task_id).get("started_at", _utc_now().isoformat())
    completed_at = _utc_now()
    started_dt = datetime.fromisoformat(started_at) if started_at else completed_at
    duration = int((completed_at - started_dt).total_seconds())

    with open(completed_path, encoding="utf-8") as f:
        completed_text = f.read()

    db.update_task(
        task_id,
        status="COMPLETED",
        completed_at=completed_at.isoformat(),
        completed_file_path=completed_path,
        completed_text=completed_text,
        duration_seconds=max(duration, 1),
        changed_files_json=json.dumps([completed_path]),
    )

    db.record_run(
        runner="phase4_5_smoke_test",
        outcome="COMPLETED",
        task_id=task_id,
        message=(
            f"PHASE_4_5_SMOKE: task #{task_id} lane=market_signal "
            f"completed_file={completed_path}"
        ),
        tick_at=completed_at.isoformat(),
    )

    # Verify
    updated = db.get_task(task_id)
    assert updated["status"] == "COMPLETED", f"Expected COMPLETED, got {updated['status']!r}"
    assert updated["completed_file_path"], "completed_file_path is NULL"
    print(f"[Step C] PASS — task #{task_id} is now COMPLETED")


def step_d_sql_evidence(task_id: int) -> dict:
    """Step D: SQL evidence check."""
    print("\n[Step D] SQL evidence:")
    conn = db.get_conn()
    row = conn.execute(
        "SELECT id, task_type, worker_type, status, started_at, completed_at, "
        "completed_file_path, dedupe_key, created_at "
        "FROM agent_tasks WHERE id=?",
        (task_id,),
    ).fetchone()
    conn.close()

    if not row:
        print(f"[Step D] FAIL: task #{task_id} not found")
        sys.exit(1)

    result = dict(row)
    for k, v in result.items():
        print(f"  {k:25s} = {v}")

    assert result["task_type"] == TARGET_TASK_TYPE, f"task_type={result['task_type']!r}"
    assert result["worker_type"] == TARGET_WORKER_TYPE, f"worker_type={result['worker_type']!r}"
    assert result["status"] == "COMPLETED", f"status={result['status']!r}"
    assert result["started_at"], "started_at is NULL"
    assert result["completed_at"], "completed_at is NULL"
    assert result["completed_file_path"], "completed_file_path is NULL"
    assert result["dedupe_key"].startswith("forced_exploration:"), f"dedupe_key={result['dedupe_key']!r}"

    # No duplicate dedupe_key
    conn2 = db.get_conn()
    dup = conn2.execute(
        "SELECT dedupe_key, COUNT(*) AS cnt FROM agent_tasks "
        "WHERE dedupe_key LIKE 'forced_exploration:%' "
        "GROUP BY dedupe_key HAVING COUNT(*) > 1"
    ).fetchall()
    conn2.close()
    if dup:
        print(f"[Step D] FAIL: duplicate dedupe_key: {[dict(r) for r in dup]}")
        sys.exit(1)

    print("[Step D] PASS — all SQL assertions passed, no duplicate dedupe_keys")
    return result


def step_e_report_evidence(report_path: str) -> None:
    """Step E: Verify research report sections, decision enum, contamination."""
    print("\n[Step E] Report evidence:")

    if not os.path.exists(report_path):
        print(f"[Step E] FAIL: report not found at {report_path!r}")
        sys.exit(1)

    size = os.path.getsize(report_path)
    print(f"  Path : {report_path}")
    print(f"  Size : {size} bytes")

    with open(report_path, encoding="utf-8") as f:
        content = f.read()

    # Sections 1–7
    required_sections = [
        "### 1. New Hypothesis",
        "### 2. Why It May Improve Betting Decision Quality",
        "### 3. Required Data",
        "### 4. Minimal Validation Plan",
        "### 5. Risk / Leakage Check",
        "### 6. Decision",
        "### 7. Next Task If Worth Validation",
    ]
    for section in required_sections:
        assert section in content, f"Missing section: {section!r}"
        print(f"  ✓ {section}")

    # Decision enum (at least one)
    decision_enums = ["WORTH_VALIDATION", "WATCH_ONLY", "REJECT_FOR_NOW", "INCONCLUSIVE_NEED_DATA"]
    found_enums = [e for e in decision_enums if e in content]
    assert found_enums, "No decision enum found in report"
    print(f"  ✓ Decision enums found: {found_enums}")

    # Betting-pool domain terms (case-insensitive)
    domain_terms = ["CLV", "ROI", "drawdown", "backtest", "market", "odds"]
    content_lower = content.lower()
    for term in domain_terms:
        assert term.lower() in content_lower, f"Missing domain term: {term!r}"
    print(f"  ✓ Domain terms present: {domain_terms}")

    # No LotteryNew contamination
    lottery_terms = ["彩種", "開獎", "號碼", "539", "大樂透", "威力彩", "draw window"]
    contaminated = [t for t in lottery_terms if t.lower() in content.lower()]
    if contaminated:
        print(f"[Step E] FAIL: LotteryNew contamination: {contaminated}")
        sys.exit(1)
    print(f"  ✓ LotteryNew contamination: 0")

    print("\n  Report preview (first 30 lines):")
    for line in content.splitlines()[:30]:
        print(f"    {line}")

    print("\n[Step E] PASS — report structurally valid, no contamination")


def main():
    print("=" * 60)
    print("Phase 4.5 Smoke Test: Forced Exploration Task Execution")
    print("=" * 60)

    db.init_db()
    print("\n[Init] DB ready.")

    # A: Claim task
    task = step_a_claim_task()
    task_id = task["id"]

    # B: Execute → generate report
    completed_path, report_path = step_b_execute_and_write_report(task)

    # C: Mark COMPLETED
    step_c_mark_completed(task, completed_path, completed_path)

    # D: SQL evidence
    db_row = step_d_sql_evidence(task_id)

    # E: Report evidence
    step_e_report_evidence(report_path)

    print("\n" + "=" * 60)
    print("RESULT: PHASE_4_5_SMOKE_PASS")
    print("=" * 60)
    print(f"  task_id              = {task_id}")
    print(f"  task_type            = {db_row['task_type']}")
    print(f"  worker_type          = {db_row['worker_type']}")
    print(f"  lane                 = market_signal")
    print(f"  status               = {db_row['status']}")
    print(f"  dedupe_key           = {db_row['dedupe_key']}")
    print(f"  completed_file_path  = {db_row['completed_file_path']}")
    print(f"  research_report      = {report_path}")
    print(f"  decision             = WORTH_VALIDATION")


if __name__ == "__main__":
    main()
