# Lottery Hedge Fund Strategy Report

## BIG_LOTTO

### Section A — Prediction Results
- Candidate source: StrategyCoordinator -> candidate tickets -> hedge-fund overlays
- Default tickets: 3
- Current jackpot: 650000000 (breakeven=593896000)

### Section B — Player Behavior Analysis
- [5, 12, 17, 23, 46, 47]: popularity=22.7, split_risk=LOW, payout_quality=75.75, ev=-24.4708
- [6, 19, 27, 42, 48, 49]: popularity=18.2, split_risk=LOW, payout_quality=78.56, ev=-23.8386
- [7, 13, 14, 15, 22, 45]: popularity=40.2, split_risk=MEDIUM, payout_quality=54.42, ev=-29.0313

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
- [3, 19, 26, 36, 37, 38]: popularity=20.5, split_risk=LOW, payout_quality=68.09, ev=-77.1977
- [10, 17, 22, 23, 27, 30]: popularity=44.5, split_risk=MEDIUM, payout_quality=49.72, ev=-82.7623
- [16, 18, 21, 28, 29, 32]: popularity=26.4, split_risk=LOW, payout_quality=60.73, ev=-79.7085

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
- [4, 12, 18, 32, 34]: popularity=21.0, split_risk=LOW, payout_quality=71.11, ev=-33.1064
- [5, 7, 17, 19, 38]: popularity=20.5, split_risk=LOW, payout_quality=64.42, ev=-33.5018
- [23, 24, 25, 26, 37]: popularity=43.0, split_risk=MEDIUM, payout_quality=38.95, ev=-34.5286

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
2. How much does it reduce split risk? Average expected-winner reduction: 15.91%
3. What is the optimal portfolio structure? BIG_LOTTO: 0 tickets, avg overlap 0.0, decision=NO_BET; POWER_LOTTO: 0 tickets, avg overlap 0.0, decision=NO_BET; DAILY_539: 0 tickets, avg overlap 0.0, decision=NO_BET
4. What is the safest bankroll strategy? BIG_LOTTO -> optimized_portfolio (defensive_fixed); POWER_LOTTO -> optimized_portfolio (defensive_fixed); DAILY_539 -> optimized_portfolio (defensive_fixed)
5. Can this system outperform naive betting in practice? Yes, operationally. Refusing to bet negative-EV draws is better than naive participation under current jackpot assumptions.
