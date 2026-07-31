"""Phase 4 debug: check analysis_allowed for C01 and verify research capture fires from main.py."""
import os
os.environ["RESEARCH_MODE"] = "1"

from data.wbc_pool_c import fetch_wbc_match
from wbc_backend.config.settings import AppConfig
from wbc_backend.data.wbc_verification import verify_game_artifact, WBCDataVerificationError

m = fetch_wbc_match("C01")
print(f"data_source: {m.data_source!r}")

try:
    vr = verify_game_artifact(
        game_id="C01",
        expected_home=m.home.code,
        expected_away=m.away.code,
        expected_game_time=m.game_time,
        expected_home_sp=m.home_sp.name,
        expected_away_sp=m.away_sp.name,
        expected_home_lineup=[p.name for p in m.home_lineup],
        expected_away_lineup=[p.name for p in m.away_lineup],
        data_source=m.data_source,
        snapshot_path=AppConfig().sources.wbc_authoritative_snapshot_json,
    )
    print(f"verify status={vr.status} blocking={vr.blocking}")
except WBCDataVerificationError as e:
    vr = e.result
    print(f"verify status={vr.status} blocking={vr.blocking}")
    for iss in vr.issues:
        print(f"  issue: {iss.code} severity={iss.severity} msg={iss.message[:80]}")

has_real = not any(t in (m.data_source or "").upper() for t in ("MOCK", "SEED", "MIXED"))
analysis_allowed = vr is not None and not vr.blocking and has_real
print(f"has_only_real_data: {has_real}")
print(f"analysis_allowed: {analysis_allowed}")

# Now test the shim directly
if analysis_allowed:
    print("\n--- Testing research capture shim ---")
    import types
    from research import is_research_mode_enabled
    from research.layer import capture as rc
    from wbc_backend.pipeline.prediction_orchestrator import PredictionOrchestrator

    print(f"research enabled: {is_research_mode_enabled()}")
    home_ml = next((o.decimal_odds for o in m.odds if o.market == "ML" and o.side == m.home.code), None)
    market_home_p = (1.0 / home_ml) if home_ml else 0.5
    print(f"home_ml={home_ml}  market_home_p={market_home_p}")

    rec = types.SimpleNamespace(
        game_id="C01",
        home_team=m.home.code,
        away_team=m.away.code,
        round_name=m.round_name,
        home_elo=getattr(m.home, "elo", None),
        away_elo=getattr(m.away, "elo", None),
        home_woba=getattr(m.home, "woba", None),
        away_woba=getattr(m.away, "woba", None),
        home_fip=getattr(m.home_sp, "fip", None),
        away_fip=getattr(m.away_sp, "fip", None),
        market_home_prob=market_home_p,
        odds={},
        league="WBC",
    )
    orc_result = PredictionOrchestrator().predict(rec, use_world_model=False, use_hierarchical_mc=False)
    print(f"home_win_prob={orc_result.home_win_prob:.4f} rec_side={orc_result.recommended_side}")
    out = rc(orc_result, record=rec)
    print(f"capture: active={out.get('active')} captured={out.get('captured')}")
    print(f"ledger_path: {out.get('ledger_path')}")
else:
    print("\nSkipping shim test — analysis_allowed=False")
    print("Reason: verification blocked or non-real data")
