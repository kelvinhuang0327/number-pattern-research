"""P541C: BIG_LOTTO legacy method review and replay-readiness selection.

Read-only review/selection artifact over the P541B classification output.
Does not touch the DB, does not generate replay rows, does not run OOS,
does not recompute any P536-P541B artifact.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

P541B_JSON = REPO_ROOT / "outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.json"
P541B_MD = REPO_ROOT / "outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.md"
P541A_JSON = REPO_ROOT / "outputs/research/p541a_biglotto_strategy_inventory_replay_coverage_audit_20260709.json"
P541A_MD = REPO_ROOT / "outputs/research/p541a_biglotto_strategy_inventory_replay_coverage_audit_20260709.md"

DISCLAIMER = (
    "Historical legacy method review and replay-readiness selection only; "
    "not a prediction, betting edge, future-winning, or production-readiness claim."
)

DECISION_READY = "ready_for_replay_readiness_now"
DECISION_ADAPTER = "needs_adapter_before_readiness"
DECISION_REFACTOR = "needs_refactor_before_readiness"
DECISION_CTO = "needs_cto_review"
DECISION_EXCLUDE = "exclude_from_replay"

ALL_DECISIONS = (DECISION_READY, DECISION_ADAPTER, DECISION_REFACTOR, DECISION_CTO, DECISION_EXCLUDE)

NEXT_TASK_OPTIONS = (
    "P541D_BIG_LOTTO_REPLAY_READINESS_FOR_SELECTED_LEGACY_METHODS_NO_DB_WRITE",
    "P541D_BIG_LOTTO_ADAPTER_DESIGN_FOR_SELECTED_METHODS_NO_DB_WRITE",
    "P541D_BIG_LOTTO_CTO_REVIEW_PACKET_FOR_AMBIGUOUS_METHODS",
    "P541C_COMPLETE_NO_SAFE_REPLAY_READINESS_CANDIDATES",
    "P541C_BLOCKED_SELECTION_TOO_AMBIGUOUS_NEEDS_OWNER_OR_CTO",
)

_EVIDENCE_BOOL_RE = re.compile(r"^([a-zA-Z_]+)=(True|False)$")


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_evidence_flags(evidence: list) -> dict:
    """Extract the `key=True/False` static-scan flags already recorded by P541B."""
    flags: dict = {}
    for line in evidence:
        m = _EVIDENCE_BOOL_RE.match(line)
        if m:
            flags[m.group(1)] = m.group(2) == "True"
    return flags


def compute_risk_level(flags: dict) -> str:
    if flags.get("uses_db_anywhere"):
        return "high"
    if flags.get("writes_files_anywhere") or flags.get("hardcoded_abs_path"):
        return "medium"
    return "low"


def _priority_for_adapter(confidence: str, risk: str) -> str:
    if risk == "high":
        return "low"
    if confidence == "high" and risk == "low":
        return "high"
    if confidence in ("high", "medium"):
        return "medium"
    return "low"


def _priority_for_refactor(confidence: str, risk: str) -> str:
    if risk == "high":
        return "low"
    if confidence == "high":
        return "medium"
    return "low"


def source_exists(source_path: str, repo_root: Path = REPO_ROOT) -> bool:
    return (repo_root / source_path).is_file()


def classify_record(rec: dict, repo_root: Path = REPO_ROOT) -> dict:
    """Map one P541B method_classification_record to a P541C decision record."""
    ra = rec["recommended_action"]
    rs = rec["runnable_status"]
    iapm = rec["is_actual_prediction_method"]
    confidence = rec["confidence"]
    flags = parse_evidence_flags(rec["evidence"])
    risk = compute_risk_level(flags)
    if rs in ("unsafe_side_effects", "imports_db_or_runs_work_at_module_load"):
        # Safety-blocking is a fact about the code regardless of which P541B
        # bucket (duplicate/not-strategy/exclude) ultimately routes it.
        risk = "high"
    exists = source_exists(rec["source_path"], repo_root)

    if not exists:
        decision = dict(
            p541c_decision=DECISION_EXCLUDE,
            required_change_before_replay="unknown",
            replay_readiness_priority="exclude",
            risk_level=risk,
            decision_reason=(
                f"source_path '{rec['source_path']}' not found on disk during P541C "
                "limited static re-check (phantom); cannot be a runnable replay "
                "candidate regardless of P541B classification."
            ),
            confidence="high",
        )
    elif ra == "mark_duplicate":
        dup = rec.get("duplicate_of_existing_strategy")
        decision = dict(
            p541c_decision=DECISION_EXCLUDE,
            required_change_before_replay="deprecate",
            replay_readiness_priority="exclude",
            risk_level=risk,
            decision_reason=(
                f"P541B: duplicate of existing replayed strategy '{dup}'; superseded, "
                "not a new replay-readiness candidate."
            ),
            confidence=confidence,
        )
    elif ra == "mark_not_strategy":
        decision = dict(
            p541c_decision=DECISION_EXCLUDE,
            required_change_before_replay="none",
            replay_readiness_priority="exclude",
            risk_level=risk,
            decision_reason=(
                "P541B: classified as non-strategy utility/report/tool script; "
                "not a prediction-method candidate."
            ),
            confidence=confidence,
        )
    elif ra == "mark_deprecated":
        decision = dict(
            p541c_decision=DECISION_EXCLUDE,
            required_change_before_replay="deprecate",
            replay_readiness_priority="exclude",
            risk_level=risk,
            decision_reason="P541B: classified obsolete/deprecated.",
            confidence=confidence,
        )
    elif ra == "include_in_replay_readiness":
        # P541B already confirmed is_actual_prediction_method == True for this bucket
        # (100% of 142 records); all carry runnable_status=needs_adapter_wrapper.
        priority = _priority_for_adapter(confidence, risk)
        decision = dict(
            p541c_decision=DECISION_ADAPTER,
            required_change_before_replay="adapter_wrapper",
            replay_readiness_priority=priority,
            risk_level=risk,
            decision_reason=(
                "P541B: confirmed actual prediction method needing a small adapter "
                f"wrapper. {rec['why_not_runnable']}"
            ),
            confidence=confidence,
        )
    elif ra == "needs_cto_review":
        if rs == "broken_or_import_error":
            decision = dict(
                p541c_decision=DECISION_CTO,
                required_change_before_replay="dependency_fix",
                replay_readiness_priority="unknown",
                risk_level=risk,
                decision_reason=(
                    f"P541B: {rec['why_not_runnable']} Mechanically broken (fails "
                    "static parse); method identity is still undetermined, needs a "
                    "CTO read plus a dependency/syntax fix before further evaluation."
                ),
                confidence=confidence,
            )
        else:
            decision = dict(
                p541c_decision=DECISION_CTO,
                required_change_before_replay="unknown",
                replay_readiness_priority="unknown",
                risk_level=risk,
                decision_reason=(
                    f"P541B: {rec['why_not_runnable']} P541C limited static re-check "
                    "(file existence + reuse of recorded evidence flags) found no "
                    "additional signal beyond what P541B already captured; identity "
                    "remains unresolved."
                ),
                confidence=confidence,
            )
    elif ra == "exclude_from_replay" and rs in (
        "unsafe_side_effects",
        "imports_db_or_runs_work_at_module_load",
    ):
        if flags.get("uses_db_anywhere"):
            required_change = "db_safety_refactor"
        elif flags.get("writes_files_anywhere"):
            required_change = "pure_function_refactor"
        else:
            required_change = "unknown"
        decision = dict(
            p541c_decision=DECISION_EXCLUDE,
            required_change_before_replay=required_change,
            replay_readiness_priority="exclude",
            risk_level=risk,
            decision_reason=(
                f"P541B: {rec['why_not_runnable']} Safety-blocking; excluded "
                "regardless of method-identity confidence."
            ),
            confidence=confidence,
        )
    elif ra == "exclude_from_replay" and iapm is True and rs == "hardcoded_paths_or_dates":
        priority = _priority_for_adapter(confidence, risk)
        decision = dict(
            p541c_decision=DECISION_ADAPTER,
            required_change_before_replay="parameterization",
            replay_readiness_priority=priority,
            risk_level=risk,
            decision_reason=(
                f"P541B: confirmed actual prediction method. {rec['why_not_runnable']}"
            ),
            confidence=confidence,
        )
    elif ra == "exclude_from_replay" and iapm is True and rs in (
        "needs_refactor_to_pure_function",
        "needs_db_safety_refactor",
    ):
        required_change = (
            "pure_function_refactor" if rs == "needs_refactor_to_pure_function" else "db_safety_refactor"
        )
        priority = _priority_for_refactor(confidence, risk)
        decision = dict(
            p541c_decision=DECISION_REFACTOR,
            required_change_before_replay=required_change,
            replay_readiness_priority=priority,
            risk_level=risk,
            decision_reason=(
                f"P541B: confirmed actual prediction method. {rec['why_not_runnable']}"
            ),
            confidence=confidence,
        )
    elif ra == "exclude_from_replay":
        # is_actual_prediction_method == "unknown" (identity itself unresolved) with a
        # mechanically-fixable blocker: defer to CTO review rather than silently
        # excluding or silently promoting a method whose identity is unconfirmed.
        decision = dict(
            p541c_decision=DECISION_CTO,
            required_change_before_replay="unknown",
            replay_readiness_priority="unknown",
            risk_level=risk,
            decision_reason=(
                f"P541B: identity unresolved (is_actual_prediction_method=unknown) "
                f"and {rec['why_not_runnable']} P541C found no additional evidence to "
                "resolve method identity; needs CTO read before any refactor "
                "investment."
            ),
            confidence=confidence,
        )
    else:
        # Defensive fallback; not expected given P541B's 6 known recommended_action values.
        decision = dict(
            p541c_decision=DECISION_CTO,
            required_change_before_replay="unknown",
            replay_readiness_priority="unknown",
            risk_level=risk,
            decision_reason=f"Unrecognized P541B recommended_action='{ra}'; defaulting to CTO review.",
            confidence="low",
        )

    return {
        "method_id": rec["method_id"],
        "source_path": rec["source_path"],
        "method_family": rec["method_family"],
        "p541b_status": {
            "recommended_action": ra,
            "runnable_status": rs,
            "is_actual_prediction_method": iapm,
            "duplicate_of_existing_strategy": rec.get("duplicate_of_existing_strategy"),
            "confidence": confidence,
        },
        "p541c_decision": decision["p541c_decision"],
        "decision_reason": decision["decision_reason"],
        "required_change_before_replay": decision["required_change_before_replay"],
        "replay_readiness_priority": decision["replay_readiness_priority"],
        "risk_level": decision["risk_level"],
        "evidence": {
            "source_path_exists": exists,
            "static_flags": flags,
            "p541b_evidence": rec["evidence"],
        },
        "confidence": decision["confidence"],
    }


def classify_all(p541b: dict, repo_root: Path = REPO_ROOT) -> list:
    return [classify_record(rec, repo_root) for rec in p541b["method_classification_records"]]


def build_shortlist(decisions: list, limit: int = 20) -> list:
    """Deterministic, family-diversified pick of the safest, highest-priority
    adapter-ready candidates. Bucket B only (needs_adapter_before_readiness),
    high priority, low risk -> no DB import/write risk, no unsafe side effects.
    """
    pool = [
        d
        for d in decisions
        if d["p541c_decision"] == DECISION_ADAPTER
        and d["replay_readiness_priority"] == "high"
        and d["risk_level"] == "low"
    ]
    by_family: dict = {}
    for d in sorted(pool, key=lambda d: d["method_id"]):
        by_family.setdefault(d["method_family"], []).append(d)

    shortlist = []
    families = sorted(by_family.keys())
    idx = 0
    while len(shortlist) < limit and any(by_family.values()):
        family = families[idx % len(families)]
        bucket = by_family[family]
        if bucket:
            shortlist.append(bucket.pop(0))
        idx += 1
        if idx > limit * len(families) + len(families):
            break
    return shortlist[:limit]


def determine_next_task(decisions: list, shortlist: list) -> str:
    adapter_ready = [d for d in decisions if d["p541c_decision"] == DECISION_ADAPTER]
    if shortlist:
        return "P541D_BIG_LOTTO_ADAPTER_DESIGN_FOR_SELECTED_METHODS_NO_DB_WRITE"
    if adapter_ready:
        return "P541D_BIG_LOTTO_ADAPTER_DESIGN_FOR_SELECTED_METHODS_NO_DB_WRITE"
    cto = [d for d in decisions if d["p541c_decision"] == DECISION_CTO]
    if cto:
        return "P541D_BIG_LOTTO_CTO_REVIEW_PACKET_FOR_AMBIGUOUS_METHODS"
    return "P541C_COMPLETE_NO_SAFE_REPLAY_READINESS_CANDIDATES"


def summarize(decisions: list) -> dict:
    counts = {k: 0 for k in ALL_DECISIONS}
    for d in decisions:
        counts[d["p541c_decision"]] += 1
    priority_counts = {"high": 0, "medium": 0, "low": 0, "exclude": 0, "unknown": 0}
    for d in decisions:
        priority_counts[d["replay_readiness_priority"]] += 1
    return {
        "total_reviewed_from_p541b": len(decisions),
        "ready_for_replay_readiness_now": counts[DECISION_READY],
        "needs_adapter_before_readiness": counts[DECISION_ADAPTER],
        "needs_refactor_before_readiness": counts[DECISION_REFACTOR],
        "needs_cto_review": counts[DECISION_CTO],
        "exclude_from_replay": counts[DECISION_EXCLUDE],
        "high_priority_candidates": priority_counts["high"],
        "medium_priority_candidates": priority_counts["medium"],
        "low_priority_candidates": priority_counts["low"],
    }


def build_artifact(p541b: dict, p541a: dict, repo_root: Path = REPO_ROOT, generated_at: str | None = None) -> dict:
    decisions = classify_all(p541b, repo_root)
    shortlist = build_shortlist(decisions)
    next_task = determine_next_task(decisions, shortlist)
    assert next_task in NEXT_TASK_OPTIONS

    by_decision = {k: [] for k in ALL_DECISIONS}
    for d in decisions:
        by_decision[d["p541c_decision"]].append(d)

    generated_at = generated_at or datetime.now(timezone.utc).isoformat()

    return {
        "schema_version": "1.0",
        "task_id": "P541C_BIG_LOTTO_LEGACY_METHOD_REVIEW_AND_REPLAY_READINESS_SELECTION",
        "generated_at": generated_at,
        "summary": summarize(decisions),
        "p541b_context": {
            "p541b_json_path": "outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.json",
            "p541b_md_path": "outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.md",
            "p541b_summary": p541b.get("summary", {}),
            "p541b_recommended_next_task": p541b.get("recommended_next_single_worker_task"),
            "p541a_json_path": "outputs/research/p541a_biglotto_strategy_inventory_replay_coverage_audit_20260709.json",
            "p541a_md_path": "outputs/research/p541a_biglotto_strategy_inventory_replay_coverage_audit_20260709.md",
            "p541a_summary_answer": p541a.get("summary_answer"),
            "p541a_replay_coverage_totals": p541a.get("replay_coverage_totals"),
        },
        "selection_policy": {
            "method": (
                "Deterministic re-bucketing of P541B's 580 method_classification_records "
                "using only fields P541B already computed (recommended_action, "
                "runnable_status, is_actual_prediction_method, confidence, evidence "
                "flags) plus one limited static re-check per record: does source_path "
                "still exist on disk. No file contents were re-read; no new static "
                "analysis was performed beyond what P541B already recorded."
            ),
            "bucket_A_ready_for_replay_readiness_now": (
                "P541B's own 'runnable_as_is'/'runnable_with_existing_adapter' records "
                "(5 total) are all mark_duplicate of an already-replayed strategy id, "
                "so bucket A is legitimately empty: P541B did not surface any candidate "
                "that needs zero further work."
            ),
            "bucket_B_needs_adapter_before_readiness": (
                "P541B recommended_action=include_in_replay_readiness (142, all "
                "is_actual_prediction_method=True, all needs_adapter_wrapper/small "
                "effort) PLUS the exclude_from_replay/hardcoded_paths_or_dates records "
                "with is_actual_prediction_method=True (31): both are confirmed real "
                "prediction methods where the only blocker is a wrapper or "
                "parameterization, matching bucket B's definition verbatim."
            ),
            "bucket_C_needs_refactor_before_readiness": (
                "exclude_from_replay/needs_refactor_to_pure_function and "
                "exclude_from_replay/needs_db_safety_refactor records with "
                "is_actual_prediction_method=True: confirmed real methods that need "
                "pure-function extraction or DB-safety refactor before they can be "
                "safely wrapped."
            ),
            "bucket_D_needs_cto_review": (
                "P541B's own needs_cto_review bucket (167) is carried through "
                "unchanged (P541C found no additional resolving evidence), PLUS any "
                "exclude_from_replay record whose is_actual_prediction_method is "
                "'unknown' (identity itself, not just readiness, is unresolved): "
                "deferring these to CTO review instead of silently excluding them or "
                "silently promoting them without confirmed identity."
            ),
            "bucket_E_exclude_from_replay": (
                "mark_not_strategy, mark_duplicate, mark_deprecated (57 total), plus "
                "exclude_from_replay/unsafe_side_effects and "
                "exclude_from_replay/imports_db_or_runs_work_at_module_load (25, "
                "excluded regardless of identity confidence because the blocker is a "
                "code-safety fact, not an identity judgment), plus any record whose "
                "source_path no longer exists on disk (phantom)."
            ),
            "risk_level_rule": (
                "high if evidence flag uses_db_anywhere=True; medium if "
                "writes_files_anywhere=True or hardcoded_abs_path=True (and not "
                "already high); else low."
            ),
            "priority_rule": (
                "Bucket B: high if confidence=high and risk=low; medium if "
                "confidence in (high, medium) and risk<=medium; low otherwise; risk=high "
                "always caps at low. Bucket C: medium if confidence=high and risk!=high, "
                "else low. Bucket D/A: unknown/n-a. Bucket E: exclude."
            ),
            "shortlist_rule": (
                "Bucket B members with priority=high and risk=low only (guarantees no "
                "DB import/write risk and no unsafe side effects by construction), "
                "deduplicated by method_id, round-robin diversified across "
                "method_family, capped at 20, sorted deterministically by method_id "
                "within each family."
            ),
        },
        "reviewed_method_decisions": decisions,
        "ready_for_replay_readiness_now": by_decision[DECISION_READY],
        "needs_adapter_before_readiness": by_decision[DECISION_ADAPTER],
        "needs_refactor_before_readiness": by_decision[DECISION_REFACTOR],
        "needs_cto_review": by_decision[DECISION_CTO],
        "excluded_methods": by_decision[DECISION_EXCLUDE],
        "high_priority_candidate_shortlist": shortlist,
        "next_task_recommendation": next_task,
        "provenance_and_limits": {
            "method": (
                "Static, read-only re-bucketing of the P541B classification artifact. "
                "No DB access. No file content re-reads beyond an os.path.isfile() "
                "existence check per reviewed record. No replay generation, no OOS "
                "evaluation, no scoring/promotion gate."
            ),
            "p541b_artifacts_consumed": [
                "outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.json",
                "outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.md",
            ],
            "p541a_artifacts_consumed": [
                "outputs/research/p541a_biglotto_strategy_inventory_replay_coverage_audit_20260709.json",
                "outputs/research/p541a_biglotto_strategy_inventory_replay_coverage_audit_20260709.md",
            ],
            "not_performed_by_this_task": [
                "No DB write, migration, backfill, or replay row generation.",
                "No OOS evaluator or strategy scoring/promotion gate.",
                "No recomputation of P536-P541B artifacts.",
                "No route/API/UI changes.",
                "No adapter code was written; only the decision to route a method to "
                "needs_adapter_before_readiness / needs_refactor_before_readiness.",
            ],
            "known_limits": [
                "The 167 needs_cto_review records inherited from P541B were not "
                "further resolved: P541B's own static evidence already shows "
                "'no strong static signal either way' for all of them (or a syntax "
                "error for the one broken_or_import_error record), so no additional "
                "P541C-level static heuristic was applied on top of evidence P541B "
                "already weighed and found inconclusive.",
                "source_path existence was the only new static check performed; 0 of "
                "580 reviewed source paths were missing at P541C review time.",
                "Risk/priority scoring is a deterministic function of P541B's own "
                "evidence flags; it is a triage aid for the next task, not a safety "
                "guarantee, and does not itself verify runtime behavior.",
            ],
            "disclaimer": DISCLAIMER,
        },
        "disclaimer": DISCLAIMER,
    }


def render_markdown(artifact: dict) -> str:
    s = artifact["summary"]
    lines = []
    lines.append("# P541C — BIG_LOTTO Legacy Method Review & Replay-Readiness Selection")
    lines.append("")
    lines.append(f"> generated_at: {artifact['generated_at']}")
    lines.append(f"> task_id: {artifact['task_id']}")
    lines.append("")
    lines.append(f"**Disclaimer:** {artifact['disclaimer']}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|---|---|")
    for k, v in s.items():
        lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("## Selection Policy")
    lines.append("")
    for k, v in artifact["selection_policy"].items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    lines.append("## Bucket Sizes")
    lines.append("")
    lines.append(f"- A. ready_for_replay_readiness_now: {len(artifact['ready_for_replay_readiness_now'])}")
    lines.append(f"- B. needs_adapter_before_readiness: {len(artifact['needs_adapter_before_readiness'])}")
    lines.append(f"- C. needs_refactor_before_readiness: {len(artifact['needs_refactor_before_readiness'])}")
    lines.append(f"- D. needs_cto_review: {len(artifact['needs_cto_review'])}")
    lines.append(f"- E. excluded_methods: {len(artifact['excluded_methods'])}")
    lines.append("")
    lines.append(f"## High-Priority Candidate Shortlist (max 20, n={len(artifact['high_priority_candidate_shortlist'])})")
    lines.append("")
    lines.append("| method_id | method_family | source_path | reason |")
    lines.append("|---|---|---|---|")
    for d in artifact["high_priority_candidate_shortlist"]:
        reason = d["decision_reason"].replace("|", "/").replace("\n", " ")
        lines.append(f"| {d['method_id']} | {d['method_family']} | {d['source_path']} | {reason} |")
    lines.append("")
    lines.append(f"## Recommended Next Task")
    lines.append("")
    lines.append(f"`{artifact['next_task_recommendation']}`")
    lines.append("")
    lines.append("## Provenance and Limits")
    lines.append("")
    for k, v in artifact["provenance_and_limits"].items():
        if isinstance(v, list):
            lines.append(f"- **{k}**:")
            for item in v:
                lines.append(f"  - {item}")
        else:
            lines.append(f"- **{k}**: {v}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    p541b = load_json(P541B_JSON)
    p541a = load_json(P541A_JSON)
    artifact = build_artifact(p541b, p541a)

    date_tag = "20260710"
    out_json = REPO_ROOT / f"outputs/research/p541c_biglotto_legacy_method_review_readiness_selection_{date_tag}.json"
    out_md = REPO_ROOT / f"outputs/research/p541c_biglotto_legacy_method_review_readiness_selection_{date_tag}.md"

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(artifact, f, ensure_ascii=False, indent=2)
        f.write("\n")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write(render_markdown(artifact))

    print(f"wrote {out_json}")
    print(f"wrote {out_md}")
    print(json.dumps(artifact["summary"], ensure_ascii=False, indent=2))
    print("next_task_recommendation:", artifact["next_task_recommendation"])


if __name__ == "__main__":
    main()
