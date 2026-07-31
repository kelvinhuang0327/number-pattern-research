"""Tests for the P544B read-only replay artifact inventory.

Unit tests exercise the pure helpers on synthetic data only. Integration
tests read the committed artifact pair and rebuild the inventory at the
commit recorded inside it, proving byte-level reproducibility without ever
touching a database or the network.
"""

from __future__ import annotations

import json
from pathlib import Path

from analysis import p544b_readonly_replay_artifact_inventory as inv

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_STEM = "outputs/research/p544b_readonly_replay_artifact_inventory_20260710"


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------

def test_parse_task_id():
    assert inv.parse_task_id("p543d_contract_validation_pilot_20260710.json") == "p543d"
    assert inv.parse_task_id("P271E_scoped_adapter_20260612.md") == "p271e"
    assert inv.parse_task_id("p268d1_backfill_20260610.ledger.json") == "p268d1"
    assert inv.parse_task_id("big649_measurement_export_20260621.json") is None


def test_parse_artifact_date():
    assert inv.parse_artifact_date("p543d_pilot_20260710.json") == "20260710"
    assert inv.parse_artifact_date("p268d1_x_20260610.summary.json") == "20260610"
    assert inv.parse_artifact_date("p268d1_x_20260610_extra.json") == "20260610"
    assert inv.parse_artifact_date("no_date_here.json") is None


HEX_A = "a" * 64
HEX_B = "b" * 64


def test_extract_declared_links_standard_shape():
    node = {
        "source_artifacts": [
            {"role": "primary", "path": "outputs/research/x_20260101.json", "sha256": HEX_A}
        ]
    }
    links = inv.extract_declared_links(node, "outputs/research/owner.json")
    assert links == [
        {
            "owner_path": "outputs/research/owner.json",
            "declared_path": "outputs/research/x_20260101.json",
            "declared_sha256": HEX_A,
            "ambiguous_pairing": False,
        }
    ]


def test_extract_declared_links_ignores_qualified_digest_keys():
    # Regression for the P271J/P271K shape: a module path next to production
    # DB hashes must NOT become a link (the digests describe the DB, not the
    # module file).
    node = {
        "implemented_module": "lottery_api/prospective_capture_ledger.py",
        "production_db_sha256_before": HEX_A,
        "production_db_sha256_after": HEX_A,
    }
    assert inv.extract_declared_links(node, "owner/a.json") == []


def test_extract_declared_links_multi_value_objects_are_ambiguous():
    two_paths = {"script": "a/b.py", "artifact": "c/d.json", "sha256": HEX_A}
    links = inv.extract_declared_links(two_paths, "owner/a.json")
    assert len(links) == 2 and all(l["ambiguous_pairing"] for l in links)

    two_hexes = {"path": "a/b.py", "sha256": HEX_A, "digest": HEX_B}
    links = inv.extract_declared_links(two_hexes, "owner/a.json")
    assert len(links) == 2 and all(l["ambiguous_pairing"] for l in links)


def test_extract_declared_links_traverses_nested_containers():
    node = {"deep": [{"inner": {"path": "x/y.json", "sha256": HEX_B}}]}
    links = inv.extract_declared_links(node, "owner/a.json")
    assert len(links) == 1 and links[0]["declared_sha256"] == HEX_B
    assert links[0]["ambiguous_pairing"] is False


def test_classify_direct_tiers():
    assert inv.classify_direct("p1_replay_export.json", "") == "replay_named"
    assert (
        inv.classify_direct("p1_export.json", "reads strategy_prediction_replays rows")
        == "replay_table_consumer"
    )
    assert inv.classify_direct("p1_export.json", "mentions replay once") == "replay_term_content"
    assert inv.classify_direct("p1_export.json", "nothing relevant") == "non_replay"


def test_apply_link_closure_transitive():
    classes = {"a.json": "non_replay", "b.json": "non_replay", "c.json": "replay_named"}
    links = [
        {"owner_path": "a.json", "declared_path": "b.json", "declared_sha256": HEX_A},
        {"owner_path": "b.json", "declared_path": "c.json", "declared_sha256": HEX_B},
    ]
    result = inv.apply_link_closure(classes, links)
    assert result["a.json"] == "replay_linked"
    assert result["b.json"] == "replay_linked"
    assert result["c.json"] == "replay_named"


def test_pair_stem_and_lottery_hints():
    assert inv.pair_stem("outputs/research/x_20260101.json") == "outputs/research/x_20260101"
    assert inv.pair_stem("outputs/research/x_20260101.md") == "outputs/research/x_20260101"
    assert inv.pair_stem("outputs/research/x.jsonl") is None
    assert inv.lottery_hints("p540b_daily539_incremental_replay.json") == ["539", "daily539"]
    assert inv.lottery_hints("p544b_generic.json") == []


def test_canonical_payload_digest_excludes_volatile_fields():
    base = {"schema": "s", "value": 1, "generated_at_utc": "2026-07-10T00:00:00+00:00"}
    later = dict(base, generated_at_utc="2026-07-11T09:09:09+00:00")
    digest = inv.canonical_payload_digest(base)
    assert digest == inv.canonical_payload_digest(later)
    assert digest == inv.canonical_payload_digest(dict(base, canonical_payload_digest=digest))
    assert digest != inv.canonical_payload_digest(dict(base, value=2))


def test_canonical_source_has_no_wall_clock_or_sqlite_access():
    source = Path(inv.__file__).read_text(encoding="utf-8")
    forbidden = (
        "datetime.now(",
        "datetime.utcnow(",
        "time.time(",
        "getmtime(",
        "st_mtime",
        "sqlite3",
    )
    assert all(token not in source for token in forbidden)


# ---------------------------------------------------------------------------
# committed artifact integration (git required, read-only)
# ---------------------------------------------------------------------------

def _load_artifact() -> dict:
    return json.loads((REPO_ROOT / f"{ARTIFACT_STEM}.json").read_text(encoding="utf-8"))


def test_committed_artifact_digest_self_consistent():
    payload = _load_artifact()
    assert payload["schema"] == inv.SCHEMA
    assert payload["canonical_payload_digest"] == inv.canonical_payload_digest(payload)


def test_committed_artifact_scope_and_safety_invariants():
    payload = _load_artifact()
    rows = payload["artifacts"]
    assert rows, "replay inventory must not be empty"
    assert all(r["path"].startswith("outputs/research/") for r in rows)
    assert all(r["classification"] != "non_replay" for r in rows)
    replay_paths = {r["path"] for r in rows}
    assert {l["owner_path"] for l in payload["link_records"]} <= replay_paths
    assert all("verification" in l for l in payload["link_records"])
    safety = payload["safety"]
    assert safety["database_opened"] is False
    assert safety["network_used"] is False
    assert safety["services_controlled"] is False
    assert (
        payload["final_classification"]
        == "P544B_READONLY_REPLAY_ARTIFACT_INVENTORY_COMPLETE"
    )


def test_committed_artifact_semantic_metrics_unchanged():
    payload = _load_artifact()
    assert payload["corpus_summary"]["total_files"] == 497
    assert payload["replay_summary"]["replay_related_files"] == 361
    assert payload["replay_summary"]["replay_related_bytes"] == 48_718_778
    assert len([key for key in payload["lineage_summary"] if key != "unparsed"]) == 180
    assert payload["link_summary"]["replay_owned_links"] == 115
    counts = payload["link_summary"]["verification_counts"]
    assert counts["verified_raw_bytes"] == 98
    assert counts["digest_mismatch"] == 1
    assert counts["path_not_relative"] == 9
    assert len(payload["unpaired_artifacts"]) == 21


def test_committed_artifact_known_mismatch_is_explained():
    payload = _load_artifact()
    mismatches = [
        l for l in payload["link_records"] if l["verification"] == "digest_mismatch"
    ]
    assert len(mismatches) == 1
    only = mismatches[0]
    assert only["declared_path"] == "analysis/p273a_distinct_ticket_identity_export.py"
    historical = only["declared_digest_matches_historical"]
    assert historical is not None
    assert historical["commit"].startswith("be6365d")


def test_markdown_consistent_with_json():
    payload = _load_artifact()
    md = (REPO_ROOT / f"{ARTIFACT_STEM}.md").read_text(encoding="utf-8")
    assert payload["canonical_payload_digest"] in md
    assert payload["head_commit"] in md
    assert payload["chain_integrity"] in md
    assert payload["final_classification"] in md
    assert f"**{payload['replay_summary']['replay_related_files']}**" in md
    assert f"**{payload['corpus_summary']['total_files']}**" in md


def test_repeated_rebuild_is_byte_reproducible_and_matches_committed():
    payload = _load_artifact()
    rebuilt_1 = inv.build_inventory(REPO_ROOT, payload["head_commit"])
    rebuilt_2 = inv.build_inventory(REPO_ROOT, payload["head_commit"])

    expected_timestamp = inv.commit_timestamp_utc(REPO_ROOT, payload["head_commit"])
    assert rebuilt_1["generated_at_utc"] == expected_timestamp
    assert rebuilt_2["generated_at_utc"] == expected_timestamp

    json_1 = inv.serialize_json(rebuilt_1)
    json_2 = inv.serialize_json(rebuilt_2)
    committed_json = (REPO_ROOT / f"{ARTIFACT_STEM}.json").read_text(encoding="utf-8")
    assert json_1 == json_2 == committed_json

    markdown_1 = inv.render_markdown(rebuilt_1)
    markdown_2 = inv.render_markdown(rebuilt_2)
    committed_markdown = (REPO_ROOT / f"{ARTIFACT_STEM}.md").read_text(encoding="utf-8")
    assert markdown_1 == markdown_2 == committed_markdown
    assert rebuilt_1["canonical_payload_digest"] == payload["canonical_payload_digest"]
    assert rebuilt_2["canonical_payload_digest"] == payload["canonical_payload_digest"]
