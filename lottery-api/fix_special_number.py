#!/usr/bin/env python3
"""
批量修復 unified_predictor.py 中所有預測方法，添加特別號碼支援
"""
import re

def fix_unified_predictor():
    file_path = '/Users/kelvin/Kelvin-WorkSpace/Lottery/lottery-api/models/unified_predictor.py'

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 需要修復的預測方法列表
    methods_to_fix = [
        'trend_predict',
        'deviation_predict',
        'frequency_predict',
        'bayesian_predict',
        'markov_predict',
        'monte_carlo_predict',
        'odd_even_balance_predict',
        'zone_balance_predict',
        'hot_cold_mix_predict',
        'sum_range_predict',
        'number_pairs_predict',
        'pattern_recognition_predict',
        'cycle_analysis_predict',
        'wheeling_predict',
        'statistical_predict',
        'random_forest_predict',
        'ensemble_advanced_predict',
        'ensemble_predict'
    ]

    for method_name in methods_to_fix:
        print(f"Fixing {method_name}...")

        # 正則表達式：匹配方法定義到return語句
        # 找到 return { 'numbers': ..., ... } 的模式
        pattern = rf"(def {method_name}\([^)]+\)[^:]*:.*?)(return \{{\s*'numbers': predicted_numbers,)"

        # 替換：在 return 前添加特別號碼預測
        replacement = r"\1# 🔧 預測特別號碼\n        predicted_special = predict_special_number(history, lottery_rules, predicted_numbers)\n        \n        result = {"

        # 第一次替換：在 return 前添加預測和建立 result 字典
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)

        # 第二次替換：將 return { ... } 改為 result = { ... } 然後添加 special 字段並 return
        # 匹配 result = { ... } 結尾
        pattern2 = rf"(result = \{{\s*'numbers': predicted_numbers,.*?}})\s*\n"

        def add_special_and_return(match):
            dict_content = match.group(1)
            return f"{dict_content}\n        \n        # 🔧 添加特別號碼\n        if predicted_special is not None:\n            result['special'] = predicted_special\n        \n        return result\n"

        content = re.sub(pattern2, add_special_and_return, content, flags=re.DOTALL)

    # 寫回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ All methods fixed!")

if __name__ == '__main__':
    fix_unified_predictor()
