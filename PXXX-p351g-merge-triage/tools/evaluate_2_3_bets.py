import sys
import numpy as np
import time
from evolving_strategy_engine.data_loader import load_big_lotto_draws
from generate_2_3_bets import generate_orthogonal_bets

def evaluate_predictions(draws, n_bets=2, n_test=1500):
    total_draws = len(draws)
    start_idx = max(500, total_draws - n_test)
    
    hits_M3_plus = 0
    total_bets = 0
    
    for i in range(start_idx, total_draws - 1):
        train_draws = draws[:i]
        actual_draw = set(draws[i])
        
        _, bets = generate_orthogonal_bets(train_draws, n_bets)
        
        for bet in bets:
            hit = len(set(bet) & actual_draw)
            if hit >= 3:
                hits_M3_plus += 1
            total_bets += 1
            
    # Baseline for M3+ is 0.0186 per bet
    # If we evaluate hit rate per bet:
    hit_rate = hits_M3_plus / total_bets
    edge = hit_rate - 0.0186
    
    # If we evaluate hit rate per draw (at least 1 ticket wins M3+)
    hits_per_draw = 0
    for i in range(start_idx, total_draws - 1):
        train_draws = draws[:i]
        actual_draw = set(draws[i])
        _, bets = generate_orthogonal_bets(train_draws, n_bets)
        won_draw = any(len(set(bet) & actual_draw) >= 3 for bet in bets)
        if won_draw:
            hits_per_draw += 1
            
    draw_win_rate = hits_per_draw / (total_draws - 1 - start_idx)
    # The chance of at least 1 ticket winning if tickets were independent: 1 - (1-0.0186)^n_bets
    # For 2 tickets: 1 - 0.9814^2 = 0.0368
    # For 3 tickets: 1 - 0.9814^3 = 0.0548
    expected_draw_win = 1 - (1 - 0.0186)**n_bets
    draw_edge = draw_win_rate - expected_draw_win
    
    return hit_rate, edge, draw_win_rate, draw_edge

if __name__ == '__main__':
    draws, _ = load_big_lotto_draws()
    print("Running 1500p backtest for 2-bet...")
    t0 = time.time()
    hr_2, edge_2, dwr_2, dedge_2 = evaluate_predictions(draws, 2, 1500)
    print(f"2-bet | Per bet Edge: {edge_2:+.4f} | Per draw (2 bets) Edge vs Baseline(3.68%): {dedge_2:+.4f} | {time.time()-t0:.1f}s")
    
    print("Running 1500p backtest for 3-bet...")
    t0 = time.time()
    hr_3, edge_3, dwr_3, dedge_3 = evaluate_predictions(draws, 3, 1500)
    print(f"3-bet | Per bet Edge: {edge_3:+.4f} | Per draw (3 bets) Edge vs Baseline(5.48%): {dedge_3:+.4f} | {time.time()-t0:.1f}s")
