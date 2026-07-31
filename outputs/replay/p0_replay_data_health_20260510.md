# P0 Replay Data Health — 2026-05-10

## Worktree Convergence

### Before

```text
/Users/kelvin/Kelvin-WorkSpace/LotteryNew                                       
      7306264 [feature/phase4-required-check-20260509]
/private/tmp/lotterynew-phase4-clean                                            
      3496d68 [phase4-clean]
/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean                                 
      3496d68 [feature/phase4-required-check-clean-20260510]
/Users/kelvin/Kelvin-WorkSpace/LotteryNew-main-postmerge                        
      4ff5adc [codex/p1-replay-lifecycle-rejected-canonical-promotion-plan]
/Users/kelvin/Kelvin-WorkSpace/LotteryNew-roadmap-20260509                      
      38cbacf [codex/replay-required-check-roadmap-reconcile-20260509]
/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/gallant-rosalind-97a32a
      3496d68 [claude/gallant-rosalind-97a32a]
/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/vigilant-meninsky-6af4cd
      3496d68 [claude/vigilant-meninsky-6af4cd]
```

### After

```text
/Users/kelvin/Kelvin-WorkSpace/LotteryNew                                       
      7306264 [feature/phase4-required-check-20260509]
/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean                                 
      3496d68 [feature/phase4-required-check-clean-20260510]
/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/gallant-rosalind-97a32a
      3496d68 [claude/gallant-rosalind-97a32a]
/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/vigilant-meninsky-6af4cd
      3496d68 [claude/vigilant-meninsky-6af4cd]
```

## Data Health

The clean worktree DB at `lottery_api/data/lottery_v2.db` is the local replay store used for validation. The replay rows do **not** expose a `lifecycle_status` column directly; the canonical lifecycle comes from the strategy catalog / registry used by the API. I used that catalog-backed lookup for the lifecycle rollup below.

### Lifecycle row counts

- ONLINE: 460
- OFFLINE: 0
- REJECTED: 0
- OBSERVATION: 0
- RETIRED: 0

### Zero-row lifecycle states

- OFFLINE
- REJECTED
- OBSERVATION
- RETIRED

## API Samples

### Freshness

```json
{"filter_lifecycle_status": "ONLINE", "coverage_mode": "LIMITED", "total_rows": 460, "total_predicted": 420, "total_replay_error": 40, "legacy_error_count": 40, "has_legacy_errors": true}
```

### History — ONLINE

```json
{"filter_lifecycle_status": "ONLINE", "total": 140, "records_len": 1, "record": {"lottery": "BIG_LOTTO", "target_draw": "99000105", "target_date": "2010/12/31", "strategy_id": "biglotto_deviation_2bet", "lifecycle_status": "ONLINE", "predicted_numbers": [3, 8, 22, 35, 38, 43], "actual_numbers": [4, 9, 27, 36, 38, 39], "hit_numbers": [38], "hit_count": 1, "replay_status": "PREDICTED"}}
```

### History — empty lifecycle states

```text
OFFLINE      -> {"filter_lifecycle_status": "OFFLINE", "total": 0, "records_len": 0}
REJECTED     -> {"filter_lifecycle_status": "REJECTED", "total": 0, "records_len": 0}
OBSERVATION  -> {"filter_lifecycle_status": "OBSERVATION", "total": 0, "records_len": 0}
RETIRED      -> {"filter_lifecycle_status": "RETIRED", "total": 0, "records_len": 0}
```

## Guardrails

- No production DB writes were performed.
- No registry backfill or strategy promotion was performed.
- No branch protection settings were modified.
- No strategy mining or result-discovery work was run.
