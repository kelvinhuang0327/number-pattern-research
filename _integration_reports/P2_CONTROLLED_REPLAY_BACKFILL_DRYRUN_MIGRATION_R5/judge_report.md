# Fresh Judge report

## Initial BOUNDED Judge

Verdict: `REFUTED`

The source and read-only DB contract passed, but the Judge found one mandatory
failure-path defect: with a valid JSON destination and invalid CSV destination,
the source published a READY JSON artifact before the CSV open failed.

```text
INITIAL_JUDGE_INPUT_HEAD: 3d6df001da3a0633ab91f164d722b595ca76d2e1
INITIAL_JUDGE_INPUT_TREE: beadb5fe3932a49d8619caf05c95ff3278489a44
INITIAL_IMPLEMENTATION_SHA256: e53dcaeea8eefc3adc2d49d198e7a4dfbfe51aea20e8723b7286b132f5f3de45
INITIAL_TEST_SHA256: 1823e8165f015240b5870a4a34ccf5e7663f7ce4ad3f711b15b5fd163c4c2854
INITIAL_JUDGE_VERDICT: REFUTED
POST_INITIAL_JUDGE_SOURCE_OR_TEST_EDIT: YES
INITIAL_JUDGE_EVIDENCE_VALID_FOR_FINAL_TREE: NO
DELTA_REJUDGE_REQUIRED: YES
```

## Bounded remediation

The Worker added destination preflight before DB access or output publication
and added an invalid-CSV regression requiring no partial JSON/CSV output and an
unchanged fixture DB. The final Worker focused suite passed `12/12`.

## DELTA Re-Judge

Verdict: `VERIFIED`

The Judge inspected the exact remediation diff and ran the invalid-CSV,
invalid-JSON, and successful-output regression slice: `3 passed in 1.16s`.
It confirmed that no SQL, DDL, migration, backfill executor, API/UI, scheduler,
production DB, scope, or ledger behavior expanded.

```text
DELTA_REJUDGE_INPUT_HEAD: 3d6df001da3a0633ab91f164d722b595ca76d2e1
DELTA_REJUDGE_INPUT_TREE: beadb5fe3932a49d8619caf05c95ff3278489a44
DELTA_IMPLEMENTATION_SHA256: cbdca8b3382ff67bb2c4e1b236e34cb0bc54761789fad8687414397d8b04cd52
DELTA_TEST_SHA256: 9551b9e4e625fa54aab5aa07a8a41492053da1abfbe07fc001cff77b3926406f
DELTA_REJUDGE_VERDICT: VERIFIED
POST_DELTA_JUDGE_SOURCE_OR_TEST_EDIT: NO
DELTA_JUDGE_EVIDENCE_VALID_FOR_FINAL_TREE: YES
FINAL_JUDGE_INPUT_HEAD: 3d6df001da3a0633ab91f164d722b595ca76d2e1
FINAL_JUDGE_INPUT_TREE: beadb5fe3932a49d8619caf05c95ff3278489a44
FINAL_JUDGE_VERDICT: VERIFIED
FINAL_TREE_JUDGE_CONTINUITY: PASS
```

## Run accounting

```text
LOCAL_FULL_SUITE_RUNS: 0
FOCUSED_TEST_RUNS: 7
INITIAL_JUDGE_RUNS: 1
DELTA_REJUDGE_RUNS: 1
FULL_JUDGE_RUNS: 0
EXACT_HEAD_CI_RUNS: 0
```

