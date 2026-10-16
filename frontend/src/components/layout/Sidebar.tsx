import React from 'react';
import { 
  LayoutDashboard, 
  Activity, 
  GitCompare, 
  ClipboardList, 
  BarChart3, 
  Wrench, 
  Settings, 
  ShieldCheck,
  CheckCircle2
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import type { NavigationTab } from '../../types';

interface NavItem {
  id: NavigationTab;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
}

const navItems: NavItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'api-monitor', label: 'API Monitor', icon: Activity, badge: 'Live' },
  { id: 'schema-diff', label: 'Schema Diff', icon: GitCompare },
  { id: 'recovery-logs', label: 'Recovery Logs', icon: ClipboardList },
  { id: 'evaluation', label: 'Evaluation', icon: BarChart3 },
  { id: 'tool-registry', label: 'Tool Registry', icon: Wrench },
  { id: 'settings', label: 'Settings', icon: Settings },
];

export const Sidebar: React.FC = () => {
  const { currentTab, setCurrentTab } = useApp();

  return (
    <aside className="w-64 bg-[#1E293B] border-r border-[#334155]/60 flex flex-col shrink-0 min-h-screen select-none z-20">
      {/* Brand Header */}
      <div className="h-16 px-5 flex items-center justify-between border-b border-[#334155]/60">
        <button 
          onClick={() => setCurrentTab('dashboard')}
          className="flex items-center gap-2.5 text-left group focus:outline-none"
        >
          <div className="w-9 h-9 rounded-lg bg-[#0F172A] border border-[#5B8C9E]/40 flex items-center justify-center text-[#5B8C9E] group-hover:border-[#5B8C9E] transition-colors">
            <ShieldCheck className="w-5 h-5 text-[#5B8C9E]" />
          </div>
          <div>
            <div className="font-bold text-white text-base tracking-wide flex items-center gap-1.5">
              DriftShield
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#5B8C9E]/20 text-[#5B8C9E] font-semibold uppercase">SaaS</span>
            </div>
            <p className="text-[11px] text-[#94A3B8] font-medium leading-none">Self-Healing Registry</p>
          </div>
        </button>
      </div>

      {/* Navigation List */}
      <nav className="p-3 space-y-1 flex-1">
        <div className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-[#64748B]">
          Navigation
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setCurrentTab(item.id)}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                isActive
                  ? 'bg-[#0F172A] text-white border-l-4 border-[#5B8C9E] shadow-sm'
                  : 'text-[#94A3B8] hover:text-white hover:bg-[#0F172A]/50'
              }`}
            >
              <div className="flex items-center gap-3">
                <Icon
                  className={`w-4 h-4 transition-colors ${
                    isActive ? 'text-[#5B8C9E]' : 'text-[#64748B]'
                  }`}
                />
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-[#0D9488]/20 text-[#0D9488] border border-[#0D9488]/30">
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Sidebar Footer - Clean System Status */}
      <div className="p-4 border-t border-[#334155]/60 bg-[#16202E]">
        <div className="flex items-center gap-3 p-2.5 rounded-lg bg-[#0F172A] border border-[#334155]/70">
          <div className="w-2.5 h-2.5 rounded-full bg-[#0D9488] animate-pulse shrink-0"></div>
          <div className="min-w-0">
            <div className="text-[10px] text-[#64748B] uppercase font-bold tracking-wider leading-none">
              SYSTEM STATUS
            </div>
            <div className="text-xs font-semibold text-white tracking-wide truncate mt-0.5">
              Continuous Defense Active
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
};
