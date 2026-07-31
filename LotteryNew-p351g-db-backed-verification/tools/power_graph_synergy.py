#!/usr/bin/env python3
"""
Power Lotto Graph Synergy Researcher
=====================================
Logic:
1. Create a co-occurrence graph where nodes are balls (1-38).
2. Edge weights are defined by how many times balls appeared together.
3. Use Louvain Community Detection to find "Clans".
4. Evaluate if selecting from strong clans yields a positive Edge.
"""
import os
import sys
import numpy as np
import networkx as nx
from community import community_louvain 

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.strategy_leaderboard import StrategyLeaderboard

def analyze_graph_communities(history, window=500):
    G = nx.Graph()
    G.add_nodes_from(range(1, 39))
    
    h_slice = history[-window:]
    for d in h_slice:
        nums = d['numbers']
        for i in range(len(nums)):
            for j in range(i + 1, len(nums)):
                u, v = nums[i], nums[j]
                if G.has_edge(u, v):
                    G[u][v]['weight'] += 1
                else:
                    G.add_edge(u, v, weight=1)
                    
    # Louvain Partition
    partition = community_louvain.best_partition(G, weight='weight')
    
    # Group by community
    communities = {}
    for node, comm_id in partition.items():
        if comm_id not in communities:
            communities[comm_id] = []
        communities[comm_id].append(node)
        
    return communities

def graph_clancy_predict(history, n_bets=2, window=500):
    comms = analyze_graph_communities(history, window=window)
    
    # Strategy: Find the "hottest" or "most stable" community?
    # For now, we take numbers from the largest communities (clans)
    sorted_comm_ids = sorted(comms.keys(), key=lambda k: len(comms[k]), reverse=True)
    
    bets = []
    # Bet 1: Pool from top 2 clans
    pool1 = []
    for cid in sorted_comm_ids[:min(2, len(sorted_comm_ids))]:
        pool1.extend(comms[cid])
    
    # Sort by frequency within history to pick members
    from collections import Counter
    recent = history[-window:]
    freq = Counter([n for d in recent for n in d['numbers']])
    
    pool1_sorted = sorted(pool1, key=lambda x: freq.get(x, 0), reverse=True)
    if len(pool1_sorted) >= 6:
        bets.append(sorted(pool1_sorted[:6]))
    else:
        # fallback
        bets.append(sorted(range(1, 7)))
        
    # Bet 2: Mixed diversity from across clans
    pool2 = []
    for cid in comms:
        # Pick 1-2 from each
        clan_members = sorted(comms[cid], key=lambda x: freq.get(x, 0), reverse=True)
        pool2.extend(clan_members[:2])
    
    if len(pool2) >= 6:
        bets.append(sorted(pool2[:6]))
    else:
        bets.append(sorted(range(7, 13)))
        
    return bets[:n_bets]

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--n', type=int, default=500)
    args = parser.parse_args()
    
    from tools.verify_strategy_longterm import UnifiedAuditor
    auditor = UnifiedAuditor(lottery_type='POWER_LOTTO')
    
    def audit_bridge(history, num_bets=2):
        return graph_clancy_predict(history, n_bets=num_bets)
        
    auditor.audit(audit_bridge, n=args.n, num_bets=2)
