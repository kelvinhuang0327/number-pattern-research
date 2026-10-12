"""
NLP 賽前特徵提取層 (Pre-game NLP Feature Extractor)
====================================================
借鑑 MiroFish report_agent.py 的 ReACT（推理→行動→觀察）模式。

支援多 Provider（自動 fallback 鏈）：
  1. Groq       — 免費 API，速度最快 (100+ tok/s)，推薦首選
  2. Gemini     — Google 免費 tier (15 RPM)
  3. Anthropic  — Claude Haiku，精準但需付費
  4. OpenRouter — 聚合器，部分模型免費
  5. Ollama     — 本地端（需自行架設）
  6. 規則引擎   — 純關鍵字分析（最終 fallback，無 API 需求）
  7. 聯盟基準值 — 所有方法失敗時的保險

API Key 從環境變數 (.env) 讀取，無需修改程式碼。

Category L 輸出：11 個 NLP 語義特徵

設計原則：
  - 開賽前狀態隔離 (只處理 game_time 之前的文字)
  - 延遲 < 30 秒（Groq 約 1-3 秒，Gemini 約 3-8 秒）
  - 無 Look-ahead（文字輸入由呼叫者負責過濾日期）
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── 載入 .env（如果存在） ────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv 未安裝時從系統環境變數讀取

# ── 是否有 requests ──────────────────────────────────────────────────────────
try:
    import requests as _requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

# ── Provider 設定（從環境變數讀取） ──────────────────────────────────────────
_NLP_PROVIDER = os.getenv("NLP_LLM_PROVIDER", "groq")   # 預設 Groq
_GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
_ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_OLLAMA_MODEL = "qwen2.5:7b"
_TIMEOUT = int(os.getenv("NLP_LLM_TIMEOUT", "25"))

# ── 聯盟基準特徵 ─────────────────────────────────────────────────────────────
_NEUTRAL_FEATURES: dict[str, float] = {
    "nlp_home_starter_confidence":  0.70,
    "nlp_away_starter_confidence":  0.70,
    "nlp_home_injury_severity":     0.00,
    "nlp_away_injury_severity":     0.00,
    "nlp_home_sentiment":           0.00,
    "nlp_away_sentiment":           0.00,
    "nlp_weather_impact":           0.00,
    "nlp_lineup_stability_diff":    0.00,
    "nlp_motivation_diff":          0.00,
    "nlp_composite_nlp_advantage":  0.00,
    "nlp_data_available":           0.00,   # 0=規則fallback, 1=LLM萃取
}

# ── 關鍵詞規則（規則引擎層） ─────────────────────────────────────────────────
_INJURY_KEYWORDS_ZH = [
    "傷", "傷勢", "傷兵", "受傷", "退出", "退賽", "無法出賽", "手術", "骨折", "扭傷",
    "拉傷", "肌肉", "韌帶", "撕裂", "疼痛", "肘", "肩", "膝"
]
_INJURY_KEYWORDS_EN = [
    "injury", "injured", "IL", "DL", "scratch", "out", "doubtful",
    "surgery", "fracture", "strain", "sprain", "tear", "elbow", "shoulder", "knee"
]
_POSITIVE_KEYWORDS_ZH = [
    "復出", "復健完成", "狀態良好", "佳", "熱身", "備戰", "信心", "打擊狀態佳"
]
_POSITIVE_KEYWORDS_EN = [
    "cleared", "activated", "ready", "strong", "confident", "sharp",
    "excellent", "good health", "no issues"
]
_NEGATIVE_KEYWORDS_ZH = [
    "疲勞", "連戰", "壓力", "狀態不佳", "低潮", "失誤", "負面", "危機", "問題"
]
_NEGATIVE_KEYWORDS_EN = [
    "tired", "fatigue", "slump", "poor", "struggling", "concern",
    "issues", "problems", "rust"
]
_WEATHER_SEVERE_KW = [
    "雨", "暴風", "強風", "打雷", "閃電", "低溫", "高溫",
    "rain", "storm", "wind", "thunder", "cold", "heat", "fog", "delay"
]
_ELIMINATION_KW_ZH = ["淘汰賽", "爭冠", "晉級", "主場優勢", "背水一戰", "決賽"]
_ELIMINATION_KW_EN = ["elimination", "championship", "playoff", "advance", "must-win", "final"]


# ══════════════════════════════════════════════════════════════════════════════
# 資料結構
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class PregameTextBundle:
    """
    賽前文字資料包。
    呼叫者負責確保所有文字均為開賽前狀態（無未來資訊）。
    """
    home_team: str
    away_team: str
    # 任何欄位均可為空字串（NLP 仍能優雅降級）
    home_lineup_news: str = ""      # 先發名單/陣容公告
    away_lineup_news: str = ""
    home_injury_report: str = ""    # 傷兵報告
    away_injury_report: str = ""
    home_starter_news: str = ""     # 先發投手相關新聞
    away_starter_news: str = ""
    weather_report: str = ""        # 天氣/場地資訊
    game_context: str = ""          # 賽事背景（輪次、積分、激勵因素）

    @property
    def home_full_text(self) -> str:
        parts = filter(None, [
            self.home_lineup_news,
            self.home_injury_report,
            self.home_starter_news,
        ])
        return " | ".join(parts)

    @property
    def away_full_text(self) -> str:
        parts = filter(None, [
            self.away_lineup_news,
            self.away_injury_report,
            self.away_starter_news,
        ])
        return " | ".join(parts)


# ══════════════════════════════════════════════════════════════════════════════
# 規則引擎（Fallback Layer 2）
# ══════════════════════════════════════════════════════════════════════════════

def _kw_count(text: str, keywords: list[str]) -> int:
    text_lower = text.lower()
    return sum(1 for kw in keywords if kw.lower() in text_lower)


def _extract_injury_severity(text: str) -> float:
    """
    從文字估算傷兵嚴重程度 (0.0 = 無傷兵, 1.0 = 主力缺陣)。
    """
    if not text:
        return 0.0

    zh_count = _kw_count(text, _INJURY_KEYWORDS_ZH)
    en_count = _kw_count(text, _INJURY_KEYWORDS_EN)
    total = zh_count + en_count

    # 檢測主力/王牌關鍵字（嚴重度加倍）
    is_key_player = bool(re.search(
        r"(主力|王牌|4號|3號|ace|star|starter|cleanup|anchor)", text, re.I
    ))

    base = min(1.0, total * 0.2)
    return min(1.0, base * (1.5 if is_key_player else 1.0))


def _extract_sentiment(text: str) -> float:
    """
    文字情感分數 (-1.0 = 極負面, 0 = 中性, +1.0 = 極正面)。
    """
    if not text:
        return 0.0

    pos = _kw_count(text, _POSITIVE_KEYWORDS_ZH) + _kw_count(text, _POSITIVE_KEYWORDS_EN)
    neg = _kw_count(text, _NEGATIVE_KEYWORDS_ZH) + _kw_count(text, _NEGATIVE_KEYWORDS_EN)

    total = pos + neg
    if total == 0:
        return 0.0
    return float(np.clip((pos - neg) / total, -1.0, 1.0))


def _extract_starter_confidence(text: str) -> float:
    """
    先發投手信心度 (0.3 = 高疑慮, 0.7 = 正常, 1.0 = 狀態絕佳)。
    """
    if not text:
        return 0.70

    injury = _extract_injury_severity(text)
    sentiment = _extract_sentiment(text)

    base = 0.70 - injury * 0.3 + sentiment * 0.15
    return float(np.clip(base, 0.20, 1.00))


def _extract_weather_impact(weather_text: str) -> float:
    """
    天氣影響程度 (0.0 = 無影響, 1.0 = 嚴重影響)。
    """
    if not weather_text:
        return 0.0
    count = _kw_count(weather_text, _WEATHER_SEVERE_KW)
    return float(np.clip(count * 0.25, 0.0, 1.0))


def _extract_motivation(game_context: str, team: str) -> float:
    """
    激勵因素 (-1.0 = 無激勵, +1.0 = 強激勵)。
    """
    if not game_context:
        return 0.0

    text = game_context.lower()
    elim_zh = _kw_count(text, _ELIMINATION_KW_ZH)
    elim_en = _kw_count(text, _ELIMINATION_KW_EN)
    home_mentioned = team.lower() in text

    base = min(1.0, (elim_zh + elim_en) * 0.3)
    return float(base * (1.2 if home_mentioned else 0.8))


def _rule_based_extract(bundle: PregameTextBundle) -> dict[str, float]:
    """關鍵詞規則引擎萃取特徵（無 LLM 依賴）。"""
    feats: dict[str, float] = {}

    feats["nlp_home_starter_confidence"] = _extract_starter_confidence(bundle.home_starter_news)
    feats["nlp_away_starter_confidence"] = _extract_starter_confidence(bundle.away_starter_news)
    feats["nlp_home_injury_severity"] = _extract_injury_severity(bundle.home_injury_report)
    feats["nlp_away_injury_severity"] = _extract_injury_severity(bundle.away_injury_report)
    feats["nlp_home_sentiment"] = _extract_sentiment(bundle.home_full_text)
    feats["nlp_away_sentiment"] = _extract_sentiment(bundle.away_full_text)
    feats["nlp_weather_impact"] = _extract_weather_impact(bundle.weather_report)

    # 陣容完整度差值
    h_lineup_words = len(bundle.home_lineup_news.split()) if bundle.home_lineup_news else 0
    a_lineup_words = len(bundle.away_lineup_news.split()) if bundle.away_lineup_news else 0
    feats["nlp_lineup_stability_diff"] = float(
        np.clip((h_lineup_words - a_lineup_words) / max(50.0, h_lineup_words + a_lineup_words), -1.0, 1.0)
    )

    # 激勵因素差值
    h_motiv = _extract_motivation(bundle.game_context, bundle.home_team)
    a_motiv = _extract_motivation(bundle.game_context, bundle.away_team)
    feats["nlp_motivation_diff"] = float(np.clip(h_motiv - a_motiv, -1.0, 1.0))
    feats["nlp_data_available"] = 0.0  # 規則 fallback

    # 綜合 NLP 優勢
    feats["nlp_composite_nlp_advantage"] = float(
        (feats["nlp_home_starter_confidence"] - feats["nlp_away_starter_confidence"]) * 1.5 +
        (feats["nlp_away_injury_severity"] - feats["nlp_home_injury_severity"]) * 2.0 +
        (feats["nlp_home_sentiment"] - feats["nlp_away_sentiment"]) * 1.0 +
        feats["nlp_motivation_diff"] * 0.5 -
        feats["nlp_weather_impact"] * 0.3  # 天氣影響雙方，對主隊略有優勢
    )

    return {k: round(float(v), 4) for k, v in feats.items()}


# ══════════════════════════════════════════════════════════════════════════════
# LLM Providers — ReACT 多 Provider 支援
# ══════════════════════════════════════════════════════════════════════════════

_REACT_PROMPT_TEMPLATE = """你是棒球賽事情報分析師。以下是賽前資訊，請以 JSON 格式輸出分析結果。

賽前資訊：
主隊：{home_team}
  先發投手新聞：{home_starter}
  傷兵報告：{home_injury}
  陣容公告：{home_lineup}

客隊：{away_team}
  先發投手新聞：{away_starter}
  傷兵報告：{away_injury}
  陣容公告：{away_lineup}

天氣/場地：{weather}
賽事背景：{context}

請輸出以下 JSON（數值範圍如括號所示）：
{{
  "home_starter_confidence": 0.70,
  "away_starter_confidence": 0.70,
  "home_injury_severity": 0.0,
  "away_injury_severity": 0.0,
  "home_sentiment": 0.0,
  "away_sentiment": 0.0,
  "weather_impact": 0.0,
  "home_lineup_stability": 0.8,
  "away_lineup_stability": 0.8,
  "home_motivation": 0.5,
  "away_motivation": 0.5
}}

只輸出 JSON，不要其他文字。"""


def _parse_llm_json(raw: str) -> Optional[dict]:
    """從 LLM 輸出中提取 JSON 物件（容錯解析）。"""
    if not raw:
        return None
    match = re.search(r'\{[^{}]+\}', raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


# ── Provider 1: Groq（免費，推薦）────────────────────────────────────────────

def _call_groq(prompt: str, model: str = "llama-3.1-8b-instant") -> Optional[str]:
    """呼叫 Groq API（OpenAI 相容格式）。免費額度充足，速度最快。"""
    if not _REQUESTS_AVAILABLE or not _GROQ_API_KEY:
        return None
    try:
        resp = _requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {_GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 400,
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.debug("Groq 呼叫失敗: %s", e)
        return None


# ── Provider 2: Google Gemini Flash（免費 tier）──────────────────────────────

def _call_gemini(prompt: str, model: str = "gemini-1.5-flash") -> Optional[str]:
    """呼叫 Google Gemini API。免費 tier：15 RPM, 1M TPM。"""
    if not _REQUESTS_AVAILABLE or not _GEMINI_API_KEY:
        return None
    try:
        resp = _requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": _GEMINI_API_KEY},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 400},
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        candidates = resp.json().get("candidates", [])
        if candidates:
            return candidates[0]["content"]["parts"][0]["text"]
        return None
    except Exception as e:
        logger.debug("Gemini 呼叫失敗: %s", e)
        return None


# ── Provider 3: Anthropic Claude Haiku（最精準）──────────────────────────────

def _call_anthropic(prompt: str, model: str = "claude-haiku-4-5-20251001") -> Optional[str]:
    """呼叫 Anthropic Claude API。claude-haiku = $0.25/1M input tokens。"""
    if not _REQUESTS_AVAILABLE or not _ANTHROPIC_API_KEY:
        return None
    try:
        resp = _requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": _ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 400,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]
    except Exception as e:
        logger.debug("Anthropic 呼叫失敗: %s", e)
        return None


# ── Provider 4: OpenRouter（部分模型免費）────────────────────────────────────

def _call_openrouter(
    prompt: str,
    model: str = "meta-llama/llama-3.1-8b-instruct:free",
) -> Optional[str]:
    """呼叫 OpenRouter API。:free 後綴模型完全免費。"""
    if not _REQUESTS_AVAILABLE or not _OPENROUTER_API_KEY:
        return None
    try:
        resp = _requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {_OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/betting-pool",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 400,
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.debug("OpenRouter 呼叫失敗: %s", e)
        return None


# ── Provider 5: Ollama（本地端）──────────────────────────────────────────────

def _call_ollama(prompt: str, model: str = _OLLAMA_MODEL) -> Optional[str]:
    """呼叫本地 Ollama API。需自行安裝並下載模型。"""
    if not _REQUESTS_AVAILABLE:
        return None
    try:
        resp = _requests.post(
            f"{_OLLAMA_BASE_URL}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.1, "num_predict": 400}},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")
    except Exception as e:
        logger.debug("Ollama 呼叫失敗: %s", e)
        return None


# ── 統一呼叫路由器 ────────────────────────────────────────────────────────────

_PROVIDER_DISPATCH: dict[str, callable] = {
    "groq":       _call_groq,
    "gemini":     _call_gemini,
    "anthropic":  _call_anthropic,
    "openrouter": _call_openrouter,
    "ollama":     _call_ollama,
}


def _call_llm(prompt: str, provider: str = _NLP_PROVIDER) -> Optional[str]:
    """
    統一 LLM 呼叫入口。
    先嘗試指定 provider，失敗後依序 fallback 至其他 provider。
    """
    try:
        from orchestrator import execution_policy

        execution_policy.assert_llm_execution_allowed(
            runner="nlp_extractor",
            provider=provider or "multi-provider",
            context="wbc_nlp_extractor",
            background=True,
            manual_override=execution_policy.is_manual_run(os.environ),
        )
    except Exception as exc:
        logger.debug("NLP: unable to read runtime guard, skip provider call (%s)", exc)
        return None

    # 指定 provider 優先
    fn = _PROVIDER_DISPATCH.get(provider)
    if fn:
        result = fn(prompt)
        if result:
            return result

    # Fallback 鏈（排除已試過的）
    fallback_order = ["groq", "gemini", "anthropic", "openrouter", "ollama"]
    for fb_provider in fallback_order:
        if fb_provider == provider:
            continue
        fb_fn = _PROVIDER_DISPATCH.get(fb_provider)
        if fb_fn:
            result = fb_fn(prompt)
            if result:
                logger.debug("NLP: fallback 到 %s 成功", fb_provider)
                return result

    return None


def _llm_extract(bundle: PregameTextBundle, provider: str = _NLP_PROVIDER) -> Optional[dict[str, float]]:
    """
    ReACT 推理循環萃取特徵（多 Provider）。
    失敗時返回 None，由上層切換到規則引擎。
    """
    prompt = _REACT_PROMPT_TEMPLATE.format(
        home_team=bundle.home_team,
        home_starter=bundle.home_starter_news or "無資訊",
        home_injury=bundle.home_injury_report or "無傷兵報告",
        home_lineup=bundle.home_lineup_news or "尚未公布",
        away_team=bundle.away_team,
        away_starter=bundle.away_starter_news or "無資訊",
        away_injury=bundle.away_injury_report or "無傷兵報告",
        away_lineup=bundle.away_lineup_news or "尚未公布",
        weather=bundle.weather_report or "場館內（無影響）",
        context=bundle.game_context or "常規賽事",
    )

    raw = _call_llm(prompt, provider)
    parsed = _parse_llm_json(raw) if raw else None

    if not parsed:
        return None

    def _safe(key: str, lo: float, hi: float, default: float) -> float:
        return float(np.clip(parsed.get(key, default), lo, hi))

    return {
        "nlp_home_starter_confidence": _safe("home_starter_confidence", 0.2, 1.0, 0.70),
        "nlp_away_starter_confidence": _safe("away_starter_confidence", 0.2, 1.0, 0.70),
        "nlp_home_injury_severity":    _safe("home_injury_severity",    0.0, 1.0, 0.00),
        "nlp_away_injury_severity":    _safe("away_injury_severity",    0.0, 1.0, 0.00),
        "nlp_home_sentiment":          _safe("home_sentiment",          -1.0, 1.0, 0.00),
        "nlp_away_sentiment":          _safe("away_sentiment",          -1.0, 1.0, 0.00),
        "nlp_weather_impact":          _safe("weather_impact",          0.0, 1.0, 0.00),
        "nlp_lineup_stability_diff":   float(np.clip(
            _safe("home_lineup_stability", 0.0, 1.0, 0.8) -
            _safe("away_lineup_stability", 0.0, 1.0, 0.8), -1.0, 1.0
        )),
        "nlp_motivation_diff": float(np.clip(
            _safe("home_motivation", 0.0, 1.0, 0.5) -
            _safe("away_motivation", 0.0, 1.0, 0.5), -1.0, 1.0
        )),
        "nlp_data_available": 1.0,  # LLM 成功萃取
    }


# ══════════════════════════════════════════════════════════════════════════════
# Category L：公開入口（整合進 alpha_signals.py）
# ══════════════════════════════════════════════════════════════════════════════

def compute_nlp_signals(
    bundle: PregameTextBundle,
    use_llm: bool = True,
    llm_model: str = _OLLAMA_MODEL,   # 向後相容，優先使用 provider
    provider: str = _NLP_PROVIDER,
) -> dict[str, float]:
    """
    Category L — NLP 賽前特徵 (11 個信號)

    Args:
        bundle:    PregameTextBundle（開賽前文字資料）
        use_llm:   True=優先嘗試 LLM；False=直接使用規則引擎
        provider:  LLM Provider: "groq"|"gemini"|"anthropic"|"openrouter"|"ollama"|"rule"
                   預設從環境變數 NLP_LLM_PROVIDER 讀取（未設定則為 "groq"）

    Returns:
        dict[str, float] — 可直接合併至 AlphaSignals.feature_dict

    延遲目標：< 30 秒（Groq 約 1-3 秒，Gemini 約 3-8 秒）
    """
    t0 = time.time()
    feats: Optional[dict[str, float]] = None

    # Layer 1：嘗試 LLM（多 Provider 支援）
    if use_llm and provider != "rule":
        try:
            feats = _llm_extract(bundle, provider=provider)
        except Exception as e:
            logger.warning("LLM 萃取發生例外: %s", e)
            feats = None

    # Layer 2：規則引擎 fallback
    if feats is None:
        feats = _rule_based_extract(bundle)
        logger.debug("NLP: 使用規則引擎 (%.1fs)", time.time() - t0)
    else:
        logger.debug("NLP: LLM 萃取成功 (%.1fs)", time.time() - t0)

    # 確保 nlp_composite_nlp_advantage 存在
    if "nlp_composite_nlp_advantage" not in feats:
        feats["nlp_composite_nlp_advantage"] = float(
            (feats.get("nlp_home_starter_confidence", 0.7) -
             feats.get("nlp_away_starter_confidence", 0.7)) * 1.5 +
            (feats.get("nlp_away_injury_severity", 0.0) -
             feats.get("nlp_home_injury_severity", 0.0)) * 2.0 +
            (feats.get("nlp_home_sentiment", 0.0) -
             feats.get("nlp_away_sentiment", 0.0)) * 1.0 +
            feats.get("nlp_motivation_diff", 0.0) * 0.5 -
            feats.get("nlp_weather_impact", 0.0) * 0.3
        )

    # 驗證所有欄位
    for key in _NEUTRAL_FEATURES:
        if key not in feats:
            feats[key] = _NEUTRAL_FEATURES[key]

    return {k: round(float(v), 4) for k, v in feats.items()}


def build_empty_nlp_features() -> dict[str, float]:
    """返回中性 NLP 特徵（無賽前文字時使用）。"""
    return dict(_NEUTRAL_FEATURES)
