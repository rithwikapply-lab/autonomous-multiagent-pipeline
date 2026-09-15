import React, { useEffect, useState } from 'react';
import { Database, Filter, Cpu, ShieldCheck, Loader2 } from 'lucide-react';

const STAGES = [
  { id: 1, label: 'Context Routing & Hybrid Search', desc: 'BM25 sparse + pgvector dense via RRF', icon: Database },
  { id: 2, label: 'Cross-Encoder Reranking', desc: 'Dual-condition neural relevance filtering', icon: Filter },
  { id: 3, label: 'Autonomous Research Synthesis', desc: 'Factual extraction & quantitative metric parsing', icon: Cpu },
  { id: 4, label: 'Tier 2 Semantic Verification', desc: 'DeBERTa NLI entailment & condition guard audit', icon: ShieldCheck },
];

export default function LoadingPipeline() {
  const [activeStage, setActiveStage] = useState(1);

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveStage((prev) => (prev < 4 ? prev + 1 : prev));
    }, 900);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="w-full max-w-4xl mx-auto my-6 p-6 rounded-2xl glass-panel border border-cyan-500/20 glow-cyan animate-fade-in">
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2.5">
          <Loader2 className="w-5 h-5 text-cyan-400 animate-spin" />
          <h3 className="text-sm sm:text-base font-semibold text-white">
            Autonomous Pipeline Executing...
          </h3>
        </div>
        <span className="text-xs font-mono text-cyan-300 px-2.5 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/20">
          Stage {activeStage} of 4
        </span>
      </div>

      {/* Progress Track */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
        {STAGES.map((stage) => {
          const Icon = stage.icon;
          const isDone = activeStage > stage.id;
          const isCurrent = activeStage === stage.id;

          return (
            <div
              key={stage.id}
              className={`p-3.5 rounded-xl border transition-all duration-300 ${
                isCurrent
                  ? 'bg-gradient-to-b from-cyan-500/15 to-indigo-500/10 border-cyan-400 shadow-md shadow-cyan-500/20 scale-[1.02]'
                  : isDone
                  ? 'bg-white/[0.04] border-emerald-500/40 text-emerald-400'
                  : 'bg-white/[0.01] border-white/5 opacity-40'
              }`}
            >
              <div className="flex items-center gap-2 mb-1.5">
                <div
                  className={`w-6 h-6 rounded-lg flex items-center justify-center text-xs ${
                    isCurrent
                      ? 'bg-cyan-500 text-black font-bold animate-pulse'
                      : isDone
                      ? 'bg-emerald-500/20 text-emerald-300'
                      : 'bg-slate-800 text-slate-400'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                </div>
                <span className="text-xs font-semibold truncate text-slate-200">
                  {stage.label}
                </span>
              </div>
              <p className="text-[10px] text-slate-400 line-clamp-2">
                {stage.desc}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
