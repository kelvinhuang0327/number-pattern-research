"""Quick smoke test for mlb_feature_repair."""
from wbc_backend.prediction.mlb_feature_repair import build_repaired_feature_rows

test_rows = [
    {
        'Date': '2025-03-18', 'Home': 'Chicago Cubs', 'Away': 'Los Angeles Dodgers',
        'model_prob_home': 0.57, 'Home ML': '+125', 'Away ML': '-150',
        'Home Score': 1.0, 'Away Score': 4.0, 'Status': 'Final',
    },
    {
        'Date': '2025-03-19', 'Home': 'Chicago Cubs', 'Away': 'Los Angeles Dodgers',
        'model_prob_home': 0.55, 'Home ML': '+125', 'Away ML': '-150',
        'Home Score': 3.0, 'Away Score': 6.0, 'Status': 'Final',
    },
]

repaired, meta = build_repaired_feature_rows(test_rows)
print('Output count:', len(repaired))
print('metadata:', meta)
r0 = repaired[0]
print('prob before:', r0['raw_model_prob_home'])
print('prob after:', r0['model_prob_home'])
print('source:', r0['probability_source'])
print('version:', r0['repaired_feature_version'])
print('bias_removed:', r0['repaired_home_bias_removed'])
print('bullpen_delta:', r0['bullpen_delta'])
print('rest_delta:', r0['rest_delta'])
print('win_rate_delta:', r0['win_rate_delta'])
print('game_id:', r0['game_id'])
