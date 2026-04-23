# 威力彩 PP3 + MidFreq 正交組合 8h 驗證

- 時間戳: 2026-04-22T16:18:32.303207
- seed: 42
- capability gate: PASS
- leakage check: PASS
- 最終結論: **WATCH**
- 下一輪: 保留 WATCH，等待更多 OOS 樣本

## 基準比較

| 策略 | 150p Edge | 500p Edge | 1500p Edge |
|---|---:|---:|---:|
| fourier_rhythm_3bet | +0.17% | +0.63% | +2.70% |
| pp3_freqort_4bet | +5.40% | +2.20% | +3.00% |

## 候選摘要

| 候選 | 公式 | rho(Fourier residual) | 150p | 500p | 1500p | Verdict |
|---|---|---:|---|---|---|---|
| mf_residual_4bet | `score = norm(midfreq, w=100)` | +0.04 | +2.06%, p=0.3881, d=0.44 | +2.20%, p=0.2139, d=0.81 | +3.06%, p=0.0199, d=2.52 | **WATCH** |
| mf_antifourier_4bet | `score = norm(midfreq, w=100) - 0.60 * norm(fourier, w=500)` | -0.23 | +0.73%, p=0.5721, d=-0.05 | +2.40%, p=0.1841, d=0.95 | +3.06%, p=0.0149, d=2.45 | **WATCH** |
| mf_stable_antifourier_4bet | `score = 0.60 * norm(midfreq, w=100) + 0.40 * norm(midfreq, w=200) - 0.50 * |mf100-mf200| - 0.35 * norm(fourier, w=500) - 0.20 * norm(gap, w=100)` | -0.06 | +0.06%, p=0.6368, d=-0.15 | +1.80%, p=0.3184, d=0.55 | +2.86%, p=0.0299, d=2.23 | **WATCH** |

## 細節

### mf_residual_4bet

- 公式: `score = norm(midfreq, w=100)`
- 特徵: midfreq100
- 正交性: rho=+0.0416, Jaccard(Fourier residual top6)=0.2062, Jaccard(PP3 core)=0.0000
- 150p: edge=+2.06%, perm_p=0.3881, d=0.44, eff={'2': 0.4003, '3': 0.7001, '4': 0.4003}, prefix={'1': {'rate': 0.0667, 'edge': 0.028}, '2': {'rate': 0.0933, 'edge': 0.0174}, '3': {'rate': 0.14, 'edge': 0.0283}, '4': {'rate': 0.1667, 'edge': 0.0206}}, gate={'edge_positive': True, 'perm_pass': False, 'cohens_d_pass': False, 'marginal_efficiency_pass': False}
- 500p: edge=+2.20%, perm_p=0.2139, d=0.81, eff={'2': 1.375, '3': 1.4375, '4': 1.4375}, prefix={'1': {'rate': 0.032, 'edge': -0.0067}, '2': {'rate': 0.076, 'edge': 0.0001}, '3': {'rate': 0.122, 'edge': 0.0103}, '4': {'rate': 0.168, 'edge': 0.022}}, gate={'edge_positive': True, 'perm_pass': False, 'cohens_d_pass': False, 'marginal_efficiency_pass': True}
- 1500p: edge=+3.06%, perm_p=0.0199, d=2.52, eff={'2': 0.736, '3': 0.6872, '4': 0.7722}, prefix={'1': {'rate': 0.0553, 'edge': 0.0166}, '2': {'rate': 0.096, 'edge': 0.0201}, '3': {'rate': 0.134, 'edge': 0.0223}, '4': {'rate': 0.1767, 'edge': 0.0306}}, gate={'edge_positive': True, 'perm_pass': True, 'cohens_d_pass': True, 'marginal_efficiency_pass': False}
- McNemar: 未執行（未通過前四閘門）

### mf_antifourier_4bet

- 公式: `score = norm(midfreq, w=100) - 0.60 * norm(fourier, w=500)`
- 特徵: midfreq100, anti_fourier500
- 正交性: rho=-0.2336, Jaccard(Fourier residual top6)=0.1102, Jaccard(PP3 core)=0.0000
- 150p: edge=+0.73%, perm_p=0.5721, d=-0.05, eff={'2': 0.4003, '3': 0.7001, '4': 0.1994}, prefix={'1': {'rate': 0.0667, 'edge': 0.028}, '2': {'rate': 0.0933, 'edge': 0.0174}, '3': {'rate': 0.14, 'edge': 0.0283}, '4': {'rate': 0.1533, 'edge': 0.0073}}, gate={'edge_positive': True, 'perm_pass': False, 'cohens_d_pass': False, 'marginal_efficiency_pass': False}
- 500p: edge=+2.40%, perm_p=0.1841, d=0.95, eff={'2': 1.375, '3': 1.4375, '4': 1.5}, prefix={'1': {'rate': 0.032, 'edge': -0.0067}, '2': {'rate': 0.076, 'edge': 0.0001}, '3': {'rate': 0.122, 'edge': 0.0103}, '4': {'rate': 0.17, 'edge': 0.024}}, gate={'edge_positive': True, 'perm_pass': False, 'cohens_d_pass': False, 'marginal_efficiency_pass': True}
- 1500p: edge=+3.06%, perm_p=0.0149, d=2.45, eff={'2': 0.736, '3': 0.6872, '4': 0.7722}, prefix={'1': {'rate': 0.0553, 'edge': 0.0166}, '2': {'rate': 0.096, 'edge': 0.0201}, '3': {'rate': 0.134, 'edge': 0.0223}, '4': {'rate': 0.1767, 'edge': 0.0306}}, gate={'edge_positive': True, 'perm_pass': True, 'cohens_d_pass': True, 'marginal_efficiency_pass': False}
- McNemar: 未執行（未通過前四閘門）

### mf_stable_antifourier_4bet

- 公式: `score = 0.60 * norm(midfreq, w=100) + 0.40 * norm(midfreq, w=200) - 0.50 * |mf100-mf200| - 0.35 * norm(fourier, w=500) - 0.20 * norm(gap, w=100)`
- 特徵: midfreq100, midfreq200, stability_penalty, anti_fourier500, anti_gap100
- 正交性: rho=-0.0638, Jaccard(Fourier residual top6)=0.1578, Jaccard(PP3 core)=0.0000
- 150p: edge=+0.06%, perm_p=0.6368, d=-0.15, eff={'2': 0.4003, '3': 0.7001, '4': 0.1004}, prefix={'1': {'rate': 0.0667, 'edge': 0.028}, '2': {'rate': 0.0933, 'edge': 0.0174}, '3': {'rate': 0.14, 'edge': 0.0283}, '4': {'rate': 0.1467, 'edge': 0.0006}}, gate={'edge_positive': True, 'perm_pass': False, 'cohens_d_pass': False, 'marginal_efficiency_pass': False}
- 500p: edge=+1.80%, perm_p=0.3184, d=0.55, eff={'2': 1.375, '3': 1.4375, '4': 1.3125}, prefix={'1': {'rate': 0.032, 'edge': -0.0067}, '2': {'rate': 0.076, 'edge': 0.0001}, '3': {'rate': 0.122, 'edge': 0.0103}, '4': {'rate': 0.164, 'edge': 0.018}}, gate={'edge_positive': True, 'perm_pass': False, 'cohens_d_pass': False, 'marginal_efficiency_pass': True}
- 1500p: edge=+2.86%, perm_p=0.0299, d=2.23, eff={'2': 0.736, '3': 0.6872, '4': 0.7468}, prefix={'1': {'rate': 0.0553, 'edge': 0.0166}, '2': {'rate': 0.096, 'edge': 0.0201}, '3': {'rate': 0.134, 'edge': 0.0223}, '4': {'rate': 0.1747, 'edge': 0.0286}}, gate={'edge_positive': True, 'perm_pass': True, 'cohens_d_pass': True, 'marginal_efficiency_pass': False}
- McNemar: 未執行（未通過前四閘門）

## 結論

3 個候選都保住 1500p 正 Edge，其中 2 個在 1500p permutation / Cohen's d 過關，但 150p、500p permutation 與 bet4 邊際效率仍未達門檻，因此結論只能是 WATCH，不可升格。

## Handoff

已更新 wiki/games/power_lotto.md 與 wiki/lessons/key_lessons.md；本輪三候選維持 WATCH-only，無升格、無 McNemar。
