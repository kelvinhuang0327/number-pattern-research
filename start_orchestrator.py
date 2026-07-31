#!/usr/bin/env python3
"""
Betting-pool Orchestrator 啟動腳本
一鍵啟動完整的編排系統
"""

import os
import sys
import time
import subprocess
import signal
import logging
from pathlib import Path

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OrchestratorLauncher:
    """編排系統啟動器"""
    
    def __init__(self):
        self.processes = []
        self.running = False
    
    def signal_handler(self, signum, frame):
        """處理信號"""
        logger.info("接收到終止信號，正在關閉系統...")
        self.stop()
        sys.exit(0)
    
    def check_dependencies(self):
        """檢查依賴"""
        logger.info("🔍 檢查系統依賴...")
        
        # 檢查 Python 版本
        if sys.version_info < (3, 8):
            raise RuntimeError("需要 Python 3.8 或更高版本")
        
        # 檢查必要的模組
        try:
            import fastapi
            import uvicorn
            import sqlite3
            logger.info("✅ 所有依賴已滿足")
        except ImportError as e:
            raise RuntimeError(f"缺少依賴模組: {e}")
    
    def initialize_database(self):
        """初始化資料庫"""
        logger.info("🗄️ 初始化資料庫...")
        
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from orchestrator import db
        
        db.init_db()
        logger.info("✅ 資料庫初始化完成")
    
    def start_api_server(self):
        """啟動 API 服務器"""
        logger.info("🚀 啟動 API 服務器...")
        
        # 確保在正確的目錄
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        
        # 啟動 FastAPI 服務器
        cmd = [
            sys.executable, "-m", "uvicorn",
            "app:app",
            "--host", "127.0.0.1",
            "--port", "8787",
            "--reload"
        ]
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        self.processes.append(process)
        logger.info("✅ API 服務器已啟動 (PID: {})".format(process.pid))
        
        return process
    
    def wait_for_api_ready(self, timeout=30):
        """等待 API 服務器準備就緒"""
        logger.info("⏳ 等待 API 服務器就緒...")
        
        import requests
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get("http://127.0.0.1:8787/health", timeout=5)
                if response.status_code == 200:
                    logger.info("✅ API 服務器已就緒")
                    return True
            except:
                pass
            
            time.sleep(2)
        
        raise TimeoutError("API 服務器啟動超時")
    
    def run_initial_test(self):
        """執行初始測試"""
        logger.info("🧪 執行初始功能測試...")
        
        import requests
        
        try:
            # 測試基本 API
            response = requests.get("http://127.0.0.1:8787/api/summary", timeout=10)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"✅ 系統狀態: {data['project']['name']}")
            logger.info(f"   調度器: {'啟用' if data['scheduler']['enabled'] else '停用'}")
            logger.info(f"   任務統計: {data['counts']}")
            
        except Exception as e:
            logger.warning(f"初始測試失敗: {e}")
    
    def start(self):
        """啟動完整系統"""
        logger.info("🎯 啟動 Betting-pool Orchestrator 系統")
        logger.info("="*50)
        
        try:
            # 1. 檢查依賴
            self.check_dependencies()
            
            # 2. 初始化資料庫
            self.initialize_database()
            
            # 3. 啟動 API 服務器
            api_process = self.start_api_server()
            
            # 4. 等待服務器就緒
            self.wait_for_api_ready()
            
            # 5. 執行初始測試
            self.run_initial_test()
            
            # 6. 系統就緒
            self.running = True
            logger.info("="*50)
            logger.info("🎉 系統啟動完成！")
            logger.info("")
            logger.info("📍 可用服務:")
            logger.info("   • API 服務器: http://127.0.0.1:8787")
            logger.info("   • API 文檔: http://127.0.0.1:8787/docs")
            logger.info("   • 健康檢查: http://127.0.0.1:8787/health")
            logger.info("   • 系統資訊: http://127.0.0.1:8787/api/system/info")
            logger.info("")
            logger.info("🎮 可用操作:")
            logger.info("   • 手動觸發 Planner: POST /api/planner/run-now")
            logger.info("   • 手動觸發 Worker: POST /api/worker/run-now")
            logger.info("   • 手動觸發 CTO: POST /api/cto/run-now")
            logger.info("")
            logger.info("📊 監控 UI: http://127.0.0.1:8789 (需啟動 proxy_server.py)")
            logger.info("")
            logger.info("按 Ctrl+C 停止系統")
            
            # 註冊信號處理
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
            
            # 保持運行並監控進程
            self.monitor_processes()
            
        except Exception as e:
            logger.error(f"❌ 系統啟動失敗: {e}")
            self.stop()
            sys.exit(1)
    
    def monitor_processes(self):
        """監控進程"""
        while self.running:
            for process in self.processes[:]:  # 複製列表避免修改問題
                if process.poll() is not None:
                    logger.warning(f"進程 {process.pid} 已退出")
                    self.processes.remove(process)
            
            if not self.processes:
                logger.error("所有進程已退出，停止系統")
                break
            
            time.sleep(5)
    
    def stop(self):
        """停止系統"""
        if not self.running:
            return
        
        self.running = False
        logger.info("🛑 正在停止系統...")
        
        for process in self.processes:
            try:
                logger.info(f"正在終止進程 {process.pid}")
                process.terminate()
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning(f"強制殺死進程 {process.pid}")
                process.kill()
            except Exception as e:
                logger.error(f"停止進程時發生錯誤: {e}")
        
        self.processes.clear()
        logger.info("✅ 系統已停止")


def main():
    """主函數"""
    launcher = OrchestratorLauncher()
    launcher.start()


if __name__ == "__main__":
    main()
