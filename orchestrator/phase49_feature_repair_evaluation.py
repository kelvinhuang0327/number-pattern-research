"""
Phase 49: Feature Repair Evaluation — Re-run Pipeline with Phase48 P0 Features
===============================================================================
Re-runs the evaluation pipeline comparing baseline predictions against the
phase48-enriched JSONL to determine whether P0 features (F-001, F-002, F-004)
improve the critical failure segments identified in Phase 45.

CRITICAL CHECK — feature_effect_mode:
  REPORT_ONLY      : phase48 model_home_prob == baseline → features not yet
                     injected into the model. Metric deltas must NOT be
                     attributed to features. Next step: Phase 50 Feature
                     Injection.
  MODEL_AFFECTING  : model_home_prob differs → features have altered predictions.
                     Metric deltas can be attributed.

Hard Rules (never violate):
  - CANDIDATE_PATCH_CREATED = False  (always)
  - PRODUCTION_MODIFIED = False      (always)
  - No external API / LLM calls
  - gate NEVER == "PATCH"
  - alpha = 0.4 (never adjusted)
  - REPORT_ONLY → gate = FEATURE_INJECTION_REQUIRED (forced)
  - All metric computation delegates to wbc_backend.evaluation.metrics (SSOT)
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wbc_backend.evaluation.metrics import (
    brier_score,
    brier_skill_score,
    expected_calibration_error,
    log_loss_score,
)
from wbc_backend.evaluation.prediction_persistence import PredictionRow

logger = logging.getLogger(__name__)

# ─── Hard Constants ───────────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False    # NEVER change
PRODUCTION_MODIFIED: bool = False        # NEVER change
ALPHA: float = 0.4                       # Fixed — never adjust
_MIN_SEGMENT_N: int = 30
_PROB_MATCH_TOLERANCE: float = 1e-9     # Tolerance for "same probability"
_VALID_GATES: frozenset[str] = frozenset({
    "FEATURE_INJECTION_REQUIRED",
    "FEATURE_REPAIR_EFFECTIVE_PAPER_ONLY",
    "FEATURE_REPAIR_NOT_EFFECTIVE",
    "COLLECT_MORE_DATA",
})

# Feature effect mode labels
REPORT_ONLY: str = "REPORT_ONLY"
MODEL_AFFECTING: str = "MODEL_AFFECTING"

# Improvement labels
IMPROVED: str = "IMPROVED"
DEGRADED: str = "DEGRADED"
UNCHANGED: str = "UNCHANGED"
NOT_EVALUABLE: str = "NOT_EVALUABLE"

# Feature availability labels
FEATURE_READY_FOR_INJECTION: str = "FEATURE_READY_FOR_INJECTION"
FEATURE_REPORT_ONLY_AVAIL: str = "FEATURE_REPORT_ONLY"
FEATURE_DATA_GAP: str = "FEATURE_DATA_GAP"

# Gate labels (for external import)
FEATURE_INJECTION_REQUIRED: str = "FEATURE_INJECTION_REQUIRED"
FEATURE_REPAIR_EFFECTIVE_PAPER_ONLY: str = "FEATURE_REPAIR_EFFECTIVE_PAPER_ONLY"
FEATURE_REPAIR_NOT_EFFECTIVE: str = "FEATURE_REPAIR_NOT_EFFECTIVE"
COLLECT_MORE_DATA: str = "COLLECT_MORE_DATA"

# ─── Critical segment keys the spec requires ─────────────────────────────────
_REQUIRED_SEGMENT_KEYS: frozenset[str] = frozenset({
    "month:2025-04", "month:2025-05", "month:2025-06", "month:2025-07",
    "odds_bucket:heavy_favorite", "odds_bucket:mid",
    "confidence:high_confidence", "confidence:low_confidence",
    "disagreement:high", "disagreement:low",
})


# ═══════════════════════════════════════════════════════════════════════════════
# § 1  Data Structures
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MetricsSnapshot:
    """Global-level metrics for one JSONL source."""
    source: str          # "baseline" | "phase48" | "market"
    n: int
    brier: float
    bss_vs_market: float
    ece: float
    log_loss: float


@dataclass
class MetricsDelta:
    """Delta between phase48 and baseline metrics."""
    delta_brier: float    # phase48_brier - baseline_brier (negative = better)
    delta_bss: float      # phase48_bss - baseline_bss (positive = better)
    delta_ece: float      # phase48_ece - baseline_ece (negative = better)
    delta_log_loss: float # phase48_log_loss - baseline_log_loss (negative = better)


@dataclass
class SegmentComparison:
    """Per-segment comparison: baseline vs phase48."""
    segment_key: str          # e.g. "month:2025-04"
    segment_type: str         # "month" | "odds_bucket" | "confidence" | "disagreement"
    segment_label: str        # e.g. "2025-04"
    sample_size: int
    baseline_bss: float
    phase48_bss: float
    delta_bss: float
    baseline_ece: float
    phase48_ece: float
    delta_ece: float
    improvement_label: str    # IMPROVED | DEGRADED | UNCHANGED | NOT_EVALUABLE


@dataclass
class FeatureAvailabilitySummary:
    """Availability stats from phase48 p0_features field."""
    total_rows: int
    park_available_count: int
    park_availability_rate: float
    season_idx_available_count: int
    season_idx_availability_rate: float
    sp_fip_available_count: int
    sp_fip_availability_rate: float
    neutral_fallback_rate: float          # fraction with sp_fip_available=False
    feature_audit_hash_present_count: int
    feature_audit_hash_present_rate: float
    feature_availability_label: str      # FEATURE_READY_FOR_INJECTION | FEATURE_REPORT_ONLY | FEATURE_DATA_GAP


@dataclass
class LeakageGuardSummary:
    """Summary of leakage guard activity from p0_features.audit_notes."""
    rows_with_forbidden_triggered: int
    total_rows: int
    forbidden_trigger_rate: float
    most_common_forbidden_field: str
    feature_hash_stable: bool            # True if all hashes are 64-char hex
    note: str


@dataclass
class Phase49EvaluationResult:
    """
    Full Phase 49 evaluation snapshot.

    Hard invariants:
      - candidate_patch_created is always False
      - production_modified is always False
      - gate is always in _VALID_GATES
      - feature_effect_mode in {REPORT_ONLY, MODEL_AFFECTING}
    """
    run_id: str
    generated_at: str
    baseline_path: str
    phase48_path: str
    # Feature effect mode — the most critical field
    feature_effect_mode: str             # REPORT_ONLY | MODEL_AFFECTING
    # Metrics
    baseline_metrics: MetricsSnapshot   = field(default_factory=lambda: MetricsSnapshot("baseline", 0, 0.0, 0.0, 0.0, 0.0))
    phase48_metrics: MetricsSnapshot    = field(default_factory=lambda: MetricsSnapshot("phase48", 0, 0.0, 0.0, 0.0, 0.0))
    market_metrics: MetricsSnapshot     = field(default_factory=lambda: MetricsSnapshot("market", 0, 0.0, 0.0, 0.0, 0.0))
    delta_metrics: MetricsDelta         = field(default_factory=lambda: MetricsDelta(0.0, 0.0, 0.0, 0.0))
    # Segment comparison
    segment_comparisons: list[SegmentComparison] = field(default_factory=list)
    # Feature / leakage summaries
    feature_availability: FeatureAvailabilitySummary = field(
        default_factory=lambda: FeatureAvailabilitySummary(
            0, 0, 0.0, 0, 0.0, 0, 0.0, 1.0, 0, 0.0, FEATURE_REPORT_ONLY_AVAIL
        )
    )
    leakage_guard: LeakageGuardSummary = field(
        default_factory=lambda: LeakageGuardSummary(0, 0, 0.0, "", True, "")
    )
    # Gate
    gate_recommendation: str = "FEATURE_INJECTION_REQUIRED"
    gate_rationale: str = ""
    # Hard-rule flags
    candidate_patch_created: bool = False
    production_modified: bool = False
    # Audit
    audit_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["candidate_patch_created"] = False
        d["production_modified"] = False
        assert d["gate_recommendation"] in _VALID_GATES, (
            f"INVARIANT VIOLATION: gate_recommendation={d['gate_recommendation']!r}"
        )
        return d


# ═══════════════════════════════════════════════════════════════════════════════
# § 2  JSONL Loading
# ═══════════════════════════════════════════════════════════════════════════════

def _load_jsonl(path: Path) -> list[dict]:
    """Load all rows from a JSONL file."""
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _to_prediction_row(d: dict) -> PredictionRow | None:
    """Convert a raw dict to PredictionRow; returns None on failure."""
    def _parse_ml(v: object) -> int | None:
        """Parse moneyline — returns None for empty/null/unparseable values."""
        if v is None or v == "":
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    try:
        return PredictionRow(
            schema_version=d.get("schema_version", "phase39-v1"),
            season=int(d.get("season", 2025)),
            game_date=str(d.get("game_date", "")),
            game_id=str(d.get("game_id", "")),
            dedupe_key=str(d.get("dedupe_key", d.get("game_id", ""))),
            home_team=str(d.get("home_team", "")),
            away_team=str(d.get("away_team", "")),
            home_win=int(d["home_win"]),
            model_home_prob=float(d["model_home_prob"]),
            market_home_prob_no_vig=float(d["market_home_prob_no_vig"]),
            market_away_prob_no_vig=float(d.get("market_away_prob_no_vig", 1.0 - float(d["market_home_prob_no_vig"]))),
            home_ml=_parse_ml(d.get("home_ml")),
            away_ml=_parse_ml(d.get("away_ml")),
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Skipping malformed row %s: %s", d.get("game_id"), exc)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# § 3  Feature Effect Mode Detection
# ═══════════════════════════════════════════════════════════════════════════════

def detect_feature_effect_mode(
    baseline_rows: list[PredictionRow],
    phase48_rows: list[PredictionRow],
) -> tuple[str, int]:
    """
    Determine whether phase48 model_home_prob differs from baseline.

    Returns (mode, mismatch_count) where mode is REPORT_ONLY or MODEL_AFFECTING.

    Methodology:
      - Align rows by game_id
      - Count rows where |phase48_prob - baseline_prob| > _PROB_MATCH_TOLERANCE
      - If mismatch_count == 0 → REPORT_ONLY
      - Else → MODEL_AFFECTING
    """
    baseline_map = {r.game_id: r.model_home_prob for r in baseline_rows}
    mismatch = 0
    matched = 0
    for row in phase48_rows:
        baseline_p = baseline_map.get(row.game_id)
        if baseline_p is None:
            continue
        matched += 1
        if abs(row.model_home_prob - baseline_p) > _PROB_MATCH_TOLERANCE:
            mismatch += 1
    if matched == 0:
        logger.warning("No game_ids matched between baseline and phase48 — defaulting REPORT_ONLY")
        return REPORT_ONLY, 0
    return (MODEL_AFFECTING if mismatch > 0 else REPORT_ONLY), mismatch


# ═══════════════════════════════════════════════════════════════════════════════
# § 4  Bucketing helpers (mirrors Phase 45)
# ═══════════════════════════════════════════════════════════════════════════════

def _odds_bucket(p: float) -> str:
    if p >= 0.65:
        return "heavy_favorite"
    if p >= 0.45:
        return "mid"
    return "underdog"


def _disagreement_bucket(model_p: float, market_p: float) -> str:
    gap = abs(model_p - market_p)
    if gap < 0.05:
        return "low"
    if gap < 0.10:
        return "medium"
    return "high"


def _confidence_bucket(model_p: float) -> str:
    dist = abs(model_p - 0.5)
    if dist >= 0.10:
        return "high_confidence"
    if dist >= 0.05:
        return "mid_confidence"
    return "low_confidence"


def _month_bucket(game_date: str) -> str:
    try:
        return game_date[:7] if game_date and len(game_date) >= 7 else "unknown"
    except (IndexError, TypeError):
        return "unknown"


def _segment_key(seg_type: str, label: str) -> str:
    return f"{seg_type}:{label}"


# ═══════════════════════════════════════════════════════════════════════════════
# § 5  Metric computation helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_metrics(rows: list[PredictionRow], source: str) -> MetricsSnapshot:
    """Compute global metrics for a list of PredictionRows."""
    if not rows:
        return MetricsSnapshot(source, 0, float("nan"), float("nan"), float("nan"), float("nan"))
    model_p = [r.model_home_prob for r in rows]
    market_p = [r.market_home_prob_no_vig for r in rows]
    labels = [r.home_win for r in rows]

    model_brier = brier_score(model_p, labels)
    market_brier = brier_score(market_p, labels)
    bss = brier_skill_score(model_brier, market_brier) or 0.0
    ece = expected_calibration_error(model_p, labels)["ece"]
    ll = log_loss_score(model_p, labels)

    return MetricsSnapshot(
        source=source,
        n=len(rows),
        brier=round(model_brier, 6),
        bss_vs_market=round(bss, 6),
        ece=round(ece, 6),
        log_loss=round(ll, 6),
    )


def _compute_segment_metrics(
    rows: list[PredictionRow],
    source: str,
) -> dict[str, dict]:
    """
    Compute per-segment BSS and ECE for one JSONL source.

    Returns dict: segment_key → {"bss": float, "ece": float, "n": int}
    """
    groups: dict[str, list[PredictionRow]] = {}

    for row in rows:
        keys = [
            _segment_key("odds_bucket", _odds_bucket(row.market_home_prob_no_vig)),
            _segment_key("disagreement", _disagreement_bucket(row.model_home_prob, row.market_home_prob_no_vig)),
            _segment_key("confidence", _confidence_bucket(row.model_home_prob)),
            _segment_key("month", _month_bucket(row.game_date)),
        ]
        for k in keys:
            groups.setdefault(k, []).append(row)

    result: dict[str, dict] = {}
    for seg_key, seg_rows in groups.items():
        n = len(seg_rows)
        model_p = [r.model_home_prob for r in seg_rows]
        market_p = [r.market_home_prob_no_vig for r in seg_rows]
        labels = [r.home_win for r in seg_rows]

        mb = brier_score(model_p, labels)
        mkt_b = brier_score(market_p, labels)
        bss = brier_skill_score(mb, mkt_b) or 0.0
        ece = expected_calibration_error(model_p, labels)["ece"] if n >= _MIN_SEGMENT_N else float("nan")
        result[seg_key] = {"bss": round(bss, 6), "ece": round(ece, 6) if not math.isnan(ece) else float("nan"), "n": n}

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# § 6  Segment comparison
# ═══════════════════════════════════════════════════════════════════════════════

def _improvement_label(delta_bss: float, n: int) -> str:
    """Classify segment-level improvement."""
    if n < _MIN_SEGMENT_N:
        return NOT_EVALUABLE
    if abs(delta_bss) < 0.001:  # < 0.1% change
        return UNCHANGED
    return IMPROVED if delta_bss > 0 else DEGRADED


def build_segment_comparisons(
    baseline_segs: dict[str, dict],
    phase48_segs: dict[str, dict],
) -> list[SegmentComparison]:
    """
    Build SegmentComparison for every segment that appears in either source.
    Required segments from spec are included even if data is absent (NOT_EVALUABLE).
    """
    all_keys = set(baseline_segs.keys()) | set(phase48_segs.keys()) | _REQUIRED_SEGMENT_KEYS
    comparisons: list[SegmentComparison] = []

    for seg_key in sorted(all_keys):
        # Parse segment_key: "type:label"
        parts = seg_key.split(":", 1)
        seg_type = parts[0] if len(parts) == 2 else "unknown"
        seg_label = parts[1] if len(parts) == 2 else seg_key

        b_data = baseline_segs.get(seg_key, {"bss": float("nan"), "ece": float("nan"), "n": 0})
        p_data = phase48_segs.get(seg_key, {"bss": float("nan"), "ece": float("nan"), "n": 0})

        n = max(b_data["n"], p_data["n"])  # use whichever source has more data

        b_bss = b_data["bss"]
        p_bss = p_data["bss"]
        b_ece = b_data["ece"]
        p_ece = p_data["ece"]

        delta_bss = (p_bss - b_bss) if not (math.isnan(p_bss) or math.isnan(b_bss)) else float("nan")
        delta_ece = (p_ece - b_ece) if not (math.isnan(p_ece) or math.isnan(b_ece)) else float("nan")

        imp = _improvement_label(delta_bss if not math.isnan(delta_bss) else 0.0, n)
        if n == 0:
            imp = NOT_EVALUABLE

        comparisons.append(SegmentComparison(
            segment_key=seg_key,
            segment_type=seg_type,
            segment_label=seg_label,
            sample_size=n,
            baseline_bss=b_bss,
            phase48_bss=p_bss,
            delta_bss=delta_bss if not math.isnan(delta_bss) else 0.0,
            baseline_ece=b_ece,
            phase48_ece=p_ece,
            delta_ece=delta_ece if not math.isnan(delta_ece) else 0.0,
            improvement_label=imp,
        ))

    return comparisons


# ═══════════════════════════════════════════════════════════════════════════════
# § 7  Feature availability & leakage guard summaries
# ═══════════════════════════════════════════════════════════════════════════════

def build_feature_availability_summary(phase48_raw: list[dict]) -> FeatureAvailabilitySummary:
    """Extract availability stats from p0_features inside phase48 JSONL rows."""
    n = len(phase48_raw)
    park_avail = 0
    season_avail = 0
    sp_avail = 0
    hash_present = 0

    for row in phase48_raw:
        pf = row.get("p0_features", {})
        if pf.get("park_factor_available"):
            park_avail += 1
        if pf.get("season_game_index_available"):
            season_avail += 1
        if pf.get("sp_fip_delta_available"):
            sp_avail += 1
        h = pf.get("feature_audit_hash", "")
        if isinstance(h, str) and len(h) == 64:
            hash_present += 1

    def _rate(count: int) -> float:
        return round(count / n, 6) if n > 0 else 0.0

    sp_rate = _rate(sp_avail)
    park_rate = _rate(park_avail)
    neutral_fallback_rate = round(1.0 - sp_rate, 6)

    # Feature availability label
    if park_rate >= 0.99 and _rate(season_avail) >= 0.99:
        avail_label = FEATURE_READY_FOR_INJECTION
    elif sp_rate == 0.0:
        avail_label = FEATURE_REPORT_ONLY_AVAIL
    else:
        avail_label = FEATURE_DATA_GAP

    return FeatureAvailabilitySummary(
        total_rows=n,
        park_available_count=park_avail,
        park_availability_rate=park_rate,
        season_idx_available_count=season_avail,
        season_idx_availability_rate=_rate(season_avail),
        sp_fip_available_count=sp_avail,
        sp_fip_availability_rate=sp_rate,
        neutral_fallback_rate=neutral_fallback_rate,
        feature_audit_hash_present_count=hash_present,
        feature_audit_hash_present_rate=_rate(hash_present),
        feature_availability_label=avail_label,
    )


def build_leakage_guard_summary(phase48_raw: list[dict]) -> LeakageGuardSummary:
    """Summarise leakage guard activity from audit_notes."""
    n = len(phase48_raw)
    triggered = 0
    field_counts: dict[str, int] = {}
    all_hashes_valid = True

    for row in phase48_raw:
        pf = row.get("p0_features", {})
        an = pf.get("audit_notes", {})
        ignored = an.get("ignored_forbidden_fields", [])
        if ignored:
            triggered += 1
            for f in ignored:
                field_counts[f] = field_counts.get(f, 0) + 1
        h = pf.get("feature_audit_hash", "")
        if not (isinstance(h, str) and len(h) == 64):
            all_hashes_valid = False

    most_common = max(field_counts, key=lambda k: field_counts[k]) if field_counts else ""

    return LeakageGuardSummary(
        rows_with_forbidden_triggered=triggered,
        total_rows=n,
        forbidden_trigger_rate=round(triggered / n, 6) if n > 0 else 0.0,
        most_common_forbidden_field=most_common,
        feature_hash_stable=all_hashes_valid,
        note=(
            f"{most_common!r} intercepted in {field_counts.get(most_common, 0)} rows; "
            "zero feature impact confirmed."
            if most_common else "No forbidden fields triggered."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 8  Gate recommendation
# ═══════════════════════════════════════════════════════════════════════════════

def _decide_gate(
    feature_effect_mode: str,
    baseline_m: MetricsSnapshot,
    phase48_m: MetricsSnapshot,
    seg_comparisons: list[SegmentComparison],
) -> tuple[str, str]:
    """
    Decide gate_recommendation and rationale.

    Phase 49 gate rules:
    - REPORT_ONLY → FEATURE_INJECTION_REQUIRED (forced, no metric attribution)
    - MODEL_AFFECTING + conditions met → FEATURE_REPAIR_EFFECTIVE_PAPER_ONLY
    - MODEL_AFFECTING + not improved → FEATURE_REPAIR_NOT_EFFECTIVE
    - Insufficient sample → COLLECT_MORE_DATA
    """
    # REPORT_ONLY always forces injection required, regardless of sample size
    if feature_effect_mode == REPORT_ONLY:
        return (
            "FEATURE_INJECTION_REQUIRED",
            "feature_effect_mode=REPORT_ONLY: Phase48 model_home_prob is identical to "
            "baseline, confirming P0 features are NOT yet injected into the prediction "
            "model. Metric deltas are zero by construction. Next required action: "
            "Phase 50 Feature Injection into Backtest Model.",
        )

    # Insufficient sample for MODEL_AFFECTING evaluation
    if baseline_m.n < 100 or phase48_m.n < 100:
        return "COLLECT_MORE_DATA", "Insufficient sample size for reliable gate decision."

    # MODEL_AFFECTING path
    seg_map = {s.segment_key: s for s in seg_comparisons}

    apr_bss = seg_map.get("month:2025-04")
    hf_ece  = seg_map.get("odds_bucket:heavy_favorite")
    hc_bss  = seg_map.get("confidence:high_confidence")

    apr_ok = apr_bss is not None and not math.isnan(apr_bss.phase48_bss) and apr_bss.phase48_bss > -0.01
    hf_ok  = hf_ece is not None and not math.isnan(hf_ece.phase48_ece) and hf_ece.phase48_ece < 0.060
    hc_ok  = hc_bss is not None and not math.isnan(hc_bss.phase48_bss) and hc_bss.phase48_bss >= 0.0
    overall_ok = (
        not math.isnan(phase48_m.bss_vs_market)
        and not math.isnan(baseline_m.bss_vs_market)
        and phase48_m.bss_vs_market > baseline_m.bss_vs_market
    )

    if apr_ok and hf_ok and hc_ok and overall_ok:
        return (
            "FEATURE_REPAIR_EFFECTIVE_PAPER_ONLY",
            "MODEL_AFFECTING: All four success criteria met — "
            "2025-04 BSS > -1%, heavy_favorite ECE < 0.060, "
            "high_confidence BSS >= 0, overall BSS improved. "
            "Paper-only validation; production deployment NOT cleared.",
        )
    return (
        "FEATURE_REPAIR_NOT_EFFECTIVE",
        "MODEL_AFFECTING: P0 features altered predictions but did not meet "
        "all success criteria. Feature repair incomplete. "
        f"apr_ok={apr_ok}, hf_ok={hf_ok}, hc_ok={hc_ok}, overall_ok={overall_ok}.",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 9  Audit hash
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_audit_hash(
    feature_effect_mode: str,
    gate: str,
    baseline_n: int,
    phase48_n: int,
    run_id: str,
) -> str:
    raw = json.dumps({
        "feature_effect_mode": feature_effect_mode,
        "gate": gate,
        "baseline_n": baseline_n,
        "phase48_n": phase48_n,
        "run_id": run_id,
        "candidate_patch_created": False,
        "production_modified": False,
    }, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════════
# § 10  Main entry point
# ═══════════════════════════════════════════════════════════════════════════════

def run_phase49_evaluation(
    baseline_path: Path | str,
    phase48_path: Path | str,
) -> Phase49EvaluationResult:
    """
    Execute Phase 49 evaluation pipeline.

    Parameters
    ----------
    baseline_path : Path | str
        Path to baseline JSONL (mlb_2025_per_game_predictions.jsonl)
    phase48_path : Path | str
        Path to phase48-enriched JSONL (mlb_2025_per_game_predictions_phase48_p0_v1.jsonl)

    Returns
    -------
    Phase49EvaluationResult
        Full evaluation snapshot with all metrics, segment comparisons, and gate.
    """
    assert not CANDIDATE_PATCH_CREATED, "INVARIANT: CANDIDATE_PATCH_CREATED must be False"
    assert not PRODUCTION_MODIFIED, "INVARIANT: PRODUCTION_MODIFIED must be False"

    baseline_path = Path(baseline_path)
    phase48_path = Path(phase48_path)

    run_id = str(uuid.uuid4())
    generated_at = datetime.now(timezone.utc).isoformat()

    # ── Load raw dicts ────────────────────────────────────────────────────────
    logger.info("Loading baseline JSONL: %s", baseline_path)
    baseline_raw = _load_jsonl(baseline_path)
    logger.info("Loading phase48 JSONL: %s", phase48_path)
    phase48_raw = _load_jsonl(phase48_path)

    # ── Parse to PredictionRow ────────────────────────────────────────────────
    baseline_rows = [r for r in (_to_prediction_row(d) for d in baseline_raw) if r is not None]
    phase48_rows  = [r for r in (_to_prediction_row(d) for d in phase48_raw)  if r is not None]
    logger.info("Parsed %d baseline rows, %d phase48 rows", len(baseline_rows), len(phase48_rows))

    # ── CRITICAL: feature effect mode ─────────────────────────────────────────
    feature_effect_mode, mismatch_count = detect_feature_effect_mode(baseline_rows, phase48_rows)
    logger.info("feature_effect_mode=%s (mismatch_count=%d)", feature_effect_mode, mismatch_count)

    # ── Global metrics ────────────────────────────────────────────────────────
    baseline_metrics = _compute_metrics(baseline_rows, "baseline")
    phase48_metrics  = _compute_metrics(phase48_rows, "phase48")

    # Market metrics from baseline (same market odds in both)
    if baseline_rows:
        market_p = [r.market_home_prob_no_vig for r in baseline_rows]
        labels   = [r.home_win for r in baseline_rows]
        mkt_brier = brier_score(market_p, labels)
        mkt_ece   = expected_calibration_error(market_p, labels)["ece"]
        mkt_ll    = log_loss_score(market_p, labels)
        market_metrics = MetricsSnapshot("market", len(baseline_rows), round(mkt_brier, 6), 0.0, round(mkt_ece, 6), round(mkt_ll, 6))
    else:
        market_metrics = MetricsSnapshot("market", 0, float("nan"), 0.0, float("nan"), float("nan"))

    delta_metrics = MetricsDelta(
        delta_brier    = round(phase48_metrics.brier - baseline_metrics.brier, 6),
        delta_bss      = round(phase48_metrics.bss_vs_market - baseline_metrics.bss_vs_market, 6),
        delta_ece      = round(phase48_metrics.ece - baseline_metrics.ece, 6),
        delta_log_loss = round(phase48_metrics.log_loss - baseline_metrics.log_loss, 6),
    )

    # ── Segment-level metrics ─────────────────────────────────────────────────
    baseline_segs = _compute_segment_metrics(baseline_rows, "baseline")
    phase48_segs  = _compute_segment_metrics(phase48_rows, "phase48")
    segment_comparisons = build_segment_comparisons(baseline_segs, phase48_segs)

    # ── Feature availability & leakage guard ──────────────────────────────────
    feature_availability = build_feature_availability_summary(phase48_raw)
    leakage_guard        = build_leakage_guard_summary(phase48_raw)

    # ── Gate recommendation ───────────────────────────────────────────────────
    gate, rationale = _decide_gate(
        feature_effect_mode, baseline_metrics, phase48_metrics, segment_comparisons
    )

    audit_hash = _compute_audit_hash(
        feature_effect_mode, gate, baseline_metrics.n, phase48_metrics.n, run_id
    )

    result = Phase49EvaluationResult(
        run_id=run_id,
        generated_at=generated_at,
        baseline_path=str(baseline_path),
        phase48_path=str(phase48_path),
        feature_effect_mode=feature_effect_mode,
        baseline_metrics=baseline_metrics,
        phase48_metrics=phase48_metrics,
        market_metrics=market_metrics,
        delta_metrics=delta_metrics,
        segment_comparisons=segment_comparisons,
        feature_availability=feature_availability,
        leakage_guard=leakage_guard,
        gate_recommendation=gate,
        gate_rationale=rationale,
        candidate_patch_created=False,
        production_modified=False,
        audit_hash=audit_hash,
    )
    logger.info(
        "Phase 49 complete: feature_effect_mode=%s gate=%s",
        feature_effect_mode, gate,
    )
    return result
