"""Quarantined Big Lotto historical recovery adapters."""

from .historical_adapters import (
    ADAPTER_METADATA,
    adapt_biglotto_10bet_combined,
    adapt_biglotto_5bet_orthogonal,
    adapt_biglotto_p0_2bet,
    adapt_biglotto_zonal_pruning,
    adapt_predict_biglotto_echo_2bet,
    adapt_predict_biglotto_echo_mixed_3bet,
    adapt_predict_biglotto_echo_phase2_2bet,
    adapt_predict_biglotto_echo_phase2_3bet,
    adapt_predict_biglotto_regime_3bet,
)

__all__ = [
    "ADAPTER_METADATA",
    "adapt_biglotto_10bet_combined",
    "adapt_biglotto_5bet_orthogonal",
    "adapt_biglotto_p0_2bet",
    "adapt_biglotto_zonal_pruning",
    "adapt_predict_biglotto_echo_2bet",
    "adapt_predict_biglotto_echo_mixed_3bet",
    "adapt_predict_biglotto_echo_phase2_2bet",
    "adapt_predict_biglotto_echo_phase2_3bet",
    "adapt_predict_biglotto_regime_3bet",
]
