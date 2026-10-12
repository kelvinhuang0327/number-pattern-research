"""P35 Prediction Rebuild Feasibility Auditor

Scans the repository for feature engineering, model training, and OOF
generation candidates, then assesses whether a leakage-safe 2024 OOF
prediction rebuild is feasible.

HARD GUARDS:
- Do NOT run model training in this phase.
- Do NOT fabricate p_oof / p_model values.
- Do NOT use y_true to derive p_oof.
- PAPER_ONLY = True always.
- PRODUCTION_READY = False always.

Key findings from codebase inspection:
- walk_forward_logistic.py: temporal train/predict separation, OOF support.
- gbm_stack.py: OOF stacking pattern exists.
- run_p13_walk_forward_logistic_oof.py: OOF CLI exists.
- BUT: all existing pipelines are configured for WBC/2025/2026 feature
  columns (e.g. indep_recent_win_rate_delta, indep_starter_era_delta).
- P32 data provides: game_id, game_date, home_team, away_team, outcome cols.
- A 2024-format feature engineering adapter is NOT yet implemented.
- Conclusion: pipeline candidates EXIST, but 2024 adapter is MISSING →
  FEASIBILITY_BLOCKED_ADAPTER_MISSING → recommend P36 implementation.
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Tuple

from wbc_backend.recommendation.p35_dual_source_import_validation_contract import (
    FEASIBILITY_BLOCKED_ADAPTER_MISSING,
    FEASIBILITY_BLOCKED_LEAKAGE_RISK,
    FEASIBILITY_BLOCKED_PIPELINE_MISSING,
    FEASIBILITY_READY,
    FEASIBILITY_REQUIRES_P36_IMPLEMENTATION,
    PAPER_ONLY,
    PRODUCTION_READY,
    P35PredictionRebuildFeasibilityResult,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known pipeline candidates (discovered during P35 codebase audit)
# ---------------------------------------------------------------------------

KNOWN_FEATURE_PIPELINE_CANDIDATES: Tuple[str, ...] = (
    "wbc_backend/models/trainer.py",
    "wbc_backend/features/advanced.py",
    "wbc_backend/research/feature_space.py",
)

KNOWN_MODEL_TRAINING_CANDIDATES: Tuple[str, ...] = (
    "wbc_backend/models/trainer.py",
    "wbc_backend/models/xgboost_model.py",
    "wbc_backend/models/lightgbm_model.py",
    "wbc_backend/models/gbm_stack.py",
    "wbc_backend/models/walk_forward_logistic.py",
)

KNOWN_OOF_GENERATION_CANDIDATES: Tuple[str, ...] = (
    "scripts/run_p13_walk_forward_logistic_oof.py",
    "wbc_backend/models/gbm_stack.py",
    "wbc_backend/models/walk_forward_logistic.py",
)

KNOWN_LEAKAGE_GUARD_INDICATORS: Tuple[str, ...] = (
    "strict temporal train/predict separation",
    "TimeSeriesSplit",
    "leakage",
    "cutoff_date",
    "walk_forward",
    "WalkForward",
)

KNOWN_TIME_AWARE_SPLIT_INDICATORS: Tuple[str, ...] = (
    "WalkForwardLogistic",
    "walk_forward",
    "temporal",
    "sort_values.*date",
    "expanding.*window",
)

# Flag files that indicate the 2024 adapter exists
ADAPTER_FOR_2024_INDICATORS: Tuple[str, ...] = (
    "p32_to_features",
    "retrosheet_feature",
    "mlb_2024_feature",
    "game_log_feature_adapter",
    "build_2024_features",
    "retrosheet_to_model_features",
)


# ---------------------------------------------------------------------------
# Scanner functions
# ---------------------------------------------------------------------------


def _file_exists_in_candidates(candidates: Tuple[str, ...], base_path: str) -> List[str]:
    """Return which candidate files exist relative to base_path."""
    found = []
    for rel_path in candidates:
        full_path = os.path.join(base_path, rel_path)
        if os.path.isfile(full_path):
            found.append(rel_path)
    return found


def _scan_for_indicators(
    base_paths: List[str],
    indicators: Tuple[str, ...],
    extensions: Tuple[str, ...] = (".py",),
) -> List[str]:
    """Scan py files for any of the indicator strings. Returns matching file paths."""
    found_files: List[str] = []
    for base_path in base_paths:
        if not os.path.isdir(base_path):
            continue
        for root, _, files in os.walk(base_path):
            # Skip hidden and cache dirs
            if any(part.startswith(".") or part == "__pycache__" for part in root.split(os.sep)):
                continue
            for fname in files:
                if not any(fname.endswith(ext) for ext in extensions):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, encoding="utf-8", errors="replace") as fh:
                        content = fh.read()
                except OSError:
                    continue
                for indicator in indicators:
                    if indicator.lower() in content.lower():
                        if fpath not in found_files:
                            found_files.append(fpath)
                        break
    return sorted(found_files)


def scan_feature_pipeline_candidates(base_paths: List[str]) -> List[str]:
    """Scan for feature engineering pipeline files in base_paths."""
    feature_indicators = (
        "FEATURE_NAMES",
        "feature_engineering",
        "build_features",
        "feature_frame",
        "FeatureNames",
        "extract_features",
        "make_features",
    )
    return _scan_for_indicators(base_paths, feature_indicators)


def scan_model_training_candidates(base_paths: List[str]) -> List[str]:
    """Scan for model training pipeline files in base_paths."""
    training_indicators = (
        "fit(",
        ".fit(",
        "train_model",
        "LogisticRegression",
        "XGBClassifier",
        "LGBMClassifier",
        "CatBoostClassifier",
        "RandomForestClassifier",
        "GradientBoostingClassifier",
    )
    return _scan_for_indicators(base_paths, training_indicators)


def scan_oof_generation_candidates(base_paths: List[str]) -> List[str]:
    """Scan for out-of-fold (OOF) prediction generation logic."""
    oof_indicators = (
        "oof_pred",
        "out_of_fold",
        "OOF",
        "oof_predictions",
        "walk_forward",
        "WalkForward",
        "TimeSeriesSplit",
        "KFold",
    )
    return _scan_for_indicators(base_paths, oof_indicators)


def _check_leakage_guards(base_paths: List[str]) -> bool:
    """Return True if leakage guard patterns are detected."""
    files = _scan_for_indicators(base_paths, KNOWN_LEAKAGE_GUARD_INDICATORS)
    return len(files) > 0


def _check_time_aware_split(base_paths: List[str]) -> bool:
    """Return True if time-aware split logic is detected."""
    files = _scan_for_indicators(base_paths, KNOWN_TIME_AWARE_SPLIT_INDICATORS)
    return len(files) > 0


def _check_2024_adapter(base_paths: List[str]) -> bool:
    """Return True if a 2024-specific feature engineering adapter is found.

    Excludes this auditor module itself (which lists the indicator strings
    as constants) from the search.
    """
    _self_path = os.path.abspath(__file__)
    files = _scan_for_indicators(base_paths, ADAPTER_FOR_2024_INDICATORS)
    # Filter out this file — it contains the indicator strings as constants
    filtered = [f for f in files if os.path.abspath(f) != _self_path]
    return len(filtered) > 0


# ---------------------------------------------------------------------------
# Main feasibility evaluator
# ---------------------------------------------------------------------------


def evaluate_2024_oof_rebuild_feasibility(
    game_log_path: str,
    base_paths: Optional[List[str]] = None,
) -> P35PredictionRebuildFeasibilityResult:
    """Assess whether a leakage-safe 2024 OOF rebuild is feasible.

    Parameters
    ----------
    game_log_path:
        Path to P32 mlb_2024_game_identity_outcomes_joined.csv.
    base_paths:
        List of directories to scan. Defaults to standard repo directories.

    Returns
    -------
    P35PredictionRebuildFeasibilityResult
    """
    assert PAPER_ONLY is True, "PAPER_ONLY must be True"
    assert PRODUCTION_READY is False, "PRODUCTION_READY must be False"

    if base_paths is None:
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        base_paths = [
            os.path.join(repo_root, "wbc_backend"),
            os.path.join(repo_root, "scripts"),
            os.path.join(repo_root, "orchestrator"),
            os.path.join(repo_root, "data"),
        ]

    # Check game log exists and has minimum rows
    game_log_exists = os.path.isfile(game_log_path)

    # Scan for pipeline candidates
    feature_candidates = scan_feature_pipeline_candidates(base_paths)
    model_candidates = scan_model_training_candidates(base_paths)
    oof_candidates = scan_oof_generation_candidates(base_paths)

    feature_pipeline_found = len(feature_candidates) > 0
    model_training_found = len(model_candidates) > 0
    oof_generation_found = len(oof_candidates) > 0
    leakage_guard_found = _check_leakage_guards(base_paths)
    time_aware_split_found = _check_time_aware_split(base_paths)
    adapter_found = _check_2024_adapter(base_paths)

    # Determine feasibility status
    # Priority: pipeline missing → adapter missing → leakage risk → requires P36
    if not feature_pipeline_found and not model_training_found:
        feasibility_status = FEASIBILITY_BLOCKED_PIPELINE_MISSING
        blocker = (
            "No feature engineering or model training pipeline found in the repository. "
            "Cannot rebuild 2024 OOF predictions without a training pipeline."
        )
    elif not adapter_found:
        # Pipeline exists but is not configured for 2024 Retrosheet format
        feasibility_status = FEASIBILITY_BLOCKED_ADAPTER_MISSING
        blocker = (
            "Feature engineering pipeline exists (walk_forward_logistic.py, gbm_stack.py) "
            "but is configured for WBC/2025/2026 feature columns "
            "(indep_recent_win_rate_delta, indep_starter_era_delta, etc.). "
            "P32 2024 Retrosheet data provides game_id, game_date, home/away teams, "
            "and outcome columns only. A 2024-format feature engineering adapter "
            "is required to bridge P32 game log columns → model input features. "
            "Recommend: P36 builds this adapter with strict leakage guards."
        )
    elif not leakage_guard_found:
        feasibility_status = FEASIBILITY_BLOCKED_LEAKAGE_RISK
        blocker = (
            "Pipeline candidates found but leakage guards (temporal separation, "
            "date-aware split) are not confirmed. Block until leakage audit passes."
        )
    else:
        # All systems go structurally but implementation not done
        feasibility_status = FEASIBILITY_REQUIRES_P36_IMPLEMENTATION
        blocker = (
            "Pipeline structure appears feasible. However, the full OOF rebuild "
            "pipeline for 2024 has not been implemented. Recommend P36 to build and validate."
        )

    # Build sorted, de-duplicated candidate lists (relative to repo root)
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    def _rel(paths: List[str]) -> Tuple[str, ...]:
        return tuple(
            sorted({
                os.path.relpath(p, repo_root) if os.path.isabs(p) else p
                for p in paths
            })
        )

    return P35PredictionRebuildFeasibilityResult(
        feature_pipeline_found=feature_pipeline_found,
        model_training_found=model_training_found,
        oof_generation_found=oof_generation_found,
        leakage_guard_found=leakage_guard_found,
        time_aware_split_found=time_aware_split_found,
        adapter_for_2024_format_found=adapter_found,
        feasibility_status=feasibility_status,
        blocker_reason=blocker,
        candidate_scripts=_rel(oof_candidates[:10]),
        candidate_models=_rel(model_candidates[:10]),
        paper_only=True,
        production_ready=False,
        season=2024,
        notes=(
            "Do NOT run model training in P35. "
            "Do NOT fabricate p_oof. "
            "Leakage audit required before any predictions can be used."
        ),
    )


# ---------------------------------------------------------------------------
# Summarizer
# ---------------------------------------------------------------------------


def summarize_prediction_rebuild_feasibility(
    result: P35PredictionRebuildFeasibilityResult,
) -> str:
    """Return a human-readable summary of prediction rebuild feasibility."""
    lines = [
        "=== P35 Prediction Rebuild Feasibility ===",
        f"PAPER_ONLY=True  |  PRODUCTION_READY=False  |  season=2024",
        "",
        f"Feature pipeline found:        {result.feature_pipeline_found}",
        f"Model training found:          {result.model_training_found}",
        f"OOF generation found:          {result.oof_generation_found}",
        f"Leakage guard found:           {result.leakage_guard_found}",
        f"Time-aware split found:        {result.time_aware_split_found}",
        f"2024 adapter found:            {result.adapter_for_2024_format_found}",
        "",
        f"Feasibility status:  {result.feasibility_status}",
        f"Blocker:             {result.blocker_reason}",
        "",
        "Candidate OOF scripts:",
    ]
    for s in result.candidate_scripts:
        lines.append(f"  - {s}")
    lines.append("")
    lines.append("Candidate model trainers:")
    for m in result.candidate_models:
        lines.append(f"  - {m}")
    lines.append("")
    lines.append(f"Notes: {result.notes}")
    return "\n".join(lines)
