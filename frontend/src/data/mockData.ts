import type { ServiceItem, LiveLog, RecoveryLogItem, ToolItem, AppSettings } from '../types';

export const initialSettings: AppSettings = {
  monitoringInterval: 300,
  maxRetries: 10,
  safeMode: true,
  betaMode: false,
  toolSchema: 's3://driftshield-schemas/prod/v2.4.json',
  mockApiVersion: 'v2',
  controlPlaneSync: true,
  apiKey: 'agy_live_948f20b8e721a9c33e8b01',
};

export const initialServices: ServiceItem[] = [
  {
    id: 'srv-1',
    name: 'User Service',
    health: 'healthy',
    status: 'Monitoring 24/7',
    lastActive: '32 mins ago',
    endpoint: '/api/v1/users',
    method: 'GET',
    latency: '18ms',
    version: 'v2.1',
    successRate: '99.9%',
  },
  {
    id: 'srv-2',
    name: 'Payment Service',
    health: 'drift',
    status: 'Monitoring Drift',
    lastActive: '12 mins ago',
    endpoint: '/api/v2/checkout',
    method: 'POST',
    latency: '64ms',
    version: 'v1.4',
    successRate: '96.2%',
  },
  {
    id: 'srv-3',
    name: 'Payment Service (Legacy)',
    health: 'drift',
    status: 'Monitoring Drift',
    lastActive: '5 mins ago',
    endpoint: '/api/v1/charge',
    method: 'POST',
    latency: '78ms',
    version: 'v1.0',
    successRate: '94.8%',
  },
  {
    id: 'srv-4',
    name: 'Notification Service',
    health: 'healthy',
    status: 'Monitoring 24/7',
    lastActive: '30 mins ago',
    endpoint: '/api/v1/notify',
    method: 'POST',
    latency: '22ms',
    version: 'v2.0',
    successRate: '100%',
  },
  {
    id: 'srv-5',
    name: 'Auth Gateway',
    health: 'healthy',
    status: 'Monitoring 24/7',
    lastActive: '1 min ago',
    endpoint: '/oauth2/token',
    method: 'POST',
    latency: '14ms',
    version: 'v3.2',
    successRate: '99.9%',
  },
  {
    id: 'srv-6',
    name: 'Inventory Sync',
    health: 'error',
    status: 'Schema Mismatch',
    lastActive: '2 mins ago',
    endpoint: '/inventory/items',
    method: 'GET',
    latency: '142ms',
    version: 'v1.9',
    successRate: '88.5%',
  },
];

export const initialLiveLogs: LiveLog[] = [
  {
    id: 'log-1',
    timestamp: '2026-10-16 15:42:01',
    status: 'Healthy',
    service: 'user-service',
    event: 'Incoming Request: GET /api/v1/users/profile',
    details: 'HTTP 200 OK - Payload matches schema baseline 2.1',
    latencyMs: 19,
  },
  {
    id: 'log-2',
    timestamp: '2026-10-16 15:41:48',
    status: 'Drift',
    service: 'payment-service',
    event: 'Schema Drift Detected: missing `currency` field',
    details: 'Interceptor triggered fallback mapping: currency="USD"',
    latencyMs: 44,
  },
  {
    id: 'log-3',
    timestamp: '2026-10-16 15:41:22',
    status: 'Recovered',
    service: 'payment-service',
    event: 'Self-Healing Interceptor Repaired Payload',
    details: 'Coerced `amount` string "49.99" to float64, schema restored',
    latencyMs: 52,
  },
  {
    id: 'log-4',
    timestamp: '2026-10-16 15:40:55',
    status: 'Healthy',
    service: 'notification-service',
    event: 'Event Broadcast: POST /api/v1/notify/email',
    details: 'Payload hash verified against active schema registry',
    latencyMs: 24,
  },
  {
    id: 'log-5',
    timestamp: '2026-10-16 15:40:12',
    status: 'Error',
    service: 'inventory-sync',
    event: 'Type Error: expected array of objects for `stock_units`',
    details: 'Received null. Retrying with safe mode empty set default',
    latencyMs: 142,
  },
  {
    id: 'log-6',
    timestamp: '2026-10-16 15:39:40',
    status: 'Healthy',
    service: 'auth-gateway',
    event: 'Token Verification: POST /oauth2/token',
    details: 'Schema compliance 100% verified',
    latencyMs: 12,
  },
  {
    id: 'log-7',
    timestamp: '2026-10-16 15:39:10',
    status: 'Recovered',
    service: 'user-service',
    event: 'Field Alias Resolved: `userId` mapped to `user_id`',
    details: 'Self-healing interceptor normalized payload before downstream consumption',
    latencyMs: 28,
  },
];

export const initialRecoveryLogs: RecoveryLogItem[] = [
  {
    id: 'rec-1',
    time: '2026-10-16 11:24:20',
    service: 'user-service',
    event: 'Runtime drift agent',
    status: 'Warning',
    details: 'Missing field: user_id -> injected from auth context',
    durationMs: 4.2,
  },
  {
    id: 'rec-2',
    time: '2026-10-16 11:24:18',
    service: 'user-service',
    event: 'Field type mutation',
    status: 'Recovered',
    details: 'Missing field: user_id -> synthesized fallback identifier',
    durationMs: 3.8,
  },
  {
    id: 'rec-3',
    time: '2026-10-16 11:24:12',
    service: 'user-service',
    event: 'Parameter mismatch',
    status: 'Success',
    details: 'Renamed parameter: "client_ref" to "reference_id"',
    durationMs: 2.1,
  },
  {
    id: 'rec-4',
    time: '2026-10-16 11:24:05',
    service: 'payment-service',
    event: 'Type coercion interceptor',
    status: 'Success',
    details: 'Converted string representation to decimal currency',
    durationMs: 1.9,
  },
  {
    id: 'rec-5',
    time: '2026-10-16 11:23:45',
    service: 'payment-service',
    event: 'Missing required field',
    status: 'Error',
    details: 'Missing billing_address - escalated to schema quarantine',
    durationMs: 18.4,
  },
  {
    id: 'rec-6',
    time: '2026-10-16 11:23:20',
    service: 'user-service',
    event: 'Runtime drift agent',
    status: 'Recovered',
    details: 'Missing field: user_id -> auto-recovered via token cache',
    durationMs: 5.1,
  },
  {
    id: 'rec-7',
    time: '2026-10-16 11:22:55',
    service: 'notification-service',
    event: 'Payload envelope drift',
    status: 'Success',
    details: 'Unnested payload wrapper { data: {...} } -> target schema',
    durationMs: 2.7,
  },
  {
    id: 'rec-8',
    time: '2026-10-16 11:22:10',
    service: 'auth-gateway',
    event: 'Timestamp format change',
    status: 'Recovered',
    details: 'Parsed epoch millisecond to ISO 8601 string format',
    durationMs: 3.4,
  },
  {
    id: 'rec-9',
    time: '2026-10-16 11:21:40',
    service: 'inventory-sync',
    event: 'Null pointer avoidance',
    status: 'Warning',
    details: 'Substituted empty array for null stock list',
    durationMs: 4.8,
  },
  {
    id: 'rec-10',
    time: '2026-10-16 11:20:15',
    service: 'user-service',
    event: 'Runtime drift agent',
    status: 'Success',
    details: 'Restored schema backward compatibility for v1 clients',
    durationMs: 3.0,
  },
];

export const initialTools: ToolItem[] = [
  {
    id: 'tool-1',
    name: 'User Service',
    description: 'Core identity, profile metadata, and tenant security registry.',
    method: 'GET',
    endpoint: '/api/v2/users/profile',
    health: 'healthy',
    statusText: 'Healthy',
    requests24h: '48.2k',
    latency: '18ms',
    version: 'v2.1',
    tags: ['Core', 'Identity'],
  },
  {
    id: 'tool-2',
    name: 'Payment Service',
    description: 'Stripe & crypto billing gateway with runtime drift interception.',
    method: 'POST',
    endpoint: '/api/v1/checkout/intent',
    health: 'drift',
    statusText: 'Drift Detected',
    requests24h: '19.4k',
    latency: '64ms',
    version: 'v1.4',
    tags: ['FinTech', 'High-Sec'],
  },
  {
    id: 'tool-3',
    name: 'Notification Service',
    description: 'Multi-channel dispatch (Email, SMS, Webhooks) with schema cache.',
    method: 'POST',
    endpoint: '/api/v1/notify/dispatch',
    health: 'healthy',
    statusText: 'Healthy',
    requests24h: '112.5k',
    latency: '22ms',
    version: 'v3.0',
    tags: ['Messaging'],
  },
  {
    id: 'tool-4',
    name: 'Auth Gateway',
    description: 'OAuth2/OIDC token broker and JWKS validator.',
    method: 'POST',
    endpoint: '/oauth2/v1/verify',
    health: 'healthy',
    statusText: 'Healthy',
    requests24h: '320.1k',
    latency: '11ms',
    version: 'v3.2',
    tags: ['Security', 'Zero-Trust'],
  },
  {
    id: 'tool-5',
    name: 'Inventory Sync',
    description: 'Warehouse inventory real-time webhook connector.',
    method: 'GET',
    endpoint: '/inventory/v2/stock',
    health: 'error',
    statusText: 'Schema Error',
    requests24h: '8.4k',
    latency: '142ms',
    version: 'v1.9',
    tags: ['Logistics'],
  },
  {
    id: 'tool-6',
    name: 'Tool Registry Gateway',
    description: 'Master catalog for self-healing AI agent tools and MCP bindings.',
    method: 'GET',
    endpoint: '/registry/tools/catalog',
    health: 'healthy',
    statusText: 'Healthy',
    requests24h: '75.8k',
    latency: '15ms',
    version: 'v2.0',
    tags: ['AI Agent', 'Core'],
  },
];

export const compatibilityChartData = [
  { date: '10/01', compatibility: 96, baseline: 92 },
  { date: '10/03', compatibility: 98, baseline: 90 },
  { date: '10/05', compatibility: 95, baseline: 88 },
  { date: '10/08', compatibility: 91, baseline: 82 },
  { date: '10/10', compatibility: 97, baseline: 79 },
  { date: '10/12', compatibility: 94, baseline: 74 },
  { date: '10/15', compatibility: 99, baseline: 70 },
  { date: '10/18', compatibility: 96, baseline: 65 },
  { date: '10/20', compatibility: 98, baseline: 61 },
  { date: '10/22', compatibility: 97, baseline: 58 },
  { date: '10/24', compatibility: 99.4, baseline: 52 },
];

export const failureClassificationData = [
  { name: 'Schema Disqualification', value: 55, color: '#5B8C9E' },
  { name: 'Deprecated', value: 10, color: '#F59E0B' },
  { name: 'Library Disqualification', value: 7, color: '#38BDF8' },
  { name: 'Serialization', value: 2, color: '#0D9488' },
  { name: 'Others', value: 1, color: '#EF4444' },
];

export const recentEventsData = [
  {
    id: 'evt-1',
    title: 'user-service detected Drift on /v1/user/profile',
    time: '5 minutes ago',
    type: 'drift',
  },
  {
    id: 'evt-2',
    title: 'payment-service recovered transaction_id schema',
    time: '12 minutes ago',
    type: 'recovered',
  },
  {
    id: 'evt-3',
    title: 'notification-service payload normalized successfully',
    time: '18 minutes ago',
    type: 'healthy',
  },
  {
    id: 'evt-4',
    title: 'inventory-service reported unexpected null schema',
    time: '30 minutes ago',
    type: 'error',
  },
  {
    id: 'evt-5',
    title: 'auth-gateway issued new self-healing interceptor rule',
    time: '1 hour ago',
    type: 'healthy',
  },
];

export const evaluationComparisonData = [
  { metric: 'Task Success Rate', baseline: 62, selfHealing: 98 },
  { metric: 'Schema Resilience', baseline: 45, selfHealing: 94 },
  { metric: 'Zero-Touch Adaptation', baseline: 20, selfHealing: 90 },
  { metric: 'Error Tolerance', baseline: 38, selfHealing: 92 },
  { metric: 'Recovery Efficiency', baseline: 15, selfHealing: 88 },
];

export const performanceOverTimeData = [
  { time: '00:00', baseline: 92, selfHealing: 96 },
  { time: '02:00', baseline: 84, selfHealing: 97 },
  { time: '04:00', baseline: 76, selfHealing: 98 },
  { time: '06:00', baseline: 65, selfHealing: 98 },
  { time: '08:00', baseline: 71, selfHealing: 99 },
  { time: '10:00', baseline: 58, selfHealing: 97 },
  { time: '12:00', baseline: 52, selfHealing: 99.2 },
];

export const schemaV1Baseline = `{
  "$schema": "https://json-schema.org/v1/schema",
  "title": "UserProfile",
  "type": "object",
  "required": [
    "user_id",
    "username",
    "email",
    "created_at",
    "status"
  ],
  "properties": {
    "user_id": {
      "type": "string",
      "format": "uuid"
    },
    "username": {
      "type": "string",
      "minLength": 3
    },
    "email": {
      "type": "string",
      "format": "email"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "status": {
      "type": "string",
      "enum": ["active", "suspended", "pending"]
    }
  }
}`;

export const schemaV2Drifted = `{
  "$schema": "https://json-schema.org/v2/schema",
  "title": "UserProfile",
  "type": "object",
  "required": [
    "userId",
    "username",
    "email",
    "kyc_status",
    "status"
  ],
  "properties": {
    "userId": {
      "type": "string",
      "description": "Renamed from user_id"
    },
    "username": {
      "type": "string",
      "minLength": 3
    },
    "email": {
      "type": "string",
      "format": "email"
    },
    "kyc_status": {
      "type": "string",
      "enum": ["verified", "pending", "unverified"]
    },
    "status": {
      "type": "string",
      "enum": ["active", "suspended", "pending"]
    },
    "metadata": {
      "type": "object",
      "properties": {
        "tier": { "type": "string" },
        "last_login_epoch": { "type": "number" }
      }
    }
  }
}`;
