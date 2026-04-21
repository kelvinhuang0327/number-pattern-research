#!/usr/bin/env python3
"""
Claude Planner tick — triggered every 10 min by launchd.
Reads backlog.md + recent completed tasks, calls `claude -p` to produce next 8h prompt.
"""

import argparse
import sys
import os
import json
import time
import logging
import subprocess
import re
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator import db, common

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [planner] %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

RUNNER = "planner"
WIKI_ROOT = os.path.join(common.ROOT, "wiki")
FALLBACK_WARNING = "%s — using local fallback payload"
DRY_RUN_HISTORY = "（dry-run：略過資料庫任務歷史）"


def _recent_history_summary(n=5) -> str:
    """Return recent tasks regardless of status so planner knows about failures."""
    conn = db.get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM agent_tasks ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
        tasks = [dict(r) for r in rows]
    finally:
        conn.close()

    if not tasks:
        return "（尚無任何歷史任務）"
    parts = []
    for t in tasks:
        status = t.get("status", "UNKNOWN")
        summary = (t.get("completed_text") or t.get("error_message") or "")[:400]
        parts.append(
            f"### [{status}] {t['title']} ({t['slot_key']})\n{summary}"
        )
    return "\n\n".join(parts)


def _extract_backlog_priorities(backlog: str, limit: int = 2) -> list[str]:
    items = []
    for line in backlog.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ["):
            item = re.sub(r"^- \[[ xX]\]\s*", "", stripped)
            if item:
                items.append(item)
        if len(items) >= limit:
            break
    return items


def _fallback_payload(backlog: str) -> dict:
    priorities = _extract_backlog_priorities(backlog)
    primary = priorities[0] if priorities else "檢查 backlog 並產出下一個可驗證任務"
    secondary = priorities[1] if len(priorities) > 1 else "整理驗證步驟、阻塞與後續 handoff"

    title_base = primary.split("：", 1)[-1].strip()
    title = title_base[:40] or "Backlog Validation Task"
    slug_hint = None
    match = re.search(r"`([^`]+)`", primary)
    if match:
        slug_hint = match.group(1)
    else:
        ascii_hint = re.sub(r"[^a-zA-Z0-9\s_-]", " ", primary).strip()
        slug_hint = ascii_hint
    slug = common.slugify(slug_hint or title) or "backlog-validation-task"

    prompt_markdown = f"""## Objective

從 backlog 的最高優先任務開始，完成一個可驗證、可交接的實作或驗證循環。

## Scope

1. 聚焦處理：{primary}
2. 次要延伸：{secondary}
3. 盤點相關程式與資料檔，確認現況、限制與可驗證方式
4. 完成最小必要修改或驗證，並保留清楚的完成摘要

## Constraints

- 不得修改 lottery_v2.db
- 不得繞過 lottery_api/CLAUDE.md 的驗證標準
- 優先採用最小變更，避免擴散到無關模組

## Acceptance Criteria

- 有明確的完成摘要或驗證結論
- 有列出異動檔案或確認無異動
- 有記錄尚未解決的風險與下一步

## Handoff Notes

- backlog 來源：runtime/agent_orchestrator/backlog.md
- orchestrator DB：runtime/agent_orchestrator/orchestrator.db
- 若有新策略驗證結果（PASS/REJECT），更新 wiki/games/<game>.md 的現役策略表
- 若為新教訓，在 wiki/lessons/key_lessons.md 末尾新增（格式：**L<N>** 說明）
- 若無新發現，Handoff Notes 填「wiki 無需更新」
- 完成後需在 completed 檔案留下人工可讀的摘要
"""

    return {
        "title": title,
        "slug": slug,
        "prompt_markdown": prompt_markdown,
    }


def _read_wiki_excerpt(path: str, max_lines: int = 60) -> str:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = []
            for _, line in zip(range(max_lines), handle):
                lines.append(line.rstrip("\n"))
        return "\n".join(lines).strip()
    except OSError:
        return ""


def _load_wiki_context(backlog: str) -> tuple[str, list[str]]:
    pages = [
        (
            "BIG_LOTTO",
            os.path.join(WIKI_ROOT, "games", "big_lotto.md"),
            ["BIG_LOTTO", "big_lotto", "大樂透", "49c6"],
        ),
        (
            "DAILY_539",
            os.path.join(WIKI_ROOT, "games", "daily_539.md"),
            ["DAILY_539", "daily_539", "今彩539", "539"],
        ),
        (
            "POWER_LOTTO",
            os.path.join(WIKI_ROOT, "games", "power_lotto.md"),
            ["POWER_LOTTO", "power_lotto", "威力彩", "38c6"],
        ),
    ]
    backlog_lower = backlog.lower()
    prioritized = []
    deferred = []
    for label, path, keywords in pages:
        entry = (label, path)
        if any(keyword.lower() in backlog_lower for keyword in keywords):
            prioritized.append(entry)
        else:
            deferred.append(entry)

    loaded = []
    labels = []
    for label, path in prioritized + deferred:
        excerpt = _read_wiki_excerpt(path)
        if excerpt:
            loaded.append(f"## {label}\n{excerpt}")
            labels.append(label)

    if labels:
        logger.info("Loaded wiki context from %d page(s): %s", len(labels), ", ".join(labels))
    else:
        logger.info("Wiki context unavailable; planner proceeding without injection")
    return "\n\n".join(loaded), labels


def _build_meta_prompt(planner_provider: str, recent_completed: str) -> tuple[str, list[str], str]:
    backlog = common.read_backlog()
    if not backlog:
        raise ValueError("backlog.md missing or empty — skip")

    wiki_context, wiki_labels = _load_wiki_context(backlog)
    meta_prompt = common.build_planner_meta_prompt(
        backlog=backlog,
        recent_completed=recent_completed,
        wiki_context=wiki_context,
        planner_provider=planner_provider,
    )
    return backlog, wiki_labels, meta_prompt


def _print_dry_run_preview(meta_prompt: str, wiki_labels: list[str]):
    preview = meta_prompt[:2000]
    print("Loaded wiki context from %d page(s): %s" % (len(wiki_labels), ", ".join(wiki_labels) or "none"))
    print("=== DRY-RUN: meta-prompt preview ===")
    print(preview)
    if len(meta_prompt) > len(preview):
        print("\n=== meta-prompt truncated at 2000 chars ===")
    print("\n=== wiki_context loaded from %d page(s) ===" % len(wiki_labels))
    if wiki_labels:
        print("\n".join(wiki_labels))


def _call_planner(meta_prompt: str, planner_provider: str) -> tuple[str, str]:
    try:
        runtime, command = common.planner_command(meta_prompt, planner_provider)
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        return runtime, result.stdout.strip() or result.stderr.strip()
    except subprocess.TimeoutExpired:
        raw = f"{planner_provider} planner timed out (180s)"
        logger.warning(FALLBACK_WARNING, raw)
        return "fallback", raw
    except Exception as exc:
        raw = f"{planner_provider} planner error: {exc}"
        logger.warning(FALLBACK_WARNING, raw)
        return "fallback", raw


def _extract_planner_payload(raw: str) -> Optional[dict]:
    json_str = raw
    if "```" in raw:
        fenced = re.search(r"```(?:json)?\s*(\{[^`]*\})\s*```", raw, re.DOTALL)
        if fenced:
            json_str = fenced.group(1)
    if not json_str.startswith("{"):
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            json_str = raw[start:end]
    try:
        return json.loads(json_str)
    except Exception:
        return None


def run(dry_run: bool = False):
    common.ensure_dirs()
    t0 = time.time()
    planner_provider = "claude" if dry_run else db.get_planner_provider()

    if dry_run:
        _, wiki_labels, meta_prompt = _build_meta_prompt(
            planner_provider=planner_provider,
            recent_completed=DRY_RUN_HISTORY,
        )
        _print_dry_run_preview(meta_prompt, wiki_labels)
        return

    if not db.is_scheduler_enabled():
        msg = "Scheduler is disabled — planner skip"
        logger.info(msg)
        db.log_tick(RUNNER, "PLANNER_SKIP_DISABLED", message=msg)
        common.log_jsonl(RUNNER, "PLANNER_SKIP_DISABLED")
        return

    latest = db.get_latest_task()

    if latest and latest["status"] not in ("COMPLETED", "FAILED", "CANCELLED"):
        msg = f"Previous task {latest['id']} still {latest['status']} — skip"
        logger.info(msg)
        db.log_tick(RUNNER, "PLANNER_SKIP_PREV_RUNNING", task_id=latest["id"], message=msg)
        common.log_jsonl(RUNNER, "PLANNER_SKIP_PREV_RUNNING", task_id=latest["id"])
        return

    try:
        backlog, wiki_labels, meta_prompt = _build_meta_prompt(
            planner_provider=planner_provider,
            recent_completed=_recent_history_summary(),
        )
    except ValueError as exc:
        msg = str(exc)
        logger.warning(msg)
        db.log_tick(RUNNER, "PLANNER_SKIP_NO_BACKLOG", message=msg)
        common.log_jsonl(RUNNER, "PLANNER_SKIP_NO_BACKLOG")
        return

    logger.info("Calling %s to generate next task prompt...", common.planner_provider_label(planner_provider))
    payload = None
    planner_source, raw = _call_planner(meta_prompt, planner_provider)

    if planner_source in ("claude", "codex"):
        payload = _extract_planner_payload(raw)
        if payload is None:
            planner_source = "fallback"
            msg = "Failed to parse planner JSON output"
            logger.warning(FALLBACK_WARNING, msg)
            db.log_tick(RUNNER, "PLANNER_FALLBACK_LOCAL", message=f"{msg}; raw={raw[:300]}")
            common.log_jsonl(RUNNER, "PLANNER_FALLBACK_LOCAL", error=msg, raw_output=raw[:300])

    if payload is None:
        payload = _fallback_payload(backlog)
        if planner_source == "fallback":
            common.log_jsonl(RUNNER, "PLANNER_FALLBACK_LOCAL", raw_output=raw[:300])

    title = payload["title"]
    slug = common.slugify(payload["slug"])
    prompt_markdown = payload["prompt_markdown"]

    slot_key = common.slot_key_now()
    date_folder = common.date_folder_now()
    p_path = common.prompt_path(slot_key, slug, date_folder)

    with open(p_path, "w") as f:
        f.write(f"# {title}\n\n")
        f.write(prompt_markdown)

    previous_task_id = latest["id"] if latest else None
    task_id = db.create_task(
        slot_key=slot_key,
        date_folder=date_folder,
        title=title,
        slug=slug,
        prompt_text=prompt_markdown,
        prompt_file_path=p_path,
        previous_task_id=previous_task_id,
    )

    common.write_meta(slot_key, date_folder,
                      task_id=task_id, title=title, slug=slug,
                      status="QUEUED", previous_task_id=previous_task_id,
                      planner_source=planner_source,
                      planner_provider=planner_provider)

    elapsed = int((time.time() - t0) * 1000)
    msg = f"Task {task_id} created: {title} [{slug}] via {planner_source}"
    logger.info(msg)
    db.log_tick(RUNNER, "PLANNER_PRODUCED", task_id=task_id, message=msg, duration_ms=elapsed)
    common.log_jsonl(
        RUNNER,
        "PLANNER_PRODUCED",
        task_id=task_id,
        title=title,
        slug=slug,
        planner_source=planner_source,
        planner_provider=planner_provider,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.dry_run:
        db.init_db()
    run(dry_run=args.dry_run)
