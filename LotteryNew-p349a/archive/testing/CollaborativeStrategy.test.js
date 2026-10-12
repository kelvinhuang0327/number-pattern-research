import { CollaborativeStrategy } from '../src/engine/strategies/CollaborativeStrategy.js';
import { StatisticsService } from '../src/data/StatisticsService.js';
import { DataProcessor } from '../src/core/DataProcessor.js';
import { LOTTERY_RULES } from '../src/utils/Constants.js';

describe('CollaborativeStrategy', () => {
  let dataProcessor;
  let statisticsService;
  let data;

  beforeEach(() => {
    dataProcessor = new DataProcessor();
    dataProcessor.loadSampleData();
    statisticsService = new StatisticsService(dataProcessor);
    data = dataProcessor.getDataRange(50);
  });

  describe('Relay Mode', () => {
    test('should predict with relay mode', async () => {
      const strategy = new CollaborativeStrategy(statisticsService, 'relay');
      const result = await strategy.predict(data);
      
      expect(result).toHaveProperty('numbers');
      expect(result).toHaveProperty('probabilities');
      expect(result).toHaveProperty('confidence');
      expect(result).toHaveProperty('method');
      expect(result).toHaveProperty('report');
    });

    test('relay mode should return 6 unique numbers', async () => {
      const strategy = new CollaborativeStrategy(statisticsService, 'relay');
      const result = await strategy.predict(data);
      
      expect(result.numbers).toHaveLength(LOTTERY_RULES.pickCount);
      expect(new Set(result.numbers).size).toBe(LOTTERY_RULES.pickCount);
    });

    test('relay mode numbers should be sorted', async () => {
      const strategy = new CollaborativeStrategy(statisticsService, 'relay');
      const result = await strategy.predict(data);
      
      const sorted = [...result.numbers].sort((a, b) => a - b);
      expect(result.numbers).toEqual(sorted);
    });

    test('relay mode method name should be correct', async () => {
      const strategy = new CollaborativeStrategy(statisticsService, 'relay');
      const result = await strategy.predict(data);
      
      expect(result.method).toBe('協作預測 (接力模式)');
    });

    test('relay mode report should mention stages', async () => {
      const strategy = new CollaborativeStrategy(statisticsService, 'relay');
      const result = await strategy.predict(data);
      
      expect(result.report).toContain('接力模式');
      expect(result.report).toContain('探索層');
    });
  }, 30000);

  describe('Cooperative Mode', () => {
    test('should predict with cooperative mode', async () => {
      const strategy = new CollaborativeStrategy(statisticsService, 'cooperative');
      const result = await strategy.predict(data);
      
      expect(result).toHaveProperty('numbers');
      expect(result).toHaveProperty('probabilities');
      expect(result).toHaveProperty('confidence');
      expect(result.method).toBe('協作預測 (合作模式)');
    });

    test('cooperative mode should return 6 unique numbers', async () => {
      const strategy = new CollaborativeStrategy(statisticsService, 'cooperative');
      const result = await strategy.predict(data);
      
      expect(result.numbers).toHaveLength(LOTTERY_RULES.pickCount);
      expect(new Set(result.numbers).size).toBe(LOTTERY_RULES.pickCount);
    });

    test('cooperative mode report should mention consensus', async () => {
      const strategy = new CollaborativeStrategy(statisticsService, 'cooperative');
      const result = await strategy.predict(data);
      
      expect(result.report).toContain('合作模式');
      expect(result.report).toContain('共識');
    });
  }, 30000);

  describe('Hybrid Mode', () => {
    test('should predict with hybrid mode (default)', async () => {
      const strategy = new CollaborativeStrategy(statisticsService);
      const result = await strategy.predict(data);
      
      expect(result).toHaveProperty('numbers');
      expect(result).toHaveProperty('probabilities');
      expect(result).toHaveProperty('confidence');
      expect(result.method).toBe('協作預測 (混合模式)');
    });

    test('hybrid mode should return 6 unique numbers', async () => {
      const strategy = new CollaborativeStrategy(statisticsService, 'hybrid');
      const result = await strategy.predict(data);
      
      expect(result.numbers).toHaveLength(LOTTERY_RULES.pickCount);
      expect(new Set(result.numbers).size).toBe(LOTTERY_RULES.pickCount);
    });

    test('hybrid mode numbers should be within valid range', async () => {
      const strategy = new CollaborativeStrategy(statisticsService, 'hybrid');
      const result = await strategy.predict(data);
      
      result.numbers.forEach(num => {
        expect(num).toBeGreaterThanOrEqual(1);
        expect(num).toBeLessThanOrEqual(49);
      });
    });

    test('hybrid mode report should mention filtering', async () => {
      const strategy = new CollaborativeStrategy(statisticsService, 'hybrid');
      const result = await strategy.predict(data);
      
      expect(result.report).toContain('混合模式');
      expect(result.report).toContain('過濾');
    });

    test('hybrid mode confidence should be reasonable', async () => {
      const strategy = new CollaborativeStrategy(statisticsService, 'hybrid');
      const result = await strategy.predict(data);
      
      expect(result.confidence).toBeGreaterThanOrEqual(60);
      expect(result.confidence).toBeLessThanOrEqual(95);
    });
  }, 60000);

  describe('Expert Groups', () => {
    test('should have all expert groups defined', () => {
      const strategy = new CollaborativeStrategy(statisticsService);
      
      expect(strategy.expertGroups).toHaveProperty('statistical');
      expect(strategy.expertGroups).toHaveProperty('probabilistic');
      expect(strategy.expertGroups).toHaveProperty('sequential');
      expect(strategy.expertGroups).toHaveProperty('feature');
      expect(strategy.expertGroups).toHaveProperty('optimizer');
    });

    test('each expert group should have strategies', () => {
      const strategy = new CollaborativeStrategy(statisticsService);
      
      Object.values(strategy.expertGroups).forEach(group => {
        expect(group).toHaveProperty('name');
        expect(group).toHaveProperty('strategies');
        expect(group).toHaveProperty('role');
        expect(Array.isArray(group.strategies)).toBe(true);
        expect(group.strategies.length).toBeGreaterThan(0);
      });
    });

    test('each strategy should have weight and name', () => {
      const strategy = new CollaborativeStrategy(statisticsService);
      
      Object.values(strategy.expertGroups).forEach(group => {
        group.strategies.forEach(expert => {
          expect(expert).toHaveProperty('name');
          expect(expert).toHaveProperty('strategy');
          expect(expert).toHaveProperty('weight');
          expect(typeof expert.weight).toBe('number');
          expect(expert.weight).toBeGreaterThan(0);
        });
      });
    });
  });

  describe('Probabilities', () => {
    test('all modes should return valid probabilities', async () => {
      const modes = ['relay', 'cooperative', 'hybrid'];
      
      for (const mode of modes) {
        const strategy = new CollaborativeStrategy(statisticsService, mode);
        const result = await strategy.predict(data);
        
        expect(Object.keys(result.probabilities)).toHaveLength(49);
        const sum = Object.values(result.probabilities).reduce((a, b) => a + b, 0);
        expect(sum).toBeCloseTo(1, 2);
      }
    }, 90000);

    test('probabilities should cover all numbers 1-49', async () => {
      const strategy = new CollaborativeStrategy(statisticsService, 'hybrid');
      const result = await strategy.predict(data);
      
      for (let i = 1; i <= 49; i++) {
        expect(result.probabilities[i]).toBeDefined();
        expect(result.probabilities[i]).toBeGreaterThanOrEqual(0);
        expect(result.probabilities[i]).toBeLessThanOrEqual(1);
      }
    });
  }, 30000);

  describe('Consistency', () => {
    test('same mode should produce consistent structure', async () => {
      const strategy = new CollaborativeStrategy(statisticsService, 'hybrid');
      
      const result1 = await strategy.predict(data);
      const result2 = await strategy.predict(data);
      
      expect(result1.method).toBe(result2.method);
      expect(Object.keys(result1)).toEqual(Object.keys(result2));
    }, 60000);

    test('different modes should have different characteristics', async () => {
      const relayStrategy = new CollaborativeStrategy(statisticsService, 'relay');
      const coopStrategy = new CollaborativeStrategy(statisticsService, 'cooperative');
      const hybridStrategy = new CollaborativeStrategy(statisticsService, 'hybrid');
      
      const relayResult = await relayStrategy.predict(data);
      const coopResult = await coopStrategy.predict(data);
      const hybridResult = await hybridStrategy.predict(data);
      
      expect(relayResult.method).not.toBe(coopResult.method);
      expect(coopResult.method).not.toBe(hybridResult.method);
      expect(relayResult.report).not.toBe(coopResult.report);
    }, 90000);
  });
});
