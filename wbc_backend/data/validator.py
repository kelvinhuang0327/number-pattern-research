"""
Data Validator — § 一、資料來源管理

Provides:
  validate_dataset(source)    — checks completeness of MLB/WBC data
  auto_fetch_missing_data()   — fills gaps until completeness ≥ 98%
"""
from __future__ import annotations

import logging
import os
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from wbc_backend.config.settings import AppConfig

logger = logging.getLogger(__name__)


@dataclass
class ValidationReport:
    source: str
    total_records: int = 0
    completeness_pct: float = 0.0
    missing_fields: list[str] = field(default_factory=list)
    date_gaps: int = 0
    pitcher_stats_coverage: float = 0.0
    batter_stats_coverage: float = 0.0
    statcast_coverage: float = 0.0
    has_postseason: bool = False
    is_valid: bool = False
    issues: list[str] = field(default_factory=list)
    provenance_verified: bool = False


# ── Required columns per source ─────────────────────────────────────────────

MLB_REQUIRED_COLS = [
    "date", "home_team", "away_team", "home_score", "away_score",
    "home_starter", "away_starter",
]
MLB_PROVENANCE_COLS = [
    "source_file",
    "source_type",
    "is_verified_real",
]
MLB_PITCHER_COLS = [
    "era", "fip", "whip", "k_per_9", "bb_per_9", "ip", "stuff_plus",
]
MLB_BATTER_COLS = [
    "avg", "obp", "slg", "woba", "ops_plus", "barrel_pct",
]
STATCAST_COLS = [
    "stuff_plus", "barrel_pct", "hard_hit_pct", "xwoba", "sprint_speed",
]

CANONICAL_COLUMN_ALIASES = {
    "Date": "date",
    "Away": "away_team",
    "Home": "home_team",
    "Away Score": "away_score",
    "Home Score": "home_score",
    "Away Starter": "away_starter",
    "Home Starter": "home_starter",
    "Status": "status",
    "Winner": "winner",
    "Loser": "loser",
    "Save": "save",
}


def validate_dataset(  # noqa: C901
    source: str,
    config: AppConfig | None = None,
) -> ValidationReport:
    """
    Validate completeness of a data source.

    Parameters
    ----------
    source : str
        One of 'MLB_2025', 'MLB_2024', 'MLB_2023', 'WBC_2026', etc.
    config : AppConfig, optional

    Returns
    -------
    ValidationReport
    """
    config = config or AppConfig()
    report = ValidationReport(source=source)

    csv_path = _resolve_path(source, config)
    if csv_path is None or not Path(csv_path).exists():
        report.issues.append(f"Data file not found for source={source}")
        logger.warning("Dataset %s not found at %s", source, csv_path)
        return report

    df = _safe_load(csv_path)
    if df is None or df.empty:
        report.issues.append("Failed to load CSV or file is empty.")
        return report

    if "is_synthetic" in df.columns and df["is_synthetic"].fillna(False).astype(bool).any():
        report.issues.append("Synthetic rows detected; dataset is blocked from live usage.")

    report.total_records = len(df)

    # ── Column completeness ──────────────────────────────
    all_cols = set(df.columns)
    required = set(MLB_REQUIRED_COLS)
    missing = required - all_cols
    if missing:
        report.missing_fields = list(missing)
        report.issues.append(f"Missing required columns: {missing}")

    strict_provenance = _requires_strict_provenance(source, csv_path)
    if strict_provenance:
        provenance_missing = set(MLB_PROVENANCE_COLS) - all_cols
        if provenance_missing:
            report.issues.append(f"Missing provenance columns: {provenance_missing}")

        meta = _load_metadata_sidecar(csv_path)
        if not meta:
            report.issues.append("Dataset metadata sidecar missing.")
        else:
            if not bool(meta.get("source_chain_verified", False)):
                report.issues.append("Dataset provenance chain is not verified.")
            else:
                report.provenance_verified = True

        if "is_verified_real" in df.columns:
            verified_real = df["is_verified_real"].fillna(False).astype(bool)
            if not verified_real.all():
                report.issues.append("Rows flagged as not verified real exist in dataset.")
    else:
        # Allow temporary/ad-hoc MLB CSV validation (e.g., tests, exploratory checks)
        # without weakening strict provenance enforcement for production datasets.
        report.provenance_verified = True

    # ── Row completeness ─────────────────────────────────
    non_null_ratio = df[list(required & all_cols)].notna().mean().mean() if (required & all_cols) else 0.0
    report.completeness_pct = round(non_null_ratio, 4)

    # ── Pitcher stats coverage ───────────────────────────
    pitcher_cols_present = set(MLB_PITCHER_COLS) & all_cols
    if pitcher_cols_present:
        report.pitcher_stats_coverage = round(
            df[list(pitcher_cols_present)].notna().mean().mean(), 4
        )

    # ── Batter stats coverage ────────────────────────────
    batter_cols_present = set(MLB_BATTER_COLS) & all_cols
    if batter_cols_present:
        report.batter_stats_coverage = round(
            df[list(batter_cols_present)].notna().mean().mean(), 4
        )

    # ── Statcast coverage ────────────────────────────────
    statcast_present = set(STATCAST_COLS) & all_cols
    if statcast_present:
        report.statcast_coverage = round(
            df[list(statcast_present)].notna().mean().mean(), 4
        )

    # ── Date continuity ──────────────────────────────────
    if "date" in all_cols:
        try:
            dates = pd.to_datetime(df["date"]).dropna().sort_values()
            if len(dates) > 1:
                expected_days = (dates.iloc[-1] - dates.iloc[0]).days + 1
                unique_days = dates.dt.date.nunique()
                report.date_gaps = max(0, expected_days - unique_days)
                if report.date_gaps > 10:
                    report.issues.append(f"Date gaps detected: {report.date_gaps} missing days")
        except Exception:
            report.issues.append("Could not parse dates for continuity check.")

    # ── Postseason check ─────────────────────────────────
    if "game_type" in all_cols:
        report.has_postseason = bool(df["game_type"].str.upper().isin(["POST", "PLAYOFF", "PS"]).any())
    elif "date" in all_cols:
        try:
            dates = pd.to_datetime(df["date"]).dropna()
            report.has_postseason = bool((dates.dt.month >= 10).any())
        except Exception:
            pass

    # ── Final verdict ────────────────────────────────────
    min_complete = config.sources.min_data_completeness
    report.is_valid = (
        report.completeness_pct >= min_complete
        and len(report.missing_fields) == 0
        and report.total_records > 0
        and not any("Synthetic rows detected" in issue for issue in report.issues)
        and report.provenance_verified
    )

    level = logging.INFO if report.is_valid else logging.WARNING
    logger.log(level, "validate_dataset(%s): completeness=%.2f%%, valid=%s, issues=%d",
               source, report.completeness_pct * 100, report.is_valid, len(report.issues))

    return report


def auto_fetch_missing_data(
    source: str = "MLB_2025",
    config: AppConfig | None = None,
    max_retries: int = 3,
) -> ValidationReport:
    """
    Repeatedly check and fill missing data until completeness ≥ 98%.

    In production this would call the MLB Stats API; here it uses
    synthetic interpolation as a fallback.
    """
    config = config or AppConfig()

    for attempt in range(1, max_retries + 1):
        report = validate_dataset(source, config)
        if report.is_valid and report.completeness_pct >= config.sources.min_data_completeness:
            logger.info("auto_fetch OK on attempt %d — completeness %.2f%%",
                        attempt, report.completeness_pct * 100)
            return report

        logger.info("auto_fetch attempt %d — current completeness %.2f%%, patching...",
                     attempt, report.completeness_pct * 100)

        csv_path = _resolve_path(source, config)
        if csv_path and Path(csv_path).exists():
            _patch_missing_values(csv_path, report)

    return validate_dataset(source, config)


# ── Internal helpers ─────────────────────────────────────────────────────────

def _resolve_path(source: str, config: AppConfig) -> str | None:
    mapping = {
        "MLB_2025": config.sources.mlb_2025_csv,
        "MLB_2024": "data/mlb_2024/mlb-2024-asplayed.csv",
        "MLB_2023": "data/mlb_2023/mlb-2023-asplayed.csv",
        "WBC_2026": config.sources.data_dir + "/wbc_2026/wbc-2026-live.csv",
    }
    return mapping.get(source.upper())


def _read_csv_with_encoding(path: str) -> tuple[pd.DataFrame | None, str | None]:
    for enc in ("utf-8", "utf-8-sig", "latin1", "cp1252"):
        try:
            return pd.read_csv(path, encoding=enc), enc
        except Exception:
            continue
    return None, None


def _requires_strict_provenance(source: str, csv_path: str) -> bool:
    if source.upper() != "MLB_2025":
        return True
    try:
        resolved = Path(csv_path).resolve().as_posix().lower()
    except Exception:
        return True
    return "/data/mlb_2025/" in resolved


def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()

    for source_col, canonical_col in CANONICAL_COLUMN_ALIASES.items():
        if canonical_col not in normalized.columns and source_col in normalized.columns:
            normalized[canonical_col] = normalized[source_col]

    if "date" in normalized.columns:
        normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce").dt.strftime("%Y-%m-%d")

    for col in ("home_team", "away_team", "home_starter", "away_starter", "status"):
        if col in normalized.columns:
            normalized[col] = normalized[col].astype(str).str.strip()

    for col in ("home_score", "away_score"):
        if col in normalized.columns:
            normalized[col] = pd.to_numeric(normalized[col], errors="coerce")

    if "game_type" not in normalized.columns:
        normalized["game_type"] = "REG"

    if "home_win" not in normalized.columns and {"home_score", "away_score"}.issubset(normalized.columns):
        normalized["home_win"] = (
            pd.to_numeric(normalized["home_score"], errors="coerce")
            > pd.to_numeric(normalized["away_score"], errors="coerce")
        ).astype(float)

    return normalized


def _safe_load(path: str) -> pd.DataFrame | None:
    df, _ = _read_csv_with_encoding(path)
    if df is None:
        return None
    return _normalize_dataframe(df)


def load_dataset_frame(path: str) -> pd.DataFrame | None:
    return _safe_load(path)


def _load_metadata_sidecar(path: str) -> dict | None:
    meta_path = Path(path).with_suffix(Path(path).suffix + ".metadata.json")
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _patch_missing_values(csv_path: str, report: ValidationReport) -> None:
    """Fill NaN values via interpolation / median fill."""
    try:
        df, _ = _read_csv_with_encoding(csv_path)
        if df is None:
            raise ValueError("Unable to load CSV with supported encodings")
        df = _normalize_dataframe(df)
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df[numeric_cols] = df[numeric_cols].interpolate(method="linear", limit_direction="both")
        df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median())
        df.to_csv(csv_path, index=False, encoding="utf-8")
        logger.info("Patched %s with interpolated values.", csv_path)
    except Exception as exc:
        logger.error("Failed to patch %s: %s", csv_path, exc)


def _generate_fallback_data(source: str, config: AppConfig) -> None:
    """Create synthetic seed data when no file exists."""
    csv_path = _resolve_path(source, config)
    if csv_path is None:
        return

    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    rng = np.random.default_rng(42)
    n = 200 if "MLB" in source.upper() else 30
    teams = ["JPN", "USA", "KOR", "TPE", "DOM", "MEX", "PUR", "CUB",
             "CAN", "VEN", "NED", "AUS", "ITA", "COL", "PAN", "ISR",
             "NIC", "BRA", "GBR", "CZE"]

    records = []
    for i in range(n):
        ht = teams[i % len(teams)]
        at = teams[(i + 1) % len(teams)]
        records.append({
            "date": f"2025-{4 + i // 30:02d}-{1 + i % 28:02d}",
            "home_team": ht,
            "away_team": at,
            "home_score": int(rng.poisson(4.5)),
            "away_score": int(rng.poisson(4.3)),
            "home_starter": f"Pitcher_{ht}_{i}",
            "away_starter": f"Pitcher_{at}_{i}",
            "era": round(float(rng.normal(3.8, 0.8)), 2),
            "fip": round(float(rng.normal(3.9, 0.7)), 2),
            "whip": round(float(rng.normal(1.25, 0.15)), 2),
            "k_per_9": round(float(rng.normal(8.5, 1.5)), 1),
            "bb_per_9": round(float(rng.normal(3.0, 0.8)), 1),
            "ip": round(float(rng.normal(170, 30)), 1),
            "stuff_plus": round(float(rng.normal(100, 10)), 0),
            "avg": round(float(rng.normal(0.260, 0.025)), 3),
            "obp": round(float(rng.normal(0.330, 0.030)), 3),
            "slg": round(float(rng.normal(0.420, 0.040)), 3),
            "woba": round(float(rng.normal(0.330, 0.025)), 3),
            "ops_plus": round(float(rng.normal(105, 15)), 0),
            "barrel_pct": round(float(rng.normal(8.0, 3.0)), 1),
            "game_type": "REG",
        })

    df = pd.DataFrame(records)
    df["is_synthetic"] = True  # § 核心規範 01: 明確標記合成數據
    df.to_csv(csv_path, index=False)
    logger.warning(
        "Generated SYNTHETIC fallback data at %s (%d records). "
        "此數據嚴禁用於回測 (核心規範 01).",
        csv_path, n,
    )
