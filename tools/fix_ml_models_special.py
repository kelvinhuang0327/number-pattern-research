#!/usr/bin/env python3
"""
批量修復機器學習模型，添加特別號碼支援
包括：prophet_model.py, xgboost_model.py, autogluon_model.py, lstm_model.py
"""
import os
import re

def fix_prophet_model():
    """修復 Prophet 模型"""
    file_path = '/Users/kelvin/Kelvin-WorkSpace/Lottery/lottery-api/models/prophet_model.py'

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. 添加 import（如果沒有）
    if 'from .unified_predictor import predict_special_number' not in content:
        # 在最後一個 import 後面添加
        import_pattern = r'(from collections import Counter\n)'
        content = re.sub(
            import_pattern,
            r'\1from .unified_predictor import predict_special_number\n',
            content
        )

    # 2. 修改 return 語句（在 line 85-98）
    # 找到 return { "numbers": predicted_numbers, ... }
    old_return = r'''            return \{
                "numbers": predicted_numbers,
                "confidence": confidence,
                "method": "Prophet 時間序列分析",
                "probabilities": None,
                "trend": trend,
                "seasonality": "檢測到每週週期性模式",
                "modelInfo": \{
                    "trainingSize": len\(history\),
                    "version": "1\.0",
                    "algorithm": "Prophet \(Facebook\)"
                \},
                "notes": "基於歷史數據的時間序列趨勢和週期性分析，結合頻率統計確保預測的穩定性"
            \}'''

    new_return = '''            # 🔧 預測特別號碼
            predicted_special = predict_special_number(history, lottery_rules, predicted_numbers)

            result = {
                "numbers": predicted_numbers,
                "confidence": confidence,
                "method": "Prophet 時間序列分析",
                "probabilities": None,
                "trend": trend,
                "seasonality": "檢測到每週週期性模式",
                "modelInfo": {
                    "trainingSize": len(history),
                    "version": "1.0",
                    "algorithm": "Prophet (Facebook)"
                },
                "notes": "基於歷史數據的時間序列趨勢和週期性分析，結合頻率統計確保預測的穩定性"
            }

            # 🔧 添加特別號碼
            if predicted_special is not None:
                result['special'] = predicted_special

            return result'''

    content = re.sub(old_return, new_return, content, flags=re.DOTALL)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ prophet_model.py 修復完成")

def fix_xgboost_model():
    """修復 XGBoost 模型"""
    file_path = '/Users/kelvin/Kelvin-WorkSpace/Lottery/lottery-api/models/xgboost_model.py'

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. 添加 import
    if 'from .unified_predictor import predict_special_number' not in content:
        import_pattern = r'(from sklearn\.preprocessing import MultiLabelBinarizer\n)'
        content = re.sub(
            import_pattern,
            r'\1from .unified_predictor import predict_special_number\n',
            content
        )

    # 2. 修改 return 語句（在 line 86-99）
    old_return = r'''            return \{
                "numbers": top_numbers,
                "confidence": float\(confidence\),
                "method": "XGBoost 梯度提升決策樹",
                "probabilities": \[float\(prob\) for num, prob in sorted_numbers\[:pick_count\]\],
                "trend": trend,
                "seasonality": None,
                "modelInfo": \{
                    "trainingSize": len\(train_history\),
                    "version": "1\.0",
                    "algorithm": "XGBoost Multi-label"
                \},
                "notes": "基於歷史開獎模式的機器學習預測，分析號碼間的關聯性"
            \}'''

    new_return = '''            # 🔧 預測特別號碼
            predicted_special = predict_special_number(history, lottery_rules, top_numbers)

            result = {
                "numbers": top_numbers,
                "confidence": float(confidence),
                "method": "XGBoost 梯度提升決策樹",
                "probabilities": [float(prob) for num, prob in sorted_numbers[:pick_count]],
                "trend": trend,
                "seasonality": None,
                "modelInfo": {
                    "trainingSize": len(train_history),
                    "version": "1.0",
                    "algorithm": "XGBoost Multi-label"
                },
                "notes": "基於歷史開獎模式的機器學習預測，分析號碼間的關聯性"
            }

            # 🔧 添加特別號碼
            if predicted_special is not None:
                result['special'] = predicted_special

            return result'''

    content = re.sub(old_return, new_return, content, flags=re.DOTALL)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ xgboost_model.py 修復完成")

def fix_autogluon_model():
    """修復 AutoGluon 模型"""
    file_path = '/Users/kelvin/Kelvin-WorkSpace/Lottery/lottery-api/models/autogluon_model.py'

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. 添加 import
    if 'from .unified_predictor import predict_special_number' not in content:
        import_pattern = r'(from collections import Counter\n)'
        content = re.sub(
            import_pattern,
            r'\1from .unified_predictor import predict_special_number\n',
            content
        )

    # 2. 修改 return 語句（在 line 52-65）
    old_return = r'''            return \{
                "numbers": predicted_numbers,
                "confidence": confidence,
                "method": "AutoGluon 智能混合策略",
                "probabilities": None,
                "trend": "基於頻率、趨勢和統計特徵的混合預測",
                "seasonality": None,
                "modelInfo": \{
                    "trainingSize": len\(recent_history\),
                    "version": "1\.0-fast",
                    "algorithm": "Hybrid Frequency \+ Statistical Features"
                \},
                "notes": "採用輕量級混合策略，結合頻率分析、遺漏值、冷熱號分析等多種特徵"
            \}'''

    new_return = '''            # 🔧 預測特別號碼
            predicted_special = predict_special_number(history, lottery_rules, predicted_numbers)

            result = {
                "numbers": predicted_numbers,
                "confidence": confidence,
                "method": "AutoGluon 智能混合策略",
                "probabilities": None,
                "trend": "基於頻率、趨勢和統計特徵的混合預測",
                "seasonality": None,
                "modelInfo": {
                    "trainingSize": len(recent_history),
                    "version": "1.0-fast",
                    "algorithm": "Hybrid Frequency + Statistical Features"
                },
                "notes": "採用輕量級混合策略，結合頻率分析、遺漏值、冷熱號分析等多種特徵"
            }

            # 🔧 添加特別號碼
            if predicted_special is not None:
                result['special'] = predicted_special

            return result'''

    content = re.sub(old_return, new_return, content, flags=re.DOTALL)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ autogluon_model.py 修復完成")

def fix_lstm_model():
    """修復 LSTM 模型"""
    file_path = '/Users/kelvin/Kelvin-WorkSpace/Lottery/lottery-api/models/lstm_model.py'

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. 添加 import
    if 'from .unified_predictor import predict_special_number' not in content:
        # 在 logger 定義之前添加
        import_pattern = r'(logger = logging\.getLogger\(__name__\))'
        content = re.sub(
            import_pattern,
            r'from .unified_predictor import predict_special_number\n\n\1',
            content
        )

    # 2. 修改 return 語句（在 line 84-95）
    # 注意：LSTM 模型的 return 在 try-except 塊內
    old_return = r'''            return \{
                "numbers": predicted_numbers,
                "confidence": float\(confidence\),
                "method": "LSTM 深度神經網絡",
                "probabilities": \[float\(prob\) for _, prob in sorted_numbers\[:pick_count\]\],
                "trend": "LSTM 深度學習趨勢預測",
                "modelInfo": \{
                    "framework": "TensorFlow/Keras",
                    "architecture": "LSTM -> Dropout -> Dense",
                    "window_size": window_size
                \}
            \}'''

    new_return = '''            # 🔧 預測特別號碼
            predicted_special = predict_special_number(history, lottery_rules, predicted_numbers)

            result = {
                "numbers": predicted_numbers,
                "confidence": float(confidence),
                "method": "LSTM 深度神經網絡",
                "probabilities": [float(prob) for _, prob in sorted_numbers[:pick_count]],
                "trend": "LSTM 深度學習趨勢預測",
                "modelInfo": {
                    "framework": "TensorFlow/Keras",
                    "architecture": "LSTM -> Dropout -> Dense",
                    "window_size": window_size
                }
            }

            # 🔧 添加特別號碼
            if predicted_special is not None:
                result['special'] = predicted_special

            return result'''

    content = re.sub(old_return, new_return, content, flags=re.DOTALL)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ lstm_model.py 修復完成")

if __name__ == '__main__':
    print("🔧 開始修復機器學習模型...")
    print()

    try:
        fix_prophet_model()
        fix_xgboost_model()
        fix_autogluon_model()
        fix_lstm_model()

        print()
        print("=" * 60)
        print("✅ 所有機器學習模型修復完成！")
        print("=" * 60)
        print()
        print("修復的模型：")
        print("  1. prophet_model.py - Prophet 時間序列分析")
        print("  2. xgboost_model.py - XGBoost 梯度提升")
        print("  3. autogluon_model.py - AutoGluon 混合策略")
        print("  4. lstm_model.py - LSTM 深度神經網絡")
        print()
        print("所有模型現在都會返回特別號碼（如果彩票類型需要）")

    except Exception as e:
        print(f"❌ 修復失敗: {e}")
        import traceback
        traceback.print_exc()
