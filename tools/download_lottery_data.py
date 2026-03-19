#!/usr/bin/env python3
"""
台灣彩券大樂透歷史數據下載工具
從台灣彩券官網下載所有年度的大樂透開獎數據並整合成CSV檔案
"""

import urllib.request
import csv
import os
from pathlib import Path

def download_lottery_data():
    """下載大樂透歷史數據"""
    
    # 設定下載目錄
    download_dir = Path.home() / "Downloads"
    output_file = download_dir / "lotto649_all_data.csv"
    
    # 台灣彩券API基礎URL（根據網站結構推測）
    base_url = "https://www.taiwanlottery.com/lotto/history/result_download"
    
    # 年度範圍：從96年度到114年度
    years = range(96, 115)  # 96 to 114
    
    all_data = []
    headers_written = False
    
    print("開始下載大樂透歷史數據...")
    print(f"目標檔案: {output_file}")
    print("-" * 50)
    
    for year in years:
        url = f"{base_url}/{year}"
        print(f"正在下載 {year}年度數據...")
        
        try:
            # 下載數據
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as response:
                content_type = response.headers.get('Content-Type', '')
                data = response.read().decode('utf-8')
            
            # 檢查是否為CSV格式
            if 'text/csv' in content_type or 'application/csv' in content_type or data.startswith('遊戲名稱'):
                # 解析CSV
                lines = data.strip().split('\n')
                
                if not lines:
                    print(f"  ⚠️  {year}年度：無數據")
                    continue
                
                # 處理CSV數據
                csv_reader = csv.reader(lines)
                rows = list(csv_reader)
                
                if not rows:
                    print(f"  ⚠️  {year}年度：無有效數據")
                    continue
                
                # 第一次寫入時保存標題行
                if not headers_written and rows:
                    all_data.append(rows[0])  # 標題行
                    headers_written = True
                
                # 過濾出大樂透的數據
                lotto_rows = []
                for row in rows[1:]:  # 跳過標題行
                    if row and len(row) > 0:
                        # 檢查是否為大樂透（遊戲名稱欄位）
                        game_name = row[0] if len(row) > 0 else ""
                        if "大樂透" in game_name or "威力彩" in game_name or "Lotto" in game_name:
                            lotto_rows.append(row)
                
                all_data.extend(lotto_rows)
                print(f"  ✓ {year}年度：成功下載 {len(lotto_rows)} 筆大樂透數據")
                
            else:
                print(f"  ⚠️  {year}年度：非CSV格式 (Content-Type: {content_type})")
                
        except urllib.error.URLError as e:
            print(f"  ✗ {year}年度：下載失敗 - {str(e)}")
            continue
        except Exception as e:
            print(f"  ✗ {year}年度：處理失敗 - {str(e)}")
            continue
    
    # 寫入整合後的CSV檔案
    if all_data:
        try:
            with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerows(all_data)
            
            print("-" * 50)
            print(f"✓ 下載完成！")
            print(f"總共 {len(all_data) - 1} 筆數據")
            print(f"檔案位置: {output_file}")
            return str(output_file)
            
        except Exception as e:
            print(f"✗ 寫入檔案失敗: {str(e)}")
            return None
    else:
        print("-" * 50)
        print("✗ 沒有下載到任何數據")
        return None

if __name__ == "__main__":
    result = download_lottery_data()
    if result:
        print(f"\n成功！數據已儲存至: {result}")
    else:
        print("\n失敗！請檢查網路連線或稍後再試。")
