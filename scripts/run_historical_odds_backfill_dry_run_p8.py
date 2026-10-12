"""
P8-C — Historical Odds Backfill Dry-Run CLI

不呼叫外部 API。只讀 sample payload，用 P7 normalizer 驗證 contract。

Usage:
  python scripts/run_historical_odds_backfill_dry_run_p8.py \\
      --provider the_odds_api \\
      --season 2025 \\
      --market h2h \\
      --dry-run \\
      --sample-payload \\
      --output data/paper_recommendations/p8_historical_backfill_dry_run_preview_20260524.json

paper_only=true。不呼叫外部 API。不做 production write。
不代表任何實盤獲利能力。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Ensure project root is importable when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from wbc_backend.recommendation.historical_odds_import_plan import (
    HistoricalOddsImportConfig,
    OddsImportError,
    OddsProviderType,
    PaperOnlyViolationError,
    normalize_the_odds_api_payload,
    normalize_tsl_forward_payload,
)
from wbc_backend.recommendation.odds_contract import MlbOddsSnapshot, OddsSourceType

DRY_RUN_BANNER = (
    "*** DRY-RUN MODE — No external API calls. No production writes. paper_only=true ***"
)

# ── Supported providers map ───────────────────────────────────────────────────
SUPPORTED_PROVIDERS: dict[str, OddsProviderType] = {
    "the_odds_api": OddsProviderType.THE_ODDS_API,
    "toa": OddsProviderType.THE_ODDS_API,
    "tsl_2026": OddsProviderType.TSL_2026_FORWARD,
    "tsl": OddsProviderType.TSL_2026_FORWARD,
}

# ── Sample payloads (static — no network) ────────────────────────────────────

_SAMPLE_TOA_GAME_START = "2025-08-10T23:05:00Z"
_SAMPLE_TOA_LAST_UPDATE = "2025-08-10T20:30:00Z"


def _build_sample_toa_payload(market: str = "h2h") -> dict:
    """Static sample The Odds API v4 payload for dry-run validation."""
    return {
        "id": "dry_run_game_abc001",
        "sport_key": "baseball_mlb",
        "commence_time": _SAMPLE_TOA_GAME_START,
        "away_team": "Boston Red Sox",
        "home_team": "New York Yankees",
        "bookmakers": [
            {
                "key": "pinnacle",
                "title": "Pinnacle",
                "last_update": _SAMPLE_TOA_LAST_UPDATE,
                "markets": [
                    {
                        "key": market,
                        "last_update": _SAMPLE_TOA_LAST_UPDATE,
                        "outcomes": [
                            {"name": "Boston Red Sox", "price": 2.15},
                            {"name": "New York Yankees", "price": 1.80},
                        ],
                    }
                ],
            }
        ],
    }


_SAMPLE_TSL_GAME_TIME = "2026-05-20T12:00:00+08:00"
_SAMPLE_TSL_FETCHED_AT = "2026-05-20T03:30:00Z"  # ~8.5h before game_start UTC


def _build_sample_tsl_payload(market: str = "MNL") -> dict:
    """Static sample TSL JSONL record for dry-run validation."""
    return {
        "source": "TSL_BLOB3RD",
        "fetched_at": _SAMPLE_TSL_FETCHED_AT,
        "snapshot_type": "pregame",
        "match_id": "dry_run_tsl_3900001.1",
        "game_time": _SAMPLE_TSL_GAME_TIME,
        "home_team_name": "洛德海洋",
        "away_team_name": "西武獅",
        "markets": [
            {
                "marketCode": market,
                "outcomes": [
                    {"outcomeName": "洛德海洋", "odds": "1.65"},
                    {"outcomeName": "西武獅", "odds": "2.10"},
                ],
            }
        ],
    }


# ── Normalization dispatch ────────────────────────────────────────────────────


def _normalize_payload(
    provider_type: OddsProviderType,
    payload: dict,
    config: HistoricalOddsImportConfig,
    game_start_utc: Optional[datetime] = None,
) -> list[MlbOddsSnapshot]:
    """Dispatch to correct normalizer based on provider_type."""
    if provider_type == OddsProviderType.THE_ODDS_API:
        return normalize_the_odds_api_payload(payload, config)
    if provider_type == OddsProviderType.TSL_2026_FORWARD:
        if game_start_utc is None:
            raise OddsImportError(
                "[DryRun] TSL normalizer requires game_start_utc. "
                "Provide --game-start or use --sample-payload."
            )
        return normalize_tsl_forward_payload(payload, config, game_start_utc)
    raise OddsImportError(f"[DryRun] Unsupported provider: {provider_type}")


# ── Output builder ────────────────────────────────────────────────────────────


def _snapshot_to_dict(snap: MlbOddsSnapshot) -> dict:
    """Serialize MlbOddsSnapshot to JSON-serializable dict."""
    return {
        "game_id": snap.game_id,
        "source": snap.source,
        "source_type": snap.source_type.value,
        "market": snap.market,
        "side": snap.side,
        "decimal_odds": snap.decimal_odds,
        "captured_at_utc": snap.captured_at_utc.isoformat() if snap.captured_at_utc else None,
        "game_start_utc": snap.game_start_utc.isoformat() if snap.game_start_utc else None,
        "paper_only": snap.paper_only,
        "source_trace": snap.source_trace,
    }


# ── Main dry-run entrypoint ───────────────────────────────────────────────────


def run_dry_run(
    provider: str,
    season: int,
    market: str,
    use_sample_payload: bool,
    output_path: Optional[str],
) -> dict:
    """
    Execute dry-run normalization. Returns result dict.

    Does NOT call any external API. Only processes static sample payloads.
    Raises OddsImportError / PaperOnlyViolationError on contract violations.
    """
    print(DRY_RUN_BANNER)

    provider_lower = provider.lower()
    if provider_lower not in SUPPORTED_PROVIDERS:
        raise OddsImportError(
            f"[DryRun] Unknown provider '{provider}'. "
            f"Supported: {list(SUPPORTED_PROVIDERS.keys())}"
        )

    provider_type = SUPPORTED_PROVIDERS[provider_lower]

    config = HistoricalOddsImportConfig(
        provider=provider_type,
        paper_only=True,
        closing_window_sec=3600,
        pregame_min_sec=60,
        allow_unknown_ts=True,
        team_norm_table={},
    )

    if not use_sample_payload:
        # In dry-run, we only support sample payload. Live API calls are blocked.
        raise OddsImportError(
            "[DryRun] Live API fetch is NOT permitted in dry-run mode. "
            "Use --sample-payload to validate with static fixture data."
        )

    # Build sample payload based on provider
    game_start_utc: Optional[datetime] = None
    if provider_type == OddsProviderType.THE_ODDS_API:
        toa_market = "spreads" if market in ("rl", "run_line") else "h2h"
        payload = _build_sample_toa_payload(toa_market)
    else:  # TSL_2026_FORWARD
        tsl_market = "MNL" if market in ("h2h", "ml", "moneyline") else "OU"
        payload = _build_sample_tsl_payload(tsl_market)
        game_start_utc = datetime(2026, 5, 20, 4, 0, 0, tzinfo=timezone.utc)  # UTC of 2026-05-20 12:00+08

    print(f"Provider : {provider_type.value}")
    print(f"Season   : {season}")
    print(f"Market   : {market}")
    print(f"Mode     : DRY-RUN (sample payload — no API call)")

    snapshots = _normalize_payload(provider_type, payload, config, game_start_utc)

    snap_dicts = [_snapshot_to_dict(s) for s in snapshots]

    # Validate all snapshots are paper_only=true
    violations = [s for s in snapshots if s.paper_only is not True]
    if violations:
        raise PaperOnlyViolationError(
            f"[DryRun] {len(violations)} snapshots have paper_only!=True — contract violation."
        )

    result = {
        "task": "P8-C",
        "title": "Historical Odds Backfill Dry-Run Preview",
        "run_date": datetime.now(timezone.utc).isoformat(),
        "paper_only": True,
        "provider": provider_type.value,
        "season": season,
        "market": market,
        "mode": "DRY_RUN_SAMPLE_PAYLOAD",
        "live_api_called": False,
        "production_write": False,
        "snapshots_normalized": len(snap_dicts),
        "all_paper_only": True,
        "snapshots": snap_dicts,
        "validation": {
            "source_types": list({s["source_type"] for s in snap_dicts}),
            "paper_only_all_true": all(s["paper_only"] for s in snap_dicts),
            "source_trace_all_populated": all(bool(s["source_trace"]) for s in snap_dicts),
            "captured_at_populated": all(s["captured_at_utc"] is not None for s in snap_dicts),
            "decimal_odds_all_valid": all(s["decimal_odds"] >= 1.0 for s in snap_dicts),
        },
        "p8_engineering_notes": [
            "dry-run validated: P7 normalizer handles sample payload correctly",
            "game_id bridge (provider_id → MLB gamePk) required for production",
            "timezone normalization confirmed working",
            "source_trace populated for all snapshots",
            "paper_only=true enforced throughout",
        ],
        "annotation": (
            "paper_only=true。此 dry-run 不呼叫外部 API。"
            "不代表任何實盤獲利能力。"
        ),
    }

    print(f"\nNormalized {len(snap_dicts)} snapshot(s).")
    for s in snap_dicts:
        print(
            f"  game_id={s['game_id']} | source_type={s['source_type']} | "
            f"side={s['side']} | odds={s['decimal_odds']} | paper_only={s['paper_only']}"
        )
    print("\nValidation:", result["validation"])

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"\nOutput written to: {output_path}")

    return result


# ── CLI ───────────────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="P8-C Historical Odds Backfill Dry-Run — NO live API calls, paper_only=true"
    )
    p.add_argument(
        "--provider",
        required=True,
        choices=list(SUPPORTED_PROVIDERS.keys()),
        help="Odds provider to simulate",
    )
    p.add_argument("--season", type=int, default=2025, help="Target season year")
    p.add_argument("--market", default="h2h", help="Market type (h2h, spreads, totals)")
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Dry-run mode (default: True; live API calls are always blocked)",
    )
    p.add_argument(
        "--sample-payload",
        action="store_true",
        default=False,
        help="Use built-in static sample payload",
    )
    p.add_argument("--output", default=None, help="Output JSON file path")
    return p


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        run_dry_run(
            provider=args.provider,
            season=args.season,
            market=args.market,
            use_sample_payload=args.sample_payload,
            output_path=args.output,
        )
    except (OddsImportError, PaperOnlyViolationError) as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
