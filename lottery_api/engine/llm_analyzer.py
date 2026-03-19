"""
LLM 分析器 — Phase 2 Multi-Provider Router
==========================================
Provider 優先順序: mock → Groq → Anthropic → OpenAI
無需修改程式碼，設定環境變數即可切換。

啟用方式:
    export GROQ_API_KEY=gsk_xxx       # Groq (免費, 最快)
    export ANTHROPIC_API_KEY=sk-ant-xxx  # Anthropic Claude
    export OPENAI_API_KEY=sk-xxx      # OpenAI

輸出: lottery_api/data/llm_analysis_log.jsonl
"""
import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Tuple


DATA_DIR = Path(__file__).parent.parent / 'data'
LOG_PATH = DATA_DIR / 'llm_analysis_log.jsonl'
ENV_PATH = Path(__file__).parent.parent / '.env'

# Try loading local .env for API keys (non-fatal if dotenv is unavailable).
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(ENV_PATH, override=False)
except Exception:
    pass

LOTTERY_NAMES = {
    'BIG_LOTTO':   '大樂透',
    'POWER_LOTTO': '威力彩',
    'DAILY_539':   '今彩539',
}

TREND_LABELS = {
    'STABLE':       '穩定',
    'ACCELERATING': '加速上升',
    'DECELERATING': '減速下降',
    'REGIME_SHIFT': '體制轉移',
}


# ─────────────────────────────────────────────
# Provider 偵測
# ─────────────────────────────────────────────

def _detect_provider() -> str:
    """依環境變數順序偵測可用 provider。"""
    if os.getenv('GROQ_API_KEY'):
        return 'groq'
    if os.getenv('ANTHROPIC_API_KEY'):
        return 'anthropic'
    if os.getenv('OPENAI_API_KEY'):
        return 'openai'
    return 'mock'


# ─────────────────────────────────────────────
# Prompt 組裝
# ─────────────────────────────────────────────

def _build_prompt(lottery_type: str, states: dict) -> str:
    """將 StrategyState dict 組裝為 LLM 分析 prompt。"""
    lt_name = LOTTERY_NAMES.get(lottery_type, lottery_type)
    lines = [
        f"你是一個彩票策略分析師，負責監控{lt_name}的滾動驗證數據（RSM）。",
        f"以下是各策略最新狀態（{datetime.now().strftime('%Y-%m-%d')}）：",
        "",
    ]
    for name, s in states.items():
        e30  = s.get('edge_30p', 0) * 100
        e100 = s.get('edge_100p', 0) * 100
        e300 = s.get('edge_300p', 0) * 100
        trend = TREND_LABELS.get(s.get('trend', ''), s.get('trend', ''))
        neg_streak = s.get('consecutive_neg_30p', 0)
        alert = s.get('alert', False)
        alert_tag = " ⚠️ 警示" if alert else ""
        lines.append(f"策略: {name}{alert_tag}")
        lines.append(f"  三窗口 Edge: 30期={e30:+.2f}%  100期={e100:+.2f}%  300期={e300:+.2f}%")
        lines.append(f"  趨勢: {trend}  連續負30期: {neg_streak}期")
        lines.append("")

    lines += [
        "請分析上述數據，回答以下三點（純中文，每點不超過60字）：",
        "1. 【健康度評估】整體策略健康狀況如何？",
        "2. 【警示項目】有哪些策略需要特別注意？",
        "3. 【建議行動】近期建議的監控重點或調整方向？",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Mock 輸出
# ─────────────────────────────────────────────

def _mock_analyze(lottery_type: str, states: dict) -> tuple[str, int]:
    """不需要 API Key 的模板分析。"""
    lt_name = LOTTERY_NAMES.get(lottery_type, lottery_type)
    total = len(states)
    alerts = [n for n, s in states.items() if s.get('alert') or s.get('consecutive_neg_30p', 0) > 10]
    stable = [n for n, s in states.items()
              if s.get('edge_30p', 0) > 0 and s.get('edge_100p', 0) > 0 and s.get('edge_300p', 0) > 0]

    health_msg = (
        f"共 {total} 個策略，{len(stable)} 個三窗口全正。"
        if stable else
        f"共 {total} 個策略，目前無三窗口全正策略，需持續觀察。"
    )

    if alerts:
        warn_msg = f"【{alerts[0]}】連續負Edge或已觸發警示，建議核查是否進入衰退期。"
    else:
        warn_msg = "目前無策略觸發警示閾值，整體穩定。"

    # 找出最強策略（300p Edge 最高）
    best = max(states.items(), key=lambda x: x[1].get('edge_300p', -999), default=(None, {}))
    best_name = best[0] or '未知'
    best_e300 = best[1].get('edge_300p', 0) * 100

    action_msg = (
        f"建議重點監控 {best_name}（300期 Edge {best_e300:+.2f}%），"
        f"並於下次{lt_name}開獎後更新 RSM 數據。"
    )

    analysis = (
        f"[MOCK] {lt_name} 策略分析\n"
        f"1. 【健康度評估】{health_msg}\n"
        f"2. 【警示項目】{warn_msg}\n"
        f"3. 【建議行動】{action_msg}"
    )
    return analysis, 0  # (text, prompt_tokens)


# ─────────────────────────────────────────────
# Groq
# ─────────────────────────────────────────────

def _groq_analyze(prompt: str) -> tuple[str, int]:
    try:
        from groq import Groq
        client = Groq(api_key=os.environ['GROQ_API_KEY'])
        resp = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=300,
            temperature=0.3,
        )
        text = resp.choices[0].message.content.strip()
        tokens = resp.usage.prompt_tokens if resp.usage else 0
        return text, tokens
    except ImportError:
        raise RuntimeError("groq 套件未安裝，執行: pip install groq")


# ─────────────────────────────────────────────
# Anthropic
# ─────────────────────────────────────────────

def _anthropic_analyze(prompt: str) -> tuple[str, int]:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=300,
            messages=[{'role': 'user', 'content': prompt}],
        )
        text = msg.content[0].text.strip()
        tokens = msg.usage.input_tokens if msg.usage else 0
        return text, tokens
    except ImportError:
        raise RuntimeError("anthropic 套件未安裝，執行: pip install anthropic")


# ─────────────────────────────────────────────
# OpenAI
# ─────────────────────────────────────────────

def _openai_analyze(prompt: str) -> tuple[str, int]:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
        resp = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=300,
            temperature=0.3,
        )
        text = resp.choices[0].message.content.strip()
        tokens = resp.usage.prompt_tokens if resp.usage else 0
        return text, tokens
    except ImportError:
        raise RuntimeError("openai 套件未安裝，執行: pip install openai")


def _with_retry(
    fn: Callable[[str], Tuple[str, int]],
    prompt: str,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> tuple[str, int]:
    """
    Retry network-bound LLM calls with exponential backoff.
    """
    last_err = None
    for i in range(max_retries):
        try:
            return fn(prompt)
        except Exception as e:
            last_err = e
            if i == max_retries - 1:
                break
            time.sleep(base_delay * (2 ** i))
    raise last_err


# ─────────────────────────────────────────────
# 主類別
# ─────────────────────────────────────────────

class LLMAnalyzer:
    def __init__(self):
        self._provider = _detect_provider()

    def get_provider(self) -> str:
        return self._provider

    def analyze_rsm(self, lottery_type: str, states: dict, trigger: str = 'manual') -> str:
        """
        分析 RSM 策略狀態，回傳中文分析文字。

        Args:
            lottery_type: 'BIG_LOTTO' / 'POWER_LOTTO' / 'DAILY_539'
            states: dict[strategy_name, state_dict]  (來自 strategy_states_*.json)
            trigger: 'auto' | 'manual'

        Returns:
            中文分析文字
        """
        if not states:
            return ""

        provider = self._provider
        try:
            if provider == 'mock':
                analysis, tokens = _mock_analyze(lottery_type, states)
            else:
                prompt = _build_prompt(lottery_type, states)
                if provider == 'groq':
                    analysis, tokens = _with_retry(_groq_analyze, prompt, max_retries=3, base_delay=1.0)
                elif provider == 'anthropic':
                    analysis, tokens = _with_retry(_anthropic_analyze, prompt, max_retries=3, base_delay=1.0)
                elif provider == 'openai':
                    analysis, tokens = _with_retry(_openai_analyze, prompt, max_retries=3, base_delay=1.0)
                else:
                    analysis, tokens = _mock_analyze(lottery_type, states)
        except Exception as e:
            analysis = f"[LLM ERROR] provider={provider}: {e}"
            tokens = 0

        self._log(lottery_type, provider, trigger, tokens, analysis)
        return analysis

    def analyze_all(self, trigger: str = 'manual') -> dict[str, str]:
        """分析三彩種，回傳 {lottery_type: analysis} dict。"""
        results = {}
        for lt in ['BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539']:
            states = _load_strategy_states(lt)
            if states:
                results[lt] = self.analyze_rsm(lt, states, trigger=trigger)
        return results

    def _log(self, lottery_type: str, provider: str, trigger: str, tokens: int, analysis: str):
        """寫入 llm_analysis_log.jsonl。"""
        record = {
            'ts': int(time.time()),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'trigger': trigger,
            'lottery_type': lottery_type,
            'provider': provider,
            'prompt_tokens': tokens,
            'analysis': analysis,
        }
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(LOG_PATH, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        except Exception:
            pass  # 日誌失敗不影響主流程


# ─────────────────────────────────────────────
# 輔助函數
# ─────────────────────────────────────────────

def _load_strategy_states(lottery_type: str) -> dict:
    """從 strategy_states_{LOTTERY_TYPE}.json 載入策略狀態。"""
    path = DATA_DIR / f'strategy_states_{lottery_type}.json'
    if not path.exists():
        return {}
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def load_recent_log(n: int = 5) -> list[dict]:
    """讀取最近 n 筆分析紀錄。"""
    if not LOG_PATH.exists():
        return []
    lines = LOG_PATH.read_text(encoding='utf-8').strip().splitlines()
    records = []
    for line in lines[-n:]:
        try:
            records.append(json.loads(line))
        except Exception:
            pass
    return records
