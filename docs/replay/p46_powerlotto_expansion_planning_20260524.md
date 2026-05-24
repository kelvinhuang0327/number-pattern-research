# P46 POWER_LOTTO Expansion Planning

**Date:** 2026-05-24  
**Branch:** p46-powerlotto-expansion-planning  
**Classification:** P46_POWERLOTTO_EXPANSION_PLANNING_MERGED_TO_MAIN  
**Production rows:** 37960 (unchanged — no DB writes in this task)

---

## 1. Scope and Goal

P46 is a **read-only planning task**. Its purpose is to:

1. Inventory the current POWER_LOTTO replay coverage (what is already row-backed).
2. Identify expansion candidates from P30/P35 evidence and RSM production data.
3. Design the POWER_LOTTO adapter bootstrap interface (38C6 + 1/8 special).
4. Recommend the P47 scope.

No adapter code was written. No dry-run rows were generated. No DB writes occurred.

---

## 2. POWER_LOTTO Pool Characteristics

| Dimension | Value |
|-----------|-------|
| First zone pool | 1–38 (pick 6) |
| Second zone / special | 1–8 (pick 1, separate pool) |
| Total draws in DB | 1912 (2008/01/24 – 2026/05/18) |
| First-zone hit baseline (3 bets) | ~11.17% |
| Signal detection advantage vs BIG_LOTTO | Pool=38 means each number appears 301.9 times over history vs BIG_LOTTO 261.5 — higher frequency per number, better signal detection probability |

The special number pool (1–8) is **completely separate** from the first-zone pool (1–38). Jackpot requires matching all 6 first-zone numbers AND the special.

---

## 3. Current POWER_LOTTO Replay Coverage

Three strategies currently have production replay rows:

| strategy_id | Registry lifecycle | Rows | Draw range | RSM edge (300p) |
|-------------|-------------------|------|------------|-----------------|
| `fourier_rhythm_3bet` | ONLINE | 1500 | 101000002–115000040 | +3.16% / Sharpe 0.090 |
| `power_orthogonal_5bet` | ONLINE | 1570 | 99000055–115000040 | +2.76% / Sharpe 0.068 |
| `power_precision_3bet` | ONLINE | 1570 | 99000055–115000040 | +3.40% / Sharpe 0.088 |

**Total POWER_LOTTO rows in DB: 4640**

All three are `dry_run=0`, `replay_status=PREDICTED`, fully visible in the replay UI.

---

## 4. Non-Row-Backed POWER_LOTTO Strategies

From P30 candidacy evaluation and registry inspection:

| strategy_id | Registry lifecycle | P30 classification | Blocking issues |
|-------------|-------------------|--------------------|-----------------|
| `h6_gate_mk20_ew85` | OBSERVATION | manual_review | H6 is a monitoring framework, not a prediction function. Cannot produce `predicted_numbers`. |
| `power_shlc_midfreq` | REJECTED | executable_no | Statistically rejected (edge –2.92%). No executable code. |
| `sgp_power_017_research` | not_registered | executable_no | Research artifact. No implementation. |
| `sgp_v9_apex_powerlotto` | not_registered | executable_no | SGP V9 research artifact. No implementation. |
| `shlc_midfreq_power` | not_registered | executable_no | SHLC tested –2.92%. Rejected. |
| `gap_rebound_powerlotto` | not_registered | manual_review | Concept only in rejected/ artifact. No tool. |
| `p1_conditional_branch_powerlotto` | not_registered | manual_review | Concept only. L67: conditional branch trigger <5% = NO-OP. |
| `structural_zone_guard_pp3_power` | not_registered | manual_review | PP3+zone guard composite. No tool. Effort HIGH. |
| `special_mab_decay_adjustment_power` | not_registered | executable_no | MAB decay special strategy. Rejected. No implementation. |

---

## 5. Expansion Candidate Classification

From RSM production data in MEMORY.md and tool inspection:

### 5.1 ready_for_bootstrap (3 strategies)

These appear in MEMORY.md as active RSM-monitored strategies with known tool implementations:

#### `pp3_freqort_4bet`
- **RSM edge:** +3.40% (300p), Sharpe 0.088, perm p=0.000 (VALIDATED)
- **Tool:** `tools/predict_power_orthogonal_5bet.py` — bets 1–4 = PP3 3bet + FreqOrt bet4
- **Effort:** LOW — extract 4-bet slice from existing 5-bet tool
- **Estimated rows:** 1,500

#### `midfreq_fourier_mk_3bet`
- **RSM edge:** +1.83% (300p, RSM monitored)
- **Validation evidence:** MidFreq+Fourier+Markov for POWER_LOTTO validated at edge=+2.48%, p=0.015, three-window PASS (MEMORY.md L83–L84)
- **Tool:** Composite of `tools/power_fourier_rhythm.py` + `lottery_api/models/unified_predictor.py::markov_predict`
- **Effort:** LOW to MEDIUM — three-component integration
- **Estimated rows:** 1,500

#### `midfreq_fourier_2bet`
- **RSM edge:** +0.08% (300p, RSM monitored — marginal but positive)
- **Validation evidence:** MidFreq+Fourier orthogonal for POWER_LOTTO validated at edge=+2.27%, p=0.005, three-window PASS (MEMORY.md L83)
- **Tool:** `tools/power_fourier_rhythm.py` (midfreq component in power_precision)
- **Effort:** LOW — 2-bet POWER_LOTTO adapter distinct from DAILY_539 RETIRED variant
- **Estimated rows:** 1,500
- **Note:** Classify as DRY_RUN WATCH after bootstrap; RSM edge below promotion threshold

### 5.2 needs_manual_review (0 strategies)

No POWER_LOTTO strategies require manual review before bootstrap decision. The three `manual_review` entries from P30 (`h6_gate_mk20_ew85`, `gap_rebound_powerlotto`, `p1_conditional_branch_powerlotto`) are blocked by structural impossibility (not a prediction function) or missing implementation.

### 5.3 unsupported (6 strategies)

| strategy_id | Reason |
|-------------|--------|
| `h6_gate_mk20_ew85` | Not a prediction strategy — monitoring framework only |
| `power_shlc_midfreq` | Statistically rejected, no code |
| `sgp_power_017_research` | Research artifact, no code |
| `sgp_v9_apex_powerlotto` | Research artifact, no code |
| `shlc_midfreq_power` | Rejected, edge –2.92% |
| `gap_rebound_powerlotto` | Concept only, no tool |
| `p1_conditional_branch_powerlotto` | Concept only; L67 applies |
| `structural_zone_guard_pp3_power` | No tool, HIGH effort, no RSM evidence |
| `special_mab_decay_adjustment_power` | Rejected MAB decay strategy |

### 5.4 already_covered (3 strategies)

`fourier_rhythm_3bet`, `power_orthogonal_5bet`, `power_precision_3bet` — all row-backed with ≥1500 rows.

---

## 6. Special Number Handling: First Zone vs Second Zone

This is the most important difference between POWER_LOTTO and both DAILY_539 and BIG_LOTTO adapters:

| Game | First zone | Special / second zone |
|------|------------|----------------------|
| DAILY_539 | 5 from 1–39 | None (no special) |
| BIG_LOTTO | 6 from 1–49 | 1 from **same** pool 1–49 |
| POWER_LOTTO | 6 from **1–38** | 1 from **separate** pool **1–8** |

### Hit count semantics
- `hit_count` = number of `predicted_numbers` (6 first-zone ints in [1,38]) that appear in `actual_numbers` (6 actual first-zone ints).
- `hit_count` is **never incremented** by a special match.

### special_hit semantics
- `special_hit = 1` if `predicted_special == actual_special` (both ints in [1,8]).
- `special_hit = 0` if strategy does not predict special (predicted_special = None).
- Special pool is 1–8, **not** 1–38. A prediction of special=5 is valid; special=39 is invalid.

### Validation rule for POWER_LOTTO adapters
```
assert len(predicted_numbers) == 6
assert all(1 <= n <= 38 for n in predicted_numbers)
assert len(set(predicted_numbers)) == 6  # unique
if predicted_special is not None:
    assert 1 <= predicted_special <= 8
```

---

## 7. Cutoff and generated_at Semantics

Same as BIG_LOTTO adapters (P42 pattern):

- `history_cutoff_draw` = last draw number in the causal slice
- `prediction_cutoff_date` = date of that last draw (YYYY/MM/DD)
- `prediction_generated_at` = ISO datetime when the prediction function ran
- Causal slice: `history = all_draws[:target_idx]` — the target draw itself is **excluded**
- No draw with `date >= target_date` may appear in the history passed to the adapter

---

## 8. POWER_LOTTO Adapter Interface Design

### File
`lottery_api/models/p47_wave4_powerlotto_adapters.py`  
(DO NOT create this file in P46 — planning only)

### Pool constants
```python
POWER_LOTTO_FIRST_ZONE_POOL = 38
POWER_LOTTO_FIRST_ZONE_PICK = 6
POWER_LOTTO_SPECIAL_POOL = 8
```

### Adapter input contract
```python
def get_one_bet(
    self,
    history: List[dict],   # strictly causal; each dict has draw/date/numbers/special
    bet_index: int = 0,    # 0 for single-bet strategies; 0..N-1 for multi-bet
) -> Tuple[List[int], Optional[int]]:
    """
    Returns:
      (predicted_numbers: List[int], predicted_special: Optional[int])
      - predicted_numbers: exactly 6 unique ints in [1, 38]
      - predicted_special: int in [1, 8] or None if strategy does not predict special
    """
```

### Per-strategy adapter design (summary)

| strategy_id | Source tools | bet_index | special | Notes |
|-------------|-------------|-----------|---------|-------|
| `pp3_freqort_4bet` | predict_power_orthogonal_5bet.py (bets 0–3) | 0–3 | None | Extract first 4 bets from 5-bet generator |
| `midfreq_fourier_mk_3bet` | power_fourier_rhythm.py + unified_predictor.markov | 0–2 | None | 3-component composite |
| `midfreq_fourier_2bet` | power_fourier_rhythm.py | 0–1 | None | MidFreq bet + Fourier bet |

---

## 9. Next Phase Recommendation

**P47 scope: POWER_LOTTO Wave 4 dry-run + temp rehearsal**

Evidence:
- 3 strategies are ready for bootstrap with LOW–MEDIUM effort
- All 3 have RSM positive edge evidence (pp3_freqort_4bet: +3.40% perm p=0.000; midfreq_fourier_mk_3bet: +1.83% with validated components; midfreq_fourier_2bet: +0.08% marginal but components validated at +2.27%)
- Draw history: 1912 draws available, well above the 1500-draw minimum
- Pool=38 provides better signal per draw than BIG_LOTTO pool=49
- P42/P43 BIG_LOTTO Wave 3 governance pattern is fully established — P47 follows the same sequence

**Estimated new rows:** 3 × 1500 = 4,500 (dry-run only; production apply in P48)

**Governance sequence:**
```
P47: Adapter bootstrap + dry-run (3 strategies × 1500 rows in /tmp/p47_temp.db)
P48: Temp rehearsal → production apply (if P47 analysis passes)
P49: POWER_LOTTO Wave 4 performance analysis
```

**Why not Wave 2 DAILY_539 monitoring (alternative P47):**
DAILY_539 Wave 2 has 6 DRY_RUN strategies accumulating live draws. The monitoring design (DRY_RUN → ONLINE promotion criteria) can be defined concurrently; it does not block POWER_LOTTO expansion. POWER_LOTTO offers higher signal potential (smaller pool) and has no coverage yet for the 3 ready candidates.

---

## 10. What P47 Must NOT Do

- No production apply (`dry_run=0` rows in `lottery_v2.db`)
- No lifecycle promotion to ONLINE for any strategy
- No modification of `replay_strategy_registry._ALL_ADAPTERS` or `_REGISTRY`
- No writes to `lottery_v2.db` main table (rehearsal only in `/tmp/p47_temp.db`)
- No alteration of `CEO-Decision.md`

---

## 11. Forbidden File Scan Result

- `lottery_api/models/p47_wave4_powerlotto_adapters.py` — does NOT exist (correct)
- No dry-run rows generated (production row count = 37960, unchanged)
- No `.db.bak_*` files added

---

*Generated by P46 planning session. All findings are read-only analysis.*
