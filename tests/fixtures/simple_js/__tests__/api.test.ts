import { describe, it, expect } from '@jest/globals';
import { buildUrl } from '../src/api';

describe('api', () => {
  test('should build url', () => {
    expect(buildUrl('http://example.com', 'users')).toBe('http://example.com/users');
  });
});
