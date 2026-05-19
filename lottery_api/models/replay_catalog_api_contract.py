"""
replay_catalog_api_contract.py
================================
P3 Replay Catalog API response contract.

Defines:
  - ReplayCatalogStrategyItem  — per-strategy item in list responses
  - ReplayCatalogListResponse  — full list with filters + summary
  - ReplayReadinessFlags       — per-strategy readiness booleans
  - VISIBILITY_STATE_MESSAGES  — canonical UI text for each state

HARD CONSTRAINTS (P3):
  - RECONSTRUCTIBLE is NOT replay success (can_show_replay_rows=False)
  - ARTIFACT_CANDIDATE is NOT ONLINE (is_catalog_visible but not production)
  - REGISTERED_NO_DATA / NO_DATA are NOT replay success
  - No DB writes; all response data is read-only derived from catalog source
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# State message table — canonical UI text
# ---------------------------------------------------------------------------

VISIBILITY_STATE_MESSAGES = {
    "REGISTERED_WITH_REPLAY_ROWS": {
        "summary":     "有歷史預測資料",
        "detail":      "此策略已在 runtime 登錄，且有歷史 replay rows 可查閱。",
        "badge":       "Has replay rows",
        "badge_zh":    "可查看歷史預測",
        "can_show_replay": True,
        "is_success":  True,
    },
    "RECONSTRUCTIBLE": {
        "summary":     "尚未補 replay rows，可進入重建佇列",
        "detail":      "此策略有 artifact/log 可供重建，但 replay rows 尚未補全。需 P5-P7 重建流程。",
        "badge":       "Reconstructible",
        "badge_zh":    "可重建 / 尚未補資料",
        "can_show_replay": False,
        "is_success":  False,
    },
    "REGISTERED_NO_DATA": {
        "summary":     "已登錄，但無歷史資料",
        "detail":      "此策略在 runtime 登錄，但既無 replay rows 也無可用 artifact。",
        "badge":       "No historical data",
        "badge_zh":    "無歷史資料",
        "can_show_replay": False,
        "is_success":  False,
    },
    "ARTIFACT_CANDIDATE": {
        "summary":     "僅 artifact 候選，尚未進 runtime registry",
        "detail":      "此策略在 code/artifact 掃描中發現，但尚未納入 runtime registry。不可視為 ONLINE。",
        "badge":       "Artifact only",
        "badge_zh":    "Artifact only / 未進 runtime",
        "can_show_replay": False,
        "is_success":  False,
    },
    "UNSUPPORTED": {
        "summary":     "不支援 replay",
        "detail":      "此策略無 artifact、無 replay rows、也無重建依據。",
        "badge":       "Unsupported",
        "badge_zh":    "不支援",
        "can_show_replay": False,
        "is_success":  False,
    },
}

ALL_VISIBILITY_STATES = list(VISIBILITY_STATE_MESSAGES.keys())


# ---------------------------------------------------------------------------
# Readiness flags (per-strategy)
# ---------------------------------------------------------------------------

@dataclass
class ReplayReadinessFlags:
    is_catalog_visible:           bool   # in catalog at all
    can_show_replay_rows:         bool   # REGISTERED_WITH_REPLAY_ROWS only
    can_show_no_data_message:     bool   # REGISTERED_NO_DATA or UNSUPPORTED
    can_enter_reconstruction_queue: bool  # RECONSTRUCTIBLE only
    is_artifact_only:             bool   # ARTIFACT_CANDIDATE
    is_production_strategy:       bool   # lifecycle_state == ONLINE

    def to_dict(self) -> dict:
        return {
            "is_catalog_visible":            self.is_catalog_visible,
            "can_show_replay_rows":          self.can_show_replay_rows,
            "can_show_no_data_message":      self.can_show_no_data_message,
            "can_enter_reconstruction_queue":self.can_enter_reconstruction_queue,
            "is_artifact_only":              self.is_artifact_only,
            "is_production_strategy":        self.is_production_strategy,
        }


def build_readiness_flags(
    catalog_visibility_state: str,
    lifecycle_state: str,
) -> ReplayReadinessFlags:
    cvs = catalog_visibility_state
    return ReplayReadinessFlags(
        is_catalog_visible            = cvs in ALL_VISIBILITY_STATES,
        can_show_replay_rows          = cvs == "REGISTERED_WITH_REPLAY_ROWS",
        can_show_no_data_message      = cvs in ("REGISTERED_NO_DATA", "UNSUPPORTED"),
        can_enter_reconstruction_queue= cvs == "RECONSTRUCTIBLE",
        is_artifact_only              = cvs == "ARTIFACT_CANDIDATE",
        is_production_strategy        = lifecycle_state == "ONLINE",
    )


# ---------------------------------------------------------------------------
# Per-strategy item
# ---------------------------------------------------------------------------

@dataclass
class ReplayCatalogStrategyItem:
    strategy_id:              str
    display_name:             str
    lottery_type:             str
    lifecycle_state:          str
    catalog_visibility_state: str
    has_replay_rows:          bool
    has_historical_predictions: bool
    reconstructible_reason:   Optional[str]
    no_data_reason:           Optional[str]
    artifact_source_type:     str
    source_paths:             List[str]
    provenance_hash:          Optional[str]
    dry_run_only:             bool
    readiness:                ReplayReadinessFlags
    state_message:            dict   # from VISIBILITY_STATE_MESSAGES

    def to_dict(self) -> dict:
        return {
            "strategy_id":               self.strategy_id,
            "display_name":              self.display_name,
            "lottery_type":              self.lottery_type,
            "lifecycle_state":           self.lifecycle_state,
            "catalog_visibility_state":  self.catalog_visibility_state,
            "has_replay_rows":           self.has_replay_rows,
            "has_historical_predictions":self.has_historical_predictions,
            "reconstructible_reason":    self.reconstructible_reason,
            "no_data_reason":            self.no_data_reason,
            "artifact_source_type":      self.artifact_source_type,
            "source_paths":              self.source_paths,
            "provenance_hash":           self.provenance_hash,
            "dry_run_only":              self.dry_run_only,
            "readiness":                 self.readiness.to_dict(),
            "state_message":             self.state_message,
        }


# ---------------------------------------------------------------------------
# List response
# ---------------------------------------------------------------------------

@dataclass
class ReplayCatalogListResponse:
    items:                List[ReplayCatalogStrategyItem]
    total:                int
    source_used:          str     # "live_db" | "p2_json" | "p1_json"
    filter_visibility:    Optional[str]
    filter_lifecycle:     Optional[str]
    summary_by_visibility:dict    # state → count
    summary_by_lifecycle: dict    # state → count
    dry_run_only:         bool    # True if source is fallback JSON

    def to_dict(self) -> dict:
        return {
            "items":                 [i.to_dict() for i in self.items],
            "total":                 self.total,
            "source_used":           self.source_used,
            "filter_visibility":     self.filter_visibility,
            "filter_lifecycle":      self.filter_lifecycle,
            "summary_by_visibility": self.summary_by_visibility,
            "summary_by_lifecycle":  self.summary_by_lifecycle,
            "dry_run_only":          self.dry_run_only,
        }


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_catalog_list_response(
    entries,
    filter_visibility: Optional[str] = None,
    filter_lifecycle: Optional[str]  = None,
    source_used: str = "unknown",
) -> ReplayCatalogListResponse:
    """
    Convert NormalizedCatalogEntry list → ReplayCatalogListResponse.
    Applies optional filters; computes summary counts.
    """
    filtered = entries
    if filter_visibility:
        filtered = [e for e in filtered if e.catalog_visibility_state == filter_visibility]
    if filter_lifecycle:
        filtered = [e for e in filtered if e.lifecycle_state == filter_lifecycle]

    items = []
    for e in filtered:
        flags = build_readiness_flags(e.catalog_visibility_state, e.lifecycle_state)
        msg   = VISIBILITY_STATE_MESSAGES.get(e.catalog_visibility_state, {
            "summary": "Unknown state",
            "detail": "",
            "badge": "Unknown",
            "badge_zh": "未知",
            "can_show_replay": False,
            "is_success": False,
        })
        items.append(ReplayCatalogStrategyItem(
            strategy_id              = e.strategy_id,
            display_name             = e.display_name,
            lottery_type             = e.lottery_type,
            lifecycle_state          = e.lifecycle_state,
            catalog_visibility_state = e.catalog_visibility_state,
            has_replay_rows          = e.has_replay_rows,
            has_historical_predictions=e.has_historical_predictions,
            reconstructible_reason   = e.reconstructible_reason,
            no_data_reason           = e.no_data_reason,
            artifact_source_type     = e.artifact_source_type,
            source_paths             = e.source_paths,
            provenance_hash          = e.provenance_hash,
            dry_run_only             = e.dry_run_only,
            readiness                = flags,
            state_message            = msg,
        ))

    from collections import Counter
    all_vis = Counter(e.catalog_visibility_state for e in entries)
    all_lc  = Counter(e.lifecycle_state for e in entries)

    return ReplayCatalogListResponse(
        items                 = items,
        total                 = len(items),
        source_used           = source_used,
        filter_visibility     = filter_visibility,
        filter_lifecycle      = filter_lifecycle,
        summary_by_visibility = dict(all_vis),
        summary_by_lifecycle  = dict(all_lc),
        dry_run_only          = source_used != "live_db",
    )
