import React, { createContext, useContext, useState, useEffect } from 'react';
import type { 
  NavigationTab, 
  ServiceItem, 
  LiveLog, 
  RecoveryLogItem, 
  ToolItem, 
  AppSettings 
} from '../types';
import { 
  initialServices, 
  initialLiveLogs, 
  initialRecoveryLogs, 
  initialTools, 
  initialSettings 
} from '../data/mockData';

interface AppContextType {
  currentTab: NavigationTab;
  setCurrentTab: (tab: NavigationTab) => void;
  showSplash: boolean;
  setShowSplash: (show: boolean) => void;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  services: ServiceItem[];
  setServices: React.Dispatch<React.SetStateAction<ServiceItem[]>>;
  liveLogs: LiveLog[];
  recoveryLogs: RecoveryLogItem[];
  tools: ToolItem[];
  settings: AppSettings;
  updateSettings: (newSettings: Partial<AppSettings>) => void;
  patchApplied: boolean;
  applyPatch: () => void;
  rollbackPatch: () => void;
  isStreaming: boolean;
  setIsStreaming: (stream: boolean) => void;
  addService: (service: Partial<ServiceItem>) => void;
  addTool: (tool: Partial<ToolItem>) => void;
  addRecoveryLog: (log: Partial<RecoveryLogItem>) => void;
  toastMessage: string | null;
  showToast: (msg: string) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentTab, setCurrentTab] = useState<NavigationTab>('dashboard');
  const [showSplash, setShowSplash] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [services, setServices] = useState<ServiceItem[]>(initialServices);
  const [liveLogs, setLiveLogs] = useState<LiveLog[]>(initialLiveLogs);
  const [recoveryLogs, setRecoveryLogs] = useState<RecoveryLogItem[]>(initialRecoveryLogs);
  const [tools, setTools] = useState<ToolItem[]>(initialTools);
  const [settings, setSettings] = useState<AppSettings>(initialSettings);
  const [patchApplied, setPatchApplied] = useState<boolean>(false);
  const [isStreaming, setIsStreaming] = useState<boolean>(true);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage(null);
    }, 3500);
  };

  const updateSettings = (newSettings: Partial<AppSettings>) => {
    setSettings((prev) => ({ ...prev, ...newSettings }));
    showToast('Settings saved successfully');
  };

  const applyPatch = () => {
    setPatchApplied(true);
    // Add recovery log
    const newLog: RecoveryLogItem = {
      id: `rec-${Date.now()}`,
      time: new Date().toISOString().replace('T', ' ').substring(0, 19),
      service: 'user-service',
      event: 'Auto-Synthesized Schema Patch Applied',
      status: 'Success',
      details: 'Patched alias: userId -> user_id, injected default kyc_status="verified"',
      durationMs: 1.8,
    };
    setRecoveryLogs((prev) => [newLog, ...prev]);
    showToast('Schema Patch Applied! Interceptor active & self-healing enabled.');
  };

  const rollbackPatch = () => {
    setPatchApplied(false);
    showToast('Schema patch rolled back to baseline.');
  };

  const addService = (service: Partial<ServiceItem>) => {
    const newSrv: ServiceItem = {
      id: `srv-${Date.now()}`,
      name: service.name || 'New Microservice',
      health: 'healthy',
      status: 'Monitoring 24/7',
      lastActive: 'Just now',
      endpoint: service.endpoint || '/api/v1/custom',
      method: service.method || 'GET',
      latency: '20ms',
      version: 'v1.0',
      successRate: '100%',
    };
    setServices((prev) => [newSrv, ...prev]);
    showToast(`Service "${newSrv.name}" registered successfully.`);
  };

  const addTool = (tool: Partial<ToolItem>) => {
    const newTool: ToolItem = {
      id: `tool-${Date.now()}`,
      name: tool.name || 'Custom Agent Tool',
      description: tool.description || 'Self-healing tool registry node.',
      method: tool.method || 'POST',
      endpoint: tool.endpoint || '/api/tools/v1',
      health: 'healthy',
      statusText: 'Healthy',
      requests24h: '1.2k',
      latency: '15ms',
      version: 'v1.0',
      tags: ['Custom', 'AI Agent'],
    };
    setTools((prev) => [newTool, ...prev]);
    showToast(`Tool "${newTool.name}" added to registry.`);
  };

  const addRecoveryLog = (log: Partial<RecoveryLogItem>) => {
    const newLog: RecoveryLogItem = {
      id: `rec-${Date.now()}`,
      time: new Date().toISOString().replace('T', ' ').substring(0, 19),
      service: log.service || 'runtime-interceptor',
      event: log.event || 'Manual Interceptor Event',
      status: log.status || 'Success',
      details: log.details || 'Schema resolved without service interruption.',
      durationMs: 2.4,
    };
    setRecoveryLogs((prev) => [newLog, ...prev]);
    showToast('New interceptor log registered.');
  };

  // Background live traffic simulation
  useEffect(() => {
    if (!isStreaming) return;
    const interval = setInterval(() => {
      const servicesList = ['user-service', 'payment-service', 'auth-gateway', 'notification-service'];
      const randomService = servicesList[Math.floor(Math.random() * servicesList.length)];
      const statuses: ('Healthy' | 'Drift' | 'Recovered')[] = ['Healthy', 'Healthy', 'Recovered', 'Drift'];
      const status = statuses[Math.floor(Math.random() * statuses.length)];
      
      let event = `Handled request on /api/v1/${randomService.split('-')[0]}`;
      let details = 'Schema contract matched baseline specifications.';
      if (status === 'Drift') {
        event = `Runtime Drift in ${randomService}: parameter mismatch`;
        details = 'Interception engine queued self-healing reconciliation.';
      } else if (status === 'Recovered') {
        event = `Zero-Touch Self-Healing restored response contract`;
        details = 'Replaced deprecated attribute with runtime alias mapping.';
      }

      const newLog: LiveLog = {
        id: `live-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
        timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
        status,
        service: randomService,
        event,
        details,
        latencyMs: Math.floor(Math.random() * 45) + 12,
      };

      setLiveLogs((prev) => [newLog, ...prev.slice(0, 49)]);
    }, 6000);

    return () => clearInterval(interval);
  }, [isStreaming]);

  return (
    <AppContext.Provider
      value={{
        currentTab,
        setCurrentTab,
        showSplash,
        setShowSplash,
        searchQuery,
        setSearchQuery,
        services,
        setServices,
        liveLogs,
        recoveryLogs,
        tools,
        settings,
        updateSettings,
        patchApplied,
        applyPatch,
        rollbackPatch,
        isStreaming,
        setIsStreaming,
        addService,
        addTool,
        addRecoveryLog,
        toastMessage,
        showToast,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};
