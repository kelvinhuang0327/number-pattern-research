import { FrequencyStrategy } from './strategies/FrequencyStrategy.js';
import { TrendStrategy } from './strategies/TrendStrategy.js';
import { CombinedStrategy } from './strategies/CombinedStrategy.js';
import { MachineLearningStrategy } from './strategies/MachineLearningStrategy.js';
import { MarkovStrategy } from './strategies/MarkovStrategy.js';
import { MonteCarloStrategy } from './strategies/MonteCarloStrategy.js';
import { CoOccurrenceStrategy } from './strategies/CoOccurrenceStrategy.js';
import { FeatureWeightedStrategy } from './strategies/FeatureWeightedStrategy.js';
import { BayesianStrategy } from './strategies/BayesianStrategy.js';
import { DeviationStrategy } from './strategies/DeviationStrategy.js';
import { BoostingStrategy } from './strategies/BoostingStrategy.js';
import { EnsembleStrategy } from './strategies/EnsembleStrategy.js';
import { TensorFlowStrategy } from './strategies/TensorFlowStrategy.js';
import { LSTMStrategy } from './strategies/LSTMStrategy.js';
import { AttentionLSTMStrategy } from './strategies/AttentionLSTMStrategy.js';

export class PredictionEngine {
    constructor(dataProcessor, statisticsService) {
        this.dataProcessor = dataProcessor;
        this.statisticsService = statisticsService;
        this.strategies = {
            'frequency': new FrequencyStrategy(statisticsService),
            'trend': new TrendStrategy(),
            'combined': new CombinedStrategy(statisticsService),
            'ml': new MachineLearningStrategy(statisticsService),
            'markov': new MarkovStrategy(),
            'montecarlo': new MonteCarloStrategy(statisticsService),
            'cooccurrence': new CoOccurrenceStrategy(),
            'weighted': new FeatureWeightedStrategy(statisticsService),
            'bayesian': new BayesianStrategy(statisticsService),
            'deviation': new DeviationStrategy(statisticsService),
            'boosting': new BoostingStrategy(statisticsService),
            'ensemble': new EnsembleStrategy(statisticsService, 'weighted'),
            'tf': new TensorFlowStrategy(statisticsService),
            'lstm': new LSTMStrategy(statisticsService),
            'attention': new AttentionLSTMStrategy(statisticsService),

            // Intelligent Ensemble Framework
            'adaptive_ensemble': new EnsembleStrategy(statisticsService, 'adaptive'),
            'consensus_voting': new EnsembleStrategy(statisticsService, 'consensus'),
            'pipeline': new EnsembleStrategy(statisticsService, 'weighted'), // Placeholder
            'hybrid_strategy': new EnsembleStrategy(statisticsService, 'adaptive'), // Placeholder
            'all_ensemble': new EnsembleStrategy(statisticsService, 'weighted'),
            'tactical_relay': new EnsembleStrategy(statisticsService, 'tactical_relay')
        };
    }

    async predict(method = 'frequency', sampleSize = 50) {
        const data = this.dataProcessor.getDataRange(sampleSize);

        if (data.length === 0) {
            throw new Error('無數據可供預測');
        }

        const strategy = this.strategies[method];
        if (!strategy) {
            // Fallback to frequency if method not found
            console.warn(`Strategy ${method} not found, falling back to frequency.`);
            return this.strategies['frequency'].predict(data);
        }

        return await strategy.predict(data);
    }

    // 模擬專用
    async predictWithData(method, data) {
        const strategy = this.strategies[method] || this.strategies['frequency'];
        return await strategy.predict(data);
    }
}
