# Lottery Replay Roadmap

**Last Updated:** 2026-05-24 Asia/Taipei (P45 update after P44 — Wave 3 BIG_LOTTO pipeline complete, maintenance mode)
**Owner:** CTO agent
**Primary Goal:** Strategy Historical Replay must become production-usable: the operator can select lottery type, strategy, date range, and 100/500/1000/1500-period presets, then inspect per-draw prediction-vs-actual comparisons in the existing historical prediction-list style. All system-developed strategies must be visible with an honest state: row-backed, artifact-only, retired, rejected-registered, observation, no-data, reconstructible, manual-review, or unsupported. The final product direction is not catalog visibility alone: it is 1500-period replay coverage for all executable strategies, with no fake replay rows and no unguarded production writes.

**CEO Goal:** 1500-period replay × all executable strategies.

**Repo Policy:** Use `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` only. Do not create a new repo.

---

## 1. Current Phase Snapshot

| Phase | Status | Evidence | CTO Note |
|---|---|---|---|
| P0 Schema stabilization | [Confirmed] Complete | `docs/replay/p0_schema_diff_20260519.md`; API contract PASS | Baseline no longer blocks replay work. |
| P14D-P21B replay backfill | [Confirmed] Complete for ONLINE strategies | git history through `a0b2867`; drift guard baseline 12460 | Three-lottery ONLINE replay store is row-backed. |
| P22 DAILY_539 API/UI verification | [Confirmed] Complete | `docs/replay/p22_daily539_api_ui_verification_20260521.md` | DAILY_539 5-number/no-special semantics verified. |
| P23 period preset quick-select | [Confirmed] Complete | `docs/replay/p23_replay_ui_period_preset_20260521.md` | 100/500/1000/1500 period presets exist. |
| P24 full strategy universe inventory | [Confirmed] Complete | `docs/replay/p24_full_strategy_universe_inventory_20260521.md` | 59-strategy universe established. |
| P25a browser verification | [Confirmed] Complete | `docs/replay/p25a_full_replay_page_browser_verification_20260521.md` | All 3 lotteries and 8 ONLINE strategies verified in browser. |
| P26 strategy state label module | [Confirmed] Complete | `docs/replay/p26_non_online_strategy_state_labels_20260521.md` | 9 canonical labels exist; pure/read-only source of label truth. |
| P27A console/404 cleanup | [Confirmed] Complete | `docs/replay/p27a_replay_ui_console_404_cleanup_20260521.md` | Wrong-port replay/API issues cleaned up. |
| P28 strategy-catalog API | [Confirmed] Complete and merged | HEAD history `cf80626`; PR #163; `docs/replay/p28_replay_strategy_catalog_label_integration_20260521.md` | `GET /api/replay/strategy-catalog` exposes 59 strategies with P26 labels. |
| P29 catalog UI section | [Confirmed] Complete and merged | HEAD history `8f9b2ce`; PR #164; `docs/replay/p29_replay_strategy_catalog_ui_section_20260521.md` | Replay page shows strategy status overview; non-queryable rows do not trigger replay query. |
| P30 reconstructible-candidacy evaluation | [Confirmed] Complete and merged | HEAD `2b6a657`; PR #165; `docs/replay/p30_reconstructible_candidacy_evaluation_20260521.md` | 51 non-row-backed strategies classified: 24 needs_promotion, 15 manual_review, 12 executable_no. |
| P31A Wave 1 adapter readiness | [Confirmed] Complete and merged | PR #166; `docs/replay/p31a_wave1_daily539_retired_adapter_readiness_20260523.md`; no-db-write; dry-run 7500 rows | Adapters wired, dry-run candidate rows generated, temp DB rehearsal passed, production rows remained 12460. |
| P31B Wave 1 production apply | [Confirmed] Complete and merged | PR #167; HEAD `f6b05e8`; production rows 12460 → 19960; 7500 rows inserted | Controlled apply under `P31B_DAILY539_RETIRED_7500_PROD_20260523`; drift guard PASS; 257 tests passed. |
| P32 Replay UI/API verification post-P31B | [Confirmed] Complete and merged | PR #168; HEAD `e704154`; production rows unchanged at 19960 | All 5 retired DAILY_539 strategies confirmed queryable via API and UI; 126 tests passed. |
| P33 Roadmap update after P31B + P32 | [Confirmed] Complete and merged | PR #169; `outputs/replay/p33_roadmap_update_after_p31b_p32_20260523.json` | Roadmap baseline updated to 19960; P34/P35/P36 prioritized. |
| P34 Replay UI usability gap closure | [Confirmed] Complete and merged | PR #170; `outputs/replay/p34_replay_ui_usability_gap_closure_20260523.json` | Half-year date default + RETIRED labeling clarity; no production DB write. |
| P35 Wave 2 candidate planning | [Confirmed] Complete and merged | PR #171; `outputs/replay/p35_wave2_candidate_planning_20260523.json` | 19 remaining needs_promotion evaluated; 6 DAILY_539 selected for Wave 2. |
| P36 Wave 2 DAILY_539 dry-run + temp rehearsal | [Confirmed] Complete and merged | PR #172; `outputs/replay/p36_wave2_daily539_dryrun_rehearsal_20260523.json` | 9000 dry-run rows; R1/R2/R3 temp rehearsal PASS; production rows remained 19960. |
| P37 Wave 2 DAILY_539 production apply | [Confirmed] Complete and merged | PR #173; `outputs/replay/p37_wave2_daily539_production_apply_20260523.json`; production rows 19960 → 28960; 9000 rows inserted | Controlled apply under `P37_DAILY539_WAVE2_9000_PROD_20260523`; drift guard PASS; lifecycle DRY_RUN. |
| P38 Post-P37 verification + freshness registry audit | [Confirmed] Complete and merged | PR #174; `outputs/replay/p38_post_p37_verification_registry_audit_20260523.json` | P37 rows verified; strategy_replay_runs ids 8-10 ACCEPTED; API verified; no production DB change. |
| P39 Replay UI smoke closure after P38 | [Confirmed] Complete and merged | PR #175; `outputs/replay/p39_replay_ui_smoke_closure_after_p38_20260523.json`; merge commit 2558f00 | P38 deferred UI smoke RESOLVED; 0 console errors; all Wave 2 strategies queryable; 28960 rows confirmed. |
| P40 Roadmap + CTO analysis update after P39 | [Confirmed] Complete and merged | PR #176; `outputs/replay/p40_roadmap_update_after_p39_20260523.json` | Roadmap baseline updated to 28960; P41-P44 prioritized; Wave 3 BIG_LOTTO bootstrap as next P0. |
| P41 Wave 3 BIG_LOTTO adapter bootstrap planning | [Confirmed] Complete and merged | PR #177; `outputs/replay/p41_wave3_biglotto_adapter_bootstrap_planning_20260524.json`; read-only | 6 Wave 3 BIG_LOTTO candidates identified; adapter interface designed; production rows remained 28960. |
| P42 Wave 3 BIG_LOTTO dry-run + temp rehearsal | [Confirmed] Complete and merged | PR #178; `outputs/replay/p42_wave3_biglotto_dryrun_rehearsal_20260524.json` | 9000 dry-run rows; R1/R2/R3 temp rehearsal PASS; production rows remained 28960. |
| P43 Wave 3 BIG_LOTTO production apply | [Confirmed] Complete and merged | PR #179; `outputs/replay/p43_wave3_biglotto_production_apply_20260523.json`; production rows 28960 → 37960; 9000 rows inserted | Controlled apply under `P43_BIGLOTTO_WAVE3_9000_PROD_20260523`; drift guard PASS; lifecycle DRY_RUN. |
| P44 Wave 3 BIG_LOTTO performance analysis | [Confirmed] Complete and merged | PR #180; `outputs/replay/p44_wave3_biglotto_performance_analysis_20260523.json`; merge commit a2a7e19 | Three-window + permutation tests; no promotion candidates; best p=0.104 (gate p<0.05 FAIL); L91 confirmed. |

---

## 2. Current Production Replay / Catalog Baseline

Verified during P45 CTO review on 2026-05-24 (post P44 — Wave 3 BIG_LOTTO pipeline complete).

## Replay Coverage Baseline (as of 2026-05-24)

| Milestone | Rows | Cumulative |
|---|---:|---:|
| Pre-Wave-1 baseline (ONLINE strategies, P14D-P21B) | 12460 | 12460 |
| P31B Wave 1 retired DAILY_539 (+7500 rows) | 7500 | 19960 |
| P37 Wave 2 DAILY_539 DRY_RUN (+9000 rows) | 9000 | 28960 |
| P43 Wave 3 BIG_LOTTO DRY_RUN (+9000 rows) | 9000 | 37960 |
| **Current total** | — | **37960** |

> **Note on Wave 2 DRY_RUN strategies:** Wave 2 strategies (`lifecycle_status=DRY_RUN`) are not shown in the strategy selector dropdown. They are visible and queryable in the replay table via the `lottery_type=DAILY_539` filter. This is accepted current behavior pending live monitoring evidence for DRY_RUN → ONLINE promotion.

> **Note on Wave 3 BIG_LOTTO DRY_RUN strategies:** Wave 3 BIG_LOTTO strategies are in production as DRY_RUN rows. P44 analysis found no promotion candidates (best p=0.104, gate p<0.05 FAIL). BIG_LOTTO is now in maintenance mode per L91. ONLINE promotion blocked until trigger conditions are met (rule change / draw anomaly / new signal class outside H001-H010).

| Metric | Value |
|---|---:|
| Production replay rows | 37960 |
| Legacy rows | 460 |
| Verified backfill rows (ONLINE strategies, P14D-P21B) | 12000 |
| P31B Wave 1 rows (retired DAILY_539 strategies) | 7500 |
| P37 Wave 2 rows (DRY_RUN DAILY_539 strategies) | 9000 |
| P43 Wave 3 rows (DRY_RUN BIG_LOTTO strategies) | 9000 |
| Row-backed strategies | 25 (8 ONLINE + 5 RETIRED + 6 DRY_RUN DAILY_539 + 6 DRY_RUN BIG_LOTTO) |
| Full strategy catalog universe | 59 |
| Non-row-backed strategies evaluated in P30 | 51 |
| DB writes in P33-P45 roadmap/docs-only phases | 0 |
| Baseline before P31B | 12460 |
| Baseline before P37 | 19960 |
| Baseline before P43 | 28960 |
| P31B Wave 1 rows inserted | 7500 |
| P37 Wave 2 rows inserted | 9000 |
| P43 Wave 3 rows inserted | 9000 |

## BIG_LOTTO Status: MAINTENANCE MODE

As of P44 (2026-05-24):
- Wave 3 strategies: 6 × 1500 rows in production (DRY_RUN)
- P44 performance analysis: no promotion candidates
- Best p-value: 0.104 (gate: p < 0.05) — FAIL
- McNemar gate: INCONCLUSIVE
- Per L91: 49C6 pool near-random, signal space exhausted (7 signals tested, zero p<0.05)
- ONLINE promotion blocked until: rule change / draw anomaly / new signal class outside H001-H010

Strategy catalog label summary after P37 + P38 + P39 + P43 + P44:

| Label | Count | Queryable | Notes |
|---|---:|---|---|
| `row-backed` | 8 | yes | ONLINE strategies with P14D-P21B backfill |
| `artifact-only` | 35 | no | — |
| `retired` | 5 | no (catalog) | Row-backed via P31B; queryable via `/api/replay/history` with lifecycle filter |
| `dry-run` (DAILY_539) | 6 | no (catalog dropdown) | Row-backed via P37; queryable via `/api/replay/history?lottery_type=DAILY_539` |
| `dry-run` (BIG_LOTTO) | 6 | no (catalog dropdown) | Row-backed via P43; queryable via `/api/replay/history?lottery_type=BIG_LOTTO`; maintenance mode |
| `rejected-registered` | 4 | no | — |
| `observation` | 1 | no | — |
| `no-data` | 0 | no | — |
| `reconstructible` | 0 | no | — |
| `manual-review` | 0 | no | — |
| `unsupported` | 0 | no | — |

> **Note on retired strategies:** The 5 P31B DAILY_539 retired strategies (`acb_1bet`, `acb_markov_midfreq`, `acb_markov_midfreq_3bet`, `midfreq_acb_2bet`, `midfreq_fourier_2bet`) are replay-backed (1500 rows each) but **remain retired**. They are NOT promoted to ONLINE. The catalog `queryable=False` and `row_count=0` fields reflect P26 label model / P24 static inventory behavior. Live row counts via `/api/replay/history?lifecycle_status=RETIRED` are authoritative (total=7500).

> **Note on Wave 2 DRY_RUN strategies:** The 6 P37 DAILY_539 DRY_RUN strategies (`acb_single_539`, `539_3bet_orthogonal`, `markov_1bet_539`, `zone_gap_3bet_539`, `p0b_539_3bet_f_cold_fmid`, `p0c_539_3bet_f_cold_x2`) are replay-backed (1500 rows each, total=9000). They are NOT in the strategy dropdown (controlled by `_REGISTRY`). Queryable via `/api/replay/history?lottery_type=DAILY_539`. DRY_RUN → ONLINE promotion requires live monitoring evidence (200+ draws). This is accepted current behavior.

P43 Wave 3 — completed BIG_LOTTO DRY_RUN strategies (no promotion candidates per P44):

| Strategy | Lifecycle label | Lottery | Rows (P43) | P44 Best p-value | Promotion Status |
|---|---|---|---:|---|---|
| `markov_single_biglotto` | DRY_RUN | BIG_LOTTO | 1500 | 0.638 | BLOCKED (p>0.05) |
| `markov_2bet_biglotto` | DRY_RUN | BIG_LOTTO | 1500 | 0.638 | BLOCKED (p>0.05) |
| `bet2_fourier_expansion_biglotto` | DRY_RUN | BIG_LOTTO | 1500 | 0.364 | BLOCKED (p>0.05) |
| `fourier30_markov30_biglotto` | DRY_RUN | BIG_LOTTO | 1500 | 0.531 | BLOCKED (p>0.05) |
| `cold_complement_biglotto` | DRY_RUN | BIG_LOTTO | 1500 | 0.104 | BLOCKED (p>0.05) |
| `coldpool15_biglotto` | DRY_RUN | BIG_LOTTO | 1500 | 0.104 | BLOCKED (p>0.05) |

P30 reconstructible-candidacy summary:

| Classification | Count | Meaning |
|---|---:|---|
| `needs_promotion` | 24 | Underlying code exists; thin replay adapter wrapper is needed. |
| `manual_review` | 15 | Human judgment needed before promotion or rejection. |
| `executable_no` | 12 | Rejected, superseded, or no viable implementation path. |

Replay-store row-backed strategy distribution (post P43):

| Lottery | Strategy | Rows | Lifecycle | Notes |
|---|---|---:|---|---|
| BIG_LOTTO | `biglotto_deviation_2bet` | 1570 | ONLINE | 1500 verified backfill + 70 legacy |
| BIG_LOTTO | `biglotto_triple_strike` | 1570 | ONLINE | 1500 verified backfill + 70 legacy |
| BIG_LOTTO | `ts3_regime_3bet` | 1500 | ONLINE | verified backfill |
| POWER_LOTTO | `fourier_rhythm_3bet` | 1500 | ONLINE | verified backfill |
| POWER_LOTTO | `power_orthogonal_5bet` | 1570 | ONLINE | 1500 verified backfill + 70 legacy |
| POWER_LOTTO | `power_precision_3bet` | 1570 | ONLINE | 1500 verified backfill + 70 legacy |
| DAILY_539 | `daily539_f4cold` | 1590 | ONLINE | 1500 verified backfill + 90 legacy |
| DAILY_539 | `daily539_markov_cold` | 1590 | ONLINE | 1500 verified backfill + 90 legacy |
| DAILY_539 | `acb_1bet` | 1500 | RETIRED (replay-backed) | P31B Wave 1; lifecycle remains retired |
| DAILY_539 | `acb_markov_midfreq` | 1500 | RETIRED (replay-backed) | P31B Wave 1; lifecycle remains retired |
| DAILY_539 | `acb_markov_midfreq_3bet` | 1500 | RETIRED (replay-backed) | P31B Wave 1; lifecycle remains retired |
| DAILY_539 | `midfreq_acb_2bet` | 1500 | RETIRED (replay-backed) | P31B Wave 1; lifecycle remains retired |
| DAILY_539 | `midfreq_fourier_2bet` | 1500 | RETIRED (replay-backed) | P31B Wave 1; lifecycle remains retired |
| DAILY_539 | `acb_single_539` | 1500 | DRY_RUN | P37 Wave 2; not in dropdown; queryable via DAILY_539 filter |
| DAILY_539 | `539_3bet_orthogonal` | 1500 | DRY_RUN | P37 Wave 2; not in dropdown; queryable via DAILY_539 filter |
| DAILY_539 | `markov_1bet_539` | 1500 | DRY_RUN | P37 Wave 2; not in dropdown; queryable via DAILY_539 filter |
| DAILY_539 | `zone_gap_3bet_539` | 1500 | DRY_RUN | P37 Wave 2; not in dropdown; queryable via DAILY_539 filter |
| DAILY_539 | `p0b_539_3bet_f_cold_fmid` | 1500 | DRY_RUN | P37 Wave 2; not in dropdown; queryable via DAILY_539 filter |
| DAILY_539 | `p0c_539_3bet_f_cold_x2` | 1500 | DRY_RUN | P37 Wave 2; not in dropdown; queryable via DAILY_539 filter |
| BIG_LOTTO | `markov_single_biglotto` | 1500 | DRY_RUN | P43 Wave 3; P44 p=0.638 FAIL; maintenance mode |
| BIG_LOTTO | `markov_2bet_biglotto` | 1500 | DRY_RUN | P43 Wave 3; P44 p=0.638 FAIL; maintenance mode |
| BIG_LOTTO | `bet2_fourier_expansion_biglotto` | 1500 | DRY_RUN | P43 Wave 3; P44 p=0.364 FAIL; maintenance mode |
| BIG_LOTTO | `fourier30_markov30_biglotto` | 1500 | DRY_RUN | P43 Wave 3; P44 p=0.531 FAIL; maintenance mode |
| BIG_LOTTO | `cold_complement_biglotto` | 1500 | DRY_RUN | P43 Wave 3; P44 p=0.104 FAIL; maintenance mode |
| BIG_LOTTO | `coldpool15_biglotto` | 1500 | DRY_RUN | P43 Wave 3; P44 p=0.104 FAIL; maintenance mode |

P31B Wave 1 — completed DAILY_539 retired strategies:

| Strategy | Lifecycle label | Lottery | Rows (P31B) | P32 Verification |
|---|---|---|---:|---|
| `acb_1bet` | RETIRED (replay-backed) | DAILY_539 | 1500 | ✅ API total=1500, UI confirmed |
| `acb_markov_midfreq` | RETIRED (replay-backed) | DAILY_539 | 1500 | ✅ API total=1500, UI confirmed |
| `acb_markov_midfreq_3bet` | RETIRED (replay-backed) | DAILY_539 | 1500 | ✅ API total=1500, UI confirmed |
| `midfreq_acb_2bet` | RETIRED (replay-backed) | DAILY_539 | 1500 | ✅ API total=1500, UI confirmed |
| `midfreq_fourier_2bet` | RETIRED (replay-backed) | DAILY_539 | 1500 | ✅ API total=1500, UI confirmed |

P37 Wave 2 — completed DAILY_539 DRY_RUN strategies:

| Strategy | Lifecycle label | Lottery | Rows (P37) | P38+P39 Verification |
|---|---|---|---:|---|
| `acb_single_539` | DRY_RUN | DAILY_539 | 1500 | ✅ API total=1500, UI queryable |
| `539_3bet_orthogonal` | DRY_RUN | DAILY_539 | 1500 | ✅ API total=1500, UI queryable |
| `markov_1bet_539` | DRY_RUN | DAILY_539 | 1500 | ✅ API total=1500, UI queryable |
| `zone_gap_3bet_539` | DRY_RUN | DAILY_539 | 1500 | ✅ API total=1500, UI queryable |
| `p0b_539_3bet_f_cold_fmid` | DRY_RUN | DAILY_539 | 1500 | ✅ API total=1500, UI queryable |
| `p0c_539_3bet_f_cold_x2` | DRY_RUN | DAILY_539 | 1500 | ✅ API total=1500, UI queryable |

---

## 3. Roadmap Alignment Assessment

| Item | Classification | Assessment |
|---|---|---|
| P29 catalog UI | [Aligned] | Complete and merged. Replay page shows 59-strategy catalog. |
| P30 reconstructible-candidacy evaluation | [Aligned] | Complete and merged. 51 strategies classified. |
| P31A Wave 1 adapter readiness | [Aligned] | Complete and merged (PR #166). 5 strategies wired, 7500 dry-run rows generated, no production DB write. |
| P31B Wave 1 production apply | [Aligned] | Complete and merged (PR #167). Production rows advanced from 12460 to 19960. 257 tests passed. |
| P32 UI/API verification post-P31B | [Aligned] | Complete and merged (PR #168). All 5 retired strategies confirmed queryable. 126 tests passed. |
| P33 Roadmap update after P31B+P32 | [Aligned] | Complete and merged. Baseline updated; P34-P36 prioritized. |
| P34 Replay UI usability gap | [Aligned] | Complete and merged. Half-year default + RETIRED labeling clarity shipped. |
| P35 Wave 2 candidate planning | [Aligned] | Complete and merged (PR #171). 19 remaining strategies evaluated; 6 DAILY_539 selected. |
| P36 Wave 2 DAILY_539 dry-run + rehearsal | [Aligned] | Complete and merged (PR #172). 9000 dry-run rows; R1/R2/R3 rehearsal PASS. |
| P37 Wave 2 DAILY_539 production apply | [Aligned] | Complete and merged (PR #173). 19960 → 28960 rows; lifecycle DRY_RUN; drift guard PASS. |
| P38 Post-P37 verification + registry audit | [Aligned] | Complete and merged (PR #174). 9000 rows verified; ids 8-10 ACCEPTED operational updates. |
| P39 Replay UI smoke closure | [Aligned] | Complete and merged (PR #175; commit 2558f00). P38 deferred UI smoke RESOLVED; 0 console errors. |
| P40 Roadmap update after P39 | [Aligned] | Complete and merged (PR #176). Baseline updated to 28960; P41-P44 prioritized. |
| P41 Wave 3 BIG_LOTTO adapter bootstrap | [Aligned] | Complete and merged (PR #177). 6 candidates identified; read-only; production rows remained 28960. |
| P42 Wave 3 BIG_LOTTO dry-run + rehearsal | [Aligned] | Complete and merged (PR #178). 9000 dry-run rows; R1/R2/R3 rehearsal PASS. |
| P43 Wave 3 BIG_LOTTO production apply | [Aligned] | Complete and merged (PR #179). 28960 → 37960 rows; lifecycle DRY_RUN; drift guard PASS. |
| P44 Wave 3 BIG_LOTTO performance analysis | [Aligned] | Complete and merged (PR #180; commit a2a7e19). No promotion candidates; best p=0.104; L91 confirmed. |
| BIG_LOTTO maintenance mode | [Confirmed] | P44 confirms BIG_LOTTO 49C6 near-random; all 7 signals exhausted; maintenance mode entered. |
| Wave 2 DRY_RUN monitoring design | [Deferred] | DRY_RUN → ONLINE promotion criteria not yet defined. Now P1 for P47. |
| POWER_LOTTO expansion | [Not started] | No adapter or planning done. Now P0 for P46. |
| Catalog freshness guard | [Drift] | Remains deferred; non-blocking ops hygiene. |
| Manual-review strategy resolution | [Drift] | Remains deferred; 15 strategies in holding state. |

---

## 4. Reprioritized P0-P9+ (Updated 2026-05-24 after P44)

| Priority | Phase | Focus | Current Status | Acceptance Criteria |
|---|---|---|---|---|
| **P0** | P46 POWER_LOTTO expansion planning | Plan adapter bootstrap for POWER_LOTTO remaining strategies (38C6+8, smaller pool than BIG_LOTTO) | [Not started] | POWER_LOTTO adapter complexity assessed; Wave plan produced; no production DB write. |
| **P1** | P47 Wave 2 DAILY_539 live monitoring design | Define DRY_RUN → ONLINE promotion criteria for Wave 2 strategies after 200+ draws | [Deferred] | Promotion criteria defined: edge stability over 200 draws + McNemar gate; no production write. |
| **P2** | P48 Freshness cadence guard improvement | Auto-insert DONE records in cadence guard; reduce manual fix burden | [Deferred] | Read-only guard with auto-insert; no DB writes to strategy rows. |
| **P3** | P49 Manual review resolution | Resolve `cluster_pivot_biglotto`, `ts3_markov_freq_5bet_biglotto`, and other deferred manual-review strategies | [Deferred] | Decision rubric applied; strategies accepted or rejected with evidence. |
| **P4** | Replay performance / pagination hardening | Keep replay/API/UI practical at 37960+ rows | [Deferred] | Query and UI remain responsive for period presets and catalog/history flows. |
| **P5** | Artifact consolidation | Index P21B-P45 docs, outputs, scripts, and test evidence | [Deferred] | One durable reference points to all evidence. |
| **P6** | Post-launch operations | Monitor future draw replay coverage and stale strategy states | [Deferred] | Reports show missing replay rows after new draws and stale strategy catalog states. |

Items completed and retired as active items (P45 update after P44):

| Item | Decision | Reason |
|---|---|---|
| P34 UI usability gap | Retired as active item | [Confirmed] Complete and merged; half-year default + RETIRED labeling shipped. |
| P35 Wave 2 candidate planning | Retired as active item | [Confirmed] Complete and merged (PR #171); 6 DAILY_539 strategies selected. |
| P36 Wave 2 DAILY_539 dry-run | Retired as active item | [Confirmed] Complete and merged (PR #172); 9000 dry-run rows; rehearsal PASS. |
| P37 Wave 2 production apply | Retired as active item | [Confirmed] Complete and merged (PR #173); 19960 → 28960 rows. |
| P38 Post-P37 verification | Retired as active item | [Confirmed] Complete and merged (PR #174); rows verified; ids 8-10 ACCEPTED. |
| P39 UI smoke closure | Retired as active item | [Confirmed] Complete and merged (PR #175); 0 console errors; all Wave 2 strategies queryable. |
| P40 Roadmap update after P39 | Retired as active item | [Confirmed] Complete and merged (PR #176); baseline updated to 28960. |
| P41 Wave 3 BIG_LOTTO bootstrap planning | Retired as active item | [Confirmed] Complete and merged (PR #177); 6 candidates identified; read-only. |
| P42 Wave 3 BIG_LOTTO dry-run + rehearsal | Retired as active item | [Confirmed] Complete and merged (PR #178); 9000 dry-run rows; R1/R2/R3 PASS. |
| P43 Wave 3 BIG_LOTTO production apply | Retired as active item | [Confirmed] Complete and merged (PR #179); 28960 → 37960 rows. |
| P44 Wave 3 BIG_LOTTO performance analysis | Retired as active item | [Confirmed] Complete and merged (PR #180); no promotion candidates; best p=0.104. |
| BIG_LOTTO new signal research | Blocked — maintenance mode | Per L91: 49C6 near-random; no new BIG_LOTTO research until trigger conditions met. |
| Wave 2 production apply (was P10) | Completed | P37 executed Wave 2 apply under governance; retired as active item. |
| Wave 3 production apply | Completed | P43 executed Wave 3 apply under governance; 28960 → 37960; retired as active item. |
| Incremental refresh before monitoring design | Downgrade to P2/P3 | Operating cadence matters after coverage expansion. |
| Broad UI redesign | Pause | CEO wants existing historical prediction-list style. |
| `manual_review=15` | Downgrade to P3 | Need separate decision rubric; deferred until POWER_LOTTO expansion is underway. |
| `executable_no=12` backfill | Retired unless new evidence appears | P30 classified as rejected, superseded, or not viable. |

---

## 5. Critical Blockers (Updated 2026-05-24 after P44)

All P41-P44 Wave 3 BIG_LOTTO blockers are resolved. BIG_LOTTO pipeline is complete (maintenance mode). Remaining blockers:

| Blocker | Impact | Why It Blocks | Risk If Ignored | Priority | Acceptance Standard |
|---|---|---|---|---|---|
| POWER_LOTTO expansion not started | Coverage expansion | No POWER_LOTTO adapter or planning done; 38C6+8 pool strategies cannot generate replay rows | Coverage stalls at 37960 rows; CEO goal (all executable strategies) not met | P0 (P46) | POWER_LOTTO adapter bootstrap design complete; no production DB write. |
| DRY_RUN → ONLINE promotion criteria undefined | Wave 2 lifecycle governance | 12 DRY_RUN strategies (6 DAILY_539 + 6 BIG_LOTTO) in production but no quantitative promotion path | Strategies remain DRY_RUN indefinitely; no decision gate | P1 (P47) | Promotion criteria defined: edge stability threshold, McNemar gate, minimum 200 draws. |
| BIG_LOTTO ONLINE promotion | Maintenance mode enforcement | P44 analysis: best p=0.104 > 0.05 gate; all 6 Wave 3 strategies remain DRY_RUN | Premature promotion of statistically insignificant strategies | Blocked (no phase) | Unblocked only by: rule change / draw anomaly / new signal class outside H001-H010. |

---

## 6. Most Valuable System Optimization Directions (Updated 2026-05-24 after P44)

### Direction A: P46 POWER_LOTTO Expansion Planning (P0)

- **Roadmap phase:** P0
- **Why important:** Wave 3 BIG_LOTTO pipeline is complete. POWER_LOTTO (38C6+8) has smaller pool than BIG_LOTTO (49C6); signal detection probability is higher.
- **System maturity gain:** Extends governance pattern to a third lottery type; tests whether smaller pool yields detectable edges.
- **Expected benefit:** Blueprint for POWER_LOTTO Wave 4 apply; adapter interface for 38C6+8 pool.
- **Risk:** POWER_LOTTO special number (1-8) adds complexity vs DAILY_539 (no special). May require separate scoring logic.
- **Acceptance:** POWER_LOTTO adapter bootstrap design complete; no-db-write; candidates catalogued with effort/risk estimate.
- **Priority:** P0

### Direction B: P47 Wave 2 DAILY_539 Live Monitoring Design (P1)

- **Roadmap phase:** P1
- **Why important:** 12 DRY_RUN strategies (6 DAILY_539 + 6 BIG_LOTTO) in production but no promotion path defined.
- **System maturity gain:** Creates DRY_RUN → ONLINE promotion ladder; separates DAILY_539 (promotable after 200+ draws) from BIG_LOTTO (maintenance mode).
- **Expected benefit:** Operators have clear decision gate for Wave 2 DAILY_539 strategies if evidence warrants.
- **Risk:** Setting criteria too loose could promote underperforming strategies; too strict could stall promotion indefinitely.
- **Acceptance:** Promotion criteria documented: edge stability over 200+ draws, McNemar gate, no adverse PSI signals.
- **Priority:** P1

### Direction C: P48 Freshness Cadence Guard Improvement (P2)

- **Roadmap phase:** P2
- **Why important:** P38 registry ids 8-10 required manual insertion; auto-insert would reduce toil each wave.
- **System maturity gain:** Automates cadence guard DONE record creation; reduces manual fix burden.
- **Expected benefit:** Guard auto-inserts DONE records when all strategies in scope have been refreshed.
- **Risk:** Auto-insert could mask underlying data freshness issues.
- **Acceptance:** Read-only guard improved; auto-insert documented; no DB writes to strategy rows.
- **Priority:** P2

### Direction D: P49 Manual Review Resolution (P3)

- **Roadmap phase:** P3
- **Why important:** `cluster_pivot_biglotto` (negative edge) and `ts3_markov_freq_5bet_biglotto` (blocked) need human decision before any inclusion.
- **System maturity gain:** Converts open classification into actionable accept/reject decisions.
- **Expected benefit:** Shrinks the unknown pool; clarifies maximum replay coverage ceiling.
- **Risk:** Rushing decisions on complex composites can produce wrong coverage estimates.
- **Acceptance:** Decision rubric applied; strategies accepted or rejected with documented evidence.
- **Priority:** P3

---

## 7. Today's Focus (Updated 2026-05-24 after P44)

**Recommended focus:** P46 POWER_LOTTO Expansion Planning.

Expected deliverable:

- POWER_LOTTO adapter bootstrap design document produced.
- POWER_LOTTO candidates classified with effort/risk/expected rows estimate.
- No production DB write.
- No lifecycle promotion.
- All existing replay tests still pass.

Do not promote any DRY_RUN strategy to ONLINE without monitoring evidence (200+ draws + McNemar gate).
Do not run new BIG_LOTTO research without trigger conditions (rule change / draw anomaly / new signal class outside H001-H010).

Final roadmap marker:

```text
CTO_ROADMAP_AFTER_P41_P42_P43_P44_P45_20260524
```
