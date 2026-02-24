import sys
import os
import numpy as np
import time
import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evolving_strategy_engine.data_loader import load_big_lotto_draws
from evolving_strategy_engine.strategy_base import FeatureLibrary

# ==========================================
# 策略發現引擎：Graph Topology (Centrality) 研究
# ==========================================

def run_graph_topology_discovery(draws, n_test=500):
    print(f"🔍 [Engine] Graph Centrality Discovery (N={len(draws)})")
    
    hits = 0
    plays = 0
    
    for i in range(len(draws) - n_test, len(draws)):
        hist = draws[:i]
        actual = set(draws[i])
        
        # 1. 建立共現矩陣 (Co-occurrence Matrix)
        comat = FeatureLibrary.co_occurrence(hist, window=100)
        
        # 2. 轉換為 NetworkX 圖形
        G = nx.from_numpy_array(comat)
        
        # 3. 計算特徵向量中心性 (Eigenvector Centrality)
        # 這能找出哪些號碼是當前網絡中的「核心節點 (Hubs)」
        try:
            centrality = nx.eigenvector_centrality(G, max_iter=500, weight='weight')
            scores = np.array([centrality[node] for node in range(49)])
        except:
            # Fallback to Degree Centrality if no convergence
            centrality = nx.degree_centrality(G)
            scores = np.array([centrality[node] for node in range(49)])
            
        # 選取中心性最高的 6 顆球 (Hubs)
        pred = np.argsort(scores)[-6:] + 1
        
        correct = len(set(pred) & actual)
        hits += correct
        plays += 6
        
    rate = (hits / plays) if plays > 0 else 0
    edge = rate - (6/49)
    
    print(f"\n📊 [Graph Centrality Results]")
    print(f"   M1+ Hit Rate: {rate*100:.2f}%")
    print(f"   Edge vs Random: {edge*100:+.2f}%")
    
    return edge

if __name__ == "__main__":
    t0 = time.time()
    try:
        draws, _ = load_big_lotto_draws()
        if len(draws) > 200:
            run_graph_topology_discovery(draws)
        else:
            print("Data too short.")
    except Exception as e:
        print(f"Error: {e}")
    print(f"\n⏱️ Elapsed: {time.time()-t0:.1f}s")
