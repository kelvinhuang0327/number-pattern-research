/**
 * 分析模組
 * 負責數據視覺化和統計分析
 */

class AnalysisEngine {
    constructor(dataProcessor) {
        this.dataProcessor = dataProcessor;
        this.charts = {};
    }

    /**
     * 初始化所有圖表
     */
    initializeCharts() {
        this.createFrequencyChart();
        this.createMissingChart();
        this.createDistributionChart();
        this.updateHotColdNumbers();
    }

    /**
     * 創建號碼頻率圖表
     */
    createFrequencyChart() {
        const ctx = document.getElementById('frequency-chart');
        if (!ctx) return;

        const frequency = this.dataProcessor.calculateFrequency();
        const labels = Object.keys(frequency);
        const data = Object.values(frequency);

        // 銷毀舊圖表
        if (this.charts.frequency) {
            this.charts.frequency.destroy();
        }

        this.charts.frequency = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: '出現次數',
                    data: data,
                    backgroundColor: this.createGradient(ctx, 'primary'),
                    borderColor: 'rgba(147, 51, 234, 1)',
                    borderWidth: 1,
                    borderRadius: 6,
                    hoverBackgroundColor: this.createGradient(ctx, 'accent')
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15, 15, 25, 0.95)',
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        borderColor: 'rgba(147, 51, 234, 0.5)',
                        borderWidth: 1,
                        padding: 12,
                        displayColors: false,
                        callbacks: {
                            label: (context) => {
                                const total = this.dataProcessor.getData().length;
                                const percentage = ((context.parsed.y / total) * 100).toFixed(1);
                                return `出現 ${context.parsed.y} 次 (${percentage}%)`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)'
                        },
                        ticks: {
                            color: 'rgba(255, 255, 255, 0.7)',
                            font: {
                                family: 'Orbitron'
                            }
                        }
                    },
                    y: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)'
                        },
                        ticks: {
                            color: 'rgba(255, 255, 255, 0.7)'
                        }
                    }
                }
            }
        });
    }

    /**
     * 創建遺漏值圖表
     */
    createMissingChart() {
        const ctx = document.getElementById('missing-chart');
        if (!ctx) return;

        const missing = this.dataProcessor.calculateMissingValues();
        const labels = Object.keys(missing);
        const data = Object.values(missing);

        if (this.charts.missing) {
            this.charts.missing.destroy();
        }

        this.charts.missing = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: '遺漏期數',
                    data: data,
                    borderColor: 'rgba(59, 130, 246, 1)',
                    backgroundColor: this.createGradient(ctx, 'secondary'),
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: 'rgba(59, 130, 246, 1)',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15, 15, 25, 0.95)',
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        borderColor: 'rgba(59, 130, 246, 0.5)',
                        borderWidth: 1,
                        padding: 12,
                        displayColors: false,
                        callbacks: {
                            label: (context) => {
                                return `已遺漏 ${context.parsed.y} 期`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)'
                        },
                        ticks: {
                            color: 'rgba(255, 255, 255, 0.7)',
                            font: {
                                family: 'Orbitron'
                            }
                        }
                    },
                    y: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)'
                        },
                        ticks: {
                            color: 'rgba(255, 255, 255, 0.7)'
                        }
                    }
                }
            }
        });
    }

    /**
     * 創建分佈圖表
     */
    createDistributionChart() {
        const ctx = document.getElementById('distribution-chart');
        if (!ctx) return;

        const distribution = this.dataProcessor.calculateDistribution();
        const labels = Object.keys(distribution);
        const data = Object.values(distribution);

        if (this.charts.distribution) {
            this.charts.distribution.destroy();
        }

        this.charts.distribution = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: [
                        'rgba(147, 51, 234, 0.8)',
                        'rgba(59, 130, 246, 0.8)',
                        'rgba(236, 72, 153, 0.8)',
                        'rgba(251, 191, 36, 0.8)',
                        'rgba(34, 197, 94, 0.8)'
                    ],
                    borderColor: [
                        'rgba(147, 51, 234, 1)',
                        'rgba(59, 130, 246, 1)',
                        'rgba(236, 72, 153, 1)',
                        'rgba(251, 191, 36, 1)',
                        'rgba(34, 197, 94, 1)'
                    ],
                    borderWidth: 2,
                    hoverOffset: 10
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: 'rgba(255, 255, 255, 0.9)',
                            padding: 15,
                            font: {
                                size: 12,
                                family: 'Noto Sans TC'
                            }
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15, 15, 25, 0.95)',
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        borderColor: 'rgba(147, 51, 234, 0.5)',
                        borderWidth: 1,
                        padding: 12,
                        callbacks: {
                            label: (context) => {
                                const total = data.reduce((a, b) => a + b, 0);
                                const percentage = ((context.parsed / total) * 100).toFixed(1);
                                return `${context.label}: ${context.parsed} 次 (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    }

    /**
     * 更新冷熱號顯示
     */
    updateHotColdNumbers() {
        const hotNumbers = this.dataProcessor.getHotNumbers(10);
        const coldNumbers = this.dataProcessor.getColdNumbers(10);

        // 顯示熱門號碼
        const hotContainer = document.getElementById('hot-numbers');
        if (hotContainer) {
            hotContainer.innerHTML = hotNumbers.map(item => `
                <div class="number-badge hot" title="出現 ${item.frequency} 次 (${item.percentage}%)">
                    ${item.number}
                </div>
            `).join('');
        }

        // 顯示冷門號碼
        const coldContainer = document.getElementById('cold-numbers');
        if (coldContainer) {
            coldContainer.innerHTML = coldNumbers.map(item => `
                <div class="number-badge cold" title="出現 ${item.frequency} 次 (${item.percentage}%)">
                    ${item.number}
                </div>
            `).join('');
        }
    }

    /**
     * 創建漸層色
     */
    createGradient(ctx, type = 'primary') {
        const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 400);

        if (type === 'primary') {
            gradient.addColorStop(0, 'rgba(147, 51, 234, 0.8)');
            gradient.addColorStop(1, 'rgba(236, 72, 153, 0.3)');
        } else if (type === 'secondary') {
            gradient.addColorStop(0, 'rgba(59, 130, 246, 0.6)');
            gradient.addColorStop(1, 'rgba(59, 130, 246, 0.1)');
        } else if (type === 'accent') {
            gradient.addColorStop(0, 'rgba(236, 72, 153, 0.8)');
            gradient.addColorStop(1, 'rgba(147, 51, 234, 0.3)');
        }

        return gradient;
    }

    /**
     * 銷毀所有圖表
     */
    destroyCharts() {
        Object.values(this.charts).forEach(chart => {
            if (chart) chart.destroy();
        });
        this.charts = {};
    }
}

// 導出為全域變數
window.AnalysisEngine = AnalysisEngine;
