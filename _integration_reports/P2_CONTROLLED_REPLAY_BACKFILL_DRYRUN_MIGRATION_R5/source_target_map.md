# Source-to-target map

The R5 locator selects one historical script as migratable product code. Historical
report and output examples are evidence only; the focused test is new work required
by the Worker Packet.

```yaml
- source_path: scripts/p2_controlled_replay_backfill_dryrun.py
  source_sha256: e53dcaeea8eefc3adc2d49d198e7a4dfbfe51aea20e8723b7286b132f5f3de45
  target_path: scripts/p2_controlled_replay_backfill_dryrun.py
  target_preexisting: false
  target_sha256: cbdca8b3382ff67bb2c4e1b236e34cb0bc54761789fad8687414397d8b04cd52
  migration_action: COPY_WITH_AUTHORIZED_FAIL_CLOSED_REMEDIATION
  source_role: DRYRUN_AUDIT_CLI

- source_path: NOT_APPLICABLE_NEW_R5_FOCUSED_TEST
  source_sha256: NOT_APPLICABLE
  target_path: tests/test_p2_controlled_replay_backfill_dryrun.py
  target_preexisting: false
  target_sha256: 9551b9e4e625fa54aab5aa07a8a41492053da1abfbe07fc001cff77b3926406f
  migration_action: CREATE_FOCUSED_CONTRACT_TEST
  source_role: R5_ACCEPTANCE_TEST

- source_path: docs/replay/p2_ts3_regime_backfill_dryrun_report_20260515.md
  source_sha256: NOT_READ_OR_COPIED
  target_path: NOT_APPLICABLE
  target_preexisting: NOT_APPLICABLE
  migration_action: EXCLUDE_HISTORICAL_EVIDENCE
  source_role: HISTORICAL_REPORT

- source_path: outputs/replay/p2_ts3_regime_backfill_dryrun_20260515.json
  source_sha256: NOT_READ_OR_COPIED
  target_path: NOT_APPLICABLE
  target_preexisting: NOT_APPLICABLE
  migration_action: EXCLUDE_HISTORICAL_EVIDENCE
  source_role: HISTORICAL_OUTPUT

- source_path: outputs/replay/p2_ts3_regime_backfill_dryrun_20260515.csv
  source_sha256: NOT_READ_OR_COPIED
  target_path: NOT_APPLICABLE
  target_preexisting: NOT_APPLICABLE
  migration_action: EXCLUDE_HISTORICAL_EVIDENCE
  source_role: HISTORICAL_OUTPUT
```
