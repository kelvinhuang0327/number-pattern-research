// 調度器狀態強制刷新腳本
// 在瀏覽器控制台中執行此腳本來手動刷新調度器狀態

const TRUSTED_UI_ORIGINS = new Set([
    'http://127.0.0.1:8789',
    'http://localhost:8789',
    'http://127.0.0.1:8787',
    'http://localhost:8787'
]);
const LEGACY_BLOCKED_PORTS = new Set(['743']);
const DEFAULT_PROXY_BASE = 'http://127.0.0.1:8789';
const BROWSER_LOCATION = globalThis.location;

function resolveSchedulerApiBase() {
    const currentOrigin = BROWSER_LOCATION.origin;
    const currentPort = BROWSER_LOCATION.port || (BROWSER_LOCATION.protocol === 'https:' ? '443' : '80');

    if (LEGACY_BLOCKED_PORTS.has(currentPort)) {
        console.warn(`Detected stale UI origin ${currentOrigin}; forcing scheduler API traffic to ${DEFAULT_PROXY_BASE}`);
        return DEFAULT_PROXY_BASE;
    }

    return TRUSTED_UI_ORIGINS.has(currentOrigin) ? currentOrigin : DEFAULT_PROXY_BASE;
}

async function forceRefreshScheduler() {
    const API_BASE = resolveSchedulerApiBase();

    try {
        // 獲取調度器狀態
        const response = await fetch(`${API_BASE}/api/scheduler`);
        const data = await response.json();

        // 更新顯示
        document.getElementById('orc-scheduler-state').textContent = data.enabled ? '啟用' : '暫停';
        const toggleBtn = document.getElementById('orc-scheduler-toggle-btn');
        toggleBtn.textContent = data.enabled ? '暫停' : '啟用';
        toggleBtn.dataset.enabled = data.enabled ? '1' : '0';

        console.log('✅ 調度器狀態已刷新:', data.enabled ? '啟用' : '暫停');

        // 測試切換功能
        toggleBtn.onclick = async () => {
            const enabled = toggleBtn.dataset.enabled === '1';
            const toggleResponse = await fetch(`${API_BASE}/api/scheduler/enable`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: !enabled })
            });

            if (toggleResponse.ok) {
                const result = await toggleResponse.json();
                document.getElementById('orc-scheduler-state').textContent = result.enabled ? '啟用' : '暫停';
                toggleBtn.textContent = result.enabled ? '暫停' : '啟用';
                toggleBtn.dataset.enabled = result.enabled ? '1' : '0';
                console.log('✅ 調度器已切換為:', result.enabled ? '啟用' : '暫停');
            }
        };

        return true;
    } catch (error) {
        console.error('❌ 調度器刷新失敗:', error);
        return false;
    }
}

console.log('Scheduler refresh helper loaded. Run forceRefreshScheduler() to execute.');