#!/usr/bin/env python3
"""Build the P224-A PIT feature contract and leakage audit from committed artifacts only."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "report"
SOURCE_P223_JSON = REPORT_DIR / "p223a_historical_evaluation_evidence_index.json"
SOURCE_P223_HTML = REPORT_DIR / "p223a_historical_evaluation_evidence_index.html"
SOURCE_P218_CSV = REPORT_DIR / "p218a_historical_sample_feature_table.csv"
SOURCE_P218_JSON = REPORT_DIR / "p218a_historical_sample_feature_table.json"
SOURCE_P218_MD = REPORT_DIR / "p218a_historical_sample_feature_table.md"
SOURCE_P221_CSV = REPORT_DIR / "p221a_historical_time_split_baseline_evaluation.csv"
SOURCE_P221_JSON = REPORT_DIR / "p221a_historical_time_split_baseline_evaluation.json"
SOURCE_P221_MD = REPORT_DIR / "p221a_historical_time_split_baseline_evaluation.md"
OUT_JSON = REPORT_DIR / "p224a_pit_feature_contract_leakage_audit.json"
OUT_MD = REPORT_DIR / "p224a_pit_feature_contract_leakage_audit.md"

TASK_NAME = "P224-A PIT Feature Contract + Baseline Derivation Window Leakage Audit"
STATUS = "PASS_P223A_ARTIFACT_ONLY_PIT_FEATURE_CONTRACT_AND_DERIVATION_WINDOW_LEAKAGE_AUDIT"
DISCLAIMER = "Historical PIT contract and leakage audit only. Not live predictions, not betting advice."
SUCCESS_BANNER = "P224-A PIT FEATURE CONTRACT AND LEAKAGE AUDIT PASS"
FAILURE_BANNER = "P224-A PIT FEATURE CONTRACT AND LEAKAGE AUDIT FAIL"
TARGET_COLUMN = "event_category"
BASELINE_A_KEY = "baseline_a_global_majority"
BASELINE_B_KEY = "baseline_b_pitch_type_majority_with_global_fallback"

SOURCE_ARTIFACTS = [
    SOURCE_P223_JSON,
    SOURCE_P223_HTML,
    SOURCE_P218_CSV,
    SOURCE_P218_JSON,
    SOURCE_P218_MD,
    SOURCE_P221_CSV,
    SOURCE_P221_JSON,
    SOURCE_P221_MD,
]
P223_HASH_REQUIRED_ARTIFACTS = [
    SOURCE_P218_CSV,
    SOURCE_P218_JSON,
    SOURCE_P218_MD,
    SOURCE_P221_CSV,
    SOURCE_P221_JSON,
    SOURCE_P221_MD,
]
P218_REQUIRED_COLUMNS = [
    "source_row_id",
    "game_date",
    "game_pk",
    "home_team",
    "away_team",
    "inning",
    "inning_topbot",
    "pitcher",
    "batter",
    "pitch_type",
    "event_category",
    "is_in_play",
    "is_strike_like",
    "is_ball_like",
    "release_speed",
    "release_speed_bucket",
    "zone",
    "zone_bucket",
]
P221_REQUIRED_COLUMNS = [
    "split_id",
    "train_date_range",
    "eval_date",
    "source_row_id",
    "pitch_type",
    "actual_event_category",
    "baseline_a_prediction",
    "baseline_a_correct",
    "baseline_b_prediction",
    "baseline_b_correct",
    "baseline_b_prediction_source",
]
PROHIBITED_CLAIMS = [
    "No future prediction claim.",
    "No live prediction claim.",
    "No betting advice claim.",
    "No production readiness claim.",
    "No edge, ROI, EV, Kelly, or CLV claim.",
]

PIT_CONTRACT_RULES: dict[str, dict[str, Any]] = {
    "source_row_id": {
        "pit_category": "identifier_or_lineage",
        "allowed_use": {
            "pregame_model_feature_allowed": False,
            "in_game_analysis_allowed": False,
            "label_or_outcome_only": False,
            "audit_only": True,
        },
        "leakage_risk_level": "low",
        "required_guardrail": "Keep for lineage and row reconciliation only; never feed it to a model or scoring rule.",
        "rationale_suffix": "It is a deterministic row identifier, not baseball context.",
    },
    "game_date": {
        "pit_category": "pregame_known",
        "allowed_use": {
            "pregame_model_feature_allowed": True,
            "in_game_analysis_allowed": True,
            "label_or_outcome_only": False,
            "audit_only": False,
        },
        "leakage_risk_level": "low",
        "required_guardrail": "If used in modeling, restrict to PIT-safe calendar transforms and avoid raw memorization keys.",
        "rationale_suffix": "The scheduled game date is known before first pitch.",
    },
    "game_pk": {
        "pit_category": "identifier_or_lineage",
        "allowed_use": {
            "pregame_model_feature_allowed": False,
            "in_game_analysis_allowed": False,
            "label_or_outcome_only": False,
            "audit_only": True,
        },
        "leakage_risk_level": "low",
        "required_guardrail": "Treat as lineage only; never use a game identifier as a predictive feature.",
        "rationale_suffix": "It identifies the historical game instance rather than pregame state.",
    },
    "home_team": {
        "pit_category": "pregame_known",
        "allowed_use": {
            "pregame_model_feature_allowed": True,
            "in_game_analysis_allowed": True,
            "label_or_outcome_only": False,
            "audit_only": False,
        },
        "leakage_risk_level": "low",
        "required_guardrail": "Use only as PIT-known team context and avoid target-encoding against the same evaluation rows.",
        "rationale_suffix": "Home team assignment is fixed before the game starts.",
    },
    "away_team": {
        "pit_category": "pregame_known",
        "allowed_use": {
            "pregame_model_feature_allowed": True,
            "in_game_analysis_allowed": True,
            "label_or_outcome_only": False,
            "audit_only": False,
        },
        "leakage_risk_level": "low",
        "required_guardrail": "Use only as PIT-known team context and avoid target-encoding against the same evaluation rows.",
        "rationale_suffix": "Away team assignment is fixed before the game starts.",
    },
    "inning": {
        "pit_category": "in_play_measured",
        "allowed_use": {
            "pregame_model_feature_allowed": False,
            "in_game_analysis_allowed": True,
            "label_or_outcome_only": False,
            "audit_only": False,
        },
        "leakage_risk_level": "low",
        "required_guardrail": "Allow only for in-game analysis products; exclude from pregame feature sets.",
        "rationale_suffix": "The inning number is only known once live game state progresses.",
    },
    "inning_topbot": {
        "pit_category": "in_play_measured",
        "allowed_use": {
            "pregame_model_feature_allowed": False,
            "in_game_analysis_allowed": True,
            "label_or_outcome_only": False,
            "audit_only": False,
        },
        "leakage_risk_level": "low",
        "required_guardrail": "Allow only for in-game analysis products; exclude from pregame feature sets.",
        "rationale_suffix": "Half-inning state is determined during live play.",
    },
    "pitcher": {
        "pit_category": "in_play_measured",
        "allowed_use": {
            "pregame_model_feature_allowed": False,
            "in_game_analysis_allowed": True,
            "label_or_outcome_only": False,
            "audit_only": False,
        },
        "leakage_risk_level": "medium",
        "required_guardrail": "Do not reuse the realized event-row pitcher as a pregame feature without a separate PIT starter or roster contract.",
        "rationale_suffix": "This artifact records the pitcher who actually threw the sampled pitch, which may depend on realized game usage.",
    },
    "batter": {
        "pit_category": "in_play_measured",
        "allowed_use": {
            "pregame_model_feature_allowed": False,
            "in_game_analysis_allowed": True,
            "label_or_outcome_only": False,
            "audit_only": False,
        },
        "leakage_risk_level": "medium",
        "required_guardrail": "Do not reuse the realized plate-appearance batter as a pregame feature without a separate PIT lineup contract.",
        "rationale_suffix": "This artifact records the batter who actually appeared in the sampled pitch event.",
    },
    "pitch_type": {
        "pit_category": "in_play_measured",
        "allowed_use": {
            "pregame_model_feature_allowed": False,
            "in_game_analysis_allowed": True,
            "label_or_outcome_only": False,
            "audit_only": False,
        },
        "leakage_risk_level": "medium",
        "required_guardrail": "Never expose realized pitch selection to a pregame model; reserve it for post-release audit or in-game analysis.",
        "rationale_suffix": "Pitch type is observed only after the pitch is thrown.",
    },
    "event_category": {
        "pit_category": "outcome_derived",
        "allowed_use": {
            "pregame_model_feature_allowed": False,
            "in_game_analysis_allowed": False,
            "label_or_outcome_only": True,
            "audit_only": False,
        },
        "leakage_risk_level": "high",
        "required_guardrail": "Use strictly as the label or evaluation outcome; never feed it back as an input feature.",
        "rationale_suffix": "It is the derived target outcome for the pitch event.",
    },
    "is_in_play": {
        "pit_category": "outcome_derived",
        "allowed_use": {
            "pregame_model_feature_allowed": False,
            "in_game_analysis_allowed": False,
            "label_or_outcome_only": True,
            "audit_only": False,
        },
        "leakage_risk_level": "high",
        "required_guardrail": "Treat as an outcome-only flag derived from realized play; do not allow it into pregame or causal feature sets.",
        "rationale_suffix": "The flag is derived from whether the pitch event resolved into ball-in-play behavior.",
    },
    "is_strike_like": {
        "pit_category": "outcome_derived",
        "allowed_use": {
            "pregame_model_feature_allowed": False,
            "in_game_analysis_allowed": False,
            "label_or_outcome_only": True,
            "audit_only": False,
        },
        "leakage_risk_level": "high",
        "required_guardrail": "Treat as an outcome-only flag derived from realized pitch result; never reuse as an input feature.",
        "rationale_suffix": "The flag is derived from realized strike-like descriptions or strikeout events.",
    },
    "is_ball_like": {
        "pit_category": "outcome_derived",
        "allowed_use": {
            "pregame_model_feature_allowed": False,
            "in_game_analysis_allowed": False,
            "label_or_outcome_only": True,
            "audit_only": False,
        },
        "leakage_risk_level": "high",
        "required_guardrail": "Treat as an outcome-only flag derived from realized pitch result; never reuse as an input feature.",
        "rationale_suffix": "The flag is derived from realized ball-like descriptions or walk outcomes.",
    },
    "release_speed": {
        "pit_category": "in_play_measured",
        "allowed_use": {
            "pregame_model_feature_allowed": False,
            "in_game_analysis_allowed": True,
            "label_or_outcome_only": False,
            "audit_only": False,
        },
        "leakage_risk_level": "medium",
        "required_guardrail": "Keep as realized pitch telemetry only; exclude from any pregame contract.",
        "rationale_suffix": "Release speed is measured only when the pitch is thrown.",
    },
    "release_speed_bucket": {
        "pit_category": "in_play_measured",
        "allowed_use": {
            "pregame_model_feature_allowed": False,
            "in_game_analysis_allowed": True,
            "label_or_outcome_only": False,
            "audit_only": False,
        },
        "leakage_risk_level": "medium",
        "required_guardrail": "Keep as realized pitch telemetry only; exclude from any pregame contract.",
        "rationale_suffix": "The bucket is derived from realized release speed after the pitch occurs.",
    },
    "zone": {
        "pit_category": "in_play_measured",
        "allowed_use": {
            "pregame_model_feature_allowed": False,
            "in_game_analysis_allowed": True,
            "label_or_outcome_only": False,
            "audit_only": False,
        },
        "leakage_risk_level": "medium",
        "required_guardrail": "Treat as post-release pitch-location telemetry only; exclude from pregame feature contracts.",
        "rationale_suffix": "Pitch zone is observed from the realized pitch location.",
    },
    "zone_bucket": {
        "pit_category": "in_play_measured",
        "allowed_use": {
            "pregame_model_feature_allowed": False,
            "in_game_analysis_allowed": True,
            "label_or_outcome_only": False,
            "audit_only": False,
        },
        "leakage_risk_level": "medium",
        "required_guardrail": "Treat as post-release pitch-location telemetry only; exclude from pregame feature contracts.",
        "rationale_suffix": "The bucket is derived from realized pitch location after the pitch occurs.",
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_label(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _fail_insufficient(message: str) -> ValueError:
    return ValueError(f"P224A_STOPPED_INSUFFICIENT_EVIDENCE: {message}")


def _normalize_cell(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _parse_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def _parse_int(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _fraction(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 6)


def _md_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _load_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str | None]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [
            {column: _normalize_cell(value) for column, value in row.items()}
            for row in reader
        ]
    return fieldnames, rows


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sorted_counts(values: list[str]) -> list[tuple[str, int]]:
    return sorted(Counter(values).items(), key=lambda item: (-item[1], item[0]))


def _distribution(values: list[str]) -> list[dict[str, Any]]:
    ranked = _sorted_counts(values)
    total = len(values)
    return [
        {
            "value": label,
            "count": count,
            "fraction": _fraction(count, total),
        }
        for label, count in ranked
    ]


def _require_keys(payload: dict[str, Any], required_keys: list[str], payload_name: str) -> None:
    missing = [key for key in required_keys if key not in payload]
    if missing:
        raise _fail_insufficient(f"{payload_name} missing keys: {', '.join(missing)}")


def _require_columns(fieldnames: list[str], required_columns: list[str], label: str) -> None:
    missing = [column for column in required_columns if column not in fieldnames]
    if missing:
        raise _fail_insufficient(f"{label} missing columns: {', '.join(missing)}")


def _date_range_label(dates: list[str]) -> str:
    if not dates:
        return ""
    return f"{dates[0]} to {dates[-1]}"


def _majority_label(values: list[str]) -> str:
    ranked = _sorted_counts(values)
    if not ranked:
        raise _fail_insufficient("training rows are empty for majority-label derivation")
    return ranked[0][0]


def _pitch_type_resolution_table(
    train_rows: list[dict[str, str | None]],
    global_majority: str,
) -> list[dict[str, Any]]:
    grouped_targets: dict[str, list[str]] = defaultdict(list)
    for row in train_rows:
        grouped_targets[row.get("pitch_type") or "missing"].append(row[TARGET_COLUMN] or "missing")

    table: list[dict[str, Any]] = []
    for pitch_type in sorted(grouped_targets):
        values = grouped_targets[pitch_type]
        ranked = _sorted_counts(values)
        top_count = ranked[0][1]
        top_labels = [label for label, count in ranked if count == top_count]
        uses_fallback = len(top_labels) != 1
        table.append(
            {
                "pitch_type": pitch_type,
                "support": len(values),
                "event_category_distribution": [
                    {"value": label, "count": count, "fraction": _fraction(count, len(values))}
                    for label, count in ranked
                ],
                "resolved_prediction": global_majority if uses_fallback else ranked[0][0],
                "prediction_source": "global_fallback_due_to_tie" if uses_fallback else "pitch_type_majority",
                "fallback_to_global_majority": uses_fallback,
            }
        )
    return table


def _resolve_baseline_b_prediction(
    pitch_type: str,
    pitch_type_table: dict[str, dict[str, Any]],
    global_majority: str,
) -> tuple[str, str]:
    resolution = pitch_type_table.get(pitch_type)
    if resolution is None:
        return global_majority, "global_fallback_missing_pitch_type"
    return resolution["resolved_prediction"], resolution["prediction_source"]


def _baseline_metrics(records: list[dict[str, Any]], prediction_key: str, correct_key: str) -> dict[str, Any]:
    row_count = len(records)
    correct_count = sum(1 for record in records if record[correct_key])
    return {
        "row_count": row_count,
        "correct_count": correct_count,
        "accuracy": _fraction(correct_count, row_count),
        "coverage_rows": row_count,
        "coverage_fraction": _fraction(row_count, row_count),
    }


def _baseline_b_coverage(records: list[dict[str, Any]]) -> dict[str, Any]:
    direct_rows = [
        record for record in records if record["baseline_b_prediction_source"] == "pitch_type_majority"
    ]
    tie_fallback_rows = [
        record for record in records if record["baseline_b_prediction_source"] == "global_fallback_due_to_tie"
    ]
    missing_pitch_type_rows = [
        record
        for record in records
        if record["baseline_b_prediction_source"] == "global_fallback_missing_pitch_type"
    ]
    fallback_rows = tie_fallback_rows + missing_pitch_type_rows
    total_rows = len(records)
    return {
        "direct_pitch_type_majority": {
            "rows": len(direct_rows),
            "fraction": _fraction(len(direct_rows), total_rows),
            "correct_rows": sum(1 for record in direct_rows if record["baseline_b_correct"]),
            "accuracy": _fraction(
                sum(1 for record in direct_rows if record["baseline_b_correct"]),
                len(direct_rows),
            ),
        },
        "global_fallback_due_to_tie": {
            "rows": len(tie_fallback_rows),
            "fraction": _fraction(len(tie_fallback_rows), total_rows),
            "correct_rows": sum(1 for record in tie_fallback_rows if record["baseline_b_correct"]),
            "accuracy": _fraction(
                sum(1 for record in tie_fallback_rows if record["baseline_b_correct"]),
                len(tie_fallback_rows),
            ),
        },
        "global_fallback_missing_pitch_type": {
            "rows": len(missing_pitch_type_rows),
            "fraction": _fraction(len(missing_pitch_type_rows), total_rows),
            "correct_rows": sum(1 for record in missing_pitch_type_rows if record["baseline_b_correct"]),
            "accuracy": _fraction(
                sum(1 for record in missing_pitch_type_rows if record["baseline_b_correct"]),
                len(missing_pitch_type_rows),
            ),
        },
        "all_global_fallback": {
            "rows": len(fallback_rows),
            "fraction": _fraction(len(fallback_rows), total_rows),
            "correct_rows": sum(1 for record in fallback_rows if record["baseline_b_correct"]),
            "accuracy": _fraction(
                sum(1 for record in fallback_rows if record["baseline_b_correct"]),
                len(fallback_rows),
            ),
        },
    }


def _metric_delta_row(
    scope: str,
    split_id: int | None,
    eval_date: str,
    baseline_name: str,
    committed: dict[str, Any],
    recomputed: dict[str, Any],
) -> dict[str, Any]:
    return {
        "scope": scope,
        "split_id": split_id,
        "eval_date": eval_date,
        "baseline": baseline_name,
        "committed_accuracy": committed["accuracy"],
        "recomputed_accuracy": recomputed["accuracy"],
        "accuracy_delta": round(recomputed["accuracy"] - committed["accuracy"], 6),
        "committed_correct_count": committed["correct_count"],
        "recomputed_correct_count": recomputed["correct_count"],
        "correct_count_delta": recomputed["correct_count"] - committed["correct_count"],
        "committed_row_count": committed["row_count"],
        "recomputed_row_count": recomputed["row_count"],
        "row_count_delta": recomputed["row_count"] - committed["row_count"],
    }


def _load_committed_rows() -> list[dict[str, Any]]:
    fieldnames, rows = _load_csv_rows(SOURCE_P221_CSV)
    _require_columns(fieldnames, P221_REQUIRED_COLUMNS, _artifact_label(SOURCE_P221_CSV))
    committed_rows: list[dict[str, Any]] = []
    for row in rows:
        committed_rows.append(
            {
                "split_id": _parse_int(row["split_id"]),
                "train_date_range": row["train_date_range"],
                "eval_date": row["eval_date"],
                "source_row_id": _parse_int(row["source_row_id"]),
                "pitch_type": row["pitch_type"],
                "actual_event_category": row["actual_event_category"],
                "baseline_a_prediction": row["baseline_a_prediction"],
                "baseline_a_correct": _parse_bool(row["baseline_a_correct"]),
                "baseline_b_prediction": row["baseline_b_prediction"],
                "baseline_b_correct": _parse_bool(row["baseline_b_correct"]),
                "baseline_b_prediction_source": row["baseline_b_prediction_source"],
            }
        )
    return committed_rows


def _validate_source_artifacts_exist() -> None:
    missing = [path for path in SOURCE_ARTIFACTS if not path.exists()]
    if missing:
        labels = ", ".join(_artifact_label(path) for path in missing)
        raise _fail_insufficient(f"missing source artifacts: {labels}")


def _verify_source_hashes(p223_json: dict[str, Any]) -> dict[str, Any]:
    source_hashes = p223_json.get("source_hashes")
    if not isinstance(source_hashes, dict):
        raise _fail_insufficient("P223 JSON missing source_hashes map")

    verified_against_p223_index: list[dict[str, Any]] = []
    for artifact in P223_HASH_REQUIRED_ARTIFACTS:
        label = _artifact_label(artifact)
        expected = source_hashes.get(label)
        actual = _sha256(artifact)
        if expected is None or actual != expected:
            raise ValueError(
                f"P224A_STOPPED_SOURCE_ARTIFACT_MISMATCH: {label} expected {expected} got {actual}"
            )
        verified_against_p223_index.append(
            {
                "path": label,
                "expected_sha256": expected,
                "actual_sha256": actual,
                "match": True,
            }
        )

    observed_index_artifacts = [
        {
            "path": _artifact_label(SOURCE_P223_JSON),
            "actual_sha256": _sha256(SOURCE_P223_JSON),
            "verification_basis": "authoritative_index_json_observed_directly",
        },
        {
            "path": _artifact_label(SOURCE_P223_HTML),
            "actual_sha256": _sha256(SOURCE_P223_HTML),
            "verification_basis": "paired_index_html_observed_directly",
        },
    ]

    return {
        "status": "PASS_P218A_P221A_SOURCE_HASHES_MATCH_P223_INDEX",
        "p223_index_status": p223_json.get("status"),
        "p223_index_source_hash_validation": p223_json.get("source_hash_validation"),
        "verified_against_p223_index": verified_against_p223_index,
        "observed_index_artifacts": observed_index_artifacts,
    }


def _build_pit_feature_contract(
    feature_columns: list[str],
    derived_feature_definitions: dict[str, str],
) -> list[dict[str, Any]]:
    missing_contract_columns = [column for column in feature_columns if column not in PIT_CONTRACT_RULES]
    if missing_contract_columns:
        raise _fail_insufficient(
            "missing PIT contract rules for columns: " + ", ".join(missing_contract_columns)
        )

    contract_rows: list[dict[str, Any]] = []
    for column in feature_columns:
        rule = PIT_CONTRACT_RULES[column]
        definition = derived_feature_definitions.get(column)
        rationale_parts = []
        if definition:
            rationale_parts.append(definition.rstrip("."))
        rationale_parts.append(rule["rationale_suffix"])
        contract_rows.append(
            {
                "column_name": column,
                "source_artifact": _artifact_label(SOURCE_P218_CSV),
                "pit_category": rule["pit_category"],
                "allowed_use": rule["allowed_use"],
                "rationale": ". ".join(rationale_parts) + ".",
                "leakage_risk_level": rule["leakage_risk_level"],
                "required_guardrail": rule["required_guardrail"],
            }
        )
    return contract_rows


def _recompute_p221_from_train_window_only_rows(
    source_rows: list[dict[str, str | None]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    date_order = sorted({row["game_date"] or "" for row in source_rows})
    if len(date_order) < 2:
        raise _fail_insufficient("P218 source rows do not span at least two historical dates")

    recomputed_rows: list[dict[str, Any]] = []
    per_split_metrics: list[dict[str, Any]] = []
    split_summaries: list[dict[str, Any]] = []

    for split_index, eval_date in enumerate(date_order[1:], start=1):
        train_rows = [row for row in source_rows if (row["game_date"] or "") < eval_date]
        eval_rows = [row for row in source_rows if row["game_date"] == eval_date]
        if not train_rows or not eval_rows:
            raise _fail_insufficient(f"split {split_index} lacks train or evaluation rows")

        train_dates = sorted({row["game_date"] or "" for row in train_rows})
        train_targets = [row[TARGET_COLUMN] or "missing" for row in train_rows]
        global_majority = _majority_label(train_targets)
        pitch_type_rows = _pitch_type_resolution_table(train_rows, global_majority)
        pitch_type_table = {row["pitch_type"]: row for row in pitch_type_rows}
        split_rows: list[dict[str, Any]] = []

        for row in eval_rows:
            pitch_type = row.get("pitch_type") or "missing"
            actual = row.get(TARGET_COLUMN) or "missing"
            baseline_b_prediction, baseline_b_source = _resolve_baseline_b_prediction(
                pitch_type,
                pitch_type_table,
                global_majority,
            )
            split_rows.append(
                {
                    "split_id": split_index,
                    "train_date_range": _date_range_label(train_dates),
                    "eval_date": eval_date,
                    "source_row_id": _parse_int(row.get("source_row_id")),
                    "pitch_type": pitch_type,
                    "actual_event_category": actual,
                    "baseline_a_prediction": global_majority,
                    "baseline_a_correct": global_majority == actual,
                    "baseline_b_prediction": baseline_b_prediction,
                    "baseline_b_correct": baseline_b_prediction == actual,
                    "baseline_b_prediction_source": baseline_b_source,
                }
            )

        recomputed_rows.extend(split_rows)
        baseline_a_metrics = _baseline_metrics(split_rows, "baseline_a_prediction", "baseline_a_correct")
        baseline_b_metrics = _baseline_metrics(split_rows, "baseline_b_prediction", "baseline_b_correct")
        per_split_metrics.append(
            {
                "split_id": split_index,
                "eval_date": eval_date,
                BASELINE_A_KEY: baseline_a_metrics,
                BASELINE_B_KEY: baseline_b_metrics,
                "baseline_b_coverage": _baseline_b_coverage(split_rows),
            }
        )
        split_summaries.append(
            {
                "split_id": split_index,
                "train_date_range": _date_range_label(train_dates),
                "eval_date": eval_date,
                "train_row_count": len(train_rows),
                "eval_row_count": len(eval_rows),
                "baseline_a_global_majority_prediction": global_majority,
                "baseline_b_pitch_type_resolution_table": pitch_type_rows,
            }
        )

    overall_metrics = {
        BASELINE_A_KEY: _baseline_metrics(recomputed_rows, "baseline_a_prediction", "baseline_a_correct"),
        BASELINE_B_KEY: _baseline_metrics(recomputed_rows, "baseline_b_prediction", "baseline_b_correct"),
        "baseline_b_coverage": _baseline_b_coverage(recomputed_rows),
    }
    return recomputed_rows, per_split_metrics, {
        "split_count": len(split_summaries),
        "time_split_definitions": split_summaries,
        "overall_holdout_metrics": overall_metrics,
    }


def _compare_with_committed_p221(
    committed_rows: list[dict[str, Any]],
    committed_json: dict[str, Any],
    recomputed_rows: list[dict[str, Any]],
    recomputed_per_split_metrics: list[dict[str, Any]],
    recomputed_summary: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str, dict[str, Any]]:
    _require_keys(
        committed_json,
        ["per_split_metrics", "overall_holdout_metrics", "time_split_definitions", "row_count"],
        "P221 JSON",
    )

    if len(committed_rows) != committed_json["row_count"]:
        raise _fail_insufficient("P221 CSV row count does not match P221 JSON row_count")
    if len(recomputed_rows) != len(committed_rows):
        raise _fail_insufficient("recomputed row count does not match committed P221 row count")
    if len(recomputed_per_split_metrics) != len(committed_json["per_split_metrics"]):
        raise _fail_insufficient("recomputed split count does not match committed P221 split count")

    committed_row_map = {
        (row["split_id"], row["eval_date"], row["source_row_id"]): row
        for row in committed_rows
    }
    row_comparison_table: list[dict[str, Any]] = []
    mismatched_row_count = 0

    for row in recomputed_rows:
        key = (row["split_id"], row["eval_date"], row["source_row_id"])
        committed = committed_row_map.get(key)
        if committed is None:
            raise _fail_insufficient(f"missing committed P221 row for key={key}")

        comparison = {
            "split_id": row["split_id"],
            "eval_date": row["eval_date"],
            "source_row_id": row["source_row_id"],
            "pitch_type": row["pitch_type"],
            "actual_event_category": row["actual_event_category"],
            "committed_baseline_a_prediction": committed["baseline_a_prediction"],
            "recomputed_baseline_a_prediction": row["baseline_a_prediction"],
            "baseline_a_prediction_match": committed["baseline_a_prediction"] == row["baseline_a_prediction"],
            "committed_baseline_b_prediction": committed["baseline_b_prediction"],
            "recomputed_baseline_b_prediction": row["baseline_b_prediction"],
            "baseline_b_prediction_match": committed["baseline_b_prediction"] == row["baseline_b_prediction"],
            "committed_baseline_b_prediction_source": committed["baseline_b_prediction_source"],
            "recomputed_baseline_b_prediction_source": row["baseline_b_prediction_source"],
            "baseline_b_prediction_source_match": committed["baseline_b_prediction_source"]
            == row["baseline_b_prediction_source"],
            "committed_baseline_a_correct": committed["baseline_a_correct"],
            "recomputed_baseline_a_correct": row["baseline_a_correct"],
            "baseline_a_correct_match": committed["baseline_a_correct"] == row["baseline_a_correct"],
            "committed_baseline_b_correct": committed["baseline_b_correct"],
            "recomputed_baseline_b_correct": row["baseline_b_correct"],
            "baseline_b_correct_match": committed["baseline_b_correct"] == row["baseline_b_correct"],
        }
        comparison["all_prediction_fields_match"] = all(
            [
                comparison["baseline_a_prediction_match"],
                comparison["baseline_b_prediction_match"],
                comparison["baseline_b_prediction_source_match"],
                comparison["baseline_a_correct_match"],
                comparison["baseline_b_correct_match"],
            ]
        )
        if not comparison["all_prediction_fields_match"]:
            mismatched_row_count += 1
        row_comparison_table.append(comparison)

    metric_delta_table: list[dict[str, Any]] = []
    for committed_split, recomputed_split in zip(
        committed_json["per_split_metrics"],
        recomputed_per_split_metrics,
    ):
        metric_delta_table.append(
            _metric_delta_row(
                scope=f"split_{committed_split['split_id']}",
                split_id=committed_split["split_id"],
                eval_date=committed_split["eval_date"],
                baseline_name=BASELINE_A_KEY,
                committed=committed_split[BASELINE_A_KEY],
                recomputed=recomputed_split[BASELINE_A_KEY],
            )
        )
        metric_delta_table.append(
            _metric_delta_row(
                scope=f"split_{committed_split['split_id']}",
                split_id=committed_split["split_id"],
                eval_date=committed_split["eval_date"],
                baseline_name=BASELINE_B_KEY,
                committed=committed_split[BASELINE_B_KEY],
                recomputed=recomputed_split[BASELINE_B_KEY],
            )
        )

    metric_delta_table.append(
        _metric_delta_row(
            scope="overall",
            split_id=None,
            eval_date="overall",
            baseline_name=BASELINE_A_KEY,
            committed=committed_json["overall_holdout_metrics"][BASELINE_A_KEY],
            recomputed=recomputed_summary["overall_holdout_metrics"][BASELINE_A_KEY],
        )
    )
    metric_delta_table.append(
        _metric_delta_row(
            scope="overall",
            split_id=None,
            eval_date="overall",
            baseline_name=BASELINE_B_KEY,
            committed=committed_json["overall_holdout_metrics"][BASELINE_B_KEY],
            recomputed=recomputed_summary["overall_holdout_metrics"][BASELINE_B_KEY],
        )
    )

    metrics_match = all(
        row["accuracy_delta"] == 0.0
        and row["correct_count_delta"] == 0
        and row["row_count_delta"] == 0
        for row in metric_delta_table
    )
    predictions_match = mismatched_row_count == 0
    if metrics_match and predictions_match:
        conclusion = "NO_DERIVATION_WINDOW_LEAKAGE_DETECTED"
    else:
        conclusion = "DERIVATION_WINDOW_LEAKAGE_SUSPECTED"

    comparison_summary = {
        "committed_split_count": len(committed_json["time_split_definitions"]),
        "recomputed_split_count": recomputed_summary["split_count"],
        "committed_row_count": committed_json["row_count"],
        "recomputed_row_count": len(recomputed_rows),
        "row_prediction_match_count": len(row_comparison_table) - mismatched_row_count,
        "row_prediction_mismatch_count": mismatched_row_count,
        "metrics_match": metrics_match,
        "predictions_match": predictions_match,
    }
    return row_comparison_table, metric_delta_table, conclusion, comparison_summary


def build_payload() -> dict[str, Any]:
    _validate_source_artifacts_exist()

    p223_json = _load_json(SOURCE_P223_JSON)
    p218_json = _load_json(SOURCE_P218_JSON)
    p221_json = _load_json(SOURCE_P221_JSON)
    _require_keys(p218_json, ["feature_columns", "derived_feature_definitions", "row_count"], "P218 JSON")
    _require_keys(p221_json, ["overall_holdout_metrics", "per_split_metrics", "row_count"], "P221 JSON")

    source_hash_verification = _verify_source_hashes(p223_json)
    p218_fieldnames, p218_rows = _load_csv_rows(SOURCE_P218_CSV)
    _require_columns(p218_fieldnames, P218_REQUIRED_COLUMNS, _artifact_label(SOURCE_P218_CSV))
    if p218_json["feature_columns"] != P218_REQUIRED_COLUMNS:
        raise _fail_insufficient("P218 feature_columns do not match the committed expected contract order")
    if len(p218_rows) != p218_json["row_count"]:
        raise _fail_insufficient("P218 CSV row count does not match P218 JSON row_count")

    pit_feature_contract = _build_pit_feature_contract(
        p218_json["feature_columns"],
        p218_json["derived_feature_definitions"],
    )
    committed_rows = _load_committed_rows()
    recomputed_rows, recomputed_per_split_metrics, recomputed_summary = _recompute_p221_from_train_window_only_rows(
        p218_rows
    )
    row_comparison_table, metric_delta_table, leakage_conclusion, comparison_summary = _compare_with_committed_p221(
        committed_rows,
        p221_json,
        recomputed_rows,
        recomputed_per_split_metrics,
        recomputed_summary,
    )

    limitations = [
        "Historical artifact audit only: all conclusions are bounded to the fixed committed P218, P221, and P223 artifacts.",
        "The audit verifies train-window-only derivation for the committed baseline heuristics; it does not establish production readiness or future predictive value.",
        "P223 can verify the P218 and P221 source artifact hashes it indexes, but its own JSON and HTML files are observed directly rather than self-hashed inside the same index.",
        "PIT classifications for participant identity fields remain conservative because the artifact captures realized pitch-event participants, not a separate pregame roster contract.",
    ]

    return {
        "task": TASK_NAME,
        "status": STATUS,
        "disclaimer": DISCLAIMER,
        "historical_only_disclaimer": DISCLAIMER,
        "source_artifacts": [_artifact_label(path) for path in SOURCE_ARTIFACTS],
        "source_hashes": {
            _artifact_label(path): _sha256(path)
            for path in SOURCE_ARTIFACTS
        },
        "source_hash_verification": source_hash_verification,
        "source_summary": {
            "p218_feature_column_count": len(p218_fieldnames),
            "p218_feature_row_count": len(p218_rows),
            "p221_committed_row_count": len(committed_rows),
            "p221_committed_split_count": len(p221_json["per_split_metrics"]),
            "p223_status": p223_json.get("status"),
            "p223_hash_validation_status": p223_json.get("source_hash_validation"),
        },
        "pit_feature_contract": pit_feature_contract,
        "leakage_audit_results": {
            "recompute_method": [
                "Read only the fixed committed P218, P221, and P223 artifacts.",
                "For each P221 eval_date split, use only P218 rows with game_date earlier than eval_date as the derivation window.",
                "Recompute Baseline A as the train-window global majority event_category using deterministic alphabetical tie-break.",
                "Recompute Baseline B as the train-window pitch_type majority event_category with fallback to the same split's train-window global majority when pitch_type support is tied or absent.",
                "Compare recomputed per-row predictions and per-split metrics against the committed P221 artifacts.",
            ],
            "committed_reference_metrics": {
                "split_count": len(p221_json["per_split_metrics"]),
                "evaluated_rows": p221_json["row_count"],
                "baseline_a_overall_accuracy": p221_json["overall_holdout_metrics"][BASELINE_A_KEY]["accuracy"],
                "baseline_b_overall_accuracy": p221_json["overall_holdout_metrics"][BASELINE_B_KEY]["accuracy"],
            },
            "recomputed_reference_metrics": {
                "split_count": recomputed_summary["split_count"],
                "evaluated_rows": len(recomputed_rows),
                "baseline_a_overall_accuracy": recomputed_summary["overall_holdout_metrics"][BASELINE_A_KEY]["accuracy"],
                "baseline_b_overall_accuracy": recomputed_summary["overall_holdout_metrics"][BASELINE_B_KEY]["accuracy"],
            },
            "per_split_committed_metrics": p221_json["per_split_metrics"],
            "per_split_recomputed_metrics": recomputed_per_split_metrics,
            "metrics_delta_table": metric_delta_table,
            "row_comparison_table": row_comparison_table,
            "recomputed_split_summaries": recomputed_summary["time_split_definitions"],
            "comparison_summary": comparison_summary,
            "leakage_conclusion": leakage_conclusion,
        },
        "limitations": limitations,
        "prohibited_claims": PROHIBITED_CLAIMS,
    }


def write_json(payload: dict[str, Any]) -> None:
    OUT_JSON.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _render_table(rows: list[dict[str, Any]], columns: list[str]) -> list[str]:
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_md_cell(row.get(column)) for column in columns) + " |")
    return lines


def render_markdown(payload: dict[str, Any]) -> str:
    audit_results = payload["leakage_audit_results"]
    contract_rows = []
    for row in payload["pit_feature_contract"]:
        allowed_use = row["allowed_use"]
        contract_rows.append(
            {
                "column_name": row["column_name"],
                "pit_category": row["pit_category"],
                "pregame_model_feature_allowed": allowed_use["pregame_model_feature_allowed"],
                "in_game_analysis_allowed": allowed_use["in_game_analysis_allowed"],
                "label_or_outcome_only": allowed_use["label_or_outcome_only"],
                "audit_only": allowed_use["audit_only"],
                "leakage_risk_level": row["leakage_risk_level"],
                "required_guardrail": row["required_guardrail"],
                "rationale": row["rationale"],
            }
        )
    lines = [
        "# P224-A PIT Feature Contract + Baseline Derivation Window Leakage Audit",
        "",
        DISCLAIMER,
        "",
        "## Summary",
        "",
        f"- Status: {payload['status']}",
        f"- Leakage conclusion: {audit_results['leakage_conclusion']}",
        f"- P218 feature columns classified: {len(payload['pit_feature_contract'])}",
        f"- Committed P221 split count: {audit_results['committed_reference_metrics']['split_count']}",
        f"- Committed P221 evaluated rows: {audit_results['committed_reference_metrics']['evaluated_rows']}",
        f"- Committed Baseline A overall accuracy: {audit_results['committed_reference_metrics']['baseline_a_overall_accuracy']:.6f}",
        f"- Committed Baseline B overall accuracy: {audit_results['committed_reference_metrics']['baseline_b_overall_accuracy']:.6f}",
        f"- Recomputed Baseline A overall accuracy: {audit_results['recomputed_reference_metrics']['baseline_a_overall_accuracy']:.6f}",
        f"- Recomputed Baseline B overall accuracy: {audit_results['recomputed_reference_metrics']['baseline_b_overall_accuracy']:.6f}",
        "",
        "## Source Hash Verification",
        "",
    ]
    lines.extend(
        _render_table(
            payload["source_hash_verification"]["verified_against_p223_index"],
            ["path", "expected_sha256", "actual_sha256", "match"],
        )
    )
    lines.extend(
        [
            "",
            "Observed P223 index artifacts:",
            "",
        ]
    )
    lines.extend(
        _render_table(
            payload["source_hash_verification"]["observed_index_artifacts"],
            ["path", "actual_sha256", "verification_basis"],
        )
    )
    lines.extend(
        [
            "",
            "## PIT Feature Contract",
            "",
        ]
    )
    lines.extend(
        _render_table(
            contract_rows,
            [
                "column_name",
                "pit_category",
                "pregame_model_feature_allowed",
                "in_game_analysis_allowed",
                "label_or_outcome_only",
                "audit_only",
                "leakage_risk_level",
                "required_guardrail",
                "rationale",
            ],
        )
    )
    lines.extend(
        [
            "",
            "## Metrics Delta Table",
            "",
        ]
    )
    lines.extend(
        _render_table(
            audit_results["metrics_delta_table"],
            [
                "scope",
                "split_id",
                "eval_date",
                "baseline",
                "committed_accuracy",
                "recomputed_accuracy",
                "accuracy_delta",
                "committed_correct_count",
                "recomputed_correct_count",
                "correct_count_delta",
                "committed_row_count",
                "recomputed_row_count",
                "row_count_delta",
            ],
        )
    )
    lines.extend(
        [
            "",
            "## Row Comparison Table",
            "",
        ]
    )
    lines.extend(
        _render_table(
            audit_results["row_comparison_table"],
            [
                "split_id",
                "eval_date",
                "source_row_id",
                "pitch_type",
                "actual_event_category",
                "committed_baseline_a_prediction",
                "recomputed_baseline_a_prediction",
                "baseline_a_prediction_match",
                "committed_baseline_b_prediction",
                "recomputed_baseline_b_prediction",
                "baseline_b_prediction_match",
                "committed_baseline_b_prediction_source",
                "recomputed_baseline_b_prediction_source",
                "baseline_b_prediction_source_match",
                "all_prediction_fields_match",
            ],
        )
    )
    lines.extend(
        [
            "",
            "## Limitations",
            "",
        ]
    )
    for limitation in payload["limitations"]:
        lines.append(f"- {limitation}")
    lines.extend(
        [
            "",
            "## Prohibited Claims",
            "",
        ]
    )
    for claim in payload["prohibited_claims"]:
        lines.append(f"- {claim}")
    lines.extend(
        [
            "",
            "Historical PIT contract and leakage audit only. Not live predictions, not betting advice.",
            "",
        ]
    )
    return "\n".join(lines)


def write_markdown(payload: dict[str, Any]) -> None:
    OUT_MD.write_text(render_markdown(payload), encoding="utf-8")


def main() -> None:
    try:
        payload = build_payload()
        write_json(payload)
        write_markdown(payload)
    except Exception as exc:
        print(FAILURE_BANNER)
        print(str(exc))
        raise
    print(SUCCESS_BANNER)
    print(f"Wrote {_artifact_label(OUT_JSON)}")
    print(f"Wrote {_artifact_label(OUT_MD)}")


if __name__ == "__main__":
    main()
