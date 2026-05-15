# DAILY_539 H013 Pool-Size / Market-Behavior Validation (2026-04-23)

**Verdict:** REJECT

## Summary

- Data availability verdict: UNUSABLE (0.00% coverage for `jackpot_amount`).
- Formal leakage checker: PASS (`tools/verify_no_data_leakage.py` -> `analysis/results/daily539_poolsize_h013_no_leakage_20260423.txt`)
- Decision rule applied: do not backfill with untrusted proxies. If the exogenous pool-size series is absent, the result is a data-availability REJECT instead of a pseudo-signal.

## Data Availability Audit

| Metric | Value |
|---|---:|
| Total DAILY_539 draws | 5839 |
| Non-null `jackpot_amount` rows | 0 |
| Null rows | 5839 |
| Coverage % | 0.00% |
| Longest consecutive non-null run | 0 |

| Validation window | Required history span | Non-null in tail span | Fully available |
|---:|---:|---:|---|
| 150 | 450 | 0 | no |
| 500 | 800 | 0 | no |
| 1500 | 1800 | 0 | no |

## Candidate Outcomes

### H013 pool_size_regime -> ACB overlay (1 bet) — REJECT

- Incumbent comparator: `acb_1bet`
- Blocker: jackpot_amount coverage is 0.00% (0/5839). No history-only pool regime/growth feature can be built without fabricating a proxy.

| Window | Status | Missing observations | Reason |
|---:|---|---:|---|
| 150 | BLOCKED_NO_POOL_DATA | 450 | jackpot_amount unavailable in the last 450 draws |
| 500 | BLOCKED_NO_POOL_DATA | 800 | jackpot_amount unavailable in the last 800 draws |
| 1500 | BLOCKED_NO_POOL_DATA | 1800 | jackpot_amount unavailable in the last 1800 draws |

### H013b pool_growth_shock -> MidFreq+ACB overlay (2 bet) — REJECT

- Incumbent comparator: `midfreq_acb_2bet`
- Blocker: jackpot_amount coverage is 0.00% (0/5839). No history-only pool regime/growth feature can be built without fabricating a proxy.

| Window | Status | Missing observations | Reason |
|---:|---|---:|---|
| 150 | BLOCKED_NO_POOL_DATA | 450 | jackpot_amount unavailable in the last 450 draws |
| 500 | BLOCKED_NO_POOL_DATA | 800 | jackpot_amount unavailable in the last 800 draws |
| 1500 | BLOCKED_NO_POOL_DATA | 1800 | jackpot_amount unavailable in the last 1800 draws |

### H013c pool_size_x_existing -> ACB+Markov+MidFreq gate (3 bet) — REJECT

- Incumbent comparator: `acb_markov_midfreq_3bet`
- Blocker: jackpot_amount coverage is 0.00% (0/5839). No history-only pool regime/growth feature can be built without fabricating a proxy.

| Window | Status | Missing observations | Reason |
|---:|---|---:|---|
| 150 | BLOCKED_NO_POOL_DATA | 450 | jackpot_amount unavailable in the last 450 draws |
| 500 | BLOCKED_NO_POOL_DATA | 800 | jackpot_amount unavailable in the last 800 draws |
| 1500 | BLOCKED_NO_POOL_DATA | 1800 | jackpot_amount unavailable in the last 1800 draws |

## Framework Checks

- Benchmark framework loaded DAILY_539 with 5839 draws and official seed=42.
- Permutation framework probe (`repeat_last_draw`): edge=-1.40%, p=0.7612, d=-0.603, n_perm=200 (probe only; not an H013 candidate).

## Conclusion

REJECT H013 for now as a data-availability conclusion, not a weak-signal conclusion. Before any future pool-size retry, extend ingestion/backfill to populate a trusted pool-size or sales field for DAILY_539; until then, do not invent proxies or rerun the same family.

## Handoff Notes

- Wiki update: applied.
- New lesson: pool-size research on 539 is blocked until ingestion/backfill provides a trusted exogenous pool series.
