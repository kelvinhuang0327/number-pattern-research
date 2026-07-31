import { StatisticsService } from '../src/data/StatisticsService.js';
import { DataProcessor } from '../src/core/DataProcessor.js';
import { LOTTERY_RULES } from '../src/utils/Constants.js';

describe('StatisticsService', () => {
  let dataProcessor;
  let statisticsService;

  beforeEach(() => {
    dataProcessor = new DataProcessor();
    dataProcessor.loadSampleData();
    statisticsService = new StatisticsService(dataProcessor);
  });

  describe('getDataStats', () => {
    test('should return null when no data', () => {
      dataProcessor.clearData();
      const stats = statisticsService.getDataStats();
      expect(stats).toBeNull();
    });

    test('should return correct stats with data', () => {
      const stats = statisticsService.getDataStats();
      
      expect(stats).toHaveProperty('totalDraws');
      expect(stats).toHaveProperty('dateRange');
      expect(stats).toHaveProperty('latestDraw');
      expect(stats.totalDraws).toBe(500);
    });

    test('should have valid date range', () => {
      const stats = statisticsService.getDataStats();
      
      expect(stats.dateRange).toHaveProperty('start');
      expect(stats.dateRange).toHaveProperty('end');
      expect(stats.dateRange.start).toBeTruthy();
      expect(stats.dateRange.end).toBeTruthy();
    });
  });

  describe('calculateFrequency', () => {
    test('should calculate frequency for all numbers', () => {
      const frequency = statisticsService.calculateFrequency();
      
      expect(Object.keys(frequency)).toHaveLength(49);
      for (let i = 1; i <= 49; i++) {
        expect(frequency[i]).toBeDefined();
        expect(frequency[i]).toBeGreaterThanOrEqual(0);
      }
    });

    test('total frequency should equal total numbers drawn', () => {
      const frequency = statisticsService.calculateFrequency();
      const totalFrequency = Object.values(frequency).reduce((sum, freq) => sum + freq, 0);
      const expectedTotal = 500 * LOTTERY_RULES.pickCount;
      
      expect(totalFrequency).toBe(expectedTotal);
    });

    test('should work with custom data', () => {
      const customData = [
        { numbers: [1, 2, 3, 4, 5, 6], special: 7 },
        { numbers: [1, 2, 3, 7, 8, 9], special: 10 },
      ];
      const frequency = statisticsService.calculateFrequency(customData);
      
      expect(frequency[1]).toBe(2);
      expect(frequency[2]).toBe(2);
      expect(frequency[3]).toBe(2);
      expect(frequency[10]).toBe(0); // not in main numbers
    });
  });

  describe('calculateMissingValues', () => {
    test('should calculate missing values for all numbers', () => {
      const missing = statisticsService.calculateMissingValues();
      
      expect(Object.keys(missing)).toHaveLength(49);
      for (let i = 1; i <= 49; i++) {
        expect(missing[i]).toBeDefined();
        expect(missing[i]).toBeGreaterThanOrEqual(0);
      }
    });

    test('missing value should be 0 for numbers in latest draw', () => {
      const data = dataProcessor.getData();
      const latestNumbers = data[0].numbers;
      const missing = statisticsService.calculateMissingValues();
      
      latestNumbers.forEach(num => {
        expect(missing[num]).toBe(0);
      });
    });

    test('should work with custom data', () => {
      const customData = [
        { numbers: [1, 2, 3, 4, 5, 6], special: 7 },
        { numbers: [7, 8, 9, 10, 11, 12], special: 13 },
        { numbers: [1, 14, 15, 16, 17, 18], special: 19 },
      ];
      const missing = statisticsService.calculateMissingValues(customData);
      
      expect(missing[1]).toBe(0); // in latest draw (index 0)
      expect(missing[7]).toBe(1); // in draw index 1
      expect(missing[20]).toBe(3); // not in any draw
    });
  });

  describe('getHotNumbers', () => {
    test('should return top 10 hot numbers by default', () => {
      const hotNumbers = statisticsService.getHotNumbers();
      expect(hotNumbers).toHaveLength(10);
    });

    test('should return specified count of hot numbers', () => {
      const hotNumbers = statisticsService.getHotNumbers(5);
      expect(hotNumbers).toHaveLength(5);
    });

    test('hot numbers should be sorted by frequency descending', () => {
      const hotNumbers = statisticsService.getHotNumbers();
      
      for (let i = 0; i < hotNumbers.length - 1; i++) {
        expect(hotNumbers[i].frequency).toBeGreaterThanOrEqual(hotNumbers[i + 1].frequency);
      }
    });

    test('each hot number should have correct structure', () => {
      const hotNumbers = statisticsService.getHotNumbers(5);
      
      hotNumbers.forEach(item => {
        expect(item).toHaveProperty('number');
        expect(item).toHaveProperty('frequency');
        expect(item).toHaveProperty('percentage');
        expect(item.number).toBeGreaterThanOrEqual(1);
        expect(item.number).toBeLessThanOrEqual(49);
        expect(typeof item.percentage).toBe('string');
      });
    });
  });

  describe('getColdNumbers', () => {
    test('should return top 10 cold numbers by default', () => {
      const coldNumbers = statisticsService.getColdNumbers();
      expect(coldNumbers).toHaveLength(10);
    });

    test('should return specified count of cold numbers', () => {
      const coldNumbers = statisticsService.getColdNumbers(5);
      expect(coldNumbers).toHaveLength(5);
    });

    test('cold numbers should be sorted by frequency ascending', () => {
      const coldNumbers = statisticsService.getColdNumbers();
      
      for (let i = 0; i < coldNumbers.length - 1; i++) {
        expect(coldNumbers[i].frequency).toBeLessThanOrEqual(coldNumbers[i + 1].frequency);
      }
    });

    test('each cold number should have correct structure', () => {
      const coldNumbers = statisticsService.getColdNumbers(5);
      
      coldNumbers.forEach(item => {
        expect(item).toHaveProperty('number');
        expect(item).toHaveProperty('frequency');
        expect(item).toHaveProperty('percentage');
      });
    });
  });

  describe('calculateDistribution', () => {
    test('should return distribution for all 5 zones', () => {
      const distribution = statisticsService.calculateDistribution();
      
      expect(distribution).toHaveProperty('1-10');
      expect(distribution).toHaveProperty('11-20');
      expect(distribution).toHaveProperty('21-30');
      expect(distribution).toHaveProperty('31-40');
      expect(distribution).toHaveProperty('41-49');
    });

    test('distribution values should be percentages', () => {
      const distribution = statisticsService.calculateDistribution();
      
      Object.values(distribution).forEach(value => {
        const num = parseFloat(value);
        expect(num).toBeGreaterThanOrEqual(0);
        expect(num).toBeLessThanOrEqual(100);
      });
    });

    test('total distribution should approximate 100%', () => {
      const distribution = statisticsService.calculateDistribution();
      const total = Object.values(distribution).reduce((sum, val) => sum + parseFloat(val), 0);
      
      // Allow small floating point error
      expect(total).toBeGreaterThanOrEqual(99.9);
      expect(total).toBeLessThanOrEqual(100.1);
    });

    test('should handle empty data', () => {
      dataProcessor.clearData();
      const distribution = statisticsService.calculateDistribution();
      
      Object.values(distribution).forEach(value => {
        // When no data, values are numbers (0) not strings
        expect(value).toBe(0);
      });
    });
  });
});
