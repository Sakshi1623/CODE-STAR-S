import React from 'react';
import { AppProvider, useApp } from './context/AppContext';
import { Sidebar } from './components/layout/Sidebar';
import { Header } from './components/layout/Header';
import { DashboardScreen } from './components/screens/DashboardScreen';
import { ApiMonitorScreen } from './components/screens/ApiMonitorScreen';
import { SchemaDiffScreen } from './components/screens/SchemaDiffScreen';
import { RecoveryLogsScreen } from './components/screens/RecoveryLogsScreen';
import { EvaluationScreen } from './components/screens/EvaluationScreen';
import { ToolRegistryScreen } from './components/screens/ToolRegistryScreen';
import { SettingsScreen } from './components/screens/SettingsScreen';
import { SplashScreen } from './components/screens/SplashScreen';
import { CheckCircle2 } from 'lucide-react';

const MainLayout: React.FC = () => {
  const { currentTab, showSplash, toastMessage } = useApp();

  const renderActiveScreen = () => {
    switch (currentTab) {
      case 'dashboard':
        return <DashboardScreen />;
      case 'api-monitor':
        return <ApiMonitorScreen />;
      case 'schema-diff':
        return <SchemaDiffScreen />;
      case 'recovery-logs':
        return <RecoveryLogsScreen />;
      case 'evaluation':
        return <EvaluationScreen />;
      case 'tool-registry':
        return <ToolRegistryScreen />;
      case 'settings':
        return <SettingsScreen />;
      default:
        return <DashboardScreen />;
    }
  };

  return (
    <div className="flex h-screen bg-[#0F172A] text-[#F8FAFC] overflow-hidden">
      {/* Left Sidebar */}
      <Sidebar />

      {/* Main View Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header */}
        <Header />

        {/* Dynamic Page Content */}
        <main className="flex-1 overflow-y-auto p-6 md:p-8 bg-[#0F172A]">
          <div className="max-w-7xl mx-auto">
            {renderActiveScreen()}
          </div>
        </main>
      </div>

      {/* Toast Notification Container */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2.5 px-4 py-3 rounded-xl bg-[#1E293B] border border-[#5B8C9E]/50 text-white shadow-2xl animate-fade-in text-xs font-medium">
          <CheckCircle2 className="w-4 h-4 text-[#0D9488]" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Splash Screen Presentation Modal */}
      {showSplash && <SplashScreen />}
    </div>
  );
};

export default function App() {
  return (
    <AppProvider>
      <MainLayout />
    </AppProvider>
  );
}
