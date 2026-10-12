import pandas as pd
import sys

try:
    file_path = '/Users/kelvin/Kelvin-WorkSpace/Betting-pool/data/mlb_2025/mlb-odds.xlsx'
    xl = pd.ExcelFile(file_path)
    print(f"Sheet names: {xl.sheet_names}")
    
    # Take 'Betting Odds' sheet
    df = xl.parse('Betting Odds')
    df.to_csv('/Users/kelvin/Kelvin-WorkSpace/Betting-pool/data/mlb_2025/mlb_odds_2025_real.csv', index=False)
    print("Conversion successful: data/mlb_2025/mlb_odds_2025_real.csv")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
