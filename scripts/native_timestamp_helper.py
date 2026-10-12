#!/usr/bin/env python3
"""
Native Timestamp Helper — Phase 6R
=====================================
Reusable timestamp capture helper for ML model output pipelines.

Captures real system-clock timestamps at each stage of the inference
pipeline and exposes them as the 9 required native fields (Phase 6J +
Phase 6O) validated by the M13_NATIVE_TIMESTAMP_CONTRACT gate.

Timing invariant enforced:
  started <= feature_cutoff <= prediction <= completed <= written

All timestamps are real datetime.now(timezone.utc) values.
No fake or backfilled timestamps are ever produced by this module.

Phase 6P validator — allowed prediction_time_source values:
  "MODEL_INFERENCE_RUNTIME"       ← used for system-clock inference time
  "MODEL_OUTPUT_EMISSION_RUNTIME" ← used when odds snapshot drives timing
  "SCHEDULER_RUN_RUNTIME"         ← used for scheduled batch runs
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

# ── Module constants (Phase 6P–approved values) ───────────────────────────────

TIMESTAMP_CAPTURE_VERSION: str = "6R-1.0"
PREDICTION_TIME_SOURCE: str = "MODEL_INFERENCE_RUNTIME"
FEATURE_CUTOFF_SOURCE_DEFAULT: str = "MLB_SCHEDULE_LOAD_TIME"


# ── Internal helper ───────────────────────────────────────────────────────────

def _fmt_utc(dt: datetime) -> str:
    """Format a UTC datetime as ISO 8601 Zulu string (second precision)."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Main helper class ─────────────────────────────────────────────────────────

class NativeTimestampCapture:
    """
    Stateful helper that records real system-clock timestamps at each stage
    of the ML inference pipeline.

    Call the stage methods in order, then call ``to_fields()`` to retrieve
    the complete dict of 9 native timestamp fields ready to merge into an
    output row.

    Typical usage::

        cap = NativeTimestampCapture()
        cap.start()
        # ... load feature store ...
        cap.feature_loaded(source="MLB_SCHEDULE_LOAD_TIME")
        # ... run model.predict() ...
        cap.prediction_made()

        # Build rows — embed early_fields() into each row:
        for game in games:
            row = {**base_fields(game), **cap.early_fields()}
            rows.append(row)

        cap.run_completed()
        for row in rows:
            row["prediction_run_completed_at_utc"] = cap.run_completed_at_str()

        cap.output_written()
        for row in rows:
            row["model_output_written_at_utc"] = cap.output_written_at_str()

        violations = cap.validate_chain()  # assert violations == []
        # ... write file ...
    """

    def __init__(self) -> None:
        self._run_started_at: Optional[datetime] = None
        self._feature_cutoff_time: Optional[datetime] = None
        self._prediction_time: Optional[datetime] = None
        self._run_completed_at: Optional[datetime] = None
        self._output_written_at: Optional[datetime] = None
        self._feature_cutoff_source: str = FEATURE_CUTOFF_SOURCE_DEFAULT
        self._timestamp_quality_flags: list[str] = []

    # ── Stage capture methods (call in order) ─────────────────────────────────

    def start(self) -> "NativeTimestampCapture":
        """Stage 1: Record pipeline start time."""
        self._run_started_at = datetime.now(timezone.utc)
        return self

    def feature_loaded(
        self,
        source: str = FEATURE_CUTOFF_SOURCE_DEFAULT,
    ) -> "NativeTimestampCapture":
        """Stage 2: Record time immediately after feature data is loaded."""
        self._feature_cutoff_time = datetime.now(timezone.utc)
        self._feature_cutoff_source = source
        return self

    def prediction_made(self) -> "NativeTimestampCapture":
        """Stage 3: Record time at model inference."""
        self._prediction_time = datetime.now(timezone.utc)
        return self

    def run_completed(self) -> "NativeTimestampCapture":
        """Stage 4: Record time after all rows are built."""
        self._run_completed_at = datetime.now(timezone.utc)
        return self

    def output_written(self) -> "NativeTimestampCapture":
        """Stage 5: Record time immediately before file write."""
        self._output_written_at = datetime.now(timezone.utc)
        return self

    # ── String accessors (for post-build timestamp updates) ───────────────────

    def run_started_at_str(self) -> Optional[str]:
        """ISO8601 string for run_started_at, or None if not yet captured."""
        return _fmt_utc(self._run_started_at) if self._run_started_at else None

    def feature_cutoff_time_utc_str(self) -> Optional[str]:
        """ISO8601 string for feature_cutoff_time_utc, or None if not yet captured."""
        return _fmt_utc(self._feature_cutoff_time) if self._feature_cutoff_time else None

    def prediction_time_utc_str(self) -> Optional[str]:
        """ISO8601 string for prediction_time_utc, or None if not yet captured."""
        return _fmt_utc(self._prediction_time) if self._prediction_time else None

    def run_completed_at_str(self) -> Optional[str]:
        """ISO8601 string for prediction_run_completed_at_utc, or None if not yet captured."""
        return _fmt_utc(self._run_completed_at) if self._run_completed_at else None

    def output_written_at_str(self) -> Optional[str]:
        """ISO8601 string for model_output_written_at_utc, or None if not yet captured."""
        return _fmt_utc(self._output_written_at) if self._output_written_at else None

    # ── Field builders ────────────────────────────────────────────────────────

    def early_fields(self) -> dict:
        """
        Return the 9 native timestamp fields available after Stage 3.

        ``prediction_run_completed_at_utc`` and ``model_output_written_at_utc``
        are None at this point and must be filled in via Stage 4/5 calls.
        Suitable for embedding into rows during initial construction.
        """
        return {
            "prediction_run_started_at_utc": self.run_started_at_str(),
            "feature_cutoff_time_utc": self.feature_cutoff_time_utc_str(),
            "prediction_time_utc": self.prediction_time_utc_str(),
            "prediction_run_completed_at_utc": None,   # filled after run_completed()
            "model_output_written_at_utc": None,        # filled after output_written()
            "prediction_time_source": PREDICTION_TIME_SOURCE,
            "feature_cutoff_source": self._feature_cutoff_source,
            "timestamp_capture_version": TIMESTAMP_CAPTURE_VERSION,
            "timestamp_quality_flags": list(self._timestamp_quality_flags),
        }

    def to_fields(self) -> dict:
        """
        Return all 9 native timestamp fields once all 5 stages are complete.

        Raises ``ValueError`` if any stage has not been captured yet.
        Use this for validation or final row assembly.
        """
        pending = []
        for attr, label in [
            ("_run_started_at", "start()"),
            ("_feature_cutoff_time", "feature_loaded()"),
            ("_prediction_time", "prediction_made()"),
            ("_run_completed_at", "run_completed()"),
            ("_output_written_at", "output_written()"),
        ]:
            if getattr(self, attr) is None:
                pending.append(label)
        if pending:
            raise ValueError(
                f"NativeTimestampCapture: stages not yet called: {pending}"
            )
        return {
            "prediction_run_started_at_utc": _fmt_utc(self._run_started_at),  # type: ignore[arg-type]
            "feature_cutoff_time_utc": _fmt_utc(self._feature_cutoff_time),  # type: ignore[arg-type]
            "prediction_time_utc": _fmt_utc(self._prediction_time),  # type: ignore[arg-type]
            "prediction_run_completed_at_utc": _fmt_utc(self._run_completed_at),  # type: ignore[arg-type]
            "model_output_written_at_utc": _fmt_utc(self._output_written_at),  # type: ignore[arg-type]
            "prediction_time_source": PREDICTION_TIME_SOURCE,
            "feature_cutoff_source": self._feature_cutoff_source,
            "timestamp_capture_version": TIMESTAMP_CAPTURE_VERSION,
            "timestamp_quality_flags": list(self._timestamp_quality_flags),
        }

    # ── Timing invariant validation ───────────────────────────────────────────

    def validate_chain(self) -> list[str]:
        """
        Verify the full timing invariant chain:
          started <= feature_cutoff <= prediction <= completed <= written

        Returns a list of violation strings.
        An empty list means all invariants are satisfied.
        """
        violations: list[str] = []
        ts = self._run_started_at
        fc = self._feature_cutoff_time
        pt = self._prediction_time
        rc = self._run_completed_at
        ow = self._output_written_at

        if ts and fc and ts > fc:
            violations.append(
                f"CHAIN_FAIL: started > feature_cutoff "
                f"({_fmt_utc(ts)} > {_fmt_utc(fc)})"
            )
        if ts and pt and ts > pt:
            violations.append(
                f"CHAIN_FAIL: started > prediction "
                f"({_fmt_utc(ts)} > {_fmt_utc(pt)})"
            )
        if fc and pt and fc > pt:
            violations.append(
                f"CHAIN_FAIL: feature_cutoff > prediction "
                f"({_fmt_utc(fc)} > {_fmt_utc(pt)})"
            )
        if pt and rc and pt > rc:
            violations.append(
                f"CHAIN_FAIL: prediction > completed "
                f"({_fmt_utc(pt)} > {_fmt_utc(rc)})"
            )
        if rc and ow and rc > ow:
            violations.append(
                f"CHAIN_FAIL: completed > written "
                f"({_fmt_utc(rc)} > {_fmt_utc(ow)})"
            )
        return violations
