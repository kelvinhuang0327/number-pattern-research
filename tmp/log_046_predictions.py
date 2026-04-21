import sys
sys.path.insert(0, 'lottery_api')
from engine.prediction_logger import PredictionLogger

logger = PredictionLogger()
PERIOD = "115000046"

strategies = [
    {
        "strategy": "regime_2bet (edge300=+3.64%)",
        "num_bets": 2,
        "bets": [[5,26,29,36,38,48],[27,28,30,31,32,34]]
    },
    {
        "strategy": "ts3_regime_3bet (edge300=+3.51%)",
        "num_bets": 3,
        "bets": [[5,26,29,36,38,48],[27,28,30,31,32,34],[14,20,22,25,39,41]]
    },
    {
        "strategy": "p1_deviation_4bet (edge300=+1.42%)",
        "num_bets": 4,
        "bets": [[6,11,12,22,23,45],[3,9,30,31,34,44],[5,7,24,25,39,48],[8,28,32,37,42,46]]
    },
    {
        "strategy": "p1_dev_sum5bet (edge300=+4.04%)",
        "num_bets": 5,
        "bets": [[6,11,12,22,23,45],[3,9,30,31,34,44],[5,7,24,25,39,48],[8,28,32,37,42,46],[10,16,17,19,40,49]]
    },
]

for s in strategies:
    added = logger.log_prediction(
        lottery_type='BIG_LOTTO',
        period=PERIOD,
        strategy=s['strategy'],
        num_bets=s['num_bets'],
        bets=s['bets'],
        specials=None,
    )
    status = "新增" if added else "已存在"
    print(f"{status}: {s['strategy']}")

print(f"\n共記錄 {len(strategies)} 策略，期號 {PERIOD}")
