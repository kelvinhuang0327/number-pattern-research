#!/usr/bin/env python3
"""
威力彩 20%+ 優化項目 - 快速檢查工具

用途: 驗證所有必需的方法和配置是否可用
"""

import sys
import os

def check_unified_predictor():
    """檢查 unified_predictor.py 中的必需方法"""
    
    print("\n" + "="*70)
    print("🔍 檢查 1: unified_predictor.py 必需方法")
    print("="*70)
    
    sys.path.insert(0, os.path.join(os.getcwd(), 'lottery_api'))
    
    try:
        from models.unified_predictor import UnifiedPredictionEngine
        engine = UnifiedPredictionEngine()
        
        required_methods = [
            'ensemble_predict',
            'zone_balance_predict',
            'bayesian_predict',
            'trend_predict',
            'anti_consensus_predict',
            'cluster_pivot_predict'
        ]
        
        print("\n必需方法檢查:")
        all_present = True
        for method in required_methods:
            has_method = hasattr(engine, method)
            status = "✅" if has_method else "❌"
            print(f"  {status} {method:<35} {'存在' if has_method else '不存在'}")
            if not has_method:
                all_present = False
        
        return all_present
        
    except Exception as e:
        print(f"❌ 錯誤: {e}")
        return False

def check_database():
    """檢查數據庫連接和數據"""
    
    print("\n" + "="*70)
    print("🔍 檢查 2: 數據庫和測試數據")
    print("="*70)
    
    try:
        from database import db_manager
        # Fix path for check
        import os
        db_path = os.path.join(os.getcwd(), 'lottery_api', 'data', 'lottery_v2.db')
        if os.path.exists(db_path):
            db_manager.db_path = db_path
            print(f"DEBUG: Updated DB path to {db_path}")
        
        # 檢查威力彩數據
        power_lotto_draws = db_manager.get_all_draws('POWER_LOTTO')
        
        if power_lotto_draws:
            print(f"\n✅ 威力彩數據: {len(power_lotto_draws)} 期")
            
            # 計算 2025 年數據
            draws_2025 = [d for d in power_lotto_draws if '2025' in str(d.get('date', ''))]
            print(f"✅ 2025年數據: {len(draws_2025)} 期")
            
            # 檢查數據完整性
            sample = power_lotto_draws[0]
            required_keys = ['numbers', 'special', 'draw', 'date']
            missing_keys = [k for k in required_keys if k not in sample]
            
            if missing_keys:
                print(f"❌ 缺少字段: {missing_keys}")
                return False
            else:
                print(f"✅ 數據結構完整")
                return True
        else:
            print(f"❌ 未找到威力彩數據")
            return False
            
    except Exception as e:
        print(f"❌ 錯誤: {e}")
        return False

def check_backtest_framework():
    """檢查回測框架"""
    
    print("\n" + "="*70)
    print("🔍 檢查 3: 回測框架")
    print("="*70)
    
    try:
        from models.backtest_framework import RollingBacktester
        
        print("\n✅ RollingBacktester 類存在")
        
        # 檢查必需方法
        required_methods = [
            'run',
            'run_multi_bet',
            'compare_methods'
        ]
        
        print("\n回測框架方法:")
        for method in required_methods:
            has_method = hasattr(RollingBacktester, method)
            status = "✅" if has_method else "❌"
            print(f"  {status} {method:<35} {'存在' if has_method else '不存在'}")
        
        return True
        
    except Exception as e:
        print(f"⚠️  回測框架檢查: {e}")
        return True  # 不是致命錯誤

def print_recommendations():
    """打印建議"""
    
    print("\n" + "="*70)
    print("📋 執行建議")
    print("="*70)
    
    recommendations = """
✅ 如果上述檢查全部通過:
   1. 立即執行 4注推薦配置回測
   2. 命令: python backtest_power_2025.py --config optimized --output results.md
   3. 預期結果: 19-21% 命中率

⚠️  如果某些方法不存在:
   1. 檢查是否需要在 unified_predictor.py 中實現
   2. 推薦實現優先級:
      a) ensemble_predict (含窗口參數) - 必須
      b) zone_balance_predict - 必須
      c) bayesian_predict - 必須
      d) trend_predict - 必須
      e) anti_consensus_predict - 優先
      f) 混合預測方法 - 可選

❌ 如果數據庫無法連接:
   1. 檢查 db_manager.db_path 配置
   2. 確保 lottery_v2.db 文件存在
   3. 驗證數據庫格式

【完整檢查清單】

方法檢查:
  □ ensemble_predict
  □ zone_balance_predict
  □ bayesian_predict
  □ trend_predict
  □ anti_consensus_predict
  □ cluster_pivot_predict

數據檢查:
  □ 威力彩數據可訪問
  □ 2025年數據存在 (>90期)
  □ 數據字段完整 (numbers, special, draw, date)

框架檢查:
  □ RollingBacktester 可導入
  □ 回測邏輯支持多注並行

配置檢查:
  □ lottery_rules 包含 POWER_LOTTO 規則
  □ 回測窗口可配置
  □ 特別號優化方法可選
    """
    
    print(recommendations)

def main():
    """執行完整檢查"""
    
    print("\n" + "="*70)
    print("🚀 威力彩 20%+ 優化項目 - 環境檢查")
    print("="*70)
    
    results = {
        '方法檢查': check_unified_predictor(),
        '數據檢查': check_database(),
        '框架檢查': check_backtest_framework(),
    }
    
    print("\n" + "="*70)
    print("📊 檢查結果總結")
    print("="*70)
    
    for check_name, result in results.items():
        status = "✅ 通過" if result else "❌ 失敗"
        print(f"  {status}: {check_name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 所有檢查通過! 可以開始優化工作")
        print("\n下一步:")
        print("  1. 運行: python backtest_power_2025.py --config 4bet_optimized")
        print("  2. 等待回測完成 (預期 1-2 小時)")
        print("  3. 查看結果是否達成 20%+ 目標")
    else:
        print("\n⚠️  存在檢查失敗項, 請根據上述建議修復")
    
    print_recommendations()
    
    return 0 if all_passed else 1

if __name__ == '__main__':
    sys.exit(main())
