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
import tempfile
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
    output_last_message_path = None
    try:
        runtime, command = common.planner_command(meta_prompt, planner_provider)
        if runtime == "codex":
            with tempfile.NamedTemporaryFile(prefix="planner-last-message-", suffix=".txt", delete=False) as handle:
                output_last_message_path = handle.name
            prompt_arg = command[-1]
            command = [*command[:-1], "--output-last-message", output_last_message_path, prompt_arg]
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        if output_last_message_path and os.path.exists(output_last_message_path):
            with open(output_last_message_path, "r", encoding="utf-8") as handle:
                last_message = handle.read().strip()
            if last_message:
                return runtime, last_message
        return runtime, result.stdout.strip() or result.stderr.strip()
    except subprocess.TimeoutExpired:
        raw = f"{planner_provider} planner timed out (180s)"
        logger.warning(FALLBACK_WARNING, raw)
        return "fallback", raw
    except Exception as exc:
        raw = f"{planner_provider} planner error: {exc}"
        logger.warning(FALLBACK_WARNING, raw)
        return "fallback", raw
    finally:
        if output_last_message_path and os.path.exists(output_last_message_path):
            try:
                os.remove(output_last_message_path)
            except OSError:
                pass


def _extract_planner_payload(raw: str) -> Optional[dict]:
    json_str = raw.strip()
    if "```" in json_str:
        fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", json_str)
        if fenced:
            json_str = fenced.group(1).strip()
    if not json_str.startswith("{"):
        start = json_str.find("{")
        end = json_str.rfind("}") + 1
        if start != -1 and end > start:
            json_str = json_str[start:end]
    try:
        return json.loads(json_str)
    except Exception:
        return None


def _payload_has_template_placeholders(payload: dict) -> bool:
    title = str(payload.get("title", "")).strip()
    slug = str(payload.get("slug", "")).strip()
    prompt_markdown = str(payload.get("prompt_markdown", "")).strip()
    markers = [
        "<任務標題",
        "<kebab-case",
        "<完整的 8 小時任務 prompt",
        "任務標題，中英文皆可",
        "kebab-case 英文識別碼",
        "完整的 8 小時任務 prompt",
        "{{",
        "}}",
    ]
    combined = "\n".join([title, slug, prompt_markdown])
    return any(marker in combined for marker in markers)


def _validate_payload(payload: dict) -> tuple[bool, str]:
    title = str(payload.get("title", "")).strip()
    slug = str(payload.get("slug", "")).strip()
    prompt_markdown = str(payload.get("prompt_markdown", "")).strip()

    if not title or not slug or not prompt_markdown:
        return False, "payload missing required keys: title/slug/prompt_markdown"
    if len(title) > 40:
        return False, "title exceeds 40 characters"
    if _payload_has_template_placeholders(payload):
        return False, "planner output still contains template placeholders"
    if not re.fullmatch(r"[a-z0-9-]{3,40}", common.slugify(slug) or ""):
        return False, "slug is not valid kebab-case after normalization"
    required_sections = [
        "## Objective",
        "## Scope",
        "## Constraints",
        "## Acceptance Criteria",
        "## Handoff Notes",
    ]
    for section in required_sections:
        if section not in prompt_markdown:
            return False, f"prompt_markdown missing section: {section}"
    if len(prompt_markdown) < 200:
        return False, "prompt_markdown too short"
    return True, ""


def _build_retry_prompt(meta_prompt: str, reason: str) -> str:
    return (
        meta_prompt
        + "\n\n"
        + "上一輪輸出無效，請重新輸出，且只輸出 JSON。\n"
        + f"無效原因：{reason}\n"
        + "請輸出實際值，不得包含模板詞或佔位符。"
    )


def _planner_candidates(provider: str) -> list[str]:
    requested = common.normalize_planner_provider(provider)
    ordered = [requested]
    ordered.append("claude" if requested == "codex" else "codex")
    deduped = []
    for item in ordered:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _attempt_planner_payload(meta_prompt: str, planner_provider: str) -> tuple[Optional[dict], str, str, str]:
    planner_source, raw = _call_planner(meta_prompt, planner_provider)
    parse_or_validate_error = ""
    payload = None

    if planner_source in ("claude", "codex"):
        payload = _extract_planner_payload(raw)
        if payload is None:
            parse_or_validate_error = "failed to parse planner JSON output"
        else:
            ok, reason = _validate_payload(payload)
            if not ok:
                parse_or_validate_error = reason

        if parse_or_validate_error:
            retry_prompt = _build_retry_prompt(meta_prompt, parse_or_validate_error)
            retry_source, retry_raw = _call_planner(retry_prompt, planner_provider)
            if retry_source in ("claude", "codex"):
                retry_payload = _extract_planner_payload(retry_raw)
                if retry_payload is not None:
                    ok, reason = _validate_payload(retry_payload)
                    if ok:
                        payload = retry_payload
                        raw = retry_raw
                        planner_source = retry_source
                        parse_or_validate_error = ""
                    else:
                        raw = retry_raw
                        parse_or_validate_error = reason
                else:
                    raw = retry_raw

    return payload, planner_source, raw, parse_or_validate_error


def _generate_planner_payload(meta_prompt: str, planner_provider: str) -> tuple[Optional[dict], str, str, str, str]:
    requested_provider = common.normalize_planner_provider(planner_provider)
    last_raw = ""
    attempt_errors = []

    for candidate in _planner_candidates(requested_provider):
        available, reason = common.provider_available("planner", candidate)
        if not available:
            attempt_errors.append(f"{candidate} unavailable: {reason}")
            continue

        logger.info("Calling %s to generate next task prompt...", common.planner_provider_label(candidate))
        payload, planner_source, raw, parse_error = _attempt_planner_payload(meta_prompt, candidate)
        last_raw = raw
        if payload is not None:
            return payload, planner_source, candidate, requested_provider, ""

        if _planner_error_is_runtime_blocker(raw):
            detail = raw
        elif parse_error and raw:
            detail = f"{parse_error}; raw={raw[:300]}"
        else:
            detail = parse_error or raw or f"{candidate} returned no usable output"
        attempt_errors.append(f"{candidate}: {detail}")

    reason = " | ".join(attempt_errors) if attempt_errors else "no planner providers available"
    return None, "fallback", requested_provider, requested_provider, reason


def _planner_error_is_runtime_blocker(reason: str) -> bool:
    lowered = str(reason or "").lower()
    markers = [
        "usage limit",
        "hit your limit",
        "hit your usage limit",
        "quota",
        "not logged in",
        "auth failed",
        "permission denied",
        "timed out",
    ]
    return any(marker in lowered for marker in markers)


def _extract_section_lines(markdown: str, header: str) -> list[str]:
    """
    Extract bullet/number lines under a markdown header, stopping at next header.
    """
    lines = str(markdown or "").splitlines()
    out = []
    in_section = False
    for raw in lines:
        line = raw.rstrip()
        if line.strip().startswith("## "):
            if in_section:
                break
            in_section = (line.strip() == header)
            continue
        if not in_section:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        stripped = re.sub(r"^[-*]\s+", "", stripped)
        stripped = re.sub(r"^\d+\.\s+", "", stripped)
        if stripped:
            out.append(stripped)
    return out


def _build_task_contract(payload: dict) -> dict:
    title = str(payload.get("title", "")).strip()
    prompt_markdown = str(payload.get("prompt_markdown", "")).strip()
    objective_lines = _extract_section_lines(prompt_markdown, "## Objective")
    scope = _extract_section_lines(prompt_markdown, "## Scope")
    constraints = _extract_section_lines(prompt_markdown, "## Constraints")
    acceptance = _extract_section_lines(prompt_markdown, "## Acceptance Criteria")
    handoff = _extract_section_lines(prompt_markdown, "## Handoff Notes")

    contract = {
        "version": "1.0",
        "objective": objective_lines[0] if objective_lines else title,
        "scope": scope or [f"完成任務：{title}"],
        "constraints": constraints or [
            "seed=42",
            "不得修改 lottery_api/data/lottery_v2.db",
            "不得直接改寫 strategy_states 配置檔",
        ],
        "acceptance_tests": acceptance or [
            "輸出需包含可驗證結論與證據",
            "列出異動檔案或明確標註無異動",
        ],
        "required_outputs": [
            "completed_markdown",
            "task_result_json",
            "changed_files_list",
        ],
        "forbidden_changes": [
            "lottery_api/data/lottery_v2.db",
            "lottery_api/data/strategy_states_",
        ],
        "handoff_questions": handoff or [
            "本輪結論是否達到 Acceptance Criteria？",
            "若未達標，下一輪需要調整哪個假設或範圍？",
        ],
    }
    return contract


def _build_worker_prompt_with_contract(prompt_markdown: str, contract: dict) -> str:
    contract_json = json.dumps(contract, ensure_ascii=False, indent=2)
    return (
        "## Task Contract (Orchestrator Enforced)\n\n"
        "Worker 必須遵守以下契約，否則任務會被標記為 REPLAN_REQUIRED：\n\n"
        f"```json\n{contract_json}\n```\n\n"
        "---\n\n"
        f"{prompt_markdown.strip()}\n"
    )


def run(dry_run: bool = False, force: bool = False):
    common.ensure_dirs()
    t0 = time.time()
    planner_provider = "claude" if dry_run else db.get_planner_provider()
    request_id = str(os.environ.get("ORCHESTRATOR_REQUEST_ID", "")).strip() or None

    if dry_run:
        _, wiki_labels, meta_prompt = _build_meta_prompt(
            planner_provider=planner_provider,
            recent_completed=DRY_RUN_HISTORY,
        )
        _print_dry_run_preview(meta_prompt, wiki_labels)
        return

    if not force and not db.is_scheduler_enabled():
        msg = "Scheduler is disabled — planner skip"
        logger.info(msg)
        db.log_tick(RUNNER, "PLANNER_SKIP_DISABLED", message=msg, request_id=request_id)
        common.log_jsonl(RUNNER, "PLANNER_SKIP_DISABLED")
        return

    latest = db.get_latest_task()

    if latest and latest["status"] not in ("COMPLETED", "FAILED", "CANCELLED", "REPLAN_REQUIRED"):
        msg = f"Previous task {latest['id']} still {latest['status']} — skip"
        logger.info(msg)
        db.log_tick(RUNNER, "PLANNER_SKIP_PREV_RUNNING", task_id=latest["id"], message=msg, request_id=request_id)
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
        db.log_tick(RUNNER, "PLANNER_SKIP_NO_BACKLOG", message=msg, request_id=request_id)
        common.log_jsonl(RUNNER, "PLANNER_SKIP_NO_BACKLOG")
        return

    payload, planner_source, effective_planner_provider, requested_planner_provider, planner_error = _generate_planner_payload(
        meta_prompt,
        planner_provider,
    )

    if payload is None:
        msg = f"Planner output invalid: {planner_error}"
        logger.warning(FALLBACK_WARNING, msg)
        db.log_tick(RUNNER, "PLANNER_FALLBACK_LOCAL", message=msg[:600], request_id=request_id)
        common.log_jsonl(RUNNER, "PLANNER_FALLBACK_LOCAL", error=msg[:600])
        if _planner_error_is_runtime_blocker(planner_error):
            skip_msg = f"Planner runtime blocked; no task created: {planner_error}"
            logger.warning(skip_msg)
            db.log_tick(RUNNER, "PLANNER_SKIP_PROVIDER_FAILURE", message=skip_msg[:600], request_id=request_id)
            common.log_jsonl(RUNNER, "PLANNER_SKIP_PROVIDER_FAILURE", error=skip_msg[:600])
            return
    elif effective_planner_provider != requested_planner_provider:
        msg = (
            f"Planner provider fallback: requested {requested_planner_provider}, "
            f"used {effective_planner_provider}"
        )
        db.log_tick(RUNNER, "PLANNER_PROVIDER_FALLBACK", message=msg, request_id=request_id)
        common.log_jsonl(
            RUNNER,
            "PLANNER_PROVIDER_FALLBACK",
            requested_provider=requested_planner_provider,
            effective_provider=effective_planner_provider,
        )

    if payload is None:
        payload = _fallback_payload(backlog)
        if planner_source == "fallback":
            common.log_jsonl(RUNNER, "PLANNER_FALLBACK_LOCAL", fallback_title=payload.get("title"))

    title = payload["title"]
    slug = common.slugify(payload["slug"])
    prompt_markdown = payload["prompt_markdown"]
    contract = _build_task_contract(payload)
    contract_ok, contract_reason = common.validate_task_contract(contract)
    if not contract_ok:
        msg = f"Planner generated invalid task contract: {contract_reason}"
        logger.warning(msg)
        db.log_tick(RUNNER, "PLANNER_INVALID_CONTRACT", message=msg, request_id=request_id)
        common.log_jsonl(RUNNER, "PLANNER_INVALID_CONTRACT", error=contract_reason)
        return

    slot_key = common.slot_key_now()
    date_folder = common.date_folder_now()
    p_path = common.prompt_path(slot_key, slug, date_folder)
    contract_file_path = common.contract_path(slot_key, slug, date_folder)
    worker_prompt = _build_worker_prompt_with_contract(prompt_markdown, contract)

    with open(p_path, "w") as f:
        f.write(f"# {title}\n\n")
        f.write(worker_prompt)
    with open(contract_file_path, "w", encoding="utf-8") as f:
        json.dump(contract, f, ensure_ascii=False, indent=2)

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
                      planner_provider=effective_planner_provider,
                      planner_requested_provider=requested_planner_provider,
                      task_contract_path=contract_file_path,
                      task_contract_version=contract.get("version"))

    elapsed = int((time.time() - t0) * 1000)
    msg = f"Task {task_id} created: {title} [{slug}] via {planner_source}"
    logger.info(msg)
    db.log_tick(RUNNER, "PLANNER_PRODUCED", task_id=task_id, message=msg, duration_ms=elapsed, request_id=request_id)
    common.log_jsonl(
        RUNNER,
        "PLANNER_PRODUCED",
        task_id=task_id,
        title=title,
        slug=slug,
        planner_source=planner_source,
        planner_provider=effective_planner_provider,
        planner_requested_provider=requested_planner_provider,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.dry_run:
        db.init_db()
    force_run = str(os.environ.get("ORCHESTRATOR_FORCE_RUN", "")).strip().lower() in ("1", "true", "yes", "on")
    run(dry_run=args.dry_run, force=force_run)
