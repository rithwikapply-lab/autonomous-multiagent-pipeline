import React from 'react';
import { Database, FileText, Search, RefreshCw, Calendar } from 'lucide-react';

export default function IndexedDocs({ documents, loading, onRefresh, onQueryDocument }) {
  return (
    <div className="w-full max-w-4xl mx-auto my-6 p-5 sm:p-6 rounded-2xl glass-panel border border-white/10 space-y-4 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <Database className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm sm:text-base font-semibold text-white flex items-center gap-2">
              Currently Indexed Knowledge Base
              <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-300 font-mono font-medium border border-purple-500/20">
                {documents.length} {documents.length === 1 ? 'doc' : 'docs'}
              </span>
            </h3>
            <p className="text-xs text-slate-400">
              Documents persistently embedded in pgvector and indexed in BM25
            </p>
          </div>
        </div>

        <button
          onClick={onRefresh}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white/5 hover:bg-white/10 text-slate-300 transition-colors disabled:opacity-50 cursor-pointer"
          title="Refresh indexed documents list"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Document Grid */}
      {documents.length === 0 ? (
        <div className="p-6 text-center text-xs text-slate-500 bg-black/20 rounded-xl border border-dashed border-white/10">
          No documents currently indexed. Use the form above to add your first document.
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {documents.map((doc) => (
            <div
              key={doc.doc_id}
              className="p-3.5 rounded-xl bg-slate-900/60 border border-white/10 hover:border-purple-500/30 transition-all duration-200 flex flex-col justify-between space-y-3 group"
            >
              <div className="space-y-1.5">
                <div className="flex items-start justify-between gap-2">
                  <span className="font-semibold text-xs sm:text-sm text-white group-hover:text-cyan-300 transition-colors line-clamp-1">
                    {doc.title}
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/20 shrink-0">
                    {doc.chunks_count || 1} {doc.chunks_count === 1 ? 'chunk' : 'chunks'}
                  </span>
                </div>
                <div className="text-[10px] text-slate-500 font-mono truncate">
                  ID: {doc.doc_id.slice(0, 12)}...
                </div>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-white/5">
                <div className="flex items-center gap-1 text-[10px] text-slate-500">
                  <Calendar className="w-3 h-3" />
                  <span>{doc.created_at ? new Date(doc.created_at).toLocaleDateString() : 'Seeded'}</span>
                </div>
                <button
                  onClick={() => onQueryDocument(doc.title)}
                  className="flex items-center gap-1 text-[11px] font-medium text-cyan-400 hover:text-cyan-300 transition-colors cursor-pointer"
                  title={`Query about ${doc.title}`}
                >
                  <Search className="w-3 h-3" />
                  <span>Ask about this</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
