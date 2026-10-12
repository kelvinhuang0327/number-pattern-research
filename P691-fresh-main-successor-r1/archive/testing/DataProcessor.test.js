import { DataProcessor } from '../src/core/DataProcessor.js';
import { LOTTERY_RULES } from '../src/utils/Constants.js';

describe('DataProcessor', () => {
  let dataProcessor;

  beforeEach(() => {
    dataProcessor = new DataProcessor();
  });

  describe('generateSampleData', () => {
    test('should generate 500 sample lottery draws', () => {
      const data = dataProcessor.generateSampleData();
      expect(data).toHaveLength(500);
    });

    test('each draw should have correct structure', () => {
      const data = dataProcessor.generateSampleData();
      const draw = data[0];
      
      expect(draw).toHaveProperty('draw');
      expect(draw).toHaveProperty('date');
      expect(draw).toHaveProperty('numbers');
      expect(draw).toHaveProperty('special');
      expect(draw.numbers).toHaveLength(LOTTERY_RULES.pickCount);
    });

    test('numbers should be sorted in ascending order', () => {
      const data = dataProcessor.generateSampleData();
      data.forEach(draw => {
        const sorted = [...draw.numbers].sort((a, b) => a - b);
        expect(draw.numbers).toEqual(sorted);
      });
    });

    test('numbers should be within valid range', () => {
      const data = dataProcessor.generateSampleData();
      data.forEach(draw => {
        draw.numbers.forEach(num => {
          expect(num).toBeGreaterThanOrEqual(LOTTERY_RULES.numberRange.min);
          expect(num).toBeLessThanOrEqual(LOTTERY_RULES.numberRange.max);
        });
      });
    });

    test('numbers should be unique within each draw', () => {
      const data = dataProcessor.generateSampleData();
      data.forEach(draw => {
        const uniqueNumbers = new Set(draw.numbers);
        expect(uniqueNumbers.size).toBe(LOTTERY_RULES.pickCount);
      });
    });

    test('special number should not be in main numbers', () => {
      const data = dataProcessor.generateSampleData();
      data.forEach(draw => {
        expect(draw.numbers).not.toContain(draw.special);
      });
    });
  });

  describe('generateRandomNumbers', () => {
    test('should generate correct count of numbers', () => {
      const numbers = dataProcessor.generateRandomNumbers(6, 1, 49);
      expect(numbers).toHaveLength(6);
    });

    test('should generate unique numbers', () => {
      const numbers = dataProcessor.generateRandomNumbers(10, 1, 49);
      const uniqueNumbers = new Set(numbers);
      expect(uniqueNumbers.size).toBe(10);
    });

    test('should generate numbers within specified range', () => {
      const numbers = dataProcessor.generateRandomNumbers(6, 10, 20);
      numbers.forEach(num => {
        expect(num).toBeGreaterThanOrEqual(10);
        expect(num).toBeLessThanOrEqual(20);
      });
    });
  });

  describe('loadSampleData', () => {
    test('should load sample data correctly', () => {
      const data = dataProcessor.loadSampleData();
      expect(data).toHaveLength(500);
      expect(dataProcessor.getData()).toHaveLength(500);
    });
  });

  describe('getData and getDataRange', () => {
    beforeEach(() => {
      dataProcessor.loadSampleData();
    });

    test('getData should return all data', () => {
      const data = dataProcessor.getData();
      expect(data).toHaveLength(500);
    });

    test('getDataRange with "all" should return all data', () => {
      const data = dataProcessor.getDataRange('all');
      expect(data).toHaveLength(500);
    });

    test('getDataRange with specific size should return correct slice', () => {
      const data = dataProcessor.getDataRange(50);
      expect(data).toHaveLength(50);
    });

    test('getDataRange should return first N entries', () => {
      const allData = dataProcessor.getData();
      const rangeData = dataProcessor.getDataRange(10);
      expect(rangeData).toEqual(allData.slice(0, 10));
    });
  });

  describe('clearData', () => {
    test('should clear all data', () => {
      dataProcessor.loadSampleData();
      expect(dataProcessor.getData()).toHaveLength(500);
      
      dataProcessor.clearData();
      expect(dataProcessor.getData()).toHaveLength(0);
    });
  });

  describe('searchData', () => {
    beforeEach(() => {
      dataProcessor.loadSampleData();
    });

    test('should return all data when query is empty', () => {
      const results = dataProcessor.searchData('');
      expect(results).toHaveLength(500);
    });

    test('should search by draw number', () => {
      const firstDraw = dataProcessor.getData()[0];
      const results = dataProcessor.searchData(firstDraw.draw.substring(0, 5));
      expect(results.length).toBeGreaterThan(0);
      expect(results.some(d => d.draw === firstDraw.draw)).toBe(true);
    });

    test('should search by date', () => {
      const firstDraw = dataProcessor.getData()[0];
      const results = dataProcessor.searchData(firstDraw.date.substring(0, 7)); // YYYY-MM
      expect(results.length).toBeGreaterThan(0);
    });
  });

  describe('sortData', () => {
    beforeEach(() => {
      dataProcessor.loadSampleData();
    });

    test('should sort in descending order by default', () => {
      const sorted = dataProcessor.sortData();
      for (let i = 0; i < sorted.length - 1; i++) {
        expect(sorted[i].draw >= sorted[i + 1].draw).toBe(true);
      }
    });

    test('should sort in ascending order when specified', () => {
      const sorted = dataProcessor.sortData('asc');
      for (let i = 0; i < sorted.length - 1; i++) {
        expect(sorted[i].draw <= sorted[i + 1].draw).toBe(true);
      }
    });

    test('should not mutate original data', () => {
      const originalFirst = dataProcessor.getData()[0];
      dataProcessor.sortData('asc');
      expect(dataProcessor.getData()[0]).toEqual(originalFirst);
    });
  });

  describe('checkDuplicates', () => {
    beforeEach(() => {
      dataProcessor.lotteryData = [
        { draw: '113000001', date: '2024-01-01', numbers: [1, 2, 3, 4, 5, 6], special: 7 },
        { draw: '113000002', date: '2024-01-04', numbers: [2, 3, 4, 5, 6, 7], special: 8 },
      ];
    });

    test('should detect no duplicates in new data', () => {
      const newData = [
        { draw: '113000003', date: '2024-01-07', numbers: [3, 4, 5, 6, 7, 8], special: 9 },
      ];
      const result = dataProcessor.checkDuplicates(newData);
      
      expect(result.duplicateCount).toBe(0);
      expect(result.newCount).toBe(1);
      expect(result.totalCount).toBe(3);
    });

    test('should detect duplicates in new data', () => {
      const newData = [
        { draw: '113000002', date: '2024-01-04', numbers: [2, 3, 4, 5, 6, 7], special: 8 },
        { draw: '113000003', date: '2024-01-07', numbers: [3, 4, 5, 6, 7, 8], special: 9 },
      ];
      const result = dataProcessor.checkDuplicates(newData);
      
      expect(result.duplicateCount).toBe(1);
      expect(result.newCount).toBe(1);
      expect(result.totalCount).toBe(3);
    });

    test('should merge data correctly', () => {
      const newData = [
        { draw: '113000003', date: '2024-01-07', numbers: [3, 4, 5, 6, 7, 8], special: 9 },
      ];
      const result = dataProcessor.checkDuplicates(newData);
      
      expect(result.mergedData).toHaveLength(3);
      expect(result.mergedData.some(d => d.draw === '113000003')).toBe(true);
    });

    test('should sort merged data in descending order', () => {
      const newData = [
        { draw: '113000000', date: '2023-12-28', numbers: [1, 2, 3, 4, 5, 6], special: 7 },
      ];
      const result = dataProcessor.checkDuplicates(newData);
      
      expect(result.mergedData[0].draw).toBe('113000002');
      expect(result.mergedData[result.mergedData.length - 1].draw).toBe('113000000');
    });
  });
});
