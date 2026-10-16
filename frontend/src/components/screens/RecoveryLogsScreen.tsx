import React, { useState } from 'react';
import { 
  Plus, 
  Search, 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  Download,
  Info
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import type { RecoveryLogItem } from '../../types';

export const RecoveryLogsScreen: React.FC = () => {
  const { recoveryLogs, addRecoveryLog, showToast } = useApp();
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedLog, setSelectedLog] = useState<RecoveryLogItem | null>(null);

  // Form states for adding interceptor event
  const [newService, setNewService] = useState('user-service');
  const [newEvent, setNewEvent] = useState('Runtime drift agent');
  const [newStatus, setNewStatus] = useState<RecoveryLogItem['status']>('Success');
  const [newDetails, setNewDetails] = useState('');

  const filteredLogs = recoveryLogs.filter((log) => {
    const matchesSearch = 
      log.service.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.event.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.details.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || log.status.toLowerCase() === statusFilter.toLowerCase();
    return matchesSearch && matchesStatus;
  });

  const handleAddSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    addRecoveryLog({
      service: newService,
      event: newEvent,
      status: newStatus,
      details: newDetails || 'Synthesized schema rule applied by operator.',
    });
    setNewDetails('');
    setShowAddModal(false);
  };

  const getStatusBadge = (status: RecoveryLogItem['status']) => {
    switch (status) {
      case 'Success':
      case 'Recovered':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[#0D9488]/15 text-[#0D9488] border border-[#0D9488]/30">
            <CheckCircle2 className="w-3 h-3" />
            {status}
          </span>
        );
      case 'Warning':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[#F59E0B]/15 text-[#F59E0B] border border-[#F59E0B]/30">
            <AlertTriangle className="w-3 h-3" />
            Warning
          </span>
        );
      case 'Error':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[#EF4444]/15 text-[#EF4444] border border-[#EF4444]/30">
            <XCircle className="w-3 h-3" />
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
            Recovery Logs
            <span className="text-xs px-2 py-0.5 rounded-full bg-[#5B8C9E]/15 text-[#5B8C9E] font-medium border border-[#5B8C9E]/30">
              Audit Trail
            </span>
          </h1>
          <p className="text-sm text-[#94A3B8] mt-0.5">
            Detailed chronological record of self-healing interceptor events and schema reconciliations
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => showToast('Exporting recovery logs as JSON...')}
            className="px-3 py-2 rounded-lg bg-[#1E293B] border border-[#334155] hover:border-[#5B8C9E] text-xs text-[#94A3B8] hover:text-white flex items-center gap-1.5 transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export</span>
          </button>
          <button
            onClick={() => setShowAddModal(true)}
            className="px-3.5 py-2 rounded-lg bg-[#5B8C9E] hover:bg-[#4E7A8B] text-white text-xs font-semibold flex items-center gap-1.5 transition-all shadow-sm"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Interceptor</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-[#1E293B] border border-[#334155]/60 rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-[#64748B] absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search logs by service, event, or details..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-[#0F172A] border border-[#334155] rounded-lg pl-9 pr-3 py-1.5 text-xs text-white placeholder-[#64748B] focus:outline-none focus:border-[#5B8C9E]"
          />
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="text-[#94A3B8] font-medium">Filter Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-[#0F172A] border border-[#334155] rounded-lg px-2.5 py-1.5 text-white focus:outline-none focus:border-[#5B8C9E]"
          >
            <option value="all">All Events ({recoveryLogs.length})</option>
            <option value="success">Success / Recovered</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
          </select>
        </div>
      </div>

      {/* Recovery Logs Table matching Card 5 */}
      <div className="bg-[#1E293B] border border-[#334155]/60 rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="bg-[#0F172A]/70 text-[#94A3B8] font-semibold border-b border-[#334155]/60 uppercase text-[11px]">
                <th className="px-5 py-3.5">Time</th>
                <th className="px-4 py-3.5">Service</th>
                <th className="px-4 py-3.5">Event</th>
                <th className="px-4 py-3.5">Status</th>
                <th className="px-4 py-3.5">Details</th>
                <th className="px-5 py-3.5 text-right">Inspect</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#334155]/40 text-[#F8FAFC]">
              {filteredLogs.map((log) => (
                <tr 
                  key={log.id} 
                  className="hover:bg-[#0F172A]/40 transition-colors group cursor-pointer"
                  onClick={() => setSelectedLog(log)}
                >
                  <td className="px-5 py-3.5 text-[#64748B] whitespace-nowrap">
                    {log.time}
                  </td>
                  <td className="px-4 py-3.5 font-semibold text-white whitespace-nowrap">
                    {log.service}
                  </td>
                  <td className="px-4 py-3.5 text-[#94A3B8] whitespace-nowrap">
                    {log.event}
                  </td>
                  <td className="px-4 py-3.5 whitespace-nowrap">
                    {getStatusBadge(log.status)}
                  </td>
                  <td className="px-4 py-3.5 font-sans text-xs text-[#94A3B8] max-w-md truncate">
                    {log.details}
                  </td>
                  <td className="px-5 py-3.5 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedLog(log);
                      }}
                      className="px-2 py-1 rounded bg-[#0F172A] border border-[#334155] text-[11px] text-[#94A3B8] group-hover:text-white group-hover:border-[#5B8C9E]"
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail Drawer Modal */}
      {selectedLog && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-[#1E293B] border border-[#334155] rounded-xl w-full max-w-lg p-6 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-[#334155]">
              <div className="flex items-center gap-2">
                <Info className="w-4 h-4 text-[#5B8C9E]" />
                <h3 className="text-sm font-bold text-white">Interceptor Event Audit</h3>
              </div>
              <button
                onClick={() => setSelectedLog(null)}
                className="text-[#64748B] hover:text-white text-xs"
              >
                Close
              </button>
            </div>

            <div className="mt-4 space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3 bg-[#0F172A] p-3 rounded-lg border border-[#334155]">
                <div>
                  <span className="text-[#64748B] block text-[11px]">Timestamp</span>
                  <span className="font-mono text-white">{selectedLog.time}</span>
                </div>
                <div>
                  <span className="text-[#64748B] block text-[11px]">Service</span>
                  <span className="font-mono text-[#5B8C9E] font-semibold">{selectedLog.service}</span>
                </div>
                <div>
                  <span className="text-[#64748B] block text-[11px]">Event Type</span>
                  <span className="text-white">{selectedLog.event}</span>
                </div>
                <div>
                  <span className="text-[#64748B] block text-[11px]">Interception Status</span>
                  {getStatusBadge(selectedLog.status)}
                </div>
              </div>

              <div>
                <span className="text-[#64748B] block text-[11px] mb-1">Audit Details</span>
                <p className="p-3 bg-[#0F172A] border border-[#334155] rounded-lg text-[#94A3B8] font-mono leading-relaxed">
                  {selectedLog.details}
                </p>
              </div>

              <div className="pt-2 flex justify-end">
                <button
                  onClick={() => setSelectedLog(null)}
                  className="px-4 py-2 rounded-lg bg-[#5B8C9E] hover:bg-[#4E7A8B] text-white font-semibold text-xs"
                >
                  Dismiss
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Add Interceptor Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-[#1E293B] border border-[#334155] rounded-xl w-full max-w-md p-6 shadow-2xl">
            <h3 className="text-base font-bold text-white mb-1">Add Interceptor Event</h3>
            <p className="text-xs text-[#94A3B8] mb-4">
              Manually trigger or register a recovery rule log.
            </p>
            <form onSubmit={handleAddSubmit} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-[#94A3B8] mb-1 font-medium">Service</label>
                <input
                  type="text"
                  required
                  value={newService}
                  onChange={(e) => setNewService(e.target.value)}
                  className="w-full bg-[#0F172A] border border-[#334155] rounded-lg px-3 py-2 text-white focus:outline-none focus:border-[#5B8C9E]"
                />
              </div>

              <div>
                <label className="block text-[#94A3B8] mb-1 font-medium">Event Name</label>
                <input
                  type="text"
                  required
                  value={newEvent}
                  onChange={(e) => setNewEvent(e.target.value)}
                  className="w-full bg-[#0F172A] border border-[#334155] rounded-lg px-3 py-2 text-white focus:outline-none focus:border-[#5B8C9E]"
                />
              </div>

              <div>
                <label className="block text-[#94A3B8] mb-1 font-medium">Status</label>
                <select
                  value={newStatus}
                  onChange={(e) => setNewStatus(e.target.value as any)}
                  className="w-full bg-[#0F172A] border border-[#334155] rounded-lg px-3 py-2 text-white focus:outline-none focus:border-[#5B8C9E]"
                >
                  <option value="Success">Success</option>
                  <option value="Recovered">Recovered</option>
                  <option value="Warning">Warning</option>
                  <option value="Error">Error</option>
                </select>
              </div>

              <div>
                <label className="block text-[#94A3B8] mb-1 font-medium">Details</label>
                <textarea
                  rows={3}
                  value={newDetails}
                  onChange={(e) => setNewDetails(e.target.value)}
                  placeholder="e.g. Injected fallback value for missing created_at attribute..."
                  className="w-full bg-[#0F172A] border border-[#334155] rounded-lg px-3 py-2 text-white focus:outline-none focus:border-[#5B8C9E]"
                />
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
                  Add Log
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
