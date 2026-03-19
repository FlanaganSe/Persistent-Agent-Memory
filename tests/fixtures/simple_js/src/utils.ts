import { readFile } from 'fs/promises';

export class ConfigManager {
  private config: Map<string, string>;

  constructor() {
    this.config = new Map();
  }

  getValue(key: string): string | undefined {
    return this.config.get(key);
  }
}

export const formatDate = (date: Date): string => {
  return date.toISOString();
};

export const parseNumber = (input: string): number => {
  return parseInt(input, 10);
};

const validateInput = (value: string): boolean => {
  return value.length > 0;
};

export function calculateTotal(items: number[]): number {
  return items.reduce((sum, item) => sum + item, 0);
}

export function createSlug(title: string): string {
  return title.toLowerCase().replace(/\s+/g, '-');
}
