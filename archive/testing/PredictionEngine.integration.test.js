import { PredictionEngine } from '../src/engine/PredictionEngine.js';
import { DataProcessor } from '../src/core/DataProcessor.js';
import { StatisticsService } from '../src/data/StatisticsService.js';
import { LOTTERY_RULES } from '../src/utils/Constants.js';

describe('PredictionEngine Integration Tests', () => {
  let dataProcessor;
  let statisticsService;
  let predictionEngine;

  beforeEach(() => {
    dataProcessor = new DataProcessor();
    dataProcessor.loadSampleData();
    statisticsService = new StatisticsService(dataProcessor);
    predictionEngine = new PredictionEngine(dataProcessor, statisticsService);
  });

  describe('Engine Initialization', () => {
    test('should initialize with all strategies', () => {
      expect(predictionEngine.strategies).toBeDefined();
      expect(Object.keys(predictionEngine.strategies).length).toBeGreaterThan(0);
    });

    test('should have core statistical strategies', () => {
      const coreStrategies = ['frequency', 'trend', 'bayesian', 'montecarlo', 'markov', 'deviation'];
      coreStrategies.forEach(strategy => {
        expect(predictionEngine.strategies[strategy]).toBeDefined();
      });
    });

    test('should have ensemble strategies', () => {
      const ensembleStrategies = [
        'ensemble_weighted',
        'ensemble_boosting',
        'ensemble_combined',
        'ensemble_cooccurrence',
        'ensemble_features'
      ];
      ensembleStrategies.forEach(strategy => {
        expect(predictionEngine.strategies[strategy]).toBeDefined();
      });
    });

    test('should have ML strategies', () => {
      const mlStrategies = ['ml_features', 'ml_forest', 'ml_genetic'];
      mlStrategies.forEach(strategy => {
        expect(predictionEngine.strategies[strategy]).toBeDefined();
      });
    });

    test('should have collaborative strategies', () => {
      const collaborativeStrategies = [
        'collaborative_relay',
        'collaborative_coop',
        'collaborative_hybrid'
      ];
      collaborativeStrategies.forEach(strategy => {
        expect(predictionEngine.strategies[strategy]).toBeDefined();
      });
    });

    test('should have folk strategies', () => {
      const folkStrategies = [
        'odd_even_balance',
        'zone_balance',
        'hot_cold_mix',
        'sum_range'
      ];
      folkStrategies.forEach(strategy => {
        expect(predictionEngine.strategies[strategy]).toBeDefined();
      });
    });
  });

  describe('predict method', () => {
    test('should throw error when no data available', async () => {
      dataProcessor.clearData();
      await expect(predictionEngine.predict('frequency', 50))
        .rejects.toThrow('無數據可供預測');
    });

    test('should predict with default parameters', async () => {
      const result = await predictionEngine.predict();
      
      expect(result).toHaveProperty('numbers');
      expect(result).toHaveProperty('probabilities');
      expect(result).toHaveProperty('confidence');
      expect(result.numbers).toHaveLength(LOTTERY_RULES.pickCount);
    });

    test('should predict with frequency method', async () => {
      const result = await predictionEngine.predict('frequency', 50);
      
      expect(result).toHaveProperty('numbers');
      expect(result.numbers).toHaveLength(6);
      expect(result.method).toBe('頻率回歸分析');
    });

    test('should fallback to frequency for unknown method', async () => {
      const result = await predictionEngine.predict('unknown_method', 50);
      
      expect(result).toHaveProperty('numbers');
      expect(result.method).toBe('頻率回歸分析');
    });

    test('should handle different sample sizes', async () => {
      const sizes = [30, 50, 100];
      
      for (const size of sizes) {
        const result = await predictionEngine.predict('frequency', size);
        expect(result.numbers).toHaveLength(6);
      }
    });
  });

  describe('predictWithData method', () => {
    test('should predict with custom data', async () => {
      const customData = dataProcessor.getDataRange(30);
      const result = await predictionEngine.predictWithData('frequency', customData);
      
      expect(result).toHaveProperty('numbers');
      expect(result.numbers).toHaveLength(6);
    });

    test('should work with different strategies', async () => {
      const customData = dataProcessor.getDataRange(50);
      const strategies = ['frequency', 'trend', 'bayesian'];
      
      for (const strategy of strategies) {
        const result = await predictionEngine.predictWithData(strategy, customData);
        expect(result.numbers).toHaveLength(6);
      }
    });

    test('should fallback to frequency for unknown strategy', async () => {
      const customData = dataProcessor.getDataRange(50);
      const result = await predictionEngine.predictWithData('unknown', customData);
      
      expect(result).toBeDefined();
      expect(result.numbers).toHaveLength(6);
    });
  });

  describe('All Strategies Integration', () => {
    test('all core strategies should produce valid predictions', async () => {
      const coreStrategies = ['frequency', 'trend', 'bayesian', 'montecarlo', 'markov', 'deviation'];
      
      for (const strategyName of coreStrategies) {
        const result = await predictionEngine.predict(strategyName, 50);
        
        expect(result.numbers).toHaveLength(6);
        expect(result.numbers.every(n => n >= 1 && n <= 49)).toBe(true);
        expect(new Set(result.numbers).size).toBe(6);
        expect(result.confidence).toBeGreaterThanOrEqual(0);
        expect(result.confidence).toBeLessThanOrEqual(100);
      }
    }, 30000); // 30 second timeout for all strategies

    test('all ensemble strategies should produce valid predictions', async () => {
      const ensembleStrategies = [
        'ensemble_weighted',
        'ensemble_boosting',
        'ensemble_combined',
        'ensemble_cooccurrence',
        'ensemble_features'
      ];
      
      for (const strategyName of ensembleStrategies) {
        const result = await predictionEngine.predict(strategyName, 50);
        
        expect(result.numbers).toHaveLength(6);
        expect(result.numbers.every(n => n >= 1 && n <= 49)).toBe(true);
        expect(new Set(result.numbers).size).toBe(6);
      }
    }, 30000);

    test('all ML strategies should produce valid predictions', async () => {
      const mlStrategies = ['ml_features', 'ml_forest', 'ml_genetic'];
      
      for (const strategyName of mlStrategies) {
        const result = await predictionEngine.predict(strategyName, 50);
        
        expect(result.numbers).toHaveLength(6);
        expect(result.numbers.every(n => n >= 1 && n <= 49)).toBe(true);
        expect(new Set(result.numbers).size).toBe(6);
      }
    }, 30000);

    test('all collaborative strategies should produce valid predictions', async () => {
      const collaborativeStrategies = [
        'collaborative_relay',
        'collaborative_coop',
        'collaborative_hybrid'
      ];
      
      for (const strategyName of collaborativeStrategies) {
        const result = await predictionEngine.predict(strategyName, 50);
        
        expect(result.numbers).toHaveLength(6);
        expect(result.numbers.every(n => n >= 1 && n <= 49)).toBe(true);
        expect(new Set(result.numbers).size).toBe(6);
      }
    }, 60000); // 60 seconds for collaborative strategies

    test('all folk strategies should produce valid predictions', async () => {
      const folkStrategies = [
        'odd_even_balance',
        'zone_balance',
        'hot_cold_mix',
        'sum_range'
      ];
      
      for (const strategyName of folkStrategies) {
        const result = await predictionEngine.predict(strategyName, 50);
        
        expect(result.numbers).toHaveLength(6);
        expect(result.numbers.every(n => n >= 1 && n <= 49)).toBe(true);
        expect(new Set(result.numbers).size).toBe(6);
      }
    }, 30000);
  });

  describe('Prediction Quality Checks', () => {
    test('predictions should be consistent for same data and method', async () => {
      const result1 = await predictionEngine.predict('frequency', 50);
      const result2 = await predictionEngine.predict('frequency', 50);
      
      // Frequency should give same results for same data
      expect(result1.numbers).toEqual(result2.numbers);
    });

    test('predictions should vary across different methods', async () => {
      const methods = ['frequency', 'trend', 'bayesian'];
      const results = [];
      
      for (const method of methods) {
        const result = await predictionEngine.predict(method, 50);
        results.push(result.numbers.join(','));
      }
      
      // At least some methods should produce different results
      const uniqueResults = new Set(results);
      expect(uniqueResults.size).toBeGreaterThan(1);
    });

    test('predictions should include probabilities for all numbers', async () => {
      const result = await predictionEngine.predict('frequency', 50);
      
      expect(Object.keys(result.probabilities)).toHaveLength(49);
      // Frequency probabilities sum to 6 (average numbers per draw)
      const sum = Object.values(result.probabilities).reduce((a, b) => a + b, 0);
      expect(sum).toBeCloseTo(6, 1);
    });
  });
});
