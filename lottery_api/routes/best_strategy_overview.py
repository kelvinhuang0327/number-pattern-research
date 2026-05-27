"""
Best Strategy Overview API (P95)

GET  /api/best-strategy-overview
     → RankingCard[] read from P94A/B/C benchmark JSON artifacts (NOT DB)
GET  /api/best-strategy-overview/{strategy_id}/next-prediction
     → NextPrediction from adapter runner (NOT DB write)

IMPORTANT:
  - Does NOT query or mutate DB for ranking data.
  - Does NOT insert replay rows.
  - Does NOT promote lifecycle.
  - All ranking data sourced from benchmark JSON artifacts.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

_api_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _api_root not in sys.path:
    sys.path.insert(0, _api_root)

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Artifact paths ─────────────────────────────────────────────────────────────
_REPO_ROOT = Path(_api_root).parent
_ARTIFACTS: Dict[str, Path] = {
    "BIG_LOTTO":    _REPO_ROOT / "outputs" / "replay" / "p94a_biglotto_all_strategy_betcount_benchmark_20260526.json",
    "POWER_LOTTO":  _REPO_ROOT / "outputs" / "replay" / "p94b_powerlotto_all_strategy_betcount_benchmark_20260527.json",
    "DAILY_539":    _REPO_ROOT / "outputs" / "replay" / "p94c_daily539_all_strategy_betcount_benchmark_20260526.json",
}

_VALID_LOTTERY_TYPES     = ("BIG_LOTTO", "POWER_LOTTO", "DAILY_539")
_VALID_BET_COUNTS        = (1, 2, 3, 5)
_VALID_WINDOWS           = (30, 100, 500, 1500)
_VALID_RANKING_METRICS   = ("m3plus_rate", "avg_hit_count", "m4plus_rate", "stability_score")

_DISCLAIMER = (
    "Benchmark ranking does not guarantee next-draw performance. "
    "Past edge is not a predictor of future returns."
)

# Lifecycle statuses that require a caveat
_CAVEAT_MAP = {
    "REJECTED":    "REJECTED: historical benchmark only",
    "OFFLINE":     "OFFLINE: decommissioned",
    "DRY_RUN":     "DRY_RUN: not yet production",
    "PROVISIONAL": "DRY_RUN: not yet production",
    "RETIRED":     "OFFLINE: decommissioned",
}

# Lifecycle sort priority (lower = shown first)
_LIFECYCLE_PRIORITY = {
    "PRODUCTION": 0, "ONLINE": 1, "DRY_RUN": 2, "PROVISIONAL": 2,
    "OBSERVATION": 3, "OFFLINE": 4, "RETIRED": 4, "REJECTED": 5,
}


# ── Artifact loading (cached per process) ─────────────────────────────────────

_cache: Dict[str, Any] = {}

def _load_artifact(lottery_type: str) -> Dict:
    if lottery_type not in _cache:
        path = _ARTIFACTS.get(lottery_type)
        if not path or not path.exists():
            return {}
        with open(path) as f:
            _cache[lottery_type] = json.load(f)
    return _cache.get(lottery_type, {})


def _artifact_available(lottery_type: str) -> bool:
    path = _ARTIFACTS.get(lottery_type)
    return bool(path and path.exists())


# ── Normalise raw entry → RankingCard ─────────────────────────────────────────

def _caveat(lifecycle: str) -> Optional[str]:
    return _CAVEAT_MAP.get(str(lifecycle).upper())


def _warn_flags(card: dict) -> List[str]:
    flags = []
    if (card.get("sample_size") or 0) < 100:
        flags.append("SMALL_SAMPLE")
    if card.get("benchmark_only"):
        flags.append("BENCHMARK_ONLY")
    cav = card.get("rejected_or_offline_caveat")
    if cav and "REJECTED" in cav:
        flags.append("REJECTED_STRATEGY")
    elif cav and ("OFFLINE" in cav or "decommissioned" in cav):
        flags.append("REJECTED_STRATEGY")
    return flags


def _normalise_biglotto_entry(raw: dict, window: int, bet_count: int) -> dict:
    lifecycle = raw.get("lifecycle", "")
    caveat = _caveat(lifecycle)
    card = {
        "strategy_id":              raw.get("strategy_id", ""),
        "display_name":             raw.get("display_name", raw.get("strategy_id", "")),
        "lottery_type":             "BIG_LOTTO",
        "bet_count":                bet_count,
        "observation_window":       window,
        "lifecycle_status":         lifecycle,
        "source_category":          raw.get("source_category", "row-backed"),
        "row_backed":               raw.get("data_source", "") == "db_rows",
        "benchmark_only":           raw.get("data_source", "") != "db_rows",
        "adapter_generated":        False,
        "rejected_or_offline_caveat": caveat,
        "sample_size":              raw.get("sample_size", 0),
        "m3plus_rate":              raw.get("m3_plus_rate") or raw.get("m3plus_rate"),
        "avg_hit_count":            raw.get("avg_hit_count"),
        "m4plus_rate":              raw.get("m4_plus_rate") or raw.get("m4plus_rate"),
        "m5_rate":                  raw.get("m5_plus_rate") or raw.get("m5_rate"),
        "m6_rate":                  raw.get("m6_rate"),
        "zero_hit_rate":            raw.get("zero_hit_rate"),
        "special_hit_rate":         None,  # BIG_LOTTO has no special ball
        "stability_score":          None,
        "stability_across_windows": {},
        "warning_flags":            [],
    }
    card["warning_flags"] = _warn_flags(card)
    return card


def _normalise_powerlotto_entry(raw: dict, window: int, bet_count: int) -> dict:
    lifecycle = raw.get("lifecycle", "")
    caveat = _caveat(lifecycle)
    source_cat = raw.get("source_category", "row-backed")
    card = {
        "strategy_id":              raw.get("strategy_id", ""),
        "display_name":             raw.get("display_name", raw.get("strategy_id", "")),
        "lottery_type":             "POWER_LOTTO",
        "bet_count":                bet_count,
        "observation_window":       window,
        "lifecycle_status":         lifecycle,
        "source_category":          source_cat,
        "row_backed":               "row" in source_cat.lower() or raw.get("data_source", "") == "db_rows",
        "benchmark_only":           "adapter" in source_cat.lower() or raw.get("data_source", "") == "adapter",
        "adapter_generated":        "adapter" in source_cat.lower(),
        "rejected_or_offline_caveat": caveat,
        "sample_size":              raw.get("sample_size", 0),
        "m3plus_rate":              raw.get("m3plus_rate") or raw.get("m3_plus_rate"),
        "avg_hit_count":            raw.get("avg_best_main_hit") or raw.get("avg_hit_count"),
        "m4plus_rate":              raw.get("m4plus_rate") or raw.get("m4_plus_rate"),
        "m5_rate":                  raw.get("m5plus_rate") or raw.get("m5_rate"),
        "m6_rate":                  None,  # POWER_LOTTO: no m6 concept
        "zero_hit_rate":            raw.get("zero_hit_rate"),
        "special_hit_rate":         raw.get("special_hit_rate"),  # required for POWER_LOTTO
        "stability_score":          None,
        "stability_across_windows": {},
        "warning_flags":            [],
    }
    card["warning_flags"] = _warn_flags(card)
    return card


def _normalise_daily539_entry(raw: dict, window: int, bet_count: int) -> dict:
    lifecycle = raw.get("lifecycle", "")
    caveat = _caveat(lifecycle)
    source = raw.get("source", raw.get("source_category", ""))
    row_backed = "DB_ROW" in source.upper() or "row" in source.lower()
    card = {
        "strategy_id":              raw.get("strategy_id", ""),
        "display_name":             raw.get("display_name", raw.get("strategy_id", "")),
        "lottery_type":             "DAILY_539",
        "bet_count":                bet_count,
        "observation_window":       window,
        "lifecycle_status":         lifecycle,
        "source_category":          raw.get("source_category", source),
        "row_backed":               row_backed,
        "benchmark_only":           not row_backed,
        "adapter_generated":        False,
        "rejected_or_offline_caveat": caveat,
        "sample_size":              raw.get("sample_size", 0),
        "m3plus_rate":              raw.get("m3_rate") or raw.get("m3plus_rate"),
        "avg_hit_count":            raw.get("avg_hit_count"),
        "m4plus_rate":              raw.get("m4_rate") or raw.get("m4plus_rate"),
        "m5_rate":                  raw.get("m5_rate"),
        "m6_rate":                  None,  # DAILY_539: no m6
        "zero_hit_rate":            raw.get("zero_hit_rate"),
        "special_hit_rate":         None,  # DAILY_539 has no special ball
        "stability_score":          None,
        "stability_across_windows": {},
        "warning_flags":            [],
    }
    card["warning_flags"] = _warn_flags(card)
    return card


# ── Extract ranked entries from each artifact ──────────────────────────────────

def _get_biglotto_ranking(window: int, bet_count: int) -> List[dict]:
    data = _load_artifact("BIG_LOTTO")
    if not data:
        return []
    rt = data.get("ranking_tables", {})
    win_entries = rt.get(str(window), {})
    raw_list = win_entries.get(str(bet_count), [])
    cards = []
    for raw in raw_list:
        card = _normalise_biglotto_entry(raw, window, bet_count)
        card["rank"] = raw.get("rank", len(cards) + 1)
        cards.append(card)
    return cards


def _get_powerlotto_ranking(window: int, bet_count: int) -> List[dict]:
    data = _load_artifact("POWER_LOTTO")
    if not data:
        return []
    ranks = data.get("rankings", {})
    win_key = f"window_{window}"
    bet_key = f"bet_{bet_count}"
    win_data = ranks.get(win_key, {})
    bet_data = win_data.get(bet_key, {})
    raw_list = bet_data.get("top3", [])
    cards = []
    for raw in raw_list:
        card = _normalise_powerlotto_entry(raw, window, bet_count)
        card["rank"] = raw.get("rank", len(cards) + 1)
        cards.append(card)
    return cards


def _get_daily539_ranking(window: int, bet_count: int) -> List[dict]:
    data = _load_artifact("DAILY_539")
    if not data:
        return []
    rt = data.get("ranking_tables", {})
    key = f"top3_w{window}_bet{bet_count}"
    raw_list = rt.get(key, [])
    cards = []
    for raw in raw_list:
        card = _normalise_daily539_entry(raw, window, bet_count)
        card["rank"] = raw.get("rank", len(cards) + 1)
        cards.append(card)
    return cards


# ── Attach stability_across_windows from all_results ──────────────────────────

def _attach_stability_biglotto(cards: List[dict]) -> None:
    data = _load_artifact("BIG_LOTTO")
    if not data:
        return
    rt = data.get("ranking_tables", {})
    for card in cards:
        sid = card["strategy_id"]
        bc = card["bet_count"]
        stability = {}
        vals = []
        for w in _VALID_WINDOWS:
            entries = rt.get(str(w), {}).get(str(bc), [])
            match = next((e for e in entries if e.get("strategy_id") == sid), None)
            if match:
                rate = match.get("m3_plus_rate") or match.get("m3plus_rate")
                ss = match.get("sample_size", 0)
                stability[str(w)] = {"m3plus_rate": rate, "sample_size": ss}
                if rate is not None and ss >= 30:
                    vals.append(rate)
        card["stability_across_windows"] = stability
        if len(vals) >= 2:
            import statistics
            mean = statistics.mean(vals)
            std = statistics.stdev(vals)
            card["stability_score"] = round(1.0 - (std / mean if mean > 0 else 0), 4)


def _attach_stability_powerlotto(cards: List[dict]) -> None:
    data = _load_artifact("POWER_LOTTO")
    if not data:
        return
    ranks = data.get("rankings", {})
    for card in cards:
        sid = card["strategy_id"]
        bc = card["bet_count"]
        stability = {}
        vals = []
        for w in _VALID_WINDOWS:
            win_key = f"window_{w}"
            bet_key = f"bet_{bc}"
            bet_data = ranks.get(win_key, {}).get(bet_key, {})
            match = next((e for e in bet_data.get("top3", []) if e.get("strategy_id") == sid), None)
            if match:
                rate = match.get("m3plus_rate")
                ss = match.get("sample_size", 0)
                stability[str(w)] = {"m3plus_rate": rate, "sample_size": ss}
                if rate is not None and ss >= 30:
                    vals.append(rate)
        card["stability_across_windows"] = stability
        if len(vals) >= 2:
            import statistics
            mean = statistics.mean(vals)
            std = statistics.stdev(vals)
            card["stability_score"] = round(1.0 - (std / mean if mean > 0 else 0), 4)


def _attach_stability_daily539(cards: List[dict]) -> None:
    data = _load_artifact("DAILY_539")
    if not data:
        return
    rt = data.get("ranking_tables", {})
    for card in cards:
        sid = card["strategy_id"]
        bc = card["bet_count"]
        stability = {}
        vals = []
        for w in _VALID_WINDOWS:
            key = f"top3_w{w}_bet{bc}"
            entries = rt.get(key, [])
            match = next((e for e in entries if e.get("strategy_id") == sid), None)
            if match:
                rate = match.get("m3_rate") or match.get("m3plus_rate")
                ss = match.get("sample_size", 0)
                stability[str(w)] = {"m3plus_rate": rate, "sample_size": ss}
                if rate is not None and ss >= 30:
                    vals.append(rate)
        card["stability_across_windows"] = stability
        if len(vals) >= 2:
            import statistics
            mean = statistics.mean(vals)
            std = statistics.stdev(vals)
            card["stability_score"] = round(1.0 - (std / mean if mean > 0 else 0), 4)


# ── Sort by ranking_metric ─────────────────────────────────────────────────────

def _sort_cards(cards: List[dict], ranking_metric: str) -> List[dict]:
    def key(c):
        lc = c.get("lifecycle_status", "")
        priority = _LIFECYCLE_PRIORITY.get(lc.upper(), 99)
        metric_val = c.get(ranking_metric) or 0
        return (priority, -(metric_val or 0))
    cards.sort(key=key)
    for i, c in enumerate(cards, start=1):
        c["rank"] = i
    return cards


# ── Next-prediction helpers ────────────────────────────────────────────────────

def _get_draw_history(lottery_type: str, limit: int = 200) -> List[dict]:
    """Fetch recent draw history from DB (read-only)."""
    try:
        from database import DatabaseManager
    except ImportError:
        try:
            from lottery_api.database import DatabaseManager
        except ImportError:
            return []
    try:
        db = DatabaseManager()
        rows = db.get_draw_history(lottery_type, limit=limit)
        return rows if rows else []
    except Exception as e:
        logger.warning(f"Could not load draw history for {lottery_type}: {e}")
        return []


def _run_adapter_predict(strategy_id: str, lottery_type: str) -> dict:
    """Call adapter to generate next-period prediction. Returns NextPrediction dict."""
    from lottery_api.models.replay_strategy_registry import (
        get_adapter, _REGISTRY, _ALL_ADAPTERS,
        UnsupportedLotteryType, InsufficientHistory,
        list_strategies,
    )
    # Check lifecycle first
    lifecycle = None
    for a in _ALL_ADAPTERS:
        if a.meta.strategy_id == strategy_id:
            lifecycle = a.meta.lifecycle_status
            break

    # Rejected/offline → blocked
    if lifecycle and lifecycle.upper() in ("REJECTED", "OFFLINE", "RETIRED"):
        return {
            "next_draw_lottery_type": lottery_type,
            "next_draw_source": "adapter",
            "next_draw_number": None,
            "prediction_generated_at": datetime.now(timezone.utc).isoformat(),
            "strategy_id": strategy_id,
            "bet_count": None,
            "predicted_bets": None,
            "predicted_special": None,
            "adapter_name": None,
            "generation_status": "REJECTED_REPLAY_ONLY",
            "disclaimer": _DISCLAIMER,
        }

    # Adapter not in registry
    if strategy_id not in _REGISTRY:
        return {
            "next_draw_lottery_type": lottery_type,
            "next_draw_source": "adapter",
            "next_draw_number": None,
            "prediction_generated_at": datetime.now(timezone.utc).isoformat(),
            "strategy_id": strategy_id,
            "bet_count": None,
            "predicted_bets": None,
            "predicted_special": None,
            "adapter_name": None,
            "generation_status": "ADAPTER_MISSING",
            "disclaimer": _DISCLAIMER,
        }

    adapter = _REGISTRY[strategy_id]

    # Check lottery type support
    if lottery_type not in adapter.meta.supported_lottery_types:
        return {
            "next_draw_lottery_type": lottery_type,
            "next_draw_source": "adapter",
            "next_draw_number": None,
            "prediction_generated_at": datetime.now(timezone.utc).isoformat(),
            "strategy_id": strategy_id,
            "bet_count": adapter.meta.native_bets if hasattr(adapter.meta, "native_bets") else None,
            "predicted_bets": None,
            "predicted_special": None,
            "adapter_name": strategy_id,
            "generation_status": "UNSUPPORTED_BET_COUNT",
            "disclaimer": _DISCLAIMER,
        }

    history = _get_draw_history(lottery_type)
    if not history:
        return {
            "next_draw_lottery_type": lottery_type,
            "next_draw_source": "adapter",
            "next_draw_number": None,
            "prediction_generated_at": datetime.now(timezone.utc).isoformat(),
            "strategy_id": strategy_id,
            "bet_count": None,
            "predicted_bets": None,
            "predicted_special": None,
            "adapter_name": strategy_id,
            "generation_status": "SOURCE_UNAVAILABLE",
            "disclaimer": _DISCLAIMER,
        }

    try:
        numbers, special = adapter.get_one_bet(history, lottery_type)
        # POWER_LOTTO: special is a separate field; BIG_LOTTO + DAILY_539: null
        predicted_special = special if lottery_type == "POWER_LOTTO" else None
        return {
            "next_draw_lottery_type": lottery_type,
            "next_draw_source": "adapter",
            "next_draw_number": None,
            "prediction_generated_at": datetime.now(timezone.utc).isoformat(),
            "strategy_id": strategy_id,
            "bet_count": 1,
            "predicted_bets": [numbers],
            "predicted_special": predicted_special,
            "adapter_name": strategy_id,
            "generation_status": "READY",
            "disclaimer": _DISCLAIMER,
        }
    except UnsupportedLotteryType:
        gen_status = "UNSUPPORTED_BET_COUNT"
    except InsufficientHistory:
        gen_status = "SOURCE_UNAVAILABLE"
    except Exception as e:
        logger.warning(f"Adapter {strategy_id} failed: {e}")
        gen_status = "ADAPTER_MISSING"

    return {
        "next_draw_lottery_type": lottery_type,
        "next_draw_source": "adapter",
        "next_draw_number": None,
        "prediction_generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy_id": strategy_id,
        "bet_count": None,
        "predicted_bets": None,
        "predicted_special": None,
        "adapter_name": strategy_id,
        "generation_status": gen_status,
        "disclaimer": _DISCLAIMER,
    }


# ── API Routes ─────────────────────────────────────────────────────────────────

@router.get("/api/best-strategy-overview")
async def get_best_strategy_overview(
    lottery_type:      str = Query(..., description="BIG_LOTTO | POWER_LOTTO | DAILY_539"),
    bet_count:         int = Query(..., description="1 | 2 | 3 | 5"),
    observation_window: int = Query(1500, description="30 | 100 | 500 | 1500"),
    ranking_metric:    str = Query("m3plus_rate", description="m3plus_rate | avg_hit_count | m4plus_rate | stability_score"),
):
    """
    Best Strategy Overview — ranked RankingCard[] for 最佳策略總覽.

    Data source: P94A/B/C benchmark JSON artifacts (NOT DB queries).
    No DB writes. No replay row inserts.
    """
    if lottery_type not in _VALID_LOTTERY_TYPES:
        raise HTTPException(400, f"Invalid lottery_type. Valid: {_VALID_LOTTERY_TYPES}")
    if bet_count not in _VALID_BET_COUNTS:
        raise HTTPException(400, f"Invalid bet_count. Valid: {_VALID_BET_COUNTS}")
    if observation_window not in _VALID_WINDOWS:
        raise HTTPException(400, f"Invalid observation_window. Valid: {_VALID_WINDOWS}")
    if ranking_metric not in _VALID_RANKING_METRICS:
        raise HTTPException(400, f"Invalid ranking_metric. Valid: {_VALID_RANKING_METRICS}")

    if not _artifact_available(lottery_type):
        return {
            "lottery_type": lottery_type,
            "bet_count": bet_count,
            "observation_window": observation_window,
            "ranking_metric": ranking_metric,
            "generation_status": "SOURCE_UNAVAILABLE",
            "cards": [],
            "disclaimer": _DISCLAIMER,
        }

    if lottery_type == "BIG_LOTTO":
        cards = _get_biglotto_ranking(observation_window, bet_count)
        _attach_stability_biglotto(cards)
    elif lottery_type == "POWER_LOTTO":
        cards = _get_powerlotto_ranking(observation_window, bet_count)
        _attach_stability_powerlotto(cards)
    else:
        cards = _get_daily539_ranking(observation_window, bet_count)
        _attach_stability_daily539(cards)

    cards = _sort_cards(cards, ranking_metric)

    return {
        "lottery_type":      lottery_type,
        "bet_count":         bet_count,
        "observation_window": observation_window,
        "ranking_metric":    ranking_metric,
        "generation_status": "READY",
        "cards":             cards,
        "disclaimer":        _DISCLAIMER,
    }


@router.get("/api/best-strategy-overview/{strategy_id}/next-prediction")
async def get_next_prediction(
    strategy_id:  str,
    lottery_type: str = Query(..., description="BIG_LOTTO | POWER_LOTTO | DAILY_539"),
):
    """
    Next-period prediction for a specific strategy.

    Data source: adapter runner (NOT DB write).
    - POWER_LOTTO: predicted_special shown separately.
    - BIG_LOTTO + DAILY_539: predicted_special = null.
    - Rejected/offline strategies → REJECTED_REPLAY_ONLY.
    - Missing adapter → ADAPTER_MISSING.
    - Unsupported bet count → UNSUPPORTED_BET_COUNT.
    """
    if lottery_type not in _VALID_LOTTERY_TYPES:
        raise HTTPException(400, f"Invalid lottery_type. Valid: {_VALID_LOTTERY_TYPES}")

    result = _run_adapter_predict(strategy_id, lottery_type)
    return result


@router.get("/api/best-strategy-overview/meta/available-artifacts")
async def get_available_artifacts():
    """List which lottery types have benchmark artifacts available."""
    return {
        lottery: _artifact_available(lottery)
        for lottery in _VALID_LOTTERY_TYPES
    }
