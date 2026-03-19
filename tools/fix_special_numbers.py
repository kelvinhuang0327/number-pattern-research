#!/usr/bin/env python3
"""
自動為 unified_predictor.py 中的所有預測方法添加特別號碼支援
"""
import re
import sys

def add_special_number_support():
    file_path = '/Users/kelvin/Kelvin-WorkSpace/Lottery/lottery_api/models/unified_predictor.py'

    print(f"讀取文件: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    modified_lines = []
    i = 0
    modifications = 0

    while i < len(lines):
        line = lines[i]
        modified_lines.append(line)

        # 檢測 return { 'numbers': predicted_numbers, 的行
        if re.match(r"\s*return \{\s*$", line) or re.match(r"\s*return \{$", line):
            # 查看下一行是否是 'numbers': predicted_numbers
            if i + 1 < len(lines) and "'numbers': predicted_numbers" in lines[i+1]:
                print(f"找到需要修復的 return 語句在第 {i+1} 行")

                # 在 return 前插入特別號碼預測代碼
                indent = len(line) - len(line.lstrip())
                indent_str = ' ' * indent

                # 回退一行，在 return 前添加代碼
                modified_lines.pop()  # 移除剛添加的 return {

                # 添加特別號碼預測
                modified_lines.append(f"{indent_str}# 🔧 預測特別號碼\n")
                modified_lines.append(f"{indent_str}predicted_special = predict_special_number(history, lottery_rules, predicted_numbers)\n")
                modified_lines.append(f"{indent_str}\n")

                # 將 return { 改為 result = {
                modified_lines.append(line.replace('return {', 'result = {'))

                # 繼續處理字典內容直到找到結束的 }
                i += 1
                brace_count = 1
                while i < len(lines) and brace_count > 0:
                    current_line = lines[i]
                    modified_lines.append(current_line)

                    # 計算大括號
                    brace_count += current_line.count('{') - current_line.count('}')

                    # 如果這行包含結束括號且括號平衡
                    if '}' in current_line and brace_count == 0:
                        # 在 } 後添加特別號碼邏輯和return
                        modified_lines.append(f"{indent_str}\n")
                        modified_lines.append(f"{indent_str}# 🔧 添加特別號碼\n")
                        modified_lines.append(f"{indent_str}if predicted_special is not None:\n")
                        modified_lines.append(f"{indent_str}    result['special'] = predicted_special\n")
                        modified_lines.append(f"{indent_str}\n")
                        modified_lines.append(f"{indent_str}return result\n")

                        modifications += 1
                        break

                    i += 1

        i += 1

    print(f"\\n完成！共修改了 {modifications} 個預測方法")

    # 寫回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(modified_lines)

    print(f"✅ 文件已更新: {file_path}")

if __name__ == '__main__':
    try:
        add_special_number_support()
    except Exception as e:
        print(f"❌ 錯誤: {e}", file=sys.stderr)
        sys.exit(1)
