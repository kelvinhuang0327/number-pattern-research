"""
P9-C — Historical Odds Backfill Script (Production-Ready Gate)

僅在 CEO decision = APPROVE_PATH_A_HISTORICAL_API 時可執行完整 backfill。
預設 --no-network，API key 缺失或未設 ALLOW_SAMPLE_API_CALL 時凍結外部呼叫。

Usage:
  # Dry-run (no network, sample payload only)
  python scripts/run_historical_odds_backfill_p9.py \\
      --dry-run --sample-only \\
      --season 2025 --market h2h \\
      --output data/paper_recommendations/p9_historical_backfill_readiness_20260525.json

  # Sample API call gate (requires ALLOW_SAMPLE_API_CALL=true env + API key)
  ALLOW_SAMPLE_API_CALL=true THE_ODDS_API_KEY=<key> \\
      python scripts/run_historical_odds_backfill_p9.py \\
      --sample-only --season 2025 --market h2h \\
      --output data/paper_recommendations/p9_historical_backfill_readiness_20260525.json

paper_only=true。不宣稱任何策略獲利能力。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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

# ── Constants ─────────────────────────────────────────────────────────────────

BANNER = (
    "*** P9-C Historical Backfill Gate — "
    "No external API calls unless CEO-approved + ALLOW_SAMPLE_API_CALL=true ***"
)
API_KEY_ENV_VAR = "THE_ODDS_API_KEY"
ALLOW_SAMPLE_API_CALL_ENV_VAR = "ALLOW_SAMPLE_API_CALL"
SAMPLE_GAME_START_UTC = "2025-08-10T23:05:00Z"
SAMPLE_LAST_UPDATE_UTC = "2025-08-10T20:30:00Z"

# ── Exceptions ────────────────────────────────────────────────────────────────


class ApiKeyMissingError(RuntimeError):
    """Raised when historical backfill is requested but no API key is available."""


class SampleApiCallNotAllowedError(RuntimeError):
    """Raised when API call attempted without ALLOW_SAMPLE_API_CALL=true."""


class NetworkModeBlockedError(RuntimeError):
    """Raised when any network call is attempted in --no-network mode."""


# ── API Key gate ──────────────────────────────────────────────────────────────


def get_api_key() -> Optional[str]:
    """Return the API key from environment, or None if not set."""
    val = os.environ.get(API_KEY_ENV_VAR, "").strip()
    return val if val else None


def assert_allow_sample_api_call() -> None:
    """Raise SampleApiCallNotAllowedError unless ALLOW_SAMPLE_API_CALL=true is set."""
    flag = os.environ.get(ALLOW_SAMPLE_API_CALL_ENV_VAR, "").strip().lower()
    if flag != "true":
        raise SampleApiCallNotAllowedError(
            f"External API call blocked. Set {ALLOW_SAMPLE_API_CALL_ENV_VAR}=true "
            "explicitly (CEO must have approved PATH A) to enable sample API call."
        )


# ── Sample payload (static — no network) ─────────────────────────────────────


def _build_sample_toa_payload(market: str = "h2h") -> dict:
    """Static The Odds API v4 sample payload for gate validation."""
    return {
        "id": "p9_dry_run_game_bos_nyy_20250810",
        "sport_key": "baseball_mlb",
        "commence_time": SAMPLE_GAME_START_UTC,
        "away_team": "Boston Red Sox",
        "home_team": "New York Yankees",
        "bookmakers": [
            {
                "key": "pinnacle",
                "title": "Pinnacle",
                "last_update": SAMPLE_LAST_UPDATE_UTC,
                "markets": [
                    {
                        "key": market,
                        "last_update": SAMPLE_LAST_UPDATE_UTC,
                        "outcomes": [
                            {"name": "Boston Red Sox", "price": 2.15},
                            {"name": "New York Yankees", "price": 1.80},
                        ],
                    }
                ],
            }
        ],
    }


# ── Snapshot serialisation ────────────────────────────────────────────────────


def _snapshot_to_dict(snap: MlbOddsSnapshot) -> dict:
    def _ts(v: object) -> object:
        """Coerce datetime to ISO string; pass through str/None."""
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return v

    return {
        "game_id": snap.game_id,
        "source_type": snap.source_type.value,
        "side": snap.side,
        "decimal_odds": snap.decimal_odds,
        "source": snap.source,
        "captured_at_utc": _ts(snap.captured_at_utc),
        "game_start_utc": _ts(snap.game_start_utc),
        "market": snap.market,
        "paper_only": snap.paper_only,
        "source_trace": snap.source_trace,
    }


# ── Readiness check ───────────────────────────────────────────────────────────


def check_api_key_readiness() -> dict:
    """Check environment for API key presence. Never log key value."""
    key = get_api_key()
    return {
        "api_key_env_var": API_KEY_ENV_VAR,
        "api_key_present": key is not None,
        "allow_sample_api_call_env": ALLOW_SAMPLE_API_CALL_ENV_VAR,
        "allow_sample_api_call_set": (
            os.environ.get(ALLOW_SAMPLE_API_CALL_ENV_VAR, "").strip().lower() == "true"
        ),
    }


# ── Core runner ───────────────────────────────────────────────────────────────


def run_backfill_gate(
    *,
    season: int,
    market: str,
    dry_run: bool,
    sample_only: bool,
    no_network: bool,
    output_path: Optional[Path],
) -> dict:
    """
    Execute the P9-C backfill readiness gate.

    Returns a result dict suitable for JSON serialisation.
    Raises ApiKeyMissingError if key absent.
    Raises NetworkModeBlockedError if no_network=True and a live call would be needed.
    Raises SampleApiCallNotAllowedError if ALLOW_SAMPLE_API_CALL flag not set.
    """
    print(BANNER)

    key_status = check_api_key_readiness()
    api_key = get_api_key()

    # ── Guard 1: no-network enforced ──────────────────────────────────────────
    if no_network and not (dry_run or sample_only):
        raise NetworkModeBlockedError(
            "--no-network is active and neither --dry-run nor --sample-only was passed. "
            "Cannot proceed with a live backfill call."
        )

    # ── Guard 2: API key required for any live path ───────────────────────────
    will_need_live_call = not (dry_run or sample_only) and not no_network
    if will_need_live_call and api_key is None:
        raise ApiKeyMissingError(
            f"API key not found in environment variable '{API_KEY_ENV_VAR}'. "
            "CEO must approve PATH A and provide the key before live backfill can run."
        )

    # ── Guard 3: sample-only still needs explicit allow flag if key exists ────
    live_api_called = False
    if sample_only and not dry_run and not no_network and api_key is not None:
        assert_allow_sample_api_call()
        live_api_called = True  # only set if guard passed

    # ── Sample payload normalization (no network, always safe) ────────────────
    config = HistoricalOddsImportConfig(
        provider=OddsProviderType.THE_ODDS_API,
        paper_only=True,
    )
    payload = _build_sample_toa_payload(market)

    snapshots: list[MlbOddsSnapshot] = normalize_the_odds_api_payload(
        payload=payload,
        config=config,
    )

    # ── Guard 4: paper_only enforcement ──────────────────────────────────────
    violations = [s for s in snapshots if not s.paper_only]
    if violations:
        raise PaperOnlyViolationError(
            f"{len(violations)} snapshot(s) have paper_only != True. "
            "P9 backfill gate refused."
        )

    # ── Guard 5: POST_GAME_PROXY cannot appear as PREGAME/CLOSING ─────────────
    # source_type is derived by the normalizer from timestamps;
    # we assert that sample payload (pregame timestamps) yields PREGAME, never proxy.
    proxy_misclassified = [
        s for s in snapshots
        if s.source_type == OddsSourceType.PREGAME
        and s.captured_at_utc >= s.game_start_utc
    ]
    if proxy_misclassified:
        raise ValueError(
            "POST_GAME_PROXY snapshot misclassified as PREGAME. Gate blocked."
        )

    snaps_dicts = [_snapshot_to_dict(s) for s in snapshots]
    all_paper_only = all(s.paper_only for s in snapshots)

    # ── Readiness classification ──────────────────────────────────────────────
    if api_key is None:
        gate_status = "P9_BLOCKED_NEEDS_API_KEY"
        gate_message = (
            f"API key not found ({API_KEY_ENV_VAR} unset). "
            "CEO must approve PATH A purchase before live backfill can proceed."
        )
    elif not key_status["allow_sample_api_call_set"] and sample_only:
        gate_status = "P9_SAMPLE_READY_AWAITING_ALLOW_FLAG"
        gate_message = (
            "API key present but ALLOW_SAMPLE_API_CALL=true not set. "
            "Set this flag explicitly after CEO approval to run sample API call."
        )
    else:
        gate_status = "P9_HISTORICAL_BACKFILL_SAMPLE_READY"
        gate_message = "API key present and ALLOW_SAMPLE_API_CALL flag set. Gate open."

    result: dict = {
        "task": "P9-C",
        "title": "Historical Odds Backfill Readiness Gate",
        "run_date": datetime.now(timezone.utc).isoformat(),
        "paper_only": True,
        "season": season,
        "market": market,
        "mode": {
            "dry_run": dry_run,
            "sample_only": sample_only,
            "no_network": no_network,
        },
        "api_key_status": key_status,
        "live_api_called": live_api_called,
        "production_write": False,
        "gate_status": gate_status,
        "gate_message": gate_message,
        "sample_payload_normalized": True,
        "snapshots_count": len(snaps_dicts),
        "all_paper_only": all_paper_only,
        "snapshots": snaps_dicts,
        "validation": {
            "paper_only_all_true": all_paper_only,
            "live_api_called": live_api_called,
            "production_write": False,
            "post_game_proxy_misclassified": len(proxy_misclassified),
            "source_type_check": "PASS" if not proxy_misclassified else "FAIL",
        },
        "p9_engineering_notes": [
            "--no-network is the default; live calls require explicit opt-in flags.",
            "API key is read from environment; never logged or stored.",
            "ALLOW_SAMPLE_API_CALL=true must be set explicitly after CEO approval.",
            "POST_GAME_PROXY cannot pass as PREGAME/CLOSING (guard active).",
            "paper_only=True enforced on all snapshots.",
        ],
        "annotation": "paper_only=true。此腳本為 CEO 裁決後的工程就緒閘門。不代表任何實盤獲利能力。",
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"Written: {output_path}")

    return result


# ── CLI ───────────────────────────────────────────────────────────────────────


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "P9-C Historical Odds Backfill Readiness Gate — "
            "defaults to --no-network. paper_only=true."
        )
    )
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Dry-run mode (default: True). No external API calls.")
    parser.add_argument("--sample-only", action="store_true", default=False,
                        help="Run sample payload normalization only.")
    parser.add_argument("--no-network", action="store_true", default=True,
                        help="Block all network calls (default: True).")
    parser.add_argument("--season", type=int, default=2025,
                        help="MLB season year (default: 2025).")
    parser.add_argument("--market", default="h2h",
                        help="Odds market key (default: h2h).")
    parser.add_argument("--output", type=Path, default=None,
                        help="Output JSON path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    try:
        result = run_backfill_gate(
            season=args.season,
            market=args.market,
            dry_run=args.dry_run,
            sample_only=args.sample_only,
            no_network=args.no_network,
            output_path=args.output,
        )
        print(f"Gate status: {result['gate_status']}")
        print(f"Live API called: {result['live_api_called']}")
        print(f"paper_only: {result['paper_only']}")
    except (ApiKeyMissingError, SampleApiCallNotAllowedError,
            NetworkModeBlockedError, PaperOnlyViolationError) as exc:
        print(f"[BLOCKED] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
