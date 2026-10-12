"""
scripts/copilot_daemon_doctor.py

Phase 36A — Copilot Daemon CLI Compatibility Doctor
======================================================
偵測本機 Copilot CLI 環境、建構指令預覽、確認 policy 與 audit 狀態。

完全乾跑（--dry-run）：不執行任何 LLM 呼叫，不消耗配額。

使用方式：
    python3 scripts/copilot_daemon_doctor.py --dry-run
    python3 scripts/copilot_daemon_doctor.py          # 預設即 dry-run
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator import db
from orchestrator.copilot_daemon import detect_copilot_cli_mode, build_copilot_command
from orchestrator.common import validate_copilot_model


def _check_policy_allowed() -> tuple[bool, str]:
    """執行 policy 評估（不呼叫 LLM），回傳 (allowed, reason)。"""
    try:
        from orchestrator import execution_policy
        decision = execution_policy.evaluate_execution(
            runner="copilot_daemon",
            requires_llm=True,
            background=True,
            manual_override=False,
        )
        allowed = not bool(decision.get("reason"))
        reason = decision.get("reason") or "OK"
        return allowed, reason
    except Exception as exc:  # noqa: BLE001
        return False, f"policy_check_error: {exc}"


def _check_audit_path() -> tuple[bool, str]:
    """確認 llm_usage.jsonl 的父目錄可寫。"""
    try:
        from orchestrator import llm_usage_logger
        log_dir = os.path.dirname(llm_usage_logger._LOG_PATH)
        os.makedirs(log_dir, exist_ok=True)
        available = os.access(log_dir, os.W_OK)
        return available, log_dir if available else f"{log_dir} (not writable)"
    except Exception as exc:  # noqa: BLE001
        return False, f"audit_path_error: {exc}"


def _check_binary(name: str) -> str:
    path = shutil.which(name)
    return path if path else "(not found)"


def run_doctor(dry_run: bool = True) -> int:
    """
    執行完整診斷。回傳 exit code（0=pass，1=fail）.
    dry_run=True 時只做偵測，不觸發任何 LLM 呼叫。
    """
    print("=" * 60)
    print("  Copilot Daemon CLI Doctor  (Phase 36A)")
    print("=" * 60)

    # ── DB 設定 ──────────────────────────────────────────────────────────
    db.init_db()
    worker_provider = db.get_worker_provider()
    copilot_model = db.get_worker_copilot_model() or None
    print(f"\n[DB Settings]")
    print(f"  worker_provider    : {worker_provider}")
    print(f"  worker_copilot_model: {copilot_model!r}")
    print(f"  model valid        : {validate_copilot_model(copilot_model)}")

    # ── Binary 偵測 ───────────────────────────────────────────────────────
    copilot_path = _check_binary("copilot")
    gh_path = _check_binary("gh")
    print(f"\n[Binary Detection]")
    print(f"  copilot binary : {copilot_path}")
    print(f"  gh binary      : {gh_path}")

    # ── CLI 模式偵測 ──────────────────────────────────────────────────────
    cli_mode = detect_copilot_cli_mode()
    cli_ok = cli_mode != "unavailable"
    print(f"\n[CLI Mode Detection]")
    print(f"  cli_mode       : {cli_mode}")
    print(f"  status         : {'OK' if cli_ok else 'UNAVAILABLE'}")

    # ── 指令預覽 ─────────────────────────────────────────────────────────
    print(f"\n[Command Preview]  (dry_run={dry_run})")
    if cli_ok:
        try:
            cmd = build_copilot_command(
                prompt="<task prompt content>",
                model=copilot_model,
                cli_mode=cli_mode,
                dry_run=True,
            )
            # 安全輸出：prompt 已被替換為 [PROMPT_CONTENT]
            print(f"  command        : {cmd}")
        except ValueError as exc:
            print(f"  command        : ERROR - {exc}")
            cli_ok = False
    else:
        print("  command        : (unavailable — CLI not detected)")

    # ── Policy 確認 ───────────────────────────────────────────────────────
    policy_allowed, policy_reason = _check_policy_allowed()
    print(f"\n[Execution Policy]")
    print(f"  policy_allowed : {policy_allowed}")
    print(f"  reason         : {policy_reason}")

    # ── Audit 路徑 ────────────────────────────────────────────────────────
    audit_ok, audit_path = _check_audit_path()
    print(f"\n[Audit Log Path]")
    print(f"  available      : {audit_ok}")
    print(f"  path           : {audit_path}")

    # ── 模型相容性說明 ──────────────────────────────────────────────────────
    print(f"\n[Model Compatibility]")
    if cli_mode == "agent_cli":
        print(f"  agent_cli uses : copilot --model <model>  (root-level flag)")
        print(f"  model passed   : {copilot_model!r}")
        print(f"  note           : 'auto' and '' omit --model (CLI default applies)")
    elif cli_mode == "gh_extension_legacy":
        print(f"  legacy uses    : gh copilot suggest --target shell --model <model>")
        print(f"  model passed   : {copilot_model!r}")
    else:
        print(f"  N/A (CLI unavailable)")

    # ── 最終判定 ─────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    all_ok = cli_ok and audit_ok
    if all_ok:
        print("  RESULT: COPILOT_DAEMON_CLI_COMPATIBILITY_VERIFIED")
        if not policy_allowed:
            print(f"  NOTE:   policy currently blocked ({policy_reason})")
            print(f"          This is normal in hard-off / scheduler-disabled states.")
    else:
        print("  RESULT: FAIL")
        if not cli_ok:
            print(f"  - CLI unavailable (mode={cli_mode})")
        if not audit_ok:
            print(f"  - Audit log path not writable ({audit_path})")
    print("=" * 60)

    return 0 if all_ok else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copilot Daemon CLI compatibility doctor (Phase 36A)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview only, do not call any external LLM (default: True)",
    )
    args = parser.parse_args()
    sys.exit(run_doctor(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
