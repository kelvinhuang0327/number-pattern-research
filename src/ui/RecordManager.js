/**
 * RecordManager - 負責歷史記錄的增刪改查功能
 */
export class RecordManager {
    constructor(app) {
        this.app = app;
        this.modal = null;
        this.modalTitle = null;
        this.recordForm = null;
        this.currentEditId = null;
        this.init();
    }

    init() {
        // 綁定 DOM 元素
        this.modal = document.getElementById('record-modal');
        this.modalTitle = document.getElementById('modal-title');
        this.recordForm = document.getElementById('record-form');

        // 綁定事件
        this.bindEvents();

        // 將方法綁定到 window 以供 HTML onclick 調用
        window.editRecord = this.openEditModal.bind(this);
        window.deleteRecord = this.confirmDelete.bind(this);
    }

    bindEvents() {
        // 新增記錄按鈕
        const addBtn = document.getElementById('add-record-btn');
        if (addBtn) {
            addBtn.addEventListener('click', () => this.openAddModal());
        }

        // 關閉按鈕
        const closeBtn = document.getElementById('modal-close-btn');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.closeModal());
        }

        // 取消按鈕
        const cancelBtn = document.getElementById('modal-cancel-btn');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.closeModal());
        }

        // 儲存按鈕
        const saveBtn = document.getElementById('modal-save-btn');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.saveRecord());
        }

        // 點擊背景關閉
        if (this.modal) {
            this.modal.addEventListener('click', (e) => {
                if (e.target === this.modal) {
                    this.closeModal();
                }
            });
        }

        // ESC 鍵關閉
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal.style.display === 'block') {
                this.closeModal();
            }
        });
    }

    /**
     * 打開新增記錄彈窗
     */
    openAddModal() {
        this.currentEditId = null;
        this.modalTitle.textContent = '新增記錄';

        // 清空表單
        this.recordForm.reset();
        document.getElementById('record-id').value = '';

        // 設定預設日期為今天
        const today = new Date().toISOString().split('T')[0];
        document.getElementById('record-date').value = today;

        // 設定預設彩券類型為大樂透
        document.getElementById('record-lottery-type').value = 'BIG_LOTTO';

        // 顯示彈窗
        this.modal.style.display = 'block';
    }

    /**
     * 打開編輯記錄彈窗
     */
    openEditModal(drawId, drawData) {
        this.currentEditId = drawId;
        this.modalTitle.textContent = '編輯記錄';

        // 填充表單數據
        document.getElementById('record-id').value = drawData.id || '';
        document.getElementById('record-draw').value = drawData.draw || '';
        document.getElementById('record-date').value = drawData.date || '';
        document.getElementById('record-lottery-type').value = drawData.lotteryType || 'BIG_LOTTO';

        // 填充號碼
        if (drawData.numbers && Array.isArray(drawData.numbers)) {
            for (let i = 0; i < 6; i++) {
                const input = document.getElementById(`record-num-${i + 1}`);
                if (input) {
                    input.value = drawData.numbers[i] || '';
                }
            }
        }

        // 填充特別號
        document.getElementById('record-special').value = drawData.special || '';

        // 顯示彈窗
        this.modal.style.display = 'block';
    }

    /**
     * 關閉彈窗
     */
    closeModal() {
        this.modal.style.display = 'none';
        this.recordForm.reset();
        this.currentEditId = null;
    }

    /**
     * 儲存記錄（新增或編輯）
     */
    async saveRecord() {
        // 驗證表單
        if (!this.recordForm.checkValidity()) {
            this.recordForm.reportValidity();
            return;
        }

        // 收集表單數據
        const recordData = {
            draw: document.getElementById('record-draw').value.trim(),
            date: document.getElementById('record-date').value,
            lotteryType: document.getElementById('record-lottery-type').value,
            numbers: [],
            special: parseInt(document.getElementById('record-special').value)
        };

        // 收集號碼
        for (let i = 1; i <= 6; i++) {
            const num = parseInt(document.getElementById(`record-num-${i}`).value);
            if (isNaN(num) || num < 1 || num > 49) {
                alert(`號碼 ${i} 必須在 1-49 之間`);
                return;
            }
            recordData.numbers.push(num);
        }

        // 驗證特別號
        if (isNaN(recordData.special) || recordData.special < 1 || recordData.special > 49) {
            alert('特別號必須在 1-49 之間');
            return;
        }

        // 檢查號碼是否重複
        const allNumbers = [...recordData.numbers, recordData.special];
        const uniqueNumbers = new Set(allNumbers);
        if (uniqueNumbers.size !== allNumbers.length) {
            alert('號碼不能重複（包含特別號）');
            return;
        }

        try {
            if (this.currentEditId) {
                // 編輯模式
                await this.updateRecord(this.currentEditId, recordData);
            } else {
                // 新增模式
                await this.createRecord(recordData);
            }
        } catch (error) {
            console.error('儲存失敗:', error);
            alert('儲存失敗: ' + error.message);
        }
    }

    /**
     * 新增記錄到後端
     */
    async createRecord(recordData) {
        const response = await fetch('http://localhost:5001/api/draws', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(recordData)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || '新增失敗');
        }

        const result = await response.json();

        // 顯示成功訊息
        this.app.uiManager.showNotification('✅ 新增成功！', 'success');

        // 關閉彈窗
        this.closeModal();

        // 重新載入數據
        await this.app.loadData();
    }

    /**
     * 更新記錄到後端
     */
    async updateRecord(drawId, recordData) {
        const response = await fetch(`http://localhost:5001/api/draws/${drawId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(recordData)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || '更新失敗');
        }

        const result = await response.json();

        // 顯示成功訊息
        this.app.uiManager.showNotification('✅ 更新成功！', 'success');

        // 關閉彈窗
        this.closeModal();

        // 重新載入數據
        await this.app.loadData();
    }

    /**
     * 確認刪除記錄
     */
    confirmDelete(drawId) {
        if (!confirm('確定要刪除此記錄嗎？此操作無法復原。')) {
            return;
        }

        this.deleteRecord(drawId);
    }

    /**
     * 刪除記錄
     */
    async deleteRecord(drawId) {
        try {
            const response = await fetch(`http://localhost:5001/api/draws/${drawId}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || '刪除失敗');
            }

            // 顯示成功訊息
            this.app.uiManager.showNotification('✅ 刪除成功！', 'success');

            // 重新載入數據
            await this.app.loadData();
        } catch (error) {
            console.error('刪除失敗:', error);
            alert('刪除失敗: ' + error.message);
        }
    }
}
