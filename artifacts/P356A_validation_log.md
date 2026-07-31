# P356A Validation Log

- Replay readiness: `NOT_RUN`
- Reason: executable entrypoints are not uniformly reliable across all lineages; ID reuse and artifact/stub-only cases would contaminate replay.
- Strategy status changes: `NONE`
- Canonical DB writes: `NONE`

## Artifact Completeness
```json
{
  "every_inventory_lineage_has_skipped_row": true,
  "every_skipped_row_has_skip_reason": true,
  "big_lotto_seed_list_fully_accounted_for": true,
  "db_sha_before": "b1d80e31f490a5a7595a91593641a8df9d488e0be243dc7bf74624dce3c25ee2",
  "db_sha_after": "b1d80e31f490a5a7595a91593641a8df9d488e0be243dc7bf74624dce3c25ee2",
  "db_draw_rows_before": 33362,
  "db_draw_rows_after": 33362,
  "db_replay_rows_before": 94924,
  "db_replay_rows_after": 94924
}
```

## DB Before/After
- SHA before: `b1d80e31f490a5a7595a91593641a8df9d488e0be243dc7bf74624dce3c25ee2`
- SHA after: `b1d80e31f490a5a7595a91593641a8df9d488e0be243dc7bf74624dce3c25ee2`
- Draw rows before/after: `33362` / `33362`
- Replay rows before/after: `94924` / `94924`

## Checks To Run After Generation
- `git status --short`
- `git diff --check`
- `python3 -m py_compile scripts/p356a_all_strategy_inventory.py tests/test_p356a_inventory_artifacts.py`
- `python3 -m pytest tests/test_p356a_inventory_artifacts.py`

## Executed Validation Results
- `python3 -m py_compile scripts/p356a_all_strategy_inventory.py tests/test_p356a_inventory_artifacts.py`: PASS
- `git diff --check`: PASS
- `pytest tests/test_p356a_inventory_artifacts.py`: PASS, 5 passed
- `python3 -m pytest tests/test_p356a_inventory_artifacts.py`: NOT RUN to completion because `/opt/homebrew/opt/python@3.14/bin/python3.14` has no `pytest` module; the local `pytest` executable uses Python 3.13.8 and passed.
