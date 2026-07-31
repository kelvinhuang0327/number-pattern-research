# P325A Limitations

- DESCRIPTIVE_ONLY. No future-performance, wagering, production-readiness, causal, best-strategy,
  recommended-number, or edge claim is made. A baseline result does NOT prove any future edge.
- The equal-budget comparison is against an ANALYTIC random reference (m independent uniform
  tickets). It is not an empirical subsample of the strategies' own tickets: doing that would need
  per-draw per-ticket hit vectors, absent from the static aggregate artifacts. equal_budget_status
  is therefore INSUFFICIENT_RAW_DATA for the actual-ticket-subsampling variant; nothing was faked.
- The random reference assumes independent tickets; the distinctness correction is negligible
  (O(m²/C(N,s))) but non-zero.
- Lottery pools are taken from documented rules (大樂透 6/49, 今彩539 5/39) and project memory,
  not re-derived from the DB (no DB is opened here).
- The binomial screen tests each row against its own equal-budget-random null; it does not model
  cross-row dependence (overlapping strategies/draws). Bonferroni is conservative but the tests are
  not independent, so surviving counts are indicative, not a formal family-wise guarantee.
- POWER_LOTTO excluded (out of scope; second-zone readiness not established upstream).
- Windows and samples are inherited verbatim from P320A (recent_50/300/750 common draws).
