import React, { useState } from 'react';
import { Search, SlidersHorizontal, ArrowRight, Loader2, X, RefreshCw } from 'lucide-react';

export default function QueryInput({
  query,
  setQuery,
  onSubmit,
  loading,
  settings,
  setSettings,
}) {
  const [showSettings, setShowSettings] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!query.trim() || loading) return;
    onSubmit();
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto">
      <form onSubmit={handleSubmit} className="relative">
        <div className="relative rounded-2xl p-[1px] bg-gradient-to-r from-cyan-500/40 via-indigo-500/40 to-purple-500/40 focus-within:from-cyan-400 focus-within:via-indigo-400 focus-within:to-purple-400 transition-all duration-300 shadow-xl shadow-cyan-950/20">
          <div className="flex items-center gap-2 bg-dark-900/90 backdrop-blur-xl rounded-2xl px-4 py-2.5 sm:py-3.5">
            {/* Search Icon */}
            <div className="text-slate-400 pl-1">
              <Search className="w-5 h-5 text-cyan-400" />
            </div>

            {/* Input Element */}
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a factual question across documents (e.g., refund policies, specs, security)..."
              disabled={loading}
              className="flex-1 bg-transparent text-sm sm:text-base text-white placeholder-slate-500 focus:outline-none disabled:opacity-60"
            />

            {/* Clear Button */}
            {query && !loading && (
              <button
                type="button"
                onClick={() => setQuery('')}
                className="text-slate-400 hover:text-white p-1 rounded-md transition-colors"
                title="Clear input"
              >
                <X className="w-4 h-4" />
              </button>
            )}

            {/* Advanced Settings Toggle Button */}
            <button
              type="button"
              onClick={() => setShowSettings(!showSettings)}
              className={`p-2 rounded-xl transition-all ${
                showSettings
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                  : 'text-slate-400 hover:text-white hover:bg-white/5'
              }`}
              title="Pipeline parameters"
            >
              <SlidersHorizontal className="w-4 h-4" />
            </button>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={!query.trim() || loading}
              className="group relative flex items-center justify-center gap-2 px-4 sm:px-6 py-2 sm:py-2.5 rounded-xl font-medium text-xs sm:text-sm text-white bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 active:scale-95 disabled:opacity-40 disabled:pointer-events-none transition-all duration-200 shadow-lg shadow-indigo-500/25 cursor-pointer"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-white" />
                  <span className="hidden sm:inline">Analyzing...</span>
                </>
              ) : (
                <>
                  <span>Run Query</span>
                  <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
                </>
              )}
            </button>
          </div>
        </div>

        {/* Collapsible Advanced Settings Drawer */}
        {showSettings && (
          <div className="mt-3 p-4 rounded-xl glass-panel border border-white/10 text-xs sm:text-sm animate-fade-in-up space-y-4">
            <div className="flex items-center justify-between border-b border-white/5 pb-2">
              <span className="font-semibold text-white flex items-center gap-1.5">
                <SlidersHorizontal className="w-4 h-4 text-cyan-400" />
                Pipeline Execution Parameters
              </span>
              <span className="text-xs text-slate-400">Live API Flags</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {/* top_k Slider */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs text-slate-300">
                  <span>Top Candidates (top_k)</span>
                  <span className="font-mono text-cyan-400 font-bold">{settings.top_k}</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="10"
                  value={settings.top_k}
                  onChange={(e) =>
                    setSettings({ ...settings, top_k: parseInt(e.target.value, 10) })
                  }
                  className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-cyan-400"
                />
                <p className="text-[11px] text-slate-500">Max chunks passed to synthesis</p>
              </div>

              {/* Reranker Toggle */}
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-white/[0.03] border border-white/5">
                <div>
                  <div className="font-medium text-slate-200 text-xs">Cross-Encoder Reranking</div>
                  <div className="text-[10px] text-slate-400">Neural dual-condition filter</div>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    setSettings({ ...settings, enable_reranking: !settings.enable_reranking })
                  }
                  className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out ${
                    settings.enable_reranking ? 'bg-cyan-500' : 'bg-slate-700'
                  }`}
                >
                  <span
                    className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                      settings.enable_reranking ? 'translate-x-4' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>

              {/* Verifier Toggle */}
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-white/[0.03] border border-white/5">
                <div>
                  <div className="font-medium text-slate-200 text-xs">Tier 2 Semantic Verifier</div>
                  <div className="text-[10px] text-slate-400">DeBERTa NLI & condition audit</div>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    setSettings({
                      ...settings,
                      enable_verification: !settings.enable_verification,
                    })
                  }
                  className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out ${
                    settings.enable_verification ? 'bg-indigo-500' : 'bg-slate-700'
                  }`}
                >
                  <span
                    className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                      settings.enable_verification ? 'translate-x-4' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>
            </div>
          </div>
        )}
      </form>
    </div>
  );
}
