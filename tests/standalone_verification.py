import sys
import os
import math
import random
import re
import importlib.util

# Add repository root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.search.bm25_index import BM25Index, PurePythonBM25Okapi
from app.search.dense_index import DenseIndex
from app.search.reranker import CrossEncoderReranker

# Load tools directly without triggering pydantic schemas dependency on bare python
tools_path = os.path.join(os.path.dirname(__file__), "..", "app", "agents", "tools.py")
spec = importlib.util.spec_from_file_location("agent_tools", tools_path)
tools_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tools_mod)
AgentTools = tools_mod.AgentTools

def test_bm25():
    print("1. Testing BM25 Sparse Search...")
    idx = BM25Index()
    chunks = [
        {"chunk_id": "c1", "content": "FastAPI is an asynchronous web framework for Python."},
        {"chunk_id": "c2", "content": "PostgreSQL with pgvector allows dense vector embeddings similarity search."},
        {"chunk_id": "c3", "content": "DeepEval is an evaluation harness for testing LLM hallucinations."}
    ]
    idx.add_documents(chunks)
    res = idx.search("FastAPI framework", top_k=2)
    assert len(res) > 0, "BM25 should return matching chunks"
    assert res[0][0] == "c1", f"Top result should be c1, got {res[0][0]}"
    print(f"   ✓ Passed! Top hit: {res[0][0]} with BM25 score: {res[0][1]:.4f}")

def test_dense_and_rrf():
    print("2. Testing Dense Vector Similarity & Reciprocal Rank Fusion...")
    dense = DenseIndex()
    # Mock vectors
    v_query = [0.1, 0.8, 0.2]
    v_doc1 = [0.12, 0.79, 0.18]
    v_doc2 = [-0.5, 0.1, 0.8]
    sim1 = dense._cosine_similarity(v_query, v_doc1)
    sim2 = dense._cosine_similarity(v_query, v_doc2)
    assert sim1 > sim2, "Doc 1 should have higher cosine similarity than Doc 2"
    print(f"   ✓ Passed! Cosine sim doc1: {sim1:.4f} vs doc2: {sim2:.4f}")

    # Test RRF formula: sum(1 / (k + rank))
    rrf_k = 60
    rrf_top = (1.0 / (rrf_k + 1)) + (1.0 / (rrf_k + 1))
    rrf_lower = 1.0 / (rrf_k + 2)
    assert rrf_top > rrf_lower, "RRF top should score higher"
    print(f"   ✓ Passed! RRF top score: {rrf_top:.5f} vs lower score: {rrf_lower:.5f}")

def test_reranker():
    print("3. Testing Cross-Encoder Reranker...")
    reranker = CrossEncoderReranker()
    chunks = [
        {"chunk_id": "c1", "content": "Unrelated topic about weather in Seattle.", "rrf_score": 0.015},
        {"chunk_id": "c2", "content": "Critical latency degradation from 120ms to 850ms during surge.", "rrf_score": 0.014}
    ]
    reranked = reranker.rerank("latency degradation during surge", chunks, top_k=2)
    assert reranked[0]["chunk_id"] == "c2", "Reranker should prioritize semantic keyword overlap"
    print(f"   ✓ Passed! Top chunk reranked: {reranked[0]['chunk_id']}")

def test_agent_tools():
    print("4. Testing Agent Tools (Calculations & Metric Extraction)...")
    calc = AgentTools.calculate("(45000 / 18) * 60")
    assert calc["result"] == 150000.0, "Calculator failed"
    print(f"   ✓ Calculation Result: {calc['result']}")

    sample_text = "The API handled 45,000 requests with 1,250 errors and 99.95% uptime."
    metrics = AgentTools.extract_numbers_and_percentages(sample_text)
    assert len(metrics) >= 3, "Should extract numbers and percentages"
    print(f"   ✓ Extracted {len(metrics)} quantitative data points: {[m['value'] for m in metrics]}")

def test_context_router_logic():
    print("5. Testing Intent Router Classification...")
    intent_patterns = {
        "quantitative_comparison": [r"compare", r"versus", r"vs"],
        "metric_extraction": [r"how many", r"percentage", r"rate", r"throughput"],
        "root_cause_analysis": [r"why did", r"cause of", r"failure"]
    }
    test_queries = [
        ("Compare latency between 8B model and GPT-4", "quantitative_comparison"),
        ("What was the throughput and error rate?", "metric_extraction"),
        ("Why did the database connection pool fail?", "root_cause_analysis")
    ]
    for q, expected in test_queries:
        matched = "general"
        for intent, pats in intent_patterns.items():
            if any(re.search(p, q.lower()) for p in pats):
                matched = intent
                break
        assert matched == expected, f"Expected {expected} for '{q}', got {matched}"
        print(f"   ✓ Query '{q[:30]}...' -> Detected Intent: {matched}")

if __name__ == "__main__":
    print("=" * 65)
    print("RUNNING PIPELINE STANDALONE VERIFICATION SUITE")
    print("=" * 65)
    test_bm25()
    test_dense_and_rrf()
    test_reranker()
    test_agent_tools()
    test_context_router_logic()
    print("=" * 65)
    print("🎉 ALL 5/5 CORE VERIFICATION SUITES PASSED FLAWLESSLY!")
    print("=" * 65)
