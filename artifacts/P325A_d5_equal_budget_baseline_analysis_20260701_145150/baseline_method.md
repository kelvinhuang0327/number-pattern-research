# P325A Baseline Method

## Observed metric (recap, from P320A `build_analysis.py`)
For a combination C of strategies over a window of `n` common draws, pool the members' stored
tickets. Per draw, `max_hit = max(|ticket ∩ winning_main|)` over all pooled tickets;
`hit_at_least_k_rate = #{draws: max_hit >= k} / n`. Ticket size s and winning size D:
BIG_LOTTO s=D=6 (pool N=49), DAILY_539 s=D=5 (pool N=39).

## Ticket budget
`m = sample_size_rows / sample_size_draws` = tickets spent per draw (raw, duplicates counted).
Verified: integer and constant per row for all 2418 rows.

## Equal-budget random reference (baseline_reference_only)
A single uniform-random ticket matches at least k of the D winning numbers with the hypergeometric
tail:

    q_k = Σ_{j=k}^{min(s,D)} C(D,j)·C(N-D, s-j) / C(N,s)

For a portfolio of m independent uniform-random tickets, `max_hit >= k` ⇔ at least one ticket
has >= k matches, so:

    random_expected_hit_at_least_k = 1 - (1 - q_k)^m

This is the SAME functional (max-hit>=k over m tickets) as the observed metric, evaluated at the
**identical budget m** — a genuine equal-budget comparison of "your m real tickets" vs "m random
tickets". Distinctness of random tickets is ignored; the correction is O(m²/C(N,s)) ≤ ~4e-4 and
negligible.

Single-ticket tails (q_k):
- BIG_LOTTO: q1=0.564035, q2=0.151016, q3=0.018638, q4=0.00098714
- DAILY_539: q1=0.516713, q2=0.113973, q3=0.010041, q4=0.00029700

## Descriptive delta
`descriptive_delta_vs_baseline_hit_at_least_k = observed - random_expected`.
Positive ⇒ the portfolio beats an equal-budget random pick (number-selection structure beyond
budget). Negative ⇒ it underperforms equal-budget random (member-ticket overlap wastes budget).

## Inferential screen (documented, retrospective)
Under the null "portfolio = m independent random tickets", the count of draws with max_hit>=k is
Binomial(n, random_expected). One-sided exact tail `p = P(X >= x_observed)` (x_observed taken
exactly from the max-hit histogram). Reported per row; a Bonferroni-corrected screen (α=0.05
over all k∈{2,3} tests) flags any combination that beats equal-budget random beyond chance.
This is a retrospective screen only — NOT a predictive, wagering, or production claim.

## Overlap reference
Two independent random tickets share on average s/N of their numbers
(
- BIG_LOTTO: random mean overlap fraction = 0.1224
- DAILY_539: random mean overlap fraction = 0.1282).
`mean_number_overlap_fraction` above this level indicates member tickets cluster more than random,
i.e. budget is partly spent on redundant numbers.
