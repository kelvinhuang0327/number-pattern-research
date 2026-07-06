# Source Readiness

- Source: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p300a-d5-ui/backups/p213l_lottery_v2_backup_20260605_20260605_151715.db` (pre-existing tracked backup snapshot).
- Open mode: SQLite URI `mode=ro&immutable=1`; `PRAGMA query_only=1` verified.
- Table: `strategy_prediction_replays`.
- Required columns present: actual_numbers, actual_special, bet_index, dry_run, lottery_type, predicted_numbers, predicted_special, replay_status, strategy_id, target_draw.
- Source rows retained for scope: BIG_LOTTO=24140; DAILY_539=34680.
- Complete predicted/actual main-number rows: verified by parsing every retained row.
- Per-draw actual consistency: verified across all strategies and bet indexes.
- Committed identity alignment: 19500 strategy/draw records and 29250 distinct tickets matched exactly against `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p300a-d5-ui/outputs/research/p273a_distinct_ticket_identity_20260615.json`.
- DB SHA256 before/after: `1b2abd793a3ea3f2d300337eb2db6d2621b52e1600453bc20141377fa6475485` / `1b2abd793a3ea3f2d300337eb2db6d2621b52e1600453bc20141377fa6475485`.
- DB size/mtime before/after: `{'size': 99368960, 'mtime_ns': 1782808188566902575}` / `{'size': 99368960, 'mtime_ns': 1782808188566902575}`.
- Sidecars before/after: `{"/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p300a-d5-ui/backups/p213l_lottery_v2_backup_20260605_20260605_151715.db-journal": {"exists": false, "mtime_ns": null, "size": null}, "/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p300a-d5-ui/backups/p213l_lottery_v2_backup_20260605_20260605_151715.db-shm": {"exists": false, "mtime_ns": null, "size": null}, "/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p300a-d5-ui/backups/p213l_lottery_v2_backup_20260605_20260605_151715.db-wal": {"exists": false, "mtime_ns": null, "size": null}}` / `{"/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p300a-d5-ui/backups/p213l_lottery_v2_backup_20260605_20260605_151715.db-journal": {"exists": false, "mtime_ns": null, "size": null}, "/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p300a-d5-ui/backups/p213l_lottery_v2_backup_20260605_20260605_151715.db-shm": {"exists": false, "mtime_ns": null, "size": null}, "/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p300a-d5-ui/backups/p213l_lottery_v2_backup_20260605_20260605_151715.db-wal": {"exists": false, "mtime_ns": null, "size": null}}`.
- True per-draw combination overlap readiness: PASS for BIG_LOTTO and DAILY_539.
- POWER_LOTTO: excluded; canonical second-zone completeness is not established for full scoring.
