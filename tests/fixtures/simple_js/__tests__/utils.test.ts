import { describe, it, expect } from '@jest/globals';
import { formatDate, calculateTotal, createSlug } from '../src/utils';

describe('utils', () => {
  it('should format date', () => {
    const date = new Date('2024-01-01');
    expect(formatDate(date)).toBe('2024-01-01T00:00:00.000Z');
  });

  test('should calculate total', () => {
    expect(calculateTotal([1, 2, 3])).toBe(6);
  });

  test('should create slug', () => {
    expect(createSlug('Hello World')).toBe('hello-world');
  });
});
