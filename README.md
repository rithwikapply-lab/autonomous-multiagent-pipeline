# Autonomous Multi-Agent Analysis Pipeline

A reference implementation of an asynchronous Multi-Agent Analysis Pipeline powered by **FastAPI**, **PostgreSQL (`pgvector`)**, **Hybrid Search (BM25 + Dense Embeddings)**, **Cross-Encoder Reranking**, and **DeepEval / LangSmith Verification**.

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

## Key Features

1. **Autonomous Multi-Agent Workflow:**
   - **ContextRouter:** Analyzes incoming queries, detects intent (quantitative comparison, metric extraction, root-cause analysis), and formulates multi-angle retrieval sub-queries.
   - **ResearchAgent:** Synthesizes evidence, extracts quantitative metrics, and enforces strict Pydantic JSON schemas (`AnalyticalSummary`).
   - **VerifierAgent:** Adversarial fact-checking agent that audits every generated claim against retrieved source chunks to reduce hallucinations.

2. **State-of-the-Art Hybrid Search:**
   - **Sparse Lexical Search:** Tokenized BM25Okapi for exact terminology, acronyms, and error codes.
   - **Dense Vector Search:** Cosine similarity via PostgreSQL `pgvector`.
   - **Reciprocal Rank Fusion (RRF):** Blends rankings using $RRF(d) = \sum \frac{1}{k + r(d)}$.
   - **Cross-Encoder Reranker:** Re-scores query-chunk pairs using cross-attention, improving top-k precision by ~18%.

3. **High-Throughput Microservice Architecture:**
   - **FastAPI:** Async routes with P95 sub-200ms target latency.
   - **Real-Time Streaming:** Server-Sent Events (`/api/v1/stream`) to stream agent thoughts, tool observations, and tokens in real time.
   - **Semantic Caching:** In-memory / Redis cache layer to eliminate redundant LLM API spend by 30%+.

4. **Automated Evaluation Harness:**
   - Dedicated benchmark runner (`evals/run_evals.py`) testing faithfulness, answer relevancy, and quantitative extraction precision.

---

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
