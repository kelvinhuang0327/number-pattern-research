import { LOTTERY_RULES } from '../../utils/Constants.js';

export class LSTMStrategy {
    constructor(statisticsService) {
        this.statisticsService = statisticsService;
    }

    async predict(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const sequenceLength = 10;
        const featureSize = range;
        const recentData = data.slice(-300);

        if (recentData.length < sequenceLength + 1) {
            const freqStrategy = new (await import('./FrequencyStrategy.js')).FrequencyStrategy(this.statisticsService);
            return freqStrategy.predict(data);
        }

        const xs = [];
        const ys = [];

        for (let i = 0; i < recentData.length - sequenceLength; i++) {
            const sequence = [];
            for (let j = 0; j < sequenceLength; j++) {
                const draw = recentData[i + j];
                const input = new Array(range).fill(0);
                draw.numbers.forEach(num => { input[num - 1] = 1; });
                sequence.push(input);
            }
            xs.push(sequence);

            const targetDraw = recentData[i + sequenceLength];
            const target = new Array(range).fill(0);
            targetDraw.numbers.forEach(num => { target[num - 1] = 1; });
            ys.push(target);
        }

        const xsTensor = tf.tensor3d(xs, [xs.length, sequenceLength, featureSize]);
        const ysTensor = tf.tensor2d(ys, [ys.length, range]);

        const model = tf.sequential();
        model.add(tf.layers.lstm({
            units: 16,
            inputShape: [sequenceLength, featureSize],
            returnSequences: false,
            kernelInitializer: 'glorotUniform',
            recurrentInitializer: 'glorotUniform'
        }));
        model.add(tf.layers.dense({ units: range, activation: 'sigmoid' }));

        model.compile({ optimizer: 'adam', loss: 'binaryCrossentropy' });

        await model.fit(xsTensor, ysTensor, {
            epochs: 2,
            batchSize: 32,
            verbose: 0
        });

        const lastSequence = [];
        for (let i = recentData.length - sequenceLength; i < recentData.length; i++) {
            const draw = recentData[i];
            const input = new Array(range).fill(0);
            draw.numbers.forEach(num => { input[num - 1] = 1; });
            lastSequence.push(input);
        }

        const inputTensor = tf.tensor3d([lastSequence], [1, sequenceLength, featureSize]);
        const outputTensor = model.predict(inputTensor);
        const probsArray = await outputTensor.data();

        xsTensor.dispose();
        ysTensor.dispose();
        inputTensor.dispose();
        outputTensor.dispose();
        model.dispose();

        const probabilities = {};
        for (let i = 0; i < range; i++) {
            probabilities[i + 1] = probsArray[i];
        }

        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);

        // 簡單信心度
        const confidence = 85;

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: 'LSTM 深度學習模型',
            report: `基於 LSTM 序列模型的預測結果。`
        };
    }
}
