import { getApiUrl } from '../config/apiConfig.js';
import { apiClient } from '../services/ApiClient.js';

/**
 * UI 管理器
 * 負責頁面切換、通知顯示和全域 UI 狀態
 */
export class UIManager {
    constructor() {
        this.setupNavigation();
        this.initWaterline();
    }

    initWaterline() {
        this.updateWaterline();
        // Refresh every 5 minutes
        setInterval(() => this.updateWaterline(), 300000);
    }

    async updateWaterline() {
        try {
            const data = await apiClient.get('/api/performance/regime');
            
            const dot = document.getElementById('waterline-status-dot');
            const regimeSpan = document.getElementById('waterline-regime');
            const adviceDiv = document.getElementById('waterline-advice');

            if (data && dot && regimeSpan && adviceDiv) {
                regimeSpan.textContent = data.regime || 'UNKNOWN';
                adviceDiv.textContent = data.recommendation || '';
                if (data.color) {
                    dot.style.background = data.color;
                    dot.style.boxShadow = `0 0 10px ${data.color}80`;
                }
            }
        } catch (error) {
            console.error('Failed to update waterline:', error);
        }
    }

    setupNavigation() {
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const section = e.currentTarget.dataset.section;
                this.showSection(section);
            });
        });
    }

    showSection(sectionName) {
        // 更新導航按鈕
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.section === sectionName) {
                btn.classList.add('active');
            }
        });

        // 顯示對應區塊
        document.querySelectorAll('.section').forEach(section => {
            section.classList.remove('active');
        });

        const targetSection = document.getElementById(`${sectionName}-section`);
        if (targetSection) {
            targetSection.classList.add('active');
        }
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;

        const icons = {
            info: 'info',
            success: 'check-circle',
            error: 'alert-circle',
            warning: 'alert-triangle'
        };

        const iconName = icons[type] || 'info';
        
        // 🛡️ Ensure message is safe
        const safeMessage = message.replace(/\n/g, '<br>');
        
        notification.innerHTML = `
            <i data-lucide="${iconName}" class="icon"></i>
            <div class="notification-content">${safeMessage}</div>
        `;

        document.body.appendChild(notification);
        
        // Initialize the new icon
        if (window.lucide) {
            window.lucide.createIcons({
                attrs: { class: 'icon' },
                nameAttr: 'data-lucide',
                root: notification
            });
        }

        // Auto remove
        setTimeout(() => {
            notification.classList.add('notification-fade-out');
            notification.addEventListener('animationend', () => {
                notification.remove();
            });
        }, 5000);
    }

    updateLotteryTypeSelector(stats, currentType) {
        const container = document.getElementById('lottery-type-container');
        const grid = document.getElementById('lottery-type-grid');

        if (!stats.lotteryTypeCount || Object.keys(stats.lotteryTypeCount).length === 0) {
            if (container) container.style.display = 'none';
            return;
        }

        if (container) container.style.display = 'block';

        // Import lottery types for metadata
        import('../utils/LotteryTypes.js').then(({ LOTTERY_TYPES }) => {
            if (grid) {
                grid.innerHTML = Object.entries(stats.lotteryTypeCount)
                    .map(([type, count]) => {
                        const lotteryType = LOTTERY_TYPES[type];
                        if (!lotteryType) return '';

                        const isActive = type === currentType ? 'active' : '';
                        const gradient = lotteryType.gradient || 'linear-gradient(135deg, #6366F1, #4F46E5)';

                        return `
                            <div class="lottery-type-card ${isActive}" 
                                 data-type="${type}" 
                                 style="--card-gradient: ${gradient};"
                                 onclick="document.getElementById('lottery-type-filter').value = '${type}'; document.getElementById('lottery-type-filter').dispatchEvent(new Event('change'));">
                                <div class="type-icon">${lotteryType.icon}</div>
                                <div class="type-name">${lotteryType.displayName}</div>
                                <div class="type-count">${count} 期</div>
                                <div class="type-description">${lotteryType.description}</div>
                            </div>
                        `;
                    }).join('');
            }
        });
    }

    /**
     * Update the current game type badge in header
     */
    updateCurrentGameBadge(lotteryType) {
        const badge = document.getElementById('current-game-badge');
        if (!badge) return;

        // Setup click listener for dropdown if not already set
        if (!badge.hasAttribute('data-listener-set')) {
            badge.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleGameSelector();
            });

            const dropdown = badge.querySelector('.game-selector-dropdown');
            if (dropdown) {
                dropdown.addEventListener('click', (e) => {
                    e.stopPropagation();
                });
            }

            // Close dropdown when clicking outside
            document.addEventListener('click', () => {
                badge.classList.remove('active');
            });

            badge.setAttribute('data-listener-set', 'true');
        }

        import('../utils/LotteryTypes.js').then(({ LOTTERY_TYPES }) => {
            if (!lotteryType || lotteryType === '') {
                // If no type selected but we have data, show "Select Game"
                const textSpan = badge.querySelector('.badge-text');
                if (textSpan) {
                    textSpan.textContent = '選擇彩券';
                    textSpan.title = '選擇彩券';
                }
                badge.title = '選擇彩券';
                badge.style.background = '';
                badge.style.display = 'flex';
                return;
            }

            const typeInfo = LOTTERY_TYPES[lotteryType];
            if (!typeInfo) return;

            const iconSpan = badge.querySelector('.badge-icon');
            const textSpan = badge.querySelector('.badge-text');
            const compactName = this.getCompactLotteryName(typeInfo);
            const fullName = typeInfo.displayName || compactName;

            if (iconSpan) iconSpan.textContent = typeInfo.icon;
            if (textSpan) {
                textSpan.textContent = compactName;
                textSpan.title = fullName;
            }
            badge.title = fullName;
            badge.style.background = '';

            badge.style.display = 'flex';

            // Pulse animation on change
            badge.style.animation = 'none';
            setTimeout(() => {
                badge.style.animation = 'badgePulse 2s ease-in-out infinite';
            }, 10);
        });
    }

    getCompactLotteryName(typeInfo) {
        if (!typeInfo) return '';
        const fullName = typeInfo.displayName || typeInfo.name || '';
        const compactMap = {
            '大樂透加開獎項': '大樂透加開',
            '6/38樂透彩': '6/38樂透',
            '賓果賓果': 'BINGO'
        };
        return compactMap[fullName] || fullName;
    }

    toggleGameSelector() {
        const badge = document.getElementById('current-game-badge');
        const listContainer = document.getElementById('header-game-list');

        if (!badge || !listContainer) return;

        // Toggle active class
        badge.classList.toggle('active');
    }

    populateGameSelector(container) {
        // Get stats from StatisticsService (we need to access App instance or pass stats)
        // Since UIManager doesn't hold stats directly, we'll look at the DOM or use a global reference if available
        // Better approach: The App calls updateDataSummary, we can cache the stats there.

        if (!this.lastStats || !this.lastStats.lotteryTypeCount) {
            container.innerHTML = '<div class="dropdown-item">無可用數據</div>';
            return;
        }

        import('../utils/LotteryTypes.js').then(({ LOTTERY_TYPES }) => {
            const html = Object.entries(this.lastStats.lotteryTypeCount)
                .map(([type, count]) => {
                    const lotteryType = LOTTERY_TYPES[type];
                    if (!lotteryType) {
                        console.warn('Unknown lottery type:', type);
                        return '';
                    }

                    const isActive = type === this.currentLotteryType ? 'active' : '';
                    const compactName = this.getCompactLotteryName(lotteryType);
                    const fullName = lotteryType.displayName || compactName;

                    return `
                        <div class="dropdown-item ${isActive}" 
                             onclick="event.stopPropagation(); document.getElementById('lottery-type-filter').value = '${type}'; document.getElementById('lottery-type-filter').dispatchEvent(new Event('change')); document.getElementById('current-game-badge').classList.remove('active');">
                            <div class="dropdown-item-icon">${lotteryType.icon}</div>
                            <div class="dropdown-item-info">
                                <span class="dropdown-item-name" title="${fullName}">${compactName}</span>
                                <span class="dropdown-item-count">${count} 期</span>
                            </div>
                        </div>
                    `;
                }).join('');

            container.innerHTML = html;
        }).catch(err => {
            console.error('Failed to populate game selector:', err);
            container.innerHTML = '<div class="dropdown-item">載入失敗</div>';
        });
    }

    updateDataSummary(stats, currentLotteryType = '') {
        if (!stats) return;

        const summary = document.getElementById('data-summary');
        if (summary) summary.style.display = 'block';

        const summaryContent = document.getElementById('summary-content');
        if (!summaryContent) return;

        summaryContent.innerHTML = `
            <div class="stat-card">
                <div class="stat-label">總期數</div>
                <div class="stat-value">${stats.totalDraws}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">日期範圍</div>
                <div class="stat-value">${stats.dateRange.start} ~ ${stats.dateRange.end}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">最新期數</div>
                <div class="stat-value">${stats.latestDraw}</div>
            </div>
        `;

        // Cache stats for dropdown
        this.lastStats = stats;
        this.currentLotteryType = currentLotteryType;

        // Update the current game badge
        this.updateCurrentGameBadge(currentLotteryType);

        // Update the lottery type selector cards
        this.updateLotteryTypeSelector(stats, currentLotteryType);

        // Pre-populate the dropdown so it's ready
        const listContainer = document.getElementById('header-game-list');
        if (listContainer) {
            this.populateGameSelector(listContainer);
        }

        // Update the history game statistics
        this.updateHistoryStats(stats, currentLotteryType);
    }

    updateHistoryStats(stats, currentLotteryType) {
        const statsContainer = document.getElementById('history-stats-container');
        if (!statsContainer) return;

        if (!stats.lotteryTypeCount || Object.keys(stats.lotteryTypeCount).length === 0) {
            statsContainer.classList.add('ui-hidden');
            return;
        }

        statsContainer.classList.remove('ui-hidden');

        import('../utils/LotteryTypes.js').then(({ LOTTERY_TYPES }) => {
            const html = Object.entries(stats.lotteryTypeCount)
                .map(([type, count]) => {
                    const lotteryType = LOTTERY_TYPES[type];
                    if (!lotteryType) return '';

                    const isActive = type === currentLotteryType ? 'active background-color-primary-light' : '';
                    const compactName = this.getCompactLotteryName(lotteryType);

                    // inline style or use existing classes for badges
                    return `
                        <div class="stat-badge ${isActive}" style="display: inline-flex; align-items: center; background: rgba(99, 102, 241, 0.1); color: #6366F1; border: 1px solid rgba(99, 102, 241, 0.2); border-radius: 20px; padding: 4px 12px; margin: 0 8px 8px 0; font-size: 0.9rem;">
                            <span class="type-icon ui-mr-5">${lotteryType.icon}</span>
                            <span class="type-name ui-fw-500">${compactName}</span>
                            <span class="type-count ui-ml-5 ui-fs-08" style="background: var(--primary-color, #6366F1); color: white; padding: 2px 6px; border-radius: 10px;">${count} 期</span>
                        </div>
                    `;
                }).join('');

            statsContainer.innerHTML = html;
        });
    }

    updateHistoryTable(data, currentPage, itemsPerPage) {
        const tbody = document.getElementById('history-tbody');
        const thead = document.querySelector('#history-table thead tr');
        if (!tbody) return;

        const startIndex = (currentPage - 1) * itemsPerPage;
        const endIndex = startIndex + itemsPerPage;
        const pageData = data.slice(startIndex, endIndex);

        // 彩券類型名稱映射
        const typeNames = {
            'BIG_LOTTO': '大樂透',
            'BIG_LOTTO_BONUS': '大樂透加開',
            'POWER_BALL': '威力彩',
            'POWER_LOTTO': '威力彩',
            'DAILY_539': '今彩539',
            'DAILY_CASH_539': '今彩539',
            'STAR_3': '三星彩',
            'STAR_4': '四星彩',
            'LOTTO_39': '39樂合彩',
            'LOTTO_49': '49樂合彩',
            'LOTTO_38': '38樂合彩',
            'BINGO_BINGO': '賓果賓果',
            'DOUBLE_WIN': '雙贏彩',
            'LOTTO_6_38': '6/38樂透彩'
        };

        // 有特別號的彩券類型
        const hasSpecialNumber = (lotteryType) => {
            if (!lotteryType) return false;
            const type = String(lotteryType).trim();
            // Debug: 檢查實際的彩券類型值
            // console.log('Checking lottery type:', type);
            // 威力彩 (POWER_LOTTO) 和大樂透 (BIG_LOTTO) 都有特別號
            return ['BIG_LOTTO', 'POWER_LOTTO', 'POWER_BALL', '大樂透', '威力彩'].includes(type);
        };

        // 檢查當前頁面是否有任何資料需要特別號欄位
        const needsSpecialColumn = pageData.some(draw => hasSpecialNumber(draw.lotteryType));
        console.log('Needs special column:', needsSpecialColumn, 'Page data sample type:', pageData[0]?.lotteryType);

        // 動態更新表頭
        if (thead) {
            if (needsSpecialColumn) {
                thead.innerHTML = `
                    <th>期數</th>
                    <th>彩券類型</th>
                    <th>開獎日期</th>
                    <th>開獎號碼</th>
                    <th>特別號</th>
                    <th style="width: 120px;">操作</th>
                `;
            } else {
                thead.innerHTML = `
                    <th>期數</th>
                    <th>彩券類型</th>
                    <th>開獎日期</th>
                    <th>開獎號碼</th>
                    <th style="width: 120px;">操作</th>
                `;
            }
        }

        // 動態生成表格內容
        tbody.innerHTML = pageData.map(draw => {
            const hasSpecial = hasSpecialNumber(draw.lotteryType);
            const drawId = draw.id || draw.draw; // 使用 id 或 draw 作為識別
            const drawData = JSON.stringify(draw).replace(/"/g, '&quot;');

            return `
                <tr>
                    <td><strong>${draw.draw}</strong></td>
                    <td><span class="lottery-type-badge">${typeNames[draw.lotteryType] || draw.lotteryType || '未知'}</span></td>
                    <td>${draw.date}</td>
                    <td>
                        <div class="draw-numbers">
                            ${draw.numbers ? draw.numbers.map(num => `<div class="draw-number">${String(num).padStart(2, '0')}</div>`).join('') : '<span>-</span>'}
                        </div>
                    </td>
                    ${needsSpecialColumn ? `
                        <td>
                            <div class="draw-numbers">
                                ${hasSpecial && draw.special ?
                        `<div class="draw-number special">${String(draw.special).padStart(2, '0')}</div>` :
                        '<span style="color: #999;">-</span>'}
                            </div>
                        </td>
                    ` : ''}
                    <td>
                        <div class="action-btn-group">
                            <button class="btn btn-sm btn-outline-primary" onclick="window.editRecord('${drawId}', ${drawData})">
                                <i data-lucide="edit-3" class="icon-sm"></i>
                                編輯
                            </button>
                            <button class="btn btn-sm btn-outline-error" onclick="window.deleteRecord('${drawId}')">
                                <i data-lucide="trash-2" class="icon-sm"></i>
                                刪除
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    }

    updatePagination(totalItems, currentPage, itemsPerPage, onPageChange) {
        const totalPages = Math.ceil(totalItems / itemsPerPage);
        const pagination = document.getElementById('pagination');
        if (!pagination) return;

        let html = '';
        if (currentPage > 1) {
            html += `<button class="page-btn" data-page="${currentPage - 1}">
                <i data-lucide="chevron-left" class="icon-sm"></i>
                上一頁
            </button>`;
        }

        const startPage = Math.max(1, currentPage - 2);
        const endPage = Math.min(totalPages, currentPage + 2);

        if (startPage > 1) {
            html += `<button class="page-btn" data-page="1">1</button>`;
            if (startPage > 2) html += `<span class="page-ellipsis">...</span>`;
        }

        for (let i = startPage; i <= endPage; i++) {
            const activeClass = i === currentPage ? 'active' : '';
            html += `<button class="page-btn ${activeClass}" data-page="${i}">${i}</button>`;
        }

        if (endPage < totalPages) {
            if (endPage < totalPages - 1) html += `<span class="page-ellipsis">...</span>`;
            html += `<button class="page-btn" data-page="${totalPages}">${totalPages}</button>`;
        }

        if (currentPage < totalPages) {
            html += `<button class="page-btn" data-page="${currentPage + 1}">
                下一頁
                <i data-lucide="chevron-right" class="icon-sm"></i>
            </button>`;
        }

        pagination.innerHTML = html;

        pagination.querySelectorAll('.page-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const page = parseInt(e.target.dataset.page);
                onPageChange(page);
            });
        });
    }
}
