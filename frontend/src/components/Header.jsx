import React from 'react';
import { Sparkles, Cpu, ShieldCheck, Zap, Server, Activity } from 'lucide-react';

export default function Header({ backendHealth }) {
  const isOnline = backendHealth?.online;

  return (
    <header className="relative pt-6 pb-4 border-b border-white/10">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 flex flex-col md:flex-row items-center justify-between gap-4">
        {/* Brand & Title */}
        <div className="flex items-center gap-3.5 text-center md:text-left">
          <div className="w-11 h-11 rounded-xl bg-gradient-to-tr from-cyan-500 to-indigo-600 flex items-center justify-center glow-cyan shadow-lg shadow-cyan-500/20">
            <Sparkles className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="flex items-center justify-center md:justify-start gap-2">
              <h1 className="text-xl sm:text-2xl font-bold bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
                Autonomous Multi-Agent RAG
              </h1>
              <span className="text-xs px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-medium">
                v2.0
              </span>
            </div>
            <p className="text-xs sm:text-sm text-slate-400">
              Hybrid Search (BM25 + pgvector) • Cross-Encoder Reranker • Redis Cache • NLI Verifier
            </p>
          </div>
        </div>

        {/* Live System Status Badges */}
        <div className="flex flex-wrap items-center justify-center gap-2 text-xs">
          {/* Backend Status */}
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full glass-panel border border-white/10">
            <span className="relative flex h-2 w-2">
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${isOnline ? 'bg-emerald-400' : 'bg-rose-400'}`} />
              <span className={`relative inline-flex rounded-full h-2 w-2 ${isOnline ? 'bg-emerald-500' : 'bg-rose-500'}`} />
            </span>
            <span className="text-slate-300 font-medium">
              API: {isOnline ? 'Online (:8000)' : 'Offline'}
            </span>
          </div>

          {/* Redis Cache Indicator */}
          <div className="flex items-center gap-1 px-3 py-1.5 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 font-medium">
            <Zap className="w-3.5 h-3.5" />
            <span>Redis L1 Cache</span>
          </div>

          {/* Semantic Verifier Indicator */}
          <div className="flex items-center gap-1 px-3 py-1.5 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 font-medium">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Tier 2 NLI Audit</span>
          </div>
        </div>
      </div>
    </header>
  );
}
