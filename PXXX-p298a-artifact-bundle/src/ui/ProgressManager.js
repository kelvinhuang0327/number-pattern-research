/**
 * 進度管理器
 * 負責顯示和管理上傳/加載進度
 */

export class ProgressManager {
    constructor() {
        this.progressContainer = null;
        this.progressBar = null;
        this.progressText = null;
        this.isShowing = false;
        this.hideTimeout = null;
        this.createProgressUI();
    }

    /**
     * 創建進度條 UI
     */
    createProgressUI() {
        // 創建容器
        this.progressContainer = document.createElement('div');
        this.progressContainer.id = 'progress-container';
        this.progressContainer.className = 'progress-container hidden';

        // 創建進度條包裝器
        const progressWrapper = document.createElement('div');
        progressWrapper.className = 'progress-wrapper';

        // 創建進度文字
        this.progressText = document.createElement('div');
        this.progressText.className = 'progress-text';
        this.progressText.textContent = '準備中...';

        // 創建進度條背景
        const progressBg = document.createElement('div');
        progressBg.className = 'progress-bg';

        // 創建進度條
        this.progressBar = document.createElement('div');
        this.progressBar.className = 'progress-bar';
        this.progressBar.style.width = '0%';

        // 創建百分比文字
        const progressPercent = document.createElement('div');
        progressPercent.className = 'progress-percent';
        progressPercent.textContent = '0%';
        this.progressPercent = progressPercent;

        // 組裝
        progressBg.appendChild(this.progressBar);
        progressWrapper.appendChild(this.progressText);
        progressWrapper.appendChild(progressBg);
        progressWrapper.appendChild(progressPercent);
        this.progressContainer.appendChild(progressWrapper);

        // 添加到 body
        document.body.appendChild(this.progressContainer);
    }

    /**
     * 顯示進度條
     * @param {string} message - 進度訊息
     * @param {number} percentage - 進度百分比 (0-100)
     */
    show(message = '處理中...', percentage = 0) {
        // 如果有正在進行的隱藏操作，取消它
        if (this.hideTimeout) {
            clearTimeout(this.hideTimeout);
            this.hideTimeout = null;
        }

        this.isShowing = true;
        this.progressContainer.classList.remove('hidden');
        this.progressText.textContent = message;
        this.updateProgress(percentage);
    }

    /**
     * 更新進度
     * @param {number} percentage - 進度百分比 (0-100)
     * @param {string} message - 可選的訊息更新
     */
    updateProgress(percentage, message = null) {
        if (!this.isShowing) return;

        // 確保百分比在 0-100 之間
        percentage = Math.max(0, Math.min(100, percentage));

        // 更新進度條
        this.progressBar.style.width = `${percentage}%`;
        this.progressPercent.textContent = `${Math.round(percentage)}%`;

        // 更新訊息（如果提供）
        if (message) {
            this.progressText.textContent = message;
        }

        // 添加完成動畫
        if (percentage >= 100) {
            this.progressBar.classList.add('complete');
        } else {
            this.progressBar.classList.remove('complete');
        }
    }

    /**
     * 隱藏進度條
     * @param {number} delay - 延遲隱藏時間（毫秒）
     */
    hide(delay = 500) {
        if (!this.isShowing) return;

        // 清除任何現有的隱藏計時器
        if (this.hideTimeout) {
            clearTimeout(this.hideTimeout);
        }

        this.hideTimeout = setTimeout(() => {
            this.progressContainer.classList.add('hidden');
            this.isShowing = false;
            this.hideTimeout = null;

            // 重置進度
            setTimeout(() => {
                // 再次檢查是否已經重新顯示，如果是則不重置
                if (!this.isShowing) {
                    this.progressBar.style.width = '0%';
                    this.progressPercent.textContent = '0%';
                    this.progressText.textContent = '準備中...';
                    this.progressBar.classList.remove('complete');
                }
            }, 300);
        }, delay);
    }

    /**
     * 顯示不確定進度（動畫條）
     * @param {string} message - 進度訊息
     */
    showIndeterminate(message = '處理中...') {
        this.isShowing = true;
        this.progressContainer.classList.remove('hidden');
        this.progressText.textContent = message;
        this.progressBar.classList.add('indeterminate');
        this.progressPercent.textContent = '';
    }

    /**
     * 停止不確定進度
     */
    stopIndeterminate() {
        this.progressBar.classList.remove('indeterminate');
    }

    /**
     * 快速進度更新（用於多步驟操作）
     * @param {Array} steps - 步驟數組 [{message, duration}]
     */
    async runSteps(steps) {
        this.show(steps[0].message, 0);

        const totalDuration = steps.reduce((sum, step) => sum + (step.duration || 1000), 0);
        let elapsed = 0;

        for (let i = 0; i < steps.length; i++) {
            const step = steps[i];
            const stepDuration = step.duration || 1000;

            this.updateProgress(
                (elapsed / totalDuration) * 100,
                step.message
            );

            if (step.action) {
                await step.action();
            } else {
                await new Promise(resolve => setTimeout(resolve, stepDuration));
            }

            elapsed += stepDuration;
        }

        this.updateProgress(100, '完成！');
        this.hide(1000);
    }
}

// 導出單例
export const progressManager = new ProgressManager();
