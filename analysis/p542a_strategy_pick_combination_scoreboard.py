"""P542A — read-only strategy pick / combination scoreboard.

This report is a retrospective description of persisted ``PREDICTED`` replay
rows.  It neither produces replay rows nor makes a prediction, promotion, or
betting claim.  The report deliberately uses deterministic content: it has no
wall-clock field and its digest is calculated from the analytic payload.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analysis import p333_strategy_pick_combination_scoreboard as p333

DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P333_ARTIFACT = (
    REPO_ROOT / "outputs" / "research" / "p333_strategy_pick_combination_scoreboard_20260702.json"
)
OUTPUT_JSON = (
    REPO_ROOT / "outputs" / "research" / "p542a_strategy_pick_combination_scoreboard_20260710.json"
)
OUTPUT_MD = (
    REPO_ROOT / "outputs" / "research" / "p542a_strategy_pick_combination_scoreboard_20260710.md"
)

TASK_ID = "P542A"
CLASSIFICATION = "P542A_STRATEGY_PICK_COMBINATION_SCOREBOARD_DESCRIPTIVE_COMPLETE"
LOTTERIES = p333.LOTTERIES
WINDOWS = p333.WINDOWS
DISCLAIMER_ZH = (
    "本報告僅描述既有 replay 的歷史統計與隨機基準比較；不預測未來、"
    "不構成投注建議，也不表示任何策略可上線或可獲利。"
)


def _open_read_only(db_path: Path | str) -> sqlite3.Connection:
    """Open SQLite exclusively read-only and reject writes at the connection."""
    resolved = Path(db_path).resolve()
    conn = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rate(value: Any) -> float | None:
    return None if value is None else float(value)


def _power_zone2_row(record: dict[str, Any], scope: str) -> dict[str, Any]:
    """Expose the POWER_LOTTO zone-2 result with its matched random baseline."""
    avg_candidates = _rate(record.get("avg_second_zone_candidates"))
    random_rate = None if avg_candidates is None else avg_candidates / 8.0
    observed_rate = _rate(record.get("second_zone_hit_rate"))
    identifier = record.get("strategy_id") or record.get("combo_id")
    return {
        "scope": scope,
        "identifier": identifier,
        "window": record["window"],
        "support_draws": record["support_draws"],
        "avg_zone2_candidates": avg_candidates,
        "zone2_hit_count": record.get("second_zone_hit_count"),
        "zone2_hit_rate": observed_rate,
        "random_zone2_hit_rate": random_rate,
        "zone2_hit_edge_pp": (
            None if observed_rate is None or random_rate is None else (observed_rate - random_rate) * 100
        ),
        "prize_aware_hit_rate": record.get("prize_signal_rate"),
        "random_prize_aware_hit_rate": record.get("baseline_prize_signal_rate"),
        "prize_aware_edge_pp": record.get("prize_signal_edge_pp"),
    }


def _build_power_zone2_metrics(
    strategy_pick_matrix: Iterable[dict[str, Any]],
    combination_leaderboard: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = [
        _power_zone2_row(record, "strategy_pick")
        for record in strategy_pick_matrix
        if record["lottery_type"] == "POWER_LOTTO"
    ]
    rows.extend(
        _power_zone2_row(record, "combination")
        for record in combination_leaderboard
        if record["lottery_type"] == "POWER_LOTTO"
    )
    return sorted(
        rows,
        key=lambda row: (
            row["scope"],
            row["window"],
            str(row["identifier"]),
        ),
    )


def _describe_top_records(
    strategy_pick_matrix: list[dict[str, Any]],
    best_combinations: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Return descriptive lookups only; no pass/fail or forward decision labels."""
    top_pick = p333.build_top_strategy_pick_index(strategy_pick_matrix)
    return {
        "top_strategy_pick_by_lottery_window_pick": top_pick,
        "best_combination_by_lottery_window_budget": best_combinations,
        "ranking_basis": (
            "Historical replay rows ranked within equal lottery/window/main-number-budget buckets; "
            "the displayed rates are descriptive and include matched analytic random baselines."
        ),
    }


def _annotate_comparisons(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add an explicit, auditable random-baseline comparison to each score row."""
    annotated: list[dict[str, Any]] = []
    for source in records:
        record = copy.deepcopy(source)
        record["random_baseline_comparison"] = {
            "any_main_hit_rate": record.get("baseline_any_main_rate"),
            "prize_aware_hit_rate": record.get("baseline_prize_signal_rate"),
            "any_main_hit_edge_pp": record.get("any_main_hit_edge_pp"),
            "prize_aware_hit_edge_pp": record.get("prize_signal_edge_pp"),
        }
        record["prize_aware_metrics"] = {
            "hit_count": record.get("prize_signal_count"),
            "hit_rate": record.get("prize_signal_rate"),
            "random_hit_rate": record.get("baseline_prize_signal_rate"),
            "edge_pp": record.get("prize_signal_edge_pp"),
        }
        annotated.append(record)
    return annotated


def _load_committed_p333_artifact(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Read the committed replay-only P333 artifact when a worktree has no DB copy."""
    if not path.is_file():
        raise FileNotFoundError(
            f"no readable database at {DB_PATH} and committed input is missing: {path}"
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "strategy_pick_matrix",
        "combination_leaderboard",
        "best_combination_by_lottery_window_budget",
        "source",
    }
    missing = sorted(required - set(payload))
    if payload.get("task_id") != "P333" or missing:
        raise ValueError(f"invalid P333 input artifact; missing={missing}")
    source = {
        "source_kind": "committed_P333_replay_scoreboard",
        "input_artifact": str(path.resolve()),
        "input_artifact_sha256": _sha256_file(path),
        "db_opened": False,
        "db_open_mode": "not opened; inherited replay statistics from committed P333 artifact",
        "baseline": payload["source"]["baseline"],
    }
    return (
        source,
        payload["strategy_pick_matrix"],
        payload["combination_leaderboard"],
        payload["best_combination_by_lottery_window_budget"],
    )


def run_analysis(
    db_path: Path | str = DB_PATH,
    source_artifact: Path | str = P333_ARTIFACT,
) -> dict[str, Any]:
    """Build the P542A report without generating replay data or writing a DB.

    A supplied database is opened only with the guarded read-only URI.  The
    default worktree path intentionally falls back to the committed P333
    replay-only artifact when the ignored SQLite file is unavailable.
    """
    resolved_db = Path(db_path)
    if resolved_db.is_file():
        conn = _open_read_only(resolved_db)
        try:
            if conn.execute("PRAGMA query_only").fetchone()[0] != 1:
                raise RuntimeError("read-only guard was not enabled")
            baseline = p333._db_baseline(conn)
            replay_draws = p333._load_replay_draws(conn)
        finally:
            conn.close()
        source = {
            "source_kind": "read_only_strategy_prediction_replays",
            "db_path": str(resolved_db.resolve()),
            "table": "strategy_prediction_replays",
            "filters": {
                "lottery_type": list(LOTTERIES),
                "replay_status": "PREDICTED",
                "dry_run": 0,
            },
            "db_opened": True,
            "db_open_mode": "sqlite URI mode=ro; PRAGMA query_only=ON",
            "baseline": baseline,
        }
        strategy_pick_matrix = p333.build_strategy_pick_matrix(replay_draws)
        raw_leaderboard, raw_best_combinations = p333.build_combination_leaderboard(
            replay_draws
        )
    else:
        source, strategy_pick_matrix, raw_leaderboard, raw_best_combinations = (
            _load_committed_p333_artifact(Path(source_artifact))
        )

    strategy_pick_matrix = _annotate_comparisons(strategy_pick_matrix)
    combination_leaderboard = _annotate_comparisons(raw_leaderboard)
    best_combinations = {
        bucket: _annotate_comparisons([record])[0]
        for bucket, record in sorted(raw_best_combinations.items())
    }
    top = _describe_top_records(strategy_pick_matrix, best_combinations)
    zone2_metrics = _build_power_zone2_metrics(
        strategy_pick_matrix, combination_leaderboard
    )

    artifact: dict[str, Any] = {
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "classification": CLASSIFICATION,
        "historical_replay_only": True,
        "no_prediction_claim": True,
        "no_betting_advice": True,
        "deterministic_output": True,
        "source": source,
        "window_policy": {
            "draw_windows": list(WINDOWS),
            "minimum_support_draws": p333.MIN_SUPPORT_DRAWS,
            "window_selection": "latest available target draws per strategy or common strategy intersection",
        },
        "metric_definitions": {
            "pick_k": "first K distinct predicted main numbers ordered by bet_index then stored prediction order",
            "any_main_hit": "at least one selected main number is in the actual main draw",
            "prize_aware_endpoint": {
                lottery: p333.GAME_RULES[lottery]["endpoint"] for lottery in LOTTERIES
            },
            "random_baseline": "analytic hypergeometric baseline matched to selected main-number and zone-2 candidate counts",
            "power_lotto_zone2": "observed predicted second-zone hit rate compared with avg candidate count divided by 8",
        },
        "summary": {
            "strategy_pick_records": len(strategy_pick_matrix),
            "combination_leaderboard_records": len(combination_leaderboard),
            "power_lotto_zone2_records": len(zone2_metrics),
            "strategy_count_by_lottery": source["baseline"]["strategy_counts_by_lottery"],
        },
        "strategy_pick_matrix": strategy_pick_matrix,
        "combination_leaderboard": combination_leaderboard,
        "descriptive_rankings": top,
        "power_lotto_zone2_metrics": zone2_metrics,
        "safety_flags": {
            "db_read_only": True,
            "db_opened": source["db_opened"],
            "db_write": False,
            "replay_generation": False,
            "model_training": False,
            "production_code_change": False,
            "betting_advice": False,
        },
        "disclaimer_zh": DISCLAIMER_ZH,
    }
    artifact["deterministic_payload_sha256"] = _digest(artifact)
    return artifact


def _pct(value: Any) -> str:
    return "-" if value is None else f"{float(value) * 100:.2f}%"


def _pp(value: Any) -> str:
    return "-" if value is None else f"{float(value):+.2f}pp"


def render_markdown(artifact: dict[str, Any]) -> str:
    """Render a stable human-readable summary of the complete JSON report."""
    lines = [
        "# P542A — Strategy Pick / Combination Scoreboard",
        "",
        f"> {artifact['disclaimer_zh']}",
        "",
        "## Scope",
        "",
        "- Historical replay rows only; no prediction, replay generation, training, or betting advice.",
        "- Draw windows: 50, 300, and 750 latest eligible target draws.",
        "- Random comparisons are analytic baselines matched to the selected budget.",
        "",
        "## Summary",
        "",
        f"- strategy_pick_records: **{artifact['summary']['strategy_pick_records']}**",
        f"- combination_leaderboard_records: **{artifact['summary']['combination_leaderboard_records']}**",
        f"- power_lotto_zone2_records: **{artifact['summary']['power_lotto_zone2_records']}**",
        f"- deterministic_payload_sha256: `{artifact['deterministic_payload_sha256']}`",
        "",
        "## Best Equal-Budget Combinations (750 Draw Window)",
        "",
        "| lottery | budget | combination | support | any-main hit | prize-aware hit | prize edge |",
        "|---|---:|---|---:|---:|---:|---:|",
    ]
    best = artifact["descriptive_rankings"]["best_combination_by_lottery_window_budget"]
    for lottery in LOTTERIES:
        for budget in range(1, int(p333.GAME_RULES[lottery]["pick_count"]) + 1):
            record = best.get(f"{lottery}|750|{budget}")
            if record is None:
                continue
            lines.append(
                f"| {lottery} | {budget} | `{record['combo_id']}` | {record['support_draws']} | "
                f"{_pct(record['any_main_hit_rate'])} | {_pct(record['prize_signal_rate'])} | "
                f"{_pp(record['prize_signal_edge_pp'])} |"
            )

    lines.extend(
        [
            "",
            "## Top Strategy Pick-K (750 Draw Window)",
            "",
            "| lottery | K | strategy | support | any-main hit | prize-aware hit | random prize baseline |",
            "|---|---:|---|---:|---:|---:|---:|",
        ]
    )
    top_pick = artifact["descriptive_rankings"]["top_strategy_pick_by_lottery_window_pick"]
    for lottery in LOTTERIES:
        for pick_k in range(1, int(p333.GAME_RULES[lottery]["pick_count"]) + 1):
            record = top_pick.get(f"{lottery}|750|{pick_k}")
            if record is None:
                continue
            lines.append(
                f"| {lottery} | {pick_k} | `{record['strategy_id']}` | {record['support_draws']} | "
                f"{_pct(record['any_main_hit_rate'])} | {_pct(record['prize_signal_rate'])} | "
                f"{_pct(record['baseline_prize_signal_rate'])} |"
            )

    lines.extend(
        [
            "",
            "## Power Lotto Zone-2 Metrics (750 Draw Window)",
            "",
            "| scope | identifier | support | zone-2 hit | random zone-2 baseline | zone-2 edge |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for record in artifact["power_lotto_zone2_metrics"]:
        if record["window"] != 750:
            continue
        lines.append(
            f"| {record['scope']} | `{record['identifier']}` | {record['support_draws']} | "
            f"{_pct(record['zone2_hit_rate'])} | {_pct(record['random_zone2_hit_rate'])} | "
            f"{_pp(record['zone2_hit_edge_pp'])} |"
        )

    lines.extend(["", "## Safety", ""])
    for key, value in artifact["safety_flags"].items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    lines.append("")
    return "\n".join(lines)


def write_artifacts(artifact: dict[str, Any], out_json: Path, out_md: Path) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    out_md.write_text(render_markdown(artifact).rstrip() + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the read-only P542A scoreboard")
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--source-artifact", default=str(P333_ARTIFACT))
    parser.add_argument("--out-json", default=str(OUTPUT_JSON))
    parser.add_argument("--out-md", default=str(OUTPUT_MD))
    args = parser.parse_args(argv)
    artifact = run_analysis(args.db, args.source_artifact)
    write_artifacts(artifact, Path(args.out_json), Path(args.out_md))
    print(
        json.dumps(
            {
                "task_id": artifact["task_id"],
                "classification": artifact["classification"],
                "deterministic_payload_sha256": artifact["deterministic_payload_sha256"],
                "out_json": args.out_json,
                "out_md": args.out_md,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
