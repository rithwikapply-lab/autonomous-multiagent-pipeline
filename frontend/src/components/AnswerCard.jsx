import React from 'react';
import { CheckCircle2, AlertTriangle, Hash, FileText, Award } from 'lucide-react';

export default function AnswerCard({ response }) {
  if (!response || !response.analysis) return null;

  const { analysis, verification } = response;
  const isNoInfo = analysis.executive_summary?.toLowerCase().includes("don't have information") ||
                   analysis.executive_summary?.toLowerCase().includes("no information");

  return (
    <div className="w-full max-w-4xl mx-auto my-6 animate-fade-in-up">
      <div className="relative rounded-2xl glass-panel border border-white/15 overflow-hidden shadow-2xl shadow-indigo-950/40">
        {/* Top Accent Gradient Bar */}
        <div className={`h-1.5 w-full ${isNoInfo ? 'bg-gradient-to-r from-amber-500 to-rose-500' : 'bg-gradient-to-r from-cyan-400 via-indigo-500 to-purple-500'}`} />

        <div className="p-5 sm:p-7 space-y-6">
          {/* Header Row */}
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 glow-cyan animate-pulse" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Synthesized Answer & Findings
              </h2>
            </div>

            {analysis.confidence_score !== undefined && (
              <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs font-mono">
                <Award className="w-3.5 h-3.5 text-cyan-400" />
                <span className="text-slate-400">Confidence:</span>
                <span className="text-cyan-300 font-bold">
                  {(analysis.confidence_score * 100).toFixed(0)}%
                </span>
              </div>
            )}
          </div>

          {/* Executive Summary Block */}
          <div className={`p-4 sm:p-5 rounded-xl border ${
            isNoInfo 
              ? 'bg-rose-500/10 border-rose-500/30 text-rose-200'
              : 'bg-white/[0.03] border-white/10 text-slate-100'
          }`}>
            <p className="text-base sm:text-lg leading-relaxed font-normal">
              {analysis.executive_summary}
            </p>
            {isNoInfo && (
              <p className="mt-2 text-xs text-rose-300/80 flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                <span>Knowledge base evaluated. No off-topic hallucinations injected.</span>
              </p>
            )}
          </div>

          {/* Quantitative Metrics Row */}
          {analysis.key_metrics && analysis.key_metrics.length > 0 && (
            <div className="space-y-2.5">
              <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400">
                <Hash className="w-3.5 h-3.5 text-indigo-400" />
                <span>Extracted Quantitative Metrics</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                {analysis.key_metrics.map((metric, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-xl bg-slate-900/80 border border-indigo-500/20 hover:border-indigo-400/40 transition-colors"
                  >
                    <div className="text-xl sm:text-2xl font-bold font-mono text-cyan-300">
                      {metric.value}
                    </div>
                    <div className="text-xs text-slate-300 font-medium truncate mt-0.5">
                      {metric.metric_name}
                    </div>
                    {metric.confidence && (
                      <div className="text-[10px] text-slate-500 mt-1">
                        Confidence: {(metric.confidence * 100).toFixed(0)}%
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Verifiable Claims */}
          {analysis.verifiable_claims && analysis.verifiable_claims.length > 0 && (
            <div className="space-y-2.5 pt-2 border-t border-white/5">
              <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400">
                <FileText className="w-3.5 h-3.5 text-emerald-400" />
                <span>Grounded Factual Assertions</span>
              </div>
              <ul className="space-y-2">
                {analysis.verifiable_claims.map((claim, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-2.5 text-xs sm:text-sm text-slate-200 bg-white/[0.02] p-2.5 rounded-lg border border-white/5"
                  >
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                    <span className="leading-snug">{claim}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
