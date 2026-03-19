# Player Behavior / Split-Risk Analysis — Methodology

## Popularity Scoring

The popularity model assigns a 0-100 score estimating how commonly human players might choose a similar ticket pattern. Higher score = more popular = greater pari-mutuel dilution risk.

### 9 Bias Heuristics

| Bias | Weight | Rationale |
|------|--------|-----------|
| Birthday (1-31) | 0.20 | Dominant player selection bias — most choose dates |
| Lucky numbers | 0.10 | Cultural: 7, 8, 9, 17, 18, 28, 38, 48 (八=發) |
| Consecutive runs | 0.15 | Players often pick sequences (12-13-14) |
| Arithmetic sequence | 0.10 | Equal-spacing patterns (5, 10, 15, 20, 25, 30) |
| Decade clustering | 0.15 | Numbers bunched in same decade (20s, 30s) |
| Low-number bias | 0.10 | Preference for lower third of pool |
| Round numbers | 0.05 | Multiples of 5 or 10 |
| Grid visual pattern | 0.10 | Alignment on 7-column Taiwan bet slip (rows, columns, diagonals) |
| Parity uniformity | 0.05 | All-odd or all-even tickets |

### Scoring Formula

```
popularity_score = 100 × Σ(weight_i × normalized_bias_i)
```

Each bias is normalized to [0,1] based on how extreme the pattern is relative to expected random behavior.

### Thresholds

| Score Range | Level | Meaning |
|-------------|-------|---------|
| 0-29 | LOW | Uncommon pattern, low split risk |
| 30-59 | MEDIUM | Some common features present |
| 60-100 | HIGH | Multiple popular biases, high dilution risk |

## Split Risk Assessment

Maps popularity score to prize tier impact:

- **BIG_LOTTO**: Tiers 1-3 pari-mutuel (頭獎/貳獎/參獎), Tiers 4-8 fixed
- **POWER_LOTTO**: Tiers 1-3 pari-mutuel, Tiers 4-10 fixed
- **DAILY_539**: Tier 1 only pari-mutuel (頭獎 ~8M), Tiers 2-4 fixed

Fixed-payout tiers are unaffected by split risk. Only pari-mutuel tiers are relevant.

## Anti-Crowd Alternatives

When a ticket scores ≥ 50, the system suggests a structurally close alternative:

1. Identify numbers with highest bias priority (birthday range > lucky > low > round)
2. Replace at most 2 numbers (never > 33% of ticket)
3. Choose replacements that are: > 31, non-lucky, non-round, in upper pool range
4. Re-score the alternative to confirm improvement

## Limitations

- This is a heuristic model based on known selection biases. Actual player distributions are unavailable.
- The model cannot account for specific lottery outlet patterns or regional preferences.
- Lucky number weights are based on general Chinese cultural numerology; individual player behavior may differ.
- Anti-crowd alternatives maintain structural similarity but may not be optimal in all cases.
