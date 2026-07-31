"""D3 ``AdversarialNullSurvivorGate`` read-only skeleton (P258E).

THIS IS SCAFFOLDING ONLY. There is no executable gate here.

Mandatory interpretation (from P258B/P258C/P258D):
- D3 is a VALIDATION / adversarial-null survivor gate, NOT a prediction model.
- D3 cannot claim improved prediction accuracy.
- D3 cannot approve production. Passing the gate means only "not yet rejected",
  NEVER "approved".
- D3 cannot touch recommendation logic, write the DB, or trigger
  controlled_apply / deployment.

This package exposes only:
- ``schemas``: typed dataclasses + a 2-value status enum (REJECTED / NOT_YET_REJECTED).
- ``gate_validation``: validation stubs that raise ``NotImplementedError``.

It contains no scoring, no null generation, no paired tests, no p-value
computation, no candidate evaluation, and no backtest loop. Those remain
forbidden until a separate, explicitly authorized task (P258F+).
"""
