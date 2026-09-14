import re
import math
from typing import List, Dict, Tuple

try:
    from rank_bm25 import BM25Okapi as ExternalBM25Okapi
except ImportError:
    ExternalBM25Okapi = None

class PurePythonBM25Okapi:
    """Pure Python implementation of BM25Okapi algorithm for zero-dependency portability."""
    def __init__(self, corpus: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.doc_lengths = [len(doc) for doc in corpus]
        self.avgdl = sum(self.doc_lengths) / self.corpus_size if self.corpus_size > 0 else 1.0
        self.doc_freqs: Dict[str, int] = {}
        self.doc_term_freqs: List[Dict[str, int]] = []

        for doc in corpus:
            term_freq = {}
            for term in doc:
                term_freq[term] = term_freq.get(term, 0) + 1
            self.doc_term_freqs.append(term_freq)
            for term in term_freq:
                self.doc_freqs[term] = self.doc_freqs.get(term, 0) + 1

        self.idf: Dict[str, float] = {}
        for term, freq in self.doc_freqs.items():
            # BM25 standard IDF with smoothing
            self.idf[term] = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)

    def get_scores(self, query: List[str]) -> List[float]:
        scores = [0.0] * self.corpus_size
        for term in query:
            if term not in self.idf:
                continue
            idf = self.idf[term]
            for i in range(self.corpus_size):
                tf = self.doc_term_freqs[i].get(term, 0)
                if tf == 0:
                    continue
                num = tf * (self.k1 + 1.0)
                denom = tf + self.k1 * (1.0 - self.b + self.b * (self.doc_lengths[i] / self.avgdl))
                scores[i] += idf * (num / denom)
        return scores

class BM25Index:
    """In-memory inverted index and BM25 scorer for sparse lexical keyword retrieval."""

    def __init__(self):
        self.chunk_ids: List[str] = []
        self.corpus: List[str] = []
        self.tokenized_corpus: List[List[str]] = []
        self.bm25 = None

    @staticmethod
    def tokenize(text: str) -> List[str]:
        return re.findall(r'\b[a-zA-Z0-9_]+\b', text.lower())

    def add_documents(self, chunks: List[Dict[str, str]]):
        """Adds chunks: [{'chunk_id': ..., 'content': ...}] and updates index."""
        for chunk in chunks:
            if chunk["chunk_id"] not in self.chunk_ids:
                self.chunk_ids.append(chunk["chunk_id"])
                self.corpus.append(chunk["content"])
                self.tokenized_corpus.append(self.tokenize(chunk["content"]))

        if self.tokenized_corpus:
            if ExternalBM25Okapi:
                self.bm25 = ExternalBM25Okapi(self.tokenized_corpus)
            else:
                self.bm25 = PurePythonBM25Okapi(self.tokenized_corpus)

    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        if not self.bm25 or not self.chunk_ids:
            return []

        tokenized_query = self.tokenize(query)
        if not tokenized_query:
            return []

        scores = self.bm25.get_scores(tokenized_query)
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        results = []
        for idx in ranked_indices:
            if scores[idx] > 0.0:
                results.append((self.chunk_ids[idx], float(scores[idx])))
        return results

bm25_index = BM25Index()
