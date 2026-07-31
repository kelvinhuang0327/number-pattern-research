import pandas as pd
import sys

file_path = '/Users/kelvin/Kelvin-WorkSpace/Betting-pool/data/mlb_2025/mlb_odds_2025_real.csv'
df = pd.read_csv(file_path)
df.columns = df.columns.str.strip()
print(f"Columns: {df.columns.tolist()}")
print(f"Head:\n{df[['Away', 'Home', 'Away Score', 'Home Score', 'Status']].head()}")
print(f"Status counts:\n{df['Status'].value_counts()}")
df = df[df['Status'].str.strip() == 'Final'].copy()
print(f"After filtering Status: {len(df)}")
df['Away Score'] = pd.to_numeric(df['Away Score'], errors='coerce')
df['Home Score'] = pd.to_numeric(df['Home Score'], errors='coerce')
print(f"Scores after numeric conversion (head):\n{df[['Away Score', 'Home Score']].head()}")
df = df.dropna(subset=['Away Score', 'Home Score'])
print(f"Final df size: {len(df)}")
