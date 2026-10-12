"""
wbc_backend/features/mlb_bullpen_full_season_ingestion.py
==========================================================
Phase 64-B — Full-Season Bullpen SSOT Ingestion

目標：
  從現有 `data/mlb_context/bullpen_usage_3d.jsonl` 建立全季 SSOT artifacts，
  並為 Phase 64-B attribution 提供覆蓋率足夠（>80%）的特徵資料。

資料來源優先順序（artifact-first）：
  1. 本地已存在的 `bullpen_usage_3d.jsonl`（Phase60 已抓取，2430 筆）
  2. Phase63 SSOT artifacts（4 teams，用於驗證）
  3. StatsAPI boxscore cache（dry_run=True 時跳過，不呼叫 live API）

安全常數（FROZEN）：
  DRY_RUN_DEFAULT = True          # 預設不呼叫 live API
  LIVE_API_CALLS_ENABLED = False  # 模組等級 API 呼叫開關

PIT 安全保證：
  bullpen_usage_last_3d_home/away = 比賽 D 日前 3 天（D-3, D-2, D-1）的牛棚用量
  資料本身由 Phase60 PIT-safe 設計確保，此模組不引入 future leakage。
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Module Constants
# ---------------------------------------------------------------------------
MODULE_VERSION: str = "phase64b_full_season_ingestion_v1"

# Safety constants — FROZEN
DRY_RUN_DEFAULT: bool = True       # Never make live API calls by default
LIVE_API_CALLS_ENABLED: bool = False  # Module-level guard; set True only in prod
RATE_LIMIT_RPM: int = 10           # Max 10 requests/minute
MAX_RETRY: int = 3                 # Max retry attempts per request
RETRY_DELAY_S: float = 2.0        # Seconds between retries

# Phase 64-B data paths (defaults)
_BULL_3D_PATH = "data/mlb_context/bullpen_usage_3d.jsonl"
_PHASE63_SSOT_PATH = "reports/phase63_bullpen_ssot_features_20260506.jsonl"
_BOXSCORE_CACHE_DIR = "data/mlb_context/boxscores_cache"

# SSOT schema fields produced by this module
_SSOT_REQUIRED_FIELDS = frozenset([
    "game_date",
    "team",
    "bullpen_usage_last_3d",
    "bullpen_usage_last_1d",
    "bullpen_usage_last_5d",
    "reliever_back_to_back_count",
    "reliever_three_in_four_days_count",
    "closer_used_last_1d",
    "closer_used_last_2d",
    "source",
    "diagnostic_only",
    "pit_safe",
])


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class FullSeasonIngestionSummary:
    """Summary of the full-season ingestion run."""
    module_version: str
    run_timestamp: str
    dry_run: bool
    live_api_enabled: bool

    # Input counts
    n_bull_3d_rows: int          # Raw rows from bullpen_usage_3d.jsonl
    n_parseable_games: int       # Games with valid game_id parse
    n_team_artifacts: int        # Total per-team SSOT artifacts produced

    # Coverage
    n_3d_available: int          # Artifacts with 3d usage available
    n_1d_available: int          # Artifacts with 1d usage (0 in dry-run)
    n_5d_available: int          # Artifacts with 5d usage (0 in dry-run)
    n_b2b_available: int         # Artifacts with b2b count (0 in dry-run)
    n_3in4_available: int        # Artifacts with 3in4 count (0 in dry-run)
    n_closer_available: int      # Artifacts with closer data (0 in dry-run)

    # Phase63 cross-validation
    n_phase63_artifacts: int     # Loaded Phase63 reference artifacts
    n_phase63_consistent: int    # Phase63 artifacts consistent with new SSOT (within 0.5 IP)

    # Output paths
    ssot_output_path: str
    appearances_output_path: str

    # Gate readiness
    coverage_rate_3d: float      # n_3d_available / n_team_artifacts
    ready_for_attribution: bool  # coverage_rate_3d >= 0.80


@dataclass
class BullpenSSOTArtifact:
    """Full-season per-team-per-game SSOT artifact."""
    game_date: str
    team: str                           # Canonical team name (raw from game_id)
    team_norm: str                      # Normalised (upper + underscore)
    side: str                           # "home" or "away"

    # Available from bull_3d file
    bullpen_usage_last_3d: float | None
    # Derived estimates (None = DATA_LIMITED)
    bullpen_usage_last_1d: float | None   # Requires StatsAPI boxscore cache
    bullpen_usage_last_5d: float | None   # Requires StatsAPI boxscore cache
    reliever_back_to_back_count: int | None  # Requires per-game appearance log
    reliever_three_in_four_days_count: int | None  # Requires per-game appearance log
    closer_used_last_1d: bool | None         # Requires per-game appearance log
    closer_used_last_2d: bool | None         # Requires per-game appearance log

    source: str                         # "bullpen_usage_3d_derived" or "statsapi_cache"
    diagnostic_only: bool               # Always True (Phase 64-B diagnostic)
    pit_safe: bool                      # Always True (3d window = prior days only)
    game_id: str                        # Original bull_3d game_id
    data_limited_fields: list[str]      # Fields that are None due to DATA_LIMITED


# ---------------------------------------------------------------------------
# Team name normalisation (consistent with Phase 64)
# ---------------------------------------------------------------------------

def _norm_team(name: str) -> str:
    """Normalise team name: upper-case, spaces → underscores, strip non-alnum_."""
    return re.sub(r"[^A-Z0-9_]", "_", name.upper().replace(" ", "_"))


def _canonical_team(raw: str) -> str:
    """Convert normalised team name back to Title Case."""
    return raw.replace("_", " ").title()


# ---------------------------------------------------------------------------
# bull_3d game_id parsing
# ---------------------------------------------------------------------------

def parse_bull3d_game_id(game_id: str) -> tuple[str, str, str] | None:
    """
    Parse bullpen_usage_3d game_id into (date_str, norm_away, norm_home).

    Format: MLB-YYYY_MM_DD-TIME-AWAY_TEAM-AT-HOME_TEAM
    Example: MLB-2025_04_27-1_40_PM-TORONTO_BLUE_JAYS-AT-NEW_YORK_YANKEES

    Returns None if parsing fails.
    PIT-safe: date derived from game_id only (no outcome data).
    """
    try:
        rest = game_id.replace("MLB-", "", 1)
        # First 10 chars: YYYY_MM_DD
        date_part = rest[:10]
        date_str = date_part.replace("_", "-")
        # Validate date format
        datetime.strptime(date_str, "%Y-%m-%d")

        after_date = rest[10:]
        at_idx = after_date.rfind("-AT-")
        if at_idx == -1:
            return None

        home_raw = after_date[at_idx + 4:]
        before_at = after_date[:at_idx].lstrip("-")

        # Time part ends at first dash that starts a letter group
        time_end = before_at.find("-")
        if time_end == -1:
            return None
        away_raw = before_at[time_end + 1:]

        if not home_raw or not away_raw:
            return None

        return date_str, _norm_team(away_raw), _norm_team(home_raw)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# SSOT artifact construction from bull_3d row
# ---------------------------------------------------------------------------

def _build_team_artifact(
    game_id: str,
    game_date: str,
    team_norm: str,
    side: str,
    usage_3d: float,
) -> BullpenSSOTArtifact:
    """Build one team SSOT artifact from a bull_3d row."""
    data_limited = [
        "bullpen_usage_last_1d",
        "bullpen_usage_last_5d",
        "reliever_back_to_back_count",
        "reliever_three_in_four_days_count",
        "closer_used_last_1d",
        "closer_used_last_2d",
    ]
    return BullpenSSOTArtifact(
        game_date=game_date,
        team=_canonical_team(team_norm),
        team_norm=team_norm,
        side=side,
        bullpen_usage_last_3d=round(usage_3d, 3),
        bullpen_usage_last_1d=None,      # DATA_LIMITED: requires StatsAPI cache
        bullpen_usage_last_5d=None,      # DATA_LIMITED: requires StatsAPI cache
        reliever_back_to_back_count=None,   # DATA_LIMITED: requires per-game appearances
        reliever_three_in_four_days_count=None,  # DATA_LIMITED: per-game appearances
        closer_used_last_1d=None,        # DATA_LIMITED: per-game appearances
        closer_used_last_2d=None,        # DATA_LIMITED: per-game appearances
        source="bullpen_usage_3d_derived",
        diagnostic_only=True,
        pit_safe=True,
        game_id=game_id,
        data_limited_fields=data_limited,
    )


# ---------------------------------------------------------------------------
# StatsAPI fetch skeleton (dry_run / cache-first)
# ---------------------------------------------------------------------------

def fetch_boxscore_cached(
    mlb_game_pk: int | str,
    cache_dir: str | Path,
    dry_run: bool = True,
    timeout_s: float = 10.0,
) -> dict[str, Any] | None:
    """
    Fetch StatsAPI boxscore for a game, using local cache first.

    Safety contract:
    - dry_run=True (default): reads cache only, NEVER calls live API.
    - live mode: requires LIVE_API_CALLS_ENABLED=True at module level.
    - Rate-limited to RATE_LIMIT_RPM requests/minute.
    - Retries MAX_RETRY times with RETRY_DELAY_S between attempts.

    Returns:
        dict with raw StatsAPI boxscore data, or None if unavailable.
    """
    cache_path = Path(cache_dir) / f"{mlb_game_pk}.json"

    # 1. Check local cache first (artifact-first)
    if cache_path.exists():
        with open(cache_path) as f:
            return json.load(f)

    # 2. In dry-run mode, return None (no live API)
    if dry_run or not LIVE_API_CALLS_ENABLED:
        return None

    # 3. Live mode: fetch from StatsAPI with rate limiting
    # This block is never reached in tests (dry_run=True enforced in test fixtures)
    url = f"https://statsapi.mlb.com/api/v1/game/{mlb_game_pk}/boxscore"
    last_err: Exception | None = None
    for attempt in range(MAX_RETRY):
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=timeout_s) as resp:  # noqa: S310
                data = json.loads(resp.read().decode("utf-8"))
            # Write to cache
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w") as f:
                json.dump(data, f)
            # Rate limit guard
            time.sleep(60 / RATE_LIMIT_RPM)
            return data
        except Exception as exc:
            last_err = exc
            if attempt < MAX_RETRY - 1:
                time.sleep(RETRY_DELAY_S)

    # Failed after all retries
    return None


# ---------------------------------------------------------------------------
# Cross-validation against Phase63 reference artifacts
# ---------------------------------------------------------------------------

def _validate_against_phase63(
    ssot_index: dict[tuple[str, str], BullpenSSOTArtifact],
    phase63_path: str,
    tolerance_ip: float = 0.5,
) -> tuple[int, int]:
    """
    Cross-validate new full-season SSOT against Phase63 reference artifacts.
    Returns (n_phase63_loaded, n_consistent).
    A match is 'consistent' if |new_3d - ref_3d| <= tolerance_ip.
    """
    try:
        phase63_rows = _load_jsonl(phase63_path)
    except FileNotFoundError:
        return 0, 0

    n_loaded = len(phase63_rows)
    n_consistent = 0
    for ref in phase63_rows:
        gd = ref.get("game_date", "")
        team = ref.get("team", "")
        key = (gd, _norm_team(team))
        new_art = ssot_index.get(key)
        if new_art is None:
            continue
        ref_3d = ref.get("bullpen_usage_last_3d")
        new_3d = new_art.bullpen_usage_last_3d
        if ref_3d is not None and new_3d is not None:
            if abs(new_3d - ref_3d) <= tolerance_ip:
                n_consistent += 1
    return n_loaded, n_consistent


# ---------------------------------------------------------------------------
# JSONL utility
# ---------------------------------------------------------------------------

def _load_jsonl(path: str) -> list[dict[str, Any]]:
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_jsonl(rows: list[dict[str, Any]], path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row, default=str) + "\n")


# ---------------------------------------------------------------------------
# Build Full-Season SSOT Index
# ---------------------------------------------------------------------------

def build_full_season_ssot_index(
    bull_3d_path: str,
) -> tuple[dict[tuple[str, str], BullpenSSOTArtifact], int, int]:
    """
    Build full-season SSOT index from bullpen_usage_3d.jsonl.

    Returns:
        ssot_index: dict[(game_date, norm_team), BullpenSSOTArtifact]
        n_rows_raw: total rows read from bull_3d file
        n_parseable: rows successfully parsed
    """
    bull_rows = _load_jsonl(bull_3d_path)
    ssot_index: dict[tuple[str, str], BullpenSSOTArtifact] = {}
    n_parseable = 0

    for row in bull_rows:
        game_id = row.get("game_id", "")
        home_3d = row.get("bullpen_usage_last_3d_home")
        away_3d = row.get("bullpen_usage_last_3d_away")

        parsed = parse_bull3d_game_id(game_id)
        if parsed is None:
            continue
        date_str, norm_away, norm_home = parsed
        n_parseable += 1

        # Build home artifact
        if home_3d is not None:
            home_art = _build_team_artifact(
                game_id=game_id,
                game_date=date_str,
                team_norm=norm_home,
                side="home",
                usage_3d=float(home_3d),
            )
            ssot_index[(date_str, norm_home)] = home_art

        # Build away artifact
        if away_3d is not None:
            away_art = _build_team_artifact(
                game_id=game_id,
                game_date=date_str,
                team_norm=norm_away,
                side="away",
                usage_3d=float(away_3d),
            )
            ssot_index[(date_str, norm_away)] = away_art

    return ssot_index, len(bull_rows), n_parseable


# ---------------------------------------------------------------------------
# Full Ingestion Pipeline
# ---------------------------------------------------------------------------

def run_full_season_ingestion(
    bull_3d_path: str = _BULL_3D_PATH,
    phase63_ssot_path: str = _PHASE63_SSOT_PATH,
    boxscore_cache_dir: str = _BOXSCORE_CACHE_DIR,
    ssot_output_path: str = "reports/phase64b_bullpen_ssot_features_20260506.jsonl",
    appearances_output_path: str = "reports/phase64b_bullpen_relief_appearances_20260506.jsonl",
    dry_run: bool = DRY_RUN_DEFAULT,
) -> FullSeasonIngestionSummary:
    """
    Full Phase 64-B ingestion pipeline.

    Steps:
    1. Load bull_3d.jsonl (artifact-first — already fetched by Phase60)
    2. Derive per-team SSOT artifacts (3d features from bull_3d)
    3. Optionally enrich with StatsAPI boxscore cache (dry_run=True: skip)
    4. Cross-validate against Phase63 reference artifacts
    5. Write SSOT JSONL + appearances JSONL (empty in dry-run)
    6. Return ingestion summary

    Safety:
    - dry_run=True (default): NEVER calls live StatsAPI
    - All test runs use dry_run=True
    - In dry-run, 1d/5d/b2b/3in4/closer remain DATA_LIMITED
    """
    run_ts = datetime.now(timezone.utc).isoformat()

    # Step 1+2: Build SSOT index from bull_3d
    ssot_index, n_raw, n_parseable = build_full_season_ssot_index(bull_3d_path)

    # Step 3: Enrich with StatsAPI cache (no-op in dry-run)
    # In production mode, this would iterate cached boxscores and fill 1d/5d/b2b/3in4/closer
    # For Phase 64-B, cache is empty → skipped even in non-dry-run
    n_enriched = 0  # placeholder for future Phase65 enrichment

    # Step 4: Cross-validate against Phase63
    n_phase63, n_consistent = _validate_against_phase63(ssot_index, phase63_ssot_path)

    # Count coverage
    artifacts = list(ssot_index.values())
    n_total = len(artifacts)
    n_3d = sum(1 for a in artifacts if a.bullpen_usage_last_3d is not None)
    n_1d = sum(1 for a in artifacts if a.bullpen_usage_last_1d is not None)
    n_5d = sum(1 for a in artifacts if a.bullpen_usage_last_5d is not None)
    n_b2b = sum(1 for a in artifacts if a.reliever_back_to_back_count is not None)
    n_3in4 = sum(1 for a in artifacts if a.reliever_three_in_four_days_count is not None)
    n_closer = sum(1 for a in artifacts if a.closer_used_last_1d is not None)

    cov_3d = n_3d / max(n_total, 1)

    # Step 5a: Write SSOT JSONL
    ssot_rows = [asdict(a) for a in artifacts]
    # Sort by game_date, team for determinism
    ssot_rows.sort(key=lambda r: (r["game_date"], r["team_norm"]))
    _write_jsonl(ssot_rows, ssot_output_path)

    # Step 5b: Write appearances JSONL (empty in dry-run since no boxscore cache)
    appearances_rows: list[dict[str, Any]] = []
    _write_jsonl(appearances_rows, appearances_output_path)

    summary = FullSeasonIngestionSummary(
        module_version=MODULE_VERSION,
        run_timestamp=run_ts,
        dry_run=dry_run,
        live_api_enabled=LIVE_API_CALLS_ENABLED,
        n_bull_3d_rows=n_raw,
        n_parseable_games=n_parseable,
        n_team_artifacts=n_total,
        n_3d_available=n_3d,
        n_1d_available=n_1d,
        n_5d_available=n_5d,
        n_b2b_available=n_b2b,
        n_3in4_available=n_3in4,
        n_closer_available=n_closer,
        n_phase63_artifacts=n_phase63,
        n_phase63_consistent=n_consistent,
        ssot_output_path=ssot_output_path,
        appearances_output_path=appearances_output_path,
        coverage_rate_3d=round(cov_3d, 4),
        ready_for_attribution=cov_3d >= 0.80,
    )
    return summary


# ---------------------------------------------------------------------------
# Public API: load SSOT index (used by Phase 64-B attribution)
# ---------------------------------------------------------------------------

def load_full_season_ssot_from_file(
    ssot_path: str,
) -> dict[tuple[str, str], dict[str, Any]]:
    """
    Load full-season SSOT from JSONL file into Phase64-compatible index.
    Returns dict: (game_date, norm_team) → artifact dict.
    Compatible with Phase64's _derive_granular_features_for_game interface.
    """
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for row in _load_jsonl(ssot_path):
        gd = row.get("game_date", "")
        team_norm = row.get("team_norm", _norm_team(row.get("team", "")))
        if gd and team_norm:
            index[(gd, team_norm)] = row
    return index
