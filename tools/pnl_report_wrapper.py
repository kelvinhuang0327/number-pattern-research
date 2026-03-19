import json
import os
import sys

# Setup paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from tools.roi_pnl_analyzer import ROIPnLAnalyzer

def run_pnl_report(results_path: str):
    if not os.path.exists(results_path):
        print(f"Error: Path {results_path} does not exist.")
        return

    with open(results_path, 'r') as f:
        results = json.load(f)

    analyzer = ROIPnLAnalyzer()
    stats = analyzer.analyze_results(results)
    analyzer.print_report(stats)

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/backtest_results_roi.json"
    run_pnl_report(path)
