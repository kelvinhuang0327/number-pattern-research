# Source to Target Semantic Map — PREDRAW_REPLAY_QUERY_NORMALIZATION_MIGRATION_R3

## Overview
This document maps the source query normalization logic from reference branch `refs/remotes/origin/task/p273a-prize-aware-inferential-validation` (`cand_087c_replay_query_normalization`) to the live target codebase `lottery_api/routes/replay.py`.

## 1. Helper Functions
- `_normalise_lottery_type_query(lottery_type: Optional[str]) -> Optional[str]`
  - Source: `lottery_api/routes/replay.py` lines 1387-1392
  - Target: Add to `lottery_api/routes/replay.py`
  - Functionality: Strips whitespace and converts string to UPPERCASE. Returns `None` if input is not a non-empty string.

- `_normalise_detail_enum_query(value: str, allowed: tuple[str, ...], param_name: str) -> str`
  - Source: `lottery_api/routes/replay.py` lines 1747-1756
  - Target: Add to `lottery_api/routes/replay.py`
  - Functionality: Strips whitespace and converts string to lowercase. Validates against `allowed` tuple, raising `HTTPException(400)` with clear error message if invalid.

## 2. Target Endpoint Integration
- `GET /api/replay/history-overview` (`get_history_replay_overview`)
  - Normalize `lottery_type` query via `_normalise_lottery_type_query(lottery_type)`.
  - Use `lottery_type_filter` for registry/DB filtering and return payload.

- `GET /api/replay/history-detail` (`get_history_replay_detail`)
  - Normalize `lottery_type` query via `_normalise_lottery_type_query(lottery_type) or lottery_type`.
  - Normalize `sort` via `_normalise_detail_enum_query(sort, _DETAIL_SORTS, "sort")`.
  - Normalize `hit_filter` via `_normalise_detail_enum_query(hit_filter, _DETAIL_HIT_FILTERS, "hit_filter")`.

- `GET /api/replay/history-detail-grouped` (`get_history_replay_detail_grouped`)
  - Normalize `lottery_type` query via `_normalise_lottery_type_query(lottery_type) or lottery_type`.
  - Normalize `sort` via `_normalise_detail_enum_query(sort, _DETAIL_SORTS, "sort")`.
  - Normalize `hit_filter` via `_normalise_detail_enum_query(hit_filter, _DETAIL_HIT_FILTERS, "hit_filter")`.

## 3. Unrelated Source Changes Excluded
- Broad D3 status coverage changes or new endpoints (`/api/replay/d3-strategy-status-coverage`) are NOT migrated.
- No DB access mode changes (`mode=ro`) or DB schema/model changes.
- Existing route declarations, response shapes, and non-query-normalization logic remain unchanged.
