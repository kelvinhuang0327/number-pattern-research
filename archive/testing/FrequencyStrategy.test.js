import { FrequencyStrategy } from '../src/engine/strategies/FrequencyStrategy.js';
import { StatisticsService } from '../src/data/StatisticsService.js';
import { DataProcessor } from '../src/core/DataProcessor.js';
import { LOTTERY_RULES } from '../src/utils/Constants.js';

describe('FrequencyStrategy', () => {
  let dataProcessor;
  let statisticsService;
  let strategy;

  beforeEach(() => {
    dataProcessor = new DataProcessor();
    dataProcessor.loadSampleData();
    statisticsService = new StatisticsService(dataProcessor);
    strategy = new FrequencyStrategy(statisticsService);
  });

  describe('predict', () => {
    test('should return prediction result with correct structure', () => {
      const data = dataProcessor.getDataRange(50);
      const result = strategy.predict(data);
      
      expect(result).toHaveProperty('numbers');
      expect(result).toHaveProperty('probabilities');
      expect(result).toHaveProperty('confidence');
      expect(result).toHaveProperty('method');
      expect(result).toHaveProperty('report');
    });

    test('should predict exactly 6 numbers', () => {
      const data = dataProcessor.getDataRange(50);
      const result = strategy.predict(data);
      
      expect(result.numbers).toHaveLength(LOTTERY_RULES.pickCount);
    });

    test('predicted numbers should be sorted', () => {
      const data = dataProcessor.getDataRange(50);
      const result = strategy.predict(data);
      
      const sorted = [...result.numbers].sort((a, b) => a - b);
      expect(result.numbers).toEqual(sorted);
    });

    test('predicted numbers should be within valid range', () => {
      const data = dataProcessor.getDataRange(50);
      const result = strategy.predict(data);
      
      result.numbers.forEach(num => {
        expect(num).toBeGreaterThanOrEqual(LOTTERY_RULES.numberRange.min);
        expect(num).toBeLessThanOrEqual(LOTTERY_RULES.numberRange.max);
      });
    });

    test('predicted numbers should be unique', () => {
      const data = dataProcessor.getDataRange(50);
      const result = strategy.predict(data);
      
      const uniqueNumbers = new Set(result.numbers);
      expect(uniqueNumbers.size).toBe(LOTTERY_RULES.pickCount);
    });

    test('probabilities should cover all numbers', () => {
      const data = dataProcessor.getDataRange(50);
      const result = strategy.predict(data);
      
      expect(Object.keys(result.probabilities)).toHaveLength(49);
      for (let i = 1; i <= 49; i++) {
        expect(result.probabilities[i]).toBeDefined();
      }
    });

    test('probabilities should sum to 6 (frequency per draw)', () => {
      const data = dataProcessor.getDataRange(50);
      const result = strategy.predict(data);
      
      // Frequency is normalized by totalDraws, so sum = (total_numbers) / totalDraws = 6
      const sum = Object.values(result.probabilities).reduce((a, b) => a + b, 0);
      expect(sum).toBeCloseTo(6, 1);
    });

    test('confidence should be between 0 and 95', () => {
      const data = dataProcessor.getDataRange(50);
      const result = strategy.predict(data);
      
      expect(result.confidence).toBeGreaterThanOrEqual(0);
      expect(result.confidence).toBeLessThanOrEqual(95);
    });

    test('method should be correct', () => {
      const data = dataProcessor.getDataRange(50);
      const result = strategy.predict(data);
      
      expect(result.method).toBe('頻率回歸分析');
    });

    test('report should include data size', () => {
      const data = dataProcessor.getDataRange(50);
      const result = strategy.predict(data);
      
      expect(result.report).toContain('50');
    });
  });

  describe('calculateConfidence', () => {
    test('should calculate confidence correctly', () => {
      const sortedNumbers = [
        { number: 1, probability: 0.1 },
        { number: 2, probability: 0.09 },
        { number: 3, probability: 0.08 },
        { number: 4, probability: 0.07 },
        { number: 5, probability: 0.06 },
        { number: 6, probability: 0.05 },
      ];
      
      const probabilities = {};
      for (let i = 1; i <= 49; i++) {
        probabilities[i] = 1 / 49;
      }
      
      const confidence = strategy.calculateConfidence(sortedNumbers, probabilities);
      
      expect(typeof confidence).toBe('number');
      expect(confidence).toBeGreaterThanOrEqual(0);
      expect(confidence).toBeLessThanOrEqual(95);
    });
  });
});
