import { LOTTERY_RULES } from '../../utils/Constants.js';

export class TensorFlowStrategy {
    constructor(statisticsService) {
        this.statisticsService = statisticsService;
    }

    async predict(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const sequenceLength = 10; // 回看期數
        const recentData = data.slice(-100); // 取最近 100 期訓練

        if (recentData.length < sequenceLength + 1) {
            // 數據不足，回退到頻率分析
            const freqStrategy = new (await import('./FrequencyStrategy.js')).FrequencyStrategy(this.statisticsService);
            return freqStrategy.predict(data);
        }

        // 準備訓練數據
        const xs = [];
        const ys = [];

        for (let i = 0; i < recentData.length - sequenceLength; i++) {
            const sequence = [];
            for (let j = 0; j < sequenceLength; j++) {
                const draw = recentData[i + j];
                // 正規化輸入 (0-1)
                const input = new Array(range).fill(0);
                draw.numbers.forEach(num => { input[num - 1] = 1; });
                sequence.push(input);
            }
            xs.push(sequence.flat()); // Flatten for simple Dense model

            const targetDraw = recentData[i + sequenceLength];
            const target = new Array(range).fill(0);
            targetDraw.numbers.forEach(num => { target[num - 1] = 1; });
            ys.push(target);
        }

        const inputSize = sequenceLength * range;
        const xsTensor = tf.tensor2d(xs, [xs.length, inputSize]);
        const ysTensor = tf.tensor2d(ys, [ys.length, range]);

        // 建立簡單的神經網路模型
        const model = tf.sequential();
        model.add(tf.layers.dense({
            units: 128,
            activation: 'relu',
            inputShape: [inputSize]
        }));
        model.add(tf.layers.dropout({ rate: 0.2 }));
        model.add(tf.layers.dense({
            units: 64,
            activation: 'relu'
        }));
        model.add(tf.layers.dense({
            units: range,
            activation: 'sigmoid' // 多標籤分類用 sigmoid
        }));

        model.compile({
            optimizer: 'adam',
            loss: 'binaryCrossentropy',
            metrics: ['accuracy']
        });

        // 訓練
        await model.fit(xsTensor, ysTensor, {
            epochs: 10,
            batchSize: 32,
            verbose: 0
        });

        // 預測下一期
        const lastSequence = [];
        for (let i = recentData.length - sequenceLength; i < recentData.length; i++) {
            const draw = recentData[i];
            const input = new Array(range).fill(0);
            draw.numbers.forEach(num => { input[num - 1] = 1; });
            lastSequence.push(input);
        }

        const inputTensor = tf.tensor2d([lastSequence.flat()], [1, inputSize]);
        const outputTensor = model.predict(inputTensor);
        const probsArray = await outputTensor.data();

        // 清理
        xsTensor.dispose();
        ysTensor.dispose();
        inputTensor.dispose();
        outputTensor.dispose();
        model.dispose();

        // 整理結果
        const probabilities = {};
        for (let i = 0; i < range; i++) {
            probabilities[i + 1] = probsArray[i];
        }

        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);

        // 計算信心度
        const sumProb = sortedNumbers.reduce((acc, item) => acc + item.probability, 0);
        const confidence = Math.min(Math.round(sumProb * 20), 95); // 簡單估算

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: 'TensorFlow 神經網路',
            report: `基於 ${recentData.length} 期數據的深度神經網路預測。`
        };
    }
}
