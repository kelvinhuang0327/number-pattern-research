"""Deterministic P545B R2 full 50/300/750 per-draw evaluator.

The committed P545C R4 compact registry is the sole row-level evidence input.
This module performs no database, network, strategy-search, or production work.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from analysis import p273a_prize_aware_inferential_validation as inference
from lottery_api.prize_aware_scorer import score_prize_aware_ticket


TASK_ID = "P545B_R2_FULL_50_300_750_PER_DRAW_EVALUATOR_FROM_COMMITTED_REGISTRY"
SCHEMA = "p545b_r2_full_per_draw_evaluator.v1"
CLASSIFICATION = "P545B_R2_RETROSPECTIVE_EVALUATION_RECONCILED_NO_BETTING_RECOMMENDATION"
REGISTRY_PATH = "outputs/research/p545c_r4_strategy_draw_opportunity_registry_20260711.json"
REGISTRY_SIZE = 52_393_107
REGISTRY_SHA256 = "ea0a712fa5ba702c51271b5664fc95e5cac2feec5967ead3bd7d01cfcd7bc5d8"
REGISTRY_SEMANTIC_DIGEST = "f2c28075a3b7020629a0c6bd41504609031ff84532a672dde4f26f0485434b39"
REGISTRY_CANONICAL_DIGEST = "34bbee9b9a3cd275025db282486f8bdd3dd5c14834813061acefce220ae0ed84"
REGISTRY_SCHEMA = "p545c_r4_strategy_draw_opportunity_registry.compact.v1"
WINDOW_BITS = {50: 1, 300: 2, 750: 4}
WINDOW_LABELS = {50: "SHORT", 300: "MID", 750: "LONG"}
OUTPUT_JSON = Path("outputs/research/p545b_r2_full_per_draw_evaluator_20260711.json")
OUTPUT_MD = Path("outputs/research/p545b_r2_full_per_draw_evaluator_20260711.md")


class EvaluationError(RuntimeError):
    """Fail-closed integrity, evaluation, or reconciliation error."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def canonical_payload_digest(payload: Mapping[str, Any]) -> str:
    candidate = dict(payload)
    candidate.pop("canonical_payload_digest", None)
    return digest(candidate)


def _outcome_projection(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "outcome_id": record["outcome_id"],
        "lottery_type": record["lottery_type"],
        "target_draw": record["target_draw"],
        "raw_date": record["raw_date"],
        "canonical_date": record["canonical_date"],
        "main_numbers": record["main_numbers"],
        "auxiliary": record["auxiliary"],
        "source_row_id": record["source_row_id"],
        "outcome_sha256": record["outcome_sha256"],
    }


def semantic_projection(registry: Mapping[str, Any]) -> dict[str, Any]:
    """Independently reproduce the P545C layout-neutral semantic projection."""
    cells = [{
        "cell_id": cell["cell_id"],
        "lottery_type": cell["lottery_type"],
        "strategy_id": cell["strategy_id"],
        "expected_bet_indices": cell["expected_bet_indices"],
    } for cell in registry["cells"]]
    outcomes = [_outcome_projection(record) for record in registry["official_outcomes"]]
    outcomes_by_id = {record["outcome_id"]: record for record in outcomes}
    provenance = {item["provenance_id"]: item["value"] for item in registry["provenance_records"]}
    attempts = []
    for attempt in registry["attempts"]:
        opportunity_id = attempt["opportunity_id"]
        outcome_id = opportunity_id.split(":", 1)[0] + ":" + opportunity_id.rsplit(":", 1)[1]
        outcome = outcomes_by_id[outcome_id]
        attempts.append({
            "attempt_id": attempt["attempt_id"], "opportunity_id": opportunity_id,
            "source_row_id": attempt["source_row_id"], "bet_index": attempt["bet_index"],
            "predicted_main_numbers": attempt["predicted_main_numbers"],
            "predicted_auxiliary": attempt["predicted_auxiliary"],
            "actual_main_numbers": outcome["main_numbers"],
            "actual_auxiliary": None if outcome["lottery_type"] == "DAILY_539" else outcome["auxiliary"],
            "history_cutoff_draw": attempt["history_cutoff_draw"],
            "replay_status": attempt["replay_status"], "dry_run": attempt["dry_run"],
            "draw_join_count": attempt["draw_join_count"], "eligible": attempt["eligible"],
            "exclusion_reason": attempt["exclusion_reason"], "ticket_identity": attempt["ticket_identity"],
            "score": attempt["score"], "provenance": provenance[attempt["provenance_ref"]],
            "attempt_sha256": attempt["attempt_sha256"],
        })
    opportunities = [{
        "opportunity_id": record["opportunity_id"], "cell_id": record["cell_id"],
        "outcome_id": record["outcome_id"], "target_draw": record["target_draw"],
        "window_membership": [label for bit, label in ((1, "SHORT"), (2, "MID"), (4, "LONG")) if record["window_mask"] & bit],
        "gross_attempt_count": record["gross_attempt_count"],
        "eligible_attempt_count": record["eligible_attempt_count"],
        "excluded_attempt_count": record["excluded_attempt_count"], "supported": record["supported"],
        "all_attempts_excluded": record["all_attempts_excluded"],
        "exclusion_by_reason": record["exclusion_by_reason"],
        "observed_bet_indices": record["observed_bet_indices"],
        "missing_expected_bet_indices": record["missing_expected_bet_indices"],
        "unexpected_bet_indices": record["unexpected_bet_indices"],
        "same_key_duplicate_count": record["same_key_duplicate_count"],
        "identical_content_collapse_count": record["identical_content_collapse_count"],
        "cross_index_duplicate_ticket_count": record["cross_index_duplicate_ticket_count"],
        "same_index_conflict_count": record["same_index_conflict_count"],
        "opportunity_sha256": record["opportunity_sha256"],
    } for record in registry["opportunities"]]
    windows = []
    for record in registry["window_reconciliation"]:
        windows.append({
            "lottery_type": record["lottery_type"], "strategy_id": record["strategy_id"],
            "window": record["window"], "window_label": record["window_label"],
            "latest_target_draw": record["latest_target_draw"],
            "earliest_target_draw": record["earliest_target_draw"],
            "draw_set_sha256": record["draw_set_sha256"], "gross_attempts": record["gross_attempts"],
            "eligible_attempts": record["eligible_attempts"], "excluded_attempts": record["excluded_attempts"],
            "support_draws": record["support_draws"], "observed_successes": record["observed_successes"],
            "exclusion_by_reason": record["exclusion_by_reason"],
            "distinct_ticket_count_distribution": record["distinct_ticket_count_distribution"],
            "duplicate_content_draw_count": record["duplicate_content_draw_count"],
            "inference": record["inference"], "inferential_record_sha256": record["inferential_record_sha256"],
        })
    return {
        "cells": sorted(cells, key=lambda item: item["cell_id"]),
        "official_outcomes": sorted(outcomes, key=lambda item: item["outcome_id"]),
        "attempts": sorted(attempts, key=lambda item: item["attempt_id"]),
        "opportunities": sorted(opportunities, key=lambda item: item["opportunity_id"]),
        "window_reconciliation": sorted(windows, key=lambda item: (item["lottery_type"], item["strategy_id"], item["window"])),
        "global_summary": registry["global_summary"],
        "snapshot_sha256": registry["snapshot_source"]["sha256"],
        "frozen_contract_commit": registry["frozen_contract_commit"],
        "canonical_database_opened": registry["safety"]["canonical_database_opened"],
    }


def load_registry(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    path = repo_root / REGISTRY_PATH
    size = path.stat().st_size
    raw_sha = file_sha256(path)
    if size != REGISTRY_SIZE or raw_sha != REGISTRY_SHA256:
        raise EvaluationError(f"registry raw identity mismatch: size={size}, sha256={raw_sha}")
    registry = json.loads(path.read_text(encoding="utf-8"))
    canonical = canonical_payload_digest(registry)
    semantic = digest(semantic_projection(registry))
    if registry.get("schema") != REGISTRY_SCHEMA:
        raise EvaluationError("registry schema mismatch")
    if canonical != REGISTRY_CANONICAL_DIGEST or registry.get("canonical_payload_digest") != canonical:
        raise EvaluationError(f"registry canonical payload digest mismatch: {canonical}")
    if semantic != REGISTRY_SEMANTIC_DIGEST:
        raise EvaluationError(f"registry semantic projection digest mismatch: {semantic}")
    if registry["semantic_equivalence"].get("compact_semantic_projection_digest") != semantic:
        raise EvaluationError("registry embedded semantic projection digest mismatch")
    return registry, {"path": REGISTRY_PATH, "byte_size": size, "sha256": raw_sha,
                      "semantic_projection_digest": semantic, "canonical_payload_digest": canonical}


def _score(lottery: str, attempt: Mapping[str, Any], outcome: Mapping[str, Any]) -> dict[str, Any]:
    kwargs = {"lottery_type": lottery, "predicted_main_numbers": attempt["predicted_main_numbers"],
              "actual_main_numbers": outcome["main_numbers"]}
    if lottery == "POWER_LOTTO":
        kwargs.update(predicted_second_zone=attempt["predicted_auxiliary"], actual_second_zone=outcome["auxiliary"])
    elif lottery == "BIG_LOTTO":
        kwargs.update(actual_special_number=outcome["auxiliary"])
    result = score_prize_aware_ticket(**kwargs)
    return {key: result[key] for key in ("main_hit_count", "special_hit", "prize_tier", "any_prize_aware_win")}


def evaluate_opportunities(registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    outcomes = {item["outcome_id"]: item for item in registry["official_outcomes"]}
    attempts = registry["attempts"]
    results = []
    for opportunity in registry["opportunities"]:
        start, count = opportunity["attempt_start"], opportunity["attempt_count"]
        selected = attempts[start:start + count]
        if len(selected) != count or any(a["opportunity_id"] != opportunity["opportunity_id"] for a in selected):
            raise EvaluationError(f"attempt slice mismatch: {opportunity['opportunity_id']}")
        outcome = outcomes[opportunity["outcome_id"]]
        lottery = opportunity["cell_id"].split(":", 1)[0]
        eligible_scores, identities, exclusions = [], [], Counter()
        for attempt in selected:
            if attempt["eligible"]:
                derived = _score(lottery, attempt, outcome)
                if derived != attempt["score"]:
                    raise EvaluationError(f"score mismatch: {attempt['attempt_id']}")
                identity = attempt["ticket_identity"]
                if digest(identity["canonical_ticket_content"]) != identity["fingerprint_sha256"]:
                    raise EvaluationError(f"ticket identity mismatch: {attempt['attempt_id']}")
                eligible_scores.append(derived)
                identities.append(canonical_bytes(identity["canonical_ticket_content"]))
            else:
                if attempt["score"] is not None or attempt["ticket_identity"] is not None:
                    raise EvaluationError(f"excluded attempt carries evaluation: {attempt['attempt_id']}")
                exclusions[attempt["exclusion_reason"]] += 1
        distinct = len(set(identities))
        derived = {
            "opportunity_id": opportunity["opportunity_id"], "cell_id": opportunity["cell_id"],
            "target_draw": opportunity["target_draw"], "window_mask": opportunity["window_mask"],
            "gross_attempts": len(selected), "eligible_attempts": len(eligible_scores),
            "excluded_attempts": len(selected) - len(eligible_scores), "supported": bool(eligible_scores),
            "distinct_ticket_count": distinct, "duplicate_ticket_count": len(identities) - distinct,
            "observed_success": any(score["any_prize_aware_win"] for score in eligible_scores),
            "exclusion_by_reason": dict(sorted(exclusions.items())),
        }
        expected = {
            "gross_attempts": opportunity["gross_attempt_count"],
            "eligible_attempts": opportunity["eligible_attempt_count"],
            "excluded_attempts": opportunity["excluded_attempt_count"], "supported": opportunity["supported"],
            "duplicate_ticket_count": opportunity["cross_index_duplicate_ticket_count"],
            "exclusion_by_reason": opportunity["exclusion_by_reason"],
        }
        for field, value in expected.items():
            if derived[field] != value:
                raise EvaluationError(f"opportunity {field} mismatch: {opportunity['opportunity_id']}")
        derived["evaluation_sha256"] = digest(derived)
        results.append(derived)
    return results


def _compare_window(derived: Mapping[str, Any], committed: Mapping[str, Any]) -> list[str]:
    mismatches = []
    direct = ("gross_attempts", "eligible_attempts", "excluded_attempts", "support_draws",
              "observed_successes", "exclusion_by_reason", "distinct_ticket_count_distribution")
    for field in direct:
        if derived[field] != committed[field]:
            mismatches.append(field)
    values = committed["inference"]["values"]
    for field, expected in values.items():
        if derived.get(field) != expected:
            mismatches.append(f"inference.{field}")
    if derived["evaluable"] != committed["inference"]["evaluable"]:
        mismatches.append("inference.evaluable")
    if derived["support_status"] != committed["inference"]["support_status"]:
        mismatches.append("inference.support_status")
    return mismatches


def evaluate_windows(registry: Mapping[str, Any], opportunities: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cells = {item["cell_id"]: item for item in registry["cells"]}
    committed = {(item["lottery_type"], item["strategy_id"], item["window"]): item
                 for item in registry["window_reconciliation"]}
    by_cell: dict[str, list[Mapping[str, Any]]] = {cell_id: [] for cell_id in cells}
    for item in opportunities:
        by_cell[item["cell_id"]].append(item)
    groups, all_windows, raw_p_locations = [], [], []
    for cell_id in sorted(cells):
        cell = cells[cell_id]
        lottery, strategy = cell["lottery_type"], cell["strategy_id"]
        by_label = {}
        for window in (50, 300, 750):
            selected = [item for item in by_cell[cell_id] if item["window_mask"] & WINDOW_BITS[window]]
            supported = [item for item in selected if item["supported"]]
            anchor = next(item for item in cell["window_anchors"] if item["window"] == window)
            if len(selected) != window or digest([item["target_draw"] for item in selected]) != anchor["draw_set_sha256"]:
                raise EvaluationError(f"draw membership mismatch: {cell_id}/w{window}")
            exclusions = dict(sorted(sum((Counter(item["exclusion_by_reason"]) for item in selected), Counter()).items()))
            window_record = {
                "lottery_type": lottery, "strategy_id": strategy, "window": window,
                "window_label": WINDOW_LABELS[window], "support_draws": len(supported),
                "observed_successes": sum(item["observed_success"] for item in supported),
                "bet_count_distribution": dict(sorted(Counter(str(item["eligible_attempts"]) for item in supported).items())),
            }
            identity_draws = [{"target_draw": item["target_draw"], "distinct_ticket_count": item["distinct_ticket_count"]}
                              for item in supported]
            evaluated = inference.evaluate_window(lottery, strategy, window_record, identity_draws)
            evaluated.update({
                "gross_attempts": sum(item["gross_attempts"] for item in selected),
                "eligible_attempts": sum(item["eligible_attempts"] for item in selected),
                "excluded_attempts": sum(item["excluded_attempts"] for item in selected),
                "exclusion_by_reason": exclusions,
            })
            by_label[WINDOW_LABELS[window]] = evaluated
        stability = inference.evaluate_stability(by_label)
        for label, item in by_label.items():
            item["window_decision"] = inference.finalize_window_decision(label, item, stability)
        provisional = inference._provisional_windows(by_label)
        provisional_stability = inference.evaluate_stability(provisional)
        for label, item in by_label.items():
            item["rejected_independent_approximation"]["window_decision"] = provisional[label]["window_decision"]
        group = {"lottery_type": lottery, "strategy_id": strategy,
                 "windows": [by_label[label] for label in inference.WINDOW_ORDER], "stability": stability,
                 "overall_group_decision": inference.overall_group_decision(by_label, stability),
                 "rejected_provisional_independent_null": {
                     "stability": provisional_stability,
                     "overall_group_decision": inference.overall_group_decision(provisional, provisional_stability),
                 }}
        groups.append(group)
        for item in group["windows"]:
            all_windows.append(item)
            if item["evaluable"]:
                raw_p_locations.append(item)
    flags = inference.benjamini_hochberg([item["raw_p_value_one_sided_upper"] for item in raw_p_locations])
    for item, flag in zip(raw_p_locations, flags):
        item["bh_fdr_descriptive_reject"] = bool(flag)
    for item in all_windows:
        item.setdefault("bh_fdr_descriptive_reject", None)
        mismatch = _compare_window(item, committed[(item["lottery_type"], item["strategy_id"], item["window"])])
        if mismatch:
            raise EvaluationError(f"window reconciliation mismatch {item['lottery_type']}/{item['strategy_id']}/w{item['window']}: {mismatch}")
        item["reconciliation"] = "PASS"
        item["evaluation_sha256"] = digest(item)
    summary = {
        "window_decision_counts": dict(sorted(Counter(item["window_decision"] for item in all_windows).items())),
        "stability_counts": dict(sorted(Counter(group["stability"]["status"] for group in groups).items())),
        "group_decision_counts": dict(sorted(Counter(group["overall_group_decision"] for group in groups).items())),
        "go_candidate_research_only_groups": [{"lottery_type": group["lottery_type"], "strategy_id": group["strategy_id"]}
                                               for group in groups if group["overall_group_decision"] == "GO_CANDIDATE_RESEARCH_ONLY"],
        "correction_surviving_edge_found": any(item["window_decision"] == "PRIZE_AWARE_EDGE_CORRECTION_SURVIVING" for item in all_windows),
        "preliminary_independent_null_candidates": sum(group["rejected_provisional_independent_null"]["overall_group_decision"] == "GO_CANDIDATE_RESEARCH_ONLY" for group in groups),
    }
    if summary != registry["reconciliation"]["inference_summary"]:
        raise EvaluationError("committed inference summary reconciliation mismatch")
    return all_windows, groups, summary


def build_evaluation(repo_root: Path) -> dict[str, Any]:
    registry, identity = load_registry(repo_root)
    opportunities = evaluate_opportunities(registry)
    windows, groups, summary = evaluate_windows(registry, opportunities)
    project = inference.overall_project_classification(groups)
    if project != registry["reconciliation"]["overall_project_classification_reproduced"]:
        raise EvaluationError("overall project classification reconciliation mismatch")
    payload = {
        "schema": SCHEMA, "task_id": TASK_ID, "classification": CLASSIFICATION,
        "generated_at_utc": registry["generated_at_utc"],
        "sole_row_level_evidence_input": identity,
        "contracts": {
            "scoring": "P544C amended prize-aware special-hit contract via committed pure scorer",
            "statistics": "P273A exact distinct-ticket null and P544C verification contract",
            "primary_windows": [50, 300, 750], "family_size": 108,
            "family_alpha": inference.FAMILY_ALPHA, "bh_fdr_q_descriptive_only": inference.BH_FDR_Q,
            "minimum_support_draws": inference.MIN_SUPPORT_DRAWS,
            "minimum_expected_successes": inference.MIN_EXPECTED_SUCCESSES,
        },
        "scope": {"frozen_cells": len(registry["cells"]), "opportunities": len(opportunities),
                  "windows": len(windows), "sqlite_opened": False, "strategy_search_performed": False,
                  "betting_recommendation_produced": False},
        "per_opportunity_evaluations": opportunities,
        "per_window_evaluations": windows,
        "group_evaluations": groups,
        "reconciliation": {"windows_passed": len(windows), "windows_failed": 0,
                           "committed_summary_match": True, "inference_summary": summary,
                           "committed_retrospective_project_classification": project},
        "limitations": ["Retrospective research evidence only.",
                        "Committed research labels are reconciled, not converted into betting advice.",
                        "No predictive-validity, ROI, EV, production-readiness, or deployment claim."],
    }
    payload["canonical_payload_digest"] = canonical_payload_digest(payload)
    return payload


def render_markdown(payload: Mapping[str, Any]) -> str:
    rec, source = payload["reconciliation"], payload["sole_row_level_evidence_input"]
    return "\n".join([
        "# P545B R2 — Full 50/300/750 Per-Draw Evaluator", "",
        "> Retrospective research reconciliation only. This is not a betting recommendation or future-performance claim.", "",
        "## Result", "", f"- Frozen cells: **{payload['scope']['frozen_cells']}**",
        f"- Independently evaluated opportunities: **{payload['scope']['opportunities']:,}**",
        f"- Reconciled windows: **{rec['windows_passed']}/108 PASS**",
        f"- Committed retrospective classification reproduced: `{rec['committed_retrospective_project_classification']}`",
        f"- Output classification: `{payload['classification']}`", "", "## Sole row-level evidence input", "",
        f"- Path: `{source['path']}`", f"- Bytes: **{source['byte_size']:,}**", f"- SHA-256: `{source['sha256']}`",
        f"- Semantic projection digest: `{source['semantic_projection_digest']}`",
        f"- Canonical payload digest: `{source['canonical_payload_digest']}`", "", "## Statistical contract", "",
        "- Primary windows: `50 / 300 / 750`; fixed Bonferroni family `m=108`.",
        "- Exact distinct-ticket without-replacement null; exact binomial or Poisson-binomial tails.",
        "- Wilson and Clopper-Pearson 95% intervals; BH-FDR remains descriptive only.",
        "- P544C amended BIG_LOTTO special-hit scoring is recomputed per eligible attempt.", "", "## Safety and limitations", "",
        "- SQLite opened: **NO**", "- Strategy combination or parameter search: **NO**",
        "- Betting recommendation, ROI, or EV output: **NO**", "- Upstream artifacts modified: **NO**", "",
        f"Canonical payload digest: `{payload['canonical_payload_digest']}`", "",
    ])


def generate(repo_root: Path, output_json: Path = OUTPUT_JSON, output_md: Path = OUTPUT_MD) -> tuple[Path, Path]:
    payload = build_evaluation(repo_root)
    json_path, md_path = repo_root / output_json, repo_root / output_md
    json_path.write_bytes(canonical_bytes(payload) + b"\n")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    generate(args.repo_root.resolve())


if __name__ == "__main__":
    main()
