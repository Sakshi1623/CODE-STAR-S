import React, { useState } from 'react';
import { 
  Activity, 
  Plus, 
  Play, 
  Pause, 
  AlertTriangle, 
  XCircle
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import type { LiveLog } from '../../types';

export const ApiMonitorScreen: React.FC = () => {
  const { 
    services, 
    liveLogs, 
    isStreaming, 
    setIsStreaming, 
    addService, 
    setCurrentTab,
    showToast 
  } = useApp();

  const [serviceFilter, setServiceFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [newServiceName, setNewServiceName] = useState('');
  const [newServiceEndpoint, setNewServiceEndpoint] = useState('');
  const [newServiceMethod, setNewServiceMethod] = useState<'GET' | 'POST'>('POST');

  const filteredLogs = liveLogs.filter((log) => {
    const matchesService = serviceFilter === 'all' || log.service.includes(serviceFilter);
    const matchesStatus = statusFilter === 'all' || log.status.toLowerCase() === statusFilter.toLowerCase();
    return matchesService && matchesStatus;
  });

  const handleAddServiceSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newServiceName.trim()) return;
    addService({
      name: newServiceName,
      endpoint: newServiceEndpoint || '/api/v1/custom',
      method: newServiceMethod,
    });
    setNewServiceName('');
    setNewServiceEndpoint('');
    setShowAddModal(false);
  };

  const getHealthBadge = (health: string) => {
    switch (health) {
      case 'healthy':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-[#0D9488]/15 text-[#0D9488] border border-[#0D9488]/30">
            <span className="w-1.5 h-1.5 rounded-full bg-[#0D9488] animate-pulse"></span>
            Healthy
          </span>
        );
      case 'drift':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-[#F59E0B]/15 text-[#F59E0B] border border-[#F59E0B]/30">
            <AlertTriangle className="w-3 h-3" />
            Monitoring Drift
          </span>
        );
      case 'error':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-[#EF4444]/15 text-[#EF4444] border border-[#EF4444]/30">
            <XCircle className="w-3 h-3" />
            Schema Error
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-[#64748B]/15 text-[#94A3B8]">
            Unknown
          </span>
        );
    }
  };

  const getLogStatusBadge = (status: LiveLog['status']) => {
    switch (status) {
      case 'Healthy':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-[#0D9488]/20 text-[#0D9488] border border-[#0D9488]/40">
            Healthy
          </span>
        );
      case 'Drift':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-[#F59E0B]/20 text-[#F59E0B] border border-[#F59E0B]/40">
            Drift Detected
          </span>
        );
      case 'Recovered':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-[#5B8C9E]/20 text-[#5B8C9E] border border-[#5B8C9E]/40">
            Recovered
          </span>
        );
      case 'Error':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-[#EF4444]/20 text-[#EF4444] border border-[#EF4444]/40">
            Error
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
            API Monitor
            <span className="text-xs px-2 py-0.5 rounded-full bg-[#0D9488]/15 text-[#0D9488] font-medium border border-[#0D9488]/30">
              Live Interception
            </span>
          </h1>
          <p className="text-sm text-[#94A3B8] mt-0.5">
            Active service health contracts, latency telemetry, and incoming traffic log stream
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowAddModal(true)}
            className="px-3.5 py-2 rounded-lg bg-[#5B8C9E] hover:bg-[#4E7A8B] text-white text-xs font-semibold flex items-center gap-2 transition-all shadow-sm"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Service</span>
          </button>
        </div>
      </div>

      {/* Services Table Card */}
      <div className="bg-[#1E293B] border border-[#334155]/60 rounded-xl overflow-hidden shadow-sm">
        <div className="px-5 py-4 border-b border-[#334155]/60 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-[#5B8C9E]" />
            <h2 className="text-sm font-semibold text-white">Monitored Services ({services.length})</h2>
          </div>
          <span className="text-xs text-[#94A3B8]">Continuous Runtime Verification</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="bg-[#0F172A]/70 text-[#94A3B8] font-semibold border-b border-[#334155]/60 uppercase tracking-wider text-[11px]">
                <th className="px-5 py-3.5">Service</th>
                <th className="px-4 py-3.5">Health</th>
                <th className="px-4 py-3.5">Status</th>
                <th className="px-4 py-3.5">Endpoint & Method</th>
                <th className="px-4 py-3.5">Latency</th>
                <th className="px-4 py-3.5">Last Sync</th>
                <th className="px-5 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#334155]/40 text-[#F8FAFC]">
              {services.map((srv) => (
                <tr 
                  key={srv.id} 
                  className="hover:bg-[#0F172A]/40 transition-colors group"
                >
                  <td className="px-5 py-3.5">
                    <div className="font-semibold text-white group-hover:text-[#5B8C9E] transition-colors flex items-center gap-2">
                      {srv.name}
                      <span className="text-[10px] text-[#64748B] font-mono">{srv.version}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3.5">
                    {getHealthBadge(srv.health)}
                  </td>
                  <td className="px-4 py-3.5 text-[#94A3B8]">
                    {srv.status}
                  </td>
                  <td className="px-4 py-3.5">
                    <div className="flex items-center gap-2 font-mono text-[11px]">
                      <span className={`px-1.5 py-0.5 rounded font-bold text-[10px] ${
                        srv.method === 'GET' 
                          ? 'bg-[#38BDF8]/15 text-[#38BDF8]' 
                          : 'bg-[#5B8C9E]/20 text-[#5B8C9E]'
                      }`}>
                        {srv.method}
                      </span>
                      <span className="text-[#94A3B8] truncate max-w-[140px]">{srv.endpoint}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3.5 font-mono text-[#94A3B8]">
                    {srv.latency}
                  </td>
                  <td className="px-4 py-3.5 text-[#64748B]">
                    {srv.lastActive}
                  </td>
                  <td className="px-5 py-3.5 text-right">
                    <button
                      onClick={() => {
                        if (srv.health === 'drift') {
                          setCurrentTab('schema-diff');
                        } else {
                          showToast(`Checking live telemetry for ${srv.name}...`);
                        }
                      }}
                      className="px-2.5 py-1 rounded bg-[#0F172A] hover:bg-[#334155] border border-[#334155] text-[11px] text-[#94A3B8] hover:text-white transition-colors"
                    >
                      {srv.health === 'drift' ? 'Inspect Drift' : 'Inspect'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Live Logs Card */}
      <div className="bg-[#1E293B] border border-[#334155]/60 rounded-xl overflow-hidden shadow-sm">
        {/* Sub-header controls */}
        <div className="px-5 py-4 border-b border-[#334155]/60 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-semibold text-white">Live Logs</h2>
            <span className="text-xs px-2 py-0.5 rounded bg-[#0F172A] text-[#5B8C9E] border border-[#5B8C9E]/30 font-mono">
              API Monitor 1
            </span>
            <div className="flex items-center gap-1.5 text-xs text-[#0D9488]">
              <span className={`w-2 h-2 rounded-full bg-[#0D9488] ${isStreaming ? 'animate-pulse' : ''}`}></span>
              <span>{isStreaming ? 'Live Streaming' : 'Stream Paused'}</span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs">
            {/* Filter by Status */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-[#0F172A] border border-[#334155] rounded-lg px-2.5 py-1.5 text-white focus:outline-none focus:border-[#5B8C9E]"
            >
              <option value="all">All Statuses</option>
              <option value="healthy">Healthy</option>
              <option value="drift">Drift Detected</option>
              <option value="recovered">Recovered</option>
              <option value="error">Error</option>
            </select>

            {/* Play/Pause Button */}
            <button
              onClick={() => setIsStreaming(!isStreaming)}
              className="px-3 py-1.5 rounded-lg bg-[#0F172A] border border-[#334155] hover:border-[#5B8C9E] text-[#94A3B8] hover:text-white flex items-center gap-1.5 transition-colors"
            >
              {isStreaming ? (
                <>
                  <Pause className="w-3.5 h-3.5 text-[#F59E0B]" />
                  <span>Pause</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 text-[#0D9488]" />
                  <span>Resume</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Live Logs Table */}
        <div className="overflow-x-auto max-h-[420px] overflow-y-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="sticky top-0 bg-[#0F172A] z-10">
              <tr className="text-[#94A3B8] font-semibold border-b border-[#334155] uppercase text-[11px]">
                <th className="px-5 py-3">Time/Date</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Service</th>
                <th className="px-4 py-3">Event / Route Details</th>
                <th className="px-5 py-3 text-right">Latency</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#334155]/40 text-[#F8FAFC]">
              {filteredLogs.map((log) => (
                <tr key={log.id} className="hover:bg-[#0F172A]/50 transition-colors">
                  <td className="px-5 py-2.5 text-[#64748B] whitespace-nowrap">
                    {log.timestamp}
                  </td>
                  <td className="px-4 py-2.5 whitespace-nowrap">
                    {getLogStatusBadge(log.status)}
                  </td>
                  <td className="px-4 py-2.5 text-[#5B8C9E] font-medium whitespace-nowrap">
                    {log.service}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="font-sans font-medium text-white">{log.event}</div>
                    <div className="font-mono text-[11px] text-[#94A3B8] truncate max-w-xl">
                      {log.details}
                    </div>
                  </td>
                  <td className="px-5 py-2.5 text-right text-[#94A3B8] whitespace-nowrap">
                    {log.latencyMs}ms
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add Service Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-[#1E293B] border border-[#334155] rounded-xl w-full max-w-md p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-white mb-1">Register New Microservice</h3>
            <p className="text-xs text-[#94A3B8] mb-4">
              Add an API endpoint to the DriftShield runtime self-healing pipeline.
            </p>
            <form onSubmit={handleAddServiceSubmit} className="space-y-4 text-xs">
              <div>
                <label className="block text-[#94A3B8] font-medium mb-1">Service Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Catalog Service"
                  value={newServiceName}
                  onChange={(e) => setNewServiceName(e.target.value)}
                  className="w-full bg-[#0F172A] border border-[#334155] rounded-lg px-3 py-2 text-white focus:outline-none focus:border-[#5B8C9E]"
                />
              </div>

              <div>
                <label className="block text-[#94A3B8] font-medium mb-1">Target Endpoint</label>
                <input
                  type="text"
                  placeholder="/api/v1/catalog/items"
                  value={newServiceEndpoint}
                  onChange={(e) => setNewServiceEndpoint(e.target.value)}
                  className="w-full bg-[#0F172A] border border-[#334155] rounded-lg px-3 py-2 text-white focus:outline-none focus:border-[#5B8C9E]"
                />
              </div>

              <div>
                <label className="block text-[#94A3B8] font-medium mb-1">HTTP Method</label>
                <select
                  value={newServiceMethod}
                  onChange={(e) => setNewServiceMethod(e.target.value as any)}
                  className="w-full bg-[#0F172A] border border-[#334155] rounded-lg px-3 py-2 text-white focus:outline-none focus:border-[#5B8C9E]"
                >
                  <option value="GET">GET</option>
                  <option value="POST">POST</option>
                  <option value="PUT">PUT</option>
                </select>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3.5 py-2 rounded-lg bg-[#0F172A] border border-[#334155] text-[#94A3B8] hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-[#5B8C9E] hover:bg-[#4E7A8B] text-white font-semibold"
                >
                  Register Service
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
