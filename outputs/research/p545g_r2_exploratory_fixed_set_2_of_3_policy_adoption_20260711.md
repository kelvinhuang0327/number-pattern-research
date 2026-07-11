# P545G R2 Exploratory Fixed-Set 2-of-3 Policy Adoption

## Decision

All three scoped DAILY_539 cells satisfy `EXPLORATORY_FIXED_SET_NULL_2_OF_3.v1`. This is an Owner-directed post-hoc exploratory policy, not a pre-registered confirmatory rule. Separately, none survives the original Bonferroni family of 108 under the fixed-set null.

## Policy

A window passes when it is evaluable, observed successes exceed fixed-set expected successes, and its one-sided raw upper-tail p-value is at most 0.05. A cell passes when at least two of SHORT/MID/LONG pass, at least one passing window is MID or LONG, and no window has correction-surviving negative evidence.

## Nine-window calculation matrix

| Cell | Window | Observed | Committed expected | Fixed expected | Difference | Committed raw p | Fixed raw p | Committed Bonf. p | Fixed Bonf. p | Exploratory pass | Confirmatory survives |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|:---:|
| `daily539_f4cold_5bet` | SHORT 50 | 35 | 22.697478187487 | 25.801249485460011775801249485460 | 3.103771297973 | 0.000381226046 | 0.006358612173812848373113204317 | 0.041172412978 | 0.686730114771787624296226066254 | PASS | NO |
| `daily539_f4cold_5bet` | MID 300 | 170 | 136.184869124920 | 154.807496912760070654807496912760 | 18.622627787840 | 0.000058213025 | 0.044614780019457699148198815648 | 0.006287006658 | 1.000000000000000000000000000000 | PASS | NO |
| `daily539_f4cold_5bet` | LONG 750 | 425 | 340.462172812300 | 387.018742281900176637018742281900 | 46.556569469600 | 0.000000000394 | 0.003042232920669618446024340700 | 0.000000042577 | 0.328561155432318792170628795651 | PASS | NO |
| `daily539_f4cold_3bet` | SHORT 50 | 23 | 15.221571787131 | 16.288382077855762066288382077856 | 1.066810290725 | 0.014728714530 | 0.032821272974945158794154987574 | 1.000000000000 | 1.000000000000000000000000000000 | PASS | NO |
| `daily539_f4cold_3bet` | MID 300 | 101 | 91.329430722788 | 97.730292467134572397730292467135 | 6.400861744347 | 0.125439796816 | 0.364129621830438705595848114322 | 1.000000000000 | 1.000000000000000000000000000000 | FAIL | NO |
| `daily539_f4cold_3bet` | LONG 750 | 275 | 228.323576806969 | 244.325731167836430994325731167836 | 16.002154360867 | 0.000154628222 | 0.009845382595326627400054747186 | 0.016699848026 | 1.000000000000000000000000000000 | PASS | NO |
| `acb_markov_midfreq_3bet` | SHORT 50 | 18 | 15.221571787131 | 15.852580168369642053852580168370 | 0.631008381239 | 0.238834823753 | 0.303586885909572890047551152732 | 1.000000000000 | 1.000000000000000000000000000000 | FAIL | NO |
| `acb_markov_midfreq_3bet` | MID 300 | 120 | 91.329430722788 | 94.975840502156291629975840502156 | 3.646409779368 | 0.000273545139 | 0.001387404030053310520923596022 | 0.029542875032 | 0.149839635245757536259748370334 | PASS | NO |
| `acb_markov_midfreq_3bet` | LONG 750 | 268 | 228.323576806969 | 237.609272661904240851609272661904 | 9.285695854935 | 0.001075920688 | 0.009991285833279449231165609443 | 0.116199434329 | 1.000000000000000000000000000000 | PASS | NO |

## Retained exploratory candidates

- `daily539_f4cold_5bet`: RETAINED_EXPLORATORY_CANDIDATE; passing windows = SHORT, MID, LONG; original Bonferroni-108 result = DOES_NOT_SURVIVE.
- `daily539_f4cold_3bet`: RETAINED_EXPLORATORY_CANDIDATE; passing windows = SHORT, LONG; original Bonferroni-108 result = DOES_NOT_SURVIVE.
- `acb_markov_midfreq_3bet`: RETAINED_EXPLORATORY_CANDIDATE; passing windows = MID, LONG; original Bonferroni-108 result = DOES_NOT_SURVIVE.

## Exact method and evidence scope

The P545C R4 registry at `a5b1b12ddcd0c8c18ebcb9aff2e8d5ab7708fac0` is the sole row-level input. The canonical P545B artifact is used only to reconcile the frozen memberships, observed successes, and committed comparison fields. Each fixed-set numerator is computed by integer category DP over the 39-number membership geometry. Window tails use deterministic integer Poisson-binomial DP; 100-digit Decimal rendering is independently checked against float DP within 1e-12.

The JSON companion publishes all 2,250 per-draw ticket sets, geometry signatures, exact favorable numerators, nine exact tail rationals, geometry diagnostics, and input identities.

## P544D gate

`DESIGN_ONLY_GATE_OPEN`: a separately authorized task may draft a predefined P544D design using exactly these three retained exploratory candidates. Combination generation or evaluation is not authorized here and was not performed.

## Safety and limitations

No database, snapshot, SQLite, network, strategy combination, candidate expansion, or threshold tuning was used. This document makes no predictive-validity, ROI, EV, staking, purchase, deployment, or betting claim.

Canonical payload digest: `5fd24575ea22747bdfd117a33a3fbf3751b928dcca75d57a590cabb04fcf982f`
