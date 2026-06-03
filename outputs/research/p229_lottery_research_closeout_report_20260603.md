# P229 — Lottery Research Closeout Report: P211A–P228

**Date:** 2026-06-03 Asia/Taipei
**Task:** `P229_LOTTERY_RESEARCH_CLOSEOUT_REPORT_COMPLETE`
**Status:** COMPLETE / REPORT-ONLY
**Authorized by:** User explicit task prompt 2026-06-03

This report summarises the P211A–P228 research chain. It contains no new research, no new scans, no DB writes, no strategy promotions, and no betting advice. Historical replay and dry-run evidence only.

---

## 1. Executive Summary

| Item | Status |
|---|---|
| Deployable strategy found | **NO** |
| Production change authorized | **NO** |
| Current state | **Research closeout — not promotion** |
| Main surviving line | `midfreq_fourier_2bet / DAILY_539` → **WAIT_FOR_OOS** |
| Star lottery line | **UNDERPOWERED_NO_SIGNAL** / straight-play **BLOCKED** |
| POWER_LOTTO second-zone | **DISPLAY_ONLY / NULL_EDGE** |
| P225 model design | **DEFERRED** |

The entire P211A–P228 research chain — spanning POWER_LOTTO second-zone, cross-lottery feature discovery (three main lotteries), DAILY_539 survivor validation, and 3_STAR/4_STAR box-play dry-run — returned no confirmed deployable signal. The closest result is `midfreq_fourier_2bet / DAILY_539` which needs ≥300–500 new draws for a meaningful re-evaluation. No action is authorized without separate explicit authorization.

---

## 2. Research Chain Timeline

| Phase | Date | Description | PR / Evidence | Final Classification |
|---|---|---|---|---|
| P211A | 2026-06-03 | POWER_LOTTO second-zone bias-reduction read-only diagnostic | PR #255 | `NO_SIGNAL` / display-only confirmed |
| P221F | 2026-06-03 | Cross-lottery feature-discovery protocol frozen | PR #256 | `PROTOCOL_FROZEN` |
| P222 | 2026-06-03 | Cross-lottery feature-discovery scan (35 strategies × 3 lotteries) | PR #257 | `CANDIDATES_FOUND_NEED_MORE_OOS` |
| P223B | 2026-06-03 | Candidate OOS cross-year validation (5 candidates) | PR #258 | `P223B_CANDIDATE_OOS_VALIDATION_COMPLETE` |
| P224 | 2026-06-03 | DAILY_539 survivor deeper validation (clean dedup slice) | PR #259 | `P224_SURVIVOR_NEEDS_MORE_OOS` |
| P224B/C | 2026-06-03 | Future OOS monitoring protocol frozen | PR #260 | `P224B_FUTURE_OOS_MONITORING_PROTOCOL_READY` |
| P225 | 2026-06-03 | Governance closeout sync P211A–P224C | PR #261, #262 | `P225_GOVERNANCE_CLOSEOUT_SYNC_COMPLETE` |
| P226 | 2026-06-03 | 3_STAR / 4_STAR replay-gap discovery | PR #263 | `P226_STAR_REPLAY_GAP_DISCOVERY_COMPLETE` |
| P227A | 2026-06-03 | Star box-play adapter design (plan-only) | PR #263 | `P227A_STAR_BOX_PLAY_ADAPTER_DESIGN_READY` |
| P227B | 2026-06-03 | Star box-play code-only dry-run implementation | PR #264 | `P227B_STAR_BOX_PLAY_DRYRUN_CODE_COMPLETE` |
| P227C | 2026-06-03 | Star box-play dry-run scan (120 hypotheses) | PR #265 | `P227C_STAR_BOX_PLAY_UNDERPOWERED_NO_SIGNAL` |
| P228 | 2026-06-03 | Governance closeout sync P226–P227C | PR #266 | `P228_STAR_REPLAY_GOVERNANCE_CLOSEOUT_COMPLETE` |
| **P229** | **2026-06-03** | **This closeout report** | **—** | `P229_LOTTERY_RESEARCH_CLOSEOUT_REPORT_COMPLETE` |

---

## 3. Per-Direction Conclusions

### Direction A — POWER_LOTTO Second-Zone

**Task:** P211A read-only diagnostic
**Question:** Is there a hit-rate edge in POWER_LOTTO second-zone (special ball 1–8) that can be exploited after removing known structural bias?

**Evidence:**
- All Bonferroni-corrected p-values > 0.04 across bias-reduction schemes tested.
- Structural bias exists (certain balls appear more in specific draw-count buckets) but this does not translate to a predictive edge.
- Hit-rate edge is NULL after bias correction.

**Conclusion:** `DISPLAY_ONLY_CONFIRMED`. Second-zone data may be shown as informational context but must not influence scoring, betting, or recommendation logic. Do not promote. This conclusion is final unless future pre-registered evidence clearly beats the random baseline with corrected significance.

---

### Direction B — Cross-Lottery Feature Discovery (P221F / P222 / P223B)

**Task:** Systematic multi-lottery, multi-feature, multi-window scan
**Question:** Are there corrected-significant OOS edge signals across BIG_LOTTO, DAILY_539, POWER_LOTTO using frozen pre-registered windows and feature families?

**P221F protocol:**
- Windows frozen: short 100/125/150, mid 500/750/1000, all-history = reference only.
- Universe: BIG_LOTTO, DAILY_539, POWER_LOTTO (3_STAR / 4_STAR were draw-only at this stage, no replay rows).
- Baselines pre-declared. Walk-forward OOS required. Bonferroni / BH-FDR applied.

**P222 scan results (35 strategies × 14 bet-index × 3 lotteries):**
- BIG_LOTTO: row-level mean ≈ random baseline. Zero corrected-significant candidates.
- DAILY_539: `midfreq_fourier_2bet` showed raw p=5.2e-35 (inflated by overlapping/duplicated slice).
- POWER_LOTTO: `midfreq_fourier_mk_3bet` showed BH-FDR pass but not Bonferroni.

**P223B (OOS cross-year validation, 5 candidates):**
- `midfreq_fourier_2bet / DAILY_539`: classified `CROSS_YEAR_CONFIRMED` on the P222 (overlapping) slice.
- Others: `CANDIDATE_NEEDS_MORE_OOS` / `WEAK_OBSERVATION_ONLY` / `REJECTED_NO_OOS_EDGE`.

**Conclusion:** `CANDIDATES_FOUND_NEED_MORE_OOS`. The P222 scan used an overlapping slice that inflated significance for `midfreq_fourier_2bet`. P224 corrected for this.

---

### Direction C — DAILY_539 Survivor (`midfreq_fourier_2bet`)

**Task:** P224 clean-slice deeper validation
**Question:** Does `midfreq_fourier_2bet / DAILY_539` hold up under clean deduplicated OOS?

**P224 findings (clean slice: 1,500 rows = 1,500 distinct draws, bet_index=1):**

| Metric | Value | Status |
|---|---|---|
| Mean hit_count | 0.6693 | — |
| Baseline (random) | 0.6410 | — |
| One-sided p-value | **0.0674** | **Fails 0.05** |
| 95% CI | [0.632, 0.706] | **Crosses baseline** |
| Block stability | 6/10 above baseline | Weak |
| Hit=3 sensitivity | Excluding 19 hit=3 rows → mean drops **below** baseline | Fragile |

**Key concern:** The entire nominal edge rests on 19 draws where `hit_count=3` (≈1.3% of the slice). This is consistent with random noise, not a reproducible signal.

**P224B future OOS monitoring protocol:**
- Reopen gate: ≥300 new DAILY_539 target draws (preferred ≥500).
- Must pass: mean > baseline, CI lower bound ≥ baseline (or pre-declared threshold), corrected p-value, block stability (majority above baseline), robustness (hit=3 removal does not drop below baseline), comparison vs `daily539_f4cold` and consensus baseline.
- Failure → classify as historical artifact, not promotable.

**Conclusion:** `WAIT_FOR_OOS`. Honest prior: lean NULL. Do not deploy, do not promote, do not change recommendation logic. P225 model design deferred — there is no validated signal to design a model around.

---

### Direction D — 3_STAR / 4_STAR Star Lottery

**Task:** P226 discovery → P227A design → P227B code → P227C scan

**Draw availability:**
- 3_STAR: 4,179 draws (2007–2026), pool digits 0–9, pick 3.
- 4_STAR: 2,922 draws (2007–2026), pool digits 0–9, pick 4.
- Replay rows: **0** for both (confirmed, all aliases).

**Critical DB limitation:**
- All draws stored as sorted JSON arrays (100% sorted, 0 repeated-digit draws observed).
- `isPermutation: true` in `lottery_types.json` — but positional order is **lost** at ingest.
- **Straight-play validation is BLOCKED** until re-ingestion from a raw positional source with separate authorization.

**Box-play implementation (P227B):**
- `star_box_exact_match(predicted, actual)` → multiset Counter comparison (not set intersection).
- `calculate_match_score` prohibited (set intersection would be wrong for repeated digits).
- `dry_run=1` always enforced.
- **42/42 targeted tests PASS.**

**P227C scan (box-play, 120 hypotheses):**

| Lottery | n_draws | Bonferroni pass | BH-FDR pass | Best lift | Best feature | Power status |
|---|---|---|---|---|---|---|
| 3_STAR | 4,179 | **0** | 1 (F7_high_low/w750, p=0.0008) | +0.00650 | high/low composition | **UNDERPOWERED** (n_OOS=2,090 < 10,000) |
| 4_STAR | 2,922 | **0** | **0** | +0.00345 | F7_high_low/w100 | **UNDERPOWERED** |

**Statistical power requirement:**
- 3_STAR: ~10,000 draws needed for 80% power to detect 20% relative lift at α=0.05 (has 4,179).
- 4_STAR: ~17,000 draws needed (has 2,922).

**Conclusion:** `UNDERPOWERED_NO_SIGNAL`. 3_STAR F7_high_low/w750 is a weak observation only — it is classified `WEAK_OBSERVATION_UNDERPOWERED`, not a deployable signal. Future action (if any) requires ~2.5× more 3_STAR draws or positional re-ingestion for straight-play.

---

## 4. Candidate Status Table

| Candidate | Lottery | Classification | Evidence | Future Gate |
|---|---|---|---|---|
| Second-zone hit-rate edge | POWER_LOTTO | **DISPLAY_ONLY / NULL_EDGE** | P211A: all corrected p > 0.04 | None — final unless new pre-registered proof |
| `midfreq_fourier_2bet` | DAILY_539 | **WAIT_FOR_OOS** | P224: p=0.0674 (fails 0.05), CI crosses baseline, edge rests on 19 rows | ≥300 new draws (preferred 500); full P224B gate |
| P225 model design | DAILY_539 | **DEFERRED** | No validated signal to design around | Requires validated survivor first |
| Box-play edge | 3_STAR | **UNDERPOWERED_NO_SIGNAL** | P227C: 0 Bonferroni; 1 BH-FDR weak obs (UNDERPOWERED) | ≥10,000 total draws or positional re-ingestion |
| Box-play edge | 4_STAR | **UNDERPOWERED_NO_SIGNAL** | P227C: 0 Bonferroni, 0 BH-FDR | ≥17,000 total draws or positional re-ingestion |
| Straight-play | 3_STAR / 4_STAR | **BLOCKED_REINGEST_REQUIRED** | Positional order lost in sorted DB storage | Re-ingestion from raw source; separate authorization |

---

## 5. Governance Status

| Governance check | Status |
|---|---|
| DB `strategy_prediction_replays` rows | **94,924 — unchanged throughout chain** |
| 3_STAR / 4_STAR replay rows | **0 — no rows ever inserted** |
| Registry | **Unchanged** |
| Production data | **Unchanged** |
| Recommendation logic | **Unchanged** |
| `controlled_apply` | **Not used** |
| Strategy promotion | **None** |
| All claims type | Historical replay evidence or dry-run evidence only |
| Bet advice | **None** |
| `dry_run` field | All star dry-run rows (in memory only) had `dry_run=1`; no DB rows written |

---

## 6. Future Action Menu

| Option | Description | Authorization needed |
|---|---|---|
| **A: Stop / passive monitoring** | No new research. Wait for ≥300 new DAILY_539 target draws; then recheck survivor per P224B protocol. | None (wait-only) |
| **B: DAILY_539 survivor backward-OOS extension** | Use ~4,376 un-replayed older DAILY_539 draws to resolve survivor p=0.0674 faster than Option A. Generates new replay rows. | **Explicit DB-write / backfill authorization required.** Inherits P224B gates; must report failure honestly. |
| **C: 3_STAR / 4_STAR straight-play re-ingestion (plan-only)** | Design a plan-only protocol for re-ingesting historical star draws with positional order preserved. No DB write in plan phase. | **Code-change authorization for re-ingestion script.** Separate DB-write authorization for actual data write. |
| **D: Wait for new draws naturally** | Similar to Option A. DAILY_539 draws arrive ~6 per week; 300 new draws ≈ 50 weeks; 500 ≈ 83 weeks. | None |
| **E: Archive and pause** | Close all active worker tasks. Retain artifacts. No further research until user explicitly restarts. | None |

**Recommended:** Option A or E. No research produces credible positive results under the current data volumes and corrected significance standards. Starting new scans on the same data without new draws simply manufactures false positives.

---

## 7. Authorization Matrix

| Action | Authorization level required |
|---|---|
| Read DB / query draws | None (read-only, always permitted) |
| Run phase-0 verification | None |
| Read governance docs | None |
| Run dry-run (no DB write) | Code-change scope authorization |
| Run P227B / P227C style scans with no DB write | Code-change scope authorization |
| Generate replay rows (DB write) | **Explicit DB-write authorization** |
| Re-ingest historical draw data | **Explicit DB-write authorization** (after plan-only is reviewed) |
| Strategy promotion / registry change | **Explicit production-promotion authorization** |
| Recommendation-logic change | **Explicit production-promotion authorization** |
| `controlled_apply` | **Explicit controlled-apply authorization** |
| Deploy to production | **Explicit deployment authorization** |
| Betting advice | **Not authorized under any circumstances** |

---

## 8. Risks and Blind Spots

| Risk / blind spot | Detail |
|---|---|
| **Overfitting via multiple comparisons** | P222/P227C tested many feature/window/lottery combinations. BH-FDR reduces but does not eliminate false positives. Any re-scan of the same data without new draws will find spurious signals. |
| **Underpowered star lottery tests** | 3_STAR and 4_STAR have far fewer draws (~4,000/~3,000) than the ~10,000–17,000 needed. Results are statistically unreliable. Classification as UNDERPOWERED is correct and honest. |
| **Sorted storage limitations** | DB stores star draws as sorted combinations; original order is lost. Straight-play validation would require raw positional data from the source. |
| **Repeated-digit limitation** | `lottery_types.json` says `repeatsAllowed: true` for star lotteries, but 0 repeated-digit draws exist in DB. Any future baseline computation must confirm whether repeats are truly disallowed or merely absent due to ingest stripping. |
| **DAILY_539 survivor fragility** | The entire edge of `midfreq_fourier_2bet` rests on 19 `hit_count=3` rows out of 1,500. This is a 1.3% tail dependency — removing it drops the mean below baseline. This is a classic hallmark of noise, not signal. |
| **Waiting for future OOS** | DAILY_539 draws arrive ~6/week. ≥300 new draws takes ~50 weeks; ≥500 takes ~83 weeks. Passive monitoring is correct but slow. |
| **Treating weak observations as deployable** | P223B's `CROSS_YEAR_CONFIRMED` classification was based on an overlapping (non-deduplicated) P222 slice. P224's dedup overturned it. A future agent must not re-promote from P223B alone — P224 is the authoritative verdict. |
| **Governance drift** | This chain generated many P-numbered artifacts. Future agents must read `CURRENT_STATE.md` (updated through P228) as the authoritative current state, not older task artifacts. |

---

## 9. Final Recommendation

**No active production work is recommended.**

1. **Do not start P225 model design.** There is no validated signal to design a model around. The sole surviving candidate (`midfreq_fourier_2bet / DAILY_539`) has a fragile, lean-null OOS result.

2. **Prefer passive monitoring (Option A or D).** Wait for ≥300–500 new DAILY_539 target draws, then re-evaluate the survivor per the P224B protocol. This is the lowest-risk path.

3. **If the user wants to accelerate resolution, Option B (backward-OOS extension)** is the most principled next step — it uses ~4,376 un-replayed historical DAILY_539 draws to resolve the p=0.0674 question without waiting. It requires explicit DB-write authorization and must apply the full P224B gate.

4. **If the user wants to explore star lotteries further**, Option C (plan-only re-ingestion design) is correct. Do not write DB or run any scan until the plan is reviewed and positional data integrity is confirmed.

5. **No strategy promotion, no recommendation-logic change, no betting advice in any scenario.**

---

## 10. Required Completion Check

1. **是否真的完成:** YES — comprehensive closeout report covering all 10 required sections.
2. **測試結果:** Phase 0 PASS; DB baseline PASS; drift guard PASS; full pytest NOT RUN (report-only task).
3. **仍卡住的唯一問題:** No blockers. DAILY_539 survivor WAIT_FOR_OOS; 3_STAR/4_STAR UNDERPOWERED; both require separate future authorizations.
4. **修改檔案清單:**
   - `outputs/research/p229_lottery_research_closeout_report_20260603.md` (new)
   - `outputs/research/p229_lottery_research_closeout_report_20260603.json` (new)
5. **staged / commit / push:** awaiting staging.
6. **是否允許進入下一輪:** YES (passive monitoring / Option B/C/E with separate authorization).
7. **Final Classification:** `P229_LOTTERY_RESEARCH_CLOSEOUT_REPORT_COMPLETE`
