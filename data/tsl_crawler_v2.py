from __future__ import annotations

import json
import ssl
import subprocess
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from data.fetch_status import write_tsl_fetch_status
from data.tsl_frontend_probe import probe_tsl_frontend, save_tsl_frontend_probe
from data.tsl_snapshot import save_tsl_snapshot


@dataclass
class TSLOdds:
    match_id: str
    home_team: str
    away_team: str
    game_time: str
    markets: dict[str, dict[str, Any]]


class TSLCrawlerV2:
    def __init__(self, use_mock: bool = False):
        self.legacy_base_url = "https://www.sportslottery.com.tw/api/v1"
        self.modern_blob_url = "https://blob3rd.sportslottery.com.tw/apidata"
        self.use_mock = use_mock
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://www.sportslottery.com.tw",
            "Referer": "https://www.sportslottery.com.tw/zh-tw/game/pre-match?sportId=1",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

    def _ssl_context(self) -> ssl.SSLContext:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def _request_json(
        self,
        url: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        body = None
        request_headers = dict(self.headers)
        if headers:
            request_headers.update(headers)
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers=request_headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req, context=self._ssl_context(), timeout=10) as response:
                raw = response.read().decode("utf-8")
        except Exception as exc:
            raw = self._request_json_via_curl(
                url,
                method=method,
                payload=payload,
                headers=request_headers,
                original_error=exc,
            )
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            snippet = raw[:160].replace("\n", " ")
            raise ValueError(f"non-json response from {url}: {snippet}") from exc

    def _request_json_via_curl(
        self,
        url: str,
        *,
        method: str,
        payload: dict[str, Any] | None,
        headers: dict[str, str],
        original_error: Exception,
    ) -> str:
        command = ["curl", "-L", "-sS", "-X", method.upper(), url]
        for key, value in headers.items():
            command.extend(["-H", f"{key}: {value}"])
        if payload is not None:
            command.extend(["--data", json.dumps(payload, ensure_ascii=False)])
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except Exception as curl_exc:  # pragma: no cover - exercised via environment behavior
            raise original_error from curl_exc
        return completed.stdout

    def _compute_decimal_odds(self, selection: dict[str, Any]) -> float | None:
        try:
            payout_unit = float(selection.get("pu"))
            price_denom = float(selection.get("pd"))
        except (TypeError, ValueError):
            return None
        if price_denom <= 0:
            return None
        return round(1.0 + (payout_unit / price_denom), 4)

    def _map_modern_market_code(self, market_name: str) -> str | None:
        name = str(market_name or "").strip()
        if not name:
            return None
        if "前五局" in name and "不讓分" in name:
            return "FMNL"
        if "單雙" in name:
            return "OE"
        if "大小" in name and "總分" in name:
            return "OU"
        if "不讓分" in name:
            return "MNL"
        if "讓分" in name:
            return "HDC"
        if "大小" in name:
            return "TTO"
        return None

    def _normalize_modern_selection(self, selection: dict[str, Any]) -> dict[str, Any] | None:
        decimal_odds = self._compute_decimal_odds(selection)
        if decimal_odds is None:
            return None
        return {
            "outcomeName": str(selection.get("name", "")),
            "odds": f"{decimal_odds:.2f}",
            "specialBetValue": selection.get("hv"),
        }

    def _normalize_modern_game(self, game: dict[str, Any]) -> dict[str, Any] | None:
        if str(game.get("san", "")).upper() != "BSB":
            return None
        home_team = str(game.get("hn") or "").strip()
        away_team = str(game.get("an") or "").strip()
        game_time = str(game.get("kt") or "").strip()
        if not home_team or not away_team or not game_time:
            return None

        markets: list[dict[str, Any]] = []
        for market in game.get("ms", []) or []:
            market_code = self._map_modern_market_code(str(market.get("name", "")))
            if not market_code:
                continue
            outcomes = []
            for selection in market.get("cs", []) or []:
                normalized = self._normalize_modern_selection(selection)
                if normalized:
                    outcomes.append(normalized)
            if len(outcomes) < 2:
                continue
            markets.append(
                {
                    "marketCode": market_code,
                    "outcomes": outcomes,
                }
            )

        if not markets:
            return None

        return {
            "gameId": str(game.get("id", "")),
            "homeTeamName": home_team,
            "awayTeamName": away_team,
            "gameTime": game_time,
            "markets": markets,
        }

    def _fetch_modern_sports(self) -> list[dict[str, Any]]:
        url = f"{self.modern_blob_url}/Pre/Sports.zh.json"
        data = self._request_json(url)
        return data if isinstance(data, list) else []

    def _fetch_modern_pre_games(self, sport_id: str, lang: str = "zh") -> list[dict[str, Any]]:
        url = f"{self.modern_blob_url}/Pre/{sport_id}-Games.{lang}.json"
        data = self._request_json(url)
        return data if isinstance(data, list) else []

    def _fetch_modern_live_games(self) -> list[dict[str, Any]]:
        url = f"{self.modern_blob_url}/Live/Games.zh.json"
        data = self._request_json(url)
        return data if isinstance(data, list) else []

    def _fetch_modern_baseball_games(self) -> tuple[list[dict[str, Any]], list[str]]:
        diagnostics: list[str] = []
        normalized_games: list[dict[str, Any]] = []

        live_games = self._fetch_modern_live_games()
        diagnostics.append(f"modern_live={len(live_games)}")
        live_baseball_count = 0
        for game in live_games:
            normalized = self._normalize_modern_game(game)
            if normalized:
                live_baseball_count += 1
                normalized_games.append(normalized)
        diagnostics.append(f"modern_live_baseball={live_baseball_count}")

        sports = self._fetch_modern_sports()
        baseball_sport_id = ""
        for sport in sports:
            if str(sport.get("abb", "")).upper() == "BSB":
                baseball_sport_id = str(sport.get("id", ""))
                break

        if baseball_sport_id:
            diagnostics.append(f"modern_baseball_sport_id={baseball_sport_id}")
            preferred_langs = ("zh", "en")
            for lang in preferred_langs:
                try:
                    pre_games = self._fetch_modern_pre_games(baseball_sport_id, lang)
                except Exception as exc:  # pragma: no cover - exercised via behavior tests
                    diagnostics.append(f"modern_pre_{lang}={exc}")
                    continue
                diagnostics.append(f"modern_pre_{lang}={len(pre_games)}")
                for game in pre_games:
                    normalized = self._normalize_modern_game(game)
                    if normalized:
                        normalized_games.append(normalized)
                # Prefer zh when available to keep team names aligned with our mapping layer.
                if pre_games:
                    break

        deduped: dict[str, dict[str, Any]] = {}
        for game in normalized_games:
            deduped[str(game.get("gameId", ""))] = game
        return list(deduped.values()), diagnostics

    def _fetch_legacy_baseball_games(self) -> list[dict[str, Any]]:
        endpoint = f"{self.legacy_base_url}/game/list"
        payload = {
            "sportId": "1",
            "marketGroupId": "0",
            "lan": "zh-TW",
        }
        data = self._request_json(endpoint, method="POST", payload=payload)
        return data.get("data", []) if isinstance(data, dict) else []

    def fetch_baseball_games(self, force_closing: bool = False) -> list[dict[str, Any]]:
        if self.use_mock:
            games = self._get_mock_data()
            write_tsl_fetch_status(
                success=True,
                games_count=len(games),
                source="TSL_API_V2_MOCK",
                note="mock mode enabled",
            )
            return games

        diagnostics: list[str] = []
        try:
            modern_games, modern_notes = self._fetch_modern_baseball_games()
            diagnostics.extend(modern_notes)
            if modern_games:
                save_tsl_snapshot(games=modern_games, source="TSL_BLOB3RD", force_closing=force_closing)
                write_tsl_fetch_status(
                    success=True,
                    games_count=len(modern_games),
                    source="TSL_BLOB3RD",
                    note="; ".join(diagnostics),
                )
                return modern_games
        except Exception as exc:
            diagnostics.append(f"modern_fetch_failed={exc}")

        try:
            probe = probe_tsl_frontend()
            save_tsl_frontend_probe(probe)
            diagnostics.append(f"frontend_bundle={probe.bundle_url.rsplit('/', 1)[-1]}")
            diagnostics.append(f"frontend_baseball_markets={len(probe.baseball_market_catalog)}")
        except Exception as exc:
            diagnostics.append(f"frontend_probe_failed={exc}")

        try:
            legacy_games = self._fetch_legacy_baseball_games()
            if legacy_games:
                save_tsl_snapshot(games=legacy_games, source="TSL_API_V2", force_closing=force_closing)
                diagnostics.append(f"legacy_games={len(legacy_games)}")
                write_tsl_fetch_status(
                    success=True,
                    games_count=len(legacy_games),
                    source="TSL_API_V2",
                    note="; ".join(diagnostics),
                )
                return legacy_games
            diagnostics.append("legacy_games=0")
        except Exception as exc:
            diagnostics.append(f"legacy_fetch_failed={exc}")

        note = "; ".join(diagnostics) or "no data returned from modern or legacy endpoints"
        write_tsl_fetch_status(
            success=False,
            games_count=0,
            source="TSL_MULTI_SOURCE",
            error=note,
            note=note,
        )
        print(f"Error fetching TSL data: {note}")
        return []

    def _get_mock_data(self) -> list[dict[str, Any]]:
        return []


if __name__ == "__main__":
    crawler = TSLCrawlerV2(use_mock=False)
    games = crawler.fetch_baseball_games()
    print(f"Fetched {len(games)} games.")
