import { ConfigManager } from './utils';

export class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  async fetchData(endpoint: string): Promise<unknown> {
    const response = await fetch(`${this.baseUrl}/${endpoint}`);
    return response.json();
  }
}

export const buildUrl = (base: string, path: string): string => {
  return `${base}/${path}`;
};

export default class DefaultExport {
  name = 'default';
}
