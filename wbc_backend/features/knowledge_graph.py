"""
棒球知識圖譜特徵層 (Baseball Knowledge Graph Feature Layer)
============================================================
借鑑 MiroFish GraphRAG 設計思想，以本地 NetworkX + SQLite 實作。

圖譜節點類型：
  - 球員 (Pitcher / Batter)
  - 球隊 (Team)
  - 場館 (Venue)
  - 裁判 (Umpire)

圖譜邊類型：
  - pitcher → batter: 歷史對決記錄 (wOBA, K%, BB%, HR)
  - team → team: 球隊對球隊歷史勝負
  - pitcher → venue: 投手在各場館的表現
  - umpire → pitcher: 裁判對投手的好球帶偏好

Category K 輸出：20 個圖結構特徵 (全部為差值形式，支援 ML 模型)

設計原則：
  - 無外部服務依賴 (純 NetworkX + SQLite)
  - 防止 Look-ahead Leakage (所有查詢指定截止日期)
  - Fallback 至聯盟平均（邊不存在時）
"""
from __future__ import annotations

import logging
import math
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

try:
    import networkx as nx
    _NX_AVAILABLE = True
except ImportError:
    _NX_AVAILABLE = False

from wbc_backend.domain.schemas import Matchup, PitcherSnapshot, TeamSnapshot

logger = logging.getLogger(__name__)

# ── 預設路徑 ─────────────────────────────────────────────────────────────────
_DB_PATH = Path("data/baseball_knowledge_graph.db")

# ── 聯盟基準值（圖譜邊不存在時的 fallback） ──────────────────────────────────
_LEAGUE_WOBA_VS_SP = 0.317
_LEAGUE_K_PCT = 0.221
_LEAGUE_BB_PCT = 0.085
_LEAGUE_HR_RATE = 0.033
_LEAGUE_WIN_PCT = 0.500


# ══════════════════════════════════════════════════════════════════════════════
# 持久化 SQLite Schema
# ══════════════════════════════════════════════════════════════════════════════

_DDL = """
CREATE TABLE IF NOT EXISTS pitcher_batter_matchup (
    pitcher_id   TEXT NOT NULL,
    batter_id    TEXT NOT NULL,
    game_date    TEXT NOT NULL,   -- YYYY-MM-DD (用於截止日期過濾)
    at_bats      INTEGER DEFAULT 0,
    hits         INTEGER DEFAULT 0,
    walks        INTEGER DEFAULT 0,
    strikeouts   INTEGER DEFAULT 0,
    home_runs    INTEGER DEFAULT 0,
    woba_sum     REAL DEFAULT 0.0,
    PRIMARY KEY (pitcher_id, batter_id, game_date)
);

CREATE TABLE IF NOT EXISTS team_vs_team (
    home_team   TEXT NOT NULL,
    away_team   TEXT NOT NULL,
    game_date   TEXT NOT NULL,
    home_win    INTEGER DEFAULT 0,  -- 1=主隊勝, 0=客隊勝
    home_runs   INTEGER DEFAULT 0,
    away_runs   INTEGER DEFAULT 0,
    PRIMARY KEY (home_team, away_team, game_date)
);

CREATE TABLE IF NOT EXISTS pitcher_venue (
    pitcher_id   TEXT NOT NULL,
    venue        TEXT NOT NULL,
    game_date    TEXT NOT NULL,
    ip           REAL DEFAULT 0.0,
    er           INTEGER DEFAULT 0,
    k            INTEGER DEFAULT 0,
    bb           INTEGER DEFAULT 0,
    PRIMARY KEY (pitcher_id, venue, game_date)
);

CREATE TABLE IF NOT EXISTS umpire_pitcher (
    umpire_id    TEXT NOT NULL,
    pitcher_id   TEXT NOT NULL,
    game_date    TEXT NOT NULL,
    pitches      INTEGER DEFAULT 0,
    called_strikes INTEGER DEFAULT 0,
    PRIMARY KEY (umpire_id, pitcher_id, game_date)
);
"""


# ══════════════════════════════════════════════════════════════════════════════
# 資料類別
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MatchupEdge:
    """投手 vs 打者 歷史對決摘要。"""
    at_bats: int = 0
    hits: int = 0
    walks: int = 0
    strikeouts: int = 0
    home_runs: int = 0
    woba: float = _LEAGUE_WOBA_VS_SP  # 聯盟平均 fallback

    @property
    def k_pct(self) -> float:
        return self.strikeouts / max(1, self.at_bats)

    @property
    def bb_pct(self) -> float:
        return self.walks / max(1, self.at_bats + self.walks)

    @property
    def hr_rate(self) -> float:
        return self.home_runs / max(1, self.at_bats)

    @property
    def sample_confidence(self) -> float:
        """樣本信心度 (0-1)，30 打席為完整信心。"""
        return min(1.0, self.at_bats / 30.0)


@dataclass
class KnowledgeGraphFeatures:
    """Category K — 20 個圖結構特徵。"""
    feature_dict: dict[str, float] = field(default_factory=dict)
    n_signals: int = 0
    data_quality: float = 0.0  # 0-1，反映圖譜資料完整度


# ══════════════════════════════════════════════════════════════════════════════
# 核心圖譜引擎
# ══════════════════════════════════════════════════════════════════════════════

class BaseballKnowledgeGraph:
    """
    本地棒球知識圖譜。

    使用 NetworkX DiGraph 作為運算層，SQLite 作為持久層。
    所有查詢均接受 cutoff_date 參數，確保無 Look-ahead Leakage。
    """

    def __init__(self, db_path: Path = _DB_PATH) -> None:
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._graph: "nx.DiGraph | None" = None
        self._init_db()

    # ── 初始化 ────────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.executescript(_DDL)
        self._conn.commit()

    def _ensure_graph(self) -> "nx.DiGraph":
        if not _NX_AVAILABLE:
            raise ImportError("networkx 未安裝，請執行: pip install networkx")
        if self._graph is None:
            self._graph = nx.DiGraph()
        return self._graph

    # ── 寫入 API ──────────────────────────────────────────────────────────────

    def record_pitcher_batter(
        self,
        pitcher_id: str,
        batter_id: str,
        game_date: str,
        at_bats: int,
        hits: int,
        walks: int,
        strikeouts: int,
        home_runs: int,
        woba_sum: float,
    ) -> None:
        """記錄投手 vs 打者 對決結果。"""
        if not self._conn:
            return
        try:
            self._conn.execute(
                """INSERT OR REPLACE INTO pitcher_batter_matchup
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (pitcher_id, batter_id, game_date,
                 at_bats, hits, walks, strikeouts, home_runs, woba_sum)
            )
            self._conn.commit()
        except sqlite3.Error as e:
            logger.error("pitcher_batter 寫入失敗: %s", e)

    def record_team_vs_team(
        self,
        home_team: str,
        away_team: str,
        game_date: str,
        home_win: bool,
        home_runs: int,
        away_runs: int,
    ) -> None:
        """記錄球隊對球隊比賽結果。"""
        if not self._conn:
            return
        try:
            self._conn.execute(
                """INSERT OR REPLACE INTO team_vs_team VALUES (?,?,?,?,?,?)""",
                (home_team, away_team, game_date,
                 int(home_win), home_runs, away_runs)
            )
            self._conn.commit()
        except sqlite3.Error as e:
            logger.error("team_vs_team 寫入失敗: %s", e)

    def record_pitcher_venue(
        self,
        pitcher_id: str,
        venue: str,
        game_date: str,
        ip: float,
        er: int,
        k: int,
        bb: int,
    ) -> None:
        """記錄投手在場館的歷史表現。"""
        if not self._conn:
            return
        try:
            self._conn.execute(
                """INSERT OR REPLACE INTO pitcher_venue VALUES (?,?,?,?,?,?,?)""",
                (pitcher_id, venue, game_date, ip, er, k, bb)
            )
            self._conn.commit()
        except sqlite3.Error as e:
            logger.error("pitcher_venue 寫入失敗: %s", e)

    def record_umpire_pitcher(
        self,
        umpire_id: str,
        pitcher_id: str,
        game_date: str,
        pitches: int,
        called_strikes: int,
    ) -> None:
        """記錄裁判對投手的好球判定歷史。"""
        if not self._conn:
            return
        try:
            self._conn.execute(
                """INSERT OR REPLACE INTO umpire_pitcher VALUES (?,?,?,?,?)""",
                (umpire_id, pitcher_id, game_date, pitches, called_strikes)
            )
            self._conn.commit()
        except sqlite3.Error as e:
            logger.error("umpire_pitcher 寫入失敗: %s", e)

    # ── 查詢 API（所有查詢均有 cutoff_date 過濾） ─────────────────────────────

    def get_pitcher_vs_lineup(
        self,
        pitcher_id: str,
        lineup_ids: list[str],
        cutoff_date: str,
    ) -> MatchupEdge:
        """
        取得投手對整個打線的歷史加總。
        cutoff_date: 'YYYY-MM-DD'，只計算此日期之前的資料。
        """
        if not self._conn or not lineup_ids:
            return MatchupEdge()

        placeholders = ",".join("?" for _ in lineup_ids)
        params = [pitcher_id] + lineup_ids + [cutoff_date]
        try:
            row = self._conn.execute(
                f"""SELECT
                      SUM(at_bats), SUM(hits), SUM(walks),
                      SUM(strikeouts), SUM(home_runs), SUM(woba_sum)
                    FROM pitcher_batter_matchup
                    WHERE pitcher_id=?
                      AND batter_id IN ({placeholders})
                      AND game_date < ?""",
                params
            ).fetchone()
        except sqlite3.Error as e:
            logger.error("get_pitcher_vs_lineup 查詢失敗: %s", e)
            return MatchupEdge()

        if not row or row[0] is None or row[0] == 0:
            return MatchupEdge()

        at_bats = int(row[0] or 0)
        hits = int(row[1] or 0)
        walks = int(row[2] or 0)
        strikeouts = int(row[3] or 0)
        home_runs = int(row[4] or 0)
        woba_sum = float(row[5] or 0.0)
        return MatchupEdge(
            at_bats=at_bats,
            hits=hits,
            walks=walks,
            strikeouts=strikeouts,
            home_runs=home_runs,
            woba=woba_sum / max(1, at_bats),
        )

    def get_team_vs_team_stats(
        self,
        home_team: str,
        away_team: str,
        cutoff_date: str,
        n_games: int = 20,
    ) -> dict[str, float]:
        """取得球隊對球隊歷史勝負統計。"""
        if not self._conn:
            return {"win_pct": _LEAGUE_WIN_PCT, "run_diff_avg": 0.0, "n_games": 0.0}

        try:
            rows = self._conn.execute(
                """SELECT home_win, home_runs, away_runs
                   FROM team_vs_team
                   WHERE home_team=? AND away_team=? AND game_date < ?
                   ORDER BY game_date DESC LIMIT ?""",
                (home_team, away_team, cutoff_date, n_games)
            ).fetchall()
        except sqlite3.Error as e:
            logger.error("get_team_vs_team_stats 查詢失敗: %s", e)
            rows = []

        if not rows:
            return {"win_pct": _LEAGUE_WIN_PCT, "run_diff_avg": 0.0, "n_games": 0.0}

        wins = sum(r[0] for r in rows)
        run_diffs = [r[1] - r[2] for r in rows]
        return {
            "win_pct": wins / len(rows),
            "run_diff_avg": float(np.mean(run_diffs)),
            "n_games": float(len(rows)),
        }

    def get_pitcher_venue_era(
        self,
        pitcher_id: str,
        venue: str,
        cutoff_date: str,
    ) -> float:
        """投手在特定場館的 ERA（無資料返回 -1 表示 N/A）。"""
        if not self._conn:
            return -1.0
        try:
            row = self._conn.execute(
                """SELECT SUM(ip), SUM(er)
                   FROM pitcher_venue
                   WHERE pitcher_id=? AND venue=? AND game_date < ?""",
                (pitcher_id, venue, cutoff_date)
            ).fetchone()
        except sqlite3.Error as e:
            logger.error("get_pitcher_venue_era 查詢失敗: %s", e)
            return -1.0

        if not row or row[0] is None or row[0] == 0:
            return -1.0

        ip, er = float(row[0] or 0), float(row[1] or 0)
        return (er / ip * 9) if ip > 0 else -1.0

    def get_umpire_csw_rate(
        self,
        umpire_id: str,
        pitcher_id: str,
        cutoff_date: str,
    ) -> float:
        """裁判對投手的 Called Strike + Whiff 率 (CSW%)。"""
        if not self._conn:
            return 0.285  # 聯盟平均
        try:
            row = self._conn.execute(
                """SELECT SUM(pitches), SUM(called_strikes)
                   FROM umpire_pitcher
                   WHERE umpire_id=? AND pitcher_id=? AND game_date < ?""",
                (umpire_id, pitcher_id, cutoff_date)
            ).fetchone()
        except sqlite3.Error as e:
            logger.error("get_umpire_csw_rate 查詢失敗: %s", e)
            return 0.285

        if not row or row[0] is None or row[0] == 0:
            return 0.285

        pitches, cs = float(row[0] or 0), float(row[1] or 0)
        return (cs / pitches) if pitches > 0 else 0.285

    # ── NetworkX 圖結構計算（可選加強功能） ────────────────────────────────────

    def build_rivalry_graph(
        self,
        cutoff_date: str,
    ) -> "nx.DiGraph":
        """
        建立球隊競爭關係圖 (Team → Team，邊權重=勝率)。
        用於計算節點中心性（Centrality）特徵。
        """
        G = self._ensure_graph()
        G.clear()

        if not self._conn:
            return G

        try:
            rows = self._conn.execute(
                """SELECT home_team, away_team,
                          AVG(home_win) as win_pct,
                          COUNT(*) as n_games
                   FROM team_vs_team
                   WHERE game_date < ?
                   GROUP BY home_team, away_team""",
                (cutoff_date,)
            ).fetchall()
        except sqlite3.Error:
            return G

        for home, away, win_pct, n_games in rows:
            G.add_edge(home, away, weight=float(win_pct or 0.5), n_games=int(n_games or 0))
            if not G.has_edge(away, home):
                G.add_edge(away, home, weight=1.0 - float(win_pct or 0.5), n_games=int(n_games or 0))

        return G

    def get_team_centrality(
        self,
        team: str,
        G: "nx.DiGraph | None" = None,
    ) -> float:
        """取得球隊在競爭圖中的 PageRank 中心性（強隊 > 1.0）。"""
        if not _NX_AVAILABLE:
            return 1.0

        if G is None or len(G) == 0:
            return 1.0

        try:
            pr = nx.pagerank(G, weight="weight")
            raw = pr.get(team, 1.0 / max(1, len(G)))
            # 正規化：相對於平均值
            avg = float(np.mean(list(pr.values()))) if pr else 1e-4
            return raw / max(avg, 1e-6)
        except Exception as e:
            logger.debug("PageRank 計算失敗: %s", e)
            return 1.0


# ══════════════════════════════════════════════════════════════════════════════
# Category K：特徵提取函數（整合進 alpha_signals.py）
# ══════════════════════════════════════════════════════════════════════════════

def compute_knowledge_graph_signals(
    matchup: Matchup,
    kg: BaseballKnowledgeGraph,
    cutoff_date: str,
) -> dict[str, float]:
    """
    Category K — 棒球知識圖譜特徵 (20 個信號)

    Args:
        matchup:      Matchup 物件（開賽前狀態）
        kg:           已初始化的 BaseballKnowledgeGraph
        cutoff_date:  'YYYY-MM-DD'，確保無資料外洩

    Returns:
        dict[str, float] — 可直接合併至 AlphaSignals.feature_dict
    """
    feats: dict[str, float] = {}
    home = matchup.home
    away = matchup.away

    home_sp_id = getattr(matchup.home_sp, "name", f"{home.team}_SP") if matchup.home_sp else f"{home.team}_SP"
    away_sp_id = getattr(matchup.away_sp, "name", f"{away.team}_SP") if matchup.away_sp else f"{away.team}_SP"
    home_lineup_ids = [b.name for b in matchup.home_lineup]
    away_lineup_ids = [b.name for b in matchup.away_lineup]

    # ── K.01 投手對打線歷史 wOBA 差值 ────────────────────────────────────────
    # away SP vs home lineup
    edge_away_sp_vs_home = kg.get_pitcher_vs_lineup(away_sp_id, home_lineup_ids, cutoff_date)
    # home SP vs away lineup
    edge_home_sp_vs_away = kg.get_pitcher_vs_lineup(home_sp_id, away_lineup_ids, cutoff_date)

    kg_away_sp_woba = edge_away_sp_vs_home.woba
    kg_home_sp_woba = edge_home_sp_vs_away.woba

    # 主隊視角：主隊打者 wOBA 越高越好，主隊投手 wOBA 越低越好
    feats["kg_lineup_vs_sp_woba_diff"] = float(
        np.clip(kg_away_sp_woba - kg_home_sp_woba, -0.15, 0.15)
    )

    # ── K.02 投手對打線 K% 差值 ───────────────────────────────────────────────
    feats["kg_sp_k_pct_diff"] = float(
        np.clip(edge_home_sp_vs_away.k_pct - edge_away_sp_vs_home.k_pct, -0.3, 0.3)
    )

    # ── K.03 投手對打線 HR 率差值（長打威脅） ────────────────────────────────
    feats["kg_sp_hr_rate_diff"] = float(
        np.clip(edge_away_sp_vs_home.hr_rate - edge_home_sp_vs_away.hr_rate, -0.1, 0.1)
    )

    # ── K.04 樣本信心度 ───────────────────────────────────────────────────────
    home_conf = edge_home_sp_vs_away.sample_confidence
    away_conf = edge_away_sp_vs_home.sample_confidence
    feats["kg_matchup_sample_confidence"] = float((home_conf + away_conf) / 2.0)
    feats["kg_sample_confidence_diff"] = float(home_conf - away_conf)

    # ── K.05 球隊對球隊歷史 ──────────────────────────────────────────────────
    tvt = kg.get_team_vs_team_stats(home.team, away.team, cutoff_date)
    feats["kg_team_rivalry_win_pct"] = float(tvt["win_pct"])
    feats["kg_team_rivalry_win_pct_centered"] = float(tvt["win_pct"] - 0.5)
    feats["kg_team_rivalry_run_diff"] = float(np.clip(tvt["run_diff_avg"], -5.0, 5.0))
    feats["kg_rivalry_sample_size"] = float(min(tvt["n_games"] / 10.0, 1.0))  # 正規化到 0-1

    # ── K.06 場館投手表現 ─────────────────────────────────────────────────────
    venue = matchup.venue or "generic"
    home_sp_venue_era = kg.get_pitcher_venue_era(home_sp_id, venue, cutoff_date)
    away_sp_venue_era = kg.get_pitcher_venue_era(away_sp_id, venue, cutoff_date)

    # ERA 差值（低 ERA 對主隊有利）
    # 無資料時使用球員整體 ERA
    home_sp_era_ref = matchup.home_sp.era if matchup.home_sp else 4.20
    away_sp_era_ref = matchup.away_sp.era if matchup.away_sp else 4.20

    if home_sp_venue_era >= 0:
        h_venue_era = home_sp_venue_era
    else:
        h_venue_era = home_sp_era_ref

    if away_sp_venue_era >= 0:
        a_venue_era = away_sp_venue_era
    else:
        a_venue_era = away_sp_era_ref

    feats["kg_venue_era_advantage"] = float(np.clip(a_venue_era - h_venue_era, -4.0, 4.0))
    feats["kg_home_sp_venue_era"] = float(np.clip(h_venue_era, 0.0, 9.0))
    feats["kg_away_sp_venue_era"] = float(np.clip(a_venue_era, 0.0, 9.0))

    # ── K.07 裁判好球帶親和力 ─────────────────────────────────────────────────
    umpire_id = matchup.umpire_id or "generic_avg"
    home_ump_csw = kg.get_umpire_csw_rate(umpire_id, home_sp_id, cutoff_date)
    away_ump_csw = kg.get_umpire_csw_rate(umpire_id, away_sp_id, cutoff_date)
    feats["kg_umpire_csw_diff"] = float(np.clip(home_ump_csw - away_ump_csw, -0.1, 0.1))
    feats["kg_umpire_home_sp_csw"] = float(home_ump_csw)

    # ── K.08 球隊競爭圖中心性 ────────────────────────────────────────────────
    try:
        rivalry_graph = kg.build_rivalry_graph(cutoff_date)
        home_centrality = kg.get_team_centrality(home.team, rivalry_graph)
        away_centrality = kg.get_team_centrality(away.team, rivalry_graph)
        feats["kg_team_centrality_diff"] = float(
            np.clip(math.log(max(home_centrality, 1e-4)) - math.log(max(away_centrality, 1e-4)), -2.0, 2.0)
        )
        feats["kg_home_team_centrality"] = float(np.clip(home_centrality, 0.0, 5.0))
    except Exception as e:
        logger.debug("圖中心性計算失敗: %s", e)
        feats["kg_team_centrality_diff"] = 0.0
        feats["kg_home_team_centrality"] = 1.0

    # ── K.09 綜合圖優勢分數 ───────────────────────────────────────────────────
    feats["kg_composite_graph_advantage"] = float(
        feats.get("kg_lineup_vs_sp_woba_diff", 0.0) * 8.0 +
        feats.get("kg_team_rivalry_win_pct_centered", 0.0) * 2.0 +
        feats.get("kg_venue_era_advantage", 0.0) * 0.15 +
        feats.get("kg_sp_k_pct_diff", 0.0) * 1.5 +
        feats.get("kg_umpire_csw_diff", 0.0) * 0.5
    )

    # 四捨五入至 4 位
    return {k: round(float(v), 4) for k, v in feats.items()}


# ── 全域單例（由 build_alpha_signals 初始化一次） ──────────────────────────────
_default_kg: Optional[BaseballKnowledgeGraph] = None


def get_default_kg(db_path: Path = _DB_PATH) -> BaseballKnowledgeGraph:
    """取得或初始化預設 KG 單例。"""
    global _default_kg
    if _default_kg is None:
        _default_kg = BaseballKnowledgeGraph(db_path=db_path)
    return _default_kg
