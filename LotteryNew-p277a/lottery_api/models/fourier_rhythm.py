import numpy as np
from scipy.fft import fft
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class FourierRhythmPredictor:
    """
    Fourier Rhythm Predictor (Phase 39)
    分析彩票號碼（特別是特別號）的頻域特徵，捕捉潛在的週期性規律。
    """
    def __init__(self, min_val: int = 1, max_val: int = 8):
        self.min_val = min_val
        self.max_val = max_val
        self.num_range = max_val - min_val + 1

    def predict(self, history: List[Dict], window_sizes: List[int] = [64, 128, 256]) -> Dict[int, float]:
        """
        對歷史數據進行多尺度傅立葉變換分析。
        
        Args:
            history: 歷史數據（最新在前）
            window_sizes: 分析窗口大小
            
        Returns:
            號碼機率分布 {num: probability}
        """
        # 提取特別號序列
        specials = [d.get('special') for d in history if d.get('special') is not None]
        
        if len(specials) < 32:
            return {n: 1.0/self.num_range for n in range(self.min_val, self.max_val + 1)}

        combined_scores = {n: 0.0 for n in range(self.min_val, self.max_val + 1)}
        active_windows = 0

        for w in window_sizes:
            if len(specials) < w:
                continue
            
            # 1. 準備數據 (轉為時間正序)
            current_seq = np.array(list(reversed(specials[:w])), dtype=float)
            
            # 2. 去均值化 (Zero-center)
            mean_val = np.mean(current_seq)
            centered = current_seq - mean_val
            
            # 3. FFT 變換
            xf = fft(centered)
            mags = np.abs(xf)
            
            # 只取前半部分（對稱性）
            half = len(mags) // 2
            if half <= 1: continue
            
            # 4. 尋找最強的 Top-3 頻率成分 (排除 DC 分量 index 0)
            dominants = np.argsort(mags[1:half])[-3:] + 1 # +1 是因為跳過了 index 0
            
            # 5. 信號重建與外推 (Extrapolation at t = w)
            # 我們要預測下一個點 t_next = w
            t_next = w
            recon_val = 0.0
            
            # 計算 SNR (最強頻率 vs 平均噪聲) 用於信心度參考
            max_mag = mags[dominants[-1]] if len(dominants) > 0 else 0
            avg_mag = np.mean(mags[1:half])
            snr = max_mag / (avg_mag + 1e-9)
            
            for k in dominants:
                # 訊號分量：A * exp(i * 2*pi * k * t / N)
                # 這裡需要考慮相位和振幅
                phase = np.angle(xf[k])
                amplitude = mags[k] / w
                
                # 簡化重建：sum (A * cos(2*pi*k*t/N + phase))
                # 注意：FFT 結果包含實部與虛部，標準重建是 ifft
                # 但我們只需要外推一個點
                val_at_t = 2.0 * amplitude * np.cos(2.0 * np.pi * k * t_next / w + phase)
                recon_val += val_at_t
            
            # 6. 加入均值並映射到號碼空間
            predicted_number = recon_val + mean_val
            
            # 7. 分數分配 (基於連續高斯分布的簡化)
            weight = np.log2(snr + 1.5) # SNR 越高，權重越大
            
            # 找到最接近的整數號碼
            clamped = max(self.min_val, min(self.max_val, round(predicted_number)))
            combined_scores[int(clamped)] += weight
            
            # 對相鄰號碼也給予少量權重 (防止過擬合)
            for offset in [-1, 1]:
                neighbor = int(clamped) + offset
                if self.min_val <= neighbor <= self.max_val:
                    combined_scores[neighbor] += weight * 0.4
            
            active_windows += 1

        # 8. 補充規則：檢查遺漏期數與頻率 (防止傅立葉完全脫離長期偏差)
        # 這裡不在此處做，由 SpecialPredictor 綜合判讀
        
        # 9. 正規化
        total_score = sum(combined_scores.values())
        if total_score > 0:
            return {n: combined_scores[n] / total_score for n in range(self.min_val, self.max_val + 1)}
        else:
            return {n: 1.0/self.num_range for n in range(self.min_val, self.max_val + 1)}

    def predict_main_numbers(self, history: List[Dict], max_num: int = 38, window_sizes: List[int] = [64, 128]) -> Dict[int, float]:
        """
        對主號碼池進行傅立葉分析 (Bitstream Fourier)
        """
        if len(history) < 32:
            return {n: 1.0 for n in range(1, max_num + 1)}

        scores = {n: 0.0 for n in range(1, max_num + 1)}
        
        # 準備每個號碼的位元流 (正序)
        # 為了效率，我們預先提取所有號碼
        for w in window_sizes:
            if len(history) < w: continue
            
            h_slice = history[:w]
            # 建立 1..max_num 的存在矩陣 [max_num, w]
            bitstreams = np.zeros((max_num + 1, w), dtype=float)
            for idx, d in enumerate(h_slice):
                for num in d.get('numbers', []):
                    if 1 <= num <= max_num:
                        # 注意：history 是倒序，所以 t = (w - 1) - idx
                        bitstreams[num][w - 1 - idx] = 1.0
            
            for n in range(1, max_num + 1):
                seq = bitstreams[n]
                mean_val = np.mean(seq)
                if mean_val == 0: continue
                
                centered = seq - mean_val
                xf = fft(centered)
                mags = np.abs(xf)
                
                half = len(mags) // 2
                if half <= 1: continue
                
                # 尋找最強頻率
                dominants = np.argsort(mags[1:half])[-2:] + 1
                
                t_next = w
                recon_val = 0.0
                for k in dominants:
                    phase = np.angle(xf[k])
                    amplitude = mags[k] / w
                    recon_val += 2.0 * amplitude * np.cos(2.0 * np.pi * k * t_next / w + phase)
                
                # 映射到機率空間 (recon_val + mean_val 越接近 1 代表週期性支持出現)
                score = recon_val + mean_val
                if score > 0:
                    scores[n] += score * np.log(w) # 較大窗口給予較高權重
                    
        return scores

# 單例模式或工廠函數
fourier_predictor = FourierRhythmPredictor()
