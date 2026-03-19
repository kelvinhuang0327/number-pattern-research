#!/usr/bin/env python3
"""
台灣彩券CSV格式轉換工具
將台灣彩券官網下載的CSV轉換為大樂透分析系統可用的格式
"""

import csv
import sys
from pathlib import Path

def convert_taiwan_lottery_csv(input_file, output_file=None):
    """
    轉換台灣彩券CSV格式
    
    輸入格式：遊戲名稱,期別,開獎日期,銷售總額,銷售注數,總獎金,獎號1,獎號2,獎號3,獎號4,獎號5,獎號6,特別號
    輸出格式：期數,日期,號碼1,號碼2,號碼3,號碼4,號碼5,號碼6,特別號
    """
    
    if not output_file:
        input_path = Path(input_file)
        output_file = input_path.parent / f"{input_path.stem}_converted.csv"
    
    print(f"輸入檔案: {input_file}")
    print(f"輸出檔案: {output_file}")
    print("-" * 50)
    
    lotto_data = []
    total_rows = 0
    lotto_rows = 0
    
    try:
        # 讀取輸入檔案
        with open(input_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            headers = next(reader)  # 跳過標題行
            
            print(f"原始欄位: {', '.join(headers)}")
            print("-" * 50)
            
            for row in reader:
                total_rows += 1
                
                if not row or len(row) < 13:
                    continue
                
                game_name = row[0].strip()
                
                # 只保留大樂透數據
                if '大樂透' in game_name or 'Lotto' in game_name:
                    try:
                        draw_number = row[1].strip()  # 期別
                        draw_date = row[2].strip()    # 開獎日期
                        
                        # 獎號（索引6-11）
                        numbers = [
                            row[6].strip(),
                            row[7].strip(),
                            row[8].strip(),
                            row[9].strip(),
                            row[10].strip(),
                            row[11].strip()
                        ]
                        
                        # 特別號（索引12）
                        special = row[12].strip()
                        
                        # 驗證數據
                        if all(n.isdigit() for n in numbers) and special.isdigit():
                            lotto_data.append([
                                draw_number,
                                draw_date,
                                *numbers,
                                special
                            ])
                            lotto_rows += 1
                        
                    except (IndexError, ValueError) as e:
                        print(f"警告：跳過無效資料行 - {e}")
                        continue
        
        # 寫入輸出檔案
        if lotto_data:
            with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                
                # 寫入標題
                writer.writerow(['期數', '日期', '號碼1', '號碼2', '號碼3', '號碼4', '號碼5', '號碼6', '特別號'])
                
                # 寫入數據
                writer.writerows(lotto_data)
            
            print(f"✓ 轉換完成！")
            print(f"  總資料筆數: {total_rows}")
            print(f"  大樂透筆數: {lotto_rows}")
            print(f"  輸出檔案: {output_file}")
            return str(output_file)
        else:
            print("✗ 沒有找到大樂透數據")
            return None
            
    except FileNotFoundError:
        print(f"✗ 錯誤：找不到檔案 {input_file}")
        return None
    except Exception as e:
        print(f"✗ 錯誤：{str(e)}")
        return None

def merge_multiple_files(input_files, output_file):
    """合併多個CSV檔案"""
    
    print(f"合併 {len(input_files)} 個檔案...")
    print(f"輸出檔案: {output_file}")
    print("-" * 50)
    
    all_data = []
    total_lotto_rows = 0
    
    for input_file in input_files:
        print(f"處理: {input_file}")
        
        try:
            with open(input_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                headers = next(reader)  # 跳過標題行
                
                for row in reader:
                    if not row or len(row) < 13:
                        continue
                    
                    game_name = row[0].strip()
                    
                    if '大樂透' in game_name or 'Lotto' in game_name:
                        try:
                            draw_number = row[1].strip()
                            draw_date = row[2].strip()
                            numbers = [row[i].strip() for i in range(6, 12)]
                            special = row[12].strip()
                            
                            if all(n.isdigit() for n in numbers) and special.isdigit():
                                all_data.append([draw_number, draw_date, *numbers, special])
                                total_lotto_rows += 1
                        except:
                            continue
            
            print(f"  ✓ 完成")
            
        except Exception as e:
            print(f"  ✗ 失敗: {str(e)}")
            continue
    
    # 按期數排序
    all_data.sort(key=lambda x: x[0])
    
    # 寫入輸出檔案
    if all_data:
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['期數', '日期', '號碼1', '號碼2', '號碼3', '號碼4', '號碼5', '號碼6', '特別號'])
            writer.writerows(all_data)
        
        print("-" * 50)
        print(f"✓ 合併完成！")
        print(f"  總筆數: {total_lotto_rows}")
        print(f"  輸出檔案: {output_file}")
        return str(output_file)
    else:
        print("✗ 沒有找到任何大樂透數據")
        return None

def main():
    """主程式"""
    
    if len(sys.argv) < 2:
        print("用法：")
        print("  單一檔案轉換：")
        print("    python3 convert_taiwan_lottery_csv.py input.csv [output.csv]")
        print()
        print("  合併多個檔案：")
        print("    python3 convert_taiwan_lottery_csv.py --merge output.csv file1.csv file2.csv ...")
        print()
        print("範例：")
        print("    python3 convert_taiwan_lottery_csv.py 114.csv")
        print("    python3 convert_taiwan_lottery_csv.py 114.csv lotto_114.csv")
        print("    python3 convert_taiwan_lottery_csv.py --merge all_lotto.csv 113.csv 114.csv")
        sys.exit(1)
    
    if sys.argv[1] == '--merge':
        if len(sys.argv) < 4:
            print("✗ 錯誤：合併模式需要至少指定輸出檔案和一個輸入檔案")
            sys.exit(1)
        
        output_file = sys.argv[2]
        input_files = sys.argv[3:]
        result = merge_multiple_files(input_files, output_file)
    else:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
        result = convert_taiwan_lottery_csv(input_file, output_file)
    
    if result:
        print()
        print("🎉 成功！您現在可以將轉換後的CSV檔案上傳到大樂透分析系統。")
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
