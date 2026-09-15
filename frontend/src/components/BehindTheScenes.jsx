import React, { useState } from 'react';
import { 
  ChevronDown, 
  ChevronUp, 
  Layers, 
  Clock, 
  Zap, 
  ShieldCheck, 
  ShieldAlert, 
  Sparkles,
  Info
} from 'lucide-react';
import ChunkCard from './ChunkCard';

export default function BehindTheScenes({ response }) {
  const [isOpen, setIsOpen] = useState(true);

  if (!response) return null;

  const {
    retrieved_chunks = [],
    verification,
    execution_time_ms,
    cached = false,
  } = response;

  const isFaithful = verification?.is_faithful;
  const hallucinationScore = verification?.hallucination_score ?? 0;
  const isSubTenMs = execution_time_ms !== undefined && execution_time_ms < 10;

  return (
    <div className="w-full max-w-4xl mx-auto my-6 animate-fade-in-up">
      <div className="rounded-2xl glass-panel border border-white/10 overflow-hidden shadow-xl">
        {/* Toggle Bar */}
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="w-full flex items-center justify-between p-4 sm:p-5 bg-white/[0.02] hover:bg-white/[0.05] transition-colors cursor-pointer text-left"
        >
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-gradient-to-tr from-cyan-500/20 to-indigo-500/20 text-cyan-400 border border-cyan-500/30">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm sm:text-base font-semibold text-white flex items-center gap-2">
                Behind the Scenes: Multi-Agent Pipeline Trace
              </h3>
              <p className="text-xs text-slate-400">
                Inspect live retrieval chunks, Redis cache telemetry, and NLI verification report
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-xs font-mono text-slate-400 hidden sm:inline">
              {isOpen ? 'Collapse Trace' : 'Expand Trace'}
            </span>
            <div className="p-1 rounded-md bg-white/5 text-slate-300">
              {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </div>
          </div>
        </button>

        {/* Expandable Content Body */}
        {isOpen && (
          <div className="p-5 sm:p-6 space-y-6 border-t border-white/5">
            {/* Live Stats Ribbon */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {/* 1. Execution Latency */}
              <div className="p-3.5 rounded-xl bg-slate-900/60 border border-white/10 flex flex-col justify-between">
                <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
                  <span>Latency</span>
                  <Clock className="w-3.5 h-3.5 text-cyan-400" />
                </div>
                <div className="flex items-baseline gap-1">
                  <span className={`text-xl sm:text-2xl font-bold font-mono ${isSubTenMs ? 'text-emerald-400' : 'text-white'}`}>
                    {execution_time_ms !== undefined ? execution_time_ms : '--'}
                  </span>
                  <span className="text-xs text-slate-400">ms</span>
                </div>
                <span className="text-[10px] text-slate-500 mt-0.5">
                  {isSubTenMs ? '⚡ Near-instant lookup' : 'Full pipeline execution'}
                </span>
              </div>

              {/* 2. Redis Cache Status */}
              <div className={`p-3.5 rounded-xl border flex flex-col justify-between ${
                cached 
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' 
                  : 'bg-cyan-500/10 border-cyan-500/30 text-cyan-300'
              }`}>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-slate-300">Cache Layer</span>
                  <Zap className={`w-3.5 h-3.5 ${cached ? 'text-emerald-400 animate-pulse' : 'text-cyan-400'}`} />
                </div>
                <div className="text-sm sm:text-base font-bold uppercase tracking-wide">
                  {cached ? 'Cache Hit' : 'Fresh Compute'}
                </div>
                <span className="text-[10px] opacity-80 mt-0.5">
                  {cached ? 'Loaded from Redis (TTL: 1h)' : 'Live RRF & synthesis'}
                </span>
              </div>

              {/* 3. Faithfulness Indicator Gauge */}
              <div className={`p-3.5 rounded-xl border flex flex-col justify-between ${
                isFaithful 
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                  : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
              }`}>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-slate-300">Faithfulness</span>
                  {isFaithful ? (
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  ) : (
                    <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
                  )}
                </div>
                <div className="text-sm sm:text-base font-bold">
                  {isFaithful ? '100% Faithful' : 'Flagged Unfaithful'}
                </div>
                <span className="text-[10px] opacity-80 mt-0.5">
                  Hallucination score: {hallucinationScore}
                </span>
              </div>

              {/* 4. Chunks Count */}
              <div className="p-3.5 rounded-xl bg-slate-900/60 border border-white/10 flex flex-col justify-between">
                <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
                  <span>Context</span>
                  <Layers className="w-3.5 h-3.5 text-purple-400" />
                </div>
                <div className="text-xl sm:text-2xl font-bold font-mono text-white">
                  {retrieved_chunks.length}
                </div>
                <span className="text-[10px] text-slate-500 mt-0.5">
                  Document chunks reranked
                </span>
              </div>
            </div>

            {/* Verification Audit Breakdown */}
            {verification && (
              <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-cyan-400" />
                    VerifierAgent Audit Report
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-mono font-medium ${
                    isFaithful ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
                  }`}>
                    {isFaithful ? 'AUDIT PASSED' : 'FLAGGED UNVERIFIED'}
                  </span>
                </div>

                {verification.verified_claims && verification.verified_claims.length > 0 && (
                  <div className="text-xs space-y-1">
                    <span className="text-slate-400 font-medium">Verified claims:</span>
                    <div className="flex flex-wrap gap-1.5">
                      {verification.verified_claims.map((claim, idx) => (
                        <span key={idx} className="px-2 py-1 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 text-[11px]">
                          ✓ {claim}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {verification.unsupported_claims && verification.unsupported_claims.length > 0 && (
                  <div className="text-xs space-y-1">
                    <span className="text-rose-400 font-medium">Flagged unsupported claims:</span>
                    <div className="flex flex-wrap gap-1.5">
                      {verification.unsupported_claims.map((claim, idx) => (
                        <span key={idx} className="px-2 py-1 rounded bg-rose-500/10 text-rose-300 border border-rose-500/20 text-[11px]">
                          ✕ {claim}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {verification.suggested_corrections && (
                  <div className="text-[11px] text-amber-300/90 bg-amber-500/10 p-2.5 rounded-lg border border-amber-500/20">
                    <span className="font-semibold">Suggested Correction:</span> {verification.suggested_corrections}
                  </div>
                )}
              </div>
            )}

            {/* Retrieved Chunks Section */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                  <Layers className="w-4 h-4 text-purple-400" />
                  Retrieved & Reranked Context Chunks
                </span>
                <span className="text-xs text-slate-500">
                  {retrieved_chunks.length === 0 ? 'No matching chunks found' : `${retrieved_chunks.length} chunks ordered by relevance`}
                </span>
              </div>

              {retrieved_chunks.length === 0 ? (
                <div className="p-6 rounded-xl bg-black/20 border border-dashed border-white/10 text-center text-xs text-slate-400 space-y-1">
                  <Info className="w-5 h-5 mx-auto text-slate-500 mb-1" />
                  <p className="font-medium text-slate-300">No document chunks passed relevance threshold.</p>
                  <p className="text-[11px] text-slate-500">The query was correctly classified as outside the knowledge base.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {retrieved_chunks.map((chunk, idx) => (
                    <ChunkCard key={chunk.chunk_id || idx} chunk={chunk} index={idx} />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
