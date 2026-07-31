#!/usr/bin/env python3
"""
Usage Budget Check CLI (Phase 36)
==================================
讀取 Usage Budget Guard 狀態並以文字或 JSON 格式輸出。
不呼叫任何外部 AI，僅讀取本地日誌。

用法:
    python3 scripts/usage_budget_check.py
    python3 scripts/usage_budget_check.py --hours 24
    python3 scripts/usage_budget_check.py --json
    python3 scripts/usage_budget_check.py --provider github-copilot
    python3 scripts/usage_budget_check.py --role worker
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 確保專案 root 在 sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _status_icon(status: str) -> str:
    return {"OK": "✅", "WARN": "⚠️ ", "CRITICAL": "🚨", "HARD_CAP": "🛑"}.get(status, "❓")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Usage Budget Guard status check (read-only, no external AI)."
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=24.0,
        help="Rolling time window in hours (default: 24).",
    )
    parser.add_argument(
        "--json",
        dest="emit_json",
        action="store_true",
        help="Emit machine-readable JSON output.",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="Filter output to a specific provider (e.g. github-copilot, claude, codex).",
    )
    parser.add_argument(
        "--role",
        type=str,
        default=None,
        help="Filter output to a specific role (e.g. worker, planner, cto).",
    )
    args = parser.parse_args()

    try:
        from orchestrator.usage_budget_guard import get_budget_summary, is_provider_allowed
    except ImportError as exc:
        print(f"[ERROR] Cannot import usage_budget_guard: {exc}", file=sys.stderr)
        return 2

    try:
        summary = get_budget_summary(hours=args.hours)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Budget evaluation failed: {exc}", file=sys.stderr)
        return 2

    # ── Provider or Role filter mode ───────────────────────────────────────
    if args.provider:
        allowed, reason = is_provider_allowed("worker", args.provider, hours=args.hours)
        if args.emit_json:
            print(json.dumps({"provider": args.provider, "allowed": allowed, "reason": reason}, indent=2))
        else:
            icon = "✅ ALLOWED" if allowed else "🛑 BLOCKED"
            print(f"Provider: {args.provider}")
            print(f"Status  : {icon}")
            print(f"Reason  : {reason}")
        return 0 if allowed else 1

    if args.role:
        role_data = summary.get("roles", {}).get(args.role)
        if role_data is None:
            print(f"[ERROR] Unknown role: {args.role}. Valid: planner, cto, worker", file=sys.stderr)
            return 2
        if args.emit_json:
            print(json.dumps({args.role: role_data}, indent=2))
        else:
            s = role_data.get("status", "OK")
            icon = _status_icon(s)
            print(f"Role: {args.role.upper()}  {icon} {s}")
            for k, v in role_data.items():
                if k != "status":
                    print(f"  {k}: {v}")
        return 0

    # ── Full summary mode ──────────────────────────────────────────────────
    if args.emit_json:
        print(json.dumps(summary, indent=2, default=str))
        return 0

    # Text output
    bar = "=" * 50
    sub = "-" * 50
    b_status = summary.get("budget_status", "?")
    icon = _status_icon(b_status)
    print(bar)
    print(f"💰 USAGE BUDGET GUARD  {icon} {b_status}  (窗口: {args.hours}h)")
    print(bar)
    print(f"排程模式: {summary.get('recommended_scheduler_mode', '?')}")
    print(f"啟用    : {summary.get('enabled', True)}")
    print(f"版本    : {summary.get('config_version', '?')}")
    print()

    print(sub)
    print("角色狀態 (Roles)")
    print(sub)
    for role_n, r in summary.get("roles", {}).items():
        rs = r.get("status", "OK")
        ri = _status_icon(rs)
        calls = r.get("calls", 0)
        blocked = r.get("blocked", 0)
        if role_n in ("planner", "cto"):
            print(f"  {role_n.upper():8} {ri} {rs:10}  外部呼叫={calls}  允許上限={r.get('allowed_external', 0)}  封鎖={blocked}")
        else:
            print(
                f"  {role_n.upper():8} {ri} {rs:10}  "
                f"呼叫={calls}/{r.get('hard_cap_calls','?')}  "
                f"(WARN>{r.get('warn_calls','?')})  封鎖={blocked}"
            )

    print()
    print(sub)
    print("Provider 狀態")
    print(sub)
    for pname, p in summary.get("providers", {}).items():
        ps = p.get("status", "OK")
        pi = _status_icon(ps)
        print(
            f"  {pname:20} {pi} {ps:10}  "
            f"呼叫={p.get('calls', 0)}/{p.get('hard_cap_calls','?')}  "
            f"(WARN>{p.get('warn_calls','?')})"
        )

    print()
    tok = summary.get("tokens", {})
    ts = tok.get("status", "OK")
    ti = _status_icon(ts)
    print(sub)
    print("Token 使用")
    print(sub)
    print(
        f"  Input Tokens: {ti} {ts}  "
        f"{tok.get('input_tokens', 0):,}/{tok.get('hard_cap_input_tokens', 0):,}"
    )

    print()
    print(f"封鎖次數合計: {summary.get('total_blocked', 0)}")

    warnings = summary.get("warnings", [])
    critical_alerts = summary.get("critical_alerts", [])
    if warnings or critical_alerts:
        print()
        print(sub)
        print("告警")
        print(sub)
        for w in warnings:
            print(f"  {w}")
        for c in critical_alerts:
            print(f"  {c}")

    print()
    exit_code = 0 if b_status == "OK" else (1 if b_status == "WARN" else 2)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
