import React, { useState } from 'react';
import { 
  Plus, 
  Search, 
  AlertTriangle, 
  XCircle
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import type { ToolItem } from '../../types';

export const ToolRegistryScreen: React.FC = () => {
  const { tools, addTool, showToast, setCurrentTab } = useApp();
  const [searchTerm, setSearchTerm] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);

  // Form states
  const [newToolName, setNewToolName] = useState('');
  const [newToolDesc, setNewToolDesc] = useState('');
  const [newToolEndpoint, setNewToolEndpoint] = useState('');
  const [newToolMethod, setNewToolMethod] = useState<'GET' | 'POST'>('POST');

  const filteredTools = tools.filter((tool) => {
    return (
      tool.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      tool.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      tool.tags.some(t => t.toLowerCase().includes(searchTerm.toLowerCase()))
    );
  });

  const handleAddSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newToolName.trim()) return;
    addTool({
      name: newToolName,
      description: newToolDesc || 'Autonomous registry tool for LLM agent integration.',
      endpoint: newToolEndpoint || '/api/tools/custom',
      method: newToolMethod,
    });
    setNewToolName('');
    setNewToolDesc('');
    setNewToolEndpoint('');
    setShowAddModal(false);
  };

  const getHealthIndicator = (health: ToolItem['health']) => {
    switch (health) {
      case 'healthy':
        return (
          <span className="flex items-center gap-1.5 text-xs text-[#0D9488] font-semibold bg-[#0D9488]/15 px-2.5 py-0.5 rounded-full border border-[#0D9488]/30">
            <span className="w-2 h-2 rounded-full bg-[#0D9488] animate-pulse"></span>
            Healthy
          </span>
        );
      case 'drift':
        return (
          <span className="flex items-center gap-1.5 text-xs text-[#F59E0B] font-semibold bg-[#F59E0B]/15 px-2.5 py-0.5 rounded-full border border-[#F59E0B]/30">
            <AlertTriangle className="w-3 h-3" />
            Drift Detected
          </span>
        );
      case 'error':
        return (
          <span className="flex items-center gap-1.5 text-xs text-[#EF4444] font-semibold bg-[#EF4444]/15 px-2.5 py-0.5 rounded-full border border-[#EF4444]/30">
            <XCircle className="w-3 h-3" />
            Schema Error
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
            Tool Registry
            <span className="text-xs px-2 py-0.5 rounded-full bg-[#5B8C9E]/15 text-[#5B8C9E] font-medium border border-[#5B8C9E]/30">
              Agent Registry
            </span>
          </h1>
          <p className="text-sm text-[#94A3B8] mt-0.5">
            Registered tools, AI agent action schemas, and active self-healing contracts
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAddModal(true)}
            className="px-3.5 py-2 rounded-lg bg-[#5B8C9E] hover:bg-[#4E7A8B] text-white text-xs font-semibold flex items-center gap-1.5 transition-all shadow-sm"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Tool</span>
          </button>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="bg-[#1E293B] border border-[#334155]/60 rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-[#64748B] absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search tools by title, description, or tag..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-[#0F172A] border border-[#334155] rounded-lg pl-9 pr-3 py-1.5 text-xs text-white placeholder-[#64748B] focus:outline-none focus:border-[#5B8C9E]"
          />
        </div>

        <div className="text-xs text-[#94A3B8]">
          Showing <span className="text-white font-semibold">{filteredTools.length}</span> registered tools
        </div>
      </div>

      {/* Grid Layout matching Card 7 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {filteredTools.map((tool) => (
          <div
            key={tool.id}
            className="bg-[#1E293B] border border-[#334155]/70 rounded-xl p-5 hover:border-[#5B8C9E]/60 transition-all flex flex-col justify-between group shadow-sm hover:shadow-md"
          >
            <div>
              {/* Top row with Method and Health */}
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold ${
                    tool.method === 'GET'
                      ? 'bg-[#38BDF8]/15 text-[#38BDF8] border border-[#38BDF8]/30'
                      : 'bg-[#5B8C9E]/20 text-[#5B8C9E] border border-[#5B8C9E]/30'
                  }`}>
                    {tool.method}
                  </span>
                  <span className="text-[11px] font-mono text-[#64748B] truncate max-w-[140px]">
                    {tool.endpoint}
                  </span>
                </div>
                {getHealthIndicator(tool.health)}
              </div>

              {/* Title and Description */}
              <h3 className="text-base font-bold text-white group-hover:text-[#5B8C9E] transition-colors flex items-center justify-between">
                <span>{tool.name}</span>
                <span className="text-[10px] text-[#64748B] font-mono">{tool.version}</span>
              </h3>
              <p className="text-xs text-[#94A3B8] mt-1.5 line-clamp-2 leading-relaxed">
                {tool.description}
              </p>

              {/* Tags */}
              <div className="flex flex-wrap gap-1.5 mt-3">
                {tool.tags.map((tag) => (
                  <span
                    key={tag}
                    className="text-[10px] px-2 py-0.5 rounded bg-[#0F172A] text-[#94A3B8] border border-[#334155]/60"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>

            {/* Bottom Metrics and Action */}
            <div className="pt-4 mt-4 border-t border-[#334155]/60 flex items-center justify-between text-xs">
              <div className="flex items-center gap-3 text-[#94A3B8]">
                <span>
                  <strong className="text-white font-mono">{tool.requests24h}</strong> reqs
                </span>
                <span>•</span>
                <span>
                  <strong className="text-white font-mono">{tool.latency}</strong>
                </span>
              </div>

              <div className="flex items-center gap-1.5">
                {tool.health === 'drift' ? (
                  <button
                    onClick={() => setCurrentTab('schema-diff')}
                    className="px-2.5 py-1 rounded bg-[#F59E0B]/15 text-[#F59E0B] border border-[#F59E0B]/30 hover:bg-[#F59E0B]/25 font-medium transition-colors text-[11px]"
                  >
                    Fix Drift
                  </button>
                ) : (
                  <button
                    onClick={() => showToast(`Tool ${tool.name} schema validation test passed.`)}
                    className="px-2.5 py-1 rounded bg-[#0F172A] hover:bg-[#334155] border border-[#334155] text-[#94A3B8] hover:text-white transition-colors text-[11px]"
                  >
                    Inspect
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Add Tool Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-[#1E293B] border border-[#334155] rounded-xl w-full max-w-md p-6 shadow-2xl">
            <h3 className="text-base font-bold text-white mb-1">Add Tool to Registry</h3>
            <p className="text-xs text-[#94A3B8] mb-4">
              Register a new tool schema for AI agent runtime self-healing interception.
            </p>
            <form onSubmit={handleAddSubmit} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-[#94A3B8] mb-1 font-medium">Tool Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Vector Search Engine"
                  value={newToolName}
                  onChange={(e) => setNewToolName(e.target.value)}
                  className="w-full bg-[#0F172A] border border-[#334155] rounded-lg px-3 py-2 text-white focus:outline-none focus:border-[#5B8C9E]"
                />
              </div>

              <div>
                <label className="block text-[#94A3B8] mb-1 font-medium">Description</label>
                <textarea
                  rows={2}
                  placeholder="Semantic document indexing and retrieval schema..."
                  value={newToolDesc}
                  onChange={(e) => setNewToolDesc(e.target.value)}
                  className="w-full bg-[#0F172A] border border-[#334155] rounded-lg px-3 py-2 text-white focus:outline-none focus:border-[#5B8C9E]"
                />
              </div>

              <div>
                <label className="block text-[#94A3B8] mb-1 font-medium">Endpoint URL</label>
                <input
                  type="text"
                  placeholder="/api/v1/search"
                  value={newToolEndpoint}
                  onChange={(e) => setNewToolEndpoint(e.target.value)}
                  className="w-full bg-[#0F172A] border border-[#334155] rounded-lg px-3 py-2 text-white focus:outline-none focus:border-[#5B8C9E]"
                />
              </div>

              <div>
                <label className="block text-[#94A3B8] mb-1 font-medium">HTTP Method</label>
                <select
                  value={newToolMethod}
                  onChange={(e) => setNewToolMethod(e.target.value as any)}
                  className="w-full bg-[#0F172A] border border-[#334155] rounded-lg px-3 py-2 text-white focus:outline-none focus:border-[#5B8C9E]"
                >
                  <option value="POST">POST</option>
                  <option value="GET">GET</option>
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
                  Add Tool
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
