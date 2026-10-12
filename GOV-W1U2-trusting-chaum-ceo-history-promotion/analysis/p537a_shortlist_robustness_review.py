"""P537A — Shortlist Robustness Review Artifact (read-only, additive).

Builds a durable robustness review purely by relabeling and re-bucketing rows
already present in the committed P536K shortlist artifact
(outputs/research/p536k_lift_candidate_shortlist_20260708.json), which itself
extends the committed P536C artifact
(outputs/research/p536c_success_matrix_lift_extension_20260708.json).

No database is opened, no route/API/UI is touched, and no new statistical
metric is computed. Every value here is copied verbatim from a field the
P536K/P536C artifacts already produced; this module only re-groups existing
rows into owner-facing review buckets and verifies the P536K -> P536C
provenance hash chain.

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

TASK_ID = "P537A"
EXTENDS_TASK_ID = "P536K"
UPSTREAM_TASK_ID = "P536C"

OUTPUT_DIR = REPO_ROOT / "outputs" / "research"
DEFAULT_K_SOURCE_ARTIFACT = OUTPUT_DIR / "p536k_lift_candidate_shortlist_20260708.json"
DEFAULT_C_SOURCE_ARTIFACT = OUTPUT_DIR / "p536c_success_matrix_lift_extension_20260708.json"

DISCLAIMER_EN = (
    "Historical replay review artifact only; not a prediction, betting edge, "
    "future-winning, or production-readiness claim."
)

LABEL_STABLE = "stable_review_candidate"
LABEL_SHORT_WINDOW = "short_window_caution"
LABEL_COMBINATION = "combination_review_candidate"
LABEL_CROSS_LOTTERY = "cross_lottery_review_candidate"
LABEL_INSUFFICIENT = "insufficient_context"

INSUFFICIENT_REASON_COMBO = (
    "avg_prize_signal_lift_across_present_windows is null in the source P536K row; "
    "the primary combination metric (prize_signal_and_any_main_hit_per_window) is not "
    "fully computable from existing fields, even though a secondary any_main_hit_lift "
    "value may still be present per-window. Not classified into "
    "combination_candidates_for_followup to avoid overstating robustness."
)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _relative_or_absolute(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _label_rows(rows: list[dict[str, Any]], label: str) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        labeled = dict(row)
        labeled["review_label"] = label
        out.append(labeled)
    return out


def _split_combination_candidates(
    combo_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sufficient = [
        r for r in combo_rows
        if r.get("avg_prize_signal_lift_across_present_windows") is not None
    ]
    insufficient = [
        r for r in combo_rows
        if r.get("avg_prize_signal_lift_across_present_windows") is None
    ]
    return sufficient, insufficient


def run_review(
    k_source_path: Path = DEFAULT_K_SOURCE_ARTIFACT,
    c_source_path: Path = DEFAULT_C_SOURCE_ARTIFACT,
) -> dict[str, Any]:
    k = _load_json(k_source_path)
    c = _load_json(c_source_path)

    k_prov = k.get("provenance_and_limits", {})
    k_hash = k_prov.get("source_data_hash_sha256")
    c_hash = c.get("source", {}).get("data_hash_sha256")
    hash_chain_verified = k_hash is not None and k_hash == c_hash

    stable = _label_rows(k.get("stable_300_750_review_candidates", []), LABEL_STABLE)
    spike = _label_rows(k.get("short_window_spike_review_candidates", []), LABEL_SHORT_WINDOW)
    cross = _label_rows(k.get("cross_lottery_review_candidates", []), LABEL_CROSS_LOTTERY)

    combo_rows = k.get("combination_review_candidates", [])
    combo_sufficient, combo_insufficient = _split_combination_candidates(combo_rows)
    combo = _label_rows(combo_sufficient, LABEL_COMBINATION)

    insufficient = []
    for row in combo_insufficient:
        labeled = dict(row)
        labeled["review_label"] = LABEL_INSUFFICIENT
        labeled["insufficient_reason"] = INSUFFICIENT_REASON_COMBO
        insufficient.append(labeled)

    counts = {
        "stable_candidates_for_owner_review": len(stable),
        "short_window_spike_caution_list": len(spike),
        "combination_candidates_for_followup": len(combo),
        "cross_lottery_candidates_for_followup": len(cross),
        "insufficient_or_ambiguous_candidates": len(insufficient),
    }

    k_limitations = k_prov.get("limitations", [])
    limitations = list(k_limitations) + [
        "This review only relabels and re-buckets rows already selected by P536K; it does "
        "not re-run P536K's own selection filters against P536C, so any future drift "
        "between the two committed artifacts is not detected by this module alone (see "
        "hash_chain_verified for the one provenance check this module does perform).",
        "insufficient_or_ambiguous_candidates contains only combination rows where "
        "avg_prize_signal_lift_across_present_windows is null in the P536K source; other "
        "sections (stable/spike/cross-lottery) had no rows with missing required fields "
        "at generation time and so contribute nothing to this bucket.",
    ]

    return {
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "extends_task_id": EXTENDS_TASK_ID,
        "upstream_task_id": UPSTREAM_TASK_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "classification": "P537A_SHORTLIST_ROBUSTNESS_REVIEW_READY",
        "stable_candidates_for_owner_review": stable,
        "short_window_spike_caution_list": spike,
        "combination_candidates_for_followup": combo,
        "cross_lottery_candidates_for_followup": cross,
        "insufficient_or_ambiguous_candidates": insufficient,
        "provenance_and_limits": {
            "derived_from_artifact": _relative_or_absolute(k_source_path),
            "derived_from_task_id": k.get("task_id", EXTENDS_TASK_ID),
            "upstream_artifact": _relative_or_absolute(c_source_path),
            "upstream_task_id": c.get("task_id", UPSTREAM_TASK_ID),
            "source_generated_at": k.get("generated_at"),
            "upstream_source_generated_at": c.get("generated_at"),
            "source_data_hash_sha256": k_hash,
            "upstream_data_hash_sha256": c_hash,
            "hash_chain_verified": hash_chain_verified,
            "source_row_counts_by_lottery": k_prov.get("source_row_counts_by_lottery"),
            "selection_method": (
                "Deterministic relabeling and re-bucketing over fields already present in "
                "the committed P536K shortlist artifact only. No database access, no "
                "route/API/UI change, no new statistical metric, and no recomputation from "
                "P536C or raw replay rows — every numeric value here is copied verbatim "
                "from the P536K source artifact. Combination rows are split into "
                "combination_candidates_for_followup / insufficient_or_ambiguous_candidates "
                "purely on whether avg_prize_signal_lift_across_present_windows is present."
            ),
            "counts": counts,
            "limitations": limitations,
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
    add("# P537A — Shortlist Robustness Review (Owner/CTO Review Artifact)")
    add("")
    add(f"> {DISCLAIMER_EN}")
    add("")
    prov = result["provenance_and_limits"]
    add(
        f"Derived from: **{result['extends_task_id']}** (`{prov['derived_from_artifact']}`), "
        f"which extends **{result['upstream_task_id']}** (`{prov['upstream_artifact']}`)."
    )
    add("")
    add(f"- hash_chain_verified: **{prov['hash_chain_verified']}**")
    add(f"- source_data_hash_sha256 (P536K): `{prov['source_data_hash_sha256']}`")
    add(f"- upstream_data_hash_sha256 (P536C): `{prov['upstream_data_hash_sha256']}`")
    add("")

    add("## Counts")
    add("")
    for key, value in result["provenance_and_limits"]["counts"].items():
        add(f"- {key}: **{value}**")
    add("")

    add("## Stable Candidates For Owner Review (window ∈ {300, 750}, positive lift)")
    add("")
    add("| lottery | strategy | family | pick_k | window | support | observed | baseline | lift | log10(lift) |")
    add("|---|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in result["stable_candidates_for_owner_review"][:25]:
        add(
            f"| {r['lottery_type']} | `{r['strategy_id']}` | {r['feature_family']} | "
            f"{r['pick_k']} | {r['window']} | {r['support_draws']} | "
            f"{_pct(r['observed_rate'])} | {_pct(r['baseline_rate'])} | "
            f"{_fmt_lift(r['lift'])} | {r['log10_lift']} |"
        )
    if len(result["stable_candidates_for_owner_review"]) > 25:
        add(f"\n_...and {len(result['stable_candidates_for_owner_review']) - 25} more rows in the JSON artifact._")
    add("")

    add("## Short-Window Spike Caution List (window=50, review-only)")
    add("")
    add("| lottery | strategy | family | pick_k | support | observed | baseline | lift |")
    add("|---|---|---|---:|---:|---:|---:|---:|")
    for r in result["short_window_spike_caution_list"][:25]:
        add(
            f"| {r['lottery_type']} | `{r['strategy_id']}` | {r['feature_family']} | "
            f"{r['pick_k']} | {r['support_draws']} | {_pct(r['observed_rate'])} | "
            f"{_pct(r['baseline_rate'])} | {_fmt_lift(r['lift'])} |"
        )
    if len(result["short_window_spike_caution_list"]) > 25:
        add(f"\n_...and {len(result['short_window_spike_caution_list']) - 25} more rows in the JSON artifact._")
    add("")

    add("## Combination Candidates For Followup (present in ≥2 windows, prize-signal lift known)")
    add("")
    add("| lottery | combo_id | budget | windows_present | avg_prize_signal_lift | stability_rank |")
    add("|---|---|---:|---|---:|---:|")
    for r in result["combination_candidates_for_followup"][:25]:
        add(
            f"| {r['lottery_type']} | `{r['combo_id']}` | {r['requested_budget']} | "
            f"{r['windows_present']} | "
            f"{_fmt_lift(r.get('avg_prize_signal_lift_across_present_windows'))} | "
            f"{r['stability_rank']} |"
        )
    if len(result["combination_candidates_for_followup"]) > 25:
        add(f"\n_...and {len(result['combination_candidates_for_followup']) - 25} more rows in the JSON artifact._")
    add("")

    add("## Cross-Lottery Candidates For Followup (≥2 lotteries, side-by-side, never pooled)")
    add("")
    add("| family | window | pick_k | lotteries present |")
    add("|---|---:|---:|---|")
    for r in result["cross_lottery_candidates_for_followup"][:25]:
        add(f"| {r['feature_family']} | {r['window']} | {r['pick_k']} | {', '.join(sorted(r['lotteries'].keys()))} |")
    if len(result["cross_lottery_candidates_for_followup"]) > 25:
        add(f"\n_...and {len(result['cross_lottery_candidates_for_followup']) - 25} more rows in the JSON artifact._")
    add("")

    add("## Insufficient Or Ambiguous Candidates (missing fields, not safely classifiable)")
    add("")
    add("| lottery | combo_id | budget | windows_present | reason |")
    add("|---|---|---:|---|---|")
    for r in result["insufficient_or_ambiguous_candidates"][:25]:
        add(
            f"| {r['lottery_type']} | `{r['combo_id']}` | {r['requested_budget']} | "
            f"{r['windows_present']} | {r['insufficient_reason']} |"
        )
    if len(result["insufficient_or_ambiguous_candidates"]) > 25:
        add(f"\n_...and {len(result['insufficient_or_ambiguous_candidates']) - 25} more rows in the JSON artifact._")
    add("")

    add("## Provenance & Limits")
    add("")
    add(f"- derived_from_task_id: **{prov['derived_from_task_id']}**")
    add(f"- upstream_task_id: **{prov['upstream_task_id']}**")
    add(f"- source_generated_at: `{prov['source_generated_at']}`")
    add(f"- upstream_source_generated_at: `{prov['upstream_source_generated_at']}`")
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
    json_path = OUTPUT_DIR / f"p537a_shortlist_robustness_review_{stamp}.json"
    md_path = OUTPUT_DIR / f"p537a_shortlist_robustness_review_{stamp}.md"
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    default_json, default_md = _default_dated_paths()
    parser = argparse.ArgumentParser(description="Build P537A shortlist robustness review artifact")
    parser.add_argument("--k-source", default=str(DEFAULT_K_SOURCE_ARTIFACT))
    parser.add_argument("--c-source", default=str(DEFAULT_C_SOURCE_ARTIFACT))
    parser.add_argument("--out-json", default=str(default_json))
    parser.add_argument("--out-md", default=str(default_md))
    args = parser.parse_args(argv)

    result = run_review(Path(args.k_source), Path(args.c_source))
    write_artifacts(result, Path(args.out_json), Path(args.out_md))
    print(
        json.dumps(
            {
                "task_id": result["task_id"],
                "classification": result["classification"],
                "counts": result["provenance_and_limits"]["counts"],
                "hash_chain_verified": result["provenance_and_limits"]["hash_chain_verified"],
                "out_json": args.out_json,
                "out_md": args.out_md,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
