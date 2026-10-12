/**
 * 自動學習頁面測試腳本
 * 在瀏覽器控制台中運行此腳本來測試自動學習功能
 */

console.log('🧪 開始自動學習頁面測試...\n');

// 測試 1: 檢查 DOM 元素
console.log('📋 測試 1: 檢查 DOM 元素');
const section = document.getElementById('autolearning-section');
const buttons = {
    refresh: document.getElementById('refresh-status-btn'),
    optimize: document.getElementById('run-optimization-btn'),
    startSchedule: document.getElementById('start-schedule-btn'),
    updateSchedule: document.getElementById('update-schedule-btn'),
    stopSchedule: document.getElementById('stop-schedule-btn'),
    loadConfig: document.getElementById('load-config-btn')
};

console.log('  ✓ Section 存在:', !!section);
console.log('  ✓ 刷新狀態按鈕:', !!buttons.refresh);
console.log('  ✓ 開始優化按鈕:', !!buttons.optimize);
console.log('  ✓ 啟動排程按鈕:', !!buttons.startSchedule);
console.log('  ✓ 更新排程按鈕:', !!buttons.updateSchedule);
console.log('  ✓ 停止排程按鈕:', !!buttons.stopSchedule);
console.log('  ✓ 載入配置按鈕:', !!buttons.loadConfig);

// 測試 2: 檢查 AutoLearningManager
console.log('\n📋 測試 2: 檢查 AutoLearningManager');
const app = window.app;
if (app && app.autoLearningManager) {
    console.log('  ✓ AutoLearningManager 已初始化');
    console.log('  ✓ 事件已綁定:', app.autoLearningManager.eventsBound);
    console.log('  ✓ 重試次數:', app.autoLearningManager.retryCount);
    console.log('  ✓ API 端點:', app.autoLearningManager.apiEndpoint);
} else {
    console.error('  ✗ AutoLearningManager 未初始化');
}

// 測試 3: 檢查事件監聽器
console.log('\n📋 測試 3: 檢查事件監聽器');
if (section) {
    const listeners = getEventListeners(section);
    if (listeners && listeners.click) {
        console.log('  ✓ Click 事件監聽器數量:', listeners.click.length);
    } else {
        console.warn('  ⚠ 無法檢查事件監聽器（需要在 Chrome DevTools 中運行）');
    }
}

// 測試 4: 模擬按鈕點擊
console.log('\n📋 測試 4: 模擬按鈕點擊');
if (buttons.refresh) {
    console.log('  → 模擬點擊「刷新狀態」按鈕...');
    try {
        buttons.refresh.click();
        console.log('  ✓ 點擊成功（檢查網絡請求）');
    } catch (error) {
        console.error('  ✗ 點擊失敗:', error.message);
    }
} else {
    console.error('  ✗ 按鈕不存在');
}

// 測試 5: 檢查 Chart.js
console.log('\n📋 測試 5: 檢查依賴庫');
console.log('  ✓ Chart.js 已載入:', typeof Chart !== 'undefined');

// 測試 6: 檢查 API 連接
console.log('\n📋 測試 6: 檢查 API 連接');
if (app && app.autoLearningManager) {
    const apiUrl = app.autoLearningManager.apiEndpoint + '/schedule/status';
    console.log('  → 測試 API 端點:', apiUrl);

    fetch(apiUrl)
        .then(response => {
            if (response.ok) {
                console.log('  ✓ API 連接成功');
                return response.json();
            } else {
                console.warn('  ⚠ API 返回錯誤:', response.status);
            }
        })
        .then(data => {
            if (data) {
                console.log('  ✓ API 數據:', data);
            }
        })
        .catch(error => {
            console.error('  ✗ API 連接失敗:', error.message);
            console.log('  ℹ️ 這是正常的，如果後端 API 未運行');
        });
}

console.log('\n✅ 測試完成！請檢查上述結果。');
console.log('💡 提示：如果所有 DOM 元素都存在但按鈕無響應，請檢查：');
console.log('   1. 瀏覽器控制台是否有錯誤訊息');
console.log('   2. 後端 API 是否正在運行');
console.log('   3. 網絡請求是否成功（Network 標籤）');
