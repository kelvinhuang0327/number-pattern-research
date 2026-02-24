# Stability Audit Report: BIG_LOTTO

          Strategy  150p_Rate  500p_Rate  1500p_Rate                                   Status
   Orthogonal_3Bet   4.000000        5.8    5.266667      📈 LATE BLOOMER (Needs Large Sample)
        VAE_Single   3.333333        2.2    2.266667 ⚖️ MODERATE DECAY (Standard AI Behavior)
Frequency_Baseline   0.666667        2.2    1.266667 ⚖️ MODERATE DECAY (Standard AI Behavior)
       Random_3Bet   6.666667        6.0         NaN ⚖️ MODERATE DECAY (Standard AI Behavior)
    Frequency_3Bet   2.666667        4.8         NaN ⚖️ MODERATE DECAY (Standard AI Behavior)

## Expert Analysis
- **Decay Rate**: Strategies with high decay from 150p to 1500p are likely capturing transient noise.
- **Consistency**: Robust strategies exhibit < 0.5% variance in hit rates across all windows.
