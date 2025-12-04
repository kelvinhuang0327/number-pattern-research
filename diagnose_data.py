#!/usr/bin/env python3
"""
診斷腳本：檢查訓練數據和測試數據的差異
"""
import json
import sys

def analyze_data():
    print("=" * 60)
    print("🔍 數據診斷分析")
    print("=" * 60)
    print()
    
    # 1. 檢查後端數據
    try:
        with open('lottery-api/data/lottery_data.json', 'r', encoding='utf-8') as f:
            backend_data = json.load(f)
        print(f"✅ 後端數據: {len(backend_data)} 期")
        
        # 按彩券類型分組
        by_type = {}
        for draw in backend_data:
            lottery_type = draw.get('lotteryType', 'UNKNOWN')
            by_type[lottery_type] = by_type.get(lottery_type, 0) + 1
        
        print("   按類型分佈:")
        for lottery_type, count in sorted(by_type.items()):
            print(f"   - {lottery_type}: {count} 期")
        print()
        
        # 檢查日期範圍
        dates = [d['date'] for d in backend_data if 'date' in d]
        if dates:
            dates.sort()
            print(f"   日期範圍: {dates[0]} ~ {dates[-1]}")
        print()
        
    except FileNotFoundError:
        print("❌ 後端數據文件不存在")
        print()
    
    # 2. 檢查最佳配置
    try:
        with open('lottery-api/data/best_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"✅ 最佳配置:")
        for key, value in config.items():
            if isinstance(value, float):
                print(f"   - {key}: {value:.4f}")
            else:
                print(f"   - {key}: {value}")
        print()
    except FileNotFoundError:
        print("❌ 最佳配置文件不存在")
        print()
    
    # 3. 檢查優化歷史
    try:
        with open('lottery-api/data/latest_history.json', 'r', encoding='utf-8') as f:
            history = json.load(f)
        print(f"✅ 優化歷史:")
        print(f"   - 訓練數據量: {history.get('data_count', 'N/A')} 期")
        print(f"   - 訓練集: {history.get('train_count', 'N/A')} 期")
        print(f"   - 驗證集: {history.get('val_count', 'N/A')} 期")
        print(f"   - 最佳適應度: {history.get('best_fitness', 'N/A')}")
        print()
    except FileNotFoundError:
        print("⚠️  優化歷史文件不存在")
        print()
    
    print("=" * 60)
    print("💡 分析建議")
    print("=" * 60)
    print()
    print("如果適應度 (11%) 遠高於模擬測試 (2%)，可能原因：")
    print()
    print("1. 📊 數據不一致")
    print("   - 訓練時使用的數據 ≠ 測試時使用的數據")
    print("   - 解決：確保同步最新數據到後端")
    print()
    print("2. 🎯 測試範圍不同")
    print("   - 訓練時驗證集是最近 20% 的數據")
    print("   - 測試時可能測試更早或更晚的數據")
    print("   - 解決：確保測試同一時間範圍")
    print()
    print("3. 🔢 樣本大小")
    print("   - 驗證集可能只有 20-30 期")
    print("   - 測試集可能有 100+ 期")
    print("   - 小樣本的成功率波動較大")
    print()
    print("4. 🎲 彩券類型")
    print("   - 訓練時可能混合了多種彩券")
    print("   - 測試時只測試單一彩券")
    print("   - 解決：確保訓練和測試使用相同彩券類型")
    print()

if __name__ == '__main__':
    analyze_data()
