import React, { useState, useRef } from 'react';
import { 
  UploadCloud, 
  FileText, 
  Edit3, 
  CheckCircle2, 
  AlertCircle, 
  Loader2, 
  Search, 
  X, 
  ArrowRight,
  Info
} from 'lucide-react';
import { ingestDocument } from '../api/pipelineApi';

const MAX_CHARS = 50000;

export default function DocumentIngest({ onIngestSuccess, onSelectSuggestedQuery }) {
  const [tab, setTab] = useState('paste'); // 'paste' | 'file'
  const [title, setTitle] = useState('');
  const [textContent, setTextContent] = useState('');
  const [fileName, setFileName] = useState('');
  const [fileSize, setFileSize] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [successResult, setSuccessResult] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  const fileInputRef = useRef(null);

  const charCount = textContent.length;
  const isOverLimit = charCount > MAX_CHARS;
  const isApproachingLimit = charCount > MAX_CHARS * 0.9 && !isOverLimit;

  // File handling for .txt files
  const handleFile = (file) => {
    setErrorMessage(null);
    setSuccessResult(null);

    if (!file) return;

    if (!file.name.endsWith('.txt') && file.type !== 'text/plain') {
      setErrorMessage('Unsupported file format. Please upload a plain text (.txt) file.');
      return;
    }

    // Auto-set title from file name if empty
    if (!title.trim()) {
      const cleanName = file.name.replace(/\.txt$/i, '').replace(/[_-]/g, ' ');
      setTitle(cleanName.charAt(0).toUpperCase() + cleanName.slice(1));
    }

    setFileName(file.name);
    setFileSize((file.size / 1024).toFixed(1) + ' KB');

    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target.result || '';
      setTextContent(text);
      if (text.length > MAX_CHARS) {
        setErrorMessage(`File exceeds the 50,000-character limit (${text.length.toLocaleString()} characters).`);
      }
    };
    reader.onerror = () => {
      setErrorMessage('Failed to read file content.');
    };
    reader.readAsText(file);
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileInputChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const clearFile = () => {
    setFileName('');
    setFileSize('');
    setTextContent('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage(null);
    setSuccessResult(null);

    if (!title.trim()) {
      setErrorMessage('Document title is required.');
      return;
    }

    if (!textContent.trim()) {
      setErrorMessage('Document content cannot be empty.');
      return;
    }

    if (isOverLimit) {
      setErrorMessage(`Payload exceeds limit of ${MAX_CHARS.toLocaleString()} characters.`);
      return;
    }

    setLoading(true);
    try {
      const res = await ingestDocument({
        title: title.trim(),
        text_content: textContent.trim(),
      });

      setSuccessResult({
        title: title.trim(),
        chunksCreated: res.chunks_created,
        docId: res.doc_id,
        suggestedQuery: `What does the ${title.trim()} document cover?`,
      });

      // Clear input fields
      setTitle('');
      setTextContent('');
      setFileName('');
      setFileSize('');

      if (onIngestSuccess) {
        onIngestSuccess(res);
      }
    } catch (err) {
      setErrorMessage(err.message || 'Failed to ingest document.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto my-6 p-5 sm:p-6 rounded-2xl glass-panel border border-white/10 space-y-5 animate-fade-in-up">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            <UploadCloud className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base sm:text-lg font-bold text-white">
              Add Your Own Documents
            </h3>
            <p className="text-xs text-slate-400">
              Chunk, embed into pgvector, and index in real-time (Plain text & .txt files)
            </p>
          </div>
        </div>

        {/* Mode Tabs */}
        <div className="flex items-center p-1 rounded-xl bg-black/40 border border-white/10 text-xs font-medium">
          <button
            type="button"
            onClick={() => { setTab('paste'); setErrorMessage(null); }}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-colors cursor-pointer ${
              tab === 'paste'
                ? 'bg-cyan-500 text-black font-bold shadow-md shadow-cyan-500/20'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Edit3 className="w-3.5 h-3.5" />
            <span>Paste Text</span>
          </button>
          <button
            type="button"
            onClick={() => { setTab('file'); setErrorMessage(null); }}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-colors cursor-pointer ${
              tab === 'file'
                ? 'bg-cyan-500 text-black font-bold shadow-md shadow-cyan-500/20'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Upload .txt File</span>
          </button>
        </div>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Title Input */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
            Document Title <span className="text-rose-400">*</span>
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Employee Travel Policy, Security Whitepaper, Q3 Incident Report..."
            disabled={loading}
            className="w-full px-4 py-2.5 rounded-xl bg-dark-900/90 border border-white/10 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400 transition-colors"
          />
        </div>

        {/* Tab 1: Paste Text */}
        {tab === 'paste' && (
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Document Text Content <span className="text-rose-400">*</span>
              </label>
              <div
                className={`text-xs font-mono font-medium ${
                  isOverLimit
                    ? 'text-rose-400 font-bold animate-pulse'
                    : isApproachingLimit
                    ? 'text-amber-400'
                    : 'text-slate-400'
                }`}
              >
                {charCount.toLocaleString()} / {MAX_CHARS.toLocaleString()} chars
              </div>
            </div>
            <textarea
              rows={6}
              value={textContent}
              onChange={(e) => setTextContent(e.target.value)}
              placeholder="Paste raw text, knowledge articles, SLA guidelines, or engineering notes here..."
              disabled={loading}
              className="w-full px-4 py-3 rounded-xl bg-dark-900/90 border border-white/10 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400 transition-colors resize-y font-sans leading-relaxed"
            />
          </div>
        )}

        {/* Tab 2: Upload .txt File */}
        {tab === 'file' && (
          <div className="space-y-2">
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Text Document (.txt only) <span className="text-rose-400">*</span>
              </label>
              <span className="text-xs text-slate-500">Max size: 50,000 characters (~50KB)</span>
            </div>

            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`relative p-6 sm:p-8 rounded-xl border-2 border-dashed transition-all duration-200 text-center cursor-pointer ${
                dragActive
                  ? 'border-cyan-400 bg-cyan-500/10'
                  : 'border-white/15 bg-black/20 hover:border-cyan-400/50 hover:bg-white/[0.02]'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,text/plain"
                onChange={handleFileInputChange}
                className="hidden"
              />

              {fileName ? (
                <div className="flex items-center justify-center gap-3">
                  <FileText className="w-8 h-8 text-cyan-400" />
                  <div className="text-left">
                    <div className="font-semibold text-sm text-white">{fileName}</div>
                    <div className="text-xs text-slate-400 font-mono">
                      {fileSize} • {charCount.toLocaleString()} characters
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      clearFile();
                    }}
                    className="p-1 rounded-md text-slate-400 hover:text-white bg-white/10"
                    title="Remove file"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  <UploadCloud className="w-9 h-9 mx-auto text-slate-400" />
                  <div className="text-sm font-medium text-slate-200">
                    Drop a <span className="text-cyan-400 font-mono">.txt</span> file here, or browse
                  </div>
                  <div className="text-[11px] text-slate-500">
                    Plain text documents only (no PDF or binary formats supported)
                  </div>
                </div>
              )}
            </div>

            {/* Character counter for uploaded file */}
            {charCount > 0 && (
              <div className="flex justify-end text-xs font-mono">
                <span className={isOverLimit ? 'text-rose-400 font-bold' : 'text-slate-400'}>
                  Loaded: {charCount.toLocaleString()} / {MAX_CHARS.toLocaleString()} chars
                </span>
              </div>
            )}
          </div>
        )}

        {/* Error Alert */}
        {errorMessage && (
          <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 flex items-start gap-2.5 text-xs sm:text-sm animate-fade-in">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <div className="flex-1 font-medium">{errorMessage}</div>
          </div>
        )}

        {/* Success Alert & Suggested Query */}
        {successResult && (
          <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 space-y-3 animate-fade-in">
            <div className="flex items-start gap-2.5 text-xs sm:text-sm text-emerald-200">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-bold">Document Successfully Ingested!</span>
                <p className="text-xs text-emerald-300/80 mt-0.5">
                  Created <span className="font-mono font-bold text-emerald-200">{successResult.chunksCreated}</span> chunk(s) 
                  with dense vector embeddings in <span className="font-mono text-emerald-200">pgvector</span> and sparse index in <span className="font-mono text-emerald-200">BM25</span>.
                </p>
              </div>
            </div>

            {/* Suggested Query Action Button */}
            <div className="pt-2 border-t border-emerald-500/20 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
              <span className="text-xs text-slate-300 flex items-center gap-1.5">
                <Search className="w-3.5 h-3.5 text-cyan-400" />
                <span>Suggested Query:</span>
                <span className="font-medium text-white">"{successResult.suggestedQuery}"</span>
              </span>
              <button
                type="button"
                onClick={() => onSelectSuggestedQuery(successResult.suggestedQuery)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-black font-semibold text-xs transition-transform active:scale-95 cursor-pointer shadow-md shadow-cyan-500/20"
              >
                <span>Try This Query Now</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

        {/* Submit Ingestion Button */}
        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={loading || !title.trim() || !textContent.trim() || isOverLimit}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium text-xs sm:text-sm text-white bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 active:scale-95 disabled:opacity-40 disabled:pointer-events-none transition-all duration-200 shadow-lg shadow-cyan-500/20 cursor-pointer"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Embedding & Persisting to pgvector...</span>
              </>
            ) : (
              <>
                <UploadCloud className="w-4 h-4" />
                <span>Index Document</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
