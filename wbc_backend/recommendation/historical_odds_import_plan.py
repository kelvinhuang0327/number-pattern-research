"""
P7-C — Historical Odds Import Plan (Spec / Dry-Run Only)
===========================================================
此模組為 spec-only 設計文件，定義 historical pregame/closing odds 匯入 adapter 的
合約規範。

【重要約束】
- 此模組不呼叫任何外部 API（dry-run / spec only）
- 不寫入 production proposal channel
- 不修改 TSL crawler
- paper_only=True 全程強制
- 此模組目的：定義 adapter contract，供 P8 實作時參照

【支援的 Provider Types】
- THE_ODDS_API      : The Odds API v4 historical endpoint
- ODDSJAM           : OddsJam API historical odds
- TSL_2026_FORWARD  : 既有 TSL odds_history.jsonl (2026 forward)
- CUSTOM_CSV        : 自定義 CSV 格式（研究用途）

【合約關係】
- Input: provider-specific payload
- Output: normalized MlbOddsSnapshot (from odds_contract.py)
- Validation: OddsContractError on any invariant violation
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional

from wbc_backend.recommendation.odds_contract import (
    MlbOddsSnapshot,
    OddsContractError,
    OddsSourceType,
)


# ---------------------------------------------------------------------------
# Provider Enum
# ---------------------------------------------------------------------------

class OddsProviderType(str, Enum):
    THE_ODDS_API     = "THE_ODDS_API"
    ODDSJAM          = "ODDSJAM"
    TSL_2026_FORWARD = "TSL_2026_FORWARD"
    CUSTOM_CSV       = "CUSTOM_CSV"


# ---------------------------------------------------------------------------
# Import Contract Errors
# ---------------------------------------------------------------------------

class OddsImportError(ValueError):
    """Historical odds import contract 違反時拋出。"""


class PaperOnlyViolationError(RuntimeError):
    """paper_only=false 嘗試時拋出。"""


# ---------------------------------------------------------------------------
# Adapter Config
# ---------------------------------------------------------------------------

@dataclass
class HistoricalOddsImportConfig:
    """
    匯入 adapter 設定。

    Fields
    ------
    provider           : OddsProviderType
    paper_only         : 必須為 True（dry-run / spec only）
    closing_window_sec : 若 captured_at 距離 game_start ≤ 此秒數，視為 CLOSING
                         預設 3600 秒（1 小時）
    pregame_min_sec    : captured_at 必須至少在開賽前幾秒才算 PREGAME
                         預設 60 秒
    allow_unknown_ts   : True → 允許 UNKNOWN timestamp（但不得進入 CLV gate）
    team_norm_table    : team abbreviation 正規化表 {provider_abbr: standard_3letter}
    """
    provider: OddsProviderType
    paper_only: bool = True
    closing_window_sec: int = 3600
    pregame_min_sec: int = 60
    allow_unknown_ts: bool = True
    team_norm_table: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Duplicate Detection
# ---------------------------------------------------------------------------

def _snapshot_dedup_key(snap: MlbOddsSnapshot) -> str:
    """
    產生快照的去重鍵值（deterministic hash）。
    相同 game_id + market + side + captured_at_utc → 視為重複，取先到的一筆。
    """
    ts_str = snap.captured_at_utc.isoformat() if snap.captured_at_utc else "UNKNOWN"
    raw = f"{snap.game_id}|{snap.market}|{snap.side}|{ts_str}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Timezone Normalization
# ---------------------------------------------------------------------------

_KNOWN_TIMEZONE_OFFSETS: dict[str, int] = {
    "EDT": -4,
    "EST": -5,
    "CDT": -5,
    "CST": -6,
    "MDT": -6,
    "MST": -7,
    "PDT": -7,
    "PST": -8,
    "UTC": 0,
    "GMT": 0,
    "JST": 9,
    "CST+8": 8,  # 台灣/中國
}


def normalize_to_utc(dt: datetime, tz_hint: str = "UTC") -> datetime:
    """
    將 datetime 正規化為 UTC-aware datetime。

    Rules:
    - 若已有 tzinfo → 直接轉換為 UTC
    - 若無 tzinfo + tz_hint 在已知表 → 套用 offset
    - 若無 tzinfo + tz_hint 未知 → raise OddsImportError
    """
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)

    offset_hours = _KNOWN_TIMEZONE_OFFSETS.get(tz_hint.upper())
    if offset_hours is None:
        raise OddsImportError(
            f"[OddsImport] Unknown timezone hint '{tz_hint}'. "
            f"Cannot normalize to UTC without explicit offset."
        )
    return (dt - timedelta(hours=offset_hours)).replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Game ID Mapping Strategy
# ---------------------------------------------------------------------------

@dataclass
class GameIdMappingResult:
    """
    Provider game ID → MLB Stats API gamePk 映射結果。

    Fields
    ------
    game_id      : 使用的最終 game_id（gamePk 優先，fallback 為 provider_raw_id）
    gamePk       : MLB Stats API gamePk（若可映射）
    game_number  : Doubleheader game number（1 or 2；若非 doubleheader 則為 1）
    is_doubleheader : 是否為連賽
    mapping_method  : "gamePk_lookup" / "date_teams_fallback" / "provider_id_only"
    """
    game_id: str
    gamePk: Optional[int]
    game_number: int = 1
    is_doubleheader: bool = False
    mapping_method: str = "provider_id_only"


def map_game_id(
    provider_game_id: str,
    game_date: str,       # YYYY-MM-DD
    away_team: str,       # 3-letter normalized
    home_team: str,       # 3-letter normalized
    game_number: int = 1,
    gamepk_lookup_fn: Optional[Any] = None,  # Callable[[str,str,str,int], Optional[int]]
) -> GameIdMappingResult:
    """
    Dry-run spec：定義 game_id 映射邏輯。

    優先順序：
    1. 若有 gamepk_lookup_fn → 嘗試查詢 gamePk
    2. Fallback → date+teams 組合 key
    3. Doubleheader → game_number 必須保留在 game_id 中

    【重要】本函數在 P7 為 dry-run spec；P8 實作時應填入真實 lookup function。
    """
    if gamepk_lookup_fn is not None:
        try:
            gamePk = gamepk_lookup_fn(game_date, away_team, home_team, game_number)
        except Exception:
            gamePk = None
    else:
        gamePk = None

    is_dh = game_number > 1
    if gamePk is not None:
        gid = f"MLB_{gamePk}"
        method = "gamePk_lookup"
    else:
        # date+teams fallback；doubleheader 加序號
        suffix = f"_G{game_number}" if is_dh else ""
        gid = f"MLB_{game_date}_{away_team}_{home_team}{suffix}"
        method = "date_teams_fallback"

    return GameIdMappingResult(
        game_id=gid,
        gamePk=gamePk,
        game_number=game_number,
        is_doubleheader=is_dh,
        mapping_method=method,
    )


# ---------------------------------------------------------------------------
# Source Type Classification
# ---------------------------------------------------------------------------

def classify_source_type(
    captured_at_utc: Optional[datetime],
    game_start_utc: datetime,
    closing_window_sec: int = 3600,
    pregame_min_sec: int = 60,
) -> OddsSourceType:
    """
    根據 captured_at_utc 與 game_start_utc 的時間差，決定 OddsSourceType。

    Rules:
    - captured_at_utc is None → UNKNOWN
    - captured_at_utc > game_start_utc → POST_GAME_PROXY（不得標為 PREGAME）
    - captured_at_utc <= game_start_utc - pregame_min_sec → PREGAME
    - captured_at_utc within closing_window_sec of game_start_utc → CLOSING
    - gap > closing_window_sec → PREGAME (early)
    """
    if captured_at_utc is None:
        return OddsSourceType.UNKNOWN

    # 確保都是 UTC-aware
    if captured_at_utc.tzinfo is None:
        captured_at_utc = captured_at_utc.replace(tzinfo=timezone.utc)
    if game_start_utc.tzinfo is None:
        game_start_utc = game_start_utc.replace(tzinfo=timezone.utc)

    delta_sec = (game_start_utc - captured_at_utc).total_seconds()

    if delta_sec < 0:
        # captured AFTER game start → POST_GAME_PROXY
        return OddsSourceType.POST_GAME_PROXY

    if delta_sec < pregame_min_sec:
        # captured within pregame_min_sec of game start → treat as CLOSING
        return OddsSourceType.CLOSING

    if delta_sec <= closing_window_sec:
        return OddsSourceType.CLOSING

    return OddsSourceType.PREGAME


# ---------------------------------------------------------------------------
# Provider Payload Normalizers (Dry-Run Specs)
# ---------------------------------------------------------------------------

def normalize_the_odds_api_payload(
    payload: dict[str, Any],
    config: HistoricalOddsImportConfig,
    seen_dedup: Optional[set[str]] = None,
) -> list[MlbOddsSnapshot]:
    """
    Normalize a single The Odds API v4 historical event payload into
    a list of MlbOddsSnapshot records.

    Expected payload structure (dry-run spec):
    {
      "id": "...",
      "sport_key": "baseball_mlb",
      "commence_time": "2025-04-01T23:10:00Z",
      "away_team": "Boston Red Sox",
      "home_team": "New York Yankees",
      "bookmakers": [
        {
          "key": "pinnacle",
          "title": "Pinnacle",
          "last_update": "2025-04-01T21:00:00Z",
          "markets": [
            {
              "key": "h2h",
              "last_update": "2025-04-01T21:00:00Z",
              "outcomes": [
                {"name": "Boston Red Sox", "price": 2.10},
                {"name": "New York Yankees", "price": 1.75}
              ]
            }
          ]
        }
      ]
    }
    """
    if config.paper_only is not True:
        raise PaperOnlyViolationError(
            "[OddsImport] paper_only must be True for historical odds import."
        )

    if seen_dedup is None:
        seen_dedup = set()

    snapshots: list[MlbOddsSnapshot] = []

    game_start_str = payload.get("commence_time", "")
    provider_game_id = payload.get("id", "")
    away_team_raw = payload.get("away_team", "")
    home_team_raw = payload.get("home_team", "")

    if not game_start_str:
        raise OddsImportError("[TheOddsAPI] Missing commence_time in payload.")

    try:
        game_start_utc = datetime.fromisoformat(
            game_start_str.replace("Z", "+00:00")
        )
    except ValueError as e:
        raise OddsImportError(f"[TheOddsAPI] Invalid commence_time: {e}") from e

    # Normalize team names
    away_team = config.team_norm_table.get(away_team_raw, away_team_raw[:3].upper())
    home_team = config.team_norm_table.get(home_team_raw, home_team_raw[:3].upper())

    for bookmaker in payload.get("bookmakers", []):
        book_key = bookmaker.get("key", "UNKNOWN")
        for market in bookmaker.get("markets", []):
            market_key = market.get("key", "")  # h2h / spreads / totals

            # Map market key to P6 contract market code
            market_code = {
                "h2h": "ML",
                "spreads": "RL",
                "totals": "OU",
            }.get(market_key, market_key.upper())

            market_update_str = market.get("last_update", bookmaker.get("last_update", ""))

            captured_at_utc: Optional[datetime] = None
            if market_update_str:
                try:
                    captured_at_utc = datetime.fromisoformat(
                        market_update_str.replace("Z", "+00:00")
                    )
                except ValueError:
                    captured_at_utc = None

            source_type = classify_source_type(
                captured_at_utc, game_start_utc,
                config.closing_window_sec, config.pregame_min_sec
            )

            for outcome in market.get("outcomes", []):
                name_raw = outcome.get("name", "")
                price = outcome.get("price", 0.0)

                if not isinstance(price, (int, float)) or price < 1.0:
                    raise OddsImportError(
                        f"[TheOddsAPI] Invalid decimal odds: {price!r} "
                        f"for outcome '{name_raw}' in game {provider_game_id}"
                    )

                # Determine side
                side = config.team_norm_table.get(name_raw, name_raw[:4].upper())
                if name_raw == away_team_raw or name_raw == away_team:
                    side = "AWAY"
                elif name_raw == home_team_raw or name_raw == home_team:
                    side = "HOME"
                elif name_raw in ("Over", "Under"):
                    side = name_raw.upper()

                game_id_result = map_game_id(
                    provider_game_id,
                    game_start_utc.strftime("%Y-%m-%d"),
                    away_team, home_team,
                )

                snap = MlbOddsSnapshot(
                    game_id=game_id_result.game_id,
                    game_start_utc=game_start_utc,
                    captured_at_utc=captured_at_utc,
                    market=market_code,
                    side=side,
                    decimal_odds=float(price),
                    source=f"TheOddsAPI/{book_key}",
                    source_type=source_type,
                    paper_only=True,
                    source_trace=(
                        f"TheOddsAPI v4 historical | event_id={provider_game_id} "
                        f"| book={book_key} | market={market_key} "
                        f"| captured={market_update_str or 'UNKNOWN'}"
                    ),
                )

                dedup_key = _snapshot_dedup_key(snap)
                if dedup_key in seen_dedup:
                    # 重複快照：deterministically skip（保留先到的）
                    continue
                seen_dedup.add(dedup_key)
                snapshots.append(snap)

    return snapshots


def normalize_tsl_forward_payload(
    record: dict[str, Any],
    config: HistoricalOddsImportConfig,
    game_start_utc: datetime,
    seen_dedup: Optional[set[str]] = None,
) -> list[MlbOddsSnapshot]:
    """
    Normalize a single TSL odds_history.jsonl record into MlbOddsSnapshot list.

    Expected record structure:
    {
      "source": "TSL_BLOB3RD",
      "fetched_at": "2026-03-13T03:30:16.039741Z",
      "match_id": "3452364.1",
      "game_time": "2026-03-13T12:00:00+08:00",
      "home_team_name": "...",
      "away_team_name": "...",
      "markets": [
        {
          "marketCode": "MNL",
          "outcomes": [{"outcomeName": "...", "odds": "1.53"}]
        }
      ]
    }
    """
    if config.paper_only is not True:
        raise PaperOnlyViolationError(
            "[OddsImport] paper_only must be True for TSL forward import."
        )

    if seen_dedup is None:
        seen_dedup = set()

    snapshots: list[MlbOddsSnapshot] = []

    match_id = record.get("match_id", "UNKNOWN")
    fetched_str = record.get("fetched_at", "")
    tsl_source = record.get("source", "TSL_UNKNOWN")

    captured_at_utc: Optional[datetime] = None
    if fetched_str:
        try:
            captured_at_utc = datetime.fromisoformat(
                fetched_str.replace("Z", "+00:00")
            )
        except ValueError:
            captured_at_utc = None

    source_type = classify_source_type(
        captured_at_utc, game_start_utc,
        config.closing_window_sec, config.pregame_min_sec
    )

    home_raw = record.get("home_team_name", "")
    away_raw = record.get("away_team_name", "")

    for mkt in record.get("markets", []):
        market_code_raw = mkt.get("marketCode", "UNKNOWN")
        market_code = {"MNL": "ML", "HDP": "RL", "OU": "OU"}.get(
            market_code_raw, market_code_raw
        )

        for outcome in mkt.get("outcomes", []):
            name_raw = outcome.get("outcomeName", "")
            odds_str = outcome.get("odds", "")

            try:
                decimal_odds = float(odds_str)
            except (ValueError, TypeError):
                raise OddsImportError(
                    f"[TSLForward] Invalid odds value '{odds_str}' "
                    f"for match_id={match_id}, outcome={name_raw}"
                )

            if decimal_odds < 1.0:
                raise OddsImportError(
                    f"[TSLForward] Decimal odds < 1.0 ({decimal_odds}) "
                    f"for match_id={match_id}"
                )

            # Determine side
            if name_raw == home_raw:
                side = "HOME"
            elif name_raw == away_raw:
                side = "AWAY"
            else:
                side = name_raw[:6].upper()

            snap = MlbOddsSnapshot(
                game_id=f"TSL_{match_id}",
                game_start_utc=game_start_utc,
                captured_at_utc=captured_at_utc,
                market=market_code,
                side=side,
                decimal_odds=decimal_odds,
                source=tsl_source,
                source_type=source_type,
                paper_only=True,
                source_trace=(
                    f"TSL forward | match_id={match_id} "
                    f"| market={market_code_raw} "
                    f"| fetched={fetched_str or 'UNKNOWN'} "
                    f"| source={tsl_source}"
                ),
            )

            dedup_key = _snapshot_dedup_key(snap)
            if dedup_key in seen_dedup:
                continue
            seen_dedup.add(dedup_key)
            snapshots.append(snap)

    return snapshots


# ---------------------------------------------------------------------------
# Validation Summary
# ---------------------------------------------------------------------------

@dataclass
class ImportBatchResult:
    """
    批次匯入結果摘要（dry-run report）。
    """
    provider: OddsProviderType
    paper_only: bool
    total_input_records: int
    total_snapshots_produced: int
    duplicates_skipped: int
    post_game_proxy_count: int
    pregame_count: int
    closing_count: int
    unknown_ts_count: int
    validation_errors: list[str]
    is_clv_ready: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider.value,
            "paper_only": self.paper_only,
            "total_input_records": self.total_input_records,
            "total_snapshots_produced": self.total_snapshots_produced,
            "duplicates_skipped": self.duplicates_skipped,
            "post_game_proxy_count": self.post_game_proxy_count,
            "pregame_count": self.pregame_count,
            "closing_count": self.closing_count,
            "unknown_ts_count": self.unknown_ts_count,
            "validation_errors": self.validation_errors,
            "is_clv_ready": self.is_clv_ready,
        }
