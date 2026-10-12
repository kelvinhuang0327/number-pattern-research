"""
P6-D — CLV Readiness Gate
===========================
在實際執行 CLV 計算前，驗證資料集是否具備必要的賠率時間序列。

Gate States
-----------
CLV_READY                       — 具備 pregame + closing 賠率，可計算 CLV
BLOCKED_NO_PREGAME_ODDS         — 缺少 pregame odds
BLOCKED_NO_CLOSING_ODDS         — 缺少 closing odds
BLOCKED_POST_GAME_PROXY_ONLY    — 所有賠率均為 POST_GAME_PROXY
BLOCKED_LOW_TIMESTAMP_COVERAGE  — timestamp coverage < 95%

禁止行為：
- UNKNOWN source_type 不得參與 CLV
- POST_GAME_PROXY 不得進入 optimizer promotion gate
- paper_only=false 直接 raise
"""
from __future__ import annotations

from typing import List

from wbc_backend.recommendation.odds_contract import OddsSourceType

# CLV 所需最低 timestamp 覆蓋率
_MIN_TIMESTAMP_COVERAGE = 0.95

CLV_READY                       = "CLV_READY"
BLOCKED_NO_PREGAME_ODDS         = "BLOCKED_NO_PREGAME_ODDS"
BLOCKED_NO_CLOSING_ODDS         = "BLOCKED_NO_CLOSING_ODDS"
BLOCKED_POST_GAME_PROXY_ONLY    = "BLOCKED_POST_GAME_PROXY_ONLY"
BLOCKED_LOW_TIMESTAMP_COVERAGE  = "BLOCKED_LOW_TIMESTAMP_COVERAGE"


class ClvGateError(ValueError):
    """CLV gate 合約違規。"""


def evaluate_clv_readiness(
    snapshots: list,
    min_coverage: float = _MIN_TIMESTAMP_COVERAGE,
) -> dict:
    """
    評估一組 odds snapshots 是否具備 CLV 計算條件。

    Parameters
    ----------
    snapshots : list of dict or MlbOddsSnapshot
        每筆需包含 source_type 欄位（str 或 OddsSourceType）
    min_coverage : float
        pregame + closing 記錄的最低佔比門檻（預設 95%）

    Returns
    -------
    dict 包含：
      status     : CLV_READY 或 BLOCKED_*
      reason     : 說明
      counts     : 各 source_type 計數
      coverage   : pregame+closing / 總有效記錄
      paper_only : True
    """
    if not snapshots:
        return _blocked(BLOCKED_NO_PREGAME_ODDS, "no snapshots provided", {}, 0.0)

    # ── paper_only 守衛 ────────────────────────────────────────────────────
    for s in snapshots:
        po = s.get("paper_only") if isinstance(s, dict) else getattr(s, "paper_only", None)
        if po is False:
            raise ClvGateError(
                "[CLVGate] paper_only=false record detected."
            )

    # ── 計數各 source_type ────────────────────────────────────────────────
    counts: dict[str, int] = {
        OddsSourceType.OPENING.value:         0,
        OddsSourceType.PREGAME.value:         0,
        OddsSourceType.CLOSING.value:         0,
        OddsSourceType.POST_GAME_PROXY.value: 0,
        OddsSourceType.UNKNOWN.value:         0,
    }

    for s in snapshots:
        raw = s.get("source_type") if isinstance(s, dict) else getattr(s, "source_type", None)
        if isinstance(raw, OddsSourceType):
            key = raw.value
        elif isinstance(raw, str):
            key = raw
        else:
            key = OddsSourceType.UNKNOWN.value
        counts[key] = counts.get(key, 0) + 1

    total = len(snapshots)
    proxy_count   = counts.get(OddsSourceType.POST_GAME_PROXY.value, 0)
    pregame_count = counts.get(OddsSourceType.PREGAME.value, 0) + counts.get(OddsSourceType.OPENING.value, 0)
    closing_count = counts.get(OddsSourceType.CLOSING.value, 0)
    unknown_count = counts.get(OddsSourceType.UNKNOWN.value, 0)

    # 有效記錄（排除 UNKNOWN）
    valid_total = total - unknown_count
    if valid_total <= 0:
        return _blocked(BLOCKED_NO_PREGAME_ODDS, "all records are UNKNOWN", counts, 0.0)

    # ── Gate 1: 全為 POST_GAME_PROXY ──────────────────────────────────────
    if proxy_count == valid_total:
        return _blocked(
            BLOCKED_POST_GAME_PROXY_ONLY,
            f"all {proxy_count} valid records are POST_GAME_PROXY. "
            "Pregame timestamp required for CLV.",
            counts, 0.0,
        )

    # ── Gate 2: 無 PREGAME odds ───────────────────────────────────────────
    if pregame_count == 0:
        return _blocked(
            BLOCKED_NO_PREGAME_ODDS,
            "no PREGAME or OPENING odds records found",
            counts, 0.0,
        )

    # ── Gate 3: 無 CLOSING odds ───────────────────────────────────────────
    if closing_count == 0:
        return _blocked(
            BLOCKED_NO_CLOSING_ODDS,
            "no CLOSING odds records found. CLV requires closing line.",
            counts, closing_count / valid_total,
        )

    # ── Gate 4: timestamp coverage ────────────────────────────────────────
    coverage = (pregame_count + closing_count) / valid_total
    if coverage < min_coverage:
        return _blocked(
            BLOCKED_LOW_TIMESTAMP_COVERAGE,
            f"coverage={coverage:.1%} < {min_coverage:.0%}. "
            f"pregame={pregame_count}, closing={closing_count}, valid={valid_total}",
            counts, coverage,
        )

    # ── CLV_READY ─────────────────────────────────────────────────────────
    return {
        "status": CLV_READY,
        "reason": (
            f"pregame={pregame_count}, closing={closing_count}, "
            f"coverage={coverage:.1%} >= {min_coverage:.0%}"
        ),
        "counts": counts,
        "coverage": round(coverage, 4),
        "paper_only": True,
    }


def _blocked(status: str, reason: str, counts: dict, coverage: float) -> dict:
    return {
        "status": status,
        "reason": reason,
        "counts": counts,
        "coverage": round(coverage, 4),
        "paper_only": True,
    }
