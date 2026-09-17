# Autonomous Multi-Agent Analysis Pipeline

A reference implementation of an asynchronous Multi-Agent Analysis Pipeline powered by **FastAPI**, **PostgreSQL (`pgvector`)**, **Hybrid Search (BM25 + Dense Embeddings)**, **Cross-Encoder Reranking**, and **DeepEval / LangSmith Verification**. The system coordinates three specialized agents—Context Routing, Research Synthesis, and Adversarial Verification—to ingest unstructured documents, retrieve multi-angle evidence via reciprocal rank fusion, and return structured, verifiable analytical summaries.

---

## Architecture Diagram

```
                              ┌────────────────────────────────────────┐
                              │  User Analytical Query / Document Ingest │
                              └────────────────────┬───────────────────┘
                                                   │
                                                   ▼
                                      ┌────────────────────────┐
                                      │    FastAPI Endpoint    │
                                      │ (/ingest, /query, /sse)│
                                      └────────────┬───────────┘
                                                   │
                             ┌─────────────────────┴─────────────────────┐
                             ▼                                           ▼
                 ┌───────────────────────┐                   ┌───────────────────────┐
                 │  Sparse BM25 Index    │                   │  Dense Vector Search  │
                 │  (Exact keyword match)│                   │ (PostgreSQL + pgvector)│
                 └───────────┬───────────┘                   └───────────┬───────────┘
                             │                                           │
                             └─────────────────────┬─────────────────────┘
                                                   ▼
                                     ┌───────────────────────────┐
                                     │   Reciprocal Rank Fusion  │
                                     │       (RRF Score)         │
                                     └─────────────┬─────────────┘
                                                   ▼
                                     ┌───────────────────────────┐
                                     │   Cross-Encoder Reranker  │
                                     │  (+18% retrieval precision)│
                                     └─────────────┬─────────────┘
                                                   ▼
                                     ┌───────────────────────────┐
                                     │   Context Router Agent    │
                                     │  (Dynamic intent routing) │
                                     └─────────────┬─────────────┘
                                                   ▼
                                     ┌───────────────────────────┐
                                     │   Research Synthesis Agent│
                                     │(Tool use & Pydantic JSON) │
                                     └─────────────┬─────────────┘
                                                   ▼
                                     ┌───────────────────────────┐
                                     │  Verifier & Grounding Agent│
                                     │ (Faithfulness & Halluc. check)
                                     └─────────────┬─────────────┘
                                                   ▼
                                      Verified Analytical Report
```

---

## Engineering Notes: What I Found and Fixed

During development, rigorous testing against adversarial queries and edge cases revealed several critical flaws in retrieval, verification, caching, and ingestion. Below is a factual breakdown of what went wrong, how each was diagnosed, and how it was fixed and verified in code.

1. **Hallucination via Fallback on Unrelated Queries & Empty Knowledge Sets**
   - **What was wrong:** When an incoming query had no relevant documentation in the knowledge base (or when retrieval returned zero chunks), the pipeline fell back to heuristic text generation. This fabricated plausible-sounding claims and metrics instead of honestly admitting the system lacked information. Furthermore, the reranker forced `reranked[:1]` to return even if candidate scores were completely disjoint (e.g. returning refund policy chunks for cryptocurrency queries).
   - **How it was diagnosed:** Tested out-of-domain queries (e.g. *"What is your policy on cryptocurrency payments?"*) against the seeded corpus. The system retrieved the Return Policy and generated confident assertions about 30-day refunds for cryptocurrency, which the verifier incorrectly passed.
   - **How it was fixed & tested:**
     - Enforced a neural relevance score cutoff ($> -5.0$) in `app/search/reranker.py` to prune off-topic candidates before synthesis.
     - Updated `app/agents/research_agent.py` to check for substantive query keywords in retrieved context. If chunks are empty or disjoint, it sets `executive_summary: "I don't have information about this in the provided documents."`, `confidence_score: 0.0`, `key_metrics: []`, and `verifiable_claims: []`.
     - Updated `app/agents/verifier_agent.py` to check topical alignment and confirm that honest admissions of missing information are verified as faithful (`is_faithful: true`, `hallucination_score: 0.0`).
     - Covered by `tests/test_regression_suite.py::test_hallucination_fallback_unrelated_query` and `tests/test_regression_suite.py::test_hallucination_fallback_direct_empty_chunks`.

2. **Verifier False Positives on Grounded-but-Misleading Claims (NLI Entailment Upgrade)**
   - **What was wrong:** The original `VerifierAgent` relied strictly on bag-of-words keyword overlap (`ratio >= 0.6`) and raw substring searching. This gave false confidence on adversarial claims that shared source vocabulary but completely altered meaning—such as dropping restrictive condition qualifiers (e.g. turning *"Refund requests after 30 days are evaluated case-by-case and are not guaranteed"* into *"Refunds are not guaranteed"*), misattributing numerical figures to the wrong entity across sentence boundaries, or asserting unsupported inferences.
   - **How it was diagnosed:** Constructed adversarial test cases against real corpus chunks. The keyword-overlap verifier marked dropped qualifiers and swapped subscription tier numbers as 100% faithful (`hallucination_score: 0.0`) because the raw tokens existed in the source paragraph.
   - **How it was fixed & tested:**
     - Replaced shallow keyword-only checking with a two-tier verification architecture in `app/agents/verifier_agent.py`: Tier 1 uses fast token overlap as a pre-filter (<0.1ms); Tier 2 evaluates surviving claims against sentence candidates using a local cross-encoder NLI model (`cross-encoder/nli-deberta-v3-small`).
     - Added an explicit condition guard regex checking for dropped restricting clauses (`after \d+ days`, `case-by-case`, `only if`, `unless`, `for disaster recovery`) and enforced localized sentence-level metric binding.
     - Calibrated and verified against an 8-case benchmark covering dropped qualifiers, misattributed numbers, direct-match SLAs, and subjective spin.
     - Covered by `tests/test_regression_suite.py::test_verifier_calibration_benchmark`.

3. **Untested Malformed & Adversarial Input Handling**
   - **What was wrong:** Edge-case input handling—including empty queries, oversized query payloads (20,000+ characters), non-UTF8 / garbled Unicode symbols, SQL injection fragments, invalid retrieval parameters (negative `top_k`), and querying against empty document stores—was completely untested, leaving the API vulnerable to unhandled 500 exceptions.
   - **How it was diagnosed:** Sent malformed, extreme-length, and boundary payloads to `/api/v1/query`. Initial runs revealed unconstrained schema parameters (e.g., negative `top_k`) and empty strings triggering uncaught exceptions in agent token extraction.
   - **How it was fixed & tested:**
     - Added Pydantic field constraints (`top_k: int = Field(default=5, ge=1)`) returning HTTP 422 for invalid parameters.
     - Hardened router, reranker, and synthesis tokenization to handle empty, long, or symbol-only inputs gracefully without crashing, returning valid `QueryResponse` structures.
     - Covered by `tests/test_regression_suite.py::test_malformed_input_empty_query`, `test_malformed_input_extremely_long_query`, `test_malformed_input_garbled_unicode_and_injection`, `test_malformed_input_empty_document_store`, and `test_malformed_input_invalid_top_k_returns_422`.

4. **Unwired & Unverified Redis Response Caching**
   - **What was wrong:** While a Redis container was defined in `docker-compose.yml`, query response caching was implemented as an in-memory dictionary stub in `app/api/query.py`. Cached entries did not persist across API container restarts, had no TTL-based eviction, and lacked automated tests verifying cache hits versus misses or latency differences.
   - **How it was diagnosed:** Audited `app/api/query.py` and inspected Redis container keys with `redis-cli`. Observed that query cache was wiped whenever the API worker restarted and keys were never written to Redis.
   - **How it was fixed & tested:**
     - Replaced the in-memory dictionary with persistent `redis.asyncio` caching, serializing `QueryResponse` models with a 1-hour TTL (`ex=3600`) keyed on `f"{query}_{top_k}_{enable_reranking}"`.
     - Wrapped Redis lookups and writes in graceful fallback handlers so connection timeouts or offline Redis instances log a warning and fall back to live execution without failing the user's request.
     - Added automated test assertions confirming cold queries execute with `cached: false` while repeated queries return `cached: true` with sub-10ms response times (`t2 < 10.0ms`).
     - Covered by `tests/test_regression_suite.py::test_cache_hit_and_latency_reduction`.

5. **Unbounded Ingestion Payload Size & Embedding Cost Exposure**
   - **What was wrong:** The `POST /api/v1/ingest` endpoint had no maximum size limit on `text_content`. An incoming payload of several megabytes would trigger unbounded dense embedding compute, high OpenAI API billing, memory exhaustion during chunk generation, and potential Denial-of-Service. Additionally, empty or whitespace-only documents were accepted without validation.
   - **How it was diagnosed:** Audited `app/api/ingest.py`. Found that payloads of arbitrary length passed directly into `chunk_text()` and were queued for vector embedding without payload guardrails.
   - **How it was fixed & tested:**
     - Implemented a server-side guardrail: `MAX_TEXT_CONTENT_CHARS = 50,000`. Requests exceeding this limit return HTTP 413 (Payload Too Large) with a detailed error message; empty or whitespace-only payloads return HTTP 400.
     - Added client-side character counting with real-time warning states (>90% warning, >100% submit blocking) in `frontend/src/components/DocumentIngest.jsx`.
     - Added `GET /api/v1/documents` endpoint to query and return currently indexed documents and chunk counts from pgvector.
     - Covered by `tests/test_regression_suite.py::test_ingestion_guardrail_empty_text_returns_400`, `test_ingestion_guardrail_whitespace_returns_400`, `test_ingestion_guardrail_over_50k_chars_returns_413`, and `test_ingestion_success_document_listing_and_query_verification` (with automated test-document cleanup fixtures).

## Quickstart Guide

### 1. Run with Docker Compose (Recommended)
```bash
# Clone and enter directory
cd autonomous_multiagent_pipeline

# Copy environment template
cp .env.example .env

# Spin up pgvector, Redis, and FastAPI in one command
docker compose up -d --build
```
The API is live at `http://localhost:8000`. Interactive OpenAPI documentation is available at `http://localhost:8000/docs`.

---

### 2. Run Locally (Python 3.11+)
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## API Endpoints

### 1. Ingest Document
`POST /api/v1/ingest`
```json
{
  "title": "Incident Postmortem",
  "text_content": "The API gateway experienced 45,000 requests per second, resulting in 1,250 HTTP 504 errors.",
  "chunk_size": 500,
  "chunk_overlap": 50
}
```

### 2. Query Analysis
`POST /api/v1/query`
```json
{
  "query": "What was the peak request rate and how many 504 errors occurred?",
  "top_k": 5,
  "enable_reranking": true,
  "enable_verification": true
}
```

### 3. Real-Time Streaming
`GET /api/v1/stream?query=Compare+latency+and+costs`
Streams real-time Server-Sent Events (SSE) detailing agent thoughts, tool executions, and final structured synthesis.

---

## Running the Evaluation Benchmark

To benchmark faithfulness, retrieval recall, and extraction accuracy:
```bash
python evals/run_evals.py
```
Sample benchmark output:
```
======================================================================
📊 BENCHMARK EVALUATION SUMMARY REPORT
======================================================================
Total Queries Evaluated:    3
Average Pipeline Latency:   18.45 ms
Faithfulness Score:         100.0%
Metric Extraction Accuracy: 100.0%
Hallucination Rate:         0.0%
======================================================================
```

---

## Evaluation Data

The dataset in `evals/test_dataset.json` is synthetic — illustrative queries and metrics used to demonstrate the evaluation harness (ground-truth matching, metric extraction), not measurements from a deployed or production system.

> **Note on Performance Figures:** Specific numerical figures cited throughout this README (including the sample benchmark metrics above, +18% retrieval precision, sub-200ms P95 latency target, and 30%+ cache savings) are illustrative/target values from the synthetic eval harness, not measured results from a production deployment.

---

## Running Unit Tests
```bash
pytest tests/ -v
```
