#!/usr/bin/env python3
"""
批量為所有預測方法添加數據範圍日誌和返回字段的自動化腳本
"""
import re
import sys

def add_data_range_to_file(file_path: str):
    """為文件中的所有預測方法添加數據範圍日誌"""

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 統計需要修改的方法
    predict_methods = re.findall(r'def (\w+_predict)\(', content)
    print(f"📊 找到 {len(predict_methods)} 個預測方法")

    # 方法名到中文名的映射
    method_names = {
        'trend_predict': '趨勢回歸分析',
        'deviation_predict': '偏差分析',
        'frequency_predict': '頻率分析',
        'bayesian_predict': '貝葉斯分析',
        'markov_predict': '馬可夫鏈',
        'monte_carlo_predict': '蒙地卡羅模擬',
        'odd_even_balance_predict': '奇偶平衡',
        'zone_balance_predict': '區間平衡',
        'hot_cold_mix_predict': '冷熱號混合',
        'sum_range_predict': '總和範圍',
        'number_pairs_predict': '號碼配對',
        'pattern_recognition_predict': '模式識別',
        'cycle_analysis_predict': '週期分析',
        'wheeling_predict': '輪盤系統',
        'statistical_predict': '統計分析',
        'random_forest_predict': '隨機森林',
        '_knn_like_predict': 'KNN分析',
        'ensemble_advanced_predict': '進階集成',
        'ensemble_predict': '集成預測',
        'entropy_predict': '熵分析',
        'clustering_predict': '聚類分析',
        'dynamic_ensemble_predict': '動態集成',
        'temporal_predict': '時序分析',
        'feature_engineering_predict': '特徵工程'
    }

    modified_count = 0

    # 為每個方法添加日誌（如果還沒有）
    for method_func, method_display_name in method_names.items():
        # 匹配方法定義
        pattern = rf'(def {method_func}\([^)]+\)[^:]*:\s*"""[^"]*""")\s*\n(\s+)'

        matches = list(re.finditer(pattern, content, re.MULTILINE | re.DOTALL))

        if matches:
            for match in matches:
                # 檢查是否已經有 log_data_range 調用
                method_start = match.end()
                method_next_lines = content[method_start:method_start + 500]

                if 'log_data_range' not in method_next_lines:
                    # 添加日誌
                    indent = match.group(2)
                    log_line = f'\n{indent}# 🔧 記錄數據範圍\n{indent}log_data_range(\'{method_display_name}\', history)\n'

                    content = content[:method_start] + log_line + content[method_start:]
                    modified_count += 1
                    print(f"✅ 已為 {method_func} 添加數據範圍日誌")

    # 為返回值添加 dataRange 字段（在 return 語句中）
    # 匹配 return {  的模式
    return_pattern = r'(return\s+\{[^}]+?)((?:\'[^\']+\'|\"[^\"]+\")\s*:\s*[^,}]+,?\s*)*\}'

    def add_dataRange_to_return(match):
        """在 return 字典中添加 dataRange 字段"""
        dict_content = match.group(0)

        # 如果已經有 dataRange，不要重複添加
        if 'dataRange' in dict_content or 'data_range' in dict_content:
            return dict_content

        # 在最後一個字段後添加 dataRange
        # 先找到最後一個 }
        last_brace_pos = dict_content.rfind('}')

        # 檢查是否需要逗號
        before_brace = dict_content[:last_brace_pos].rstrip()
        needs_comma = not before_brace.endswith(',')

        comma = ',' if needs_comma else ''

        # 插入 dataRange 字段
        new_dict = (
            dict_content[:last_brace_pos] +
            f"{comma}\n            'dataRange': get_data_range_info(history)  # 🔧 添加數據範圍信息\n        " +
            dict_content[last_brace_pos:]
        )

        return new_dict

    # 只在預測方法中的 return 語句添加（通過檢查前面是否有 def xxx_predict）
    lines = content.split('\n')
    new_lines = []
    in_predict_method = False
    current_method = None

    for i, line in enumerate(lines):
        # 檢查是否進入預測方法
        predict_match = re.match(r'\s*def (\w+_predict)\(', line)
        if predict_match:
            in_predict_method = True
            current_method = predict_match.group(1)

        # 檢查是否離開方法（新的方法定義）
        elif in_predict_method and re.match(r'\s*def \w+\(', line):
            in_predict_method = False
            current_method = None

        # 如果在預測方法中，並且這行是 return { 開頭
        if in_predict_method and re.search(r'return\s+\{', line):
            # 檢查是否已經有 dataRange
            if 'dataRange' not in line and 'data_range' not in line:
                # 收集完整的 return 語句（可能跨多行）
                return_lines = [line]
                j = i + 1
                brace_count = line.count('{') - line.count('}')

                while brace_count > 0 and j < len(lines):
                    return_lines.append(lines[j])
                    brace_count += lines[j].count('{') - lines[j].count('}')
                    j += 1

                # 完整的 return 語句
                full_return = '\n'.join(return_lines)

                # 在最後的 } 前添加 dataRange
                if full_return.count('}') > 0:
                    # 找到最後一個 }
                    last_brace_line_idx = len(return_lines) - 1
                    for idx in range(len(return_lines) - 1, -1, -1):
                        if '}' in return_lines[idx]:
                            last_brace_line_idx = idx
                            break

                    # 在該行前插入 dataRange
                    indent = '            '  # 假設標準縮進
                    return_lines.insert(last_brace_line_idx, f"{indent}'dataRange': get_data_range_info(history)  # 🔧 添加數據範圍信息")

                    # 替換原來的行
                    new_lines.extend(return_lines)

                    # 跳過已處理的行
                    for _ in range(j - i - 1):
                        next(enumerate(lines[i+1:]), None)

                    modified_count += 1
                    print(f"✅ 已為 {current_method} 的返回值添加 dataRange 字段")
                    continue

        new_lines.append(line)

    # 寫回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))

    print(f"\n🎉 完成! 共修改了 {modified_count} 處")
    return modified_count

if __name__ == '__main__':
    file_path = '/Users/kelvin/Kelvin-WorkSpace/Lottery/lottery_api/models/unified_predictor.py'

    print("=" * 60)
    print("📝 批量添加數據範圍日誌工具")
    print("=" * 60)

    modified = add_data_range_to_file(file_path)

    if modified > 0:
        print(f"\n✅ 成功修改 {modified} 個位置")
    else:
        print("\n✅ 文件已經是最新狀態，無需修改")
