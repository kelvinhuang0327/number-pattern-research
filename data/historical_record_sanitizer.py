from __future__ import annotations

from copy import deepcopy
from typing import Any


def sanitize_historical_records(
    records: list[dict[str, Any]],
    *,
    result_source: str,
    tournament: str,
    default_odds_source: str = "",
    keep_unverified_odds: bool = False,
) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for record in records:
        item = deepcopy(record)
        item["tournament"] = item.get("tournament", tournament)
        item["result_source"] = item.get("result_source", result_source)
        item["result_verified"] = bool(item.get("result_verified", True))

        odds_source = item.get("odds_source", default_odds_source)
        odds_verified = bool(item.get("odds_verified", False))
        item["odds_source"] = odds_source
        item["odds_verified"] = odds_verified

        if not odds_verified and not keep_unverified_odds:
            item["tsl_odds"] = {}

        if item["result_verified"]:
            item["data_source"] = f"{result_source}|results_verified"
        else:
            item["data_source"] = f"{result_source}|results_unverified"
        sanitized.append(item)
    return sanitized
