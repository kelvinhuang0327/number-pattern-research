"""
報告生成器
Report Generator: JSON + Console Text Report
"""
import json
import time
import numpy as np
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path

from .config import MAX_NUM, PICK, n_bet_baseline, TEST_WINDOWS
from .backtest_engine import BacktestResult


class ReportGenerator:
    """生成 JSON + 文字報告"""

    def __init__(self, total_draws: int, seed: int = 42):
        self.total_draws = total_draws
        self.seed = seed
        self.start_time = time.time()

    def generate_json_report(self, phase1_results: List[Dict],
                              phase2_results: List[Dict] = None,
                              fusion_results: Dict = None,
                              overfitting_results: Dict = None,
                              output_path: str = None) -> Dict:
        """生成完整 JSON 報告"""
        runtime = time.time() - self.start_time

        report = {
            'metadata': self._build_metadata(runtime),
            'phase1_leaderboard': self._build_phase1_leaderboard(phase1_results),
            'phase2_discoveries': self._build_phase2_section(phase2_results),
            'dark_horses': self._find_dark_horses(phase1_results),
            'combination_leaderboard': self._build_combination_section(fusion_results),
            'not_recommended': self._build_not_recommended(phase1_results),
            'statistical_tests': self._build_stats_section(phase1_results, overfitting_results),
            'conclusion': self._build_conclusion(phase1_results, phase2_results, fusion_results),
        }

        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)

        return report

    def print_console_report(self, report: Dict):
        """輸出文字報告到 console"""
        print("\n" + "=" * 80)
        print("  大樂透 AutoML 探索系統 — 完整報告")
        print("  BIG_LOTTO AutoML Exploration System — Full Report")
        print("=" * 80)

        # Metadata
        meta = report['metadata']
        print(f"\n📅 Run Date: {meta['run_date']}")
        print(f"📊 Total Draws: {meta['total_draws']}")
        print(f"⏱  Runtime: {meta['runtime_seconds']:.1f}s")
        print(f"🎲 Seed: {meta['seed']}")

        # Phase 1 Leaderboard
        print("\n" + "-" * 80)
        print("  PHASE 1: 已知方法排行榜 (Known Methods Leaderboard)")
        print("-" * 80)
        leaderboard = report.get('phase1_leaderboard', [])
        if leaderboard:
            print(f"\n{'Rank':<5} {'Strategy':<40} {'Bets':<5} {'Edge%':<8} "
                  f"{'z':<7} {'p':<8} {'Type':<12}")
            print("-" * 90)
            for entry in leaderboard[:20]:
                r = entry.get('primary_result', {})
                score = entry.get('scores', {})
                print(f"{entry['rank']:<5} {entry['name'][:39]:<40} "
                      f"{r.get('n_bets', 1):<5} "
                      f"{r.get('edge_pct', 0):>+7.2f} "
                      f"{r.get('z_score', 0):>6.2f} "
                      f"{r.get('p_value', 1):>7.4f} "
                      f"{score.get('classification', 'N/A'):<12}")
        else:
            print("  (No results)")

        # Phase 2 Discoveries
        print("\n" + "-" * 80)
        print("  PHASE 2: 新發現方法 (Novel Discoveries)")
        print("-" * 80)
        discoveries = report.get('phase2_discoveries', [])
        if discoveries:
            for i, d in enumerate(discoveries[:5]):
                print(f"\n  #{i+1} [{d.get('origin', 'GP')}]")
                formula = d.get('formula', 'N/A')
                if len(formula) > 70:
                    formula = formula[:67] + "..."
                print(f"    Formula: {formula}")
                print(f"    Train Edge: {d.get('train_edge', 0)*100:+.2f}%  "
                      f"Test Edge: {d.get('test_edge', 0)*100:+.2f}%")
        else:
            print("  (No discoveries with positive train+test edge)")

        # Dark Horses
        print("\n" + "-" * 80)
        print("  黑馬策略 (Dark Horses)")
        print("-" * 80)
        dark_horses = report.get('dark_horses', [])
        if dark_horses:
            for dh in dark_horses[:5]:
                print(f"  • {dh['name']}: avg_edge={dh.get('avg_edge', 0)*100:+.2f}%, "
                      f"peak_30p={dh.get('peak_30p_rate', 0)*100:.1f}%, "
                      f"burst={dh.get('burst_score', 0):.0f}")
        else:
            print("  (No dark horses found)")

        # Combination Leaderboard
        print("\n" + "-" * 80)
        print("  策略組合排行 (Combination Leaderboard)")
        print("-" * 80)
        combos = report.get('combination_leaderboard', [])
        if combos:
            for i, c in enumerate(combos[:10]):
                strategies = c.get('strategies', [])
                strat_str = ' + '.join(strategies) if strategies else c.get('name', 'N/A')
                if len(strat_str) > 50:
                    strat_str = strat_str[:47] + "..."
                print(f"  #{i+1} {strat_str}")
                print(f"      Edge: {c.get('edge_pct', 0):+.2f}%, "
                      f"z={c.get('z_score', 0):.2f}, "
                      f"bets={c.get('n_bets', 0)}, "
                      f"overlap={c.get('overlap', 0):.2f}")
        else:
            print("  (No combination results)")

        # Not Recommended
        print("\n" + "-" * 80)
        print("  不建議使用 (Not Recommended)")
        print("-" * 80)
        not_rec = report.get('not_recommended', [])
        if not_rec:
            for nr in not_rec[:10]:
                print(f"  ✗ {nr['name']}: edge={nr.get('edge_pct', 0):+.2f}%, "
                      f"reason={nr.get('reason', 'N/A')}")
        else:
            print("  (All strategies have non-negative edge)")

        # Statistical Tests
        print("\n" + "-" * 80)
        print("  統計顯著性檢定 (Statistical Significance)")
        print("-" * 80)
        stats = report.get('statistical_tests', {})
        n_tested = stats.get('n_strategies_tested', 0)
        bonf = stats.get('bonferroni_alpha', 0.05)
        n_pass = stats.get('n_passing_bonferroni', 0)
        print(f"  Strategies tested: {n_tested}")
        print(f"  Bonferroni α: {bonf:.6f}")
        print(f"  Passing Bonferroni: {n_pass}")

        perm_results = stats.get('permutation_results', [])
        if perm_results:
            print(f"\n  排列檢定結果 (Permutation Test Results):")
            for pr in perm_results[:10]:
                print(f"    {pr['name']}: edge={pr.get('real_edge_pct', 0):+.2f}%, "
                      f"p={pr.get('p_value', 1):.3f}, "
                      f"verdict={pr.get('verdict', 'N/A')}")

        decay_results = stats.get('decay_results', [])
        if decay_results:
            print(f"\n  衰減偵測結果 (Decay Detection Results):")
            for dr in decay_results:
                trajectory = dr.get('trajectory', '')
                print(f"    {dr['name']}: [{trajectory}] → {dr.get('verdict', 'N/A')}"
                      f" {'ADOPT' if dr.get('adoptable') else 'REJECT'}")

        # Conclusion
        print("\n" + "=" * 80)
        print("  結論 (Conclusion)")
        print("=" * 80)
        conclusion = report.get('conclusion', {})
        exploitable = conclusion.get('exploitable_pattern_exists', False)
        evidence = conclusion.get('evidence_strength', 'NONE')
        best = conclusion.get('best_strategy', 'N/A')
        rec = conclusion.get('recommendation', 'N/A')

        print(f"  Exploitable Pattern: {'YES' if exploitable else 'NO'}")
        print(f"  Evidence Strength: {evidence}")
        print(f"  Best Strategy: {best}")
        print(f"  Recommendation: {rec}")
        print("=" * 80 + "\n")

    def _build_metadata(self, runtime: float) -> Dict:
        baselines = {}
        for n in [1, 2, 3, 5]:
            baselines[f'{n}_bet'] = round(n_bet_baseline(n) * 100, 2)
        return {
            'run_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_draws': self.total_draws,
            'test_windows': TEST_WINDOWS,
            'baselines_pct': baselines,
            'seed': self.seed,
            'runtime_seconds': round(runtime, 1),
            'max_num': MAX_NUM,
            'pick': PICK,
        }

    def _build_phase1_leaderboard(self, results: List[Dict]) -> List[Dict]:
        """從 Phase 1 結果建立排行榜"""
        if not results:
            return []

        # 排序 by edge_pct (primary result)
        sorted_results = sorted(results,
                                key=lambda x: -x.get('primary_edge_pct', 0))

        leaderboard = []
        for rank, entry in enumerate(sorted_results, 1):
            item = {
                'rank': rank,
                'name': entry.get('name', ''),
                'category': entry.get('category', ''),
                'primary_result': entry.get('primary_result', {}),
                'multi_window_results': entry.get('multi_window_results', {}),
                'scores': entry.get('scores', {}),
            }
            # Flatten primary result fields for convenience
            pr = entry.get('primary_result', {})
            if isinstance(pr, BacktestResult):
                item['primary_result'] = pr.to_dict()
            elif isinstance(pr, dict):
                item['primary_result'] = pr

            leaderboard.append(item)

        return leaderboard

    def _build_phase2_section(self, results: List[Dict] = None) -> List[Dict]:
        if not results:
            return []
        section = []
        for r in results[:20]:
            section.append({
                'formula': r.get('formula', ''),
                'origin': r.get('origin', 'GP'),
                'train_edge': r.get('train_edge', 0),
                'test_edge': r.get('test_edge', 0),
                'depth': r.get('depth', 0),
                'generation': r.get('generation', -1),
            })
        return section

    def _find_dark_horses(self, results: List[Dict]) -> List[Dict]:
        """
        黑馬 = 整體 edge 不高，但 burst 或 peak 表現突出
        """
        if not results:
            return []

        dark_horses = []
        for entry in results:
            pr = entry.get('primary_result', {})
            scores = entry.get('scores', {})

            edge_pct = _safe_get(pr, 'edge_pct', 0)
            burst = _safe_get(scores, 'burst_score', 0)
            peak = _safe_get(pr, 'peak_30p_m3_rate', 0)

            # 黑馬定義：整體 edge < 2% 但 burst >= 40 或 peak > baseline*2
            if edge_pct < 2.0 and (burst >= 40 or peak > _safe_get(pr, 'baseline_rate', 0.02) * 2):
                dark_horses.append({
                    'name': entry.get('name', ''),
                    'avg_edge': _safe_get(pr, 'edge', 0),
                    'peak_30p_rate': peak,
                    'burst_score': burst,
                    'classification': _safe_get(scores, 'classification', 'MIXED'),
                })

        dark_horses.sort(key=lambda x: -x.get('burst_score', 0))
        return dark_horses[:10]

    def _build_combination_section(self, fusion_results: Dict = None) -> List[Dict]:
        if not fusion_results:
            return []

        combos = []
        for section_name in ['pairs', 'triples', 'voting', 'switching', 'dynamic']:
            section = fusion_results.get(section_name, [])
            if isinstance(section, list):
                for item in section[:20]:
                    combos.append({
                        'name': item.get('name', ''),
                        'strategies': item.get('strategies', []),
                        'n_bets': item.get('n_bets', 0),
                        'edge_pct': item.get('edge_pct', 0),
                        'z_score': item.get('z_score', 0),
                        'p_value': item.get('p_value', 1),
                        'overlap': item.get('overlap', 0),
                        'type': section_name,
                    })
            elif isinstance(section, dict):
                # Single result (voting, switching, dynamic)
                r = section.get('result', section)
                combos.append({
                    'name': section_name,
                    'strategies': [],
                    'n_bets': _safe_get(r, 'n_bets', 0),
                    'edge_pct': _safe_get(r, 'edge_pct', 0),
                    'z_score': _safe_get(r, 'z_score', 0),
                    'p_value': _safe_get(r, 'p_value', 1),
                    'overlap': 0,
                    'type': section_name,
                })

        combos.sort(key=lambda x: -x.get('edge_pct', 0))
        return combos

    def _build_not_recommended(self, results: List[Dict]) -> List[Dict]:
        if not results:
            return []

        not_rec = []
        for entry in results:
            pr = entry.get('primary_result', {})
            edge_pct = _safe_get(pr, 'edge_pct', 0)
            p_value = _safe_get(pr, 'p_value', 1)
            half1 = _safe_get(pr, 'half1_edge', 0)
            half2 = _safe_get(pr, 'half2_edge', 0)

            reasons = []
            if edge_pct < 0:
                reasons.append(f'negative edge ({edge_pct:+.2f}%)')
            if p_value > 0.5:
                reasons.append(f'not significant (p={p_value:.3f})')
            if half1 > 0 and half2 < -0.01:
                reasons.append('possibly overfit (half2 negative)')
            if half2 > 0 and half1 < -0.01:
                reasons.append('possibly overfit (half1 negative)')

            if reasons:
                not_rec.append({
                    'name': entry.get('name', ''),
                    'edge_pct': edge_pct,
                    'reason': '; '.join(reasons),
                })

        not_rec.sort(key=lambda x: x.get('edge_pct', 0))
        return not_rec[:30]

    def _build_stats_section(self, results: List[Dict],
                              overfitting_results: Dict = None) -> Dict:
        n_tested = len(results) if results else 0
        bonf_alpha = 0.05 / n_tested if n_tested > 0 else 0.05

        # Count passing Bonferroni
        n_passing = 0
        if results:
            for entry in results:
                pr = entry.get('primary_result', {})
                p = _safe_get(pr, 'p_value', 1)
                if p < bonf_alpha:
                    n_passing += 1

        section = {
            'n_strategies_tested': n_tested,
            'bonferroni_alpha': bonf_alpha,
            'n_passing_bonferroni': n_passing,
            'permutation_results': [],
            'noise_results': [],
        }

        if overfitting_results:
            perm = overfitting_results.get('permutation', {})
            for name, pr in perm.items():
                section['permutation_results'].append({
                    'name': name,
                    'real_edge_pct': pr.get('real_edge_pct', 0),
                    'shuffle_mean': pr.get('shuffle_mean', 0),
                    'p_value': pr.get('p_value', 1),
                    'cohens_d': pr.get('cohens_d', 0),
                    'verdict': pr.get('verdict', 'N/A'),
                })

            noise = overfitting_results.get('noise', {})
            for name, nr in noise.items():
                section['noise_results'].append({
                    'name': name,
                    'real_edge': nr.get('real_edge', 0),
                    'overall_robust': nr.get('overall_robust', False),
                    'levels': nr.get('levels', {}),
                })

            # Decay results
            decay = overfitting_results.get('decay', {})
            decay_list = []
            for name, dr in decay.items():
                trajectory = ' -> '.join(f"{e:+.2f}%" for e in dr.get('edge_trajectory', []))
                decay_list.append({
                    'name': name,
                    'verdict': dr.get('verdict', 'N/A'),
                    'adoptable': dr.get('adoptable', False),
                    'decay_ratio': dr.get('decay_ratio', 0),
                    'trajectory': trajectory,
                    'windows': dr.get('sorted_windows', []),
                })
            section['decay_results'] = decay_list
            section['n_decay_adoptable'] = sum(1 for d in decay_list if d.get('adoptable'))

        return section

    def _build_conclusion(self, phase1_results: List[Dict],
                           phase2_results: List[Dict] = None,
                           fusion_results: Dict = None) -> Dict:
        # Determine best strategy
        best_name = 'N/A'
        best_edge = 0
        best_p = 1.0

        if phase1_results:
            sorted_r = sorted(phase1_results,
                              key=lambda x: -x.get('primary_edge_pct', 0))
            if sorted_r:
                top = sorted_r[0]
                best_name = top.get('name', 'N/A')
                best_edge = top.get('primary_edge_pct', 0)
                pr = top.get('primary_result', {})
                best_p = _safe_get(pr, 'p_value', 1)

        # Evidence strength
        n_tested = len(phase1_results) if phase1_results else 0
        bonf_alpha = 0.05 / n_tested if n_tested > 0 else 0.05

        if best_p < bonf_alpha and best_edge > 1.0:
            evidence = 'STRONG'
            exploitable = True
        elif best_p < 0.05 and best_edge > 0.5:
            evidence = 'MODERATE'
            exploitable = True
        elif best_p < 0.10 and best_edge > 0:
            evidence = 'WEAK'
            exploitable = False
        else:
            evidence = 'NONE'
            exploitable = False

        # Recommendation
        if exploitable and evidence == 'STRONG':
            recommendation = (
                f"Strategy '{best_name}' shows statistically significant edge "
                f"of {best_edge:+.2f}% (p={best_p:.4f}). "
                f"Passes Bonferroni correction. Consider for production use with "
                f"continued monitoring."
            )
        elif exploitable:
            recommendation = (
                f"Strategy '{best_name}' has edge {best_edge:+.2f}% (p={best_p:.4f}). "
                f"Signal is present but may not survive multiple testing correction. "
                f"Use with caution and monitor performance."
            )
        else:
            recommendation = (
                f"No strategy shows reliably exploitable edge after correction. "
                f"Best observed: '{best_name}' at {best_edge:+.2f}%. "
                f"Recommend continued research or combination strategies."
            )

        # Check fusion
        best_combo_edge = 0
        best_combo_name = 'N/A'
        if fusion_results:
            for section_name in ['pairs', 'triples']:
                section = fusion_results.get(section_name, [])
                if isinstance(section, list) and section:
                    top = section[0]
                    e = top.get('edge_pct', 0)
                    if e > best_combo_edge:
                        best_combo_edge = e
                        best_combo_name = top.get('name', 'N/A')

        return {
            'exploitable_pattern_exists': exploitable,
            'evidence_strength': evidence,
            'best_strategy': best_name,
            'best_edge_pct': best_edge,
            'best_p_value': best_p,
            'best_combination': best_combo_name,
            'best_combo_edge_pct': best_combo_edge,
            'recommendation': recommendation,
        }


def _safe_get(obj: Any, key: str, default=0):
    """安全取值，支援 dict 和 dataclass"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)
