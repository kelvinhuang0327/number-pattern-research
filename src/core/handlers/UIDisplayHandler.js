/**
 * UIDisplayHandler - 處理UI顯示相關邏輯
 */
export class UIDisplayHandler {
    constructor(app) {
        this.app = app;
    }

    /**
     * 更新預測方法說明卡片
     */
    updateMethodDescription(method) {
        console.log('🔄 updateMethodDescription called with method:', method);

        const card = document.getElementById('method-description-card');
        const icon = document.getElementById('method-icon');
        const title = document.getElementById('method-title');
        const description = document.getElementById('method-description');

        console.log('📋 Elements found:', { card: !!card, icon: !!icon, title: !!title, description: !!description });

        if (!card || !icon || !title || !description) {
            console.error('❌ Missing elements for method description card');
            return;
        }

        // 定義所有預測方法的說明
        const methodDescriptions = {
            'frequency': {
                icon: '📊',
                title: '頻率分析',
                desc: '分析歷史開獎號碼的出現頻率，選擇高頻號碼作為預測依據。',
                logic: [
                    '統計每個號碼在歷史記錄中的出現次數',
                    '計算出現頻率並排序',
                    '選擇頻率最高的號碼組合'
                ]
            },
            'trend': {
                icon: '📈',
                title: '趨勢分析',
                desc: '追蹤號碼的出現趨勢，識別上升或下降的模式。',
                logic: [
                    '分析近期號碼的出現趨勢',
                    '計算趨勢斜率和動量',
                    '選擇趨勢向上的號碼'
                ]
            },
            'bayesian': {
                icon: '🎲',
                title: '貝葉斯機率',
                desc: '基於貝葉斯定理，計算條件機率來預測號碼。',
                logic: [
                    '計算先驗機率（歷史頻率）',
                    '根據最近開獎更新後驗機率',
                    '選擇後驗機率最高的號碼'
                ]
            },
            'montecarlo': {
                icon: '🎯',
                title: '蒙地卡羅模擬',
                desc: '使用隨機模擬方法，產生大量可能組合並評估。',
                logic: [
                    '基於歷史數據生成機率分布',
                    '進行 10000+ 次隨機模擬',
                    '選擇出現頻率最高的組合'
                ]
            },
            'markov': {
                icon: '🔗',
                title: '馬可夫鏈',
                desc: '基於狀態轉移機率，預測下一期號碼。',
                logic: [
                    '建立號碼間的轉移機率矩陣',
                    '計算從當前狀態到下一狀態的機率',
                    '選擇轉移機率最高的號碼'
                ]
            },
            'deviation': {
                icon: '📉',
                title: '偏差追蹤',
                desc: '追蹤號碼的理論頻率與實際頻率的偏差。',
                logic: [
                    '計算每個號碼的理論出現頻率',
                    '比較實際頻率與理論頻率的差距',
                    '選擇負偏差（冷門）號碼進行回歸'
                ]
            },
            'ensemble_weighted': {
                icon: '🎯',
                title: '集成預測 (Ensemble)',
                desc: '結合多種策略的加權平均，提高預測穩定性。',
                logic: [
                    '同時運行 8+ 種核心策略',
                    '根據歷史表現分配權重',
                    '加權平均所有策略的預測結果'
                ]
            },
            'ensemble_combined': {
                icon: '⭐',
                title: '綜合集成 (最強)',
                desc: '結合統計、機器學習和民間策略的綜合預測。',
                logic: [
                    '融合 15+ 種不同類型的策略',
                    '使用動態權重調整機制',
                    '多層投票決策選出最優組合'
                ]
            },
            'ensemble_advanced': {
                icon: '🚀',
                title: '進階集成 (Boosting+關聯+特徵)',
                desc: '使用 Boosting、號碼關聯性和特徵加權的進階集成。',
                logic: [
                    'Boosting：迭代加強弱預測器',
                    '號碼關聯性：分析號碼間的共現模式',
                    '特徵加權：根據多維特徵動態調整'
                ]
            },
            'ml_forest': {
                icon: '🌲',
                title: '隨機森林 (Random Forest)',
                desc: '使用隨機森林機器學習算法進行預測。',
                logic: [
                    '構建多棵決策樹組成森林',
                    '每棵樹使用不同的特徵子集',
                    '投票決定最終預測結果'
                ]
            },
            'ml_genetic': {
                icon: '🧬',
                title: '遺傳優化 (Genetic)',
                desc: '使用遺傳算法優化號碼組合。',
                logic: [
                    '生成初始號碼組合種群',
                    '通過選擇、交叉、突變進化',
                    '適應度函數評估並保留最優解'
                ]
            },
            'collaborative_hybrid': {
                icon: '🤝',
                title: '混合協作模式',
                desc: '多個預測引擎協作，互相驗證和修正。',
                logic: [
                    '多個獨立引擎並行預測',
                    '交叉驗證並修正異常結果',
                    '協商決定最終預測組合'
                ]
            },
            'auto_optimize': {
                icon: '🤖',
                title: '智能自動優化',
                desc: '使用遺傳算法自動優化策略參數。',
                logic: [
                    '自動調整所有策略的權重參數',
                    '基於歷史數據進行回測驗證',
                    '迭代優化至最佳配置'
                ]
            },
            'backend_optimized': {
                icon: '🚀',
                title: '後端優化預測',
                desc: '使用後端計算資源進行深度優化（目標 10% 成功率）。',
                logic: [
                    '後端大規模並行計算',
                    '深度優化算法（30 代種群 50）',
                    '持久化最佳配置並應用'
                ]
            },
            'ai_prophet': {
                icon: '🔮',
                title: 'Prophet 時間序列',
                desc: 'Facebook 開源的時間序列預測模型。',
                logic: [
                    '分解趨勢、季節性、節假日效應',
                    '自動檢測變點（changepoints）',
                    '基於加法模型進行預測'
                ]
            },
            'ai_xgboost': {
                icon: '⚡',
                title: 'XGBoost 梯度提升',
                desc: '強大的梯度提升決策樹算法。',
                logic: [
                    '構建多個弱學習器（決策樹）',
                    '梯度下降優化殘差',
                    '正則化防止過擬合'
                ]
            },
            'ai_autogluon': {
                icon: '🤖',
                title: 'AutoGluon AutoML',
                desc: '自動機器學習框架，自動選擇最佳模型。',
                logic: [
                    '自動嘗試多種模型（XGBoost、CatBoost 等）',
                    '自動超參數調優',
                    '集成多個最佳模型'
                ]
            },
            'ai_lstm': {
                icon: '🧠',
                title: 'LSTM 神經網絡',
                desc: '長短期記憶神經網絡，擅長序列預測。',
                logic: [
                    '學習歷史序列的長期依賴關係',
                    '記憶門控制信息流動',
                    '輸出門生成預測結果'
                ]
            },
            'odd_even': {
                icon: '⚖️',
                title: '奇偶比例',
                desc: '根據奇數偶數的黃金比例進行預測。',
                logic: [
                    '分析歷史奇偶數比例分布',
                    '選擇接近 3:3 或 4:2 的組合',
                    '平衡奇偶數分布'
                ]
            },
            'zone_balance': {
                icon: '📍',
                title: '區間平衡',
                desc: '平衡不同號碼區間的分布。',
                logic: [
                    '將號碼範圍分為 3 個區間',
                    '每個區間選擇 2 個號碼',
                    '確保區間均勻分布'
                ]
            },
            'hot_cold': {
                icon: '🔥',
                title: '冷熱號混合',
                desc: '結合熱門號碼和冷門號碼的平衡策略。',
                logic: [
                    '識別最近 10 期的熱號',
                    '識別長期未出現的冷號',
                    '按 4:2 或 3:3 比例混合'
                ]
            },
            'sum_range': {
                icon: '➕',
                title: '和值+AC值',
                desc: '基於號碼總和與 AC 值（算術複雜度）的預測。',
                logic: [
                    '計算歷史和值的分布範圍',
                    '計算 AC 值評估號碼離散度',
                    '選擇和值與 AC 值在正常範圍的組合'
                ]
            },
            'number_pairs': {
                icon: '👥',
                title: '連號配對',
                desc: '分析連續號碼出現的模式。',
                logic: [
                    '統計連號（如 12-13）出現頻率',
                    '識別常見的號碼對',
                    '優先選擇高頻連號組合'
                ]
            },
            'statistical': {
                icon: '📐',
                title: '多維統計',
                desc: '綜合多種統計指標的多維分析。',
                logic: [
                    '計算均值、標準差、偏度、峰度',
                    '分析號碼分布的多維特徵',
                    '選擇統計特徵最優的組合'
                ]
            }
        };

        // 獲取對應方法的說明
        const info = methodDescriptions[method] || {
            icon: '❓',
            title: '未知方法',
            desc: '此方法暫無說明。',
            logic: ['暫無詳細邏輯說明']
        };

        // 更新卡片內容
        icon.textContent = info.icon;
        title.textContent = info.title;

        // 構建描述 HTML
        const logicList = info.logic.map(item => `<li>${item}</li>`).join('');
        description.innerHTML = `
            <p style="margin: 0 0 10px 0;">${info.desc}</p>
            <div style="background: rgba(255,255,255,0.15); padding: 12px; border-radius: 8px; margin-top: 10px;">
                <strong style="display: block; margin-bottom: 6px;">📌 預測邏輯：</strong>
                <ul style="margin: 5px 0; padding-left: 20px;">
                    ${logicList}
                </ul>
            </div>
        `;
    }

    /**
     * 顯示單注預測結果
     */
    displayPredictionResult(result) {
        // 顯示單注結果，隱藏雙注結果
        const singleResult = document.getElementById('prediction-results');
        const dualResult = document.getElementById('dual-bet-results');

        if (singleResult) singleResult.style.display = 'block';
        if (dualResult) dualResult.style.display = 'none';

        const container = document.getElementById('predicted-numbers');
        if (container) {
            container.innerHTML = result.numbers.map(num =>
                `<div class="predicted-number">${num}</div>`
            ).join('');
        }

        // Apply lottery-type-specific styling
        const predictionResults = document.querySelector('.prediction-results');
        if (predictionResults && this.app.currentLotteryType) {
            predictionResults.setAttribute('data-lottery-type', this.app.currentLotteryType);
        }

        const confidenceVal = document.getElementById('confidence-value');
        const confidenceFill = document.getElementById('confidence-fill');

        // 顯示信心度
        let confidenceDisplay = result.confidence;
        // 如果是小數 (0.82)，轉換為百分比 (82)
        if (confidenceDisplay <= 1) {
            confidenceDisplay = (confidenceDisplay * 100).toFixed(1);
        }

        if (confidenceVal) confidenceVal.textContent = `${confidenceDisplay}%`;
        if (confidenceFill) confidenceFill.style.width = `${Math.min(100, confidenceDisplay)}%`;

        // 顯示分析報告和方法名稱
        const report = document.getElementById('prediction-report');
        if (report) {
            let methodInfo = '';
            if (result.method) {
                methodInfo = `<strong>使用策略：</strong> ${result.method}<br>`;
            }

            // 如果有詳細信息 (集成預測會返回 details)
            let detailsInfo = '';
            if (result.details && Array.isArray(result.details)) {
                detailsInfo = `<br><div style="font-size: 0.9em; margin-top: 8px; color: #aaa;">
                    <strong>策略詳情：</strong><br>
                    ${result.details.join('<br>')}
                </div>`;
            }

            report.innerHTML = `${methodInfo}${result.report || '分析完成'}${detailsInfo}`;
        }
    }

    /**
     * 顯示雙注預測結果
     */
    displayDualBetResult(result) {
        // 顯示雙注結果（保持單注結果可見）
        const dualResult = document.getElementById('dual-bet-results');

        if (dualResult) dualResult.style.display = 'block';

        // 第一注號碼
        const bet1Container = document.getElementById('dual-bet-numbers-1');
        if (bet1Container) {
            bet1Container.innerHTML = result.bet1.numbers.map(num =>
                `<div class="predicted-number">${num}</div>`
            ).join('');
        }

        // 第二注號碼
        const bet2Container = document.getElementById('dual-bet-numbers-2');
        if (bet2Container) {
            bet2Container.innerHTML = result.bet2.numbers.map(num =>
                `<div class="predicted-number">${num}</div>`
            ).join('');
        }

        // 信心度
        const conf1 = document.getElementById('dual-bet-confidence-1');
        const conf2 = document.getElementById('dual-bet-confidence-2');
        const confOverall = document.getElementById('dual-bet-overall-confidence');
        const stratCount = document.getElementById('dual-bet-strategy-count');

        if (conf1) conf1.textContent = `${result.bet1.confidence.toFixed(1)}%`;
        if (conf2) conf2.textContent = `${result.bet2.confidence.toFixed(1)}%`;
        if (confOverall) confOverall.textContent = `${result.overall.confidence.toFixed(1)}%`;
        if (stratCount) stratCount.textContent = result.overall.strategyCount;

        // 詳細報告
        const report = document.getElementById('dual-bet-report');
        if (report) {
            report.innerHTML = `
                <h4>策略整合分析</h4>
                <p><strong>參與策略：</strong>${result.overall.strategyCount} 個</p>
                <p><strong>前5大貢獻策略：</strong></p>
                <ul>
                    ${result.overall.topStrategies.map(s => `<li>${s}</li>`).join('')}
                </ul>
                <p><strong>建議：</strong>第一注為最高信心組合，第二注為次優補充。兩注覆蓋12個最佳候選號碼，提升整體中獎機會。</p>
            `;
        }
    }

    /**
     * 顯示智能雙注預測結果
     */
    displaySmartDualBetResult(result) {
        // 顯示結果區域
        const resultsDiv = document.getElementById('smart-dual-bet-results');
        if (resultsDiv) {
            resultsDiv.style.display = 'block';
        }

        // 第一注號碼 + 特別號
        const bet1Container = document.getElementById('smart-dual-bet-numbers-1');
        if (bet1Container) {
            let html = result.bet1.numbers.map(num =>
                `<div class="predicted-number">${num}</div>`
            ).join('');
            // 添加特別號（如果有）
            if (result.bet1.special) {
                html += `<div class="predicted-number special-number" style="background: linear-gradient(135deg, #FFD700, #FFA500); color: #000; border: 2px solid #FF8C00;" title="特別號">★${result.bet1.special}</div>`;
            }
            bet1Container.innerHTML = html;
        }

        // 第二注號碼 + 特別號
        const bet2Container = document.getElementById('smart-dual-bet-numbers-2');
        if (bet2Container) {
            let html = result.bet2.numbers.map(num =>
                `<div class="predicted-number">${num}</div>`
            ).join('');
            // 添加特別號（如果有）
            if (result.bet2.special) {
                html += `<div class="predicted-number special-number" style="background: linear-gradient(135deg, #FFD700, #FFA500); color: #000; border: 2px solid #FF8C00;" title="特別號">★${result.bet2.special}</div>`;
            }
            bet2Container.innerHTML = html;
        }

        // 信心度
        const conf1 = document.getElementById('smart-dual-bet-confidence-1');
        const conf2 = document.getElementById('smart-dual-bet-confidence-2');
        if (conf1) conf1.textContent = `${result.bet1.confidence.toFixed(1)}%`;
        if (conf2) conf2.textContent = `${result.bet2.confidence.toFixed(1)}%`;

        // 使用的方法說明
        const methodDiv = document.getElementById('smart-dual-bet-method');
        if (methodDiv) {
            const specialNote = (result.bet1.special || result.bet2.special) ? ' (含特別號預測)' : '';
            methodDiv.innerHTML = `使用策略：<strong>${result.method}</strong>${specialNote} | 基於全部歷史數據分析`;
        }

        // 滾動到結果區域
        if (resultsDiv) {
            resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    /**
     * 顯示下一期預測結果
     */
    displayNextPeriodPrediction(result) {
        const bet1Container = document.getElementById('next-period-numbers-1');
        if (bet1Container) {
            bet1Container.innerHTML = result.bet1.numbers.map(num =>
                `<div class="predicted-number">${num}</div>`
            ).join('');
        }

        const bet2Container = document.getElementById('next-period-numbers-2');
        if (bet2Container) {
            bet2Container.innerHTML = result.bet2.numbers.map(num =>
                `<div class="predicted-number">${num}</div>`
            ).join('');
        }

        const bet1ConfidenceEl = document.getElementById('next-period-confidence-1');
        if (bet1ConfidenceEl) {
            bet1ConfidenceEl.textContent = `${result.bet1.confidence.toFixed(1)}%`;
        }

        const bet2ConfidenceEl = document.getElementById('next-period-confidence-2');
        if (bet2ConfidenceEl) {
            bet2ConfidenceEl.textContent = `${result.bet2.confidence.toFixed(1)}%`;
        }

        // 更新策略數量
        const strategyCountEl = document.getElementById('next-period-strategy-count');
        if (strategyCountEl) {
            strategyCountEl.textContent = result.strategyCount || 0;
        }

        // 更新整體信心度
        const overallConfidenceEl = document.getElementById('next-period-overall-confidence');
        if (overallConfidenceEl) {
            overallConfidenceEl.textContent = `${result.overallConfidence.toFixed(1)}%`;
        }

        // 更新基準期數
        const basePeriodEl = document.getElementById('next-period-base');
        if (basePeriodEl) {
            basePeriodEl.textContent = result.basePeriod || '-';
        }

        // 更新預測報告
        const reportEl = document.getElementById('next-period-report');
        if (reportEl) {
            reportEl.innerHTML = `
                <h4>預測分析報告</h4>
                <p><strong>預測策略：</strong>${result.strategyCount} 種策略協作預測</p>
                <p><strong>數據基準：</strong>${result.basePeriod} 期之前的所有歷史數據</p>
                <p><strong>整體信心度：</strong>${result.overallConfidence.toFixed(1)}%</p>
                <p><strong>預測說明：</strong></p>
                <ul>
                    <li>第一注為最高信心組合（信心度 ${result.bet1.confidence.toFixed(1)}%）</li>
                    <li>第二注為次優補充組合（信心度 ${result.bet2.confidence.toFixed(1)}%）</li>
                    <li>兩注合計覆蓋 ${result.bet1.numbers.length + result.bet2.numbers.length} 個最佳候選號碼</li>
                </ul>
                <p><strong>建議：</strong>建議優先投注第一組號碼。如預算充足，可同時投注兩組以提高中獎機會。</p>
            `;
        }
    }

    /**
     * 顯示模擬測試結果
     */
    displaySimulationResults(results, successCount) {
        const resultsDiv = document.getElementById('simulation-results');
        const rateSpan = document.getElementById('simulation-success-rate');
        const tbody = document.getElementById('simulation-tbody');

        if (resultsDiv && rateSpan && tbody) {
            resultsDiv.style.display = 'block';

            // 計算成功率
            const successRate = results.length > 0 ? Math.round((successCount / results.length) * 100) : 0;
            rateSpan.textContent = `${successRate}%`;

            // 清空表格
            tbody.innerHTML = '';

            // 依日期降序排列（最新的在最上面）
            const sortedResults = [...results].sort((a, b) => {
                const dateA = a.date.replace(/\//g, '-');
                const dateB = b.date.replace(/\//g, '-');
                return dateB.localeCompare(dateA);
            });

            // 顯示結果
            sortedResults.forEach(r => {
                const row = document.createElement('tr');

                // 如果成功，整行加上成功樣式
                if (r.isSuccess) {
                    row.classList.add('success-row');
                }

                // 期數與日期
                const drawCell = document.createElement('td');
                drawCell.innerHTML = `
                    <div style="font-weight: 500;">${r.draw}</div>
                    <div style="font-size: 0.85em; color: #888;">${r.date}</div>
                `;
                row.appendChild(drawCell);

                // 預測號碼（含特別號）
                const predCell = document.createElement('td');
                let predHtml = r.predicted.map(n => `<span class="num-badge">${n}</span>`).join(' ');
                if (r.predictedSpecial) {
                    predHtml += ` <span class="num-badge special" style="background: #FFD700; color: #000;">★${r.predictedSpecial}</span>`;
                }
                predCell.innerHTML = predHtml;
                row.appendChild(predCell);

                // 實際開獎號碼（含特別號）
                const actualCell = document.createElement('td');
                let actualHtml = r.actual.map(n => `<span class="num-badge">${n}</span>`).join(' ');
                if (r.actualSpecial) {
                    actualHtml += ` <span class="num-badge special" style="background: #FFD700; color: #000;">★${r.actualSpecial}</span>`;
                }
                actualCell.innerHTML = actualHtml;
                row.appendChild(actualCell);

                // 命中數（強調）
                const hitsCell = document.createElement('td');
                hitsCell.style.fontWeight = '700';
                hitsCell.style.color = r.hits >= 3 ? '#22c55e' : '#888';
                hitsCell.textContent = r.hits;
                row.appendChild(hitsCell);

                // 結果（用圖示）
                const resultCell = document.createElement('td');
                resultCell.textContent = r.isSuccess ? '✅' : '❌';
                row.appendChild(resultCell);

                // 參考期數範圍（顯示起訖期數）
                const refCell = document.createElement('td');
                refCell.style.fontSize = '0.85em';
                refCell.style.color = '#888';
                refCell.textContent = r.refRange || '-';
                row.appendChild(refCell);

                tbody.appendChild(row);
            });
        }

        // 統計分析（可選）
        const existingStats = document.getElementById('simulation-stats');
        if (existingStats) {
            const hitDistribution = {};
            results.forEach(r => {
                const key = r.hits;
                hitDistribution[key] = (hitDistribution[key] || 0) + 1;
            });

            let statsHtml = '<h4>命中數分布</h4><ul>';
            Object.keys(hitDistribution).sort((a, b) => b - a).forEach(hits => {
                const count = hitDistribution[hits];
                const percent = ((count / results.length) * 100).toFixed(1);
                statsHtml += `<li>命中 ${hits} 個號碼: ${count} 次 (${percent}%)</li>`;
            });
            statsHtml += '</ul>';

            existingStats.innerHTML = statsHtml;
            existingStats.style.display = 'block';
        }

        // 滾動到結果
        const table = document.getElementById('simulation-table');
        if (table && table.parentNode) {
            table.parentNode.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }
}
