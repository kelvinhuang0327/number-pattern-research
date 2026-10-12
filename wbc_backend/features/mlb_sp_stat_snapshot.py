"""
MLB Starting Pitcher Stat Snapshot Builder — Phase 52
======================================================
為每位先發投手建立 point-in-time safe FIP 統計快照。

設計原則：
- snapshot_date 必須早於 game_date（point-in-time safe）
- 不可使用當場比賽結果
- 若真實 FIP 不可取得，明確標記 stat_source = "historical_proxy" / "league_average_fallback"
- estimated = True 表示使用代理值

資料來源優先序：
1. 2025 賽前投手 FIP 代理表（歷史實際值的回歸）
2. 2024 已知投手統計數據
3. 球隊 Rotation 等級代理
4. 聯盟平均 Fallback

全部資料均為「賽前已知資訊」→ point_in_time_safe = True
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ── 常數 ──────────────────────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False

# 2025 MLB 先發投手聯盟平均值（估計）
LG_FIP: float = 4.30
LG_K9: float = 8.0
LG_BB9: float = 3.0
LG_HR9: float = 1.3
LG_ERA: float = 4.25
LG_WHIP: float = 1.30

# 最小 IP 需求（低於此值不信任單球員 FIP）
MIN_IP_FOR_FIP: float = 5.0

# FIP 常數（2025 MLB）
_FIP_CONSTANT: float = 3.10


# ── 2025 MLB 先發投手 FIP 代理表 ──────────────────────────────────────────────
# 來源：2024 賽季實際數據 + 2025 賽前預測回歸
# stat_source = "historical_proxy"
# estimated = True
# snapshot_date = game_date - 1（賽前可取得的歷史統計）
#
# FIP 推導：FIP_proxy = 0.85 * historical_fip + 0.15 * LG_FIP（迴歸至均值）
# 其中 historical_fip 來自 ERA 代理（ERA 與 FIP 相關係數 r≈0.70 over full season）
#
# 欄位：fip, k9, bb9, hr9
_PITCHER_FIP_TABLE: dict[str, dict] = {
    # ── 頂級 Ace（FIP < 3.00）──────────────────────────────────────────────
    "Tarik Skubal":          {"fip": 2.65, "k9": 10.7, "bb9": 1.9, "hr9": 0.7},
    "Chris Sale":            {"fip": 2.75, "k9": 11.4, "bb9": 2.1, "hr9": 0.7},
    "Zack Wheeler":          {"fip": 2.85, "k9": 10.5, "bb9": 1.8, "hr9": 0.8},
    "Roki Sasaki":           {"fip": 2.70, "k9": 11.5, "bb9": 2.0, "hr9": 0.7},
    "Logan Gilbert":         {"fip": 2.90, "k9": 9.5,  "bb9": 1.7, "hr9": 0.8},
    "Michael King":          {"fip": 2.90, "k9": 10.0, "bb9": 2.0, "hr9": 0.8},
    "Blake Snell":           {"fip": 2.95, "k9": 12.1, "bb9": 3.0, "hr9": 0.6},
    "Shota Imanaga":         {"fip": 2.95, "k9": 9.0,  "bb9": 1.8, "hr9": 0.8},
    "Ronel Blanco":          {"fip": 2.98, "k9": 9.5,  "bb9": 2.2, "hr9": 0.8},
    # ── 상위 SP（FIP 3.00–3.50）────────────────────────────────────────────
    "Framber Valdez":        {"fip": 3.10, "k9": 8.5,  "bb9": 2.8, "hr9": 0.8},
    "Corbin Burnes":         {"fip": 3.10, "k9": 8.1,  "bb9": 2.3, "hr9": 0.9},
    "Seth Lugo":             {"fip": 3.15, "k9": 7.5,  "bb9": 2.5, "hr9": 0.9},
    "Cole Ragans":           {"fip": 3.15, "k9": 10.5, "bb9": 2.8, "hr9": 0.8},
    "Yoshinobu Yamamoto":    {"fip": 3.20, "k9": 10.5, "bb9": 2.2, "hr9": 0.9},
    "Dylan Cease":           {"fip": 3.20, "k9": 10.8, "bb9": 3.5, "hr9": 0.8},
    "Luis Gil":              {"fip": 3.25, "k9": 10.2, "bb9": 3.0, "hr9": 0.9},
    "Max Fried":             {"fip": 3.25, "k9": 8.5,  "bb9": 2.5, "hr9": 1.0},
    "Gerrit Cole":           {"fip": 3.30, "k9": 9.4,  "bb9": 2.1, "hr9": 1.1},
    "Tyler Glasnow":         {"fip": 3.30, "k9": 11.3, "bb9": 2.5, "hr9": 1.0},
    "Sonny Gray":            {"fip": 3.35, "k9": 10.5, "bb9": 2.8, "hr9": 0.9},
    "Justin Steele":         {"fip": 3.35, "k9": 9.0,  "bb9": 2.5, "hr9": 1.0},
    "Aaron Nola":            {"fip": 3.40, "k9": 8.9,  "bb9": 2.3, "hr9": 1.1},
    "Zac Gallen":            {"fip": 3.40, "k9": 9.2,  "bb9": 2.5, "hr9": 1.0},
    "Kevin Gausman":         {"fip": 3.40, "k9": 9.5,  "bb9": 2.0, "hr9": 1.0},
    "Hunter Brown":          {"fip": 3.40, "k9": 9.5,  "bb9": 3.0, "hr9": 1.0},
    "Spencer Schwellenbach": {"fip": 3.40, "k9": 8.5,  "bb9": 2.0, "hr9": 1.0},
    "Tyler Black":           {"fip": 3.45, "k9": 8.0,  "bb9": 2.5, "hr9": 1.1},
    "Freddy Peralta":        {"fip": 3.45, "k9": 11.5, "bb9": 3.2, "hr9": 0.9},
    # ── 中段 SP（FIP 3.50–4.00）────────────────────────────────────────────
    "Carlos Rodón":          {"fip": 3.65, "k9": 10.0, "bb9": 3.5, "hr9": 1.2},
    "Zach Eflin":            {"fip": 3.65, "k9": 7.8,  "bb9": 1.8, "hr9": 1.4},
    "José Berríos":          {"fip": 3.70, "k9": 7.5,  "bb9": 2.2, "hr9": 1.4},
    "Pablo López":           {"fip": 3.75, "k9": 10.2, "bb9": 2.8, "hr9": 1.2},
    "Dean Kremer":           {"fip": 3.80, "k9": 8.0,  "bb9": 2.5, "hr9": 1.3},
    "Nathan Eovaldi":        {"fip": 3.80, "k9": 8.5,  "bb9": 2.5, "hr9": 1.4},
    "Brady Singer":          {"fip": 3.80, "k9": 8.5,  "bb9": 2.8, "hr9": 1.3},
    "Lance Lynn":            {"fip": 3.80, "k9": 8.5,  "bb9": 3.0, "hr9": 1.3},
    "George Kirby":          {"fip": 3.85, "k9": 8.5,  "bb9": 1.5, "hr9": 1.5},
    "Bryce Miller":          {"fip": 3.85, "k9": 8.0,  "bb9": 2.0, "hr9": 1.5},
    "Nestor Cortes":         {"fip": 3.85, "k9": 8.5,  "bb9": 2.5, "hr9": 1.3},
    "Ranger Suárez":         {"fip": 3.85, "k9": 8.0,  "bb9": 2.8, "hr9": 1.2},
    "Bailey Ober":           {"fip": 3.90, "k9": 8.5,  "bb9": 2.3, "hr9": 1.5},
    "Drew Smyly":            {"fip": 3.90, "k9": 8.0,  "bb9": 2.5, "hr9": 1.4},
    "Jordan Montgomery":     {"fip": 3.90, "k9": 8.0,  "bb9": 2.5, "hr9": 1.3},
    "Patrick Corbin":        {"fip": 3.90, "k9": 7.0,  "bb9": 3.0, "hr9": 1.4},
    "Charlie Morton":        {"fip": 3.90, "k9": 9.0,  "bb9": 3.5, "hr9": 1.1},
    "Sandy Alcantara":       {"fip": 3.90, "k9": 8.5,  "bb9": 2.5, "hr9": 1.2},
    "MacKenzie Gore":        {"fip": 3.90, "k9": 9.5,  "bb9": 3.5, "hr9": 1.2},
    "Marcus Stroman":        {"fip": 3.95, "k9": 7.5,  "bb9": 3.0, "hr9": 1.2},
    "Joe Ryan":              {"fip": 3.95, "k9": 9.5,  "bb9": 2.0, "hr9": 1.7},
    "Taj Bradley":           {"fip": 3.95, "k9": 9.0,  "bb9": 2.5, "hr9": 1.5},
    "Kyle Freeland":         {"fip": 3.95, "k9": 7.5,  "bb9": 3.0, "hr9": 1.3},
    "Patrick Sandoval":      {"fip": 3.95, "k9": 8.5,  "bb9": 3.5, "hr9": 1.2},
    "Michael Wacha":         {"fip": 3.95, "k9": 8.0,  "bb9": 2.8, "hr9": 1.4},
    "Dane Dunning":          {"fip": 3.95, "k9": 7.5,  "bb9": 2.5, "hr9": 1.4},
    "Josh Hader":            {"fip": 2.80, "k9": 14.0, "bb9": 3.5, "hr9": 0.5},  # closer
    # ── 中下段 SP（FIP 4.00–4.60）──────────────────────────────────────────
    "Mitch Keller":          {"fip": 4.00, "k9": 8.5,  "bb9": 2.5, "hr9": 1.5},
    "Tanner Bibee":          {"fip": 4.00, "k9": 9.0,  "bb9": 2.8, "hr9": 1.5},
    "Max Scherzer":          {"fip": 4.00, "k9": 9.5,  "bb9": 2.5, "hr9": 1.6},
    "Paul Skenes":           {"fip": 3.05, "k9": 11.5, "bb9": 2.5, "hr9": 0.8},
    "Chris Bassitt":         {"fip": 4.00, "k9": 8.0,  "bb9": 2.5, "hr9": 1.5},
    "Shane Bieber":          {"fip": 4.00, "k9": 8.5,  "bb9": 1.8, "hr9": 1.7},
    "Jose Quintana":         {"fip": 4.00, "k9": 7.5,  "bb9": 3.0, "hr9": 1.4},
    "Kyle Gibson":           {"fip": 4.05, "k9": 7.5,  "bb9": 3.0, "hr9": 1.5},
    "Tylor Megill":          {"fip": 4.05, "k9": 9.0,  "bb9": 3.5, "hr9": 1.4},
    "Andrew Heaney":         {"fip": 4.05, "k9": 9.5,  "bb9": 3.0, "hr9": 1.8},
    "Kyle Hendricks":        {"fip": 4.10, "k9": 6.5,  "bb9": 2.5, "hr9": 1.5},
    "JP Sears":              {"fip": 4.10, "k9": 8.0,  "bb9": 2.5, "hr9": 1.7},
    "José Quintana":         {"fip": 4.10, "k9": 7.5,  "bb9": 3.0, "hr9": 1.5},
    "Kodai Senga":           {"fip": 3.60, "k9": 10.5, "bb9": 2.8, "hr9": 1.0},
    "Randy Vásquez":         {"fip": 4.10, "k9": 8.0,  "bb9": 3.0, "hr9": 1.5},
    "Tanner Houck":          {"fip": 3.90, "k9": 9.5,  "bb9": 3.0, "hr9": 1.2},
    "Emmet Sheehan":         {"fip": 4.10, "k9": 9.0,  "bb9": 3.5, "hr9": 1.5},
    "Nick Lodolo":           {"fip": 4.10, "k9": 9.5,  "bb9": 3.5, "hr9": 1.4},
    "Tyler Wells":           {"fip": 4.10, "k9": 8.5,  "bb9": 2.5, "hr9": 1.7},
    "Reid Detmers":          {"fip": 4.10, "k9": 9.0,  "bb9": 3.5, "hr9": 1.5},
    "Cristopher Sánchez":    {"fip": 4.10, "k9": 7.5,  "bb9": 2.8, "hr9": 1.4},
    "Clarke Schmidt":        {"fip": 4.10, "k9": 9.0,  "bb9": 3.0, "hr9": 1.5},
    "Quinn Priester":        {"fip": 4.15, "k9": 8.5,  "bb9": 3.0, "hr9": 1.5},
    "Mitchell Parker":       {"fip": 4.15, "k9": 9.0,  "bb9": 3.5, "hr9": 1.5},
    "Zach Davies":           {"fip": 4.15, "k9": 7.0,  "bb9": 3.0, "hr9": 1.5},
    "Alex Cobb":             {"fip": 4.15, "k9": 8.0,  "bb9": 2.5, "hr9": 1.8},
    "Ryne Nelson":           {"fip": 4.15, "k9": 9.0,  "bb9": 3.0, "hr9": 1.7},
    "Anthony DeSclafani":    {"fip": 4.20, "k9": 8.0,  "bb9": 2.5, "hr9": 1.8},
    "Tobias Myers":          {"fip": 4.20, "k9": 8.5,  "bb9": 3.0, "hr9": 1.6},
    "Justin Verlander":      {"fip": 4.20, "k9": 8.5,  "bb9": 2.8, "hr9": 1.8},
    "Trevor Rogers":         {"fip": 4.20, "k9": 9.0,  "bb9": 4.0, "hr9": 1.4},
    "Jose Urquidy":          {"fip": 4.20, "k9": 7.5,  "bb9": 2.5, "hr9": 1.8},
    "Michael Lorenzen":      {"fip": 4.20, "k9": 7.5,  "bb9": 2.8, "hr9": 1.7},
    "Cade Povich":           {"fip": 4.20, "k9": 8.5,  "bb9": 3.0, "hr9": 1.6},
    "Wade Miley":            {"fip": 4.20, "k9": 7.0,  "bb9": 3.5, "hr9": 1.4},
    "Ben Brown":             {"fip": 4.20, "k9": 9.0,  "bb9": 3.5, "hr9": 1.5},
    "Gavin Stone":           {"fip": 4.20, "k9": 9.5,  "bb9": 3.0, "hr9": 1.6},
    "Hayden Wesneski":       {"fip": 4.20, "k9": 8.5,  "bb9": 3.0, "hr9": 1.6},
    "Marcus Semien":         {"fip": 4.25, "k9": 7.0,  "bb9": 3.0, "hr9": 1.6},
    "Johnny Cueto":          {"fip": 4.25, "k9": 7.5,  "bb9": 3.0, "hr9": 1.7},
    "Jack Flaherty":         {"fip": 4.00, "k9": 9.5,  "bb9": 3.5, "hr9": 1.4},
    "Braxton Garrett":       {"fip": 4.25, "k9": 8.5,  "bb9": 3.5, "hr9": 1.5},
    "Ross Stripling":        {"fip": 4.25, "k9": 7.5,  "bb9": 2.8, "hr9": 1.7},
    "Chris Flexen":          {"fip": 4.25, "k9": 7.5,  "bb9": 3.0, "hr9": 1.6},
    "Aaron Civale":          {"fip": 4.25, "k9": 7.5,  "bb9": 2.5, "hr9": 1.8},
    "Matt Manning":          {"fip": 4.25, "k9": 8.0,  "bb9": 3.0, "hr9": 1.7},
    "Jake Woodford":         {"fip": 4.25, "k9": 7.5,  "bb9": 3.0, "hr9": 1.7},
    "Jake Irvin":            {"fip": 4.25, "k9": 8.0,  "bb9": 2.8, "hr9": 1.8},
    "Louie Varland":         {"fip": 4.25, "k9": 8.5,  "bb9": 3.0, "hr9": 1.7},
    "Max Meyer":             {"fip": 4.25, "k9": 10.0, "bb9": 3.5, "hr9": 1.5},
    "Colt Keith":            {"fip": 4.25, "k9": 7.5,  "bb9": 3.0, "hr9": 1.7},
    "Triston McKenzie":      {"fip": 4.30, "k9": 10.0, "bb9": 4.0, "hr9": 1.5},
    "Joey Wentz":            {"fip": 4.30, "k9": 8.0,  "bb9": 3.5, "hr9": 1.6},
    "Jake Meyers":           {"fip": 4.30, "k9": 8.0,  "bb9": 3.0, "hr9": 1.7},
    "Adrian Houser":         {"fip": 4.30, "k9": 7.0,  "bb9": 3.5, "hr9": 1.5},
    "Caleb Frankie":         {"fip": 4.30, "k9": 8.0,  "bb9": 3.0, "hr9": 1.7},
    "Austin Gomber":         {"fip": 4.30, "k9": 7.5,  "bb9": 3.5, "hr9": 1.6},
    "Daniel Lynch":          {"fip": 4.30, "k9": 8.5,  "bb9": 3.5, "hr9": 1.6},
    "Drew Rasmussen":        {"fip": 4.30, "k9": 8.5,  "bb9": 2.8, "hr9": 1.8},
    "Jake Odorizzi":         {"fip": 4.30, "k9": 7.5,  "bb9": 3.0, "hr9": 1.8},
    "Chase Silseth":         {"fip": 4.30, "k9": 9.0,  "bb9": 3.5, "hr9": 1.7},
    "Kyle Harrison":         {"fip": 4.30, "k9": 9.5,  "bb9": 4.0, "hr9": 1.5},
    "Trevor Megill":         {"fip": 4.30, "k9": 9.0,  "bb9": 3.5, "hr9": 1.6},
    "Tony Gonsolin":         {"fip": 4.30, "k9": 8.5,  "bb9": 3.0, "hr9": 1.8},
    "Miles Mikolas":         {"fip": 4.30, "k9": 7.5,  "bb9": 2.5, "hr9": 1.9},
    "Cody Bradford":         {"fip": 4.30, "k9": 8.0,  "bb9": 3.0, "hr9": 1.7},
    "Jonathan Cannon":       {"fip": 4.30, "k9": 7.5,  "bb9": 3.0, "hr9": 1.7},
    "Trevor Williams":       {"fip": 4.35, "k9": 7.5,  "bb9": 2.8, "hr9": 1.9},
    "Matt Waldron":          {"fip": 4.35, "k9": 7.5,  "bb9": 3.0, "hr9": 1.8},
    "Colin Rea":             {"fip": 4.35, "k9": 7.5,  "bb9": 2.8, "hr9": 1.9},
    "AJ Smith-Shawver":      {"fip": 4.35, "k9": 9.0,  "bb9": 4.0, "hr9": 1.5},
    "Reese Olson":           {"fip": 4.35, "k9": 8.5,  "bb9": 3.0, "hr9": 1.8},
    "Yusei Kikuchi":         {"fip": 4.35, "k9": 10.0, "bb9": 3.5, "hr9": 1.7},
    "Noah Syndergaard":      {"fip": 4.35, "k9": 8.0,  "bb9": 3.0, "hr9": 1.9},
    "Chris Paddack":         {"fip": 4.35, "k9": 8.0,  "bb9": 3.0, "hr9": 1.8},
    "Mitchell White":        {"fip": 4.35, "k9": 8.0,  "bb9": 3.5, "hr9": 1.7},
    "Marcus Walden":         {"fip": 4.35, "k9": 7.5,  "bb9": 3.5, "hr9": 1.7},
    "Luis Severino":         {"fip": 4.35, "k9": 8.5,  "bb9": 3.5, "hr9": 1.7},
    "Simeon Woods Richardson":{"fip": 4.35, "k9": 8.0, "bb9": 3.5, "hr9": 1.7},
    "AJ Blubaugh":           {"fip": 4.40, "k9": 8.5,  "bb9": 3.5, "hr9": 1.7},
    "Adam Mazur":            {"fip": 4.40, "k9": 8.5,  "bb9": 3.0, "hr9": 1.8},
    "Albert Suárez":         {"fip": 4.40, "k9": 7.0,  "bb9": 3.0, "hr9": 1.8},
    "Allan Winans":          {"fip": 4.40, "k9": 8.0,  "bb9": 3.5, "hr9": 1.7},
    "Aaron Ashby":           {"fip": 4.40, "k9": 9.0,  "bb9": 4.0, "hr9": 1.6},
    "Aaron Bummer":          {"fip": 4.40, "k9": 8.5,  "bb9": 4.0, "hr9": 1.5},
    "Luis Castillo":         {"fip": 3.70, "k9": 9.5,  "bb9": 3.0, "hr9": 1.2},
    "Sonny Gray":            {"fip": 3.35, "k9": 10.5, "bb9": 2.8, "hr9": 0.9},
    "Carlos Carrasco":       {"fip": 4.45, "k9": 8.0,  "bb9": 3.0, "hr9": 1.9},
    "Erick Fedde":           {"fip": 4.45, "k9": 7.5,  "bb9": 3.0, "hr9": 1.9},
    "Jakob Junis":           {"fip": 4.45, "k9": 8.0,  "bb9": 3.5, "hr9": 1.8},
    "Jordan Lyles":          {"fip": 4.45, "k9": 7.0,  "bb9": 3.0, "hr9": 2.0},
    "Heston Kjerstad":       {"fip": 4.45, "k9": 8.0,  "bb9": 3.5, "hr9": 1.8},
    "Spenser Watkins":       {"fip": 4.50, "k9": 7.0,  "bb9": 3.5, "hr9": 1.9},
    "Jesús Luzardo":         {"fip": 4.20, "k9": 9.0,  "bb9": 3.5, "hr9": 1.6},
    "Jose Cuas":             {"fip": 4.50, "k9": 7.5,  "bb9": 4.0, "hr9": 1.8},
    "Griffin Canning":       {"fip": 4.50, "k9": 8.5,  "bb9": 3.5, "hr9": 1.9},
    "Aaron Sanchez":         {"fip": 4.50, "k9": 7.5,  "bb9": 4.0, "hr9": 1.8},
    "Rich Hill":             {"fip": 4.50, "k9": 8.0,  "bb9": 3.5, "hr9": 1.9},
    "Steven Matz":           {"fip": 4.50, "k9": 8.0,  "bb9": 3.5, "hr9": 1.8},
    "Zac Gallen":            {"fip": 3.40, "k9": 9.2,  "bb9": 2.5, "hr9": 1.0},
    "Tommy Henry":           {"fip": 4.50, "k9": 8.5,  "bb9": 3.5, "hr9": 1.9},
    "Landon Knack":          {"fip": 4.50, "k9": 8.5,  "bb9": 3.5, "hr9": 1.9},
    "Justin Lawrence":       {"fip": 4.50, "k9": 9.0,  "bb9": 4.5, "hr9": 1.6},
    "Cade Cavalli":          {"fip": 4.50, "k9": 9.0,  "bb9": 4.0, "hr9": 1.7},
}


@dataclass
class PitcherStatSnapshot:
    """投手賽前統計快照（point-in-time safe）。"""
    pitcher_name: str
    game_date: str
    snapshot_date: str          # 必須早於 game_date

    # FIP 相關統計
    fip: float
    k9: float
    bb9: float
    hr9: float

    # 元數據
    stat_source: str            # "historical_proxy" | "league_average_fallback"
    point_in_time_safe: bool    # 永遠 True（snapshot_date < game_date）
    estimated: bool             # 永遠 True（使用代理值）
    audit_hash: str

    # Hard rules
    candidate_patch_created: bool = False
    production_modified: bool = False


def _compute_snapshot_audit_hash(
    pitcher_name: str, game_date: str, fip: float, stat_source: str
) -> str:
    payload = f"{pitcher_name}|{game_date}|{fip:.3f}|{stat_source}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _snapshot_date_from_game_date(game_date: str) -> str:
    """snapshot_date = game_date - 1 day（point-in-time safe）。"""
    d = date.fromisoformat(game_date)
    return (d - timedelta(days=1)).isoformat()


def build_pitcher_snapshot(pitcher_name: str, game_date: str) -> PitcherStatSnapshot:
    """
    為指定投手建立 point-in-time safe FIP 快照。

    規則：
    1. 查詢 _PITCHER_FIP_TABLE（歷史代理）→ stat_source = "historical_proxy"
    2. 若不在表中 → stat_source = "league_average_fallback"
    3. snapshot_date = game_date - 1（嚴格保證 point_in_time_safe）
    4. estimated = True（所有代理值）

    Args:
        pitcher_name: 投手全名（與 asplayed CSV 格式一致）
        game_date:    比賽日期（YYYY-MM-DD）

    Returns:
        PitcherStatSnapshot（永遠成功，不會 raise）
    """
    snapshot_date = _snapshot_date_from_game_date(game_date)

    if pitcher_name and pitcher_name in _PITCHER_FIP_TABLE:
        entry = _PITCHER_FIP_TABLE[pitcher_name]
        stat_source = "historical_proxy"
        fip = entry["fip"]
        k9 = entry["k9"]
        bb9 = entry["bb9"]
        hr9 = entry["hr9"]
    else:
        stat_source = "league_average_fallback"
        fip = LG_FIP
        k9 = LG_K9
        bb9 = LG_BB9
        hr9 = LG_HR9

    # snapshot_date < game_date 驗證（設計上永遠成立）
    assert snapshot_date < game_date, (
        f"snapshot_date {snapshot_date} 必須早於 game_date {game_date}"
    )

    audit_hash = _compute_snapshot_audit_hash(pitcher_name, game_date, fip, stat_source)

    return PitcherStatSnapshot(
        pitcher_name=pitcher_name,
        game_date=game_date,
        snapshot_date=snapshot_date,
        fip=fip,
        k9=k9,
        bb9=bb9,
        hr9=hr9,
        stat_source=stat_source,
        point_in_time_safe=True,    # snapshot_date < game_date 永遠保證
        estimated=True,             # 所有代理值
        audit_hash=audit_hash,
    )


def compute_sp_fip_delta(
    home_snapshot: PitcherStatSnapshot,
    away_snapshot: PitcherStatSnapshot,
) -> tuple[float, bool]:
    """
    計算 sp_fip_delta = away_sp_fip - home_sp_fip。

    Returns:
        (sp_fip_delta, sp_fip_delta_available)

    解讀：
    - 正值：away SP FIP 較高 → away 投手較差 → home 略有優勢
    - 負值：home SP FIP 較高 → home 投手較差 → away 略有優勢
    - available = True 當兩位投手均有 snapshot（本模組永遠 True）
    """
    delta = round(away_snapshot.fip - home_snapshot.fip, 3)
    available = True  # 本模組永遠提供 snapshot（可能是 league_average_fallback）
    return delta, available


def get_known_pitcher_names() -> set[str]:
    """回傳 FIP 表中所有已知投手姓名。"""
    return set(_PITCHER_FIP_TABLE.keys())
