import pandas as pd
import sys
import json

try:
    file_path = '/Users/kelvin/Kelvin-WorkSpace/Betting-pool/data/mlb_2025/mlb-odds.xlsx'
    xl = pd.ExcelFile(file_path)
    print(f"Sheet names: {xl.sheet_names}")
    
    # Take 'Betting Odds' sheet
    df = xl.parse('Betting Odds')
    df["source_file"] = "mlb-odds.xlsx"
    df["source_type"] = "user_supplied_xlsx"
    df["is_verified_real"] = False
    df.to_csv('/Users/kelvin/Kelvin-WorkSpace/Betting-pool/data/mlb_2025/mlb_odds_2025_real.csv', index=False)
    metadata = {
        "dataset": "MLB_2025",
        "ingest_source_file": "mlb-odds.xlsx",
        "ingest_source_type": "user_supplied_xlsx",
        "source_chain_verified": False,
        "notes": "Converted from local workbook. Record-level provenance not independently verified.",
    }
    with open('/Users/kelvin/Kelvin-WorkSpace/Betting-pool/data/mlb_2025/mlb_odds_2025_real.csv.metadata.json', 'w', encoding='utf-8') as fh:
        json.dump(metadata, fh, ensure_ascii=False, indent=2)
    print("Conversion successful: data/mlb_2025/mlb_odds_2025_real.csv")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
