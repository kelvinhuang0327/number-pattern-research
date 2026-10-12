from analysis.power_lotto.szc1_second_zone_containment_diagnostic import (
    BASELINE,
    bh_correction,
    entropy,
    normal_2sided_p,
    wilson_ci,
)


def test_wilson_ci_bounds_and_order():
    lo, hi = wilson_ci(1, 8)
    assert 0 <= lo <= hi <= 1


def test_entropy_concentrated_less_than_uniform():
    h_conc = entropy({3: 100})
    h_uni = entropy({i: 10 for i in range(1, 9)})
    assert h_conc < h_uni


def test_bh_correction_monotonic_for_sorted_pvals():
    pvals = [0.001, 0.01, 0.04, 0.2]
    qvals = bh_correction(pvals)
    assert all(0 <= q <= 1 for q in qvals)
    assert qvals[0] <= qvals[1] <= qvals[2] <= qvals[3]


def test_pvalue_behaves_near_baseline():
    p_far = normal_2sided_p(0.30, 1000, BASELINE)
    p_near = normal_2sided_p(0.126, 1000, BASELINE)
    assert p_far < p_near
