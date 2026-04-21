# Lottery Hedge Fund Strategy Report

## BIG_LOTTO

### Section A — Prediction Results
- Candidate source: StrategyCoordinator -> candidate tickets -> hedge-fund overlays
- Default tickets: 3
- Current jackpot: 650000000 (breakeven=593896000)

### Section B — Player Behavior Analysis
- [11, 19, 23, 36, 38, 48]: popularity=13.8, split_risk=LOW, payout_quality=84.74, ev=-22.4345
- [1, 5, 12, 16, 27, 43]: popularity=22.2, split_risk=LOW, payout_quality=75.2, ev=-24.5981
- [13, 32, 33, 35, 39, 47]: popularity=21.0, split_risk=LOW, payout_quality=76.81, ev=-24.2355

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
- [12, 17, 25, 26, 29, 32]: popularity=18.9, split_risk=LOW, payout_quality=65.41, ev=-78.1014
- [14, 15, 23, 27, 36, 37]: popularity=12.0, split_risk=LOW, payout_quality=73.5, ev=-75.0735
- [6, 20, 24, 33, 35, 38]: popularity=10.0, split_risk=LOW, payout_quality=84.75, ev=-70.2923

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
- [9, 25, 35, 37, 38]: popularity=26.0, split_risk=LOW, payout_quality=64.65, ev=-33.5013
- [6, 13, 20, 23, 32]: popularity=9.0, split_risk=LOW, payout_quality=71.68, ev=-32.9853
- [10, 22, 24, 29, 34]: popularity=9.5, split_risk=LOW, payout_quality=71.36, ev=-33.0122

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
2. How much does it reduce split risk? Average expected-winner reduction: 6.03%
3. What is the optimal portfolio structure? BIG_LOTTO: 0 tickets, avg overlap 0.0, decision=NO_BET; POWER_LOTTO: 0 tickets, avg overlap 0.0, decision=NO_BET; DAILY_539: 0 tickets, avg overlap 0.0, decision=NO_BET
4. What is the safest bankroll strategy? BIG_LOTTO -> optimized_portfolio (defensive_fixed); POWER_LOTTO -> optimized_portfolio (defensive_fixed); DAILY_539 -> optimized_portfolio (defensive_fixed)
5. Can this system outperform naive betting in practice? Yes, operationally. Refusing to bet negative-EV draws is better than naive participation under current jackpot assumptions.
