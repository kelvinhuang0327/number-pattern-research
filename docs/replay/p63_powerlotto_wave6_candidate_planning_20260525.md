# P63 POWER_LOTTO Wave 6 Candidate Planning

**Date:** 2026-05-25
**Branch:** p63-powerlotto-wave6-candidate-planning
**Classification:** P63_POWERLOTTO_WAVE6_CANDIDATE_PLANNING_COMPLETED
**Production rows (DB):** 43960 (unchanged — no DB writes in this task)
**POWER_LOTTO rows in DB:** 10640 (7 strategies, 10570–1500 rows each)

---

## 1. Scope and Governance

P63 is a **read-only planning task**. Its purpose is to:

1. Confirm P62 closure (HTTP API verification pass, commit `57f9ec3` on main).
2. Inventory the current POWER_LOTTO replay coverage (what is already row-backed).
3. Identify Wave 6 candidates from Wave 5 WATCHLIST holdouts and novel strategy tools.
4. Score each candidate across 10 governance dimensions.
5. Select a final Wave 6 shortlist (3 candidates) for P64 adapter bootstrap / dry-run rehearsal.
6. List reviewed-but-excluded candidates with reasons.

**No adapter code is written. No dry-run rows are generated. No DB writes occur.**

---

## 2. P62 Closure Confirmation

| Check | Result |
|-------|--------|
| Commit `57f9ec3` on main | ✅ CONFIRMED |
| Branch `p62-post-p59-http-api-verification-closure` ff-merged | ✅ CONFIRMED |
| `unified_predictor.py` torch optional-dep guard | ✅ CONFIRMED |
| HTTP `/api/replay/summary` fourier30_markov30_2bet total_rows=1500 | ✅ CONFIRMED |
| HTTP `/api/replay/history` 1500 rows PREDICTED | ✅ CONFIRMED |
| HTTP `/api/replay/strategies` lifecycle catalog | ✅ CONFIRMED |
| WATCHLIST not applied: cold_complement_2bet=0 rows, zonal_entropy_2bet=0 rows | ✅ CONFIRMED |
| Production rows: 43960 | ✅ CONFIRMED |
| P59 rows: 1500 | ✅ CONFIRMED |
| Tests: 174/174 PASS | ✅ CONFIRMED |
| Drift guard: PASS | ✅ CONFIRMED |
| No DB write, no ONLINE promotion, no champion replacement | ✅ CONFIRMED |

---

## 3. Current POWER_LOTTO Replay Coverage

### 3.1 Pre-Wave 4 (legacy row-backed, lifecycle registered ONLINE)

| strategy_id | Lifecycle status | Rows | avg_hit | hit3plus | Draw range |
|-------------|-----------------|------|---------|----------|------------|
| `fourier_rhythm_3bet` | **ONLINE (champion)** | 1500 | 0.993 | 74 | history |
| `power_orthogonal_5bet` | ONLINE | 1570 | 0.992 | 77 | history |
| `power_precision_3bet` | ONLINE | 1570 | 0.992 | 77 | history |

Subtotal: **4640 rows**

### 3.2 Wave 4 (P48 production apply — not lifecycle registered as ONLINE)

| strategy_id | P51/P52 classification | Rows | avg_hit | hit3plus |
|-------------|----------------------|------|---------|----------|
| `midfreq_fourier_mk_3bet` | WATCHLIST (G4 waiver, 500-draw OOS gate) | 1500 | 1.027 | 66 |
| `midfreq_fourier_2bet` | INCONCLUSIVE (p=0.073 > 0.05) | 1500 | 0.973 | 70 |
| `pp3_freqort_4bet` | INCONCLUSIVE (RSM edge −0.68%, below baseline) | 1500 | 1.002 | 81 |

Subtotal: **4500 rows**

### 3.3 Wave 5 (P59 controlled production apply)

| strategy_id | P57/P58 classification | Rows | avg_hit | hit3plus | CAID |
|-------------|----------------------|------|---------|----------|------|
| `fourier30_markov30_2bet` | **PRODUCTION APPLY** (P59) | 1500 | 0.964 | 61 | P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525 |

Wave 5 WATCHLIST (adapters built, NOT yet row-backed):

| strategy_id | P57 classification | Rows | P57 dry-run M3+ | Baseline |
|-------------|-------------------|------|-----------------|----------|
| `cold_complement_2bet` | `WATCHLIST_REHEARSAL_ONLY` | 0 | 3.67% | 3.87% |
| `zonal_entropy_2bet` | `WATCHLIST_REHEARSAL_ONLY` | 0 | 3.67% | 3.87% |

WATCHLIST reason: M3+/draw 3.67% < baseline 3.87% (−0.20pp), McNemar p=0.656 (not significant). Both held out from P59 controlled apply.

Wave 5 subtotal: **1500 rows**

**Total POWER_LOTTO rows in DB: 10640**
**Total lifecycle-registered POWER_LOTTO strategies: 5**
(power_precision_3bet ONLINE, power_orthogonal_5bet ONLINE, fourier_rhythm_3bet ONLINE, power_shlc_midfreq REJECTED, h6_gate_mk20_ew85 OBSERVATION)

---

## 4. Candidate Universe Inventory

### 4.1 Sources Inspected

| Source | Finding |
|--------|---------|
| `lottery_api/models/p56_wave5_powerlotto_adapters.py` | 3 Wave 5 adapters: cold_complement_2bet, fourier30_markov30_2bet, zonal_entropy_2bet |
| `lottery_api/models/p47_wave4_powerlotto_adapters.py` | 3 Wave 4 adapters: pp3_freqort_4bet, midfreq_fourier_mk_3bet, midfreq_fourier_2bet |
| `lottery_api/models/replay_strategy_registry.py` | lifecycle POWER_LOTTO: 5 entries incl. h6_gate_mk20_ew85 OBSERVATION (no predict method) |
| `lottery_api/models/lag_reversion.py` | `LagReversionPredictor` class, 100 lines, deterministic, no torch |
| `tools/power_twin_strike.py` | cold_complement_2bet source (N=200, edge +0.45%) |
| `tools/power_scientific_zonal.py` | zonal_entropy_2bet source (zonal dispersion optimizer) |
| `tools/power_lag_reversion.py` | Lag reversion: median interval / overdue ratio scoring |
| `tools/power_graph_synergy.py` | Graph co-occurrence + Louvain community detection |
| `tools/power_wavelet_mra.py` | Wavelet MRA (CWT via pywt) |
| `tools/power_precision_2bet.py` | UnifiedPredictionEngine-based (torch dep risk) |
| `FCF_TS3_POWERLOTTO_REPORT.md` | TS3 edge −3.04%, FCF edge −16.21% — both below baseline |
| Hypothesis registry | 13+ REJECTED POWER_LOTTO strategies documented |
| `docs/replay/p55_powerlotto_wave5_candidate_planning_20260525.md` | Wave 5 planning reference |
| `docs/replay/p57_powerlotto_wave5_controlled_rehearsal_readiness_20260525.md` | Wave 5 dry-run scores, WATCHLIST classification |
| `00-Plan/roadmap/roadmap.md` | P61-D: Wave 6 candidate planning placeholder |

### 4.2 Candidate Identification

From the universe inspection, **4 new candidates** were identified for evaluation:

| Candidate | Source | Mechanism | Prior evaluation |
|-----------|--------|-----------|-----------------|
| `cold_complement_2bet` | Wave 5 WATCHLIST | Cold-reversion complementary selection | P55 scored 75, P57 rehearsed, WATCHLIST_REHEARSAL_ONLY |
| `zonal_entropy_2bet` | Wave 5 WATCHLIST | Zonal entropy regime switch | P55 scored 64, P57 rehearsed, WATCHLIST_REHEARSAL_ONLY |
| `lag_reversion_2bet` | `tools/power_lag_reversion.py` + `models/lag_reversion.py` | Median interval overdue ranking | Never evaluated for POWER_LOTTO replay |
| `cooccurrence_graph_2bet` | `tools/power_graph_synergy.py` | Graph community detection | Never evaluated for replay |

Plus 2 dependency-blocked candidates: wavelet MRA (pywt), precision_2bet (torch dep).

---

## 5. Candidate Scoring

### Scoring Dimensions (0–10 each, max 100)

1. **Executable readiness** — working implementation and adapter available
2. **Data availability** — sufficient draws for 1500-period replay
3. **Adapter complexity** — effort to build/reuse P56-pattern adapter
4. **POWER_LOTTO semantic compatibility** — pool=[1,38] pick=6, special=[1,8] correctness
5. **Evidence quality** — formal backtest / OOS validation evidence
6. **Uniqueness vs existing strategies** — not a duplicate or subset
7. **Overlap risk with champion** — would it cannibalize `fourier_rhythm_3bet` (low=good)
8. **Testability** — deterministic, no external state, writable governance tests
9. **Expected replay coverage value** — adds meaningful new hypothesis
10. **Governance risk** — clean from registry mutation / lifecycle promotion risk (low=good)

---

### 5.1 `cold_complement_2bet` — Score: 82 / 100

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Executable readiness | 10 | Adapter already built in `p56_wave5_powerlotto_adapters.py`; source in `tools/power_twin_strike.py` |
| Data availability | 10 | 14,000+ POWER_LOTTO draws available |
| Adapter complexity | 10 | Zero adapter work for P64 — adapter already exists and was tested in P56/P57 |
| POWER_LOTTO compatibility | 10 | pool=38, pick=6 — explicitly designed for POWER_LOTTO |
| Evidence quality | 7 | N=200 tool validation edge +0.45%; P57 1500-period dry-run M3+=3.67% (−0.20pp vs 3.87% baseline); small negative edge within noise band (SE≈0.5pp) |
| Uniqueness | 10 | Pure cold-reversion: fully orthogonal to all Fourier/Markov strategies |
| Overlap risk (low=good) | 10 | No Fourier component; different prediction philosophy |
| Testability | 9 | Deterministic cold-number ranking; no external state |
| Coverage value | 9 | Cold-reversion hypothesis not currently represented in DB for POWER_LOTTO |
| Governance risk (low=good) | 7 | Clean; P56 adapter registered as DRY_RUN only; no registry mutation |
| **Total** | **92** | **HIGHEST priority** |

**Theory basis (Score: 92/100):** Cold-number complementary selection — bet-0: cold ranks 1–6 (frequency[1..38] over last 100 draws, ascending); bet-1: cold ranks 7–12. 100% non-overlap between bets maximizes zone coverage (31.6% of 38-ball pool). Hypothesis: underrepresented numbers revert toward expected frequency over longer observation windows.

**P57 dry-run result:** M3+/draw = 3.67% vs baseline 3.87% (−0.20pp). McNemar p=0.656 (not significant). The −0.20pp gap is within 1 standard error (SE≈0.50pp at N=1500, 2-bet). A 1500-draw additional OOS window in Wave 6 would directly resolve this signal question.

**Wave 6 rationale:** The WATCHLIST classification was correct at Wave 5 — a borderline result (-0.20pp within noise) does not justify production apply. Wave 6 gives cold_complement_2bet a second independent 1500-draw OOS window under new draws (different draw range from P57 dry-run). This follows standard governance: re-evaluate after accumulating more OOS evidence.

**P64 required work:**
- Reuse `ColdComplement2BetAdapter` from `lottery_api/models/p56_wave5_powerlotto_adapters.py`
- No code changes needed
- P64 scope: temp-DB dry-run rehearsal (1500 new draws) → McNemar test → P64 report

---

### 5.2 `zonal_entropy_2bet` — Score: 70 / 100

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Executable readiness | 8 | Adapter built in `p56_wave5_powerlotto_adapters.py`; determinism concern must be resolved |
| Data availability | 10 | 14,000+ draws available |
| Adapter complexity | 7 | Adapter exists; needs determinism review (remove or neutralize `random.seed(42)` usage) |
| POWER_LOTTO compatibility | 9 | Zonal splits for pool=38; entropy over 6 zones (verified in P56) |
| Evidence quality | 6 | P57 1500-period dry-run M3+=3.67% (−0.20pp vs baseline); source tool lacks formal backtest |
| Uniqueness | 8 | Entropy regime switch axis not present in any existing strategy |
| Overlap risk (low=good) | 8 | Partial cold-score overlap with cold_complement; entropy gating is unique |
| Testability | 7 | Entropy computation deterministic once seed removed; boundary tests needed |
| Coverage value | 8 | Regime-adaptive zonal coverage adds novel signal axis |
| Governance risk (low=good) | 7 | Clean after determinism fix |
| **Total** | **78** | **MEDIUM priority** |

**Theory basis:** Divide 1–38 into 6 equal zones. Compute Shannon entropy of recent 30-draw zone distribution. LOW entropy (predictable regime) → reinforce dominant zone cluster. HIGH entropy (chaotic regime) → revert to cold/gap selection. Regime-adaptive selection provides a different signal axis from pure Fourier or cold strategies.

**P57 dry-run result:** Same M3+/draw as cold_complement (3.67% vs 3.87%, −0.20pp). Both borderline results that warrant re-evaluation with new draws.

**Determinism concern (P55 flagged):** `random.seed(42)` in `ZonalEntropy2BetAdapter` must be removed or confirmed non-impactful before P64 adapter validation. Shannon entropy calculation is inherently deterministic given fixed history; the seed is likely vestigial from prototype code.

**P64 required work:**
1. Review and remove `random.seed(42)` from `ZonalEntropy2BetAdapter` (5 min fix)
2. Run determinism validation test (call adapter twice on same history → verify identical output)
3. 1500-draw temp-DB dry-run rehearsal → McNemar test → P64 report

---

### 5.3 `lag_reversion_2bet` — Score: 60 / 100

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Executable readiness | 6 | `tools/power_lag_reversion.py` + `models/lag_reversion.py` exist; no replay adapter yet |
| Data availability | 10 | 14,000+ draws available |
| Adapter complexity | 6 | Adapter must be built from scratch following P56 pattern; LOW-MEDIUM effort |
| POWER_LOTTO compatibility | 9 | `tools/power_lag_reversion.py` hardcodes pool=38, pick=6 correctly |
| Evidence quality | 4 | No formal 1500-period POWER_LOTTO backtest found; tool is research-only |
| Uniqueness | 10 | Median interval / overdue ratio: completely orthogonal to all 7 existing strategies |
| Overlap risk (low=good) | 10 | No Fourier, no cold-frequency, no Markov — pure temporal reversion signal |
| Testability | 8 | Deterministic NumPy computation; predict() method exists in `models/lag_reversion.py` |
| Coverage value | 10 | Fills completely unexplored temporal-reversion hypothesis space |
| Governance risk (low=good) | 7 | Clean; no existing registry entry; adapter would be DRY_RUN only |
| **Total** | **80** | **LOWER-MEDIUM priority — requires mini-backtest before P64** |

**Theory basis:** For each ball 1–38, compute median interval between appearances over last 500 draws. Compute current lag (draws since last appearance). Score = current_lag / median_interval. Higher score = number is overdue relative to its own historical rhythm. Select top 6 (bet-0) and next top 6 (bet-1). 100% non-overlap between bets.

**Mechanism distinction:** Unlike cold-frequency which uses raw count, lag_reversion uses each number's individual historical rhythm. A number that appears infrequently but is currently at double its median interval scores higher than a number that appears more often but is only slightly past its median.

**P64 required work:**
1. Mini-backtest: run `tools/power_lag_reversion.py` over last 150/500/1500 draws → collect M3+/draw hit rate
2. If evidence positive (M3+/draw ≥ baseline 3.87%): build replay adapter following P56 pattern
3. If evidence negative: defer to P65+ or mark REJECTED
4. Adapter build: ~2 hours following `ColdComplement2BetAdapter` as template

**Note:** Because evidence quality is LOW (no prior formal OOS backtest), P64 should run the mini-backtest **before** building the adapter. This is a departure from the Wave 5 pattern where adapters were built first.

---

## 6. Non-Selected Candidates

| Candidate | Disposition | Reason |
|-----------|------------|--------|
| `h6_gate_mk20_ew85` | DEFERRED (P65+) | OBSERVATION stub in lifecycle registry; v0.0; no `predict()` method implemented; `min_history=0` indicates placeholder; not production-grade |
| `cooccurrence_graph_2bet` | DEFERRED (P65+) | Requires `python-louvain` dep (not in venv); Louvain community detection is non-deterministic (random seed required) — fails governance determinism requirement |
| `power_wavelet_mra` | DEFERRED (P65+) | Requires `pywt` (PyWavelets) — not in venv; wavelet dep risk; determinism acceptable but dep install needed |
| `power_precision_2bet` | EXCLUDED | Uses `UnifiedPredictionEngine` which imports torch-dependent modules; fails dependency guard even with P62 fix |
| `midfreq_fourier_mk_3bet` (re-eval) | EXCLUDED | Already row-backed (1500 rows, Wave 4, WATCHLIST in docs); re-evaluation would be monitoring, not new rows |
| `midfreq_fourier_2bet` (re-eval) | EXCLUDED | Already row-backed (1500 rows, Wave 4, INCONCLUSIVE); monitoring-only |
| `pp3_freqort_4bet` (re-eval) | EXCLUDED | Already row-backed (1500 rows, Wave 4, INCONCLUSIVE); monitoring-only |
| `fourier30_markov30_2bet` (re-eval) | EXCLUDED | Already row-backed via P59 (1500 rows, Wave 5, avg_hit=0.964); monitoring-only |
| `power_triple_strike` (TS3) | EXCLUDED | Edge −3.04% < baseline 11.14% (actually POWER_LOTTO: baseline 3.87% M3+); documented in FCF_TS3_POWERLOTTO_REPORT.md; too far below baseline |
| `power_fcf` | EXCLUDED | Edge −16.21% vs baseline; documented in FCF_TS3_POWERLOTTO_REPORT.md |
| `shlc_midfreq_power` | EXCLUDED | REJECTED in lifecycle registry; edge −2.92% documented |
| `regime_adaptive_5bet` | DEFERRED | High complexity (5-bet); mechanistically overlaps with `power_orthogonal_5bet`; no clear edge evidence |
| All 13 hypothesis-registry REJECTED strategies | EXCLUDED | Per governance: rejected strategies may only be re-evaluated if test conditions change |

---

## 7. Wave 6 Shortlist

| Rank | strategy_id | Mechanism | Bets | Score | Status | Adapter |
|------|-------------|-----------|------|-------|--------|---------|
| 1 | `cold_complement_2bet` | Cold-reversion, 100% non-overlap | 2 | 92 | WATCHLIST_REHEARSAL_ONLY → Wave 6 priority | EXISTS (`p56_wave5_powerlotto_adapters.py`) |
| 2 | `lag_reversion_2bet` | Median interval overdue ranking | 2 | 80 | NEW → mini-backtest required before adapter build | DOES NOT EXIST |
| 3 | `zonal_entropy_2bet` | Entropy-adaptive zone selection | 2 | 78 | WATCHLIST_REHEARSAL_ONLY → Wave 6 after determinism fix | EXISTS (needs seed review) |

**Mechanism diversity check (Wave 6 + existing production strategies):**
- `fourier_rhythm_3bet` (ONLINE champion): long-window Fourier frequency
- `fourier30_markov30_2bet` (P59 apply): short-window Fourier+Markov
- `cold_complement_2bet` (Wave 6 C1): cold frequency, 100% non-overlap
- `zonal_entropy_2bet` (Wave 6 C2): entropy regime × zone
- `lag_reversion_2bet` (Wave 6 C3): per-ball median interval reversion

No two strategies share the same primary mechanism. No candidate duplicates Wave 1–5 strategies.

**Expected rows if Wave 6 full apply (1500 draws per candidate, 2 bets):**
- `cold_complement_2bet`: 3000 rows
- `zonal_entropy_2bet`: 3000 rows
- `lag_reversion_2bet`: 3000 rows (if evidence positive)
- **Total Wave 6 max**: 9000 new rows → DB total would be 52960

---

## 8. Sequencing Recommendation for P64

### Option A: Full Wave 6 (recommended)

**P64a:** `cold_complement_2bet` dry-run rehearsal
- Reuse existing `ColdComplement2BetAdapter` from P56
- Run 1500-draw temp-DB dry-run (new draw range)
- McNemar vs baseline → classify PASS/WATCHLIST/FAIL

**P64b:** `zonal_entropy_2bet` determinism review + dry-run
- Remove `random.seed(42)` if present in `ZonalEntropy2BetAdapter`
- Determinism test (dual-call validation)
- Run 1500-draw temp-DB dry-run (new draw range)
- McNemar vs baseline → classify

**P64c:** `lag_reversion_2bet` mini-backtest + (conditional) adapter build
- Run `tools/power_lag_reversion.py` over 150/500/1500 draw windows
- If M3+/draw ≥ 3.87% (baseline) in any window: build adapter
- If consistently below: defer to P65 or mark REJECTED

**Then P65:** Controlled rehearsal readiness gate (mirror P57 pattern for Wave 6)
**Then P66:** Controlled apply proposal (mirror P58 pattern)
**Then P67:** Controlled production apply for Wave 6 top candidate(s)

### Option B: Partial Wave 6 (if P64 resources are limited)

- P64: cold_complement_2bet only (highest readiness, zero adapter work)
- Defer zonal_entropy_2bet and lag_reversion_2bet to P65

### Governance constraint (mandatory for P64):
- Only one of the two WATCHLIST candidates may advance to production apply per wave
- `lag_reversion_2bet` requires positive mini-backtest evidence before any adapter build
- No production apply may happen in P64 (plan/adapter/dry-run only)
- Production rows must remain 43960 throughout P64

---

## 9. P63 Pre-flight / Post-flight Results

### Pre-flight

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| Repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` | ✅ |
| Branch (pre) | `main` | `main` | ✅ |
| HEAD | `57f9ec3` | `57f9ec3` | ✅ |
| Total rows | 43960 | 43960 | ✅ |
| P59 rows | 1500 | 1500 | ✅ |
| Drift guard | PASS | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS | ✅ |
| Branch governance guard | PASS | BRANCH_GOVERNANCE_PASS | ✅ |

### Post-implementation

| Check | Expected | Status |
|-------|----------|--------|
| Branch | `p63-powerlotto-wave6-candidate-planning` | ✅ |
| Total rows | 43960 | ✅ |
| P59 rows | 1500 | ✅ |
| Drift guard | PASS | ✅ |
| No DB write | ✅ | ✅ |
| No ONLINE promotion | ✅ | ✅ |
| No champion replacement | ✅ | ✅ |
| No registry mutation | ✅ | ✅ |

---

## 10. Governance Summary

| Constraint | Status |
|-----------|--------|
| No DB write | ✅ CONFIRMED |
| No ONLINE promotion | ✅ CONFIRMED |
| No champion replacement | ✅ CONFIRMED |
| No registry mutation | ✅ CONFIRMED |
| No production apply | ✅ CONFIRMED |
| No force push | ✅ CONFIRMED |
| Whitelist-only staging | ✅ CONFIRMED |
| Production rows unchanged (43960) | ✅ CONFIRMED |
| P59 rows unchanged (1500) | ✅ CONFIRMED |

---

## Appendix A: POWER_LOTTO Baseline Reference

| Metric | Value | Source |
|--------|-------|--------|
| Pool | 1–38, pick 6 | canonical spec |
| Special pool | 1–8, pick 1 | canonical spec |
| Theoretical M3+ rate per bet (6C3 × 32C3 / 38C6) | ~3.87% | P57 doc |
| Expected hit_count per draw (2-bet, M3+ baseline) | 0.0774 | derived |
| POWER_LOTTO draws available | ~14,000+ | DB |

---

**Classification: P63_POWERLOTTO_WAVE6_CANDIDATE_PLANNING_COMPLETED**
**Marker: P63_POWERLOTTO_WAVE6_CANDIDATE_PLANNING_20260525**
