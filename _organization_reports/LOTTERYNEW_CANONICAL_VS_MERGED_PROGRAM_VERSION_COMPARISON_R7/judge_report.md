# Fresh-Context Judge Report

**Task:** `LOTTERYNEW_CANONICAL_VS_MERGED_PROGRAM_VERSION_COMPARISON_R7`  
**Terminal Fable Judge verdict:** `VERIFIED_WITH_CAVEATS`  
**Packet verdict:** `PASS_WITH_CAVEATS`

## Judge continuity

The Initial BOUNDED Judge returned `REFUTED` for one remediation-eligible `REPORT_DEFECT`.

The reports incorrectly stated that merged live registry source implemented two P541F `OBSERVATION` stubs. Independent inspection established that:

- Canonical source/test implements four executable target-native IDs as `ONLINE`.
- Merged live `lottery_api/models/replay_strategy_registry.py` implements none of those IDs or registration hooks.
- The untracked merged P541F test proposes two non-executable `OBSERVATION` stubs that are absent from merged registry source.

No clean retry was required because the defect was confined to report classification and wording.

## Remediation

The Worker updated only:

- `semantic_comparison.jsonl`
- `contract_conflicts.md`
- `program_version_summary.yaml`
- `next_action_recommendation.md`
- `final_report.yaml`

The corrected reports now distinguish implemented source authority from the untracked proposed test contract.

## DELTA evidence

- All five supplied remediated-file SHA-256 values reproduced exactly.
- `semantic_comparison.jsonl` contains 30 unique valid rows with this distribution:
  - `MERGED_AHEAD_UNVERIFIED`: 5
  - `BIDIRECTIONAL_DIVERGENCE`: 2
  - `MERGED_AHEAD_VERIFIED`: 8
  - `CANONICAL_AHEAD`: 13
  - `CONTRACT_CONFLICT`: 2
- The merged registry row is correctly `CANONICAL_AHEAD`.
- The P541F test row remains `CONTRACT_CONFLICT` because the untracked test proposes behavior absent from merged source and incompatible with canonical `ONLINE` authority.
- Stale claims that merged live source implements the two stubs are absent.
- Program counts are internally consistent: 13 canonical-ahead, two conflicts, and 1,317 unresolved.
- The next recommendation is exactly one Owner decision concerning the P541F source/test authority and lifecycle contract.
- The 13-file artifact manifest, using the declared Ruby bytewise basename order and manifest serialization, reproduces:
  `daa3e8911e256b5a130c400c1006c33eb5b00df11387847abae8c868a782a688`.

## Final-tree and scope continuity

- Merged HEAD: `3d6df001da3a0633ab91f164d722b595ca76d2e1`
- Merged tree: `beadb5fe3932a49d8619caf05c95ff3278489a44`
- Merged registry SHA-256 remains:
  `bdc035b2f49a0368001ffd1af07d90f4d382cba79671abdea904e8b91de9a54f`
- Merged P541F test SHA-256 remains:
  `1a4bcfc0fec647025d104c43d7ac1e0fdfeab3c87c4113502be1b09f4fdee916`
- No source, test, config, output, database, or Git-ref change occurred after the Initial Judge.
- No protected or unknown content was read.
- Tests, application, DB access, network, fetch, LSP, indexing, and full scans were not run.

## Caveats

- Canonical remote freshness remains `UNVERIFIED_NO_FETCH`.
- Semantic review is intentionally bounded to 30 load-bearing paths; 1,308 nonidentical paths remain outside semantic review.
- Eleven unknown, four protected, and one Owner-protected path remain metadata-only.

## Run accounting

LOCAL_FULL_SUITE_RUNS: 0
FOCUSED_TEST_RUNS: 0
INITIAL_JUDGE_RUNS: 1
DELTA_REJUDGE_RUNS: 1
FULL_JUDGE_RUNS: 0
EXACT_HEAD_CI_RUNS: 0

INITIAL_JUDGE_INPUT_HEAD: 3d6df001da3a0633ab91f164d722b595ca76d2e1
INITIAL_JUDGE_INPUT_TREE: beadb5fe3932a49d8619caf05c95ff3278489a44
INITIAL_JUDGE_VERDICT: REFUTED
POST_INITIAL_JUDGE_SOURCE_OR_TEST_EDIT: NO

DELTA_REJUDGE_INPUT_HEAD: 3d6df001da3a0633ab91f164d722b595ca76d2e1
DELTA_REJUDGE_INPUT_TREE: beadb5fe3932a49d8619caf05c95ff3278489a44
DELTA_REJUDGE_VERDICT: VERIFIED_WITH_CAVEATS
POST_DELTA_JUDGE_SOURCE_OR_TEST_EDIT: NO

FINAL_JUDGE_INPUT_HEAD: 3d6df001da3a0633ab91f164d722b595ca76d2e1
FINAL_JUDGE_INPUT_TREE: beadb5fe3932a49d8619caf05c95ff3278489a44
FINAL_JUDGE_VERDICT: VERIFIED_WITH_CAVEATS

NEW_FINAL_TREE_EVIDENCE: Five remediated-file hashes; corrected semantic distribution; exact canonical/merged source-test authority inspection; 13-file artifact-set digest
REUSED_FINAL_TREE_EVIDENCE: Unaffected Initial authority, inventory, byte-level, lineage, dirty-collision, scope, and safety evidence
INVALIDATED_EVIDENCE: Initial P541F semantic wording and pre-remediation five-file identities
UNAFFECTED_EVIDENCE_REUSED_BY_DELTA: Canonical/merged identities, path inventory, byte comparison, lineage map, dirty-collision handling, and safety ledger
