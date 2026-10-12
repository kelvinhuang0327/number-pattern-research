"""
P6-C — MLB Odds Snapshot Contract
===================================
定義合法的 pregame/closing odds 資料結構與不變條件（invariants）。

核心約束：
- captured_at_utc <= game_start_utc → 才可標為 PREGAME/CLOSING
- captured_at_utc > game_start_utc → 不得標為 PREGAME/CLOSING（強制 POST_GAME_PROXY）
- UNKNOWN timestamp 不得進入 CLV 或 promotion gate
- POST_GAME_PROXY 不得進入 optimizer promotion gate
- paper_only 必須為 True
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class OddsSourceType(str, Enum):
    OPENING          = "OPENING"           # 開盤賠率（賽前遠期）
    PREGAME          = "PREGAME"           # 賽前快照（captured < game_start）
    CLOSING          = "CLOSING"           # 封盤賠率（captured ≤ 幾分鐘前）
    POST_GAME_PROXY  = "POST_GAME_PROXY"   # 賽後抓取，無法確認為賽前
    UNKNOWN          = "UNKNOWN"           # 無法判斷時間點

# captured_at_utc 與 game_start_utc 的容忍區間（秒）
_CLOSING_MAX_SECONDS_BEFORE_START = 3600   # 最晚在開賽前 1 小時算 closing
_PREGAME_MIN_SECONDS_BEFORE_START = 60     # 至少開賽前 1 分鐘才算 pregame


class OddsContractError(ValueError):
    """Odds contract 驗證錯誤。"""


@dataclass
class MlbOddsSnapshot:
    """
    單筆 MLB 賠率快照，符合 P6-C 合約約束。

    Fields
    ------
    game_id           : 唯一場次識別碼
    game_start_utc    : 比賽開始時間（UTC）
    captured_at_utc   : 賠率抓取時間（UTC），None 表示未知
    market            : 市場代碼（ML / RL / OU）
    side              : HOME / AWAY / OVER / UNDER
    decimal_odds      : 小數賠率（>= 1.0）
    source            : 資料來源名稱（e.g. TSL / TheOddsAPI / ESPN）
    source_type       : OddsSourceType（由 validate() 強制套用）
    paper_only        : 必須為 True
    source_trace      : 溯源說明（不得為空）
    """
    game_id: str
    game_start_utc: datetime
    captured_at_utc: Optional[datetime]
    market: str
    side: str
    decimal_odds: float
    source: str
    source_type: OddsSourceType = OddsSourceType.UNKNOWN
    paper_only: bool = True
    source_trace: str = ""

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """
        執行所有 contract invariants。
        任何違反直接 raise OddsContractError。
        """
        # ── paper_only 必須為 True ────────────────────────────────────────
        if self.paper_only is not True:
            raise OddsContractError(
                f"[OddsContract] paper_only must be True; got {self.paper_only!r}"
            )

        # ── source_trace 不得為空 ─────────────────────────────────────────
        if not self.source_trace or not self.source_trace.strip():
            raise OddsContractError(
                "[OddsContract] source_trace is required and must not be empty."
            )

        # ── decimal_odds 合法範圍 ─────────────────────────────────────────
        if not isinstance(self.decimal_odds, (int, float)) or self.decimal_odds < 1.0:
            raise OddsContractError(
                f"[OddsContract] decimal_odds must be >= 1.0; got {self.decimal_odds!r}"
            )

        # ── 時間一致性：無 captured_at → UNKNOWN ─────────────────────────
        if self.captured_at_utc is None:
            if self.source_type in (OddsSourceType.PREGAME, OddsSourceType.CLOSING,
                                    OddsSourceType.OPENING):
                raise OddsContractError(
                    f"[OddsContract] source_type={self.source_type.value} requires "
                    "captured_at_utc, but it is None. Set to UNKNOWN or POST_GAME_PROXY."
                )
            return  # UNKNOWN / POST_GAME_PROXY 允許 None timestamp

        # ── captured_at > game_start → 不得標為 PREGAME/CLOSING/OPENING ──
        diff_seconds = (self.game_start_utc - self.captured_at_utc).total_seconds()

        if diff_seconds < 0:
            # captured_at > game_start（賽後）
            if self.source_type in (OddsSourceType.PREGAME, OddsSourceType.CLOSING,
                                    OddsSourceType.OPENING):
                raise OddsContractError(
                    f"[OddsContract] captured_at_utc={self.captured_at_utc.isoformat()} "
                    f"is AFTER game_start_utc={self.game_start_utc.isoformat()}. "
                    f"Cannot be classified as {self.source_type.value}. "
                    "Use POST_GAME_PROXY instead."
                )
        else:
            # captured_at <= game_start（賽前）
            if self.source_type == OddsSourceType.POST_GAME_PROXY:
                raise OddsContractError(
                    f"[OddsContract] captured_at_utc={self.captured_at_utc.isoformat()} "
                    f"is BEFORE game_start. Cannot be POST_GAME_PROXY. "
                    "Use PREGAME or CLOSING."
                )

    @classmethod
    def infer_source_type(
        cls,
        captured_at_utc: Optional[datetime],
        game_start_utc: datetime,
    ) -> OddsSourceType:
        """
        根據時間戳自動推斷 OddsSourceType。
        供外部呼叫，不修改 self。
        """
        if captured_at_utc is None:
            return OddsSourceType.UNKNOWN

        diff = (game_start_utc - captured_at_utc).total_seconds()

        if diff < 0:
            return OddsSourceType.POST_GAME_PROXY

        if diff <= _CLOSING_MAX_SECONDS_BEFORE_START:
            return OddsSourceType.CLOSING

        return OddsSourceType.PREGAME


def classify_odds_record(record: dict) -> OddsSourceType:
    """
    對 dict 格式的 odds record 套用 source_type 分類。
    供批次審計使用。
    """
    captured = record.get("captured_at_utc") or record.get("odds_timestamp")
    game_start = record.get("game_start_utc") or record.get("game_start_time")

    if not captured:
        return OddsSourceType.UNKNOWN

    try:
        if isinstance(captured, str):
            captured = datetime.fromisoformat(captured.replace("Z", "+00:00"))
        if isinstance(game_start, str):
            game_start = datetime.fromisoformat(game_start.replace("Z", "+00:00"))
        if game_start is None:
            return OddsSourceType.UNKNOWN
        return MlbOddsSnapshot.infer_source_type(captured, game_start)
    except Exception:
        return OddsSourceType.UNKNOWN
