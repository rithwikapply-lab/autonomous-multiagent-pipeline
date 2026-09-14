import pytest
import asyncio
from app.search.bm25_index import BM25Index
from app.search.hybrid_retriever import HybridRetriever
from app.search.reranker import CrossEncoderReranker

def test_bm25_sparse_search():
    index = BM25Index()
    chunks = [
        {"chunk_id": "c1", "content": "PostgreSQL with pgvector provides dense vector search capabilities."},
        {"chunk_id": "c2", "content": "FastAPI is a modern asynchronous Python web framework for building APIs."},
        {"chunk_id": "c3", "content": "BM25 is an effective sparse lexical keyword ranking algorithm."}
    ]
    index.add_documents(chunks)
    
    results = index.search("fastapi web framework", top_k=2)
    assert len(results) > 0
    assert results[0][0] == "c2"

def test_cross_encoder_reranker():
    reranker = CrossEncoderReranker()
    chunks = [
        {"chunk_id": "c1", "content": "The weather today in San Francisco is foggy and cold."},
        {"chunk_id": "c2", "content": "FastAPI endpoints can serve streaming tokens using Server-Sent Events."},
        {"chunk_id": "c3", "content": "Database indexes optimize query execution time."}
    ]
    reranked = reranker.rerank("fastapi streaming tokens", chunks, top_k=2)
    assert len(reranked) == 2
    assert reranked[0]["chunk_id"] == "c2"
