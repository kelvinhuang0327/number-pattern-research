#!/usr/bin/env python3
"""
雙注API調用示例
展示如何使用新的雙注預測API
"""
import requests
import json

# API基礎URL（根據實際部署調整）
BASE_URL = "http://localhost:8000"

def demo_optimal_mode():
    """
    示例1：最優模式（極端奇數+冷號回歸）
    """
    print("=" * 80)
    print("示例1：最優模式（optimal）")
    print("=" * 80)

    url = f"{BASE_URL}/api/predict-double-bet"
    params = {
        "lottery_type": "BIG_LOTTO",
        "mode": "optimal"
    }

    try:
        response = requests.post(url, params=params, timeout=30)
        response.raise_for_status()
        result = response.json()

        print(f"\n彩票類型: {result['lotteryType']}")
        print(f"模式: {result['mode']}")
        print(f"\n🎯 注1 [{result['bet1']['method']}]:")
        print(f"   號碼: {result['bet1']['numbers']}")
        print(f"   信心度: {result['bet1']['confidence']:.1%}")
        if result['bet1'].get('special'):
            print(f"   特別號: {result['bet1']['special']}")

        print(f"\n🎯 注2 [{result['bet2']['method']}]:")
        print(f"   號碼: {result['bet2']['numbers']}")
        print(f"   信心度: {result['bet2']['confidence']:.1%}")
        if result['bet2'].get('special'):
            print(f"   特別號: {result['bet2']['special']}")

        print(f"\n📊 分析:")
        print(f"   總覆蓋: {result['analysis']['total_coverage']}個號碼")
        print(f"   號碼重疊: {result['analysis']['overlap_count']}個")
        print(f"   互補性分數: {result['analysis']['complementary_score']}")
        print(f"   預期命中率: {result['analysis']['expected_hit_rate']}")

        print(f"\n💡 推薦理由:")
        print(f"   {result['recommendation']['why_this_combo']}")
        print(f"   覆蓋效率: {result['recommendation']['coverage_efficiency']}")
        print(f"   使用提示: {result['recommendation']['usage_tip']}")

    except requests.exceptions.RequestException as e:
        print(f"❌ API調用失敗: {e}")
        print(f"   請確保後端服務運行中: python3 app.py")

def demo_dynamic_mode():
    """
    示例2：動態模式（根據上期自動選擇）
    """
    print("\n" + "=" * 80)
    print("示例2：動態模式（dynamic）")
    print("=" * 80)
    print("根據上期奇偶配比自動選擇最佳策略組合")

    url = f"{BASE_URL}/api/predict-double-bet"
    params = {
        "lottery_type": "BIG_LOTTO",
        "mode": "dynamic"
    }

    try:
        response = requests.post(url, params=params, timeout=30)
        response.raise_for_status()
        result = response.json()

        print(f"\n策略選擇原因: {result['analysis']['reason']}")
        print(f"\n注1: {result['bet1']['numbers']}")
        print(f"注2: {result['bet2']['numbers']}")
        print(f"\n組合覆蓋: {result['analysis']['total_coverage']}個號碼")

    except requests.exceptions.RequestException as e:
        print(f"❌ API調用失敗: {e}")

def demo_balanced_mode():
    """
    示例3：平衡模式（標準熱號+極端奇數）
    """
    print("\n" + "=" * 80)
    print("示例3：平衡模式（balanced）")
    print("=" * 80)
    print("116期測試命中率: 66.7%（最高）")

    url = f"{BASE_URL}/api/predict-double-bet"
    params = {
        "lottery_type": "BIG_LOTTO",
        "mode": "balanced"
    }

    try:
        response = requests.post(url, params=params, timeout=30)
        response.raise_for_status()
        result = response.json()

        print(f"\n注1: {result['bet1']['numbers']} [{result['bet1']['method']}]")
        print(f"注2: {result['bet2']['numbers']} [{result['bet2']['method']}]")
        print(f"\n覆蓋率: {result['recommendation']['coverage_efficiency']}")

    except requests.exceptions.RequestException as e:
        print(f"❌ API調用失敗: {e}")

def demo_all_lottery_types():
    """
    示例4：測試所有彩票類型
    """
    print("\n" + "=" * 80)
    print("示例4：所有彩票類型雙注預測")
    print("=" * 80)

    lottery_types = ['BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539']

    for lottery_type in lottery_types:
        print(f"\n【{lottery_type}】")
        url = f"{BASE_URL}/api/predict-double-bet"
        params = {
            "lottery_type": lottery_type,
            "mode": "optimal"
        }

        try:
            response = requests.post(url, params=params, timeout=30)
            response.raise_for_status()
            result = response.json()

            print(f"  注1: {result['bet1']['numbers']}")
            print(f"  注2: {result['bet2']['numbers']}")
            print(f"  覆蓋: {result['analysis']['total_coverage']}個號碼")

        except requests.exceptions.RequestException as e:
            print(f"  ❌ 失敗: {e}")

def demo_curl_commands():
    """
    示例5：顯示等效的curl命令
    """
    print("\n" + "=" * 80)
    print("示例5：等效curl命令")
    print("=" * 80)

    commands = [
        ("最優模式", f'curl -X POST "{BASE_URL}/api/predict-double-bet?lottery_type=BIG_LOTTO&mode=optimal"'),
        ("動態模式", f'curl -X POST "{BASE_URL}/api/predict-double-bet?lottery_type=BIG_LOTTO&mode=dynamic"'),
        ("平衡模式", f'curl -X POST "{BASE_URL}/api/predict-double-bet?lottery_type=BIG_LOTTO&mode=balanced"'),
    ]

    for name, cmd in commands:
        print(f"\n{name}:")
        print(f"  {cmd}")

def main():
    """
    主函數：運行所有示例
    """
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 24 + "雙注API調用示例" + " " * 40 + "║")
    print("╚" + "═" * 78 + "╝")

    print("\n⚠️  注意: 請先確保後端服務正在運行")
    print("   啟動命令: cd lottery-api && python3 app.py")

    input("\n按Enter鍵開始測試...")

    # 運行示例
    demo_optimal_mode()
    demo_dynamic_mode()
    demo_balanced_mode()
    demo_all_lottery_types()
    demo_curl_commands()

    print("\n" + "=" * 80)
    print("所有示例完成！")
    print("=" * 80)
    print("\n📚 API文檔:")
    print(f"   Swagger UI: {BASE_URL}/docs")
    print(f"   ReDoc: {BASE_URL}/redoc")
    print("\n💡 推薦配置:")
    print("   - 116期驗證: balanced模式命中率最高(66.7%)")
    print("   - 通用推薦: optimal模式(極端奇數+冷號回歸)")
    print("   - 智能選擇: dynamic模式(根據上期自動調整)\n")

if __name__ == "__main__":
    main()
