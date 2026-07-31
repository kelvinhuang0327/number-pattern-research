# P356A Phase 0 Evidence

- Standalone Owner authorization: [Confirmed]
- Canonical repo: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`
- Canonical cwd: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`
- Canonical branch: `task/p273a-prize-aware-inferential-validation`
- Canonical HEAD: `3d6df001da3a0633ab91f164d722b595ca76d2e1`
- local main: `ce2c042e7f4967841e6b31e17552d55bf4717f91`
- origin/main: `e3265ad4baeb35d0e8e60d6df5915bdd4ddfa855`
- main...origin/main left/right: `0	6`
- Target worktree exists after Phase 1: `True`
- Branch exists after Phase 1: `True`

## Canonical Git Status
```text
M 00-Plan/roadmap/agent_bootstrap/SHARED_AGENT_BOOTSTRAP.md
 M 00-Plan/roadmap/agent_bootstrap/TASK_TEMPLATES.md
 M backend.pid
 M claude-code-showcase
 M data/lottery_v2.db
 M frontend.pid
 M index.html
 M lottery_api/data/performance_history.json
 M lottery_api/routes/replay.py
?? .gstack/
?? ".schema strategy_replay_runs"
?? analysis/p333_strategy_pick_combination_scoreboard.py
?? claude-code-showcase.worktrees/
?? data/performance_history.json
?? lottery_api/data/ingest_log.jsonl
?? outputs/research/p245a_external_predictive_method_scouting_20260605.json
?? outputs/research/p245a_external_predictive_method_scouting_20260605.md
?? outputs/research/p251d_evidence_dashboard_readonly_api_route_20260609.json
?? outputs/research/p251d_evidence_dashboard_readonly_api_route_20260609.md
?? outputs/research/p333_strategy_pick_combination_scoreboard_20260702.json
?? outputs/research/p333_strategy_pick_combination_scoreboard_20260702.md
?? runtime/
?? tests/test_p245a_external_predictive_method_scouting.py
?? tests/test_p333_strategy_pick_combination_scoreboard.py
```

## Open PR Status
```json
[{"baseRefName":"main","headRefName":"task/p282b-big649-deduplicated-portfolio-replay","number":467,"state":"OPEN","title":"research(p282b): replay deduplicated big649 portfolio","url":"https://github.com/kelvinhuang0327/number-pattern-research/pull/467"},{"baseRefName":"main","headRefName":"task/p280aw-big649-private-ticket-decision-runner","number":465,"state":"OPEN","title":"feat(p280aw): add private BIG ticket decision runner","url":"https://github.com/kelvinhuang0327/number-pattern-research/pull/465"},{"baseRefName":"main","headRefName":"task/p280amr-big649-local-replay-research","number":462,"state":"OPEN","title":"research(p280amr): replay BIG strategy combinations","url":"https://github.com/kelvinhuang0327/number-pattern-research/pull/462"},{"baseRefName":"main","headRefName":"task/p274d-pre-g2-acceptance-evidence-gate-verification","number":444,"state":"OPEN","title":"P274D verify pre-G2 acceptance evidence gates","url":"https://github.com/kelvinhuang0327/number-pattern-research/pull/444"}]
```

## DB Read-Only Evidence
- Selected DB: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db`
- Immutable URI: `file:/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db?mode=ro&immutable=1`
- DB SHA256: `b1d80e31f490a5a7595a91593641a8df9d488e0be243dc7bf74624dce3c25ee2`
- Draw row count: `33362`
- Schema dump hash: `d714605f75cdec193b87e2b08c479dbe2aeac96cced2a60e001c607be8307150`
- strategy_prediction_replays rows: `94924`
- strategy_replay_runs rows: `10`
- Distinct DB strategy IDs: `42`

## DB Strategy IDs
```text
539_3bet_orthogonal
acb_1bet
acb_markov_midfreq
acb_markov_midfreq_3bet
acb_single_539
bet2_fourier_expansion_biglotto
biglotto_deviation_2bet
biglotto_echo_aware_3bet
biglotto_triple_strike
biglotto_triple_strike,biglotto_deviation_2bet
biglotto_ts3_markov_4bet_w30
cold_complement_2bet
cold_complement_biglotto
coldpool15_biglotto
daily539_f4cold
daily539_f4cold,daily539_markov_cold
daily539_f4cold_3bet
daily539_f4cold_5bet
daily539_markov_cold
f4cold_5bet
fourier30_markov30_2bet
fourier30_markov30_biglotto
fourier_rhythm_2bet
fourier_rhythm_3bet
fourier_rhythm_3bet,power_precision_3bet,power_orthogonal_5bet
markov_1bet_539
markov_2bet_biglotto
markov_single_biglotto
midfreq_acb_2bet
midfreq_fourier_2bet
midfreq_fourier_mk_3bet
orthogonal_5bet
power_fourier_rhythm_2bet
power_orthogonal_5bet
power_precision_3bet
power_precision_3bet,power_orthogonal_5bet
pp3_freqort_4bet
regime_2bet
ts3_regime_3bet
ts3_regime_3bet,biglotto_triple_strike,biglotto_deviation_2bet
zonal_entropy_2bet
zone_gap_3bet_539
```
