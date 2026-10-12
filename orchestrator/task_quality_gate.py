from __future__ import annotations

import re
import json
from dataclasses import dataclass
from difflib import SequenceMatcher
from hashlib import sha256
from typing import Optional


MAX_MAJOR_OBJECTIVES = 2
MAX_DATASET_COUNT = 2
MAX_REAL_COMPUTE_HOURS = 2
REQUIRED_OUTPUT_FIELDS = ("violations", "metrics", "regime_counts", "leakage_detected", "candidate_fix")
ALLOWED_DELIVERABLES = {"insight", "metric_delta", "violation_count", "candidate_patch"}
FORBIDDEN_TERMS = (
    "signal_exhausted",
    "no_signal",
    "停止建議",
    "目前沒有方向",
    # Generic task titles that lack measurable metrics / target files (Task 5 rule)
    "improve mlb model",
    "optimize prediction",
    "analyze system",
    "improve the model",
    "general cleanup",
    "misc improvements",
)

MONTE_CARLO_PATTERN = re.compile(r"(?i)monte\s*carlo|蒙特卡洛")
FINAL_RECOMMEND_PATTERN = re.compile(r"(?i)最終推薦|final recommendation|recommendation|推薦方案")
AUDIT_PATTERN = re.compile(r"(?i)audit|審計|驗證|盤點|檢查")
PROPOSAL_PATTERN = re.compile(r"(?i)proposal|修正方案|fix proposal|patch proposal|提案")


@dataclass(frozen=True)
class TaskQualityVerdict:
    quality_status: str
    rejection_reasons: list[str]
    criteria_results: dict[str, bool]

    @property
    def passed(self) -> bool:
        return self.quality_status == "PASS"


def build_task_dedupe_key(task_draft: dict) -> str:
    seed_parts = [
        str(task_draft.get("focus_area") or ""),
        str(task_draft.get("market_scope") or ""),
        str(task_draft.get("analysis_family") or ""),
        _normalize_text(_combine_task_text(task_draft)),
    ]
    seed = "|".join(part for part in seed_parts if part)
    return f"quality-gate:{sha256(seed.encode('utf-8')).hexdigest()[:16]}"


def evaluate_task_quality(task_draft: dict, recent_tasks: list[dict] | None = None) -> TaskQualityVerdict:
    recent_tasks = recent_tasks or []
    reasons, criteria = _collect_results(task_draft, recent_tasks)
    return _build_verdict(reasons, criteria)


def _build_verdict(reasons: list[str], criteria: dict[str, bool]) -> TaskQualityVerdict:
    quality_status = "PASS" if not reasons else "REJECT"
    return TaskQualityVerdict(
        quality_status=quality_status,
        rejection_reasons=reasons,
        criteria_results=criteria,
    )


def _combine_task_text(task_draft: dict) -> str:
    title = str(task_draft.get("title") or "")
    prompt_text = str(task_draft.get("prompt_text") or "")
    return "\n".join(part for part in (title, prompt_text) if part).strip()


def _collect_results(
    task_draft: dict, recent_tasks: list[dict]
) -> tuple[list[str], dict[str, bool]]:
    """回傳 (rejection_reasons, criteria_results) 兩者。"""
    reasons: list[str] = []
    criteria: dict[str, bool] = {}
    combined_text = _combine_task_text(task_draft)
    contract = _load_contract(task_draft)

    _check_forbidden_terms(combined_text.lower(), reasons, criteria)
    _check_compute_budget(task_draft, contract, reasons, criteria)
    _check_objective_granularity(task_draft, contract, reasons, criteria)
    _check_dataset_count(task_draft, contract, reasons, criteria)
    _check_output_contract(contract, combined_text, reasons, criteria)
    _check_loop_compatibility(task_draft, contract, reasons, criteria)
    _check_monte_carlo_isolation(task_draft, contract, combined_text, reasons, criteria)
    _check_narrative_only_recommendation(task_draft, contract, combined_text, reasons, criteria)
    _check_duplicate(task_draft, combined_text, recent_tasks, reasons, criteria)
    _check_fake_length(combined_text, reasons, criteria)

    return reasons, criteria


# Keep old name as alias for tests that import it directly
def _collect_rejection_reasons(combined_text: str, recent_tasks: list[dict]) -> list[str]:
    reasons, _ = _collect_results({"title": "", "prompt_text": combined_text}, recent_tasks)
    return reasons


def _check_forbidden_terms(lowered_text: str, reasons: list[str], criteria: dict[str, bool]) -> None:
    forbidden_hits = [term for term in FORBIDDEN_TERMS if term in lowered_text]
    passed = not forbidden_hits
    criteria["no_forbidden_terms"] = passed
    if not passed:
        reasons.append(
            "禁止內容: 任務含有禁止字樣 " + ", ".join(sorted(forbidden_hits))
        )


def _check_compute_budget(task_draft: dict, contract: dict, reasons: list[str], criteria: dict[str, bool]) -> None:
    expected_hours = int(task_draft.get("expected_duration_hours") or contract.get("expected_duration_hours") or 0)
    passed = expected_hours <= MAX_REAL_COMPUTE_HOURS
    criteria["within_compute_budget"] = passed
    if not passed:
        reasons.append(f"粒度要求: 任務預期計算時間超過 {MAX_REAL_COMPUTE_HOURS} 小時，當前為 {expected_hours} 小時")


def _check_objective_granularity(task_draft: dict, contract: dict, reasons: list[str], criteria: dict[str, bool]) -> None:
    objectives = task_draft.get("major_objectives") or contract.get("major_objectives") or []
    if isinstance(objectives, str):
        objectives = [objectives]
    objective_count = len([item for item in objectives if item]) or 1
    task_kind = str(task_draft.get("task_kind") or contract.get("task_kind") or "audit")
    deliverable_kind = str(task_draft.get("deliverable_kind") or contract.get("deliverable_kind") or "")
    passed = objective_count <= MAX_MAJOR_OBJECTIVES and deliverable_kind in ALLOWED_DELIVERABLES and task_kind in {"audit", "simulation", "proposal", "validation"}
    criteria["atomic_objective_ok"] = passed
    if not passed:
        reasons.append("粒度要求: 任務必須是單一/雙目標的原子任務，且需有可執行 deliverable_kind")


def _check_dataset_count(task_draft: dict, contract: dict, reasons: list[str], criteria: dict[str, bool]) -> None:
    dataset_paths = task_draft.get("dataset_paths") or contract.get("dataset_paths") or []
    passed = len(dataset_paths) <= MAX_DATASET_COUNT
    criteria["dataset_count_ok"] = passed
    if not passed:
        reasons.append(f"粒度要求: 任務資料集超過 {MAX_DATASET_COUNT} 個，請拆成多個 task")


def _check_output_contract(contract: dict, text: str, reasons: list[str], criteria: dict[str, bool]) -> None:
    required_fields = contract.get("required_output_fields") or REQUIRED_OUTPUT_FIELDS
    contract_ok = all(field in required_fields for field in REQUIRED_OUTPUT_FIELDS)
    text_ok = all(field in text for field in REQUIRED_OUTPUT_FIELDS)
    passed = contract_ok and text_ok
    criteria["output_contract_ok"] = passed
    if not passed:
        reasons.append("輸出要求: 任務必須輸出 violations / metrics / regime_counts / leakage_detected / candidate_fix JSON")


def _check_loop_compatibility(task_draft: dict, contract: dict, reasons: list[str], criteria: dict[str, bool]) -> None:
    signal_state_type = str(task_draft.get("signal_state_type") or contract.get("signal_state_type") or "")
    deliverable_kind = str(task_draft.get("deliverable_kind") or contract.get("deliverable_kind") or "")
    passed = bool(signal_state_type) and deliverable_kind in ALLOWED_DELIVERABLES
    criteria["loop_compatible"] = passed
    if not passed:
        reasons.append("Loop Compatibility: 任務缺少可行的 signal_state_type 或 deliverable_kind")


def _check_monte_carlo_isolation(task_draft: dict, contract: dict, text: str, reasons: list[str], criteria: dict[str, bool]) -> None:
    task_kind = str(task_draft.get("task_kind") or contract.get("task_kind") or "audit")
    mentions_monte_carlo = bool(MONTE_CARLO_PATTERN.search(text))
    mixes_audit = mentions_monte_carlo and bool(AUDIT_PATTERN.search(text)) and task_kind != "simulation"
    mixes_proposal = mentions_monte_carlo and bool(PROPOSAL_PATTERN.search(text)) and task_kind != "simulation"
    passed = not mixes_audit and not mixes_proposal
    criteria["monte_carlo_isolated"] = passed
    if not passed:
        reasons.append("Monte Carlo 隔離: 模擬任務必須獨立，不可與 audit 或 proposal 混在同一 task")


def _check_narrative_only_recommendation(task_draft: dict, contract: dict, text: str, reasons: list[str], criteria: dict[str, bool]) -> None:
    task_kind = str(task_draft.get("task_kind") or contract.get("task_kind") or "audit")
    asks_final_recommendation = bool(FINAL_RECOMMEND_PATTERN.search(text))
    passed = not asks_final_recommendation or task_kind == "proposal"
    criteria["no_bundled_recommendation"] = passed
    if not passed:
        reasons.append("粒度要求: 不可在 audit / simulation 任務中要求最終推薦或總結性結論")


def _check_duplicate(
    task_draft: dict, text: str, recent_tasks: list[dict], reasons: list[str], criteria: dict[str, bool]
) -> None:
    duplicate_reason = _detect_duplicate_task(
        text,
        recent_tasks,
        current_focus=str(task_draft.get("focus_area") or ""),
        current_family=str(task_draft.get("analysis_family") or ""),
    )
    criteria["not_duplicate"] = duplicate_reason is None
    if duplicate_reason:
        reasons.append(duplicate_reason)


def _check_fake_length(text: str, reasons: list[str], criteria: dict[str, bool]) -> None:
    fake_long_reason = _detect_fake_length(text)
    criteria["not_fake_length"] = fake_long_reason is None
    if fake_long_reason:
        reasons.append(fake_long_reason)


def _load_contract(task_draft: dict) -> dict:
    raw_contract = task_draft.get("contract_json")
    if isinstance(raw_contract, dict):
        return raw_contract
    if isinstance(raw_contract, str) and raw_contract.strip():
        try:
            return json.loads(raw_contract)
        except json.JSONDecodeError:
            return {}
    return {}


def _detect_duplicate_task(
    text: str,
    recent_tasks: list[dict],
    current_focus: str = "",
    current_family: str = "",
) -> str | None:
    """
    重複性偵測:
    1. dedupe_key 完全相同 → 拒絕（內容完全重複）
    2. text similarity >= 0.82 AND (focus_area 或 analysis_family 相同) → 拒絕
       （防止同 blueprint 同週期的近似重複任務；不同 family 的高相似文本不拒絕）
    純 text similarity >= 0.82（無 focus_area/family 信息）保持舊行為向下相容。
    """
    normalized_current = _normalize_text(text)
    current_dedupe_key = build_task_dedupe_key({"title": "", "prompt_text": text})

    for task in recent_tasks[:50]:
        if not task:
            continue

        # Dimension 1: exact dedupe_key match → always reject
        prior_dedupe_key = str(task.get("dedupe_key") or "")
        if prior_dedupe_key and prior_dedupe_key == current_dedupe_key:
            return "重複性檢查: 任務與最近任務 dedupe_key 相同，focus / 結構 / 輸出要求重複"

        # Dimension 2: text similarity check (relaxed: requires same family context)
        prior_text = "\n".join(
            part for part in (str(task.get("title") or ""), str(task.get("prompt_text") or "")) if part
        ).strip()
        if not prior_text:
            continue
        normalized_prior = _normalize_text(prior_text)
        similarity = SequenceMatcher(None, normalized_current, normalized_prior).ratio()
        if similarity >= 0.82:
            # Check if they share focus_area or analysis_family (same blueprint family)
            prior_focus = str(task.get("focus_area") or "")
            prior_family = str(task.get("analysis_family") or "")
            same_family = (
                (prior_focus and current_focus and prior_focus == current_focus)
                or (prior_family and current_family and prior_family == current_family)
            )
            # If no family context available, fall back to old behavior (reject on similarity alone)
            if same_family or (not prior_focus and not prior_family and not current_focus and not current_family):
                return "重複性檢查: 任務與最近任務高度相似，focus / 結構 / 輸出要求重複"

    return None


def _detect_fake_length(text: str) -> str | None:
    non_empty_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not non_empty_lines:
        return "禁止偽長任務: 任務內容為空"
    repeated_line_ratio = 1 - (len(set(non_empty_lines)) / len(non_empty_lines))
    if repeated_line_ratio >= 0.35:
        return "禁止偽長任務: 任務存在大量重複描述"
    return None


def _normalize_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return normalized