"""
Betting-pool Orchestrator Common Utilities
Betting-pool Orchestrator 共用工具函數（UTC dedupe、型別轉換、安全讀取）
"""

import os
import json
import uuid
import hashlib
import re
import shutil
from datetime import datetime, timezone
from typing import Optional, Dict, Any


SAFE_RUN_MODE = "safe-run"
HARD_OFF_MODE = "hard-off"


def generate_request_id() -> str:
    """產生請求 ID"""
    return str(uuid.uuid4())


def generate_run_id(prefix: str = "run") -> str:
    """產生執行 ID"""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    return f"{prefix}-{timestamp}-{unique_id}"


def normalize_date_folder(date_input: Optional[str] = None) -> str:
    """標準化日期資料夾格式"""
    if date_input:
        # 移除連字符，只保留數字
        return date_input.replace("-", "").replace("/", "")[:8]
    else:
        return datetime.now(timezone.utc).strftime("%Y%m%d")


def dedupe_day_utc() -> str:
    """Returns current UTC date as YYYYMMDD for dedupe_key construction.
    Use this — NOT local time — for all task dedupe keys to avoid timezone confusion.
    """
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def calculate_dedupe_key(content: str, context: Optional[Dict[str, Any]] = None) -> str:
    """計算去重鍵值"""
    # 組合內容和上下文
    combined = content
    if context:
        context_str = json.dumps(context, sort_keys=True)
        combined = f"{content}|{context_str}"
    
    # 計算 SHA-256 hash
    hash_obj = hashlib.sha256(combined.encode('utf-8'))
    return f"hash:{hash_obj.hexdigest()[:16]}"


def format_duration(seconds: Optional[int]) -> str:
    """格式化執行時間"""
    if not seconds:
        return "—"
    
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds}s"
    else:
        hours = seconds // 3600
        remaining_minutes = (seconds % 3600) // 60
        return f"{hours}h {remaining_minutes}m"


def safe_read_file(file_path: str, max_lines: int = 1000) -> Optional[str]:
    """安全讀取檔案內容"""
    if not file_path or not os.path.exists(file_path):
        return None
    
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    lines.append(f"... (truncated after {max_lines} lines)")
                    break
                lines.append(line.rstrip())
            return "\n".join(lines)
    except Exception:
        return None


def safe_read_json(file_path: str) -> Optional[Dict[str, Any]]:
    """安全讀取 JSON 檔案"""
    content = safe_read_file(file_path)
    if not content:
        return None
    
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None


def ensure_directory(file_path: str):
    """確保目錄存在"""
    directory = os.path.dirname(file_path)
    if directory:
        os.makedirs(directory, exist_ok=True)


def get_file_size_mb(file_path: str) -> float:
    """取得檔案大小（MB）"""
    if not os.path.exists(file_path):
        return 0.0
    
    try:
        size_bytes = os.path.getsize(file_path)
        return size_bytes / (1024 * 1024)
    except Exception:
        return 0.0


def truncate_text(text: str, max_length: int = 500) -> str:
    """截斷文字"""
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - 3] + "..."


def validate_task_status(status: str) -> bool:
    """驗證任務狀態"""
    valid_statuses = {"QUEUED", "RUNNING", "COMPLETED", "FAILED", "REPLAN_REQUIRED", "CANCELLED"}
    return status in valid_statuses


def validate_severity_level(severity: str) -> bool:
    """驗證嚴重程度"""
    valid_levels = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
    return severity in valid_levels


def validate_urgency_level(urgency: str) -> bool:
    """驗證緊急程度"""
    valid_levels = {"IMMEDIATE", "HIGH", "MEDIUM", "LOW"}
    return urgency in valid_levels


def parse_iso_datetime(datetime_str: Optional[str]) -> Optional[datetime]:
    """解析 ISO 格式日期時間"""
    if not datetime_str:
        return None
    
    try:
        dt = datetime.fromisoformat(str(datetime_str))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def format_iso_datetime(dt: Optional[datetime]) -> Optional[str]:
    """格式化為 ISO 日期時間"""
    if not dt:
        return None
    
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    return dt.isoformat()


def get_current_timestamp() -> str:
    """取得當前時間戳"""
    return datetime.now(timezone.utc).isoformat()


def create_error_response(error_code: str, message: str, details: Optional[Dict] = None) -> Dict[str, Any]:
    """建立錯誤回應"""
    response = {
        "error": True,
        "error_code": error_code,
        "message": message,
        "timestamp": get_current_timestamp()
    }
    
    if details:
        response["details"] = details
    
    return response


def create_success_response(data: Any = None, message: Optional[str] = None) -> Dict[str, Any]:
    """建立成功回應"""
    response = {
        "error": False,
        "timestamp": get_current_timestamp()
    }
    
    if message:
        response["message"] = message
    
    if data is not None:
        response["data"] = data
    
    return response


def sanitize_filename(filename: str) -> str:
    """清理檔案名稱"""
    # 移除或替換不安全字符
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, "-")
    
    # 限制長度
    if len(filename) > 200:
        filename = filename[:200]
    
    return filename.strip()


def extract_changed_files_from_git() -> list[str]:
    """從 Git 提取變更檔案（模擬）"""
    # 這是一個模擬函數，實際應用中會執行 git 命令
    sample_files = [
        "models/wbc_predictor.py",
        "data/feature_engineering.py",
        "tests/test_predictions.py",
        "README.md"
    ]
    
    import random
    return random.sample(sample_files, k=random.randint(1, len(sample_files)))


class TaskFileManager:
    """任務檔案管理器"""
    
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
    
    def create_task_directory(self, date_folder: str) -> str:
        """建立任務目錄"""
        task_dir = os.path.join(self.base_dir, "tasks", date_folder)
        os.makedirs(task_dir, exist_ok=True)
        return task_dir
    
    def get_task_file_path(self, date_folder: str, slot_key: str, file_type: str) -> str:
        """取得任務檔案路徑"""
        task_dir = self.create_task_directory(date_folder)
        return os.path.join(task_dir, f"{slot_key}-{file_type}")
    
    def write_task_file(self, file_path: str, content: str):
        """寫入任務檔案"""
        ensure_directory(file_path)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
    
    def read_task_file(self, file_path: str) -> Optional[str]:
        """讀取任務檔案"""
        return safe_read_file(file_path)


# 常數定義
DEFAULT_TASK_TIMEOUT = 3600  # 1小時
DEFAULT_CTO_REVIEW_INTERVAL = 86400  # 24小時
DEFAULT_PLANNER_INTERVAL = 600  # 10分鐘
DEFAULT_WORKER_INTERVAL = 600  # 10分鐘

ORCH_RUNTIME_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "runtime",
    "agent_orchestrator",
)
COPILOT_DAEMON_STATE_PATH = os.path.join(
    ORCH_RUNTIME_ROOT,
    "locks",
    "copilot_daemon_state.json",
)
COPILOT_DAEMON_HEARTBEAT_TTL = 45
PLANNER_PROVIDER_LABELS = {
    "local": "本地確定性（Local）",   # Phase 0: 預設選項，不呼叫外部 LLM
    "claude": "Claude CLI",
    "codex": "Codex CLI",
}
WORKER_PROVIDER_LABELS = {
    "codex": "Codex CLI",
    "copilot": "GitHub Copilot CLI",
    "copilot-daemon": "GitHub Copilot Daemon",
    "claude": "Claude CLI",
}
COPILOT_MODEL_PRESETS = [
    {"value": "", "label": "預設"},
    {"value": "auto", "label": "auto（建議）"},
    {"value": "gpt-5-mini", "label": "gpt-5-mini"},
]

PROVIDER_TYPES = {
    "claude", "codex", "copilot", "copilot-daemon", "openai"
}

TASK_PRIORITIES = {
    "CRITICAL": 100,
    "HIGH": 80,
    "MEDIUM": 50,
    "LOW": 20
}

BACKLOG_CATEGORIES = {
    "architecture", "validation", "security", "performance", 
    "quality", "tech_debt", "uiux", "knowledge", "other"
}


def _is_process_alive(pid: Optional[int]) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError, TypeError):
        return False
    return True


def copilot_daemon_status() -> dict:
    state = {
        "available": shutil.which("gh") is not None,
        "running": False,
        "pid": None,
        "reason": "Ready; start resident LaunchAgent to run Copilot in user session",
    }
    if not state["available"]:
        state["reason"] = "GitHub CLI 未安裝或不在 PATH"
        return state

    payload = safe_read_json(COPILOT_DAEMON_STATE_PATH)
    if not payload:
        return state

    heartbeat_at = parse_iso_datetime(payload.get("heartbeat_at"))
    now = datetime.now(timezone.utc)
    is_fresh = bool(
        heartbeat_at and (now - heartbeat_at).total_seconds() <= COPILOT_DAEMON_HEARTBEAT_TTL
    )
    pid = payload.get("pid")
    if _is_process_alive(pid) and is_fresh:
        state["running"] = True
        state["pid"] = int(pid)
        state["reason"] = f"Daemon running (PID {pid})"
    return state


def validate_copilot_model(model: Optional[str]) -> bool:
    if model in (None, ""):
        return True
    return re.fullmatch(r"[A-Za-z0-9._:-]+", str(model)) is not None


def provider_available(provider: str) -> tuple[bool, str]:
    if provider == "claude":
        available = shutil.which("claude") is not None
        return available, "Ready" if available else "Claude CLI 不在 PATH"
    if provider == "codex":
        available = shutil.which("codex") is not None
        return available, "Ready" if available else "Codex CLI 不在 PATH"
    if provider == "copilot":
        available = shutil.which("gh") is not None
        return available, "Ready" if available else "GitHub CLI 不在 PATH"
    if provider == "copilot-daemon":
        status = copilot_daemon_status()
        return status["available"], status["reason"]
    return False, "Unsupported provider"


def planner_provider_options() -> list[dict]:
    options = []
    for value, label in PLANNER_PROVIDER_LABELS.items():
        available, reason = provider_available(value)
        options.append({
            "value": value,
            "label": label,
            "available": available,
            "reason": reason,
        })
    return options


def worker_provider_options() -> list[dict]:
    options = []
    for value, label in WORKER_PROVIDER_LABELS.items():
        available, reason = provider_available(value)
        options.append({
            "value": value,
            "label": label,
            "available": available,
            "reason": reason,
        })
    return options


def planner_provider_label(provider: Optional[str]) -> str:
    return PLANNER_PROVIDER_LABELS.get(str(provider or ""), str(provider or "N/A"))


def worker_provider_label(provider: Optional[str]) -> str:
    return WORKER_PROVIDER_LABELS.get(str(provider or ""), str(provider or "N/A"))


def provider_combo_label(planner_provider: Optional[str], worker_provider: Optional[str]) -> str:
    return f"{planner_provider_label(planner_provider)} Planner + {worker_provider_label(worker_provider)} Worker"


def build_runtime_guard_message(reason: str, runner: str) -> str:
    normalized_runner = str(runner or "runtime").strip() or "runtime"
    if reason == HARD_OFF_MODE:
        return f"GLOBAL_HARD_OFF — skip execution ({normalized_runner})"
    if reason == "scheduler-disabled":
        return f"GLOBAL_SCHEDULER_DISABLED — skip execution ({normalized_runner})"
    return f"GLOBAL_RUNTIME_BLOCKED[{reason}] — skip execution ({normalized_runner})"
