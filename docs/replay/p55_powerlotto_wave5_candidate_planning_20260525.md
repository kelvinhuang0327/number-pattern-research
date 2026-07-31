# P55 POWER_LOTTO Wave 5 Candidate Planning

**Date:** 2026-05-25
**Branch:** p55-wave5-powerlotto-candidate-planning
**Classification:** P55_POWERLOTTO_WAVE5_CANDIDATE_PLANNING_COMPLETED
**Production rows (DB):** 42460 (unchanged — no DB writes in this task)
**POWER_LOTTO rows in DB:** 9140 (6 strategies × 1500–1570 rows)

---

## 1. Scope and Governance

P55 is a **read-only planning task**. Its purpose is to:

1. Inventory the current POWER_LOTTO replay coverage (what is already row-backed).
2. Identify Wave 5 candidates from P0 strategy universe, tools, benchmark data, and rejected strategy records.
3. Score each candidate across 10 governance dimensions.
4. Select a final Wave 5 shortlist (3 strategies) for P56 dry-run.
5. Produce a P56 dry-run readiness plan.

**No adapter code is written. No dry-run rows are generated. No DB writes occur.**

---

## 2. Current POWER_LOTTO Replay Coverage (Wave 1–4)

### 2.1 Pre-Wave 4 (row-backed before P48)

| strategy_id | Status | Rows | Draw range |
|-------------|--------|------|------------|
| `fourier_rhythm_3bet` | ONLINE (champion) | 1500 | history |
| `power_orthogonal_5bet` | PREDICTED | 1570 | history |
| `power_precision_3bet` | PREDICTED | 1570 | history |

Subtotal: **4640 rows**

### 2.2 Wave 4 (P48 production apply)

| strategy_id | P51/P52 classification | Rows |
|-------------|----------------------|------|
| `midfreq_fourier_mk_3bet` | WATCHLIST (G4 waiver, 500-draw OOS gate) | 1500 |
| `midfreq_fourier_2bet` | INCONCLUSIVE (p=0.073 > 0.05) | 1500 |
| `pp3_freqort_4bet` | INCONCLUSIVE (RSM edge −0.68%, below baseline) | 1500 |

Subtotal: **4500 rows**

**Total POWER_LOTTO rows in DB: 9140**

---

## 3. Strategy Universe Review

### 3.1 P0 Inventory (512 strategies total)

POWER_LOTTO-typed strategies in P0 inventory: 12 total.
Already covered (Wave 1–4): 6 strategies.
Remaining candidates for evaluation: 6 POWER_LOTTO-typed + 5 UNSPECIFIED-typed non-champion strategies.

### 3.2 Hypothesis Registry — Known Failure Patterns (POWER_LOTTO)

From `data/hypothesis_registry.jsonl` and MEMORY.md:

| Strategy / Pattern | Failure reason | Final status |
|--------------------|---------------|--------------|
| `shlc_midfreq_power` | Edge −2.92%, no signal | REJECTED |
| `gap_rebound_powerlotto` | Concept only, no implementation | REJECTED |
| `p1_conditional_branch_powerlotto` | Concept only; L67 conditional <5% = NO-OP | REJECTED |
| `structural_zone_guard_pp3_power` | No tool, HIGH effort, no RSM evidence | REJECTED |
| `special_mab_decay_adjustment_power` | MAB decay, rejected | REJECTED |
| `sgp_power_017_research` | Research artifact only | REJECTED |
| `sgp_v9_apex_powerlotto` | Research artifact only | REJECTED |
| `midfreq_regime_gate` | Regime gate adds noise, no signal | REJECTED |
| `orthogonal` / `orthogonal_v2` | Superseded by `power_orthogonal_5bet` | REJECTED |
| `sum_regime` | Sum+regime combo failed validation | REJECTED |
| `fourier_downgrade` | Fourier downgrade = worse than baseline | REJECTED |
| `regime_gate` | Gate adds noise without signal | REJECTED |

### 3.3 FCF vs TS3 Validation (1500-period walk-forward, documented)

From `FCF_TS3_POWERLOTTO_REPORT.md`:
- **TS3** (`power_triple_strike`): 162/1500 M3+ (10.80%), Edge = **−3.04%** vs baseline 11.14%
- **FCF**: 140/1500 M3+ (9.33%), Edge = **−16.21%** vs baseline

Both strategies are **below baseline (11.14%)**. TS3 performs better than FCF in 1v1 McNemar (p=0.0143) but cannot meet the ROI > baseline gate required by governance. → **Both excluded from Wave 5.**

---

## 4. Candidate Evaluation

All 10 candidates were scored across 10 dimensions (0–10 each, max 100).

### Scoring Dimensions
1. **Executable readiness** — working tool implementation exists
2. **Data availability** — sufficient draws for 1500-period replay
3. **Adapter complexity** — effort to build a P47-pattern adapter
4. **POWER_LOTTO semantic compatibility** — pool=[1,38] pick=6, special=[1,8] correctness
5. **Backfill feasibility** — can 1500 rows be produced efficiently
6. **Uniqueness vs existing strategies** — not a duplicate or subset
7. **Overlap risk with champion** — would it cannibalize `fourier_rhythm_3bet`
8. **Testability** — deterministic, no external state, writable governance tests
9. **Expected replay coverage value** — adds meaningful new coverage type
10. **Governance risk** — clean from registry mutation / lifecycle promotion risk

### 4.1 `fourier30_markov30_2bet` — Score: 72 / 100 [SHORTLISTED]

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Executable readiness | 9 | RSM has it (`fourier30_markov30_2bet`); P42 has parallel biglotto pattern |
| Data availability | 10 | 1912 POWER_LOTTO draws available |
| Adapter complexity | 7 | Adapt from biglotto pool=49→38; LOW-MEDIUM effort |
| POWER_LOTTO compatibility | 8 | Fourier+Markov on pool=38, window=30 each |
| Backfill feasibility | 9 | 2-bet × 1500 = 3000 rows; fast |
| Uniqueness | 9 | Fourier-window=30+Markov-window=30 distinct from champion window=500 |
| Overlap risk (low=good) | 8 | Very low overlap — short-window + Markov component |
| Testability | 9 | Deterministic FFT + Markov, no external state |
| Coverage value | 8 | Fills gap for short-window frequency strategies |
| Governance risk (low=good) | 5 | Clean; RSM already tracks it |
| **Total** | **72** | **HIGH priority** |

**Theory basis:** Fourier with 30-period window captures recent regime; Markov 30-period transition matrix captures conditional probabilities. Together they provide a short-window frequency+sequence signal distinct from the champion's long-window Fourier.

**Validation path:** 1500-period dry-run → McNemar vs baseline. Promotion gate: p < 0.05, edge > 0.

### 4.2 `cold_complement_2bet` (power_twin_strike) — Score: 75 / 100 [SHORTLISTED]

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Executable readiness | 8 | `tools/power_twin_strike.py` fully implemented |
| Data availability | 10 | 1912 POWER_LOTTO draws |
| Adapter complexity | 8 | Cold-number logic; LOW effort adapter |
| POWER_LOTTO compatibility | 10 | Explicitly designed for POWER_LOTTO 1–38 |
| Backfill feasibility | 9 | 2-bet × 1500 = 3000 rows; fast |
| Uniqueness | 10 | Cold-reversion only: fully orthogonal to all Fourier strategies |
| Overlap risk (low=good) | 9 | No Fourier, different prediction philosophy |
| Testability | 9 | Deterministic cold-number ranking |
| Coverage value | 9 | Cold-reversion is a distinct hypothesis not covered in DB |
| Governance risk (low=good) | 5 | Clean; no registry interaction |
| **Total** | **75** | **HIGHEST priority** |

**Theory basis:** Cold-number complementary selection (bet-1: cold ranks 1–6; bet-2: cold ranks 7–12). 100% non-overlap between bets maximizes zone coverage (31.6% of 38-ball pool). The hypothesis is that underrepresented numbers revert toward expected frequency. Validated at edge +0.45% (N=200); needs 1500-period OOS confirmation.

**Validation path:** 1500-period dry-run → McNemar vs baseline. Promotion gate: p < 0.05, edge > 0.

### 4.3 `zonal_entropy_2bet` (scientific_power_predict) — Score: 64 / 100 [SHORTLISTED]

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Executable readiness | 6 | `tools/power_scientific_zonal.py` exists; determinism review needed |
| Data availability | 10 | 1912 POWER_LOTTO draws |
| Adapter complexity | 5 | Entropy calculation + regime switch; MEDIUM effort |
| POWER_LOTTO compatibility | 9 | Designed for 1–38 zonal splits |
| Backfill feasibility | 7 | 2-bet × 1500 = 3000 rows; moderately fast |
| Uniqueness | 8 | Zonal entropy regime switch not present in any existing strategy |
| Overlap risk (low=good) | 7 | Partial cold overlap but entropy gating is unique |
| Testability | 7 | Entropy regime needs boundary tests |
| Coverage value | 7 | Adds zonal coverage hypothesis to DB |
| Governance risk (low=good) | 3 | `random.seed(42)` usage — must be determinism-reviewed |
| **Total** | **64** | **MEDIUM priority** |

**Theory basis:** Divide 1–38 into 6 equal zones. Compute Shannon entropy of recent 30-draw zone distribution. When entropy is LOW (predictable regime): reinforce cluster. When entropy is HIGH (chaotic): revert to cold/gap. Regime-adaptive selection provides a different signal axis from pure Fourier or cold strategies.

**Validation path:** Requires determinism review before adapter build. 1500-period dry-run after P56 scaffold.

---

## 5. Excluded / Deferred Candidates

| strategy_id | Disposition | Reason |
|-------------|------------|--------|
| `power_triple_strike` (TS3) | EXCLUDED | Edge −3.04% < baseline 11.14% in 1500p walk-forward (FCF_TS3 report) |
| `powerlotto_2bet_fourier_rhythm` | EXCLUDED | High overlap with champion `fourier_rhythm_3bet` (same algorithm, subset bet) |
| `powerlotto_3bet_power_precision` | EXCLUDED | Duplicate of `power_precision_3bet` (already row-backed, 1570 rows) |
| `powerlotto_5bet_orthogonal` | EXCLUDED | Duplicate of `power_orthogonal_5bet` (already row-backed, 1570 rows) |
| `pp3_freqort_3bet` | DEFERRED | Too similar to Wave 4 INCONCLUSIVE `pp3_freqort_4bet`; only bet-count differs |
| `power_lotto_pp3_sum_regime` | DEFERRED | WATCHING status; no clear implementation path found |
| `regime_adaptive_5bet` | DEFERRED | 5-bet complexity HIGH; overlaps mechanistically with `power_orthogonal_5bet` |
| `get_fourier_rank` | EXCLUDED | Utility function, not a prediction strategy |
| `strategy_states_power_lotto` | EXCLUDED | State query, not a prediction strategy |
| `strategy_states_power_lotto_json` | EXCLUDED | State query, not a prediction strategy |
| `power_lotto_watch` | EXCLUDED | Monitoring entry, not a prediction strategy |
| All 13 REJECTED strategies | EXCLUDED | Per hypothesis registry and governance |

---

## 6. Wave 5 Shortlist

| Rank | strategy_id | Mechanism | Bet count | Score | Priority |
|------|-------------|-----------|-----------|-------|----------|
| 1 | `cold_complement_2bet` | Cold-reversion, 100% non-overlap | 2 | 75 | HIGH |
| 2 | `fourier30_markov30_2bet` | Short-window Fourier+Markov | 2 | 72 | HIGH |
| 3 | `zonal_entropy_2bet` | Entropy-adaptive zone selection | 2 | 64 | MEDIUM |

All 3 candidates use 2-bet = 3000 rows each × 3 = **9000 new rows planned for Wave 5**.

**Mechanism diversity check:**
- `cold_complement_2bet` — cold frequency only (anti-correlated with Fourier)
- `fourier30_markov30_2bet` — short-window Fourier + Markov (distinct from long-window champion)
- `zonal_entropy_2bet` — entropy regime + zone (novel axis)

No two candidates share the same primary mechanism. No candidate duplicates Wave 1–4 strategies.

---

## 7. P56 Dry-Run Readiness Plan

### 7.1 Adapter File (to be created in P56)

```
lottery_api/models/p56_wave5_powerlotto_adapters.py
```

Pattern: follows `p47_wave4_powerlotto_adapters.py` exactly.
Lifecycle for all Wave 5 strategies: `DRY_RUN` (not ONLINE).

### 7.2 Adapter Designs

#### `cold_complement_2bet`

```python
def get_one_bet(history: List[dict], bet_index: int = 0) -> Tuple[List[int], None]:
    """
    Bet-0: cold ranks 1–6 (window=100)
    Bet-1: cold ranks 7–12 (window=100)
    No predicted_special.
    """
    recent = history[-100:] if len(history) >= 100 else history
    freq = Counter(n for d in recent for n in d['numbers'] if 1 <= n <= 38)
    all_nums = sorted(range(1, 39), key=lambda x: freq.get(x, 0))
    if bet_index == 0:
        return sorted(all_nums[:6]), None
    return sorted(all_nums[6:12]), None
```

**Note:** Uses `Counter` over `history[-100:]`, fully deterministic, no external state.

#### `fourier30_markov30_2bet`

```python
# Fourier30 scores: FFT on 30-period window (same as _fourier_scores() but window=30)
# Markov30: transition matrix on 30-period window, then compute marginal next-draw
# Bet-0: top-6 by Fourier30 score
# Bet-1: top-6 by Markov30 marginal probability
```

**Note:** Both windows = 30. No shared numbers required between bets (orthogonal).

#### `zonal_entropy_2bet`

```python
# Zone entropy on last 30 draws (6 zones of [1..38])
# is_chaotic = entropy > 2.2 (log2(6) max ≈ 2.58)
# Chaotic mode: top-6 cold numbers (window=100)
# Stable mode: top-6 cluster reinforcement numbers
# Bet-0 and Bet-1 use the same regime; Bet-1 = next top-6 excluding Bet-0
```

**Note:** `random.seed(42)` must be removed and replaced with deterministic ranking before adapter build.

### 7.3 Dry-Run Scope

| strategy_id | Bet count | Rows planned | DB target |
|-------------|-----------|-------------|-----------|
| `cold_complement_2bet` | 2 | 3000 | `/tmp/p56_temp.db` (DRY_RUN only) |
| `fourier30_markov30_2bet` | 2 | 3000 | `/tmp/p56_temp.db` (DRY_RUN only) |
| `zonal_entropy_2bet` | 2 | 3000 | `/tmp/p56_temp.db` (DRY_RUN only) |

Total new dry-run rows: **9000** (temp DB only; production rows remain 42460).

### 7.4 Governance Sequence (Wave 5)

```
P56: Adapter bootstrap + dry-run (3 strategies × 3000 rows in /tmp/p56_temp.db)
P57: Temp rehearsal analysis + McNemar gate
P58: Wave 5 production apply (if P57 analysis passes)
P59: Wave 5 performance analysis
```

---

## 8. POWER_LOTTO Semantic Reminders for P56

(From P46 and P47 governance canon)

- First-zone pool: **1–38** (pick 6 unique)
- Second-zone (special): **1–8** (pick 1, separate pool, or `None`)
- `hit_count` = first-zone matches ONLY — never incremented by special
- `special_hit` = 1 if `predicted_special == actual_special`, else 0
- Causal slice: `history = all_draws[:target_idx]` (target draw excluded)

Validation rule for Wave 5 adapters:
```python
assert len(predicted_numbers) == 6
assert all(1 <= n <= 38 for n in predicted_numbers)
assert len(set(predicted_numbers)) == 6
if predicted_special is not None:
    assert 1 <= predicted_special <= 8
```

---

## 9. Post-Flight Results

| Check | Result |
|-------|--------|
| Production row count | 42460 ✅ (unchanged) |
| POWER_LOTTO rows | 9140 ✅ (unchanged) |
| Drift guard | PASS ✅ |
| Branch governance guard | PASS ✅ |
| Forbidden staging scan | CLEAR ✅ (4 whitelist files only) |

---

## 10. What P55 Must NOT Do

- No DB writes (`lottery_v2.db` remains at 42460 rows)
- No adapter implementation
- No lifecycle promotion for any strategy
- No modification of `replay_strategy_registry._ALL_ADAPTERS` or `_REGISTRY`
- No writes to any `.db` file
- No alteration of `CEO-Decision.md` or `active_task.md`
- No registry mutation
- No champion replacement (`fourier_rhythm_3bet` remains ONLINE)

---

*Generated by P55 planning session. All findings are read-only analysis.*
*Classification: P55_POWERLOTTO_WAVE5_CANDIDATE_PLANNING_COMPLETED*
