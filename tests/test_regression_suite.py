import pytest
import uuid
from app.models.state import AgentState
from app.agents.research_agent import research_agent
from app.agents.verifier_agent import verifier_agent
from app.search.hybrid_retriever import hybrid_retriever

# =====================================================================
# 1. Hallucination-via-Fallback Test Cases
# =====================================================================

@pytest.mark.asyncio
async def test_hallucination_fallback_unrelated_query(async_client):
    """
    Requirement 1: Query with no matching documents returns graceful
    'no information' response, not a fabricated answer.
    """
    query = "What is your policy on cryptocurrency payments?"
    resp = await async_client.post(
        "/api/v1/query",
        json={"query": query, "top_k": 3, "enable_reranking": True, "enable_verification": True}
    )
    assert resp.status_code == 200
    data = resp.json()

    # Assert graceful no-information response
    summary = data["analysis"]["executive_summary"]
    assert "I don't have information about this in the provided documents." in summary
    assert data["analysis"]["confidence_score"] == 0.0
    assert data["analysis"]["key_metrics"] == []
    assert data["analysis"]["verifiable_claims"] == []

    # Assert verifier marks honest admission of lack of knowledge as faithful (no hallucinations)
    verification = data.get("verification")
    assert verification is not None
    assert verification["is_faithful"] is True
    assert verification["hallucination_score"] == 0.0
    assert len(verification["unsupported_claims"]) == 0


@pytest.mark.asyncio
async def test_hallucination_fallback_direct_empty_chunks():
    """
    Requirement 1: Direct AgentState execution with empty chunks yields
    unfabricated no-information summary and 0.0 hallucination score.
    """
    state = AgentState(query="What is the company policy on space tourism?")
    state.retrieved_chunks = []

    # Research agent analysis with zero context
    state = await research_agent.analyze(state)
    assert state.draft_summary["executive_summary"] == "I don't have information about this in the provided documents."
    assert state.draft_summary["confidence_score"] == 0.0
    assert state.draft_summary["key_metrics"] == []
    assert state.draft_summary["verifiable_claims"] == []

    # Verifier agent audit
    state = verifier_agent.verify(state)
    report = state.final_output["verification_report"]
    assert report["is_faithful"] is True
    assert report["hallucination_score"] == 0.0


# =====================================================================
# 2. Verifier Calibration (8-Case NLI Benchmark)
# =====================================================================

CHUNK_REFUND = {
    "chunk_id": "chunk_refund_01",
    "content": "Customers may request a full refund within 30 days of purchase if they are unsatisfied with the product. Refunds are processed within 5-7 business days and issued to the original payment method. Refund requests after 30 days are evaluated case-by-case and are not guaranteed."
}

CHUNK_PRICING = {
    "chunk_id": "chunk_pricing_01",
    "content": "The Basic plan costs $9/month and includes up to 3 team members. The Pro plan costs $29/month and includes up to 15 team members plus priority support. The Enterprise plan is custom-priced and includes unlimited team members, a dedicated account manager, and SSO integration."
}

CHUNK_SECURITY = {
    "chunk_id": "chunk_sec_01",
    "content": "All accounts require two-factor authentication for logins from new devices. Passwords must be at least 12 characters and are hashed using bcrypt before storage. Users can enable hardware security keys as an additional authentication method in account settings."
}

CHUNK_SHIPPING = {
    "chunk_id": "chunk_ship_01",
    "content": "Standard shipping within the continental US takes 3-5 business days. Expedited shipping takes 1-2 business days and costs an additional $15. International shipping typically takes 7-14 business days depending on customs processing in the destination country."
}

BENCHMARK_CASES = [
    # 1. Known Adversarial: Dropped Qualifier
    (1, "Dropped Qualifier", "What is your refund policy?", CHUNK_REFUND, "Refunds are not guaranteed", [], False),
    # 2. Known Adversarial: Misattributed Number
    (2, "Misattributed Number", "How many team members are included in the Basic plan?", CHUNK_PRICING, "The Basic plan includes up to 15 team members", [{"metric_name": "Basic plan team members", "value": "15", "source_chunk_id": "chunk_pricing_01"}], False),
    # 3. Direct-Match Faithful: Refund SLA
    (3, "Refund SLA", "What is the refund timeline?", CHUNK_REFUND, "Refunds are processed within 5-7 business days", [], True),
    # 4. Direct-Match Faithful: Password Security
    (4, "Password Security", "What are the password requirements?", CHUNK_SECURITY, "Passwords must be at least 12 characters and are hashed using bcrypt before storage.", [], True),
    # 5. Direct-Match Faithful: Expedited Shipping
    (5, "Expedited Shipping", "How much is expedited shipping?", CHUNK_SHIPPING, "Expedited shipping takes 1-2 business days and costs an additional $15.", [], True),
    # 6. Direct-Match Faithful: Basic Plan Specs
    (6, "Basic Plan Specs", "What does the Basic plan include?", CHUNK_PRICING, "The Basic plan costs $9/month and includes up to 3 team members.", [{"metric_name": "Basic plan team members", "value": "3", "source_chunk_id": "chunk_pricing_01"}], True),
    # 7. Constructed Adversarial: Unsupported Inference
    (7, "Unsupported Inference", "Are passwords required with two-factor authentication?", CHUNK_SECURITY, "Enabling two-factor authentication allows users to use passwords shorter than 12 characters.", [], False),
    # 8. Constructed Adversarial: Subjective Spin
    (8, "Subjective Spin", "How much is expedited shipping?", CHUNK_SHIPPING, "Expedited shipping is an expensive and overpriced option for continental US deliveries.", [], False)
]

@pytest.mark.parametrize("case_id, name, query, chunk, claim, metrics, expected_faithful", BENCHMARK_CASES)
def test_verifier_calibration_benchmark(case_id, name, query, chunk, claim, metrics, expected_faithful):
    """
    Requirement 2: 8-case NLI benchmark asserting that grounded-but-misleading claims
    are flagged and genuinely faithful claims pass with expected is_faithful and hallucination_score.
    """
    state = AgentState(query=query)
    state.retrieved_chunks = [chunk]
    state.draft_summary = {
        "executive_summary": claim,
        "verifiable_claims": [claim],
        "key_metrics": metrics
    }

    result = verifier_agent.verify(state)
    report = result.final_output["verification_report"]

    assert report["is_faithful"] is expected_faithful, (
        f"Case {case_id} ({name}) failed: expected is_faithful={expected_faithful}, got {report['is_faithful']}. "
        f"Unsupported: {report['unsupported_claims']}"
    )

    if expected_faithful:
        assert report["hallucination_score"] == 0.0, f"Case {case_id} expected 0.0 hallucination_score"
        assert len(report["unsupported_claims"]) == 0
    else:
        assert report["hallucination_score"] > 0.0, f"Case {case_id} expected >0.0 hallucination_score"
        assert len(report["unsupported_claims"]) > 0


# =====================================================================
# 3. Malformed Input Test Cases
# =====================================================================

@pytest.mark.asyncio
async def test_malformed_input_empty_query(async_client):
    """Requirement 3: Empty query should not crash the server and return a valid QueryResponse."""
    resp = await async_client.post("/api/v1/query", json={"query": ""})
    assert resp.status_code == 200
    data = resp.json()
    assert "query" in data
    assert "analysis" in data
    assert isinstance(data["analysis"]["executive_summary"], str)
    assert len(data["analysis"]["executive_summary"]) > 0


@pytest.mark.asyncio
async def test_malformed_input_extremely_long_query(async_client):
    """Requirement 3: Extremely long query (20,000 chars) should not crash the server."""
    long_q = "What is the return policy? " + ("word " * 4000)
    resp = await async_client.post("/api/v1/query", json={"query": long_q})
    assert resp.status_code == 200
    data = resp.json()
    assert "analysis" in data


@pytest.mark.asyncio
async def test_malformed_input_garbled_unicode_and_injection(async_client):
    """Requirement 3: Non-UTF8/garbled input and symbols should not crash the server."""
    garbled = "\x00\ufffd\u200b\U0001f600\U0001f4a9 <script>alert('xss')</script> %20%27; DROP TABLE documents; --"
    resp = await async_client.post("/api/v1/query", json={"query": garbled})
    assert resp.status_code == 200
    data = resp.json()
    assert "analysis" in data


@pytest.mark.asyncio
async def test_malformed_input_empty_document_store():
    """Requirement 3: Querying with an empty document store should return graceful fallback without crashing."""
    chunks = await hybrid_retriever.retrieve(
        query="Any arbitrary query",
        session=None,
        top_k=5,
        in_memory_chunks=[]
    )
    assert chunks == []


@pytest.mark.asyncio
async def test_malformed_input_invalid_top_k_returns_422(async_client):
    """Requirement 3: Invalid top_k (< 1) returns 422 Unprocessable Entity."""
    resp = await async_client.post("/api/v1/query", json={"query": "Valid query", "top_k": -1})
    assert resp.status_code == 422


# =====================================================================
# 4. Cache Behavior Test Cases
# =====================================================================

@pytest.mark.asyncio
async def test_cache_hit_and_latency_reduction(async_client):
    """
    Requirement 4: Query once (miss), query again (hit) — assert latency and cache-status differ appropriately.
    """
    unique_id = uuid.uuid4().hex[:8]
    query = f"How long do I have to request a refund? {unique_id}"
    payload = {"query": query, "top_k": 2, "enable_reranking": True, "enable_verification": True}

    # 1. First execution -> cache miss
    resp1 = await async_client.post("/api/v1/query", json=payload)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["cached"] is False
    t1 = data1["execution_time_ms"]

    # 2. Second execution -> cache hit
    resp2 = await async_client.post("/api/v1/query", json=payload)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["cached"] is True
    t2 = data2["execution_time_ms"]

    # Assert cache hit latency is lower than cold execution
    assert t2 < t1 or t2 < 100.0, f"Expected cache hit latency ({t2}ms) to be lower than miss ({t1}ms)"
    assert data2["analysis"]["executive_summary"] == data1["analysis"]["executive_summary"]


# =====================================================================
# 5. Ingestion Guardrails Test Cases
# =====================================================================

@pytest.mark.asyncio
async def test_ingestion_guardrail_empty_text_returns_400(async_client):
    """Requirement 5: Empty text_content returns 400 Bad Request."""
    resp = await async_client.post("/api/v1/ingest", json={"title": "Empty Document", "text_content": ""})
    assert resp.status_code == 400
    assert "cannot be empty" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_ingestion_guardrail_whitespace_returns_400(async_client):
    """Requirement 5: Whitespace-only text_content returns 400 Bad Request."""
    resp = await async_client.post("/api/v1/ingest", json={"title": "Whitespace Document", "text_content": "   \n\t  "})
    assert resp.status_code == 400
    assert "cannot be empty" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_ingestion_guardrail_over_50k_chars_returns_413(async_client):
    """Requirement 5: text_content over 50,000 chars returns 413 Payload Too Large."""
    huge_text = "A" * 50001
    resp = await async_client.post("/api/v1/ingest", json={"title": "Oversized Document", "text_content": huge_text})
    assert resp.status_code == 413
    detail = resp.json()["detail"]
    assert "50,000" in detail
    assert "exceeds" in detail.lower()


@pytest.mark.asyncio
async def test_ingestion_success_document_listing_and_query_verification(async_client, test_doc_tracker):
    """
    Requirement 5:
    1. Valid ingestion succeeds (200).
    2. Document appears in GET /api/v1/documents.
    3. Query against freshly ingested content returns a correct, verified answer.
    4. Fixture automatically cleans up document from DB and in-memory store.
    """
    uid = uuid.uuid4().hex[:8]
    doc_id = f"test_doc_{uid}"
    test_doc_tracker.append(doc_id)

    title = f"Autonomous Agent Fleet SLA {uid}"
    content = (
        f"The Autonomous Agent Fleet SLA for cluster {uid} guarantees 99.98% operational availability. "
        f"The automated failover protocol completes in under 45 seconds during regional disruptions."
    )

    # 1. Ingest document
    ingest_resp = await async_client.post(
        "/api/v1/ingest",
        json={"doc_id": doc_id, "title": title, "text_content": content}
    )
    assert ingest_resp.status_code == 200
    ingest_data = ingest_resp.json()
    assert ingest_data["status"] == "success"
    assert ingest_data["chunks_created"] >= 1

    # 2. Verify appearance in GET /api/v1/documents
    docs_resp = await async_client.get("/api/v1/documents")
    assert docs_resp.status_code == 200
    docs = docs_resp.json()
    matching_docs = [d for d in docs if d.get("doc_id") == doc_id or d.get("title") == title]
    assert len(matching_docs) == 1
    assert matching_docs[0]["chunks_count"] >= 1

    # 3. Query against freshly ingested content
    query = f"What is the operational availability guarantee and failover protocol time for cluster {uid}?"
    query_resp = await async_client.post(
        "/api/v1/query",
        json={"query": query, "top_k": 2, "enable_reranking": True, "enable_verification": True}
    )
    assert query_resp.status_code == 200
    query_data = query_resp.json()

    # Assert retrieved chunks contain new doc
    assert len(query_data["retrieved_chunks"]) > 0
    retrieved_content = " ".join([c["content"] for c in query_data["retrieved_chunks"]])
    assert "99.98%" in retrieved_content

    # Assert verification report is faithful
    verification = query_data.get("verification")
    assert verification is not None
    assert verification["is_faithful"] is True
    assert verification["hallucination_score"] == 0.0
