from __future__ import annotations

import ast
from copy import deepcopy
import inspect
import json
from pathlib import Path

import pytest

from data.mlb_pitcher_game_events import (
    CONTRACT_VERSION,
    EVENT_FIELDS,
    PARSER_VERSION,
    PitcherEventStoreError,
    PitcherGameEventError,
    PitcherGameEventStore,
    adapt_finalized_boxscore_payload as _adapt_finalized_boxscore_payload,
    innings_display_to_outs,
    normalize_pitcher_game_event,
    outs_to_innings_display,
    select_prior_pitcher_events,
)


FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "mlb_pitcher_game_event_fixtures.json"
)


@pytest.fixture(scope="module")
def corpus():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture()
def valid_payload(corpus):
    return deepcopy(corpus["payloads"]["multi_pitcher_final"])


def adapt_finalized_boxscore_payload(
    payload,
    *,
    collected_at_utc=None,
    parser_version=PARSER_VERSION,
):
    return _adapt_finalized_boxscore_payload(
        payload,
        collected_at_utc=collected_at_utc or payload.get("collectedAtUtc"),
        source_provider="statsapi_decoded_final_boxscore",
        source_endpoint_or_feed_id="caller_supplied_boxscore",
        parser_version=parser_version,
    )


@pytest.fixture()
def valid_events(valid_payload):
    result = adapt_finalized_boxscore_payload(valid_payload)
    assert result.rejected_records == 0
    return result.events


def event_raw(event, **overrides):
    raw = event.to_dict()
    raw.pop("payload_fingerprint")
    raw.update(overrides)
    return raw


def revised_event(event, **overrides):
    return normalize_pitcher_game_event(event_raw(event, **overrides))


def reordered_home_payload(payload, *, corrected):
    """Copy ``payload`` with the home pitcher list reordered so that pitcher
    880101 moves from list position 1 to position 2. When ``corrected`` is set,
    mark the game corrected and bump 880101's strikeouts."""
    reordered = deepcopy(payload)
    game = reordered["games"][0]
    game["teams"]["home"]["pitchers"] = [880102, 880101, 880103]
    if corrected:
        game["recordStatus"] = "corrected"
        game["teams"]["home"]["players"]["ID880101"]["stats"]["pitching"][
            "strikeOuts"
        ] = 9
    return reordered


def test_fixture_declares_synthetic_data_and_required_scenarios(corpus):
    assert "synthetic" in corpus["fixture_notice"].lower()
    assert len(corpus["scenario_catalog"]) >= 26
    assert {
        "valid_starter",
        "valid_reliever",
        "valid_opener",
        "zero_out_appearance",
        "estimated_proxy_rejected",
        "ambiguous_same_time_correction",
        "stake_independence",
    } <= set(corpus["scenario_catalog"])


@pytest.mark.parametrize(
    ("display", "outs"),
    [
        ("0.0", 0),
        ("0.1", 1),
        ("0.2", 2),
        ("1.0", 3),
        ("6.2", 20),
        ("9.0", 27),
        ("12.1", 37),
    ],
)
def test_baseball_innings_notation_round_trips(display, outs):
    assert innings_display_to_outs(display) == outs
    assert outs_to_innings_display(outs) == display


@pytest.mark.parametrize(
    "display",
    [
        "0.3",
        "1.4",
        "2",
        "2.00",
        "2.5",
        "-1.0",
        "1.1+",
        1.1,
        None,
        "",
    ],
)
def test_invalid_baseball_innings_notation_is_rejected(display):
    with pytest.raises(PitcherGameEventError):
        innings_display_to_outs(display)


def test_adapter_emits_complete_per_pitcher_records(valid_payload):
    result = adapt_finalized_boxscore_payload(valid_payload)
    assert result.accepted_records == 5
    assert result.rejected_records == 0
    assert not result.diagnostics
    assert all(set(event.to_dict()) == set(EVENT_FIELDS) for event in result.events)


def test_adapter_requires_explicit_provenance_arguments():
    signature = inspect.signature(_adapt_finalized_boxscore_payload)
    for field in (
        "collected_at_utc",
        "source_provider",
        "source_endpoint_or_feed_id",
        "parser_version",
    ):
        assert signature.parameters[field].default is inspect.Parameter.empty


def test_explicit_collection_time_is_authoritative(valid_payload):
    result = adapt_finalized_boxscore_payload(
        valid_payload,
        collected_at_utc="2099-06-02T05:00:00Z",
    )
    assert {event.collected_at_utc for event in result.events} == {
        "2099-06-02T05:00:00Z"
    }


def test_unsupported_explicit_parser_version_is_rejected(valid_payload):
    result = adapt_finalized_boxscore_payload(
        valid_payload,
        parser_version="unreviewed-parser",
    )
    assert not result.events
    assert result.rejected_records == 5


def test_adapter_preserves_starter_reliever_and_opener_identity(valid_events):
    by_id = {event.pitcher_id: event for event in valid_events}
    assert by_id[880101].starter_flag is True
    assert by_id[880102].starter_flag is False
    assert by_id[880201].starter_flag is True
    assert by_id[880201].innings_outs == 3


def test_adapter_accepts_zero_out_appearance(valid_events):
    zero_out = next(event for event in valid_events if event.pitcher_id == 880103)
    assert zero_out.innings_outs == 0
    assert zero_out.innings_pitched_display == "0.0"
    assert zero_out.batters_faced == 2


def test_adapter_assigns_deterministic_side_local_sequence(valid_events):
    home = [event for event in valid_events if event.home_away == "home"]
    away = [event for event in valid_events if event.home_away == "away"]
    assert [event.appearance_sequence for event in home] == [1, 2, 3]
    assert [event.appearance_sequence for event in away] == [1, 2]


def test_adapter_maps_team_and_opponent_ids(valid_events):
    home = next(event for event in valid_events if event.home_away == "home")
    away = next(event for event in valid_events if event.home_away == "away")
    assert (home.team_id, home.opponent_team_id) == (99101, 99102)
    assert (away.team_id, away.opponent_team_id) == (99102, 99101)


def test_normalized_event_is_diagnostic_only(valid_events):
    event = valid_events[0]
    assert event.contract_version == CONTRACT_VERSION
    assert event.parser_version == PARSER_VERSION
    assert event.diagnostic_only is True
    assert event.production_ready is False
    assert "learning_eligible" not in event.to_dict()


def test_payload_fingerprint_is_deterministic(valid_events):
    raw = event_raw(valid_events[0])
    first = normalize_pitcher_game_event(raw)
    second = normalize_pitcher_game_event(deepcopy(raw))
    assert first.payload_fingerprint == second.payload_fingerprint
    assert len(first.payload_fingerprint) == 64


def test_tampered_payload_fingerprint_is_rejected(valid_events):
    raw = valid_events[0].to_dict()
    raw["payload_fingerprint"] = "0" * 64
    with pytest.raises(PitcherGameEventError, match="fingerprint"):
        normalize_pitcher_game_event(raw)


def test_unknown_normalized_event_field_is_rejected(valid_events):
    raw = event_raw(valid_events[0])
    raw["unreviewed_metadata"] = "not part of the contract"
    with pytest.raises(PitcherGameEventError, match="unknown event fields"):
        normalize_pitcher_game_event(raw)


@pytest.mark.parametrize(
    "field",
    ["strikeOuts", "baseOnBalls", "hitBatsmen", "homeRuns"],
)
def test_missing_required_fip_component_is_rejected(valid_payload, field):
    del valid_payload["games"][0]["teams"]["home"]["players"]["ID880101"]["stats"][
        "pitching"
    ][field]
    result = adapt_finalized_boxscore_payload(valid_payload)
    assert result.accepted_records == 4
    assert result.rejected_records == 1
    assert result.diagnostics[0].code == "malformed_pitcher_event"


@pytest.mark.parametrize(
    "field",
    [
        "battersFaced",
        "strikeOuts",
        "baseOnBalls",
        "intentionalWalks",
        "hitBatsmen",
        "homeRuns",
        "hits",
        "earnedRuns",
        "runs",
        "numberOfPitches",
        "strikes",
    ],
)
def test_negative_pitching_stat_is_rejected(valid_payload, field):
    valid_payload["games"][0]["teams"]["home"]["players"]["ID880101"]["stats"][
        "pitching"
    ][field] = -1
    result = adapt_finalized_boxscore_payload(valid_payload)
    assert result.accepted_records == 4
    assert result.rejected_records == 1


def test_earned_runs_cannot_exceed_runs(valid_payload):
    pitching = valid_payload["games"][0]["teams"]["home"]["players"]["ID880101"][
        "stats"
    ]["pitching"]
    pitching["earnedRuns"] = 3
    pitching["runs"] = 2
    result = adapt_finalized_boxscore_payload(valid_payload)
    assert result.rejected_records == 1
    assert "earned_runs" in result.diagnostics[0].message


def test_strikes_cannot_exceed_pitches(valid_payload):
    pitching = valid_payload["games"][0]["teams"]["home"]["players"]["ID880101"][
        "stats"
    ]["pitching"]
    pitching["numberOfPitches"] = 10
    pitching["strikes"] = 11
    result = adapt_finalized_boxscore_payload(valid_payload)
    assert result.rejected_records == 1
    assert "strikes" in result.diagnostics[0].message


def test_malformed_innings_suffix_is_rejected(valid_payload):
    valid_payload["games"][0]["teams"]["home"]["players"]["ID880101"]["stats"][
        "pitching"
    ]["inningsPitched"] = "6.3"
    result = adapt_finalized_boxscore_payload(valid_payload)
    assert result.accepted_records == 4
    assert result.diagnostics[0].code == "invalid_innings_notation"


def test_missing_explicit_starter_flag_is_rejected(valid_payload):
    del valid_payload["games"][0]["teams"]["home"]["players"]["ID880101"][
        "starterFlag"
    ]
    result = adapt_finalized_boxscore_payload(valid_payload)
    assert result.accepted_records == 4
    assert "starter_flag" in result.diagnostics[0].message


def test_missing_game_pk_is_rejected_without_inference(valid_payload):
    del valid_payload["games"][0]["gamePk"]
    result = adapt_finalized_boxscore_payload(valid_payload)
    assert not result.events
    assert result.rejected_records == 5


def test_missing_pitcher_id_is_rejected_without_name_inference(valid_payload):
    del valid_payload["games"][0]["teams"]["home"]["players"]["ID880101"]["person"][
        "id"
    ]
    result = adapt_finalized_boxscore_payload(valid_payload)
    assert result.accepted_records == 4
    assert result.rejected_records == 1


@pytest.mark.parametrize("side", ["home", "away"])
def test_missing_team_identity_rejects_that_side(valid_payload, side):
    del valid_payload["games"][0]["teams"][side]["team"]["id"]
    result = adapt_finalized_boxscore_payload(valid_payload)
    assert result.rejected_records == 5
    assert not result.events


def test_innings_display_and_outs_must_agree(valid_events):
    with pytest.raises(PitcherGameEventError, match="disagree"):
        normalize_pitcher_game_event(
            event_raw(valid_events[0], innings_outs=19)
        )


def test_team_aggregate_without_pitcher_games_is_rejected(corpus):
    result = adapt_finalized_boxscore_payload(
        corpus["payloads"]["team_aggregate_only"]
    )
    assert not result.events
    assert result.diagnostics[0].code == "team_aggregate_without_pitcher_games"


def test_empty_finalized_side_is_diagnosed(valid_payload):
    valid_payload["games"][0]["teams"]["home"]["pitchers"] = []
    valid_payload["games"][0]["teams"]["home"]["players"] = {}
    result = adapt_finalized_boxscore_payload(valid_payload)
    assert result.accepted_records == 2
    assert result.rejected_records == 1
    assert result.diagnostics[0].code == "empty_pitcher_list"


def test_source_unavailable_is_diagnostic_not_event(corpus):
    result = adapt_finalized_boxscore_payload(corpus["payloads"]["source_unavailable"])
    assert not result.events
    assert result.diagnostics[0].code == "source_unavailable"


@pytest.mark.parametrize("payload_name", ["live_game", "cancelled_game"])
def test_non_final_game_is_rejected(corpus, payload_name):
    result = adapt_finalized_boxscore_payload(corpus["payloads"][payload_name])
    assert not result.events
    assert result.diagnostics[0].code == "game_not_final"


def test_suspended_then_finalized_game_is_accepted(corpus):
    result = adapt_finalized_boxscore_payload(
        corpus["payloads"]["suspended_then_finalized"]
    )
    assert result.accepted_records == 1
    assert result.events[0].game_pk == 9903001


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("estimated", True),
        ("proxy", True),
        ("averaged", 1),
        ("allocationMethod", "schedule_proxy_fallback"),
    ],
)
def test_estimated_or_proxy_payload_is_rejected(valid_payload, key, value):
    valid_payload[key] = value
    result = adapt_finalized_boxscore_payload(valid_payload)
    assert not result.events
    assert result.diagnostics[0].code == "proxy_or_leakage_rejected"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("odds", -110),
        ("winner", "home"),
        ("homeScore", 4),
        ("settlement", "won"),
        ("learningEligible", True),
        ("modelProbability", 0.61),
    ],
)
def test_outcome_or_decision_field_is_rejected(valid_payload, key, value):
    valid_payload["games"][0][key] = value
    result = adapt_finalized_boxscore_payload(valid_payload)
    assert not result.events
    assert result.diagnostics[0].code == "proxy_or_leakage_rejected"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("collected_at_utc", "2099-06-02T04:30:00"),
        ("game_start_utc", "2099-06-01T19:30:00-04:00"),
        ("game_finalized_at_utc", "2099-06-02T03:55:00+01:00"),
    ],
)
def test_timestamps_must_be_explicit_utc(valid_events, field, value):
    with pytest.raises(PitcherGameEventError, match="UTC"):
        normalize_pitcher_game_event(event_raw(valid_events[0], **{field: value}))


def test_finalization_cannot_precede_game_start(valid_events):
    with pytest.raises(PitcherGameEventError, match="precede game_start"):
        normalize_pitcher_game_event(
            event_raw(
                valid_events[0],
                game_finalized_at_utc="2099-06-01T22:00:00Z",
            )
        )


def test_collection_cannot_precede_finalization(valid_events):
    with pytest.raises(PitcherGameEventError, match="collected_at_utc"):
        normalize_pitcher_game_event(
            event_raw(valid_events[0], collected_at_utc="2099-06-02T03:00:00Z")
        )


def test_official_date_must_match_game_start_window(valid_events):
    with pytest.raises(PitcherGameEventError, match="compatible"):
        normalize_pitcher_game_event(
            event_raw(valid_events[0], official_game_date="2099-05-20")
        )


def test_overnight_official_date_is_allowed(valid_events):
    event = normalize_pitcher_game_event(
        event_raw(
            valid_events[0],
            game_start_utc="2099-06-02T00:30:00Z",
            official_game_date="2099-06-01",
        )
    )
    assert event.official_game_date == "2099-06-01"


def test_optional_pitch_counts_must_be_both_present_or_both_null(valid_events):
    event = normalize_pitcher_game_event(
        event_raw(valid_events[0], pitches_thrown=None, strikes=None)
    )
    assert event.pitches_thrown is None
    with pytest.raises(PitcherGameEventError, match="require"):
        normalize_pitcher_game_event(
            event_raw(valid_events[0], pitches_thrown=None, strikes=10)
        )


def test_diagnostic_and_production_flags_are_fixed(valid_events):
    with pytest.raises(PitcherGameEventError, match="diagnostic_only"):
        normalize_pitcher_game_event(
            event_raw(valid_events[0], diagnostic_only=False)
        )
    with pytest.raises(PitcherGameEventError, match="production_ready"):
        normalize_pitcher_game_event(
            event_raw(valid_events[0], production_ready=True)
        )


def test_jsonl_store_appends_loads_and_suppresses_exact_duplicates(
    tmp_path, valid_events
):
    store = PitcherGameEventStore(tmp_path / "pitcher_events.jsonl")
    first = store.append(valid_events[:2])
    second = store.append((valid_events[0], valid_events[2]))
    assert (first.appended, first.duplicates_skipped) == (2, 0)
    assert (second.appended, second.duplicates_skipped) == (1, 1)
    assert store.load() == (valid_events[0], valid_events[1], valid_events[2])


def test_jsonl_store_deduplicates_within_one_append(tmp_path, valid_events):
    store = PitcherGameEventStore(tmp_path / "pitcher_events.jsonl")
    result = store.append((valid_events[0], valid_events[0]))
    assert result.appended == 1
    assert result.duplicates_skipped == 1


def test_jsonl_store_appends_correction_and_preserves_prior_row(
    tmp_path, valid_events
):
    store = PitcherGameEventStore(tmp_path / "pitcher_events.jsonl")
    correction = revised_event(
        valid_events[0],
        record_status="corrected",
        collected_at_utc="2099-06-03T12:00:00Z",
        strikeouts=9,
    )
    assert store.append((valid_events[0],)).appended == 1
    assert store.append((correction,)).appended == 1
    loaded = store.load()
    assert [event.record_status for event in loaded] == ["final", "corrected"]
    assert [event.strikeouts for event in loaded] == [8, 9]


def test_jsonl_store_rejects_corrupt_line(tmp_path):
    path = tmp_path / "pitcher_events.jsonl"
    path.write_text("{not-json}\n", encoding="utf-8")
    with pytest.raises(PitcherEventStoreError, match="line 1"):
        PitcherGameEventStore(path).load()


def test_jsonl_store_rejects_unknown_contract_field(tmp_path, valid_events):
    raw = valid_events[0].to_dict()
    raw["stake"] = 100
    path = tmp_path / "pitcher_events.jsonl"
    path.write_text(json.dumps(raw) + "\n", encoding="utf-8")
    with pytest.raises(PitcherEventStoreError, match="fields"):
        PitcherGameEventStore(path).load()


def test_jsonl_store_requires_existing_parent(tmp_path, valid_events):
    store = PitcherGameEventStore(tmp_path / "missing" / "pitcher_events.jsonl")
    with pytest.raises(PitcherEventStoreError, match="parent directory"):
        store.append((valid_events[0],))


def test_later_correction_replaces_earlier_record(corpus, valid_events):
    corrected = adapt_finalized_boxscore_payload(
        corpus["payloads"]["corrected_final"]
    ).events[0]
    result = select_prior_pitcher_events(
        (valid_events[0], corrected),
        pitcher_id=880101,
        target_information_cutoff_utc="2099-06-04T00:00:00Z",
    )
    assert result.status == "ok"
    assert len(result.events) == 1
    assert result.events[0].record_status == "corrected"
    assert result.events[0].strikeouts == 9


def test_correction_after_cutoff_does_not_replace_known_record(corpus, valid_events):
    corrected = adapt_finalized_boxscore_payload(
        corpus["payloads"]["corrected_final"]
    ).events[0]
    result = select_prior_pitcher_events(
        (valid_events[0], corrected),
        pitcher_id=880101,
        target_information_cutoff_utc="2099-06-03T00:00:00Z",
    )
    assert result.events == (valid_events[0],)


def test_ambiguous_latest_corrections_fail_closed(valid_events):
    first = revised_event(
        valid_events[0],
        record_status="corrected",
        collected_at_utc="2099-06-03T12:00:00Z",
        strikeouts=9,
    )
    second = revised_event(
        valid_events[0],
        record_status="corrected",
        collected_at_utc="2099-06-03T12:00:00Z",
        strikeouts=10,
    )
    result = select_prior_pitcher_events(
        (valid_events[0], first, second),
        pitcher_id=880101,
        target_information_cutoff_utc="2099-06-04T00:00:00Z",
    )
    assert result.status == "ambiguous_revision"
    assert not result.events


def test_exact_duplicate_revision_is_not_ambiguous(valid_events):
    result = select_prior_pitcher_events(
        (valid_events[0], valid_events[0]),
        pitcher_id=880101,
        target_information_cutoff_utc="2099-06-04T00:00:00Z",
    )
    assert result.status == "ok"
    assert result.events == (valid_events[0],)


def test_latest_superseded_marker_excludes_appearance(valid_events):
    superseded = revised_event(
        valid_events[0],
        record_status="superseded",
        collected_at_utc="2099-06-03T12:00:00Z",
    )
    result = select_prior_pitcher_events(
        (valid_events[0], superseded),
        pitcher_id=880101,
        target_information_cutoff_utc="2099-06-04T00:00:00Z",
    )
    assert result.status == "no_records"
    assert not result.events


def test_future_game_is_excluded(valid_events):
    future = revised_event(
        valid_events[0],
        source_record_id="future",
        game_pk=9909999,
        game_start_utc="2099-06-10T18:00:00Z",
        game_finalized_at_utc="2099-06-10T21:00:00Z",
        collected_at_utc="2099-06-10T21:30:00Z",
        official_game_date="2099-06-10",
    )
    result = select_prior_pitcher_events(
        (valid_events[0], future),
        pitcher_id=880101,
        target_information_cutoff_utc="2099-06-05T00:00:00Z",
    )
    assert result.events == (valid_events[0],)


def test_target_game_is_explicitly_excluded(valid_events):
    result = select_prior_pitcher_events(
        valid_events,
        pitcher_id=880101,
        target_information_cutoff_utc="2099-06-04T00:00:00Z",
        target_game_pk=9901001,
    )
    assert result.status == "no_records"


def test_late_collection_is_excluded(valid_events):
    late = revised_event(
        valid_events[0],
        collected_at_utc="2099-06-05T12:00:00Z",
    )
    result = select_prior_pitcher_events(
        (late,),
        pitcher_id=880101,
        target_information_cutoff_utc="2099-06-04T00:00:00Z",
    )
    assert result.status == "no_records"


def test_doubleheader_games_remain_distinct(corpus):
    events = adapt_finalized_boxscore_payload(
        corpus["payloads"]["doubleheader_final"]
    ).events
    result = select_prior_pitcher_events(
        events,
        pitcher_id=881001,
        target_information_cutoff_utc="2099-07-11T00:00:00Z",
    )
    assert [event.game_pk for event in result.events] == [9902001, 9902002]
    assert result.max_included_game_start_utc == "2099-07-10T20:30:00Z"


def test_reordered_corrected_payload_resolves_to_single_revision(
    valid_payload, valid_events, tmp_path
):
    """A corrected payload that reorders the pitcher list must resolve to one
    logical pitcher-game revision, not a second appearance."""
    original = next(event for event in valid_events if event.pitcher_id == 880101)
    assert original.appearance_sequence == 1
    corrected = next(
        event
        for event in adapt_finalized_boxscore_payload(
            reordered_home_payload(valid_payload, corrected=True),
            collected_at_utc="2099-06-03T12:00:00Z",
        ).events
        if event.pitcher_id == 880101
    )
    # observed source order changed, but logical identity did not
    assert corrected.appearance_sequence == 2
    assert corrected.record_status == "corrected"
    assert corrected.strikeouts == 9

    # append-only storage keeps both observations
    store = PitcherGameEventStore(tmp_path / "events.jsonl")
    assert store.append((original,)).appended == 1
    assert store.append((corrected,)).appended == 1
    assert len(store.load()) == 2

    # but as-of selection resolves to exactly one corrected revision
    result = select_prior_pitcher_events(
        store.load(),
        pitcher_id=880101,
        target_information_cutoff_utc="2099-06-04T00:00:00Z",
    )
    assert result.status == "ok"
    assert len(result.events) == 1
    assert result.events[0].record_status == "corrected"
    assert result.events[0].strikeouts == 9
    assert result.events[0].appearance_sequence == 2


def test_source_record_id_is_stable_across_pitcher_list_reorder(
    valid_payload, valid_events
):
    original = next(event for event in valid_events if event.pitcher_id == 880101)
    corrected = next(
        event
        for event in adapt_finalized_boxscore_payload(
            reordered_home_payload(valid_payload, corrected=True),
            collected_at_utc="2099-06-03T12:00:00Z",
        ).events
        if event.pitcher_id == 880101
    )
    assert original.appearance_sequence != corrected.appearance_sequence
    assert original.source_record_id == corrected.source_record_id
    assert original.source_record_id == "9901001:pitcher:880101"
    assert (
        original.logical_event_key == corrected.logical_event_key == (9901001, 880101)
    )


def test_reordered_correction_after_cutoff_keeps_known_record(
    valid_payload, valid_events
):
    original = next(event for event in valid_events if event.pitcher_id == 880101)
    corrected = next(
        event
        for event in adapt_finalized_boxscore_payload(
            reordered_home_payload(valid_payload, corrected=True),
            collected_at_utc="2099-06-03T12:00:00Z",
        ).events
        if event.pitcher_id == 880101
    )
    result = select_prior_pitcher_events(
        (original, corrected),
        pitcher_id=880101,
        target_information_cutoff_utc="2099-06-03T00:00:00Z",
    )
    assert len(result.events) == 1
    assert result.events[0].record_status == "final"
    assert result.events[0].strikeouts == original.strikeouts


def test_reorder_only_later_observation_selects_single_row(
    valid_payload, valid_events
):
    """Statistics unchanged; only list order and collection time change."""
    original = next(event for event in valid_events if event.pitcher_id == 880101)
    reobserved = next(
        event
        for event in adapt_finalized_boxscore_payload(
            reordered_home_payload(valid_payload, corrected=False),
            collected_at_utc="2099-06-03T12:00:00Z",
        ).events
        if event.pitcher_id == 880101
    )
    assert reobserved.appearance_sequence == 2
    assert reobserved.strikeouts == original.strikeouts
    assert reobserved.source_record_id == original.source_record_id
    result = select_prior_pitcher_events(
        (original, reobserved),
        pitcher_id=880101,
        target_information_cutoff_utc="2099-06-04T00:00:00Z",
    )
    assert result.status == "ok"
    assert len(result.events) == 1
    assert result.events[0].appearance_sequence == 2


def test_direct_repeated_appearance_for_one_pitcher_game_fails_closed(valid_events):
    """Contract v1 stores one row per (game_pk, pitcher_id). Two simultaneous
    logical rows for the same pitcher-game are ambiguous and fail closed; the
    selector must not return both."""
    first = valid_events[0]
    second = revised_event(
        first,
        source_record_id=f"{first.game_pk}:pitcher:{first.pitcher_id}",
        appearance_sequence=2,
        starter_flag=False,
        innings_outs=1,
        innings_pitched_display="0.1",
        batters_faced=1,
        strikeouts=1,
        walks=0,
        intentional_walks=0,
        hit_by_pitch=0,
        home_runs_allowed=0,
        hits_allowed=0,
        earned_runs=0,
        runs_allowed=0,
        pitches_thrown=4,
        strikes=3,
    )
    result = select_prior_pitcher_events(
        (first, second),
        pitcher_id=880101,
        target_information_cutoff_utc="2099-06-04T00:00:00Z",
    )
    assert result.status == "ambiguous_revision"
    assert not result.events


def test_adapter_rejects_same_pitcher_on_both_sides(valid_payload):
    valid_payload["games"][0]["teams"]["away"]["pitchers"].append(880101)
    result = adapt_finalized_boxscore_payload(valid_payload)
    assert not result.events
    assert any(
        diagnostic.code == "ambiguous_pitcher_both_sides"
        for diagnostic in result.diagnostics
    )


def test_post_hoc_2024_game_collected_in_2026_excluded_before_2025_cutoff(valid_events):
    """A finalized 2024 game collected only in 2026 cannot be treated as known
    at a 2025 cutoff merely because it finalized in 2024."""
    historical = revised_event(
        valid_events[0],
        source_record_id="2401001:pitcher:880101",
        game_pk=2401001,
        game_start_utc="2024-05-01T18:00:00Z",
        game_finalized_at_utc="2024-05-01T21:00:00Z",
        collected_at_utc="2026-06-01T00:00:00Z",
        official_game_date="2024-05-01",
    )
    result = select_prior_pitcher_events(
        (historical,),
        pitcher_id=880101,
        target_information_cutoff_utc="2025-06-01T00:00:00Z",
    )
    assert result.status == "no_records"
    assert not result.events


def test_post_hoc_event_eligible_after_actual_collection_time(valid_events):
    historical = revised_event(
        valid_events[0],
        source_record_id="2401001:pitcher:880101",
        game_pk=2401001,
        game_start_utc="2024-05-01T18:00:00Z",
        game_finalized_at_utc="2024-05-01T21:00:00Z",
        collected_at_utc="2026-06-01T00:00:00Z",
        official_game_date="2024-05-01",
    )
    result = select_prior_pitcher_events(
        (historical,),
        pitcher_id=880101,
        target_information_cutoff_utc="2026-07-01T00:00:00Z",
    )
    assert result.status == "ok"
    assert len(result.events) == 1
    assert result.events[0].game_pk == 2401001


def test_cross_provider_later_row_does_not_silently_overwrite(valid_events):
    """A later row from a different provider for the same (game_pk, pitcher_id)
    must not silently replace the earlier provider's row. Selection fails closed
    with a cross-source-lineage diagnostic and returns nothing -- no
    latest-provider-wins."""
    other_provider = revised_event(
        valid_events[0],
        source_provider="rival_provider",
        collected_at_utc="2099-06-03T12:00:00Z",
        strikeouts=3,
    )
    assert other_provider.source_record_id == valid_events[0].source_record_id
    assert other_provider.logical_event_key == valid_events[0].logical_event_key
    result = select_prior_pitcher_events(
        (valid_events[0], other_provider),
        pitcher_id=880101,
        target_information_cutoff_utc="2099-06-04T00:00:00Z",
    )
    assert result.status == "ambiguous_cross_source_lineage"
    assert not result.events
    assert "source lineages" in result.diagnostics[0]
    assert "game_pk=9901001" in result.diagnostics[0]
    assert "pitcher_id=880101" in result.diagnostics[0]


def test_cross_provider_same_timestamp_is_cross_source_not_revision(valid_events):
    """Two providers conflicting at the same collection time fail closed as a
    cross-source lineage conflict, not as an accidental same-time
    ambiguous_revision."""
    other_provider = revised_event(
        valid_events[0],
        source_provider="rival_provider",
        strikeouts=3,
    )
    assert other_provider.collected_at_utc == valid_events[0].collected_at_utc
    result = select_prior_pitcher_events(
        (valid_events[0], other_provider),
        pitcher_id=880101,
        target_information_cutoff_utc="2099-06-04T00:00:00Z",
    )
    assert result.status == "ambiguous_cross_source_lineage"
    assert not result.events


def test_cross_provider_identical_content_is_not_silently_deduped(valid_events):
    """Even byte-identical statistics from two providers stay ambiguous; there
    is no silent cross-provider dedup, voting, or consensus."""
    other_provider = revised_event(
        valid_events[0],
        source_provider="rival_provider",
        collected_at_utc="2099-06-03T12:00:00Z",
    )
    assert other_provider.strikeouts == valid_events[0].strikeouts
    result = select_prior_pitcher_events(
        (valid_events[0], other_provider),
        pitcher_id=880101,
        target_information_cutoff_utc="2099-06-04T00:00:00Z",
    )
    assert result.status == "ambiguous_cross_source_lineage"
    assert not result.events


def test_second_provider_after_cutoff_does_not_create_historical_ambiguity(
    valid_events,
):
    """A different-provider row collected after the cutoff is filtered out before
    lineage detection, so the earlier known provider remains selectable."""
    future_provider = revised_event(
        valid_events[0],
        source_provider="rival_provider",
        collected_at_utc="2099-06-05T12:00:00Z",
        strikeouts=3,
    )
    result = select_prior_pitcher_events(
        (valid_events[0], future_provider),
        pitcher_id=880101,
        target_information_cutoff_utc="2099-06-04T00:00:00Z",
    )
    assert result.status == "ok"
    assert result.events == (valid_events[0],)


def test_same_provider_different_feed_fails_closed(valid_events):
    """Different feed IDs from one provider are distinct lineages and are not
    automatic revisions of one another."""
    other_feed = revised_event(
        valid_events[0],
        source_endpoint_or_feed_id="alternate_feed",
        collected_at_utc="2099-06-03T12:00:00Z",
        strikeouts=3,
    )
    assert other_feed.source_provider == valid_events[0].source_provider
    assert (
        other_feed.source_endpoint_or_feed_id
        != valid_events[0].source_endpoint_or_feed_id
    )
    result = select_prior_pitcher_events(
        (valid_events[0], other_feed),
        pitcher_id=880101,
        target_information_cutoff_utc="2099-06-04T00:00:00Z",
    )
    assert result.status == "ambiguous_cross_source_lineage"
    assert not result.events


def test_cross_source_diagnostic_is_order_independent(valid_events):
    """The cross-source diagnostic is deterministic regardless of input order;
    no provider precedence is implied by ordering."""
    other_provider = revised_event(
        valid_events[0],
        source_provider="rival_provider",
        collected_at_utc="2099-06-03T12:00:00Z",
        strikeouts=3,
    )
    forward = select_prior_pitcher_events(
        (valid_events[0], other_provider),
        pitcher_id=880101,
        target_information_cutoff_utc="2099-06-04T00:00:00Z",
    )
    reverse = select_prior_pitcher_events(
        (other_provider, valid_events[0]),
        pitcher_id=880101,
        target_information_cutoff_utc="2099-06-04T00:00:00Z",
    )
    assert forward.status == reverse.status == "ambiguous_cross_source_lineage"
    assert forward.diagnostics == reverse.diagnostics


def test_cross_source_ambiguity_blocks_whole_selection_no_partial_escape(
    valid_events,
):
    """A cross-source-ambiguous logical event fails the whole selection closed
    rather than silently returning only the unambiguous games for that pitcher;
    no partial cross-provider row escapes."""
    other_provider = revised_event(
        valid_events[0],
        source_provider="rival_provider",
        collected_at_utc="2099-06-03T12:00:00Z",
        strikeouts=3,
    )
    clean_other_game = revised_event(
        valid_events[0],
        source_record_id="9902001:pitcher:880101",
        game_pk=9902001,
        game_start_utc="2099-05-20T18:00:00Z",
        game_finalized_at_utc="2099-05-20T21:00:00Z",
        collected_at_utc="2099-05-20T21:30:00Z",
        official_game_date="2099-05-20",
    )
    result = select_prior_pitcher_events(
        (valid_events[0], other_provider, clean_other_game),
        pitcher_id=880101,
        target_information_cutoff_utc="2099-06-04T00:00:00Z",
    )
    assert result.status == "ambiguous_cross_source_lineage"
    assert not result.events


def test_same_lineage_same_time_conflict_remains_ambiguous_revision(valid_events):
    """Within one lineage, two differing revisions sharing the latest collection
    time still fail closed as ambiguous_revision, never as cross-source."""
    first = revised_event(
        valid_events[0],
        record_status="corrected",
        collected_at_utc="2099-06-03T12:00:00Z",
        strikeouts=9,
    )
    second = revised_event(
        valid_events[0],
        record_status="corrected",
        collected_at_utc="2099-06-03T12:00:00Z",
        strikeouts=10,
    )
    assert first.source_lineage_key == second.source_lineage_key
    result = select_prior_pitcher_events(
        (first, second),
        pitcher_id=880101,
        target_information_cutoff_utc="2099-06-04T00:00:00Z",
    )
    assert result.status == "ambiguous_revision"
    assert not result.events


def test_source_lineage_completes_source_identity(valid_events):
    """source_record_id is stable per logical pitcher-game; the full source
    identity is the lineage (provider, feed) plus source_record_id."""
    event = valid_events[0]
    assert event.source_record_id == "9901001:pitcher:880101"
    assert event.source_lineage_key == (
        "statsapi_decoded_final_boxscore",
        "caller_supplied_boxscore",
    )
    other = revised_event(event, source_provider="rival_provider")
    assert other.logical_event_key == event.logical_event_key
    assert other.source_record_id == event.source_record_id
    assert other.source_lineage_key != event.source_lineage_key


def test_selector_ignores_other_pitchers(valid_events):
    result = select_prior_pitcher_events(
        valid_events,
        pitcher_id=880102,
        target_information_cutoff_utc="2099-06-04T00:00:00Z",
    )
    assert len(result.events) == 1
    assert result.events[0].pitcher_id == 880102


def test_selector_fails_closed_on_invalid_input_record(valid_events):
    malformed = event_raw(valid_events[0], innings_pitched_display="6.3")
    result = select_prior_pitcher_events(
        (malformed,),
        pitcher_id=880101,
        target_information_cutoff_utc="2099-06-04T00:00:00Z",
    )
    assert result.status == "invalid_record"
    assert not result.events


def test_unknown_availability_is_rejected_by_adapter(valid_payload):
    del valid_payload["collectedAtUtc"]
    result = adapt_finalized_boxscore_payload(
        valid_payload,
        collected_at_utc=None,
    )
    assert not any(event.pitcher_id == 880101 for event in result.events)
    assert result.rejected_records == 5


def test_adapter_rejects_ambiguous_duplicate_pitcher_list(valid_payload):
    valid_payload["games"][0]["teams"]["home"]["pitchers"].append(880101)
    result = adapt_finalized_boxscore_payload(valid_payload)
    assert not any(event.home_away == "home" for event in result.events)
    assert result.diagnostics[0].code == "ambiguous_duplicate_pitcher"


def test_adapter_diagnoses_malformed_pitcher_list(valid_payload):
    valid_payload["games"][0]["teams"]["home"]["pitchers"].append(
        {"id": "not-decoded"}
    )
    result = adapt_finalized_boxscore_payload(valid_payload)
    assert not any(event.home_away == "home" for event in result.events)
    assert result.diagnostics[0].code == "malformed_pitcher_list"


def test_module_has_no_network_import_or_default_store_path():
    module_path = Path(__file__).parents[1] / "data" / "mlb_pitcher_game_events.py"
    source = module_path.read_text(encoding="utf-8")
    assert "import requests" not in source
    assert "urllib.request" not in source
    assert "socket" not in source
    store_signature = inspect.signature(PitcherGameEventStore)
    assert store_signature.parameters["path"].default is inspect.Parameter.empty


def test_module_has_no_scheduler_recommendation_or_model_integration():
    module_path = Path(__file__).parents[1] / "data" / "mlb_pitcher_game_events.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not imported_roots & {
        "scheduler",
        "recommendation",
        "model",
        "registry",
    }
    assert "learning_eligible" not in EVENT_FIELDS


def test_stake_changes_cannot_change_pitcher_event_or_selection(valid_events):
    baseline = select_prior_pitcher_events(
        valid_events,
        pitcher_id=880101,
        target_information_cutoff_utc="2099-06-04T00:00:00Z",
    )
    for hypothetical_stake in (0, 25, 1000000):
        unrelated_bet_context = {"stake": hypothetical_stake}
        assert "stake" not in baseline.events[0].to_dict()
        assert unrelated_bet_context["stake"] == hypothetical_stake
        repeated = select_prior_pitcher_events(
            valid_events,
            pitcher_id=880101,
            target_information_cutoff_utc="2099-06-04T00:00:00Z",
        )
        assert repeated == baseline
