"""Outcome-free divergence baseline for P84-B and P278 Moneyline predictions.

The comparison deliberately projects each source onto game identity, teams, date,
model provenance, and home-win probability before doing any work. Extra fields --
including outcomes, scores, availability, settlement, and odds -- are ignored and
cannot influence either the ledger or its deterministic summary fingerprint.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_P84B_PATH = (
    REPO_ROOT / "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl"
)
DEFAULT_P278_PATH = REPO_ROOT / "report/mlb_2026_corrected_moneyline_shadow_predictions.csv"
DEFAULT_P278_MANIFEST_PATH = (
    REPO_ROOT / "report/mlb_2026_corrected_moneyline_shadow_manifest.json"
)
DEFAULT_OUT_DIR = REPO_ROOT / "report"

COMPARISON_VERSION = "p279a.moneyline_shadow_divergence.v1"
SCHEMA_VERSION = "p279a.moneyline_shadow_divergence.schema.v1"
P84B_MODEL_ID = "p84b_moneyline_diagnostic_baseline"
EXPECTED_P84B_VERSION = "p84b_diagnostic_baseline_v1"
EXPECTED_P278_VERSION = "p278a_corrected_moneyline_shadow_v1"
THRESHOLDS = (0.02, 0.05, 0.10)
PERCENTILE_METHOD = (
    "R-7 linear interpolation: h=(n-1)*q, interpolate between floor(h) and ceil(h)"
)

LEDGER_FIELDS = (
    "game_id",
    "game_date",
    "away_team",
    "home_team",
    "p84b_model_id",
    "p84b_model_version",
    "p278_model_id",
    "p278_model_version",
    "p84b_home_win_probability",
    "p278_home_win_probability",
    "signed_probability_delta",
    "absolute_probability_delta",
    "p84b_predicted_side",
    "p278_predicted_side",
    "side_agreement",
    "side_disagreement",
    "p84b_confidence_distance_from_0_5",
    "p278_confidence_distance_from_0_5",
    "confidence_change",
    "material_difference_bucket",
    "abs_delta_ge_0_02",
    "abs_delta_ge_0_05",
    "abs_delta_ge_0_10",
    "p84b_source_artifact_fingerprint",
    "p278_source_artifact_fingerprint",
    "comparison_version",
)


@dataclass(frozen=True)
class NormalizedPrediction:
    game_id: str
    game_date: str
    away_team: str
    home_team: str
    model_id: str
    model_version: str
    home_win_probability: float
    predicted_side: str

    def fingerprint_row(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "game_date": self.game_date,
            "away_team": self.away_team,
            "home_team": self.home_team,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "home_win_probability": self.home_win_probability,
            "predicted_side": self.predicted_side,
        }


def _require_text(row: dict[str, Any], key: str, *, source: str) -> str:
    value = row.get(key)
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError(f"missing required {source} field {key!r}")
    return text


def _probability(value: Any, *, field: str, game_id: str) -> float:
    try:
        probability = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field} for {game_id}: {value!r}") from exc
    if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
        raise ValueError(f"{field} outside [0,1] for {game_id}: {value!r}")
    return probability


def _side(value: Any, *, probability: float, game_id: str, source: str) -> str:
    side = str(value or "").strip().upper()
    if side not in {"HOME", "AWAY"}:
        raise ValueError(f"invalid {source} predicted side for {game_id}: {value!r}")
    expected = "HOME" if probability >= 0.5 else "AWAY"
    if side != expected:
        raise ValueError(
            f"{source} side/probability orientation mismatch for {game_id}: "
            f"side={side}, home_win_probability={probability}"
        )
    return side


def _validate_game_identity(prediction: NormalizedPrediction, *, source: str) -> None:
    if prediction.home_team.casefold() == prediction.away_team.casefold():
        raise ValueError(f"invalid {source} teams for {prediction.game_id}: home equals away")
    try:
        datetime.strptime(prediction.game_date, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(
            f"invalid {source} game_date for {prediction.game_id}: "
            f"{prediction.game_date!r}"
        ) from exc


def _index_unique(
    rows: Iterable[NormalizedPrediction], *, source: str
) -> dict[str, NormalizedPrediction]:
    indexed: dict[str, NormalizedPrediction] = {}
    duplicates: list[str] = []
    for row in rows:
        _validate_game_identity(row, source=source)
        if row.game_id in indexed:
            duplicates.append(row.game_id)
        else:
            indexed[row.game_id] = row
    if duplicates:
        duplicate_ids = sorted(set(duplicates))
        raise ValueError(
            f"duplicate game IDs in {source}: count={len(duplicate_ids)}, "
            f"ids={duplicate_ids[:10]}"
        )
    return indexed


def load_p84b_predictions(path: Path) -> dict[str, NormalizedPrediction]:
    """Load only the outcome-free P84-B comparison projection."""
    rows: list[NormalizedPrediction] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid P84-B JSON at line {line_number}") from exc
            game_id = _require_text(raw, "game_id", source="P84-B")
            probability = _probability(
                raw.get("model_probability"),
                field="P84-B model_probability",
                game_id=game_id,
            )
            version = _require_text(raw, "source_prediction_version", source="P84-B")
            if version != EXPECTED_P84B_VERSION:
                raise ValueError(f"unexpected P84-B version for {game_id}: {version!r}")
            rows.append(
                NormalizedPrediction(
                    game_id=game_id,
                    game_date=_require_text(raw, "game_date", source="P84-B"),
                    away_team=_require_text(raw, "away_team", source="P84-B"),
                    home_team=_require_text(raw, "home_team", source="P84-B"),
                    model_id=P84B_MODEL_ID,
                    model_version=version,
                    home_win_probability=probability,
                    predicted_side=_side(
                        raw.get("predicted_side"),
                        probability=probability,
                        game_id=game_id,
                        source="P84-B",
                    ),
                )
            )
    return _index_unique(rows, source="P84-B")


def load_p278_predictions(path: Path) -> dict[str, NormalizedPrediction]:
    """Load only the outcome-free P278 comparison projection."""
    rows: list[NormalizedPrediction] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("P278 CSV is missing a header")
        required = {
            "game_id",
            "game_date",
            "away_team",
            "home_team",
            "shadow_home_win_probability",
            "predicted_side",
            "model_id",
            "model_version",
        }
        missing = sorted(required - set(reader.fieldnames))
        if missing:
            raise ValueError(f"P278 CSV missing required columns: {missing}")
        for raw in reader:
            game_id = _require_text(raw, "game_id", source="P278")
            probability = _probability(
                raw.get("shadow_home_win_probability"),
                field="P278 shadow_home_win_probability",
                game_id=game_id,
            )
            version = _require_text(raw, "model_version", source="P278")
            if version != EXPECTED_P278_VERSION:
                raise ValueError(f"unexpected P278 version for {game_id}: {version!r}")
            rows.append(
                NormalizedPrediction(
                    game_id=game_id,
                    game_date=_require_text(raw, "game_date", source="P278"),
                    away_team=_require_text(raw, "away_team", source="P278"),
                    home_team=_require_text(raw, "home_team", source="P278"),
                    model_id=_require_text(raw, "model_id", source="P278"),
                    model_version=version,
                    home_win_probability=probability,
                    predicted_side=_side(
                        raw.get("predicted_side"),
                        probability=probability,
                        game_id=game_id,
                        source="P278",
                    ),
                )
            )
    return _index_unique(rows, source="P278")


def _semantic_fingerprint(rows: dict[str, NormalizedPrediction]) -> str:
    projection = [rows[game_id].fingerprint_row() for game_id in sorted(rows)]
    payload = json.dumps(
        projection, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _manifest_provenance(path: Path | None, *, expected_rows: int) -> dict[str, Any] | None:
    if path is None:
        return None
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    if manifest.get("artifact_version") != EXPECTED_P278_VERSION:
        raise ValueError(
            f"unexpected P278 manifest version: {manifest.get('artifact_version')!r}"
        )
    manifest_rows = manifest.get("artifacts", {}).get("prediction_row_count")
    if manifest_rows != expected_rows:
        raise ValueError(
            f"P278 manifest row count mismatch: manifest={manifest_rows}, "
            f"predictions={expected_rows}"
        )
    model = manifest.get("model", {})
    if model.get("model_version") != EXPECTED_P278_VERSION:
        raise ValueError("P278 manifest model version does not match comparison contract")
    projection = {
        "artifact_version": manifest.get("artifact_version"),
        "baseline_source_version": manifest.get("baseline_separation", {}).get(
            "baseline_source_version"
        ),
        "model_id": model.get("model_id"),
        "model_version": model.get("model_version"),
        "prediction_row_count": manifest_rows,
        "state_mode": manifest.get("state_mode"),
    }
    payload = json.dumps(projection, sort_keys=True, separators=(",", ":")).encode()
    return {
        "comparison_projection": projection,
        "comparison_projection_sha256": hashlib.sha256(payload).hexdigest(),
        "p84b_protected_byte_sha256": manifest.get("baseline_separation", {}).get(
            "baseline_sha256_before"
        ),
        "p278_protected_byte_sha256": manifest.get("artifacts", {}).get(
            "predictions_csv_sha256"
        ),
    }


def percentile_r7(values: Sequence[float], q: float) -> float:
    """Return a deterministic R-7 linearly interpolated percentile."""
    if not values:
        raise ValueError("percentile requires at least one value")
    if not 0.0 <= q <= 1.0:
        raise ValueError(f"percentile q outside [0,1]: {q}")
    ordered = sorted(float(value) for value in values)
    h = (len(ordered) - 1) * q
    low = math.floor(h)
    high = math.ceil(h)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (h - low)


def _bucket(absolute_delta: Decimal) -> str:
    if absolute_delta >= Decimal("0.10"):
        return "GE_0_10"
    if absolute_delta >= Decimal("0.05"):
        return "GE_0_05_LT_0_10"
    if absolute_delta >= Decimal("0.02"):
        return "GE_0_02_LT_0_05"
    return "LT_0_02"


def _present(value: float) -> float:
    """Round only values serialized for report presentation."""
    return round(value, 12)


def _rate(numerator: int, denominator: int) -> float:
    return _present(numerator / denominator) if denominator else 0.0


def _metric_summary(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    signed = [float(row["_signed_delta"]) for row in rows]
    absolute = [float(row["_absolute_delta"]) for row in rows]
    agreements = sum(bool(row["side_agreement"]) for row in rows)
    confidence_counts = {
        state: sum(row["confidence_change"] == state for row in rows)
        for state in ("INCREASED", "DECREASED", "UNCHANGED")
    }
    threshold_summary = {}
    for threshold in THRESHOLDS:
        material_count = sum(value >= threshold for value in absolute)
        threshold_summary[f"{threshold:.2f}"] = {
            "count": material_count,
            "rate": _rate(material_count, count),
        }
    return {
        "row_count": count,
        "side_agreement_count": agreements,
        "side_agreement_rate": _rate(agreements, count),
        "side_disagreement_count": count - agreements,
        "side_disagreement_rate": _rate(count - agreements, count),
        "mean_signed_delta": _present(sum(signed) / count) if count else None,
        "mean_absolute_delta": _present(sum(absolute) / count) if count else None,
        "median_absolute_delta": _present(percentile_r7(absolute, 0.50)) if count else None,
        "p90_absolute_delta": _present(percentile_r7(absolute, 0.90)) if count else None,
        "p95_absolute_delta": _present(percentile_r7(absolute, 0.95)) if count else None,
        "maximum_absolute_delta": _present(max(absolute)) if count else None,
        "thresholds": threshold_summary,
        "confidence_change_counts": confidence_counts,
    }


def _logical_path(path: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return Path(path).name


def build_divergence(
    *,
    p84b_path: Path,
    p278_path: Path,
    p278_manifest_path: Path | None = None,
    require_full_alignment: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build an outcome-free ledger and deterministic summary payload."""
    p84b = load_p84b_predictions(Path(p84b_path))
    p278 = load_p278_predictions(Path(p278_path))
    manifest_provenance = _manifest_provenance(
        p278_manifest_path, expected_rows=len(p278)
    )

    p84b_ids = set(p84b)
    p278_ids = set(p278)
    missing_left = sorted(p278_ids - p84b_ids)
    missing_right = sorted(p84b_ids - p278_ids)
    if require_full_alignment and (missing_left or missing_right):
        raise ValueError(
            "prediction game-ID alignment is incomplete: "
            f"missing_p84b={len(missing_left)} {missing_left[:10]}, "
            f"missing_p278={len(missing_right)} {missing_right[:10]}"
        )

    p84b_fingerprint = _semantic_fingerprint(p84b)
    p278_fingerprint = _semantic_fingerprint(p278)
    internal_rows: list[dict[str, Any]] = []
    identity_mismatches: list[str] = []
    for game_id in sorted(p84b_ids & p278_ids, key=lambda gid: (p84b[gid].game_date, gid)):
        left = p84b[game_id]
        right = p278[game_id]
        if (
            left.game_date != right.game_date
            or left.home_team != right.home_team
            or left.away_team != right.away_team
        ):
            identity_mismatches.append(game_id)
            continue
        signed_delta_decimal = Decimal(str(right.home_win_probability)) - Decimal(
            str(left.home_win_probability)
        )
        absolute_delta_decimal = abs(signed_delta_decimal)
        left_confidence_decimal = abs(
            Decimal(str(left.home_win_probability)) - Decimal("0.5")
        )
        right_confidence_decimal = abs(
            Decimal(str(right.home_win_probability)) - Decimal("0.5")
        )
        signed_delta = float(signed_delta_decimal)
        absolute_delta = float(absolute_delta_decimal)
        left_confidence = float(left_confidence_decimal)
        right_confidence = float(right_confidence_decimal)
        if right_confidence_decimal > left_confidence_decimal:
            confidence_change = "INCREASED"
        elif right_confidence_decimal < left_confidence_decimal:
            confidence_change = "DECREASED"
        else:
            confidence_change = "UNCHANGED"
        agreement = left.predicted_side == right.predicted_side
        internal_rows.append(
            {
                "game_id": game_id,
                "game_date": left.game_date,
                "away_team": left.away_team,
                "home_team": left.home_team,
                "p84b_model_id": left.model_id,
                "p84b_model_version": left.model_version,
                "p278_model_id": right.model_id,
                "p278_model_version": right.model_version,
                "p84b_home_win_probability": _present(left.home_win_probability),
                "p278_home_win_probability": _present(right.home_win_probability),
                "signed_probability_delta": _present(signed_delta),
                "absolute_probability_delta": _present(absolute_delta),
                "p84b_predicted_side": left.predicted_side,
                "p278_predicted_side": right.predicted_side,
                "side_agreement": agreement,
                "side_disagreement": not agreement,
                "p84b_confidence_distance_from_0_5": _present(left_confidence),
                "p278_confidence_distance_from_0_5": _present(right_confidence),
                "confidence_change": confidence_change,
                "material_difference_bucket": _bucket(absolute_delta_decimal),
                "abs_delta_ge_0_02": absolute_delta_decimal >= Decimal("0.02"),
                "abs_delta_ge_0_05": absolute_delta_decimal >= Decimal("0.05"),
                "abs_delta_ge_0_10": absolute_delta_decimal >= Decimal("0.10"),
                "p84b_source_artifact_fingerprint": p84b_fingerprint,
                "p278_source_artifact_fingerprint": p278_fingerprint,
                "comparison_version": COMPARISON_VERSION,
                "_signed_delta": signed_delta,
                "_absolute_delta": absolute_delta,
            }
        )

    if identity_mismatches:
        raise ValueError(
            "game identity fields disagree for shared IDs: "
            f"count={len(identity_mismatches)}, ids={identity_mismatches[:10]}"
        )

    overall = _metric_summary(internal_rows)
    month_rows: dict[str, list[dict[str, Any]]] = {}
    for row in internal_rows:
        month_rows.setdefault(str(row["game_date"])[:7], []).append(row)
    monthly = [
        {"month": month, **_metric_summary(month_rows[month])}
        for month in sorted(month_rows)
    ]

    ledger = [
        {field: row[field] for field in LEDGER_FIELDS}
        for row in internal_rows
    ]
    summary = {
        "task": "P279-A Moneyline shadow outcome-free divergence baseline",
        "scope": "OUTCOME_FREE_PAPER_DIAGNOSTIC_ONLY",
        "status": "AVAILABLE_OUTCOME_FREE_DIVERGENCE_BASELINE",
        "schema_version": SCHEMA_VERSION,
        "comparison_version": COMPARISON_VERSION,
        "comparison_contract": {
            "alignment_key": "exact game_id",
            "probability_orientation": "home_win_probability",
            "signed_delta": "P278 - P84-B",
            "material_difference_thresholds": list(THRESHOLDS),
            "material_difference_buckets": [
                "LT_0_02",
                "GE_0_02_LT_0_05",
                "GE_0_05_LT_0_10",
                "GE_0_10",
            ],
            "percentile_method": PERCENTILE_METHOD,
            "input_projection": [
                "game_id",
                "game_date",
                "away_team",
                "home_team",
                "model provenance",
                "home-win probability",
                "predicted side",
            ],
            "outcome_fields_used": "NONE",
            "odds_fields_used": "NONE",
            "evaluation_denominator": 0,
        },
        "source_artifacts": {
            "p84b": {
                "path": _logical_path(Path(p84b_path)),
                "model_id": P84B_MODEL_ID,
                "model_version": EXPECTED_P84B_VERSION,
                "fingerprint_type": "sha256_of_canonical_outcome_free_projection",
                "fingerprint": p84b_fingerprint,
                "protected_byte_sha256_recorded_by_p278_manifest": (
                    manifest_provenance.get("p84b_protected_byte_sha256")
                    if manifest_provenance
                    else None
                ),
            },
            "p278": {
                "path": _logical_path(Path(p278_path)),
                "model_id": next(iter(p278.values())).model_id if p278 else None,
                "model_version": EXPECTED_P278_VERSION,
                "fingerprint_type": "sha256_of_canonical_outcome_free_projection",
                "fingerprint": p278_fingerprint,
                "protected_byte_sha256_recorded_by_p278_manifest": (
                    manifest_provenance.get("p278_protected_byte_sha256")
                    if manifest_provenance
                    else None
                ),
                "manifest_path": (
                    _logical_path(Path(p278_manifest_path))
                    if p278_manifest_path is not None
                    else None
                ),
                "manifest_provenance": manifest_provenance,
            },
        },
        "alignment": {
            "total_p84b_rows": len(p84b),
            "total_p278_rows": len(p278),
            "shared_game_count": len(ledger),
            "missing_p84b_count": len(missing_left),
            "missing_p278_count": len(missing_right),
            "missing_p84b_game_ids": missing_left,
            "missing_p278_game_ids": missing_right,
            "p84b_duplicate_id_count": 0,
            "p278_duplicate_id_count": 0,
            "duplicate_id_count": 0,
            "identity_mismatch_count": 0,
        },
        "divergence_metrics": overall,
        "monthly_breakdown": monthly,
        "claims": {
            "divergence_is_accuracy_or_superiority": False,
            "model_winner_declared": False,
            "champion_activated": False,
            "production_ready": False,
            "paper_only": True,
            "diagnostic_only": True,
            "future_outcome_evaluation_requires_prospective_availability": True,
        },
        "statement": (
            "This report measures prediction divergence only; it is not an accuracy, "
            "performance, calibration, profitability, or model-superiority evaluation."
        ),
        "limitations": [
            "Neither P84-B nor P278 is selected, activated, deployed, or declared superior.",
            "Any future performance evaluation requires prospectively available outcomes.",
            "Outcome, score, availability, odds, settlement, ROI, EV, Kelly, and betting "
            "result fields are outside this comparison contract.",
        ],
    }
    return ledger, summary


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def deterministic_summary_fingerprint(summary: dict[str, Any]) -> str:
    payload = deepcopy(summary)
    payload.pop("runtime_metadata", None)
    payload.pop("output_artifacts", None)
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _write_ledger_csv(rows: Sequence[dict[str, Any]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _utc_now_iso() -> str:
    """Wall clock is used only for truthful runtime metadata, never comparison logic."""
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


def write_divergence_reports(
    *,
    ledger: Sequence[dict[str, Any]],
    summary: dict[str, Any],
    out_dir: Path,
    generated_at_utc: str | None = None,
    source_git_commit: str | None = None,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "mlb_2026_moneyline_shadow_divergence.csv"
    json_path = out_dir / "mlb_2026_moneyline_shadow_divergence_summary.json"
    markdown_path = out_dir / "mlb_2026_moneyline_shadow_divergence_summary.md"

    _write_ledger_csv(ledger, csv_path)
    ledger_sha256 = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    summary_payload_sha256 = deterministic_summary_fingerprint(summary)

    json_payload = deepcopy(summary)
    json_payload["output_artifacts"] = {
        "ledger_csv": _logical_path(csv_path),
        "ledger_csv_sha256": ledger_sha256,
        "ledger_row_count": len(ledger),
        "summary_json": _logical_path(json_path),
        "summary_deterministic_payload_sha256": summary_payload_sha256,
        "summary_markdown": _logical_path(markdown_path),
    }
    json_payload["runtime_metadata"] = {
        "generated_at_utc": generated_at_utc or _utc_now_iso(),
        "source_git_commit": source_git_commit,
        "runtime_metadata_excluded_from_deterministic_fingerprints": True,
    }
    json_path.write_text(
        json.dumps(json_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary_json_sha256 = hashlib.sha256(json_path.read_bytes()).hexdigest()
    markdown_path.write_text(
        render_markdown(json_payload, summary_json_sha256=summary_json_sha256),
        encoding="utf-8",
    )
    return {
        "ledger_csv": csv_path,
        "summary_json": json_path,
        "summary_markdown": markdown_path,
        "ledger_csv_sha256": ledger_sha256,
        "summary_deterministic_payload_sha256": summary_payload_sha256,
        "summary_json_sha256": summary_json_sha256,
    }


def render_markdown(summary: dict[str, Any], *, summary_json_sha256: str) -> str:
    alignment = summary["alignment"]
    metrics = summary["divergence_metrics"]
    outputs = summary["output_artifacts"]
    runtime = summary["runtime_metadata"]
    source = summary["source_artifacts"]
    lines = [
        "# 2026 Moneyline Shadow Outcome-Free Divergence Baseline",
        "",
        "**Scope:** `OUTCOME_FREE_PAPER_DIAGNOSTIC_ONLY`",
        "",
        (
            "This report compares the existing P84-B Moneyline baseline with the P278 "
            "corrected Moneyline shadow. It measures prediction divergence only; it is "
            "not accuracy, performance, profitability, or evidence of model superiority."
        ),
        "",
        "## Comparison Contract",
        "",
        "- Alignment key: exact `game_id` (never row order).",
        "- Probability orientation: home-win probability for both sources.",
        "- Signed delta: `P278 - P84-B`.",
        "- Descriptive thresholds: `0.02`, `0.05`, `0.10` absolute probability delta.",
        f"- Percentiles: {PERCENTILE_METHOD}.",
        "- Outcome fields used: `NONE`.",
        "- Odds fields used: `NONE`.",
        "- Evaluation denominator: `0`.",
        "",
        "## Alignment",
        "",
        f"- Total P84-B rows: `{alignment['total_p84b_rows']}`",
        f"- Total P278 rows: `{alignment['total_p278_rows']}`",
        f"- Shared games: `{alignment['shared_game_count']}`",
        f"- Missing P84-B / P278: `{alignment['missing_p84b_count']}` / "
        f"`{alignment['missing_p278_count']}`",
        f"- Duplicate IDs: `{alignment['duplicate_id_count']}`",
        f"- Identity mismatches: `{alignment['identity_mismatch_count']}`",
        "",
        "## Divergence Summary",
        "",
        f"- Side agreement: `{metrics['side_agreement_count']}` "
        f"(`{metrics['side_agreement_rate']:.2%}`)",
        f"- Side disagreement: `{metrics['side_disagreement_count']}` "
        f"(`{metrics['side_disagreement_rate']:.2%}`)",
        f"- Mean signed delta: `{metrics['mean_signed_delta']:.6f}`",
        f"- Mean absolute delta: `{metrics['mean_absolute_delta']:.6f}`",
        f"- Median / p90 / p95 absolute delta: "
        f"`{metrics['median_absolute_delta']:.6f}` / "
        f"`{metrics['p90_absolute_delta']:.6f}` / "
        f"`{metrics['p95_absolute_delta']:.6f}`",
        f"- Maximum absolute delta: `{metrics['maximum_absolute_delta']:.6f}`",
    ]
    for threshold in ("0.02", "0.05", "0.10"):
        row = metrics["thresholds"][threshold]
        lines.append(
            f"- Absolute delta >= `{threshold}`: `{row['count']}` (`{row['rate']:.2%}`)"
        )
    confidence = metrics["confidence_change_counts"]
    lines.extend(
        [
            "- Confidence distance increased / decreased / unchanged: "
            f"`{confidence['INCREASED']}` / `{confidence['DECREASED']}` / "
            f"`{confidence['UNCHANGED']}`",
            "",
            "## Month-Level Descriptive Breakdown",
            "",
            "| Month | Rows | Agree | Disagree | Mean Signed | Mean Abs | "
            ">=0.02 | >=0.05 | >=0.10 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in summary["monthly_breakdown"]:
        lines.append(
            f"| {row['month']} | {row['row_count']} | {row['side_agreement_count']} | "
            f"{row['side_disagreement_count']} | {row['mean_signed_delta']:.6f} | "
            f"{row['mean_absolute_delta']:.6f} | "
            f"{row['thresholds']['0.02']['count']} | "
            f"{row['thresholds']['0.05']['count']} | "
            f"{row['thresholds']['0.10']['count']} |"
        )
    lines.extend(
        [
            "",
            "## Provenance and Output Fingerprints",
            "",
            f"- P84-B comparison fingerprint: `{source['p84b']['fingerprint']}`",
            f"- P278 comparison fingerprint: `{source['p278']['fingerprint']}`",
            f"- Ledger CSV SHA-256: `{outputs['ledger_csv_sha256']}`",
            "- Deterministic summary payload SHA-256: "
            f"`{outputs['summary_deterministic_payload_sha256']}`",
            f"- Summary JSON file SHA-256: `{summary_json_sha256}`",
            f"- Generated at (runtime metadata only): `{runtime['generated_at_utc']}`",
            f"- Source Git commit (runtime metadata only): `{runtime['source_git_commit']}`",
            "",
            "## Boundary",
            "",
            "- Neither model is activated, selected, deployed, or declared superior.",
            "- Divergence thresholds are descriptive, not performance thresholds.",
            "- Future performance evaluation requires prospectively available outcomes.",
            "- No champion selection, publication, or betting action was performed.",
            "",
        ]
    )
    return "\n".join(lines)


def generate_divergence_reports(
    *,
    p84b_path: Path = DEFAULT_P84B_PATH,
    p278_path: Path = DEFAULT_P278_PATH,
    p278_manifest_path: Path | None = DEFAULT_P278_MANIFEST_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
    generated_at_utc: str | None = None,
    source_git_commit: str | None = None,
) -> dict[str, Any]:
    ledger, summary = build_divergence(
        p84b_path=Path(p84b_path),
        p278_path=Path(p278_path),
        p278_manifest_path=(
            Path(p278_manifest_path) if p278_manifest_path is not None else None
        ),
    )
    return write_divergence_reports(
        ledger=ledger,
        summary=summary,
        out_dir=Path(out_dir),
        generated_at_utc=generated_at_utc,
        source_git_commit=source_git_commit,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the outcome-free P84-B/P278 Moneyline divergence baseline."
    )
    parser.add_argument("--p84b-path", default=str(DEFAULT_P84B_PATH))
    parser.add_argument("--p278-path", default=str(DEFAULT_P278_PATH))
    parser.add_argument("--p278-manifest-path", default=str(DEFAULT_P278_MANIFEST_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--generated-at-utc")
    parser.add_argument("--source-git-commit")
    args = parser.parse_args(argv)
    result = generate_divergence_reports(
        p84b_path=Path(args.p84b_path),
        p278_path=Path(args.p278_path),
        p278_manifest_path=Path(args.p278_manifest_path),
        out_dir=Path(args.out_dir),
        generated_at_utc=args.generated_at_utc,
        source_git_commit=args.source_git_commit,
    )
    print("P279A_OUTCOME_FREE_DIVERGENCE_GENERATED")
    print(f"ledger_rows={sum(1 for _ in csv.DictReader(result['ledger_csv'].open()))}")
    print(f"ledger_sha256={result['ledger_csv_sha256']}")
    print(
        "summary_deterministic_payload_sha256="
        f"{result['summary_deterministic_payload_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
