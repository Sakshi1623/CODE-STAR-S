import React, { useState } from 'react';
import { Search, Bell, Shield, ChevronDown, Check, RefreshCw } from 'lucide-react';
import { useApp } from '../../context/AppContext';

export const Header: React.FC = () => {
  const { 
    searchQuery, 
    setSearchQuery, 
    settings, 
    updateSettings,
    patchApplied,
    rollbackPatch,
    applyPatch
  } = useApp();
  const [profileOpen, setProfileOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);

  return (
    <header className="h-16 bg-[#1E293B] border-b border-[#334155]/60 px-6 flex items-center justify-between sticky top-0 z-10 select-none">
      {/* Search Bar */}
      <div className="relative w-80 md:w-96">
        <Search className="w-4 h-4 text-[#94A3B8] absolute left-3.5 top-1/2 -translate-y-1/2" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search endpoints, services, schemas..."
          className="w-full bg-[#0F172A] border border-[#334155] rounded-lg pl-10 pr-4 py-2 text-sm text-white placeholder-[#64748B] focus:outline-none focus:border-[#5B8C9E] transition-colors"
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery('')}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-[#64748B] hover:text-white"
          >
            Clear
          </button>
        )}
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-3">
        {/* Mock API Version Quick Switcher */}
        <div className="hidden sm:flex items-center gap-1.5 bg-[#0F172A] border border-[#334155] rounded-lg p-1 text-xs">
          <span className="text-[#64748B] px-2 font-medium">Mock API:</span>
          <button
            onClick={() => updateSettings({ mockApiVersion: 'v1' })}
            className={`px-2.5 py-1 rounded font-semibold transition-all ${
              settings.mockApiVersion === 'v1'
                ? 'bg-[#5B8C9E] text-white shadow-sm'
                : 'text-[#94A3B8] hover:text-white'
            }`}
          >
            V1
          </button>
          <button
            onClick={() => updateSettings({ mockApiVersion: 'v2' })}
            className={`px-2.5 py-1 rounded font-semibold transition-all ${
              settings.mockApiVersion === 'v2'
                ? 'bg-[#5B8C9E] text-white shadow-sm'
                : 'text-[#94A3B8] hover:text-white'
            }`}
          >
            V2 (Drift)
          </button>
        </div>

        {/* Patch Status Indicator */}
        <button
          onClick={() => (patchApplied ? rollbackPatch() : applyPatch())}
          className={`hidden md:flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border transition-all ${
            patchApplied
              ? 'bg-[#0D9488]/15 border-[#0D9488]/40 text-[#0D9488]'
              : 'bg-[#F59E0B]/15 border-[#F59E0B]/40 text-[#F59E0B]'
          }`}
          title="Toggle Self-Healing Interceptor"
        >
          {patchApplied ? (
            <>
              <Check className="w-3.5 h-3.5" />
              <span>Interceptor: Healed</span>
            </>
          ) : (
            <>
              <RefreshCw className="w-3.5 h-3.5 animate-spin-slow" />
              <span>Drift Intercept Active</span>
            </>
          )}
        </button>

        {/* Runtime Interceptor Status Badge */}
        <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#0F172A] border border-[#334155] text-xs">
          <div className="w-2 h-2 rounded-full bg-[#0D9488] animate-pulse"></div>
          <span className="text-[#94A3B8]">Runtime Interceptor:</span>
          <span className="text-[#5B8C9E] font-semibold">Active</span>
        </div>

        {/* Notification Bell */}
        <div className="relative">
          <button
            onClick={() => setNotificationsOpen(!notificationsOpen)}
            className="w-9 h-9 rounded-lg bg-[#0F172A] border border-[#334155] flex items-center justify-center text-[#94A3B8] hover:text-white hover:border-[#5B8C9E] transition-colors relative"
            title="Notifications"
          >
            <Bell className="w-4 h-4" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-[#F59E0B] rounded-full"></span>
          </button>

          {/* Notifications Dropdown */}
          {notificationsOpen && (
            <div className="absolute right-0 mt-2 w-80 bg-[#1E293B] border border-[#334155] rounded-xl shadow-2xl p-4 text-xs z-50">
              <div className="flex items-center justify-between pb-3 border-b border-[#334155]">
                <span className="font-semibold text-white">System Alerts</span>
                <span className="text-[10px] text-[#5B8C9E] cursor-pointer hover:underline">Mark all read</span>
              </div>
              <div className="mt-3 space-y-2.5 max-h-60 overflow-y-auto">
                <div className="p-2.5 rounded-lg bg-[#0F172A] border border-[#F59E0B]/30">
                  <div className="font-medium text-[#F59E0B] flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#F59E0B]"></span>
                    Payment Service Schema Drift
                  </div>
                  <p className="text-[#94A3B8] mt-1 text-[11px]">Field 'currency' omitted in payload from v2/checkout.</p>
                  <span className="text-[10px] text-[#64748B] mt-1 block">5m ago</span>
                </div>
                <div className="p-2.5 rounded-lg bg-[#0F172A] border border-[#0D9488]/30">
                  <div className="font-medium text-[#0D9488] flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#0D9488]"></span>
                    Self-Healing Interceptor Active
                  </div>
                  <p className="text-[#94A3B8] mt-1 text-[11px]">User service payload patched without downtime.</p>
                  <span className="text-[10px] text-[#64748B] mt-1 block">18m ago</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* User Profile */}
        <div className="relative">
          <button
            onClick={() => setProfileOpen(!profileOpen)}
            className="flex items-center gap-2 pl-2 pr-3 py-1.5 rounded-lg bg-[#0F172A] border border-[#334155] hover:border-[#5B8C9E] transition-colors"
          >
            <div className="w-7 h-7 rounded-full bg-[#5B8C9E]/20 border border-[#5B8C9E] flex items-center justify-center text-xs font-bold text-[#5B8C9E]">
              DS
            </div>
            <div className="hidden sm:block text-left text-xs leading-tight">
              <div className="font-semibold text-white">SecOps Lead</div>
              <div className="text-[10px] text-[#64748B]">enterprise-admin</div>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-[#64748B]" />
          </button>

          {profileOpen && (
            <div className="absolute right-0 mt-2 w-56 bg-[#1E293B] border border-[#334155] rounded-xl shadow-2xl py-2 text-xs z-50">
              <div className="px-4 py-2 border-b border-[#334155]">
                <p className="font-semibold text-white">Security Operations</p>
                <p className="text-[11px] text-[#94A3B8] truncate">secops@driftshield.io</p>
              </div>
              <div className="py-1">
                <button 
                  onClick={() => { setProfileOpen(false); }}
                  className="w-full text-left px-4 py-2 text-[#94A3B8] hover:text-white hover:bg-[#0F172A] flex items-center gap-2"
                >
                  <Shield className="w-3.5 h-3.5 text-[#5B8C9E]" />
                  Zero-Trust Policy
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
