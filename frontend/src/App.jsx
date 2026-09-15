import React, { useState, useEffect, useRef } from 'react';
import Header from './components/Header';
import PresetQueries from './components/PresetQueries';
import QueryInput from './components/QueryInput';
import LoadingPipeline from './components/LoadingPipeline';
import AnswerCard from './components/AnswerCard';
import BehindTheScenes from './components/BehindTheScenes';
import DocumentIngest from './components/DocumentIngest';
import IndexedDocs from './components/IndexedDocs';
import { queryPipeline, checkBackendHealth, fetchIndexedDocuments, BASE_URL } from './api/pipelineApi';
import { AlertCircle, RefreshCw } from 'lucide-react';

export default function App() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [response, setResponse] = useState(null);
  const [backendHealth, setBackendHealth] = useState(null);
  const [indexedDocs, setIndexedDocs] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(false);

  const [settings, setSettings] = useState({
    top_k: 5,
    enable_reranking: true,
    enable_verification: true,
  });

  const queryInputRef = useRef(null);

  const loadDocuments = async () => {
    setLoadingDocs(true);
    try {
      const docs = await fetchIndexedDocuments();
      setIndexedDocs(docs);
    } catch (err) {
      console.warn('Failed to fetch indexed documents:', err);
    } finally {
      setLoadingDocs(false);
    }
  };

  // Check health and load documents on mount
  useEffect(() => {
    let mounted = true;
    const pollHealth = async () => {
      const health = await checkBackendHealth();
      if (mounted) setBackendHealth(health);
    };
    pollHealth();
    loadDocuments();
    const interval = setInterval(pollHealth, 15000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const handleExecuteQuery = async (overrideQuery) => {
    const q = (overrideQuery || query).trim();
    if (!q) return;

    if (overrideQuery) {
      setQuery(overrideQuery);
    }

    setLoading(true);
    setError(null);

    try {
      const result = await queryPipeline({
        query: q,
        top_k: settings.top_k,
        enable_reranking: settings.enable_reranking,
        enable_verification: settings.enable_verification,
      });
      setResponse(result);
    } catch (err) {
      console.error('Query execution failed:', err);
      setError(err.message || 'Failed to reach backend pipeline API.');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectSuggestedQuery = (suggestedQ) => {
    setQuery(suggestedQ);
    window.scrollTo({ top: 0, behavior: 'smooth' });
    handleExecuteQuery(suggestedQ);
  };

  const handleQueryDocumentTopic = (docTitle) => {
    const q = `What are the details regarding ${docTitle}?`;
    setQuery(q);
    window.scrollTo({ top: 0, behavior: 'smooth' });
    handleExecuteQuery(q);
  };

  return (
    <div className="min-h-screen flex flex-col justify-between">
      {/* Header */}
      <Header backendHealth={backendHealth} />

      {/* Main Container */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-8 space-y-8">
        {/* Intro Tagline */}
        <div className="text-center max-w-2xl mx-auto">
          <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            Real-Time Factual Verification Engine
          </h2>
          <p className="mt-2 text-xs sm:text-sm text-slate-400">
            Query across enterprise knowledge with hybrid BM25 + dense pgvector retrieval, 
            neural cross-attention reranking, Redis persistent cache, and NLI entailment auditing.
          </p>
        </div>

        {/* Section 1: Query & Analysis */}
        <div className="space-y-4">
          {/* Query Input Box */}
          <QueryInput
            query={query}
            setQuery={setQuery}
            onSubmit={() => handleExecuteQuery()}
            loading={loading}
            settings={settings}
            setSettings={setSettings}
          />

          {/* Preset Query Pills */}
          <PresetQueries
            onSelect={(preset) => handleExecuteQuery(preset)}
            disabled={loading}
          />
        </div>

        {/* Error Notification */}
        {error && (
          <div className="w-full max-w-4xl mx-auto p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 flex items-start gap-3 animate-fade-in">
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
            <div className="flex-1 text-xs sm:text-sm">
              <span className="font-semibold block">Pipeline Error</span>
              <span>{error}</span>
              <div className="mt-2 flex items-center gap-2">
                <button
                  onClick={() => handleExecuteQuery()}
                  className="px-3 py-1 rounded bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 text-xs font-medium transition-colors cursor-pointer flex items-center gap-1.5"
                >
                  <RefreshCw className="w-3 h-3" />
                  <span>Retry Query</span>
                </button>
                <span className="text-[11px] text-rose-400/80">API Target: {BASE_URL}</span>
              </div>
            </div>
          </div>
        )}

        {/* Loading Pipeline State */}
        {loading && <LoadingPipeline />}

        {/* Answer Presentation */}
        {!loading && response && <AnswerCard response={response} />}

        {/* Behind the Scenes Telemetry Trace */}
        {!loading && response && <BehindTheScenes response={response} />}

        {/* Section 2: Document Ingestion */}
        <div className="pt-6 border-t border-white/10 space-y-6">
          <DocumentIngest
            onIngestSuccess={() => loadDocuments()}
            onSelectSuggestedQuery={handleSelectSuggestedQuery}
          />

          {/* Section 3: Currently Indexed Documents */}
          <IndexedDocs
            documents={indexedDocs}
            loading={loadingDocs}
            onRefresh={loadDocuments}
            onQueryDocument={handleQueryDocumentTopic}
          />
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-white/5 py-5 text-center text-xs text-slate-500">
        <div className="max-w-6xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <span>Autonomous Multi-Agent Pipeline • Reference Implementation</span>
          <div className="flex items-center gap-2 text-[11px] font-mono text-slate-400">
            <span>FastAPI: :8000</span>
            <span>•</span>
            <span>pgvector: :5432</span>
            <span>•</span>
            <span>Redis: :6379</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
