"""P536K — Lift Candidate Shortlist Artifact (read-only, additive).

Builds a durable review shortlist purely by filtering rows already present in
the committed P536C artifact (outputs/research/p536c_success_matrix_lift_extension_20260708.json).

No database is opened, no route/API/UI is touched, and no new statistical
metric is computed. Every value in the shortlist is copied verbatim from a
field the P536C artifact already produced; this module only selects which
existing rows to surface and adds human-readable why_included / caution_label
annotations.

This is a historical replay review artifact only; not a prediction, betting
edge, future-winning, or production-readiness claim.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TASK_ID = "P536K"
EXTENDS_TASK_ID = "P536C"

OUTPUT_DIR = REPO_ROOT / "outputs" / "research"
DEFAULT_SOURCE_ARTIFACT = OUTPUT_DIR / "p536c_success_matrix_lift_extension_20260708.json"

DISCLAIMER_EN = (
    "Historical replay review artifact only; not a prediction, betting edge, "
    "future-winning, or production-readiness claim."
)
CAUTION_STANDARD = (
    "Historical replay review only; not a prediction or betting edge."
)
CAUTION_SPIKE = (
    "SHORT-WINDOW SPIKE — review only, not a stable pattern; do not treat as a validated edge."
)
CAUTION_CROSS_LOTTERY = (
    "Historical replay review only; not a prediction or betting edge. Cross-lottery "
    "comparison uses each lottery's own baseline; rates are never pooled across games."
)

MAIN_HIT_METRIC = "any_main_hit"


def _load_source_artifact(source_path: Path) -> dict[str, Any]:
    with source_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _relative_or_absolute(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _stable_300_750_review_candidates(matrix: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        r for r in matrix
        if r.get("window") in (300, 750)
        and r.get("any_main_hit_lift") is not None
        and r["any_main_hit_lift"] > 1
    ]
    rows.sort(key=lambda r: (r["lottery_type"], r["strategy_id"], r["window"], r["pick_k"]))
    return [
        {
            "lottery_type": r["lottery_type"],
            "window": r["window"],
            "strategy_id": r["strategy_id"],
            "feature_family": r.get("feature_family"),
            "pick_k": r["pick_k"],
            "metric": MAIN_HIT_METRIC,
            "observed_rate": r.get("any_main_hit_rate"),
            "baseline_rate": r.get("baseline_any_main_hit_rate"),
            "lift": r.get("any_main_hit_lift"),
            "log10_lift": r.get("any_main_hit_log10_lift"),
            "support_draws": r.get("support_draws"),
            "why_included": (
                "window∈{300,750} with any_main_hit_lift > 1 "
                "(positive lift over the hypergeometric baseline)"
            ),
            "caution_label": CAUTION_STANDARD,
        }
        for r in rows
    ]


def _short_window_spike_review_candidates(matrix: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        r for r in matrix
        if r.get("window") == 50
        and r.get("any_main_hit_lift") is not None
        and r["any_main_hit_lift"] > 1
    ]
    rows.sort(key=lambda r: (r["lottery_type"], r["strategy_id"], r["pick_k"]))
    return [
        {
            "lottery_type": r["lottery_type"],
            "window": r["window"],
            "strategy_id": r["strategy_id"],
            "feature_family": r.get("feature_family"),
            "pick_k": r["pick_k"],
            "metric": MAIN_HIT_METRIC,
            "observed_rate": r.get("any_main_hit_rate"),
            "baseline_rate": r.get("baseline_any_main_hit_rate"),
            "lift": r.get("any_main_hit_lift"),
            "log10_lift": r.get("any_main_hit_log10_lift"),
            "support_draws": r.get("support_draws"),
            "why_included": (
                "window=50 (short-window) with any_main_hit_lift > 1; "
                "short-window-review-only, may not persist at 300/750"
            ),
            "caution_label": CAUTION_SPIKE,
        }
        for r in rows
    ]


def _combination_review_candidates(stability_rank: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [r for r in stability_rank if r.get("windows_present_count", 0) >= 2]
    rows.sort(key=lambda r: (r["lottery_type"], r["stability_rank"]))
    return [
        {
            "lottery_type": r["lottery_type"],
            "combo_id": r["combo_id"],
            "requested_budget": r.get("requested_budget"),
            "windows_present": r.get("windows_present"),
            "windows_present_count": r.get("windows_present_count"),
            "metric": "prize_signal_and_any_main_hit_per_window",
            "avg_prize_signal_lift_across_present_windows": r.get(
                "avg_prize_signal_lift_across_present_windows"
            ),
            "per_window": r.get("per_window"),
            "stability_rank": r.get("stability_rank"),
            "why_included": (
                "combo already present in P333's own top-10-per-bucket leaderboard for "
                ">=2 of the 3 windows (multi-window stability signal, no new search)"
            ),
            "caution_label": CAUTION_STANDARD,
        }
        for r in rows
    ]


def _cross_lottery_review_candidates(cross_lift: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [r for r in cross_lift if len(r.get("lotteries", {})) >= 2]
    rows.sort(key=lambda r: (r["feature_family"], r["window"], r["pick_k"]))
    return [
        {
            "feature_family": r["feature_family"],
            "window": r["window"],
            "pick_k": r["pick_k"],
            "lotteries": r["lotteries"],
            "why_included": (
                "normalized lift record present for >=2 lotteries at this "
                "feature_family/window/pick_k, shown side-by-side (never pooled)"
            ),
            "caution_label": CAUTION_CROSS_LOTTERY,
        }
        for r in rows
    ]


def run_shortlist(source_path: Path = DEFAULT_SOURCE_ARTIFACT) -> dict[str, Any]:
    source = _load_source_artifact(source_path)

    matrix = source["strategy_pick_matrix_lift_extension"]
    cross_lift = source["cross_lottery_normalized_lift"]
    stability_rank = source["combination_stability_rank"]

    stable = _stable_300_750_review_candidates(matrix)
    spike = _short_window_spike_review_candidates(matrix)
    combo = _combination_review_candidates(stability_rank)
    cross = _cross_lottery_review_candidates(cross_lift)

    return {
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "extends_task_id": EXTENDS_TASK_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "classification": "P536K_LIFT_CANDIDATE_SHORTLIST_READY",
        "stable_300_750_review_candidates": stable,
        "short_window_spike_review_candidates": spike,
        "combination_review_candidates": combo,
        "cross_lottery_review_candidates": cross,
        "provenance_and_limits": {
            "derived_from_artifact": _relative_or_absolute(source_path),
            "derived_from_task_id": source.get("task_id"),
            "source_generated_at": source.get("generated_at"),
            "source_data_hash_sha256": source.get("source", {}).get("data_hash_sha256"),
            "source_row_counts_by_lottery": source.get("source", {}).get("row_counts_by_lottery"),
            "selection_method": (
                "Deterministic filters over fields already present in the P536C artifact "
                "only. No database access, no route/API/UI change, no new statistical "
                "metric, and no recomputation from raw replay rows — every numeric "
                "value here is copied verbatim from the source artifact."
            ),
            "counts": {
                "stable_300_750_review_candidates": len(stable),
                "short_window_spike_review_candidates": len(spike),
                "combination_review_candidates": len(combo),
                "cross_lottery_review_candidates": len(cross),
            },
            "limitations": [
                "Retrospective replay evidence only; does not imply future performance.",
                "Short-window (50-draw) spike rows are especially prone to reversal; "
                "treat as review-only, not a stable pattern.",
                "Combination rows are an enrichment over P333's existing top-10-per-bucket "
                "leaderboard, not an independent re-search of the full combination space.",
                "Cross-lottery rows compare normalized lift only; raw hit rates are never "
                "pooled across games because each game has a different hypergeometric baseline.",
                "No strategy promotion, ranking formula, or new metric is introduced by "
                "this shortlist; it is a read-only view over already-computed P536C fields.",
            ],
            "disclaimer_en": DISCLAIMER_EN,
        },
    }


def _pct(value: Any) -> str:
    if value is None:
        return "-"
    return f"{float(value) * 100:.2f}%"


def _fmt_lift(value: Any) -> str:
    if value is None:
        return "-"
    return f"{float(value):.3f}x"


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    add = lines.append
    add("# P536K — Lift Candidate Shortlist (Review Artifact)")
    add("")
    add(f"> {DISCLAIMER_EN}")
    add("")
    add(f"Derived from: **{result['extends_task_id']}** "
        f"(`{result['provenance_and_limits']['derived_from_artifact']}`)")
    add("")

    add("## Counts")
    add("")
    for key, value in result["provenance_and_limits"]["counts"].items():
        add(f"- {key}: **{value}**")
    add("")

    add("## Stable 300/750 Review Candidates")
    add("")
    add("| lottery | strategy | family | pick_k | window | support | observed | baseline | lift | log10(lift) |")
    add("|---|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in result["stable_300_750_review_candidates"][:25]:
        add(
            f"| {r['lottery_type']} | `{r['strategy_id']}` | {r['feature_family']} | "
            f"{r['pick_k']} | {r['window']} | {r['support_draws']} | "
            f"{_pct(r['observed_rate'])} | {_pct(r['baseline_rate'])} | "
            f"{_fmt_lift(r['lift'])} | {r['log10_lift']} |"
        )
    if len(result["stable_300_750_review_candidates"]) > 25:
        add(f"\n_...and {len(result['stable_300_750_review_candidates']) - 25} more rows in the JSON artifact._")
    add("")

    add("## Short-Window Spike Review Candidates (window=50, review-only)")
    add("")
    add("| lottery | strategy | family | pick_k | support | observed | baseline | lift |")
    add("|---|---|---|---:|---:|---:|---:|---:|")
    for r in result["short_window_spike_review_candidates"][:25]:
        add(
            f"| {r['lottery_type']} | `{r['strategy_id']}` | {r['feature_family']} | "
            f"{r['pick_k']} | {r['support_draws']} | {_pct(r['observed_rate'])} | "
            f"{_pct(r['baseline_rate'])} | {_fmt_lift(r['lift'])} |"
        )
    if len(result["short_window_spike_review_candidates"]) > 25:
        add(f"\n_...and {len(result['short_window_spike_review_candidates']) - 25} more rows in the JSON artifact._")
    add("")

    add("## Combination Review Candidates (present in ≥2 windows)")
    add("")
    add("| lottery | combo_id | budget | windows_present | stability_rank |")
    add("|---|---|---:|---|---:|")
    for r in result["combination_review_candidates"][:25]:
        add(
            f"| {r['lottery_type']} | `{r['combo_id']}` | {r['requested_budget']} | "
            f"{r['windows_present']} | {r['stability_rank']} |"
        )
    if len(result["combination_review_candidates"]) > 25:
        add(f"\n_...and {len(result['combination_review_candidates']) - 25} more rows in the JSON artifact._")
    add("")

    add("## Cross-Lottery Review Candidates (≥2 lotteries, side-by-side, never pooled)")
    add("")
    add("| family | window | pick_k | lotteries present |")
    add("|---|---:|---:|---|")
    for r in result["cross_lottery_review_candidates"][:25]:
        add(f"| {r['feature_family']} | {r['window']} | {r['pick_k']} | {', '.join(sorted(r['lotteries'].keys()))} |")
    if len(result["cross_lottery_review_candidates"]) > 25:
        add(f"\n_...and {len(result['cross_lottery_review_candidates']) - 25} more rows in the JSON artifact._")
    add("")

    add("## Provenance & Limits")
    add("")
    prov = result["provenance_and_limits"]
    add(f"- derived_from_task_id: **{prov['derived_from_task_id']}**")
    add(f"- source_generated_at: `{prov['source_generated_at']}`")
    add(f"- source_data_hash_sha256: `{prov['source_data_hash_sha256']}`")
    add(f"- selection_method: {prov['selection_method']}")
    add("- limitations:")
    for item in prov["limitations"]:
        add(f"  - {item}")
    add("")
    add(f"> {prov['disclaimer_en']}")
    add("")
    return "\n".join(lines)


def write_artifacts(result: dict[str, Any], out_json: Path, out_md: Path) -> None:
    if out_json.exists():
        raise FileExistsError(f"refusing to overwrite existing artifact: {out_json}")
    if out_md.exists():
        raise FileExistsError(f"refusing to overwrite existing artifact: {out_md}")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(render_markdown(result) + "\n", encoding="utf-8")


def _default_dated_paths() -> tuple[Path, Path]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    json_path = OUTPUT_DIR / f"p536k_lift_candidate_shortlist_{stamp}.json"
    md_path = OUTPUT_DIR / f"p536k_lift_candidate_shortlist_{stamp}.md"
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    default_json, default_md = _default_dated_paths()
    parser = argparse.ArgumentParser(description="Build P536K lift candidate shortlist artifact")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE_ARTIFACT))
    parser.add_argument("--out-json", default=str(default_json))
    parser.add_argument("--out-md", default=str(default_md))
    args = parser.parse_args(argv)

    result = run_shortlist(Path(args.source))
    write_artifacts(result, Path(args.out_json), Path(args.out_md))
    print(
        json.dumps(
            {
                "task_id": result["task_id"],
                "classification": result["classification"],
                "counts": result["provenance_and_limits"]["counts"],
                "out_json": args.out_json,
                "out_md": args.out_md,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
