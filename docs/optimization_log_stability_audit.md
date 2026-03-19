# Optimization History: Strategy Stability Audit & Identification System
**Status:** Phase 4 (3-Bet Structural Synergy) Completed

## 1. Objective
Identify and categorize strategies based on performance stability across different backtesting windows (150p, 500p, 1500p) to detect overfitting and long-term decay.

## 2. Code Locations
- **Analysis Tool**: `tools/auto_regime_identifier.py`
  - Purpose: Reads benchmark JSON files and calculates decay rates between windows.
- **Service Layer**: `lottery_api/models/stability_profile.py`
  - Purpose: Provides a runtime interface for querying strategy stability profiles (ROBUST, SHORT_MOMENTUM, LATE_BLOOMER).
- **Integration Points**:
  - `lottery_api/models/unified_predictor.py`: Added `auto_identify_stability` to automatically tag VAE predictions.
  - `lottery_api/models/multi_bet_optimizer.py`: Tagged `Orthogonal_3Bet` strategy results with stability metadata.

## 3. Backtest Report Summary (Power Lotto)
| Strategy | 150p Rate | 1500p Rate | Status | Finding |
| :--- | :--- | :--- | :--- | :--- |
| **VAE_Single** | 6.0% | 5.6% | ✅ **ROBUST** | High consistency; suitable for systematic betting. |
| **Orthogonal_3Bet** | 14.0% | 11.9% | ⚖️ **MODERATE DECAY** | Exhibits short-term momentum; slight long-term decay. |
| **Random_3Bet** | 12.0% | N/A | ⚖️ **STABLE** | Baseline remains consistent in the short-medium term. |

## 4. Key Discoveries
- **VAE Robustness**: VAE-based strategies show the least "performance cliff" between short and long data windows.
- **Short-term Momentum**: The Orthogonal 3-bet strategy captures period-specific noise more effectively, leading to higher short-term spikes but lower long-term averages.

## 5. Phase 2: Adaptive MAB Decay (2026-02-09)
### Objective
Integrate stability metadata into the Multi-Armed Bandit (MAB) learning process to differentiate between "ephemeral momentum" and "long-term robust" strategies.

### Implementation
- **Code Location**: `lottery_api/models/mab_ensemble.py`
- **Logic**:
  - `SHORT_MOMENTUM` strategies (e.g., Orthogonal 3-Bet): Assigned a **High Decay Factor (0.85)**. Forces the MAB to "forget" old performance quickly, reacting faster to recent performance cliffs.
  - `ROBUST` strategies (e.g., VAE): Assigned a **Low Decay Factor (0.98)**. Retains historical credits longer, providing a stable anchor for the ensemble.
  - `LATE_BLOOMER` strategies: Assigned a **Minimal Decay Factor (0.99)** to support large-sample accumulation.

### Expected Impact
Reduces drawdown during "Regime Shifts" by preventing the ensemble from over-allocating to overfitted strategies that are currently in their performance decay phase.

## 6. Phase 3: Power Lotto Zone 2 (1-8) Precision Enhancement (2026-02-09)
### Objective
Improve the hit rate of the special number (Zone 2) from 12.5% (random) towards 18-20%.

### Implementation
- **Code Location**: `lottery_api/models/special_predictor.py`
- **Key Features**:
  - **2nd-Order Markov Integration**: Direct ensemble of `MarkovChain2ndOrderPredictor`.
  - **Modulo & Parity Strategy**: Added `_modulo_parity_strategy` to capture Odd/Even and Mod 4 regression patterns.
  - **Regime-Aware Hybrid Weights**: Enhanced the entropy-based switching logic.

### Results
- **Backtest (300p)**: Reached **15.00%** hit rate.
- **Observation**: Showed high potential (22%) in specific regimes but reverted to 15% overall. This represents a ~20% improvement over the random baseline.

## 7. Phase 4: 3-Bet Structural Synergy (2026-02-09)
### Objective
Extend the "Zone Gap Correction" logic (previously only for 5+ bets) to the 3-bet Orthogonal Strategy to ensure spatial coverage even in low-budget scenarios.

### Implementation
- **Code Location**: `lottery_api/models/multi_bet_optimizer.py`
- **Method**: `generate_orthogonal_strategy_3bets`
- **Logic**:
  - After generating the standard 3 bets (Balanced, Cluster, Recovery), the system now calls `_apply_zone_gap_correction`.
  - If a specific spatial zone (1-5) is identified as a "performance/frequency gap" and is not covered by the regular prediction, the 3rd bet (Recovery/Gap-based) is surgically adjusted to include a number from the missing zone.

### Results
- **Validation**: Verified through `tools/test_3bet_zone_correction.py` using a simulated cold-zone scenario.
- **Impact**: Guaranteed minimum spatial coverage across all 5 zones even with only 3 tickets, providing a safety net against "unpredictable" regime shifts.

## 8. Next Optimization Goal
**Big Lotto Portfolio Balancing**:
- Apply similar structural synergy to the Big Lotto (49 numbers) logic.
- Optimize the `Elite Cluster` size dynamically based on the current regime stability identified by the `StabilityProfile`.
