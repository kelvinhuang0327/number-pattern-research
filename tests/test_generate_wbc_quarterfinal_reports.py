from scripts.generate_wbc_quarterfinal_reports import (
    starter_quality_score,
    starter_run_suppression_factor,
    starter_summary_text,
)


def test_starter_quality_score_rewards_better_profile():
    ace = {"name": "Ace", "era": 2.50, "whip": 1.02, "k_per_9": 10.2, "bb_per_9": 2.0}
    shaky = {"name": "Shaky", "era": 4.80, "whip": 1.35, "k_per_9": 7.1, "bb_per_9": 3.4}

    assert starter_quality_score(ace) > starter_quality_score(shaky)
    assert starter_run_suppression_factor(ace) < 1.0
    assert starter_run_suppression_factor(shaky) > 1.0


def test_starter_summary_text_handles_missing_and_known():
    assert starter_summary_text(None) == "官方 feed 尚未列出"
    text = starter_summary_text(
        {"name": "Logan Webb", "era": 3.22, "whip": 1.24, "k_per_9": 9.74, "bb_per_9": 2.0}
    )
    assert "Logan Webb" in text
    assert "ERA 3.22" in text
