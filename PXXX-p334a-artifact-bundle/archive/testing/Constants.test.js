import { LOTTERY_RULES } from '../src/utils/Constants.js';

describe('LOTTERY_RULES Constants', () => {
  test('should have correct name and description', () => {
    expect(LOTTERY_RULES.name).toBe('大樂透');
    expect(LOTTERY_RULES.description).toBe('台灣大樂透彩券遊戲');
  });

  test('should have valid number range', () => {
    expect(LOTTERY_RULES.numberRange.min).toBe(1);
    expect(LOTTERY_RULES.numberRange.max).toBe(49);
    expect(LOTTERY_RULES.numberRange.min).toBeLessThan(LOTTERY_RULES.numberRange.max);
  });

  test('should have correct pick count', () => {
    expect(LOTTERY_RULES.pickCount).toBe(6);
  });

  test('should have correct special count', () => {
    expect(LOTTERY_RULES.specialCount).toBe(1);
  });

  describe('Prize Rules', () => {
    test('should have 8 prize levels', () => {
      expect(Object.keys(LOTTERY_RULES.prizes)).toHaveLength(8);
    });

    test('first prize should not require special number', () => {
      expect(LOTTERY_RULES.prizes.first.specialRequired).toBe(false);
      expect(LOTTERY_RULES.prizes.first.condition).toBe('6 個號碼全中');
    });

    test('second prize should require special number', () => {
      expect(LOTTERY_RULES.prizes.second.specialRequired).toBe(true);
      expect(LOTTERY_RULES.prizes.second.condition).toBe('5 個號碼 + 特別號');
    });

    test('all prizes should have name and condition', () => {
      Object.values(LOTTERY_RULES.prizes).forEach(prize => {
        expect(prize).toHaveProperty('name');
        expect(prize).toHaveProperty('condition');
        expect(prize).toHaveProperty('specialRequired');
      });
    });

    test('special number prizes should be correct', () => {
      const specialPrizes = ['second', 'fourth', 'sixth', 'seventh'];
      specialPrizes.forEach(key => {
        expect(LOTTERY_RULES.prizes[key].specialRequired).toBe(true);
      });
    });

    test('non-special number prizes should be correct', () => {
      const nonSpecialPrizes = ['first', 'third', 'fifth', 'eighth'];
      nonSpecialPrizes.forEach(key => {
        expect(LOTTERY_RULES.prizes[key].specialRequired).toBe(false);
      });
    });
  });
});
