
    def _zone_analysis(self, history: List[Dict], min_num: int, max_num: int) -> Dict[int, float]:
        """
        區間分析：根據近期熱門區間加權
        """
        scores = {num: 0.5 for num in range(min_num, max_num + 1)}
        if not history: return scores
        
        # 將號碼分為 5 個區間
        range_len = max_num - min_num + 1
        zone_size = max(1, range_len // 5)
        recent = history[-10:] # 最近10期
        zone_counts = Counter()
        
        for draw in recent:
            for num in draw['numbers']:
                zone_idx = (num - min_num) // zone_size
                zone_counts[zone_idx] += 1
        
        max_count = max(zone_counts.values()) if zone_counts else 1
        
        for num in range(min_num, max_num + 1):
            zone_idx = (num - min_num) // zone_size
            # 熱門區間加分
            scores[num] = zone_counts[zone_idx] / max_count
            
        return scores

    def _last_digit_analysis(self, history: List[Dict], min_num: int, max_num: int) -> Dict[int, float]:
        """
        尾數分析：統計號碼尾數的規律
        """
        scores = {num: 0.5 for num in range(min_num, max_num + 1)}
        if not history: return scores
        
        recent = history[-20:]
        digit_counts = Counter()
        
        for draw in recent:
            for num in draw['numbers']:
                last_digit = num % 10
                digit_counts[last_digit] += 1
                
        max_count = max(digit_counts.values()) if digit_counts else 1
        
        for num in range(min_num, max_num + 1):
            last_digit = num % 10
            scores[num] = digit_counts[last_digit] / max_count
            
        return scores

    def _odd_even_analysis(self, history: List[Dict], min_num: int, max_num: int) -> Dict[int, float]:
        """
        奇偶分析：分析奇偶數比例
        """
        scores = {num: 0.5 for num in range(min_num, max_num + 1)}
        if not history: return scores
        
        recent = history[-20:]
        odd_count = 0
        total_nums = 0
        
        for draw in recent:
            for num in draw['numbers']:
                if num % 2 != 0:
                    odd_count += 1
                total_nums += 1
                
        odd_ratio = odd_count / total_nums if total_nums > 0 else 0.5
        
        # 假設趨勢延續：如果近期奇數多，則給奇數較高分
        for num in range(min_num, max_num + 1):
            is_odd = num % 2 != 0
            # 將分數映射到 0.3 - 0.7 之間，避免過度極端
            base_score = odd_ratio if is_odd else (1 - odd_ratio)
            scores[num] = 0.3 + (base_score * 0.4)
            
        return scores
