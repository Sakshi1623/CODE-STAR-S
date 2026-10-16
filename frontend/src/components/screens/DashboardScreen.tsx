import React from 'react';
import { 
  Activity, 
  AlertTriangle, 
  CheckCircle2, 
  Clock, 
  ArrowUpRight, 
  Layers,
  Sparkles
} from 'lucide-react';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell
} from 'recharts';
import { useApp } from '../../context/AppContext';
import { 
  compatibilityChartData, 
  failureClassificationData, 
  recentEventsData 
} from '../../data/mockData';

export const DashboardScreen: React.FC = () => {
  const { setCurrentTab, patchApplied, settings } = useApp();

  // Adjust metrics based on mock API version or patch
  const totalRequests = settings.mockApiVersion === 'v2' ? '1,248' : '1,120';
  const driftDetected = patchApplied ? 0 : (settings.mockApiVersion === 'v2' ? 3 : 1);
  const recovered = patchApplied ? 4 : 3;
  const uptime = '99.8%';

  return (
    <div className="space-y-6">
      {/* Top Banner / Heading */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
            Dashboard
            <span className="text-xs px-2 py-0.5 rounded-full bg-[#5B8C9E]/15 text-[#5B8C9E] font-medium border border-[#5B8C9E]/30">
              Overview
            </span>
          </h1>
          <p className="text-sm text-[#94A3B8] mt-0.5">
            Runtime Schema Drift Detection & Self-Healing Telemetry
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setCurrentTab('schema-diff')}
            className="px-3.5 py-2 rounded-lg bg-[#5B8C9E] hover:bg-[#4E7A8B] text-white text-xs font-semibold flex items-center gap-2 transition-all shadow-sm"
          >
            <Layers className="w-3.5 h-3.5" />
            <span>View Schema Diff</span>
          </button>
          <button
            onClick={() => setCurrentTab('api-monitor')}
            className="px-3.5 py-2 rounded-lg bg-[#1E293B] hover:bg-[#283548] text-[#94A3B8] hover:text-white border border-[#334155] text-xs font-medium flex items-center gap-2 transition-all"
          >
            <Activity className="w-3.5 h-3.5 text-[#5B8C9E]" />
            <span>API Monitor</span>
          </button>
        </div>
      </div>

      {/* KPI Cards Row (Total Requests, Drift Detected, Recovered, Uptime) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Requests */}
        <div className="bg-[#1E293B] border border-[#334155]/60 rounded-xl p-5 relative overflow-hidden group hover:border-[#5B8C9E]/50 transition-colors">
          <div className="flex items-center justify-between text-xs text-[#94A3B8] mb-2 font-medium">
            <span>Total Requests</span>
            <Activity className="w-4 h-4 text-[#5B8C9E]" />
          </div>
          <div className="text-3xl font-extrabold text-white tracking-tight">
            {totalRequests}
          </div>
          <div className="flex items-center gap-1.5 mt-2 text-xs text-[#0D9488]">
            <ArrowUpRight className="w-3.5 h-3.5" />
            <span>+12.4% from last period</span>
          </div>
        </div>

        {/* Drift Detected */}
        <div className="bg-[#1E293B] border border-[#334155]/60 rounded-xl p-5 relative overflow-hidden group hover:border-[#F59E0B]/50 transition-colors">
          <div className="flex items-center justify-between text-xs text-[#94A3B8] mb-2 font-medium">
            <span>Drift Detected</span>
            <div className="p-1 rounded bg-[#F59E0B]/15 text-[#F59E0B]">
              <AlertTriangle className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-[#F59E0B] tracking-tight">
              {driftDetected}
            </span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-[#F59E0B]/20 text-[#F59E0B] font-semibold border border-[#F59E0B]/40">
              {driftDetected > 0 ? 'Requires Action' : 'Resolved'}
            </span>
          </div>
          <div className="flex items-center gap-1.5 mt-2 text-xs text-[#94A3B8]">
            <span>Active monitoring on 6 endpoints</span>
          </div>
        </div>

        {/* Recovered */}
        <div className="bg-[#1E293B] border border-[#334155]/60 rounded-xl p-5 relative overflow-hidden group hover:border-[#0D9488]/50 transition-colors">
          <div className="flex items-center justify-between text-xs text-[#94A3B8] mb-2 font-medium">
            <span>Recovered</span>
            <div className="p-1 rounded bg-[#0D9488]/15 text-[#0D9488]">
              <CheckCircle2 className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-[#0D9488] tracking-tight">
              {recovered}
            </span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-[#0D9488]/20 text-[#0D9488] font-semibold border border-[#0D9488]/40">
              100% Self-Healed
            </span>
          </div>
          <div className="flex items-center gap-1.5 mt-2 text-xs text-[#94A3B8]">
            <span>Average recovery MTTR: 6s</span>
          </div>
        </div>

        {/* Uptime */}
        <div className="bg-[#1E293B] border border-[#334155]/60 rounded-xl p-5 relative overflow-hidden group hover:border-[#5B8C9E]/50 transition-colors">
          <div className="flex items-center justify-between text-xs text-[#94A3B8] mb-2 font-medium">
            <span>Uptime</span>
            <div className="w-2 h-2 rounded-full bg-[#0D9488] animate-pulse"></div>
          </div>
          <div className="text-3xl font-extrabold text-white tracking-tight">
            {uptime}
          </div>
          <div className="flex items-center gap-1.5 mt-2 text-xs text-[#94A3B8]">
            <span>Zero downtime under schema mutation</span>
          </div>
        </div>
      </div>

      {/* Main Charts & Events Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (2 cols): API Compatibility Chart & Failure Classification */}
        <div className="lg:col-span-2 space-y-6">
          {/* API Compatibility Over Time Chart */}
          <div className="bg-[#1E293B] border border-[#334155]/60 rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-base font-semibold text-white">
                  API Compatibility Over Time
                </h3>
                <p className="text-xs text-[#94A3B8]">
                  Compatibility index maintained across client deployments
                </p>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <span className="flex items-center gap-1.5 text-[#5B8C9E]">
                  <span className="w-2.5 h-2.5 rounded-sm bg-[#5B8C9E]"></span>
                  Self-Healing Interceptor
                </span>
                <span className="flex items-center gap-1.5 text-[#64748B] ml-2">
                  <span className="w-2.5 h-2.5 rounded-sm bg-[#64748B]"></span>
                  Without DriftShield
                </span>
              </div>
            </div>

            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={compatibilityChartData}
                  margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="colorCompat" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#5B8C9E" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#5B8C9E" stopOpacity={0.0} />
                    </linearGradient>
                    <linearGradient id="colorBase" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#64748B" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#64748B" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.4} vertical={false} />
                  <XAxis 
                    dataKey="date" 
                    stroke="#64748B" 
                    fontSize={11} 
                    tickLine={false}
                  />
                  <YAxis 
                    domain={[40, 100]} 
                    stroke="#64748B" 
                    fontSize={11} 
                    tickLine={false}
                    tickFormatter={(val) => `${val}%`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0F172A',
                      borderColor: '#334155',
                      borderRadius: '8px',
                      fontSize: '12px',
                      color: '#F8FAFC',
                    }}
                    formatter={(value: any, name: any) => [
                      `${value}%`,
                      name === 'compatibility' ? 'DriftShield Active' : 'Baseline Unshielded'
                    ]}
                  />
                  <Area
                    type="monotone"
                    dataKey="compatibility"
                    stroke="#5B8C9E"
                    strokeWidth={2.5}
                    fillOpacity={1}
                    fill="url(#colorCompat)"
                  />
                  <Area
                    type="monotone"
                    dataKey="baseline"
                    stroke="#64748B"
                    strokeWidth={1.5}
                    strokeDasharray="4 4"
                    fillOpacity={1}
                    fill="url(#colorBase)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Failure Classification Donut Chart */}
          <div className="bg-[#1E293B] border border-[#334155]/60 rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-base font-semibold text-white">
                  Failure Classification
                </h3>
                <p className="text-xs text-[#94A3B8]">
                  Categorization of intercepted runtime schema mismatches
                </p>
              </div>
              <span className="text-xs text-[#5B8C9E] bg-[#5B8C9E]/10 px-2.5 py-1 rounded border border-[#5B8C9E]/30 font-medium">
                Total: 75 Interceptions
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-center">
              <div className="h-48 flex items-center justify-center">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={failureClassificationData}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={75}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {failureClassificationData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} stroke="#1E293B" strokeWidth={2} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#0F172A',
                        borderColor: '#334155',
                        borderRadius: '8px',
                        fontSize: '12px',
                        color: '#F8FAFC',
                      }}
                      formatter={(val: any) => [`${val} occurrences`, 'Frequency']}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              {/* Classification Legend matching image */}
              <div className="space-y-2 text-xs">
                {failureClassificationData.map((item) => (
                  <div key={item.name} className="flex items-center justify-between p-2 rounded-lg bg-[#0F172A]/40 border border-[#334155]/40">
                    <div className="flex items-center gap-2">
                      <span
                        className="w-2.5 h-2.5 rounded-full shrink-0"
                        style={{ backgroundColor: item.color }}
                      ></span>
                      <span className="text-[#94A3B8] font-medium">{item.name}</span>
                    </div>
                    <span className="text-white font-bold">{item.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right Column (1 col): Recent Events */}
        <div className="bg-[#1E293B] border border-[#334155]/60 rounded-xl p-5 flex flex-col">
          <div className="flex items-center justify-between pb-3 border-b border-[#334155]/60 mb-3">
            <div>
              <h3 className="text-base font-semibold text-white">Recent Events</h3>
              <p className="text-xs text-[#94A3B8]">Real-time system telemetry feed</p>
            </div>
            <button
              onClick={() => setCurrentTab('recovery-logs')}
              className="text-xs text-[#5B8C9E] hover:underline flex items-center gap-1"
            >
              View all
            </button>
          </div>

          <div className="space-y-3 flex-1 overflow-y-auto pr-1">
            {recentEventsData.map((evt) => {
              const isDrift = evt.type === 'drift';
              const isRecovered = evt.type === 'recovered';
              const isError = evt.type === 'error';

              return (
                <div
                  key={evt.id}
                  className={`p-3 rounded-lg border text-xs transition-colors ${
                    isDrift
                      ? 'bg-[#F59E0B]/10 border-[#F59E0B]/30'
                      : isRecovered
                      ? 'bg-[#0D9488]/10 border-[#0D9488]/30'
                      : isError
                      ? 'bg-[#EF4444]/10 border-[#EF4444]/30'
                      : 'bg-[#0F172A] border-[#334155]/60'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-semibold text-white leading-snug">
                      {evt.title}
                    </span>
                    <span
                      className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded font-medium ${
                        isDrift
                          ? 'bg-[#F59E0B]/20 text-[#F59E0B]'
                          : isRecovered
                          ? 'bg-[#0D9488]/20 text-[#0D9488]'
                          : isError
                          ? 'bg-[#EF4444]/20 text-[#EF4444]'
                          : 'bg-[#5B8C9E]/20 text-[#5B8C9E]'
                      }`}
                    >
                      {evt.type.toUpperCase()}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 mt-2 text-[11px] text-[#64748B]">
                    <Clock className="w-3 h-3" />
                    <span>{evt.time}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Quick Interceptor Callout */}
          <div className="mt-4 p-3 rounded-lg bg-[#0F172A] border border-[#5B8C9E]/30">
            <div className="flex items-center gap-2 text-xs font-semibold text-[#5B8C9E]">
              <Sparkles className="w-4 h-4" />
              <span>Self-Healing Engine Active</span>
            </div>
            <p className="text-[11px] text-[#94A3B8] mt-1 leading-relaxed">
              DriftShield interceptors are actively monitoring schema contracts for 6 microservices.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
