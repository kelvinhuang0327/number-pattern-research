#!/usr/bin/env python3
"""
Fetch Super Lotto (威力彩) History Data
Crawls data from taiwanlottery using standard libraries (no bs4).
"""
import sys
import os
import requests
import re
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

def fetch_data():
    url = "https://www.taiwanlottery.com.tw/lotto/superlotto638/history.aspx"
    print(f"Fetching {url}...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/115.0'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        html = response.text
        
        # Regex extraction
        # Pattern for DrawTerm: <span id="SuperLotto638Control_history1_dlQuery_ctl00_DrawTerm">113000004</span>
        # We look for "DrawTerm">(\d+)</span>
        
        draws = []
        
        # Split by table row or some delimiter to keep data grouped?
        # The structure is a DataList, so it repeats for each item.
        # Let's find all blocks.
        
        # We can find all matches for each field and zip them, assuming order is preserved.
        
        draw_terms = re.findall(r'id=".*DrawTerm">(\d+)<', html)
        dates = re.findall(r'id=".*Date">(\d+/\d+/\d+)<', html)
        
        # Numbers are trickier: SNo1 to SNo6. 
        # They appear in blocks.
        # Let's try to split the HTML by "DrawTerm" to isolate blocks.
        
        blocks = html.split('DrawTerm">')
        if len(blocks) > 1:
            blocks = blocks[1:] # Skip header
            
            for block in blocks:
                try:
                    term_match = re.match(r'(\d+)<', block)
                    if not term_match: continue
                    term = term_match.group(1)
                    
                    date_match = re.search(r'Date">(\d+/\d+/\d+)<', block)
                    if not date_match: continue
                    date_str = date_match.group(1)
                    
                    # Convert Date
                    y, m, d = date_str.split('/')
                    ad_year = int(y) + 1911
                    full_date = f"{ad_year}/{m}/{d}"
                    
                    # Numbers
                    numbers = []
                    for i in range(1, 7):
                        num_match = re.search(f'SNo{i}">(\d+)<', block)
                        if num_match:
                            numbers.append(int(num_match.group(1)))
                            
                    special_match = re.search(r'SNo7">(\d+)<', block)
                    special = int(special_match.group(1)) if special_match else 0
                    
                    if len(numbers) == 6:
                        draws.append({
                            'draw': term,
                            'date': full_date,
                            'lotteryType': 'POWER_LOTTO',
                            'numbers': numbers,
                            'special': special
                        })
                        
                except Exception as e:
                    print(f"Block parse error: {e}")
                    
        print(f"Parsed {len(draws)} draws.")
        return draws

    except Exception as e:
        print(f"Fetch failed: {e}")
        return []

def main():
    draws = fetch_data()
    if draws:
        db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
        count, _ = db.insert_draws(draws)
        print(f"Inserted {count} new draws.")
    else:
        print("No data found.")

if __name__ == '__main__':
    main()
