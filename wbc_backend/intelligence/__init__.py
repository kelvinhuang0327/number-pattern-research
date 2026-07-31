"""
Institutional Betting Intelligence System
==========================================
10-phase decision pipeline for professional sports betting.

Modules:
  1.  edge_validator         — Edge validity scoring (0-100)
  1b. edge_realism_filter    — Market-execution realism gate (0-100)
  1c. edge_decay_predictor   — Edge half-life & urgency prediction
  1d. line_movement_predictor — Line direction & timing recommendation
  1e. market_impact_simulator — Execution slippage & risk simulation
  2.  regime_classifier      — Market regime classification (5 regimes)
  3.  bet_selector           — Multi-gate bet selection
  4.  position_sizing_ai     — Dynamic position sizing (5 strategies)
  5.  meta_learning_loop     — Self-improving model management
  6.  sharpness_monitor      — CLV tracking & staleness detection
  7.  risk_engine            — Institutional risk limits
  8.  decision_engine        — Master orchestrator → Decision Report
"""
from wbc_backend.intelligence.decision_engine import (  # noqa: F401
    InstitutionalDecisionEngine,
    DecisionReport,
    format_decision_report,
)
from wbc_backend.intelligence.edge_realism_filter import (  # noqa: F401
    assess_edge_realism,
    RealismInput,
    RealismReport,
    RealEdgeLabel,
    REALISM_THRESHOLD,
)
from wbc_backend.intelligence.edge_decay_predictor import (  # noqa: F401
    predict_edge_decay,
    EdgeDecayInput,
    EdgeDecayForecast,
    UrgencyLevel,
    LEAGUE_DECAY_PROFILES,
)
from wbc_backend.intelligence.market_impact_simulator import (  # noqa: F401
    simulate_market_impact,
    MarketImpactInput,
    MarketImpactReport,
    ExecutionStrategy,
)
