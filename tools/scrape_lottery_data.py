#!/usr/bin/env python3
"""
台灣彩券大樂透數據爬蟲
從台灣彩券網站直接抓取歷史開獎數據
"""

import urllib.request
import json
import csv
import time
from pathlib import Path
from datetime import datetime, timedelta

def fetch_lotto_draw(draw_number):
    """
    抓取單期開獎數據
    使用台灣彩券API
    """
    api_url = f"https://api.taiwanlottery.com/TLCAPIWeB/Lotto649/history?period={draw_number}"
    
    try:
        req = urllib.request.Request(api_url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json'
        })
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read().decode('utf-8')
            result = json.loads(data)
            return result
    except Exception as e:
        return None

def fetch_recent_draws(count=100):
    """
    抓取最近N期的開獎數據
    """
    print(f"開始抓取最近 {count} 期大樂透開獎數據...")
    print("-" * 50)
    
    # 先抓取最新一期來確定期號
    latest_url = "https://api.taiwanlottery.com/TLCAPIWeB/Lotto649/history"
    
    try:
        req = urllib.request.Request(latest_url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json'
        })
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read().decode('utf-8')
            latest = json.loads(data)
            
            if not latest or 'content' not in latest:
                print("✗ 無法獲取最新期數")
                return []
            
            # 獲取最新期號
            latest_draw = latest['content'][0]['period'] if latest['content'] else None
            
            if not latest_draw:
                print("✗ 無法解析最新期號")
                return []
            
            print(f"最新期號: {latest_draw}")
            
    except Exception as e:
        print(f"✗ 獲取最新期號失敗: {str(e)}")
        return []
    
    # 計算起始期號
    try:
        latest_num = int(latest_draw)
        start_num = latest_num - count + 1
    except:
        print("✗ 期號格式錯誤")
        return []
    
    all_draws = []
    success_count = 0
    
    for i in range(count):
        draw_num = str(start_num + i).zfill(9)
        
        # 抓取數據
        url = f"https://api.taiwanlottery.com/TLCAPIWeB/Lotto649/history?period={draw_num}"
        
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json'
            })
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = response.read().decode('utf-8')
                result = json.loads(data)
                
                if result and 'content' in result and result['content']:
                    draw_data = result['content'][0]
                    
                    # 解析開獎號碼
                    numbers = draw_data.get('lotto649Number', '').split(',')
                    special = draw_data.get('lotto649SNumber', '')
                    date = draw_data.get('lotto649DrawTerm', '')
                    
                    if len(numbers) == 6 and special:
                        all_draws.append({
                            'draw': draw_num,
                            'date': date,
                            'numbers': [int(n) for n in numbers],
                            'special': int(special)
                        })
                        success_count += 1
                        print(f"✓ {draw_num} ({date}): {', '.join(numbers)} + {special}")
                    
        except Exception as e:
            print(f"⚠ {draw_num}: 跳過 - {str(e)}")
            continue
        
        # 避免請求過快
        time.sleep(0.1)
    
    print("-" * 50)
    print(f"✓ 成功抓取 {success_count}/{count} 期數據")
    
    return all_draws

def fetch_by_date_range(start_date, end_date):
    """
    根據日期範圍抓取數據
    """
    print(f"抓取日期範圍: {start_date} 至 {end_date}")
    print("-" * 50)
    
    # 台灣彩券大樂透每週二、五開獎
    # 我們需要找出這個範圍內的所有開獎日
    
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    all_draws = []
    current = start
    
    while current <= end:
        # 檢查是否為週二(1)或週五(4)
        if current.weekday() in [1, 4]:
            date_str = current.strftime('%Y-%m-%d')
            
            # 嘗試抓取該日期的數據
            url = f"https://api.taiwanlottery.com/TLCAPIWeB/Lotto649/history?date={date_str}"
            
            try:
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'Mozilla/5.0',
                    'Accept': 'application/json'
                })
                
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = response.read().decode('utf-8')
                    result = json.loads(data)
                    
                    if result and 'content' in result and result['content']:
                        draw_data = result['content'][0]
                        
                        numbers = draw_data.get('lotto649Number', '').split(',')
                        special = draw_data.get('lotto649SNumber', '')
                        draw_num = draw_data.get('period', '')
                        
                        if len(numbers) == 6 and special:
                            all_draws.append({
                                'draw': draw_num,
                                'date': date_str,
                                'numbers': [int(n) for n in numbers],
                                'special': int(special)
                            })
                            print(f"✓ {date_str} ({draw_num}): {', '.join(numbers)} + {special}")
                
                time.sleep(0.1)
                
            except:
                pass
        
        current += timedelta(days=1)
    
    print("-" * 50)
    print(f"✓ 成功抓取 {len(all_draws)} 期數據")
    
    return all_draws

def save_to_csv(draws, output_file):
    """儲存為CSV格式"""
    
    if not draws:
        print("✗ 沒有數據可儲存")
        return False
    
    try:
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            
            # 寫入標題
            writer.writerow(['期數', '日期', '號碼1', '號碼2', '號碼3', '號碼4', '號碼5', '號碼6', '特別號'])
            
            # 寫入數據
            for draw in draws:
                writer.writerow([
                    draw['draw'],
                    draw['date'],
                    *draw['numbers'],
                    draw['special']
                ])
        
        print(f"✓ 數據已儲存至: {output_file}")
        return True
        
    except Exception as e:
        print(f"✗ 儲存失敗: {str(e)}")
        return False

def main():
    """主程式"""
    
    print("=" * 50)
    print("台灣彩券大樂透數據爬蟲")
    print("=" * 50)
    print()
    print("請選擇抓取方式:")
    print("1. 抓取最近N期數據（推薦）")
    print("2. 抓取指定日期範圍")
    print("3. 快速抓取最近100期（直接執行）")
    print()
    
    choice = input("請輸入選項 (1-3) [預設: 3]: ").strip() or "3"
    
    output_dir = Path.home() / "Downloads"
    output_file = output_dir / "lotto649_data.csv"
    
    draws = []
    
    if choice == "1":
        count = input("請輸入要抓取的期數 [預設: 100]: ").strip()
        count = int(count) if count.isdigit() else 100
        draws = fetch_recent_draws(count)
        
    elif choice == "2":
        start_date = input("請輸入起始日期 (YYYY-MM-DD): ").strip()
        end_date = input("請輸入結束日期 (YYYY-MM-DD): ").strip()
        
        if start_date and end_date:
            draws = fetch_by_date_range(start_date, end_date)
        else:
            print("✗ 日期格式錯誤")
            return
            
    else:  # choice == "3"
        print("\n快速模式：抓取最近100期數據\n")
        draws = fetch_recent_draws(100)
    
    # 儲存數據
    if draws:
        print()
        if save_to_csv(draws, output_file):
            print()
            print("=" * 50)
            print("🎉 完成！")
            print(f"總共抓取 {len(draws)} 期數據")
            print(f"檔案位置: {output_file}")
            print()
            print("您現在可以:")
            print("1. 開啟大樂透分析系統 (index.html)")
            print("2. 點擊「選擇檔案」上傳此CSV")
            print("3. 開始分析！")
            print("=" * 50)
    else:
        print()
        print("✗ 沒有抓取到任何數據")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✗ 使用者中斷")
    except Exception as e:
        print(f"\n✗ 發生錯誤: {str(e)}")
