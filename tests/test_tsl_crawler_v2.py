from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_normalize_modern_game_converts_realistic_blob3rd_shape():
    from data.tsl_crawler_v2 import TSLCrawlerV2

    crawler = TSLCrawlerV2()
    normalized = crawler._normalize_modern_game(
        {
            "id": "3450001.1",
            "an": "中華台北",
            "hn": "日本",
            "kt": "2026-03-14T18:00:00+08:00",
            "san": "BSB",
            "ms": [
                {
                    "name": "不讓分",
                    "cs": [
                        {"name": "中華台北", "pd": "20", "pu": "27", "hv": None},
                        {"name": "日本", "pd": "100", "pu": "33", "hv": None},
                    ],
                },
                {
                    "name": "[總分]大小 7.5",
                    "cs": [
                        {"name": "大 7.5", "pd": "10", "pu": "8", "hv": "7.5"},
                        {"name": "小 7.5", "pd": "10", "pu": "9", "hv": "7.5"},
                    ],
                },
            ],
        }
    )

    assert normalized is not None
    assert normalized["homeTeamName"] == "日本"
    assert normalized["awayTeamName"] == "中華台北"
    assert normalized["markets"][0]["marketCode"] == "MNL"
    assert normalized["markets"][0]["outcomes"][0]["odds"] == "2.35"
    assert normalized["markets"][1]["marketCode"] == "OU"
    assert normalized["markets"][1]["outcomes"][0]["specialBetValue"] == "7.5"


def test_fetch_baseball_games_falls_back_and_records_diagnostics(monkeypatch):
    from data.tsl_crawler_v2 import TSLCrawlerV2

    crawler = TSLCrawlerV2()
    writes = []
    snapshots = []

    monkeypatch.setattr(
        crawler,
        "_fetch_modern_baseball_games",
        lambda: ([], ["modern_live=0", "modern_pre_zh=AccessDenied"]),
    )
    monkeypatch.setattr(
        crawler,
        "_fetch_legacy_baseball_games",
        lambda: [
            {
                "gameId": "9001",
                "homeTeamName": "日本",
                "awayTeamName": "中華台北",
                "gameTime": "2026-03-14T18:00:00+08:00",
                "markets": [],
            }
        ],
    )
    monkeypatch.setattr(
        "data.tsl_crawler_v2.save_tsl_snapshot",
        lambda *, games, source, force_closing=False: snapshots.append((source, games)),
    )
    monkeypatch.setattr(
        "data.tsl_crawler_v2.write_tsl_fetch_status",
        lambda **kwargs: writes.append(kwargs),
    )

    games = crawler.fetch_baseball_games()

    assert len(games) == 1
    assert snapshots[0][0] == "TSL_API_V2"
    assert writes[-1]["success"] is True
    assert "modern_pre_zh=AccessDenied" in writes[-1]["note"]


def test_fetch_modern_baseball_games_uses_language_payloads(monkeypatch):
    from data.tsl_crawler_v2 import TSLCrawlerV2

    crawler = TSLCrawlerV2()

    monkeypatch.setattr(crawler, "_fetch_modern_live_games", lambda: [])
    monkeypatch.setattr(crawler, "_fetch_modern_sports", lambda: [{"id": "34731.1", "abb": "BSB"}])

    seen_langs = []

    def fake_pre_games(sport_id: str, lang: str = "zh"):
        seen_langs.append((sport_id, lang))
        assert sport_id == "34731.1"
        if lang != "zh":
            return []
        return [
            {
                "id": "3452400.1",
                "an": "南韓",
                "hn": "多明尼加",
                "kt": "2026-03-14T06:30:00+08:00",
                "san": "BSB",
                "ms": [
                    {
                        "name": "不讓分",
                        "cs": [
                            {"name": "南韓", "pd": "10", "pu": "37", "hv": None},
                            {"name": "多明尼加", "pd": "20", "pu": "1", "hv": None},
                        ],
                    }
                ],
            }
        ]

    monkeypatch.setattr(crawler, "_fetch_modern_pre_games", fake_pre_games)

    games, diagnostics = crawler._fetch_modern_baseball_games()

    assert seen_langs == [("34731.1", "zh")]
    assert len(games) == 1
    assert games[0]["homeTeamName"] == "多明尼加"
    assert "modern_pre_zh=1" in diagnostics
