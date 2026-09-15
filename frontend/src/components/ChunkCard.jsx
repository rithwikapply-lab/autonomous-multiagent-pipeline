import React, { useState } from 'react';
import { FileText, Copy, Check, Hash } from 'lucide-react';

export default function ChunkCard({ chunk, index }) {
  const [copied, setCopied] = useState(false);

  const title = chunk.metadata?.title || `Document ${chunk.doc_id ? chunk.doc_id.slice(0, 8) : 'Source'}`;
  const chunkIndex = chunk.chunk_index !== undefined ? chunk.chunk_index : index;
  const score = chunk.rerank_score !== undefined 
    ? chunk.rerank_score 
    : (chunk.score !== null && chunk.score !== undefined ? chunk.score : null);

  const handleCopy = () => {
    navigator.clipboard.writeText(chunk.content || '');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      style={{ animationDelay: `${index * 120}ms` }}
      className="glass-panel-interactive rounded-xl p-4 animate-fade-in-up space-y-3 relative group"
    >
      {/* Top Meta Bar */}
      <div className="flex items-center justify-between gap-2 flex-wrap text-xs">
        <div className="flex items-center gap-2">
          <span className="p-1 rounded-md bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            <FileText className="w-3.5 h-3.5" />
          </span>
          <span className="font-semibold text-white truncate max-w-[200px] sm:max-w-xs">
            {title}
          </span>
          <span className="text-[10px] text-slate-400 font-mono bg-white/5 px-2 py-0.5 rounded">
            Chunk #{chunkIndex}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {score !== null && (
            <span className="text-[11px] font-mono font-medium px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
              Score: {typeof score === 'number' ? score.toFixed(3) : score}
            </span>
          )}
          <button
            onClick={handleCopy}
            className="p-1 rounded text-slate-400 hover:text-white transition-colors"
            title="Copy chunk text"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* Chunk Excerpt */}
      <div className="text-xs sm:text-sm text-slate-300 leading-relaxed font-sans bg-black/20 p-3 rounded-lg border border-white/5">
        "{chunk.content}"
      </div>
    </div>
  );
}
