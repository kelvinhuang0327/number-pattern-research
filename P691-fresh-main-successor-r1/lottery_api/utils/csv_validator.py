import csv
import io
import re
from datetime import datetime
from typing import List, Dict, Any, Tuple
import logging
from config import lottery_config

# Configure logger
logger = logging.getLogger(__name__)

class CSVValidator:
    """
    CSV/TXT 數據驗證工具
    提供詳細的錯誤報告和修正建議
    支援格式：
    - CSV: 標準逗號分隔格式
    - TXT: 今彩539官方格式
    """

    def _get_effective_pick_count(self, rules, play_mode: str = None) -> int:
        """
        獲取有效的號碼選取數量
        對於樂合彩系列，根據玩法模式返回對應的pickCount
        對於其他彩券，返回規則定義的pickCount
        """
        # 如果有指定 play_mode，使用對應規則
        if play_mode and getattr(rules, 'playModes', None) and play_mode in rules.playModes:
            return rules.playModes[play_mode].pickCount
            
        # 如果是子遊戲但沒指定 play_mode，使用自身定義的 pickCount (通常是完整號碼數)
        # 例如 49樂合彩 pickCount=6 (同大樂透)
        return rules.pickCount

    def _validate_play_mode(self, lottery_type: str, play_mode: str = None) -> Tuple[bool, str]:
        """
        驗證玩法模式是否有效
        Returns: (is_valid, error_message)
        """
        rules = lottery_config.get_rules(lottery_type)
        if not rules:
            return False, f"未知的彩券類型: {lottery_type}"

        # 子遊戲檢查 (僅當指定了 play_mode 時才驗證，未指定則視為匯入原始數據)
        if play_mode and play_mode not in getattr(rules, 'playModes', {}):
             available = ', '.join(getattr(rules, 'playModes', {}).keys())
             return False, f"無效的玩法模式: {play_mode}，可選: {available}"
             
        return True, ""

    def validate(self, content: bytes, lottery_type: str, file_type: str = 'csv', play_mode: str = None) -> Dict[str, Any]:
        """
        驗證 CSV/TXT 內容
        Args:
            content: 文件內容
            lottery_type: 彩券類型
            file_type: 文件類型 ('csv' 或 'txt')
            play_mode: 玩法模式（僅適用於樂合彩系列，例如：'二合', '三合', '四合'）
        """
        if file_type.lower() == 'txt':
            return self._validate_txt(content, lottery_type, play_mode)
        else:
            return self._validate_csv(content, lottery_type, play_mode)

    def _validate_txt(self, content: bytes, lottery_type: str, play_mode: str = None) -> Dict[str, Any]:
        """
        驗證 TXT 格式（今彩539官方格式）
        Args:
            content: 文件內容
            lottery_type: 彩券類型
            play_mode: 玩法模式（適用於樂合彩系列）
        """
        result = {
            "valid": True,
            "errors": [],
            "parsed_data": [],
            "stats": {"total_rows": 0, "valid_rows": 0, "error_rows": 0}
        }

        # 驗證玩法模式
        is_valid, error_msg = self._validate_play_mode(lottery_type, play_mode)
        if not is_valid:
            result["valid"] = False
            result["errors"].append({"line": 0, "message": error_msg, "suggestion": ""})
            return result

        rules = lottery_config.get_rules(lottery_type)
        if not rules:
            result["valid"] = False
            result["errors"].append({"line": 0, "message": f"未知的彩券類型: {lottery_type}", "suggestion": ""})
            return result

        # 獲取有效的號碼選取數量
        effective_pick_count = self._get_effective_pick_count(rules, play_mode)

        try:
            text = None
            detected_encoding = None
            for encoding in ['utf-8-sig', 'big5', 'cp950']:
                try:
                    text = content.decode(encoding).strip()
                    detected_encoding = encoding
                    break
                except UnicodeDecodeError:
                    continue
            
            if text is None:
                logger.error(f"[{lottery_type}] Encoding detection failed.")
                result["valid"] = False
                result["errors"].append({"line": 0, "message": "無法識別文件編碼 (支援 UTF-8 或 Big5)", "suggestion": "請將文件另存為 UTF-8 編碼"})
                return result

            logger.info(f"[{lottery_type}] Detected encoding: {detected_encoding}")
            logger.info(f"[{lottery_type}] File content preview (first 500 chars): {text[:500]}")

            if not text:
                result["valid"] = False
                result["errors"].append({"line": 0, "message": "文件為空", "suggestion": ""})
                return result

            lines = text.split('\n')
            i = 0
            line_num = 0

            while i < len(lines):
                line_num += 1
                line = lines[i].strip()
                
                # Debug log for every line
                # logger.debug(f"Processing line {line_num}: {line}")

                if not line:
                    i += 1
                    continue

                # 檢查是否為記錄開始
                # 支援: "第112000001期", "112000001期", "112000001"
                draw_match = re.search(r'(?:第)?(\d{6,})(?:期)?', line)
                
                if draw_match:
                    logger.info(f"Line {line_num}: Matched draw pattern. Content: '{line}'")
                    row_errors = []
                    parsed_row = None
                    try:
                        # 1. 提取期號
                        draw = draw_match.group(1)
                        start_line_index = i
                        logger.info(f"Line {line_num}: Found draw {draw}")

                        # 2. 尋找日期 (先找當前行，再往下找最多3行)
                        date_str = None
                        date_line_index = -1
                        lines_checked_for_date = 0
                        temp_i = start_line_index
                        
                        while temp_i < len(lines) and lines_checked_for_date < 4:
                            check_line = lines[temp_i].strip()
                            # 支援: "開獎日期: 112/01/01", "112/01/01", "2023-01-01"
                            date_match = re.search(r'(?:開獎日期[:：]\s*)?(\d{3,4})[/\-](\d{1,2})[/\-](\d{1,2})', check_line)
                            if date_match:
                                year_val = int(date_match.group(1))
                                month = date_match.group(2).zfill(2)
                                day = date_match.group(3).zfill(2)
                                
                                # 判斷是民國年還是西元年
                                if year_val > 1000:
                                    ad_year = year_val
                                else:
                                    ad_year = year_val + 1911
                                    
                                date_str = f"{ad_year}/{month}/{day}"
                                logger.info(f"  -> Found date: {date_str}")
                                date_line_index = temp_i
                                break
                            lines_checked_for_date += 1
                            temp_i += 1
                        
                        if not date_str:
                             logger.warning(f"Line {line_num}: Date not found for draw {draw}")
                             row_errors.append("缺少開獎日期")
                        
                        # 3. 尋找號碼 (從當前行往下找最多5行)
                        best_nums = []
                        best_line_idx = -1
                        lines_checked_for_nums = 0
                        temp_i = start_line_index
                        
                        while temp_i < len(lines) and lines_checked_for_nums < 6:
                            check_line = lines[temp_i].strip()
                            
                            # 如果是包含期號的行，移除期號以免干擾
                            if str(draw) in check_line:
                                check_line = check_line.replace(str(draw), '', 1)
                                
                            # 如果是包含日期的行，移除日期以免干擾
                            if temp_i == date_line_index:
                                check_line = re.sub(r'(?:開獎日期[:：]\s*)?(\d{3,4})[/\-](\d{1,2})[/\-](\d{1,2})', '', check_line)

                            clean_line = check_line
                            all_digits = re.findall(r'\d+', clean_line)
                            
                            current_nums = []
                            if len(all_digits) > 0:
                                # 🌟 新增邏輯：處理連號格式 (例如 08152324414702)
                                # 如果只有一個數字，且長度足夠長 (>= 2 * expected_count)，則嘗試切分
                                if len(all_digits) == 1 and len(all_digits[0]) >= (effective_pick_count * 2):
                                    long_num_str = all_digits[0]
                                    # 每2位切分
                                    split_nums = [int(long_num_str[k:k+2]) for k in range(0, len(long_num_str), 2)]
                                    # 過濾掉明顯不合理的數字 (例如 00 或 > 49，視規則而定)
                                    # 這裡先不做嚴格過濾，交給後面的驗證邏輯
                                    current_nums = split_nums
                                    logger.info(f"  -> Detected continuous number string '{long_num_str}', split into: {current_nums}")
                                else:
                                    try:
                                        current_nums = [int(d) for d in all_digits]
                                    except: pass
                                
                                # 特殊處理：3星/4星 連號 (e.g. 1234 -> [1,2,3,4])
                                is_permutation = getattr(rules, 'isPermutation', False)
                                if is_permutation and len(current_nums) == 1 and len(all_digits[0]) >= rules.pickCount:
                                    digit_str = all_digits[0]
                                    current_nums = [int(ch) for ch in digit_str]

                            # 評估候選行
                            if len(current_nums) > len(best_nums):
                                best_nums = current_nums
                                best_line_idx = temp_i
                            
                            # 如果已經完全滿足預期，直接選中並停止搜索
                            expected_count = effective_pick_count
                            if len(current_nums) >= expected_count:
                                best_nums = current_nums
                                best_line_idx = temp_i
                                break
                            
                            temp_i += 1
                            lines_checked_for_nums += 1

                        # Process the best candidate
                        if best_line_idx != -1 and len(best_nums) > 0:
                            # Update main pointer i to the last line used
                            max_idx = start_line_index
                            if date_line_index > max_idx: max_idx = date_line_index
                            if best_line_idx > max_idx: max_idx = best_line_idx
                            i = max_idx 
                            
                            logger.info(f"  -> Found numbers: {best_nums} (Expected >= {effective_pick_count})")
                            
                            parsed_nums = best_nums
                            expected_count = effective_pick_count # Re-define for scope safety

                            # --- 號碼驗證邏輯 ---
                            # 針對 49樂合彩 等附屬玩法的特殊處理
                            has_special = rules.hasSpecialNumber and len(parsed_nums) > expected_count
                            if getattr(rules, 'dependsOn', None) == 'BIG_LOTTO' and len(parsed_nums) == 7 and expected_count == 6:
                                parsed_nums = parsed_nums[:6]
                                has_special = False

                            if len(parsed_nums) < expected_count:
                                    logger.warning(f"Line {line_num}: Numbers insufficient. Got {len(parsed_nums)}, Expected {expected_count}")
                                    row_errors.append(f"號碼數量不足: 預期 {expected_count}, 實際 {len(parsed_nums)}")
                            else:
                                numbers = parsed_nums[:expected_count]
                                special = None
                                
                                if has_special and rules.hasSpecialNumber:
                                    special = parsed_nums[expected_count]

                                # Range Check
                                for n in numbers:
                                    if not (rules.minNumber <= n <= rules.maxNumber):
                                        row_errors.append(f"號碼 {n} 超出範圍 ({rules.minNumber}-{rules.maxNumber})")
                                
                                if special is not None:
                                    s_min = rules.specialMinNumber if rules.specialMinNumber else rules.minNumber
                                    s_max = rules.specialMaxNumber if rules.specialMaxNumber else rules.maxNumber
                                    if not (s_min <= special <= s_max):
                                        row_errors.append(f"特別號 {special} 超出範圍 ({s_min}-{s_max})")

                                repeats_allowed = getattr(rules, 'repeatsAllowed', False)
                                if not repeats_allowed and len(set(numbers)) != len(numbers):
                                    row_errors.append("號碼重複")
                                    
                                if not row_errors:
                                    final_numbers = numbers if is_permutation else sorted(numbers)
                                    parsed_row = {
                                        "date": date_str,
                                        "draw": draw,
                                        "numbers": final_numbers,
                                        "special": special,
                                        "lotteryType": lottery_type
                                    }
                                    result["parsed_data"].append(parsed_row)
                                    result["stats"]["valid_rows"] += 1
                                else:
                                    for e in row_errors:
                                        result["errors"].append({"line": line_num, "message": e, "content": lines[best_line_idx].strip()})
                                    result["stats"]["error_rows"] += 1
                        
                        else:
                                # 如果沒找到號碼 (Scan 5 lines and found nothing resembling numbers)
                                if date_str:
                                    logger.warning(f"Line {line_num}: No numbers found in search window for draw {draw}")
                                    result["errors"].append({"line": line_num, "message": f"找不到號碼行 (預期 {effective_pick_count} 個數字)", "content": line})
                                    result["stats"]["error_rows"] += 1

                    except Exception as e:
                        logger.error(f"Parsing error at line {line_num}: {e}")
                        result["errors"].append({
                            "line": line_num,
                            "message": f"解析錯誤: {str(e)}",
                            "content": line
                        })
                        result["stats"]["error_rows"] += 1

                i += 1

            if result["stats"]["error_rows"] > 0:
                result["valid"] = False

        except Exception as e:
            result["valid"] = False
            result["errors"].append({"line": 0, "message": f"TXT 解析嚴重錯誤: {str(e)}", "suggestion": "檢查文件編碼或格式"})

        return result

    def _validate_csv(self, content: bytes, lottery_type: str, play_mode: str = None) -> Dict[str, Any]:
        """
        驗證 CSV 格式
        Args:
            content: 文件內容
            lottery_type: 彩券類型
            play_mode: 玩法模式（適用於樂合彩系列）
        """
        result = {
            "valid": True,
            "errors": [],
            "parsed_data": [],
            "stats": {"total_rows": 0, "valid_rows": 0, "error_rows": 0}
        }

        # 驗證玩法模式
        is_valid, error_msg = self._validate_play_mode(lottery_type, play_mode)
        if not is_valid:
            result["valid"] = False
            result["errors"].append({"line": 0, "message": error_msg, "suggestion": ""})
            return result

        rules = lottery_config.get_rules(lottery_type)
        if not rules:
            result["valid"] = False
            result["errors"].append({"line": 0, "message": f"未知的彩券類型: {lottery_type}", "suggestion": ""})
            return result

        # 獲取有效的號碼選取數量
        effective_pick_count = self._get_effective_pick_count(rules, play_mode)

        try:
            text = content.decode('utf-8-sig').strip()
            if not text:
                result["valid"] = False
                result["errors"].append({"line": 0, "message": "文件為空", "suggestion": ""})
                return result
                
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)
            if not rows:
                result["valid"] = False
                result["errors"].append({"line": 0, "message": "無數據", "suggestion": ""})
                return result

            # Header Check
            # Assuming format: Date, Draw, Num1, Num2...
            
            result["stats"]["total_rows"] = len(rows) - 1 

            for idx, row in enumerate(rows[1:], start=2):
                row_errors = []
                parsed_row = None
                
                # Check column count
                expected_cols = 2 + effective_pick_count + (1 if rules.hasSpecialNumber else 0)
                if len(row) < expected_cols:
                    row_errors.append(f"欄位數量不足 (預期 {expected_cols}, 實際 {len(row)})")
                
                if not row_errors:
                    date_str = row[0].strip()
                    draw_str = row[1].strip()
                    numbers = []
                    special = None
                    
                    # 1. Date Validation
                    try:
                        dt = None
                        for fmt in ['%Y/%m/%d', '%Y-%m-%d', '%Y.%m.%d']:
                            try:
                                dt = datetime.strptime(date_str, fmt)
                                break
                            except ValueError: continue
                        
                        if not dt:
                            row_errors.append(f"日期格式無效: {date_str} (建議: YYYY/MM/DD)")
                        else:
                            date_str = dt.strftime('%Y/%m/%d')
                    except Exception:
                        row_errors.append(f"日期無法解析: {date_str}")

                    # 2. Draw Validation
                    if not re.match(r'^\d+$', draw_str):
                        row_errors.append(f"期號必須為數字: {draw_str}")

                    # 3. Numbers Validation
                    try:
                        raw_nums = row[2:2+effective_pick_count]
                        for n_str in raw_nums:
                            try:
                                n = int(n_str)
                                if not (rules.minNumber <= n <= rules.maxNumber):
                                    row_errors.append(f"號碼 {n} 超出範圍 ({rules.minNumber}-{rules.maxNumber})")
                                numbers.append(n)
                            except ValueError:
                                row_errors.append(f"號碼必須為整數: {n_str}")
                        
                        # 檢查重複 (除非規則允許)
                        repeats_allowed = getattr(rules, 'repeatsAllowed', False)
                        if not repeats_allowed and len(set(numbers)) != len(numbers):
                            row_errors.append("號碼重複")

                    except IndexError:
                        row_errors.append("號碼欄位缺失")
                        
                    # 4. Special Number
                    if rules.hasSpecialNumber:
                        try:
                            spec_idx = 2 + effective_pick_count
                            if spec_idx < len(row):
                                spec_str = row[spec_idx]
                                s = int(spec_str)
                                if rules.specialMinNumber and rules.specialMaxNumber:
                                    if not (rules.specialMinNumber <= s <= rules.specialMaxNumber):
                                        row_errors.append(f"特別號 {s} 超出範圍 ({rules.specialMinNumber}-{rules.specialMaxNumber})")
                                special = s
                            else:
                                row_errors.append("特別號欄位缺失")
                        except ValueError:
                            row_errors.append("特別號必須為整數")
                            
                    if not row_errors:
                        # 排列型彩票(3星/4星)不排序號碼
                        is_permutation = getattr(rules, 'isPermutation', False)
                        final_numbers = numbers if is_permutation else sorted(numbers)

                        parsed_row = {
                            "date": date_str,
                            "draw": draw_str,
                            "numbers": final_numbers,
                            "special": special,
                            "lotteryType": lottery_type
                        }
                
                if row_errors:
                    for e in row_errors:
                        result["errors"].append({
                            "line": idx, 
                            "message": e, 
                            "content": str(row)
                        })
                    result["stats"]["error_rows"] += 1
                else:
                    result["parsed_data"].append(parsed_row)
                    result["stats"]["valid_rows"] += 1
            
            if result["stats"]["error_rows"] > 0:
                result["valid"] = False
                
        except Exception as e:
            result["valid"] = False
            result["errors"].append({"line": 0, "message": f"CSV 解析嚴重錯誤: {str(e)}", "suggestion": "檢查文件編碼或格式"})
            
        return result

# Singleton
csv_validator = CSVValidator()
