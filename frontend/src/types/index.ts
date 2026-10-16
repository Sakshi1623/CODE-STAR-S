export type NavigationTab = 
  | 'dashboard' 
  | 'api-monitor' 
  | 'schema-diff' 
  | 'recovery-logs' 
  | 'evaluation' 
  | 'tool-registry' 
  | 'settings';

export type HealthStatus = 'healthy' | 'drift' | 'error' | 'recovering';

export interface ServiceItem {
  id: string;
  name: string;
  health: HealthStatus;
  status: string;
  lastActive: string;
  endpoint: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  latency: string;
  version: string;
  successRate: string;
}

export interface LiveLog {
  id: string;
  timestamp: string;
  status: 'Healthy' | 'Drift' | 'Recovered' | 'Error';
  service: string;
  event: string;
  details: string;
  latencyMs: number;
}

export interface RecoveryLogItem {
  id: string;
  time: string;
  service: string;
  event: string;
  status: 'Success' | 'Warning' | 'Error' | 'Recovered';
  details: string;
  durationMs: number;
  payloadDiff?: string;
}

export interface ToolItem {
  id: string;
  name: string;
  description: string;
  method: 'GET' | 'POST' | 'PUT';
  endpoint: string;
  health: HealthStatus;
  statusText: string;
  requests24h: string;
  latency: string;
  version: string;
  tags: string[];
}

export interface AppSettings {
  monitoringInterval: number;
  maxRetries: number;
  safeMode: boolean;
  betaMode: boolean;
  toolSchema: string;
  mockApiVersion: 'v1' | 'v2';
  controlPlaneSync: boolean;
  apiKey: string;
}
