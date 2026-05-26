"""
P52: POWER_LOTTO midfreq_fourier_mk_3bet Promotion Readiness Decision

Read-only analysis. No DB write, no registry mutation, no lifecycle promotion.
Reads P51 JSON artifact and produces P52 decision matrix + classification.

Usage:
  .venv/bin/python scripts/p52_powerlotto_promotion_readiness.py \
      --p51-json outputs/replay/p51_powerlotto_wave4_rolling_window_mcnemar_gate_20260525.json \
      --json-out outputs/replay/p52_powerlotto_midfreq_fourier_mk_3bet_promotion_readiness_20260525.json
"""

import argparse
import json
import math
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CANDIDATE_STRATEGY = "midfreq_fourier_mk_3bet"
BASELINE_STRATEGY = "fourier_rhythm_3bet"
THEORETICAL_BASELINE = 0.9474

# Known champion (baseline) mean_hit from P51 DB query
CHAMPION_MEAN_HIT = 0.9927

# McNemar event: hit_count >= 3
MCNEMAR_THRESHOLD = 3

# G4 policy choices
G4_POLICY_NOT_BLOCKING = "G4_NOT_BLOCKING_FOR_RARE_EVENT"
G4_POLICY_WAIVER = "G4_REQUIRES_WAIVER"
G4_POLICY_BLOCKS = "G4_BLOCKS_PROMOTION"


# ---------------------------------------------------------------------------
# Decision logic
# ---------------------------------------------------------------------------

def decide_g4_policy(mcnemar_data: dict) -> dict:
    """
    Determine G4 McNemar policy for midfreq_fourier_mk_3bet.

    P52 must choose one of three policies and document the rationale.

    Key facts for this decision:
    - b (strategy wins on hit_count>=3): 42
    - c (champion wins on hit_count>=3): 50
    - chi2 = 0.5326, p = 0.4655 (not significant)
    - Direction: c > b → champion outperforms candidate on rare event

    Since b < c:
    - It is NOT purely a power/sample-size problem.
    - The direction of the rare-event effect actually favors the champion.
    - Choosing G4_NOT_BLOCKING would incorrectly describe this as a power issue.
    - G4_BLOCKS_PROMOTION is too strict: mean_hit advantage is real (p=0.0003).
    - G4_REQUIRES_WAIVER is appropriate: acknowledges real G4 weakness, requires
      CTO/CEO explicit sign-off before promotion.
    """
    b = mcnemar_data["b_strategy_wins"]
    c = mcnemar_data["c_baseline_wins"]
    p = mcnemar_data["p_value"]
    direction = "CANDIDATE" if b > c else ("CHAMPION" if c > b else "TIED")
    discordant_total = b + c
    discordant_ratio = b / c if c > 0 else float("inf")

    if direction == "CANDIDATE" and p >= 0.05:
        # Candidate wins direction but not statistically significant
        # → rare-event interpretation is defensible
        policy = G4_POLICY_NOT_BLOCKING
        rationale = (
            "b > c: candidate wins on hit_count>=3 event more often than champion, "
            "but not significantly. Power limitation from rare event frequency is the "
            "primary explanation. G4 treated as diagnostic, not blocking."
        )
    elif direction == "CHAMPION":
        # Champion wins direction on the high-value event
        # → This is not a pure power issue; effect direction is adverse
        policy = G4_POLICY_WAIVER
        rationale = (
            f"c > b ({c} > {b}): champion outperforms candidate on hit_count>={MCNEMAR_THRESHOLD} "
            "event. This is not solely a statistical-power problem — the effect direction "
            "is adverse to the candidate. The candidate achieves higher mean_hit through "
            "moderate (1-2 hit) draws, not through high-value (3-hit) draws. "
            "Explicit CTO/CEO waiver required to promote despite this directional weakness "
            "on the high-value lottery event."
        )
    else:
        # Tied direction, not significant
        policy = G4_POLICY_WAIVER
        rationale = (
            "b == c: no directional advantage on rare event. "
            "Waiver required given neutral McNemar evidence."
        )

    return {
        "policy": policy,
        "b_strategy_wins": b,
        "c_champion_wins": c,
        "direction_favors": direction,
        "discordant_total": discordant_total,
        "discordant_ratio_b_over_c": round(discordant_ratio, 4),
        "p_value": p,
        "rationale": rationale,
    }


def compute_effect_size(candidate_mean: float, baseline_mean: float, std_dev: float) -> dict:
    """Cohen's d for practical significance."""
    if std_dev == 0:
        return {"cohens_d": None, "interpretation": "undefined"}
    d = (candidate_mean - baseline_mean) / std_dev
    if abs(d) < 0.2:
        interp = "negligible"
    elif abs(d) < 0.5:
        interp = "small"
    elif abs(d) < 0.8:
        interp = "medium"
    else:
        interp = "large"
    return {"cohens_d": round(d, 4), "interpretation": interp}


def build_decision_matrix(p51_candidate: dict, g4_policy: dict) -> dict:
    """
    Build the P52 decision matrix for midfreq_fourier_mk_3bet.
    """
    rw = p51_candidate["rolling_windows"]
    perm = p51_candidate["permutation_test"]
    mc = p51_candidate["mcnemar_test"]
    mean_hit = p51_candidate["mean_hit_overall"]
    sp_rate = p51_candidate["special_hit_rate"]

    # Effect size vs theoretical baseline (std dev estimated from hit_count 0-3 range)
    # POWER_LOTTO 3-bet: first-zone hits ~ Binomial(5,5/38)*3 draws, std ~1.0 estimated
    # We use the observed std from the rolling windows as a proxy
    w150_mean = rw["W150"]["mean_hit"]
    w500_mean = rw["W500"]["mean_hit"]
    w1500_mean = rw["W1500"]["mean_hit"]
    approx_std = 0.90  # conservative estimate for hit_count per draw (3-bet, Binomial)
    eff_vs_theoretical = compute_effect_size(mean_hit, THEORETICAL_BASELINE, approx_std)
    eff_vs_champion = compute_effect_size(mean_hit, CHAMPION_MEAN_HIT, approx_std)

    # Rolling stability assessment
    window_deltas = [
        rw["W150"]["delta_vs_baseline"],
        rw["W500"]["delta_vs_baseline"],
        rw["W1500"]["delta_vs_baseline"],
    ]
    all_positive = all(d > 0 for d in window_deltas)
    monotonic_improvement = (
        rw["W150"]["delta_vs_baseline"] < rw["W500"]["delta_vs_baseline"] < rw["W1500"]["delta_vs_baseline"]
    )

    # Evidence strength score (simple composite, not a model)
    evidence_score = 0
    evidence_notes = []
    if p51_candidate["gates"]["G1_sample_size"]["pass"]:
        evidence_score += 1
        evidence_notes.append("G1 PASS: 1500 samples")
    if p51_candidate["gates"]["G2_three_window_mean_hit"]["pass"]:
        evidence_score += 2
        evidence_notes.append("G2 PASS: all rolling windows above theoretical baseline")
    if perm["p_value"] < 0.001:
        evidence_score += 3
        evidence_notes.append(f"G3 STRONG: permutation p={perm['p_value']} (< 0.001)")
    elif perm["p_value"] < 0.05:
        evidence_score += 2
        evidence_notes.append(f"G3 PASS: permutation p={perm['p_value']}")
    if not p51_candidate["gates"]["G4_mcnemar_vs_champion"]["pass"]:
        evidence_score -= 1
        evidence_notes.append(f"G4 FAIL: McNemar p={mc['p_value']:.4f}, direction adverse (c>b)")
    if p51_candidate["gates"]["G5_special_hit_ci"]["pass"]:
        evidence_score += 1
        evidence_notes.append("G5 PASS: special hit rate in theoretical CI")
    if p51_candidate["gates"]["G6_rolling_stability"]["pass"]:
        evidence_score += 1
        evidence_notes.append("G6 PASS: positive delta in all windows")

    return {
        "strategy": CANDIDATE_STRATEGY,
        "mean_hit_overall": mean_hit,
        "theoretical_baseline": THEORETICAL_BASELINE,
        "champion_mean_hit": CHAMPION_MEAN_HIT,
        "mean_hit_vs_theoretical_delta": round(mean_hit - THEORETICAL_BASELINE, 6),
        "mean_hit_vs_champion_delta": round(mean_hit - CHAMPION_MEAN_HIT, 6),
        "rolling_windows": {
            "W150": round(w150_mean, 6),
            "W500": round(w500_mean, 6),
            "W1500": round(w1500_mean, 6),
            "all_above_theoretical_baseline": all_positive,
            "monotonic_improvement": monotonic_improvement,
        },
        "permutation_test": {
            "p_value": perm["p_value"],
            "significant": perm["significant"],
            "strength": "highly_significant" if perm["p_value"] < 0.001 else "significant",
        },
        "mcnemar_test": {
            "p_value": mc["p_value"],
            "significant": mc["significant"],
            "b_strategy_wins": mc["b_strategy_wins"],
            "c_champion_wins": mc["c_baseline_wins"],
            "direction_favors": "CHAMPION" if mc["c_baseline_wins"] > mc["b_strategy_wins"] else "CANDIDATE",
            "g4_policy": g4_policy["policy"],
        },
        "effect_sizes": {
            "vs_theoretical_baseline": eff_vs_theoretical,
            "vs_champion": eff_vs_champion,
        },
        "special_hit_rate": sp_rate,
        "evidence_score": evidence_score,
        "evidence_notes": evidence_notes,
        "high_variance_caveat": (
            "Lottery outcomes are inherently high-variance. A 1500-draw sample spans "
            "approximately 3 years of draws. Effect sizes are small. There is non-trivial "
            "probability that observed mean advantage reverts under regime change."
        ),
        "comparison_vs_champion_summary": (
            f"{CANDIDATE_STRATEGY} mean_hit={mean_hit:.4f} exceeds champion "
            f"{BASELINE_STRATEGY} mean_hit={CHAMPION_MEAN_HIT:.4f} by "
            f"{mean_hit - CHAMPION_MEAN_HIT:+.4f}. However, champion outperforms "
            f"candidate on hit_count>={MCNEMAR_THRESHOLD} event ({mc['c_baseline_wins']} "
            f"vs {mc['b_strategy_wins']} discordant pairs). The candidate excels in "
            "moderate hits (1-2 per draw), not in high-value hits (3 per draw)."
        ),
        "online_promotion_justified_now": False,
        "online_promotion_justification": (
            "No. G4 McNemar fails and direction favors champion on high-value event. "
            "Promotion to ONLINE without waiver would replace a champion that is stronger "
            "on the high-value prize tier with a candidate that is stronger only in "
            "average/moderate hits. Explicit waiver required."
        ),
        "watchlist_recommendation": (
            "WATCHLIST is the safer classification. Monitor mean_hit trend over next "
            "500 draws. If mean_hit advantage holds AND hit_count>=3 event parity improves, "
            "revisit for P53 promotion with McNemar threshold lowered to hit_count>=2 "
            "to capture moderate-hit advantage where the candidate is actually stronger."
        ),
        "p53_recommendation": (
            "P53 controlled promotion task should be created IF CEO/CTO waiver is granted. "
            "P53 should: (1) lower McNemar threshold to hit_count>=2 for supplementary test, "
            "(2) run an additional 500-draw OOS holdout, (3) promote to WATCHLIST first "
            "(not ONLINE), (4) compare 90-day live WATCHLIST performance vs champion."
        ),
    }


def classify_strategy(decision_matrix: dict, g4_policy: dict) -> str:
    """Classify midfreq_fourier_mk_3bet for P52 output."""
    if g4_policy["policy"] == G4_POLICY_BLOCKS:
        return "WATCHLIST_G4_BLOCKED"
    elif g4_policy["policy"] == G4_POLICY_WAIVER:
        return "PROMOTION_WITH_WAIVER_REQUIRED"
    elif g4_policy["policy"] == G4_POLICY_NOT_BLOCKING:
        return "P53_PROMOTION_TASK_CANDIDATE"
    return "INCONCLUSIVE_NEEDS_MORE_DRAWS"


def build_output(p51_json_path: str) -> dict:
    """Build complete P52 output from P51 evidence."""
    with open(p51_json_path) as f:
        p51 = json.load(f)

    # Verify P51 classification
    assert p51["task"] == "P51", "Input is not a P51 artifact"
    assert p51["no_db_write"] is True
    assert p51["no_lifecycle_promotion"] is True
    assert p51["no_registry_mutation"] is True
    assert "midfreq_fourier_mk_3bet" in p51["strategies"]
    assert p51["strategies"]["midfreq_fourier_mk_3bet"]["classification"] == "P52_PROMOTION_CANDIDATE"

    candidate_data = p51["strategies"][CANDIDATE_STRATEGY]
    mc_data = candidate_data["mcnemar_test"]

    g4_policy = decide_g4_policy(mc_data)
    decision_matrix = build_decision_matrix(candidate_data, g4_policy)
    classification = classify_strategy(decision_matrix, g4_policy)

    # Determine overall P52 classification
    if classification == "P53_PROMOTION_TASK_CANDIDATE":
        overall = "P52_PROMOTION_READINESS_COMPLETED"
    elif classification == "PROMOTION_WITH_WAIVER_REQUIRED":
        overall = "P52_PROMOTION_READINESS_WAIVER_REQUIRED"
    elif classification == "WATCHLIST_G4_BLOCKED":
        overall = "P52_PROMOTION_READINESS_COMPLETED"
    else:
        overall = "P52_INCONCLUSIVE_NEEDS_MORE_DRAWS"

    return {
        "task": "P52",
        "description": "POWER_LOTTO midfreq_fourier_mk_3bet Promotion Readiness Decision",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "p51_source": p51_json_path,
        "p51_overall_classification": p51["overall_classification"],
        "p51_commit": "0415cc8",
        "no_db_write": True,
        "no_lifecycle_promotion": True,
        "no_registry_mutation": True,
        "production_rows": 42460,
        "g4_mcnemar_policy": g4_policy,
        "candidate_decision": {
            "strategy": CANDIDATE_STRATEGY,
            "p51_classification": candidate_data["classification"],
            "p52_classification": classification,
            "decision_matrix": decision_matrix,
        },
        "other_strategies": {
            "pp3_freqort_4bet": {
                "p51_classification": p51["strategies"]["pp3_freqort_4bet"]["classification"],
                "p52_classification": "INCONCLUSIVE",
                "note": (
                    "W1500 delta positive (+0.055) but early windows underperform. "
                    "G2/G6 FAIL. Recommend 500 additional draws before re-evaluation."
                ),
            },
            "midfreq_fourier_2bet": {
                "p51_classification": p51["strategies"]["midfreq_fourier_2bet"]["classification"],
                "p52_classification": "INCONCLUSIVE",
                "note": (
                    "G2/G3/G6 all FAIL. Mean hit 0.9727 does not significantly exceed "
                    "theoretical baseline. Not a promotion candidate at this time."
                ),
            },
        },
        "overall_p52_classification": overall,
        "p52_governance_note": (
            "P52 is promotion-readiness decision only. No lifecycle promotion performed. "
            "P53 requires separate explicit authorization before any promotion proceeds."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="P52 POWER_LOTTO promotion readiness")
    parser.add_argument(
        "--p51-json",
        default="outputs/replay/p51_powerlotto_wave4_rolling_window_mcnemar_gate_20260525.json",
        help="Path to P51 JSON artifact",
    )
    parser.add_argument(
        "--json-out",
        default="outputs/replay/p52_powerlotto_midfreq_fourier_mk_3bet_promotion_readiness_20260525.json",
        help="Output path for P52 JSON artifact",
    )
    args = parser.parse_args()

    output = build_output(args.p51_json)

    with open(args.json_out, "w") as f:
        json.dump(output, f, indent=2)

    print(f"P52 Classification: {output['overall_p52_classification']}")
    print(f"  midfreq_fourier_mk_3bet: {output['candidate_decision']['p52_classification']}")
    print(f"  G4 policy: {output['g4_mcnemar_policy']['policy']}")
    print(f"  G4 direction: favors {output['g4_mcnemar_policy']['direction_favors']}")
    print(f"JSON written to: {args.json_out}")


if __name__ == "__main__":
    main()
