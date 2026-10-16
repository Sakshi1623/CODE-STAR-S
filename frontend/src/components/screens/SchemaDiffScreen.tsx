import React, { useState } from 'react';
import { 
  GitCompare, 
  AlertTriangle, 
  RotateCcw, 
  Sparkles, 
  Copy, 
  FileCode2
} from 'lucide-react';
import { useApp } from '../../context/AppContext';

export const SchemaDiffScreen: React.FC = () => {
  const { 
    patchApplied, 
    applyPatch, 
    rollbackPatch, 
    showToast 
  } = useApp();

  const [selectedSchema, setSelectedSchema] = useState('user-profile');

  // Baseline lines for user-profile
  const baselineLines = [
    { num: 1, text: '{', type: 'normal' },
    { num: 2, text: '  "$schema": "https://json-schema.org/v1/schema",', type: 'normal' },
    { num: 3, text: '  "title": "UserProfile",', type: 'normal' },
    { num: 4, text: '  "type": "object",', type: 'normal' },
    { num: 5, text: '  "required": [', type: 'normal' },
    { num: 6, text: '    "user_id",', type: 'removed' },
    { num: 7, text: '    "username",', type: 'normal' },
    { num: 8, text: '    "email",', type: 'normal' },
    { num: 9, text: '    "created_at",', type: 'removed' },
    { num: 10, text: '    "status"', type: 'normal' },
    { num: 11, text: '  ],', type: 'normal' },
    { num: 12, text: '  "properties": {', type: 'normal' },
    { num: 13, text: '    "user_id": {', type: 'removed' },
    { num: 14, text: '      "type": "string",', type: 'removed' },
    { num: 15, text: '      "format": "uuid"', type: 'removed' },
    { num: 16, text: '    },', type: 'removed' },
    { num: 17, text: '    "username": { "type": "string" },', type: 'normal' },
    { num: 18, text: '    "email": { "type": "string" },', type: 'normal' },
    { num: 19, text: '    "created_at": {', type: 'removed' },
    { num: 20, text: '      "type": "string",', type: 'removed' },
    { num: 21, text: '      "format": "date-time"', type: 'removed' },
    { num: 22, text: '    },', type: 'removed' },
    { num: 23, text: '    "status": { "type": "string" }', type: 'normal' },
    { num: 24, text: '  }', type: 'normal' },
    { num: 25, text: '}', type: 'normal' },
  ];

  // Drifted lines for user-profile
  const driftedLines = [
    { num: 1, text: '{', type: 'normal' },
    { num: 2, text: '  "$schema": "https://json-schema.org/v2/schema",', type: 'modified' },
    { num: 3, text: '  "title": "UserProfile",', type: 'normal' },
    { num: 4, text: '  "type": "object",', type: 'normal' },
    { num: 5, text: '  "required": [', type: 'normal' },
    { num: 6, text: '    "userId",', type: 'added' },
    { num: 7, text: '    "username",', type: 'normal' },
    { num: 8, text: '    "email",', type: 'normal' },
    { num: 9, text: '    "kyc_status",', type: 'added' },
    { num: 10, text: '    "status"', type: 'normal' },
    { num: 11, text: '  ],', type: 'normal' },
    { num: 12, text: '  "properties": {', type: 'normal' },
    { num: 13, text: '    "userId": {', type: 'added' },
    { num: 14, text: '      "type": "string",', type: 'added' },
    { num: 15, text: '      "description": "Renamed user_id"', type: 'added' },
    { num: 16, text: '    },', type: 'added' },
    { num: 17, text: '    "username": { "type": "string" },', type: 'normal' },
    { num: 18, text: '    "email": { "type": "string" },', type: 'normal' },
    { num: 19, text: '    "kyc_status": {', type: 'added' },
    { num: 20, text: '      "type": "string",', type: 'added' },
    { num: 21, text: '      "enum": ["verified", "pending"]', type: 'added' },
    { num: 22, text: '    },', type: 'added' },
    { num: 23, text: '    "status": { "type": "string" }', type: 'normal' },
    { num: 24, text: '  }', type: 'normal' },
    { num: 25, text: '}', type: 'normal' },
  ];

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
            Schema Diff
            <span className="text-xs px-2 py-0.5 rounded-full bg-[#5B8C9E]/15 text-[#5B8C9E] font-medium border border-[#5B8C9E]/30">
              Interactive Inspector
            </span>
          </h1>
          <p className="text-sm text-[#94A3B8] mt-0.5">
            Side-by-side JSON comparison showing schema drift mutations and recommended patches
          </p>
        </div>

        {/* Schema Selector & Controls */}
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={selectedSchema}
            onChange={(e) => setSelectedSchema(e.target.value)}
            className="bg-[#1E293B] border border-[#334155] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-[#5B8C9E]"
          >
            <option value="user-profile">UserProfile (v1 vs v2)</option>
            <option value="payment-intent">PaymentIntent (v1 vs v2)</option>
            <option value="notification">NotificationPayload (v2 vs v3)</option>
          </select>

          <button
            onClick={() => showToast('Diff re-computed against latest runtime payload.')}
            className="px-3 py-2 rounded-lg bg-[#1E293B] border border-[#334155] hover:border-[#5B8C9E] text-xs text-[#94A3B8] hover:text-white flex items-center gap-1.5 transition-colors"
          >
            <GitCompare className="w-3.5 h-3.5 text-[#5B8C9E]" />
            <span>Compare</span>
          </button>

          {patchApplied ? (
            <button
              onClick={rollbackPatch}
              className="px-3.5 py-2 rounded-lg bg-[#EF4444]/20 border border-[#EF4444]/40 hover:bg-[#EF4444]/30 text-white text-xs font-semibold flex items-center gap-1.5 transition-all"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Rollback Patch</span>
            </button>
          ) : (
            <button
              onClick={applyPatch}
              className="px-3.5 py-2 rounded-lg bg-[#0D9488] hover:bg-[#0f766e] text-white text-xs font-semibold flex items-center gap-1.5 transition-all shadow-sm"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Apply Patch</span>
            </button>
          )}
        </div>
      </div>

      {/* Side-by-Side Diff Container */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left: Baseline Schema */}
        <div className="bg-[#1E293B] border border-[#334155]/60 rounded-xl overflow-hidden shadow-sm flex flex-col">
          <div className="px-4 py-3 bg-[#182234] border-b border-[#334155]/60 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileCode2 className="w-4 h-4 text-[#94A3B8]" />
              <span className="text-xs font-semibold text-white">Baseline</span>
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#0F172A] text-[#94A3B8] border border-[#334155] font-mono">
                baseline.json (v1)
              </span>
            </div>
            <button
              onClick={() => showToast('Baseline JSON copied to clipboard')}
              className="text-[#94A3B8] hover:text-white transition-colors"
              title="Copy"
            >
              <Copy className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="p-3 bg-[#0F172A] font-mono text-[12px] overflow-x-auto max-h-[460px] overflow-y-auto leading-relaxed select-text">
            {baselineLines.map((line) => (
              <div
                key={`base-${line.num}`}
                className={`flex items-start px-2 py-0.5 rounded ${
                  line.type === 'removed'
                    ? 'bg-[#EF4444]/15 text-[#FCA5A5] border-l-2 border-[#EF4444]'
                    : 'text-[#94A3B8]'
                }`}
              >
                <span className="w-8 shrink-0 text-[#64748B] select-none text-[11px] text-right pr-3">
                  {line.num}
                </span>
                <span className="whitespace-pre">{line.text}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Drifted Schema */}
        <div className="bg-[#1E293B] border border-[#334155]/60 rounded-xl overflow-hidden shadow-sm flex flex-col">
          <div className="px-4 py-3 bg-[#182234] border-b border-[#334155]/60 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileCode2 className="w-4 h-4 text-[#F59E0B]" />
              <span className="text-xs font-semibold text-white">Drifted</span>
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#F59E0B]/15 text-[#F59E0B] border border-[#F59E0B]/30 font-mono">
                drifted_payload.json (v2)
              </span>
            </div>
            <button
              onClick={() => showToast('Drifted JSON copied to clipboard')}
              className="text-[#94A3B8] hover:text-white transition-colors"
              title="Copy"
            >
              <Copy className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="p-3 bg-[#0F172A] font-mono text-[12px] overflow-x-auto max-h-[460px] overflow-y-auto leading-relaxed select-text">
            {driftedLines.map((line) => (
              <div
                key={`drift-${line.num}`}
                className={`flex items-start px-2 py-0.5 rounded ${
                  line.type === 'added'
                    ? 'bg-[#0D9488]/20 text-[#5EEAD4] border-l-2 border-[#0D9488]'
                    : line.type === 'modified'
                    ? 'bg-[#F59E0B]/15 text-[#FCD34D] border-l-2 border-[#F59E0B]'
                    : 'text-[#94A3B8]'
                }`}
              >
                <span className="w-8 shrink-0 text-[#64748B] select-none text-[11px] text-right pr-3">
                  {line.num}
                </span>
                <span className="whitespace-pre">{line.text}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Schema Drift Detected Alert Box */}
      <div className="bg-[#1E293B] border border-[#F59E0B]/40 rounded-xl p-5 relative overflow-hidden">
        <div className="flex items-start gap-3.5">
          <div className="p-2 rounded-lg bg-[#F59E0B]/15 text-[#F59E0B] shrink-0 mt-0.5">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-white">Schema Drift Detected</h3>
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-[#F59E0B]/20 text-[#F59E0B] font-semibold border border-[#F59E0B]/40">
                Critical Contract Deviation
              </span>
            </div>
            <p className="text-xs text-[#94A3B8] mt-1 leading-relaxed">
              Two breaking changes detected in runtime schema definition:
            </p>
            <ul className="mt-2 space-y-1 text-xs font-mono text-[#94A3B8]">
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-[#EF4444]"></span>
                <span className="text-[#EF4444]">Missing required field:</span> "user_id" (renamed to "userId")
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-[#EF4444]"></span>
                <span className="text-[#EF4444]">Missing required field:</span> "created_at"
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-[#0D9488]"></span>
                <span className="text-[#0D9488]">Added unmapped field:</span> "kyc_status"
              </li>
            </ul>
          </div>
        </div>
      </div>

      {/* Recommended Patch Card */}
      <div className="bg-[#1E293B] border border-[#5B8C9E]/50 rounded-xl p-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-[#334155]/60 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-[#5B8C9E]" />
              <h3 className="text-sm font-bold text-white">Recommended Patch</h3>
              {patchApplied && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-[#0D9488]/20 text-[#0D9488] font-semibold border border-[#0D9488]/40">
                  Applied & Active
                </span>
              )}
            </div>
            <p className="text-xs text-[#94A3B8] mt-1">
              Zero-Touch Auto-Synthesized Interceptor Rule generated by DriftShield Engine
            </p>
          </div>

          <div className="flex items-center gap-2">
            {patchApplied ? (
              <button
                onClick={rollbackPatch}
                className="px-4 py-2 rounded-lg bg-[#EF4444]/20 border border-[#EF4444]/40 hover:bg-[#EF4444]/30 text-white text-xs font-semibold flex items-center gap-2 transition-all"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Revert Patch</span>
              </button>
            ) : (
              <button
                onClick={applyPatch}
                className="px-5 py-2.5 rounded-lg bg-[#5B8C9E] hover:bg-[#4E7A8B] text-white text-xs font-bold flex items-center gap-2 transition-all shadow-md hover:scale-[1.01]"
              >
                <Sparkles className="w-4 h-4" />
                <span>Apply Patch</span>
              </button>
            )}
          </div>
        </div>

        {/* Interceptor Code Rule */}
        <div className="bg-[#0F172A] border border-[#334155] rounded-lg p-3 font-mono text-xs text-[#94A3B8]">
          <div className="text-[#64748B] text-[11px] mb-2">// Interceptor Synthesis Target: UserProfile v1 &lt;-&gt; v2</div>
          <pre className="text-[#5EEAD4] overflow-x-auto">
{`{
  "interceptor_id": "rule_user_profile_v2_v1",
  "direction": "inbound_response",
  "actions": [
    { "op": "alias", "from": "userId", "to": "user_id" },
    { "op": "default", "field": "created_at", "value": "$epoch_timestamp_now" },
    { "op": "preserve", "field": "kyc_status", "fallback": "verified" }
  ]
}`}
          </pre>
        </div>
      </div>
    </div>
  );
};
