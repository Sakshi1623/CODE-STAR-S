import React from 'react';
import { 
  Clock, 
  Cpu, 
  Play
} from 'lucide-react';
import { 
  LineChart, 
  Line, 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer
} from 'recharts';
import { useApp } from '../../context/AppContext';
import { 
  performanceOverTimeData, 
  evaluationComparisonData 
} from '../../data/mockData';

export const EvaluationScreen: React.FC = () => {
  const { showToast } = useApp();

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
            Evaluation
            <span className="text-xs px-2 py-0.5 rounded-full bg-[#0D9488]/15 text-[#0D9488] font-medium border border-[#0D9488]/30">
              Benchmark Suite
            </span>
          </h1>
          <p className="text-sm text-[#94A3B8] mt-0.5">
            Empirical benchmark comparison between Unassisted Baseline Agent and DriftShield Self-Healing Interceptor
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => showToast('Benchmark suite initiated: 50 synthetic schema drift permutations running...')}
            className="px-3.5 py-2 rounded-lg bg-[#5B8C9E] hover:bg-[#4E7A8B] text-white text-xs font-semibold flex items-center gap-1.5 transition-all shadow-sm"
          >
            <Play className="w-3.5 h-3.5" />
            <span>Run Benchmark</span>
          </button>
        </div>
      </div>

      {/* Top Performance Chart (Baseline vs Self-Healing) */}
      <div className="bg-[#1E293B] border border-[#334155]/60 rounded-xl p-5 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-[#334155]/60 mb-4 gap-2">
          <div>
            <h2 className="text-sm font-semibold text-white">Performance Charts</h2>
            <p className="text-xs text-[#94A3B8]">
              API invocation success rate across sudden schema drifts
            </p>
          </div>

          <div className="flex items-center gap-4 text-xs">
            <span className="flex items-center gap-1.5 text-[#64748B]">
              <span className="w-2.5 h-2.5 rounded-full bg-[#64748B]"></span>
              Baseline Agent
            </span>
            <span className="flex items-center gap-1.5 text-[#5B8C9E] font-medium">
              <span className="w-2.5 h-2.5 rounded-full bg-[#5B8C9E]"></span>
              Self-Healing Agent
            </span>
          </div>
        </div>

        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={performanceOverTimeData}
              margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.4} vertical={false} />
              <XAxis dataKey="time" stroke="#64748B" fontSize={11} tickLine={false} />
              <YAxis domain={[40, 105]} stroke="#64748B" fontSize={11} tickLine={false} tickFormatter={(v) => `${v}%`} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0F172A',
                  borderColor: '#334155',
                  borderRadius: '8px',
                  fontSize: '12px',
                  color: '#F8FAFC',
                }}
                formatter={(val: any, name: any) => [
                  `${val}%`,
                  name === 'selfHealing' ? 'Self-Healing Agent' : 'Baseline Agent'
                ]}
              />
              <Line
                type="monotone"
                dataKey="selfHealing"
                stroke="#5B8C9E"
                strokeWidth={2.5}
                dot={{ r: 4, fill: '#5B8C9E' }}
                activeDot={{ r: 6 }}
              />
              <Line
                type="monotone"
                dataKey="baseline"
                stroke="#64748B"
                strokeWidth={1.8}
                strokeDasharray="4 4"
                dot={{ r: 3, fill: '#64748B' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* KPI Cards Row (ZTAR, MTTR, Token Overhead) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* ZTAR (Zero-Touch Adaptation Rate) */}
        <div className="bg-[#1E293B] border border-[#334155]/60 rounded-xl p-5 relative overflow-hidden group hover:border-[#0D9488]/50 transition-colors">
          <div className="flex items-center justify-between text-xs text-[#94A3B8] mb-1 font-medium">
            <span>ZTAR</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#0D9488]/20 text-[#0D9488] font-bold">
              Autonomous
            </span>
          </div>
          <p className="text-[11px] text-[#64748B]">Zero-Touch Adaptation Rate</p>

          <div className="flex items-baseline gap-3 mt-3">
            <span className="text-4xl font-extrabold text-[#0D9488] tracking-tight">
              90%
            </span>
            <div className="text-xs text-[#94A3B8]">
              Automated reconciliation without developer intervention
            </div>
          </div>

          <div className="w-full bg-[#0F172A] rounded-full h-1.5 mt-3 overflow-hidden">
            <div className="bg-[#0D9488] h-full rounded-full" style={{ width: '90%' }}></div>
          </div>
        </div>

        {/* MTTR (Mean Time to Recovery) */}
        <div className="bg-[#1E293B] border border-[#334155]/60 rounded-xl p-5 relative overflow-hidden group hover:border-[#5B8C9E]/50 transition-colors">
          <div className="flex items-center justify-between text-xs text-[#94A3B8] mb-1 font-medium">
            <span>MTTR</span>
            <Clock className="w-3.5 h-3.5 text-[#5B8C9E]" />
          </div>
          <p className="text-[11px] text-[#64748B]">Mean Time to Recovery</p>

          <div className="flex items-baseline gap-3 mt-3">
            <span className="text-4xl font-extrabold text-[#5B8C9E] tracking-tight">
              6s
            </span>
            <div className="text-xs text-[#94A3B8]">
              vs. 4.2 hours average manual remediation SLA
            </div>
          </div>

          <div className="w-full bg-[#0F172A] rounded-full h-1.5 mt-3 overflow-hidden">
            <div className="bg-[#5B8C9E] h-full rounded-full" style={{ width: '95%' }}></div>
          </div>
        </div>

        {/* Token Overhead */}
        <div className="bg-[#1E293B] border border-[#334155]/60 rounded-xl p-5 relative overflow-hidden group hover:border-[#38BDF8]/50 transition-colors">
          <div className="flex items-center justify-between text-xs text-[#94A3B8] mb-1 font-medium">
            <span>Token Overhead</span>
            <Cpu className="w-3.5 h-3.5 text-[#38BDF8]" />
          </div>
          <p className="text-[11px] text-[#64748B]">Execution Overhead</p>

          <div className="flex items-baseline gap-3 mt-3">
            <span className="text-4xl font-extrabold text-white tracking-tight">
              25%
            </span>
            <div className="text-xs text-[#94A3B8]">
              Lightweight runtime schema synthesis footprint
            </div>
          </div>

          <div className="w-full bg-[#0F172A] rounded-full h-1.5 mt-3 overflow-hidden">
            <div className="bg-[#38BDF8] h-full rounded-full" style={{ width: '25%' }}></div>
          </div>
        </div>
      </div>

      {/* Side-by-Side Comparative Bar Chart */}
      <div className="bg-[#1E293B] border border-[#334155]/60 rounded-xl p-5 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-[#334155]/60 mb-4 gap-2">
          <div>
            <h2 className="text-sm font-semibold text-white">Evaluation Comparison</h2>
            <p className="text-xs text-[#94A3B8]">
              Side-by-side metric breakdown across agent resilience and adaptation dimensions
            </p>
          </div>

          <div className="flex items-center gap-4 text-xs">
            <span className="flex items-center gap-1.5 text-[#64748B]">
              <span className="w-2.5 h-2.5 rounded-sm bg-[#64748B]"></span>
              Baseline Agent
            </span>
            <span className="flex items-center gap-1.5 text-[#5B8C9E] font-medium">
              <span className="w-2.5 h-2.5 rounded-sm bg-[#5B8C9E]"></span>
              Self-Healing Agent
            </span>
          </div>
        </div>

        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={evaluationComparisonData}
              margin={{ top: 10, right: 10, left: -20, bottom: 20 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.4} vertical={false} />
              <XAxis 
                dataKey="metric" 
                stroke="#64748B" 
                fontSize={11} 
                tickLine={false}
                interval={0}
              />
              <YAxis 
                domain={[0, 100]} 
                stroke="#64748B" 
                fontSize={11} 
                tickLine={false} 
                tickFormatter={(v) => `${v}%`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0F172A',
                  borderColor: '#334155',
                  borderRadius: '8px',
                  fontSize: '12px',
                  color: '#F8FAFC',
                }}
                formatter={(val: any, name: any) => [
                  `${val}%`,
                  name === 'selfHealing' ? 'Self-Healing Agent' : 'Baseline Agent'
                ]}
              />
              <Bar 
                dataKey="baseline" 
                name="Baseline Agent"
                fill="#64748B" 
                radius={[4, 4, 0, 0]} 
                maxBarSize={32}
              />
              <Bar 
                dataKey="selfHealing" 
                name="Self-Healing Agent"
                fill="#5B8C9E" 
                radius={[4, 4, 0, 0]} 
                maxBarSize={32}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
