/**
 * UI 管理器
 * 負責頁面切換、通知顯示和全域 UI 狀態
 */
export class UIManager {
    constructor() {
        this.setupNavigation();
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
        notification.textContent = message;

        Object.assign(notification.style, {
            position: 'fixed',
            top: '20px',
            right: '20px',
            padding: '16px 24px',
            borderRadius: '12px',
            color: 'white',
            fontWeight: '500',
            zIndex: '1000',
            animation: 'slideIn 0.3s ease',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
            maxWidth: '400px'
        });

        const colors = {
            info: 'linear-gradient(135deg, rgba(59, 130, 246, 0.95), rgba(147, 51, 234, 0.95))',
            success: 'linear-gradient(135deg, rgba(34, 197, 94, 0.95), rgba(59, 130, 246, 0.95))',
            warning: 'linear-gradient(135deg, rgba(251, 191, 36, 0.95), rgba(245, 158, 11, 0.95))',
            error: 'linear-gradient(135deg, rgba(239, 68, 68, 0.95), rgba(220, 38, 38, 0.95))'
        };

        notification.style.background = colors[type] || colors.info;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 300);
        }, 3000);
    }

    updateDataSummary(stats) {
        if (!stats) return;

        const summary = document.getElementById('data-summary');
        if (summary) summary.style.display = 'block';

        const totalDraws = document.getElementById('total-draws');
        const dateRange = document.getElementById('date-range');
        const latestDraw = document.getElementById('latest-draw');

        if (totalDraws) totalDraws.textContent = stats.totalDraws;
        if (dateRange) dateRange.textContent = `${stats.dateRange.start} ~ ${stats.dateRange.end}`;
        if (latestDraw) latestDraw.textContent = stats.latestDraw;
    }

    updateHistoryTable(data, currentPage, itemsPerPage) {
        const tbody = document.getElementById('history-tbody');
        if (!tbody) return;

        const startIndex = (currentPage - 1) * itemsPerPage;
        const endIndex = startIndex + itemsPerPage;
        const pageData = data.slice(startIndex, endIndex);

        tbody.innerHTML = pageData.map(draw => `
            <tr>
                <td><strong>${draw.draw}</strong></td>
                <td>${draw.date}</td>
                <td>
                    <div class="draw-numbers">
                        ${draw.numbers.map(num => `<div class="draw-number">${num}</div>`).join('')}
                    </div>
                </td>
                <td>
                    <div class="draw-numbers">
                        <div class="draw-number special">${draw.special}</div>
                    </div>
                </td>
            </tr>
        `).join('');
    }

    updatePagination(totalItems, currentPage, itemsPerPage, onPageChange) {
        const totalPages = Math.ceil(totalItems / itemsPerPage);
        const pagination = document.getElementById('pagination');
        if (!pagination) return;

        let html = '';
        if (currentPage > 1) {
            html += `<button class="page-btn" data-page="${currentPage - 1}">‹ 上一頁</button>`;
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
            html += `<button class="page-btn" data-page="${currentPage + 1}">下一頁 ›</button>`;
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
