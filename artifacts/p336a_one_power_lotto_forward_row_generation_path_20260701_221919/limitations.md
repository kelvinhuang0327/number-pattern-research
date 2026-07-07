# P336A — Limitations

1. **Not yet persisting.** The path *generates* a guarded, non-NULL-second-zone
   row but deliberately does **not** write it to any database. Actually recording
   forward POWER_LOTTO rows requires a separately-authorized persistence step
   (BLOCKER-2: the pipeline has been dormant since 2026-05-29). Until then the
   27,104 existing historical NULL rows remain (correctly, by no-backfill policy).

2. **First-zone is an input, not computed by this module.** The builder is
   second-zone-focused (the whole P333–P335 arc's concern). A caller must supply
   `predicted_numbers` from an existing first-zone predictor. The complete-path
   test wires a real p47 `predict_midfreq_fourier_mk_3bet_bet1`, but the module
   itself does not pick a canonical first-zone strategy — that binding is left to
   the (separately-authorized) pipeline-resume.

3. **No new call site is exercised in production.** Nothing on origin/main calls
   `build_power_lotto_forward_replay_row` yet; it is the reusable path the resume
   will adopt. (This is intentional — wiring a *running* pipeline is out of scope.)

4. **Ordering convention is inherited, not reconciled.** `PowerLottoSpecialPredictor`
   internally treats `history[0]` as most-recent while the p47 first-zone helpers
   treat `history[-1]` as most-recent. P336A passes `history` to the P335A helper
   exactly as P335A's validated tests do and makes **no prediction-quality claim**,
   so this pre-existing convention difference does not affect correctness of the
   coverage plumbing (values are valid and deterministic either way). Reconciling
   it is not in scope.

5. **DB-backed existing tests NOT RUN.** The canonical 99 MB DB is untracked and
   absent in a fresh origin/main worktree, so one pre-existing p47 DB fixture
   errors (proven non-causal to this change). P336A's own tests need no DB.

6. **No edge / McNemar / significance claim.** Prior POWER second-zone findings
   remain negative; P336A changes only NULL *coverage* mechanics, not predictive
   value.

7. **Not committed, not pushed.** Left uncommitted for review; push is gated on
   separate Owner authorization.
