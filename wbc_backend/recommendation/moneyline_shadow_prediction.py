"""P278-A corrected Moneyline paper-only local shadow prediction handoff.

The generator refits the P276-selected ``retrained_team_history_smooth`` model
on every eligible 2025 game, freezes the state after the final complete date,
and scores the already committed P84-B 2026 prediction-input rows.  It never
fetches data, writes a database, treats a raw outcome flag as availability, or
derives a feature as-of from a game date, file metadata, or wall time.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shlex
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts import _p274_prospective_result_availability_index as p274
from scripts import _p275_prospective_availability_consumer_gate as p275
from wbc_backend.recommendation import local_retrain_scorecard as retrain


ALGORITHM_NAME = "retrained_team_history_smooth"
MODEL_ID = "corrected_moneyline_shadow"
MODEL_VERSION = "p278a_corrected_moneyline_shadow_v1"
ARTIFACT_VERSION = MODEL_VERSION
GENERATOR_VERSION = "p278a.moneyline_shadow_prediction.v1"
BASELINE_SOURCE_VERSION = "p84b_diagnostic_baseline_v1"
STATE_TRANSITION_CONTRACT = "PREDICT_FULL_DATE_THEN_UPDATE"
STATE_UPDATE_POLICY = (
    "P275_EXACT_GAME_ID_AND_CANONICAL_ROW_AS_OF_COMPLETE_DATE_BATCH_ONLY"
)
FROZEN_STATE_MODE = "frozen_final_2025_state"
GATED_STATE_MODE = "p275_gated_rolling_state"
PROVENANCE_REFERENCE = "report/mlb_2026_corrected_moneyline_shadow_manifest.json"
P274_COVERAGE_LIMITATION = (
    "P274 currently contains one prospective availability record; it does not "
    "establish season-wide PIT coverage or replay readiness."
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRAINING_PATH = REPO_ROOT / "data/mlb_2025/mlb_odds_2025_real.csv"
DEFAULT_PREDICTION_INPUT_PATH = (
    REPO_ROOT / "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl"
)
DEFAULT_OUTCOME_PATH = (
    REPO_ROOT
    / "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl"
)
DEFAULT_AVAILABILITY_ROOT = (
    REPO_ROOT
    / "data/mlb_2026/derived/p274_prospective_result_availability_index_v1"
)
DEFAULT_AVAILABILITY_INDEX_PATH = DEFAULT_AVAILABILITY_ROOT / p274.INDEX_FILENAME
DEFAULT_AVAILABILITY_MANIFEST_PATH = DEFAULT_AVAILABILITY_ROOT / p274.CHECKSUM_FILENAME
DEFAULT_OUT_DIR = REPO_ROOT / "report"

CSV_FILENAME = "mlb_2026_corrected_moneyline_shadow_predictions.csv"
MANIFEST_FILENAME = "mlb_2026_corrected_moneyline_shadow_manifest.json"
SUMMARY_FILENAME = "mlb_2026_corrected_moneyline_shadow_summary.md"

PREDICTION_OUTCOME_FIELDS = (
    "actual_winner",
    "is_correct",
    "result_home_score",
    "result_away_score",
)


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _portable_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _runtime_timestamp() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class RefitResult:
    state: retrain.DateBatchedTeamState
    metadata: dict[str, Any]


@dataclass
class GateAccounting:
    attempted: int = 0
    allowed: int = 0
    denied: int = 0
    denial_reasons: Counter[str] = field(default_factory=Counter)
    attempted_game_ids: set[str] = field(default_factory=set)
    applied_game_ids: set[str] = field(default_factory=set)

    def record_denied_batch(
        self,
        decisions: list[p275.AvailabilityGateDecision],
        *,
        batch_reason: str,
    ) -> None:
        self.attempted += len(decisions)
        self.denied += len(decisions)
        for decision in decisions:
            self.attempted_game_ids.add(decision.game_id)
            reason = decision.block_reason or batch_reason
            self.denial_reasons[reason] += 1

    def record_allowed_batch(
        self, decisions: list[p275.AvailabilityGateDecision]
    ) -> None:
        self.attempted += len(decisions)
        self.allowed += len(decisions)
        for decision in decisions:
            self.attempted_game_ids.add(decision.game_id)
            self.applied_game_ids.add(decision.game_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempted": self.attempted,
            "allowed": self.allowed,
            "denied": self.denied,
            "denial_counts_by_reason": dict(sorted(self.denial_reasons.items())),
        }


def refit_selected_model(training_path: Path) -> RefitResult:
    """Refit the selected model on all eligible 2025 rows in complete dates."""
    training_path = Path(training_path)
    loaded = retrain.load_games(training_path)
    games = [game for game in loaded if game.dt.year == 2025]
    if not games:
        raise ValueError("training input has no eligible 2025 games")

    state = retrain.DateBatchedTeamState()
    date_batches = list(retrain.iter_date_batches(games))
    for batch in date_batches:
        state.advance_date(batch, collect=False)

    canonical_rows = [
        {
            "game_id": game.game_id,
            "game_date": game.date,
            "away_team": game.away,
            "home_team": game.home,
            "home_win": game.home_win,
        }
        for batch in date_batches
        for game in batch
    ]
    selected_state = state.selected_model_state()
    metadata = {
        "algorithm": ALGORITHM_NAME,
        "training_path": _portable_path(training_path),
        "training_input_fingerprint": _sha256_file(training_path),
        "eligible_training_rows_fingerprint": _sha256_bytes(
            _canonical_json_bytes(canonical_rows)
        ),
        "eligible_row_count": len(games),
        "eligible_date_count": len(date_batches),
        "first_training_date": date_batches[0][0].date,
        "last_training_date": date_batches[-1][0].date,
        "training_cutoff": f"after_complete_date_{date_batches[-1][0].date}",
        "state_transition_contract": STATE_TRANSITION_CONTRACT,
        "final_state_fingerprint": _sha256_bytes(_canonical_json_bytes(selected_state)),
        "team_count": len(selected_state["history_games"]),
    }
    return RefitResult(state=state, metadata=metadata)


def _canonical_feature_as_of(value: Any) -> tuple[str | None, str]:
    if value is None or str(value).strip() == "":
        return None, "missing"
    try:
        canonical, _ = p274.parse_canonical_utc(str(value), "feature_as_of_utc")
    except p274.P274Error:
        return None, "invalid"
    return canonical, "explicit_canonical"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{line_number}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"JSONL row must be an object at {path}:{line_number}")
            rows.append(payload)
    return rows


def load_prediction_inputs(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load only the pre-outcome identity contract from the P84-B path."""
    raw_rows = _load_jsonl(path)
    if not raw_rows:
        raise ValueError("2026 prediction input has no rows")

    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_rows, start=1):
        game_id = str(raw.get("game_id") or "").strip()
        game_date = str(raw.get("game_date") or "").strip()
        home_team = str(raw.get("home_team") or "").strip()
        away_team = str(raw.get("away_team") or "").strip()
        if not game_id or not game_date or not home_team or not away_team:
            raise ValueError(f"missing deterministic game identity in input row {index}")
        if home_team.casefold() == away_team.casefold():
            raise ValueError(f"invalid same-team matchup for {game_id}")
        try:
            parsed_date = datetime.strptime(game_date, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError(f"invalid game_date for {game_id}: {game_date!r}") from exc
        if parsed_date.year != 2026:
            raise ValueError(f"non-2026 game in prediction input: {game_id}")
        if game_id in seen_ids:
            raise ValueError(f"duplicate game_id in prediction input: {game_id}")
        seen_ids.add(game_id)

        source_version = str(raw.get("source_prediction_version") or "").strip()
        if source_version != BASELINE_SOURCE_VERSION:
            raise ValueError(
                f"unexpected prediction source for {game_id}: {source_version!r}"
            )
        leaked = [
            field_name
            for field_name in PREDICTION_OUTCOME_FIELDS
            if raw.get(field_name) is not None
        ]
        if leaked:
            raise ValueError(
                f"prediction input contains outcome fields for {game_id}: {leaked}"
            )

        feature_as_of, as_of_status = _canonical_feature_as_of(
            raw.get("feature_as_of_utc")
        )
        rows.append(
            {
                "game_id": game_id,
                "game_date": game_date,
                "home_team": home_team,
                "away_team": away_team,
                "source_prediction_version": source_version,
                "feature_as_of_utc": feature_as_of,
                "feature_as_of_status": as_of_status,
            }
        )

    rows.sort(
        key=lambda row: (
            row["game_date"],
            row["game_id"],
            row["away_team"],
            row["home_team"],
        )
    )
    canonical_identity = [
        {
            key: row[key]
            for key in (
                "game_id",
                "game_date",
                "away_team",
                "home_team",
                "source_prediction_version",
                "feature_as_of_utc",
            )
        }
        for row in rows
    ]
    metadata = {
        "prediction_input_path": _portable_path(path),
        "prediction_input_fingerprint": _sha256_file(path),
        "eligible_rows_fingerprint": _sha256_bytes(
            _canonical_json_bytes(canonical_identity)
        ),
        "row_count": len(rows),
        "date_count": len({row["game_date"] for row in rows}),
        "first_game_date": rows[0]["game_date"],
        "last_game_date": rows[-1]["game_date"],
        "explicit_canonical_as_of_rows": sum(
            row["feature_as_of_status"] == "explicit_canonical" for row in rows
        ),
        "missing_as_of_rows": sum(
            row["feature_as_of_status"] == "missing" for row in rows
        ),
        "invalid_as_of_rows": sum(
            row["feature_as_of_status"] == "invalid" for row in rows
        ),
    }
    return rows, metadata


def _index_outcome_rows(path: Path | None) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if path is None or not Path(path).exists():
        return {}, {
            "outcome_path": _portable_path(path),
            "outcome_input_fingerprint": None,
            "row_count": 0,
            "raw_outcome_available_true_rows": 0,
        }
    rows = _load_jsonl(path)
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        game_id = str(row.get("game_id") or "").strip()
        if not game_id:
            raise ValueError("outcome row is missing game_id")
        if game_id in indexed:
            raise ValueError(f"duplicate game_id in outcome input: {game_id}")
        indexed[game_id] = row
    return indexed, {
        "outcome_path": _portable_path(path),
        "outcome_input_fingerprint": _sha256_file(path),
        "row_count": len(rows),
        "raw_outcome_available_true_rows": sum(
            row.get("outcome_available") is True for row in rows
        ),
    }


def _group_prediction_dates(
    rows: list[dict[str, Any]],
) -> list[tuple[str, list[dict[str, Any]]]]:
    grouped: list[tuple[str, list[dict[str, Any]]]] = []
    for row in rows:
        if not grouped or grouped[-1][0] != row["game_date"]:
            grouped.append((row["game_date"], []))
        grouped[-1][1].append(row)
    return grouped


def _complete_date_as_of(batch: list[dict[str, Any]]) -> str | None:
    values = {row["feature_as_of_utc"] for row in batch}
    if len(values) != 1 or None in values:
        return None
    return next(iter(values))


def _outcome_home_win(
    prediction: dict[str, Any], outcome: dict[str, Any]
) -> int:
    if str(outcome.get("game_id") or "") != prediction["game_id"]:
        raise ValueError("outcome identity mismatch")
    actual_winner = str(outcome.get("actual_winner") or "").strip().lower()
    if actual_winner in {"home", "away"}:
        return int(actual_winner == "home")
    try:
        home_score = int(outcome["result_home_score"])
        away_score = int(outcome["result_away_score"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid outcome payload for {prediction['game_id']}") from exc
    if home_score == away_score:
        raise ValueError(f"tied outcome payload for {prediction['game_id']}")
    return int(home_score > away_score)


def _outcome_game(
    prediction: dict[str, Any], outcome: dict[str, Any]
) -> retrain.Game:
    return retrain.Game(
        dt=datetime.strptime(prediction["game_date"], "%Y-%m-%d"),
        date=prediction["game_date"],
        home=prediction["home_team"],
        away=prediction["away_team"],
        home_win=_outcome_home_win(prediction, outcome),
    )


def _availability_record_count(index_path: Path, manifest_path: Path) -> tuple[int, str]:
    try:
        index = p275.load_verified_availability_index(index_path, manifest_path)
    except p275.MissingAvailabilityEvidenceError:
        return 0, p275.MISSING_AVAILABILITY_EVIDENCE
    except p275.InvalidAvailabilityEvidenceError:
        return 0, p275.INVALID_AVAILABILITY_EVIDENCE
    return int(index["record_count"]), "VERIFIED"


def _model_provenance() -> dict[str, Any]:
    source_files = {
        "wbc_backend/recommendation/local_retrain_scorecard.py": _sha256_file(
            Path(retrain.__file__)
        ),
        "wbc_backend/recommendation/moneyline_shadow_prediction.py": _sha256_file(
            Path(__file__)
        ),
    }
    config = {
        "algorithm": ALGORITHM_NAME,
        "smooth_k": retrain.SMOOTH_K,
        "home_logit_bump": retrain.HOME_LOGIT_BUMP,
        "state_transition_contract": STATE_TRANSITION_CONTRACT,
        "state_update_policy": STATE_UPDATE_POLICY,
    }
    fingerprint_payload = {"config": config, "source_files": source_files}
    return {
        "config": config,
        "source_file_fingerprints": source_files,
        "model_code_config_fingerprint": _sha256_bytes(
            _canonical_json_bytes(fingerprint_payload)
        ),
    }


def _gate_pending_date_batches(
    *,
    state: retrain.DateBatchedTeamState,
    prior_batches: list[tuple[str, list[dict[str, Any]]]],
    outcome_rows: dict[str, dict[str, Any]],
    feature_as_of_utc: str,
    index_path: Path,
    manifest_path: Path,
    accounting: GateAccounting,
    applied_dates: set[str],
    attempted_date_as_of_pairs: set[tuple[str, str]],
) -> None:
    """Apply only complete prior-date batches whose every P275 decision allows."""
    for game_date, batch in prior_batches:
        if game_date in applied_dates:
            continue
        attempt_key = (game_date, feature_as_of_utc)
        if attempt_key in attempted_date_as_of_pairs:
            continue
        candidate_outcomes = [outcome_rows.get(row["game_id"]) for row in batch]
        if any(
            outcome is None or outcome.get("outcome_available") is not True
            for outcome in candidate_outcomes
        ):
            continue
        attempted_date_as_of_pairs.add(attempt_key)
        decisions = [
            p275.evaluate_result_availability(
                game_id=row["game_id"],
                feature_as_of_utc=feature_as_of_utc,
                index_path=index_path,
                manifest_path=manifest_path,
            )
            for row in batch
        ]
        if not all(decision.result_usage_allowed for decision in decisions):
            accounting.record_denied_batch(
                decisions,
                batch_reason="complete_date_batch_not_fully_gate_available",
            )
            continue
        try:
            games = [
                _outcome_game(row, outcome)
                for row, outcome in zip(batch, candidate_outcomes)
                if outcome is not None
            ]
        except ValueError:
            accounting.record_denied_batch(
                [
                    p275.AvailabilityGateDecision(
                        result_usage_allowed=False,
                        block_reason="invalid_outcome_payload_after_gate",
                        game_id=decision.game_id,
                        feature_as_of_utc=decision.feature_as_of_utc,
                        result_available_at_utc=decision.result_available_at_utc,
                    )
                    for decision in decisions
                ],
                batch_reason="invalid_outcome_payload_after_gate",
            )
            continue
        state.advance_date(games, collect=False)
        accounting.record_allowed_batch(decisions)
        applied_dates.add(game_date)


def _evaluate_predictions(
    *,
    prediction_rows: list[dict[str, Any]],
    shadow_rows: list[dict[str, Any]],
    outcome_rows: dict[str, dict[str, Any]],
    index_path: Path,
    manifest_path: Path,
) -> tuple[dict[str, Any], GateAccounting]:
    accounting = GateAccounting()
    by_id = {row["game_id"]: row for row in shadow_rows}
    probabilities: list[float] = []
    outcomes: list[int] = []
    for prediction in prediction_rows:
        outcome = outcome_rows.get(prediction["game_id"])
        feature_as_of = prediction["feature_as_of_utc"]
        if (
            outcome is None
            or outcome.get("outcome_available") is not True
            or feature_as_of is None
        ):
            continue
        decision = p275.evaluate_result_availability(
            game_id=prediction["game_id"],
            feature_as_of_utc=feature_as_of,
            index_path=index_path,
            manifest_path=manifest_path,
        )
        accounting.attempted += 1
        accounting.attempted_game_ids.add(prediction["game_id"])
        if not decision.result_usage_allowed:
            accounting.denied += 1
            accounting.denial_reasons[
                decision.block_reason or p275.INVALID_AVAILABILITY_EVIDENCE
            ] += 1
            continue
        try:
            actual = _outcome_home_win(prediction, outcome)
        except ValueError:
            accounting.denied += 1
            accounting.denial_reasons["invalid_outcome_payload_after_gate"] += 1
            continue
        accounting.allowed += 1
        accounting.applied_game_ids.add(prediction["game_id"])
        probabilities.append(float(by_id[prediction["game_id"]]["shadow_home_win_probability"]))
        outcomes.append(actual)
        by_id[prediction["game_id"]]["outcome_evaluation_gate_available"] = True

    denominator = len(outcomes)
    accuracy = None
    brier = None
    if denominator:
        accuracy = sum(
            int((probability >= 0.5) == (actual == 1))
            for probability, actual in zip(probabilities, outcomes)
        ) / denominator
        brier = sum(
            (probability - actual) ** 2
            for probability, actual in zip(probabilities, outcomes)
        ) / denominator
    return {
        "outcome_evaluation_denominator": denominator,
        "accuracy": None if accuracy is None else round(accuracy, 6),
        "brier_score": None if brier is None else round(brier, 6),
        "roi": None,
        "expected_value": None,
        "kelly": None,
        "zero_denominator_metrics_display": "N/A" if denominator == 0 else None,
    }, accounting


def _write_predictions_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fields = [
        "game_id",
        "game_date",
        "away_team",
        "home_team",
        "shadow_home_win_probability",
        "predicted_side",
        "model_id",
        "model_version",
        "source_input_identity",
        "source_prediction_version",
        "state_mode",
        "feature_as_of_utc",
        "prior_outcome_update_applied",
        "outcome_evaluation_gate_available",
        "provenance_reference",
        "paper_only",
        "diagnostic_only",
        "retrospectively_generated",
        "production_ready",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _metric_display(value: Any) -> str:
    return "N/A" if value is None else str(value)


def render_summary(manifest: dict[str, Any]) -> str:
    training = manifest["training"]
    inputs = manifest["prediction_input"]
    updates = manifest["p275_state_updates"]
    evaluation = manifest["outcome_evaluation"]
    runtime = manifest["generation"]["runtime_metadata"]
    lines = [
        "# P278-A Corrected Moneyline Local Shadow Prediction Handoff",
        "",
        "> Retrospectively generated from committed local data. Paper-only and "
        "diagnostic-only; not a live or pregame publication, not production-ready, "
        "not deployment, and not betting readiness.",
        "",
        "## Model and refit",
        "",
        f"- Selected model: `{manifest['model']['algorithm']}`",
        f"- Model/version: `{manifest['model']['model_id']}` / "
        f"`{manifest['model']['model_version']}`",
        f"- Training period: `{training['first_training_date']}` to "
        f"`{training['last_training_date']}`",
        f"- Training cutoff: `{training['training_cutoff']}`",
        f"- Eligible training rows/dates: `{training['eligible_row_count']}` / "
        f"`{training['eligible_date_count']}`",
        f"- State transition: `{training['state_transition_contract']}`",
        f"- Final state fingerprint: `{training['final_state_fingerprint']}`",
        f"- Model code/config fingerprint: "
        f"`{manifest['model']['model_code_config_fingerprint']}`",
        f"- Training input fingerprint: `{training['training_input_fingerprint']}`",
        "",
        "## 2026 shadow generation",
        "",
        f"- Existing committed input rows: `{inputs['row_count']}`",
        f"- Shadow prediction rows: `{manifest['artifacts']['prediction_row_count']}`",
        f"- 2026 input fingerprint: `{inputs['prediction_input_fingerprint']}`",
        f"- State mode: `{manifest['state_mode']}`",
        f"- Source Git commit: `{manifest['source_git_commit']}`",
        f"- Generator/version: `{manifest['generation']['generator_version']}`",
        f"- Generated at: `{runtime['generated_at_utc']}`",
        f"- Execution command: `{runtime['execution_command']}`",
        f"- Execution output root: `{runtime['execution_output_root']}`",
        (
            "- No row supplied a trustworthy explicit canonical feature-as-of; no "
            "game date, current time, or file mtime was substituted."
            if inputs["explicit_canonical_as_of_rows"] == 0
            else "- Explicit canonical row-level as-of values were used only through "
            "the P275 gate; no date, current time, or mtime was substituted."
        ),
        "",
        "## P275 availability and state-update policy",
        "",
        f"- Policy: `{manifest['p275_policy']}`",
        f"- P274 verified record count: "
        f"`{manifest['availability_evidence']['record_count']}`",
        f"- Attempted / allowed / denied updates: `{updates['attempted']}` / "
        f"`{updates['allowed']}` / `{updates['denied']}`",
        f"- Applied 2026 outcome updates: `{updates['applied']}`",
        f"- Denial counts by reason: `{updates['denial_counts_by_reason']}`",
        f"- Raw outcome-available candidates not attempted without a trustworthy "
        f"as-of: `{updates['candidate_rows_not_attempted']}`",
        f"- Coverage limitation: {P274_COVERAGE_LIMITATION}",
        "",
        "## Separation and evaluation",
        "",
        f"- Existing baseline remains separate: `{BASELINE_SOURCE_VERSION}`.",
        "- Existing P84-B predictions remain byte-unchanged and were not relabeled "
        "or replaced.",
        f"- Corrected shadow source: `{ARTIFACT_VERSION}`; no champion activation.",
        f"- Outcome-evaluation denominator: "
        f"`{evaluation['outcome_evaluation_denominator']}`",
        f"- Accuracy: `{_metric_display(evaluation['accuracy'])}`",
        f"- Brier: `{_metric_display(evaluation['brier_score'])}`",
        f"- ROI / EV / Kelly: `{_metric_display(evaluation['roi'])}` / "
        f"`{_metric_display(evaluation['expected_value'])}` / "
        f"`{_metric_display(evaluation['kelly'])}`",
        "- No outcome-based comparative winner is declared.",
        "- Corrected historical performance does not establish future predictive ability.",
        "",
    ]
    return "\n".join(lines)


def generate_shadow_handoff(
    *,
    training_path: Path = DEFAULT_TRAINING_PATH,
    prediction_input_path: Path = DEFAULT_PREDICTION_INPUT_PATH,
    outcome_path: Path | None = DEFAULT_OUTCOME_PATH,
    availability_index_path: Path = DEFAULT_AVAILABILITY_INDEX_PATH,
    availability_manifest_path: Path = DEFAULT_AVAILABILITY_MANIFEST_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
    source_git_commit: str,
    generated_at_utc: str | None = None,
    execution_command: str | None = None,
) -> dict[str, Any]:
    """Generate the separate P278 CSV, manifest, and Markdown summary."""
    training_path = Path(training_path)
    prediction_input_path = Path(prediction_input_path)
    outcome_path = Path(outcome_path) if outcome_path is not None else None
    availability_index_path = Path(availability_index_path)
    availability_manifest_path = Path(availability_manifest_path)
    out_dir = Path(out_dir)
    if not source_git_commit or not str(source_git_commit).strip():
        raise ValueError("source_git_commit must be explicit")

    baseline_hash_before = _sha256_file(prediction_input_path)
    refit = refit_selected_model(training_path)
    prediction_rows, prediction_metadata = load_prediction_inputs(prediction_input_path)
    outcome_rows, outcome_metadata = _index_outcome_rows(outcome_path)
    record_count, evidence_status = _availability_record_count(
        availability_index_path, availability_manifest_path
    )

    date_batches = _group_prediction_dates(prediction_rows)
    state_updates = GateAccounting()
    applied_dates: set[str] = set()
    attempted_date_as_of_pairs: set[tuple[str, str]] = set()
    shadow_rows: list[dict[str, Any]] = []
    prior_batches: list[tuple[str, list[dict[str, Any]]]] = []

    for game_date, batch in date_batches:
        complete_date_as_of = _complete_date_as_of(batch)
        if complete_date_as_of is not None:
            _gate_pending_date_batches(
                state=refit.state,
                prior_batches=prior_batches,
                outcome_rows=outcome_rows,
                feature_as_of_utc=complete_date_as_of,
                index_path=availability_index_path,
                manifest_path=availability_manifest_path,
                accounting=state_updates,
                applied_dates=applied_dates,
                attempted_date_as_of_pairs=attempted_date_as_of_pairs,
            )
        prior_update_applied = bool(state_updates.applied_game_ids)
        state_mode = GATED_STATE_MODE if prior_update_applied else FROZEN_STATE_MODE
        for row in batch:
            probability = refit.state.team_history_smooth_probability(
                row["home_team"], row["away_team"]
            )
            shadow_rows.append(
                {
                    "game_id": row["game_id"],
                    "game_date": game_date,
                    "away_team": row["away_team"],
                    "home_team": row["home_team"],
                    "shadow_home_win_probability": round(probability, 6),
                    "predicted_side": "HOME" if probability >= 0.5 else "AWAY",
                    "model_id": MODEL_ID,
                    "model_version": MODEL_VERSION,
                    "source_input_identity": (
                        f"{row['source_prediction_version']}:{row['game_id']}"
                    ),
                    "source_prediction_version": row["source_prediction_version"],
                    "state_mode": state_mode,
                    "feature_as_of_utc": row["feature_as_of_utc"] or "",
                    "prior_outcome_update_applied": prior_update_applied,
                    "outcome_evaluation_gate_available": False,
                    "provenance_reference": PROVENANCE_REFERENCE,
                    "paper_only": True,
                    "diagnostic_only": True,
                    "retrospectively_generated": True,
                    "production_ready": False,
                }
            )
        prior_batches.append((game_date, batch))

    evaluation, evaluation_gate = _evaluate_predictions(
        prediction_rows=prediction_rows,
        shadow_rows=shadow_rows,
        outcome_rows=outcome_rows,
        index_path=availability_index_path,
        manifest_path=availability_manifest_path,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / CSV_FILENAME
    manifest_path = out_dir / MANIFEST_FILENAME
    summary_path = out_dir / SUMMARY_FILENAME
    _write_predictions_csv(shadow_rows, csv_path)

    candidate_ids = {
        game_id
        for game_id, row in outcome_rows.items()
        if row.get("outcome_available") is True
    }
    model_provenance = _model_provenance()
    baseline_hash_after = _sha256_file(prediction_input_path)
    runtime_metadata = {
        "generated_at_utc": generated_at_utc or _runtime_timestamp(),
        "execution_command": execution_command or GENERATOR_VERSION,
        "execution_output_root": _portable_path(out_dir),
    }
    manifest: dict[str, Any] = {
        "task": "P278-A corrected Moneyline PIT-safe local shadow handoff",
        "artifact_version": ARTIFACT_VERSION,
        "scope": "RETROSPECTIVE_LOCAL_PAPER_DIAGNOSTIC_ONLY",
        "paper_only": True,
        "diagnostic_only": True,
        "live_publication": False,
        "pregame_publication_verified": False,
        "production_ready": False,
        "source_git_commit": str(source_git_commit).strip(),
        "generation": {
            "generator_version": GENERATOR_VERSION,
            "runtime_metadata": runtime_metadata,
        },
        "model": {
            "algorithm": ALGORITHM_NAME,
            "model_id": MODEL_ID,
            "model_version": MODEL_VERSION,
            **model_provenance,
        },
        "training": refit.metadata,
        "prediction_input": prediction_metadata,
        "outcome_input": outcome_metadata,
        "state_mode": (
            GATED_STATE_MODE if state_updates.applied_game_ids else FROZEN_STATE_MODE
        ),
        "p275_policy": STATE_UPDATE_POLICY,
        "availability_evidence": {
            "index_path": _portable_path(availability_index_path),
            "manifest_path": _portable_path(availability_manifest_path),
            "index_fingerprint": _sha256_file(availability_index_path),
            "manifest_fingerprint": _sha256_file(availability_manifest_path),
            "verification_status": evidence_status,
            "record_count": record_count,
            "coverage_limitation": P274_COVERAGE_LIMITATION,
        },
        "p275_state_updates": {
            **state_updates.to_dict(),
            "applied": len(state_updates.applied_game_ids),
            "raw_outcome_available_candidate_rows": len(candidate_ids),
            "candidate_rows_not_attempted": len(
                candidate_ids - state_updates.attempted_game_ids
            ),
            "raw_outcome_flag_alone_can_update_state": False,
            "missing_as_of_policy": "FREEZE_AND_DO_NOT_INVOKE_OUTCOME_UPDATE",
        },
        "outcome_evaluation_gate": evaluation_gate.to_dict(),
        "outcome_evaluation": evaluation,
        "baseline_separation": {
            "baseline_source_version": BASELINE_SOURCE_VERSION,
            "baseline_prediction_path": _portable_path(prediction_input_path),
            "baseline_sha256_before": baseline_hash_before,
            "baseline_sha256_after": baseline_hash_after,
            "baseline_byte_unchanged": baseline_hash_before == baseline_hash_after,
            "baseline_replaced": False,
            "champion_activated": False,
        },
        "artifacts": {
            "predictions_csv": f"report/{CSV_FILENAME}",
            "manifest_json": f"report/{MANIFEST_FILENAME}",
            "summary_markdown": f"report/{SUMMARY_FILENAME}",
            "prediction_row_count": len(shadow_rows),
            "predictions_csv_sha256": _sha256_file(csv_path),
        },
        "limitations": [
            P274_COVERAGE_LIMITATION,
            "No committed prediction row has a trustworthy explicit row-level as-of.",
            "Frozen-state predictions are retrospective local diagnostics, not live evidence.",
            "Corrected historical performance does not establish future predictive ability.",
        ],
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(render_summary(manifest), encoding="utf-8")
    return {
        "manifest": manifest,
        "predictions": shadow_rows,
        "paths": {
            "predictions_csv": csv_path,
            "manifest_json": manifest_path,
            "summary_markdown": summary_path,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the P278-A retrospective paper-only Moneyline shadow handoff."
    )
    parser.add_argument("--training-path", default=str(DEFAULT_TRAINING_PATH))
    parser.add_argument(
        "--prediction-input-path", default=str(DEFAULT_PREDICTION_INPUT_PATH)
    )
    parser.add_argument("--outcome-path", default=str(DEFAULT_OUTCOME_PATH))
    parser.add_argument(
        "--availability-index-path", default=str(DEFAULT_AVAILABILITY_INDEX_PATH)
    )
    parser.add_argument(
        "--availability-manifest-path",
        default=str(DEFAULT_AVAILABILITY_MANIFEST_PATH),
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--source-git-commit", required=True)
    args = parser.parse_args(argv)
    effective_args = sys.argv[1:] if argv is None else argv
    execution_command = shlex.join(
        [
            "python3",
            "-m",
            "wbc_backend.recommendation.moneyline_shadow_prediction",
            *effective_args,
        ]
    )
    result = generate_shadow_handoff(
        training_path=Path(args.training_path),
        prediction_input_path=Path(args.prediction_input_path),
        outcome_path=Path(args.outcome_path) if args.outcome_path else None,
        availability_index_path=Path(args.availability_index_path),
        availability_manifest_path=Path(args.availability_manifest_path),
        out_dir=Path(args.out_dir),
        source_git_commit=args.source_git_commit,
        execution_command=execution_command,
    )
    manifest = result["manifest"]
    print(
        "P278A_SHADOW_GENERATED "
        f"rows={manifest['artifacts']['prediction_row_count']} "
        f"state_mode={manifest['state_mode']} "
        f"evaluation_n={manifest['outcome_evaluation']['outcome_evaluation_denominator']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
