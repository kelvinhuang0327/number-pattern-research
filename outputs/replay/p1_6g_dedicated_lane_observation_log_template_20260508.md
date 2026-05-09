# P1-6G Dedicated Lane Observation Log Template

Use one section per dedicated lane run.

## Run Record
- Run date (UTC):
- Trigger type (`workflow_dispatch` / dry-run):
- Commit SHA:
- Branch:

## Fixture Info
- Fixture path:
- fixture_name:
- fixture_version:
- schema_version:
- synthetic_only:
- Fixture integrity result (PASS/FAIL):

## Dedicated Validation
- Command:
- Result summary (example: `32 passed, 4 deselected, 1 warning`):
- Zero skip result (PASS/FAIL):
- Unexpected skip count:

## Failure Classification
- Classification:
  - fixture_missing
  - fixture_integrity_fail
  - schema_drift
  - test_regression
  - infra_transient
- Immediate action:
- Owner:
- ETA:

## Promotion Criteria Progress
- Main consecutive PASS count:
- PR dry-run consecutive PASS count:
- Integrity false-positive observed (Y/N):
- No-skip enforcement stable (Y/N):
- Triage within 1 business day (Y/N):

## Notes
- Additional evidence links:
- Follow-up tasks:
