# Lottery Hedge Fund Strategy Report

## BIG_LOTTO

### Section A — Prediction Results
- Candidate source: StrategyCoordinator -> candidate tickets -> hedge-fund overlays
- Default tickets: 3
- Current jackpot: 650000000 (breakeven=593896000)

### Section B — Player Behavior Analysis
- [26, 27, 38, 40, 43, 49]: popularity=19.5, split_risk=LOW, payout_quality=80.6, ev=-23.3664
- [15, 22, 25, 42, 44, 46]: popularity=12.5, split_risk=LOW, payout_quality=85.55, ev=-22.2452
- [3, 5, 10, 29, 31, 45]: popularity=33.8, split_risk=MEDIUM, payout_quality=65.15, ev=-26.7777

### Section C — Payout Optimization
- Best payout portfolio score: 0.0
- Decision: NO_BET (No portfolio satisfies overlap, budget, and EV constraints)
- Avg overlap: 0.0, diversity bonus: 0.0
- Portfolio EV sum: 0.0, total cost: 0.0

### Section D — Risk & Bankroll Analysis
- Safest bankroll strategy: optimized_portfolio (defensive_fixed, optimal size=0.0)
- Risk of ruin: 0.0, survival probability: 1.0

## POWER_LOTTO

### Section A — Prediction Results
- Candidate source: StrategyCoordinator -> candidate tickets -> hedge-fund overlays
- Default tickets: 3
- Current jackpot: 200000000 (breakeven=2147659000)

### Section B — Player Behavior Analysis
- [18, 22, 25, 27, 33, 35]: popularity=20.0, split_risk=LOW, payout_quality=75.37, ev=-74.2997
- [4, 6, 7, 12, 26, 37]: popularity=21.5, split_risk=LOW, payout_quality=63.78, ev=-78.6861
- [16, 23, 28, 29, 31, 34]: popularity=21.4, split_risk=LOW, payout_quality=66.67, ev=-77.7064

### Section C — Payout Optimization
- Best payout portfolio score: 0.0
- Decision: NO_BET (No portfolio satisfies overlap, budget, and EV constraints)
- Avg overlap: 0.0, diversity bonus: 0.0
- Portfolio EV sum: 0.0, total cost: 0.0

### Section D — Risk & Bankroll Analysis
- Safest bankroll strategy: optimized_portfolio (defensive_fixed, optimal size=0.0)
- Risk of ruin: 0.0, survival probability: 1.0

## DAILY_539

### Section A — Prediction Results
- Candidate source: StrategyCoordinator -> candidate tickets -> hedge-fund overlays
- Default tickets: 3
- Current jackpot: 8000000 (breakeven=25891062)

### Section B — Player Behavior Analysis
- [4, 7, 20, 27, 35]: popularity=11.5, split_risk=LOW, payout_quality=70.07, ev=-33.1151
- [9, 18, 23, 29, 30]: popularity=47.0, split_risk=MEDIUM, payout_quality=45.36, ev=-34.3291
- [1, 6, 17, 31, 32]: popularity=16.0, split_risk=LOW, payout_quality=63.92, ev=-33.4906

### Section C — Payout Optimization
- Best payout portfolio score: 0.0
- Decision: NO_BET (No portfolio satisfies overlap, budget, and EV constraints)
- Avg overlap: 0.0, diversity bonus: 0.0
- Portfolio EV sum: 0.0, total cost: 0.0

### Section D — Risk & Bankroll Analysis
- Safest bankroll strategy: optimized_portfolio (defensive_fixed, optimal size=0.0)
- Risk of ruin: 0.0, survival probability: 1.0

## Final Answers

1. Does payout optimization improve real-world outcomes? Yes, because it prevents forced entry under negative-EV jackpot conditions and turns all current games into NO_BET.
2. How much does it reduce split risk? Average expected-winner reduction: 11.84%
3. What is the optimal portfolio structure? BIG_LOTTO: 0 tickets, avg overlap 0.0, decision=NO_BET; POWER_LOTTO: 0 tickets, avg overlap 0.0, decision=NO_BET; DAILY_539: 0 tickets, avg overlap 0.0, decision=NO_BET
4. What is the safest bankroll strategy? BIG_LOTTO -> optimized_portfolio (defensive_fixed); POWER_LOTTO -> optimized_portfolio (defensive_fixed); DAILY_539 -> optimized_portfolio (defensive_fixed)
5. Can this system outperform naive betting in practice? Yes, operationally. Refusing to bet negative-EV draws is better than naive participation under current jackpot assumptions.
