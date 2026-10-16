import React, { useState } from 'react';
import { 
  Save, 
  ShieldCheck, 
  Zap, 
  Sliders, 
  Server, 
  ToggleLeft, 
  ToggleRight, 
  Sparkles 
} from 'lucide-react';
import { useApp } from '../../context/AppContext';

export const SettingsScreen: React.FC = () => {
  const { settings, updateSettings, showToast } = useApp();

  const [interval, setInterval] = useState(settings.monitoringInterval);
  const [retries, setRetries] = useState(settings.maxRetries);
  const [safeMode, setSafeMode] = useState(settings.safeMode);
  const [betaMode, setBetaMode] = useState(settings.betaMode);
  const [toolSchema, setToolSchema] = useState(settings.toolSchema);
  const [mockVersion, setMockVersion] = useState<'v1' | 'v2'>(settings.mockApiVersion);
  const [apiKey, setApiKey] = useState(settings.apiKey);

  const handleSave = () => {
    updateSettings({
      monitoringInterval: Number(interval),
      maxRetries: Number(retries),
      safeMode,
      betaMode,
      toolSchema,
      mockApiVersion: mockVersion,
      apiKey,
    });
  };

  const handleTestConnection = () => {
    showToast('Control Plane API handshake successful: Latency 14ms (Healthy)');
  };

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
            Settings
            <span className="text-xs px-2 py-0.5 rounded-full bg-[#5B8C9E]/15 text-[#5B8C9E] font-medium border border-[#5B8C9E]/30">
              System Configuration
            </span>
          </h1>
          <p className="text-sm text-[#94A3B8] mt-0.5">
            Configure runtime monitoring intervals, safe mode fallbacks, and control plane integration hooks
          </p>
        </div>

        <button
          onClick={handleSave}
          className="px-4 py-2 rounded-lg bg-[#5B8C9E] hover:bg-[#4E7A8B] text-white text-xs font-semibold flex items-center gap-1.5 transition-all shadow-sm"
        >
          <Save className="w-3.5 h-3.5" />
          <span>Save Changes</span>
        </button>
      </div>

      {/* General Settings Panel matching Card 8 */}
      <div className="bg-[#1E293B] border border-[#334155]/60 rounded-xl p-6 shadow-sm space-y-6">
        <div className="flex items-center gap-2 pb-3 border-b border-[#334155]/60">
          <Sliders className="w-4 h-4 text-[#5B8C9E]" />
          <h2 className="text-sm font-semibold text-white">General Settings</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {/* Numeric Interval Input */}
          <div>
            <label className="block text-xs font-medium text-[#94A3B8] mb-1.5">
              Monitoring Interval (seconds)
            </label>
            <input
              type="number"
              min={10}
              max={3600}
              value={interval}
              onChange={(e) => setInterval(Number(e.target.value))}
              className="w-full bg-[#0F172A] border border-[#334155] rounded-lg px-3.5 py-2 text-sm text-white focus:outline-none focus:border-[#5B8C9E] font-mono"
            />
            <p className="text-[11px] text-[#64748B] mt-1">
              Frequency of automated background schema introspection
            </p>
          </div>

          {/* Max Retries Numeric Input */}
          <div>
            <label className="block text-xs font-medium text-[#94A3B8] mb-1.5">
              Max Recovery Retries
            </label>
            <input
              type="number"
              min={1}
              max={50}
              value={retries}
              onChange={(e) => setRetries(Number(e.target.value))}
              className="w-full bg-[#0F172A] border border-[#334155] rounded-lg px-3.5 py-2 text-sm text-white focus:outline-none focus:border-[#5B8C9E] font-mono"
            />
            <p className="text-[11px] text-[#64748B] mt-1">
              Maximum self-healing attempts before triggering quarantine escalation
            </p>
          </div>
        </div>

        {/* Safe Mode Toggle */}
        <div className="flex items-center justify-between p-4 bg-[#0F172A] border border-[#334155] rounded-xl">
          <div>
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-[#0D9488]" />
              <span className="text-sm font-semibold text-white">Safe Mode</span>
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#0D9488]/20 text-[#0D9488] font-semibold">
                Recommended
              </span>
            </div>
            <p className="text-xs text-[#94A3B8] mt-1">
              Automatically inject synthesized fallback types when unrecoverable schema fields are omitted
            </p>
          </div>
          <button
            onClick={() => setSafeMode(!safeMode)}
            className="text-2xl text-[#5B8C9E] focus:outline-none"
          >
            {safeMode ? (
              <ToggleRight className="w-9 h-9 text-[#0D9488]" />
            ) : (
              <ToggleLeft className="w-9 h-9 text-[#64748B]" />
            )}
          </button>
        </div>

        {/* Beta Mode & Schema Registry */}
        <div className="space-y-4 pt-2">
          <div className="flex items-center justify-between p-4 bg-[#0F172A] border border-[#334155] rounded-xl">
            <div>
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-[#F59E0B]" />
                <span className="text-sm font-semibold text-white">Beta Mode: Neural Interceptor</span>
              </div>
              <p className="text-xs text-[#94A3B8] mt-1">
                Enable LLM-guided dynamic schema rewriting for multi-modal payloads
              </p>
            </div>
            <button
              onClick={() => setBetaMode(!betaMode)}
              className="text-2xl text-[#5B8C9E] focus:outline-none"
            >
              {betaMode ? (
                <ToggleRight className="w-9 h-9 text-[#5B8C9E]" />
              ) : (
                <ToggleLeft className="w-9 h-9 text-[#64748B]" />
              )}
            </button>
          </div>

          <div>
            <label className="block text-xs font-medium text-[#94A3B8] mb-1.5">
              Remote Tool Schema URI
            </label>
            <input
              type="text"
              value={toolSchema}
              onChange={(e) => setToolSchema(e.target.value)}
              className="w-full bg-[#0F172A] border border-[#334155] rounded-lg px-3.5 py-2 text-xs font-mono text-white focus:outline-none focus:border-[#5B8C9E]"
            />
          </div>
        </div>
      </div>

      {/* Control Plane & Gateway Integrations Panel */}
      <div className="bg-[#1E293B] border border-[#334155]/60 rounded-xl p-6 shadow-sm space-y-5">
        <div className="flex items-center gap-2 pb-3 border-b border-[#334155]/60">
          <Server className="w-4 h-4 text-[#5B8C9E]" />
          <h2 className="text-sm font-semibold text-white">Gateway & Agent Integrations</h2>
        </div>

        <p className="text-xs text-[#94A3B8]">
          Connect DriftShield directly to security control planes, MCP agent servers, and orchestration endpoints.
        </p>

        <div>
          <label className="block text-xs font-medium text-[#94A3B8] mb-1.5">
            Security Gateway API Key
          </label>
          <div className="flex items-center gap-2">
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="flex-1 bg-[#0F172A] border border-[#334155] rounded-lg px-3.5 py-2 text-xs font-mono text-white focus:outline-none focus:border-[#5B8C9E]"
            />
            <button
              onClick={handleTestConnection}
              className="px-3.5 py-2 rounded-lg bg-[#0F172A] hover:bg-[#283548] border border-[#334155] text-xs font-medium text-[#94A3B8] hover:text-white transition-colors whitespace-nowrap"
            >
              Test Connection
            </button>
          </div>
        </div>
      </div>

      {/* Mock API Version Control matching Card 8 */}
      <div className="bg-[#1E293B] border border-[#334155]/60 rounded-xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-[#334155]/60">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-[#F59E0B]" />
            <h2 className="text-sm font-semibold text-white">Mock API Version Control</h2>
          </div>
          <span className="text-xs text-[#94A3B8]">Interactive Simulation</span>
        </div>

        <p className="text-xs text-[#94A3B8]">
          Switch runtime traffic between Version 1 (Compliant Baseline) and Version 2 (Injected Runtime Schema Drift).
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div
            onClick={() => {
              setMockVersion('v1');
              updateSettings({ mockApiVersion: 'v1' });
            }}
            className={`cursor-pointer p-4 rounded-xl border transition-all ${
              mockVersion === 'v1'
                ? 'bg-[#0F172A] border-[#0D9488] shadow-sm'
                : 'bg-[#0F172A]/40 border-[#334155] hover:border-[#64748B]'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-bold text-white text-sm">Version 1 (Baseline)</span>
              <span className={`w-3 h-3 rounded-full border ${
                mockVersion === 'v1' ? 'bg-[#0D9488] border-[#0D9488]' : 'border-[#64748B]'
              }`}></span>
            </div>
            <p className="text-xs text-[#94A3B8]">
              Standard compliant contracts without schema mutation. 100% baseline compatibility.
            </p>
          </div>

          <div
            onClick={() => {
              setMockVersion('v2');
              updateSettings({ mockApiVersion: 'v2' });
            }}
            className={`cursor-pointer p-4 rounded-xl border transition-all ${
              mockVersion === 'v2'
                ? 'bg-[#0F172A] border-[#F59E0B] shadow-sm'
                : 'bg-[#0F172A]/40 border-[#334155] hover:border-[#64748B]'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-bold text-white text-sm">Version 2 (Runtime Drift)</span>
              <span className={`w-3 h-3 rounded-full border ${
                mockVersion === 'v2' ? 'bg-[#F59E0B] border-[#F59E0B]' : 'border-[#64748B]'
              }`}></span>
            </div>
            <p className="text-xs text-[#94A3B8]">
              Simulates breaking schema changes: renamed fields, altered enums, omitted timestamps.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
