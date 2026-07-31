#!/usr/bin/env python3
"""
scripts/llm_usage_recent.py

Universal AI / GitHub Usage Logger — LLM 使用量近期記錄查詢 CLI。

用法：
    python3 scripts/llm_usage_recent.py
    python3 scripts/llm_usage_recent.py --hours 24
    python3 scripts/llm_usage_recent.py --role worker
    python3 scripts/llm_usage_recent.py --provider codex --hours 1
    python3 scripts/llm_usage_recent.py --blocked-only
    python3 scripts/llm_usage_recent.py --json --tail 20
    python3 scripts/llm_usage_recent.py --summary
    python3 scripts/llm_usage_recent.py --rate-limited

選項：
    --hours N         查詢最近 N 小時（預設：24）
    --role NAME       篩選 role（planner / worker / cto / manual / backfill）
    --runner NAME     篩選 runner（向後相容；與 --role 相同）
    --provider NAME   篩選 provider（codex / claude / github-copilot / github-cli 等）
    --blocked-only    只顯示被封鎖的記錄
    --rate-limited    只顯示觸發 rate limit 的記錄
    --json            以 JSON 格式輸出原始記錄
    --tail N          顯示最新 N 筆（預設不限；搭配 --json 時預設 20）
    --summary         顯示聚合摘要（預設行為）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "runtime",
    "agent_orchestrator",
    "llm_usage.jsonl",
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="查詢 llm_usage.jsonl 外部 AI / GitHub 使用量記錄",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--hours", type=float, default=24.0, help="查詢最近 N 小時（預設 24）")
    p.add_argument("--role", type=str, default=None, help="篩選 role（planner/worker/cto…）")
    p.add_argument("--runner", type=str, default=None, help="篩選 runner（向後相容）")
    p.add_argument("--provider", type=str, default=None, help="篩選 provider")
    p.add_argument("--blocked-only", action="store_true", help="只顯示被封鎖的記錄")
    p.add_argument("--rate-limited", action="store_true", help="只顯示觸及 rate limit 的記錄")
    p.add_argument("--json", action="store_true", dest="json_out", help="輸出 JSON 格式")
    p.add_argument("--tail", type=int, default=None, help="僅顯示最新 N 筆")
    p.add_argument("--summary", action="store_true", help="顯示聚合摘要（預設）")
    return p.parse_args()


def _load_records(
    cutoff: datetime,
    role_filter: Optional[str],
    provider_filter: Optional[str],
    blocked_only: bool,
    rate_limited_only: bool,
) -> list[dict]:
    if not os.path.exists(_LOG_PATH):
        return []

    records: list[dict] = []
    with open(_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts_str = rec.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                continue

            if ts < cutoff:
                continue

            # 支援 role 和舊有 runner 兩種篩選
            if role_filter:
                rec_role = (rec.get("role") or rec.get("runner") or "").lower()
                if rec_role != role_filter.lower():
                    continue
            if provider_filter and rec.get("provider", "").lower() != provider_filter.lower():
                continue
            if blocked_only and not rec.get("blocked", False):
                continue
            if rate_limited_only and not rec.get("rate_limit"):
                continue

            records.append(rec)

    return records


def _summarize(records: list[dict], hours: float) -> None:
    total = len(records)
    allowed = sum(1 for r in records if not r.get("blocked"))
    blocked = sum(1 for r in records if r.get("blocked"))
    rate_limited = sum(1 for r in records if r.get("rate_limit"))

    # 按 role / runner 統計
    by_role: dict[str, dict[str, int]] = {}
    for r in records:
        role = r.get("role") or r.get("runner") or "unknown"
        if role not in by_role:
            by_role[role] = {"allowed": 0, "blocked": 0, "rate_limited": 0}
        if r.get("blocked"):
            by_role[role]["blocked"] += 1
        else:
            by_role[role]["allowed"] += 1
        if r.get("rate_limit"):
            by_role[role]["rate_limited"] += 1

    # 按 provider 統計
    by_provider: dict[str, int] = {}
    for r in records:
        prov = r.get("provider") or "unknown"
        by_provider[prov] = by_provider.get(prov, 0) + 1

    # 封鎖原因統計
    block_reasons: dict[str, int] = {}
    for r in records:
        if r.get("blocked"):
            reason = r.get("block_reason") or "unknown"
            block_reasons[reason] = block_reasons.get(reason, 0) + 1

    # Token 累計
    t_in = sum(int(r.get("input_tokens") or 0) for r in records)
    t_out = sum(int(r.get("output_tokens") or 0) for r in records)
    t_cache = sum(int(r.get("cached_tokens") or 0) for r in records)
    t_prem = sum(int(r.get("premium_requests") or 0) for r in records)

    print(f"\n{'='*65}")
    print(f"  Universal AI / GitHub Usage — 最近 {hours:.0f} 小時")
    print(f"{'='*65}")
    print(f"  總記錄數：{total}  |  允許：{allowed}  |  封鎖：{blocked}  |  Rate-Limited：{rate_limited}")

    if t_in or t_out or t_prem:
        print(f"\n  ── Token 使用量 ──")
        print(f"    Input：{t_in:,}  Output：{t_out:,}  Cached：{t_cache:,}  Premium Requests：{t_prem}")

    print(f"\n  ── 按 Role ──")
    for role, counts in sorted(by_role.items()):
        rl = f"  RL={counts['rate_limited']}" if counts["rate_limited"] else ""
        print(f"    {role:20s}  allowed={counts['allowed']}  blocked={counts['blocked']}{rl}")

    print(f"\n  ── 按 Provider ──")
    for prov, count in sorted(by_provider.items(), key=lambda x: -x[1]):
        print(f"    {prov:25s}  {count}")

    if block_reasons:
        print(f"\n  ── 封鎖原因 ──")
        for reason, count in sorted(block_reasons.items(), key=lambda x: -x[1]):
            print(f"    {reason:45s}  {count}")

    # 最近 5 筆記錄（含新欄位）
    if records:
        print(f"\n  ── 最近 5 筆記錄 ──")
        header = f"  {'時間':19s} {'role':10s} {'provider':20s} {'sf':30s} {'狀態'}"
        print(header)
        print("  " + "-" * 90)
        for r in records[-5:]:
            ts = str(r.get("timestamp", "?"))[:19]
            role = str(r.get("role") or r.get("runner") or "?")[:10]
            prov = str(r.get("provider") or "?")[:20]
            sf = str(r.get("source_function") or "")[:30]
            status = "BLOCKED" if r.get("blocked") else "OK"
            rl_flag = " RL" if r.get("rate_limit") else ""
            err = f" ERR" if r.get("error") else ""
            print(f"  {ts} {role:10s} {prov:20s} {sf:30s} {status}{rl_flag}{err}")

    print(f"{'='*65}\n")


if __name__ == "__main__":
    args = _parse_args()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.hours)

    role_filter = args.role or args.runner  # 向後相容

    records = _load_records(
        cutoff=cutoff,
        role_filter=role_filter,
        provider_filter=args.provider,
        blocked_only=args.blocked_only,
        rate_limited_only=args.rate_limited,
    )

    if args.json_out:
        tail = args.tail or 20
        output = records[-tail:] if tail else records
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        _summarize(records, hours=args.hours)
