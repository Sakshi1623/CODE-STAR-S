import React, { useState } from 'react';
import { 
  ShieldCheck, 
  ArrowRight, 
  Play, 
  X, 
  CheckCircle2 
} from 'lucide-react';
import { useApp } from '../../context/AppContext';

export const SplashScreen: React.FC = () => {
  const { setShowSplash, setCurrentTab, applyPatch, showToast } = useApp();
  const [demoPlaying, setDemoPlaying] = useState(false);
  const [demoStep, setDemoStep] = useState(0);

  const startDemo = () => {
    setDemoPlaying(true);
    setDemoStep(1);
    showToast('Demo Step 1: Simulating runtime schema drift injection...');
    setTimeout(() => {
      setDemoStep(2);
      showToast('Demo Step 2: Interceptor detected parameter mismatch!');
    }, 2000);
    setTimeout(() => {
      setDemoStep(3);
      applyPatch();
      showToast('Demo Step 3: Zero-Touch Self-Healing patch synthesized & applied!');
    }, 4000);
    setTimeout(() => {
      setDemoPlaying(false);
      setDemoStep(0);
      setShowSplash(false);
      setCurrentTab('dashboard');
    }, 6000);
  };

  return (
    <div className="fixed inset-0 z-50 bg-[#0F172A] flex flex-col justify-between overflow-y-auto select-none p-6 md:p-12">
      {/* Top Header */}
      <div className="flex items-center justify-between w-full max-w-6xl mx-auto">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-[#1E293B] border border-[#5B8C9E]/50 flex items-center justify-center">
            <ShieldCheck className="w-5 h-5 text-[#5B8C9E]" />
          </div>
          <span className="font-bold text-white text-lg tracking-wide">DriftShield</span>
        </div>

        <button
          onClick={() => setShowSplash(false)}
          className="w-8 h-8 rounded-lg bg-[#1E293B] hover:bg-[#334155] border border-[#334155] text-[#94A3B8] hover:text-white flex items-center justify-center transition-colors"
          title="Enter Dashboard"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Hero Center */}
      <div className="my-auto py-12 flex flex-col items-center text-center max-w-3xl mx-auto">
        {/* Layered Security Shield Visual */}
        <div className="relative mb-8 flex items-center justify-center">
          {/* Subtle Outer Concentric Rings */}
          <div className="absolute w-56 h-56 rounded-full border border-[#5B8C9E]/20 animate-spin-slow"></div>
          <div className="absolute w-44 h-44 rounded-full border border-[#5B8C9E]/30 border-dashed"></div>

          {/* Central Shield Container */}
          <div className="relative w-32 h-32 rounded-2xl bg-[#1E293B] border-2 border-[#5B8C9E] shadow-2xl flex items-center justify-center z-10 transition-transform hover:scale-105 duration-300">
            <ShieldCheck className="w-16 h-16 text-[#5B8C9E]" />
          </div>
        </div>

        {/* Title and Tagline */}
        <h1 className="text-3xl md:text-5xl font-extrabold text-white tracking-tight leading-tight">
          DriftShield –
        </h1>
        <h2 className="text-xl md:text-3xl font-semibold text-[#94A3B8] mt-2 max-w-2xl">
          Self-Healing API Registries under Runtime Schema Drift
        </h2>

        {/* Demo Status Banner if running */}
        {demoPlaying && (
          <div className="mt-6 p-3 rounded-lg bg-[#1E293B] border border-[#0D9488] text-xs text-[#0D9488] flex items-center gap-2 animate-pulse">
            <CheckCircle2 className="w-4 h-4" />
            <span>
              {demoStep === 1 && 'Simulating breaking payload from /v2/users...'}
              {demoStep === 2 && 'Detecting schema mutation without downtime...'}
              {demoStep === 3 && 'Self-Healing patch deployed! Redirecting to Dashboard...'}
            </span>
          </div>
        )}

        {/* Action Buttons */}
        <div className="mt-8 flex flex-col sm:flex-row items-center gap-4">
          <button
            onClick={() => {
              setShowSplash(false);
              setCurrentTab('dashboard');
            }}
            className="w-full sm:w-auto px-8 py-3.5 rounded-xl bg-[#5B8C9E] hover:bg-[#4E7A8B] text-white font-bold text-sm flex items-center justify-center gap-2 transition-all shadow-lg hover:shadow-[#5B8C9E]/20 hover:scale-[1.02]"
          >
            <span>Get Started</span>
            <ArrowRight className="w-4 h-4" />
          </button>

          <button
            onClick={startDemo}
            disabled={demoPlaying}
            className="w-full sm:w-auto px-8 py-3.5 rounded-xl bg-[#1E293B] hover:bg-[#283548] border border-[#334155] text-white font-semibold text-sm flex items-center justify-center gap-2 transition-all hover:scale-[1.02]"
          >
            <Play className="w-4 h-4 text-[#5B8C9E]" />
            <span>{demoPlaying ? 'Playing Demo...' : 'Watch Demo'}</span>
          </button>
        </div>
      </div>

      {/* Bottom Footer */}
      <div className="w-full max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between text-xs text-[#64748B] pt-6 border-t border-[#334155]/60 gap-4">
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded bg-[#5B8C9E]/20 flex items-center justify-center">
            <ShieldCheck className="w-3.5 h-3.5 text-[#5B8C9E]" />
          </div>
          <span className="font-semibold text-[#94A3B8]">DriftShield Autonomous Defense</span>
        </div>

        <div>
          Production-Ready Autonomous Cybersecurity SaaS • Real-Time Zero-Touch Adaptation
        </div>
      </div>
    </div>
  );
};
