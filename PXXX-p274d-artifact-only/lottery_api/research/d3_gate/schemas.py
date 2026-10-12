"""D3 gate read-only schemas (P258E skeleton).

Schema/dataclass/enum definitions ONLY. No DB access, no production/registry/
recommendation/controlled_apply/deployment imports, no statistical computation,
no execution. Stdlib only.

The gate status enum is deliberately limited to two values. There is no
``APPROVED`` / ``PROMOTED`` / ``PRODUCTION_READY`` / ``RECOMMENDED`` value, by
design: passing the gate means only "not yet rejected", never "approved".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class GateStatus(str, Enum):
    """The only two permissible gate outcomes.

    ``NOT_YET_REJECTED`` is explicitly NOT approval. A candidate that is not yet
    rejected remains observation-only and requires a separate, human-authorized
    prototype plus later corrected-OOS confirmation before any further step.
    """

    REJECTED = "REJECTED"
    NOT_YET_REJECTED = "NOT_YET_REJECTED"


@dataclass(frozen=True)
class CandidateInput:
    """Read-only contract for a candidate method's frozen OOS output artifact."""

    candidate_id: str
    lottery_type: str
    target_draw_id: str
    target_draw_date: str
    n_bet_count: int
    numbers_per_bet: int
    feature_dimensionality: int
    regime_count_or_parameter_count: int
    window_schedule: str
    generated_at: str
    available_information_cutoff: str
    random_seed: int
    source_artifact_path: str
    provenance_digest: str


@dataclass(frozen=True)
class P257ABaselineInput:
    """Read-only contract for the P257A best-N-bet baseline comparison input."""

    baseline_id: str
    lottery_type: str
    target_draw_id: str
    n_bet_count: int
    source_artifact_path: str
    baseline_digest: str


@dataclass(frozen=True)
class MatchedNullFamily:
    """Read-only contract for a candidate-matched adversarial-null family."""

    null_family_id: str
    matched_lottery_type: str
    matched_n_bet_count: int
    matched_numbers_per_bet: int
    matched_window_schedule: str
    matched_feature_dimensionality: int
    matched_regime_or_parameter_count: int
    null_generation_seed: int
    null_count: int
    source_artifact_path: str


@dataclass(frozen=True)
class GateOutput:
    """Read-only contract for the diagnostic-only gate output artifact.

    ``gate_decision`` is a :class:`GateStatus` — never an approval. The output is
    diagnostic only and may not be read as a promotion or recommendation.
    """

    gate_decision: GateStatus
    rejection_reasons: List[str] = field(default_factory=list)
    not_yet_rejected_reasons: List[str] = field(default_factory=list)
    paired_baseline_summary: Optional[dict] = None
    null_percentile_summary: Optional[dict] = None
    correction_family_summary: Optional[dict] = None
    short_mid_long_summary: Optional[dict] = None
    leakage_provenance_summary: Optional[dict] = None
    audit_trail: List[dict] = field(default_factory=list)
