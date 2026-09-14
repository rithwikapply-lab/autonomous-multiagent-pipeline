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

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such", "than",
    "that", "that's", "the", "their", "theirs", "them", "themselves", "then",
    "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've",
    "this", "those", "through", "to", "too", "under", "until", "up", "very", "was",
    "wasn't", "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what",
    "what's", "when", "when's", "where", "where's", "which", "while", "who",
    "who's", "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you",
    "you'd", "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves"
}

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
            self.bm25 = PurePythonBM25Okapi(self.tokenized_corpus)

    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        if not self.bm25 or not self.chunk_ids:
            return []

        all_tokens = self.tokenize(query)
        # Prioritize informative keywords by removing stopwords
        content_tokens = [w for w in all_tokens if w not in STOP_WORDS]
        tokenized_query = content_tokens if content_tokens else all_tokens
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
