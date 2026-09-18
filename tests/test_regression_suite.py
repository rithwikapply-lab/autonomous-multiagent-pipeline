import pytest
import uuid
from app.models.state import AgentState
from app.agents.research_agent import research_agent
from app.agents.verifier_agent import verifier_agent
from app.search.hybrid_retriever import hybrid_retriever
from app.search.reranker import cross_encoder_reranker

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

    # Assert cache hit latency is lower than cold execution and achieves sub-10ms response time
    assert t2 < t1, f"Expected cache hit latency ({t2}ms) to be lower than miss ({t1}ms)"
    assert t2 < 10.0, f"Expected cache hit latency to be under 10ms, got {t2}ms"
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


# =====================================================================
# 6. Topical Relevance & Vocabulary Overlap Regression Cases
# =====================================================================

DOC_VACATION = {
    "chunk_id": "chunk_vacation_01",
    "doc_id": "doc_vacation_policy",
    "content": "Company Vacation Policy All full-time employees receive 15 paid vacation days per calendar year. Vacation requests must be submitted at least two weeks in advance. Unused vacation days roll over up to a maximum of 5 days."
}

DOC_REMOTE_WORK = {
    "chunk_id": "chunk_remote_01",
    "doc_id": "doc_remote_work_policy",
    "content": "Remote Work Policy 2026 Employees may work remotely up to 3 days per week with manager approval. Core working hours are 10 AM to 4 PM EST. A one-time stipend of $500 is provided for home office equipment."
}

DOC_PARENTAL_LEAVE = {
    "chunk_id": "chunk_parental_01",
    "doc_id": "doc_parental_leave_policy",
    "content": "Parental Leave Guidelines Eligible employees receive up to 12 weeks of fully paid parental leave following the birth or adoption of a child. Leave must be taken within the first 12 months."
}

DOC_EQUIPMENT = {
    "chunk_id": "chunk_equipment_01",
    "doc_id": "doc_equipment_policy",
    "content": "Employee Equipment and Expense Policy Company-issued laptops, smartphones, and peripheral devices remain the property of the organization. Damaged or lost equipment must be reported to IT within 48 hours. Employees may request replacement equipment through the internal service portal."
}

CORPUS_REAL_DOCS = [DOC_VACATION, DOC_REMOTE_WORK, DOC_PARENTAL_LEAVE]


@pytest.mark.asyncio
async def test_regression_unmentioned_sick_days_query():
    """
    Exact User Bug Reproduction:
    Query: 'How many sick days do employees get?' against Vacation Policy, Remote Work Policy,
    and Parental Leave Guidelines — none of which discuss sick leave.
    
    Verifies:
    1. Cross-encoder relevance gate rejects all 3 chunks (rerank returns []).
    2. Even if candidate chunks reach ResearchAgent, topical match check fails.
    3. Returns standard no-information response with 0.0 confidence score and empty metrics/claims.
    4. Verifier confirms honest lack-of-info admission with is_faithful=True and 0.0 hallucination score.
    5. Does NOT fabricate an answer using Vacation Policy or misattribute '3 days per week'.
    """
    query = "How many sick days do employees get?"

    # 1. Reranker relevance gate: all 3 candidate chunks must be filtered out
    reranked = cross_encoder_reranker.rerank(query, CORPUS_REAL_DOCS, filter_irrelevant=True)
    assert reranked == [], f"Expected reranker to reject all chunks, got: {reranked}"

    # 2. ResearchAgent topical relevance gate (even if chunks were supplied)
    state = AgentState(query=query)
    state.retrieved_chunks = CORPUS_REAL_DOCS
    state = await research_agent.analyze(state)

    summary = state.draft_summary["executive_summary"]
    assert "I don't have information about this in the provided documents." in summary
    assert state.draft_summary["confidence_score"] == 0.0
    assert state.draft_summary["key_metrics"] == []
    assert state.draft_summary["verifiable_claims"] == []

    # 3. VerifierAgent confirms faithful admission of lack of knowledge
    state = verifier_agent.verify(state)
    report = state.final_output["verification_report"]
    assert report["is_faithful"] is True
    assert report["hallucination_score"] == 0.0
    assert len(report["unsupported_claims"]) == 0


@pytest.mark.asyncio
async def test_regression_lost_laptop_equipment_policy():
    """
    Exact User Bug Reproduction: False-Negative Regression on Paraphrase & Irregular Inflection.
    Query: 'What happens if an employee loses their laptop?'
    Retrieved Chunk: Employee Equipment and Expense Policy (chunk_equipment_01), containing:
    'Damaged or lost equipment must be reported to IT within 48 hours.'

    ARCHITECTURAL LIMITATION & DESIGN NOTE:
    Rule-based discriminative keyword coverage has an inherent blind spot for semantic paraphrases:
    1. Morphological/Stem Divergence: Suffix-stripping stemmers do not unify irregular verb inflections
       such as 'loses' (stem: 'los') vs. past participle 'lost' (stem: 'lost' without irregular mapping).
    2. Entity Hypernym / Synecdoche: The user's query refers to an instance ('laptop'), while the policy
       document states the governing rule using the categorical hypernym ('equipment').
    3. Cross-Encoder Semantic Resolution: The neural cross-encoder (ms-marco-MiniLM-L-6-v2) already
       exhibits strong semantic comprehension, ranking chunk_equipment_01 #1 with a positive rerank score
       (> +2.0) across the mixed corpus.
    A rigid lexical-only coverage gate causes false-negative rejections of genuinely answerable questions.
    The pipeline addresses this by:
    - Normalizing irregular inflection pairs ('lost' -> 'los') in _stem().
    - Treating interrogative framing verbs ('happens', 'occur') as generic query words.
    - Allowing high cross-encoder scores (rerank_score >= 0.0) with partial keyword coverage to satisfy
      topical matching.
    - Scoring candidate sentences and claims by keyword matches + quantitative metric presence.

    Verifies:
    1. Cross-encoder reranks chunk_equipment_01 as #1 with positive rerank_score > 0.0 from mixed corpus.
    2. ResearchAgent successfully identifies topical match (confidence >= 0.80), extracts metric 48,
       and incorporates the directly relevant sentence ('Damaged or lost equipment...') into the summary.
    3. VerifierAgent confirms faithfulness (is_faithful=True, hallucination_score=0.0) without
       falsely flagging the claim or metric as off-topic.
    """
    query = "What happens if an employee loses their laptop?"
    mixed_corpus = CORPUS_REAL_DOCS + [DOC_EQUIPMENT]

    # 1. Reranker selects equipment chunk as top candidate
    reranked = cross_encoder_reranker.rerank(query, mixed_corpus, filter_irrelevant=True)
    assert len(reranked) >= 1, f"Expected reranker to keep relevant chunk, got: {reranked}"
    assert reranked[0]["chunk_id"] == "chunk_equipment_01"
    assert reranked[0].get("rerank_score", -999.0) > 0.0

    # 2. ResearchAgent deterministic synthesis extracts relevant sentence and metrics
    state = AgentState(query=query)
    state.retrieved_chunks = [reranked[0]]
    state = await research_agent.analyze(state)

    summary = state.draft_summary["executive_summary"]
    assert "I don't have information about this in the provided documents." not in summary
    assert "Damaged or lost equipment must be reported to IT within 48 hours" in summary
    assert state.draft_summary["confidence_score"] >= 0.80

    metric_values = [str(m["value"]) for m in state.draft_summary["key_metrics"]]
    assert "48" in metric_values

    claims = state.draft_summary["verifiable_claims"]
    assert any("Damaged or lost equipment must be reported to IT within 48 hours" in c for c in claims)

    # 3. VerifierAgent audits factual grounding & topical relevance
    state = verifier_agent.verify(state)
    report = state.final_output["verification_report"]
    assert report["is_faithful"] is True
    assert report["hallucination_score"] == 0.0
    assert len(report["unsupported_claims"]) == 0
    assert any("48" in c for c in report["verified_claims"])


@pytest.mark.asyncio
async def test_generalization_fake_question_sharing_vocabulary_pet_policy():
    """
    Generalization Case: Fake question sharing vocabulary ('policy', 'remote', 'workers')
    with Remote Work Policy, but Remote Work Policy never mentions pets.
    Must return graceful no-information response.
    """
    query = "What is the pet policy for remote workers?"

    state = AgentState(query=query)
    state.retrieved_chunks = CORPUS_REAL_DOCS
    state = await research_agent.analyze(state)

    summary = state.draft_summary["executive_summary"]
    assert "I don't have information about this in the provided documents." in summary
    assert state.draft_summary["confidence_score"] == 0.0
    assert state.draft_summary["key_metrics"] == []
    assert state.draft_summary["verifiable_claims"] == []

    state = verifier_agent.verify(state)
    report = state.final_output["verification_report"]
    assert report["is_faithful"] is True
    assert report["hallucination_score"] == 0.0


@pytest.mark.asyncio
async def test_generalization_fake_question_sharing_vocabulary_vacation_charity():
    """
    Generalization Case: Fake question sharing vocabulary ('employees', 'unused', 'vacation', 'days')
    with Vacation Policy, but Vacation Policy never mentions charity donations.
    Must return graceful no-information response.
    """
    query = "Can employees donate unused vacation days to charity?"

    state = AgentState(query=query)
    state.retrieved_chunks = CORPUS_REAL_DOCS
    state = await research_agent.analyze(state)

    summary = state.draft_summary["executive_summary"]
    assert "I don't have information about this in the provided documents." in summary
    assert state.draft_summary["confidence_score"] == 0.0
    assert state.draft_summary["key_metrics"] == []
    assert state.draft_summary["verifiable_claims"] == []

    state = verifier_agent.verify(state)
    report = state.final_output["verification_report"]
    assert report["is_faithful"] is True
    assert report["hallucination_score"] == 0.0


@pytest.mark.asyncio
async def test_generalization_real_question_vacation_policy():
    """
    Generalization Case: Genuine question about Vacation Policy.
    Must accurately match, extract 15 days metric, and pass verification faithfully.
    """
    query = "How many vacation days do full-time employees receive?"

    reranked = cross_encoder_reranker.rerank(query, CORPUS_REAL_DOCS, filter_irrelevant=True)
    assert len(reranked) >= 1
    assert reranked[0]["chunk_id"] == "chunk_vacation_01"

    state = AgentState(query=query)
    state.retrieved_chunks = [reranked[0]]
    state = await research_agent.analyze(state)

    assert state.draft_summary["confidence_score"] >= 0.80
    metric_values = [str(m["value"]) for m in state.draft_summary["key_metrics"]]
    assert "15" in metric_values

    state = verifier_agent.verify(state)
    report = state.final_output["verification_report"]
    assert report["is_faithful"] is True
    assert report["hallucination_score"] == 0.0


@pytest.mark.asyncio
async def test_generalization_real_question_remote_work_policy():
    """
    Generalization Case: Genuine question about Remote Work Policy.
    Must accurately match, extract 3 days per week metric, and pass verification faithfully.
    """
    query = "How many days per week can employees work remotely?"

    reranked = cross_encoder_reranker.rerank(query, CORPUS_REAL_DOCS, filter_irrelevant=True)
    assert len(reranked) >= 1
    assert reranked[0]["chunk_id"] == "chunk_remote_01"

    state = AgentState(query=query)
    state.retrieved_chunks = [reranked[0]]
    state = await research_agent.analyze(state)

    assert state.draft_summary["confidence_score"] >= 0.80
    metric_values = [str(m["value"]) for m in state.draft_summary["key_metrics"]]
    assert "3" in metric_values

    state = verifier_agent.verify(state)
    report = state.final_output["verification_report"]
    assert report["is_faithful"] is True
    assert report["hallucination_score"] == 0.0


@pytest.mark.asyncio
async def test_generalization_real_question_parental_leave_policy():
    """
    Generalization Case: Genuine question about Parental Leave Guidelines.
    Must accurately match, extract 12 weeks metric, and pass verification faithfully.
    """
    query = "How many weeks of parental leave are provided?"

    reranked = cross_encoder_reranker.rerank(query, CORPUS_REAL_DOCS, filter_irrelevant=True)
    assert len(reranked) >= 1
    assert reranked[0]["chunk_id"] == "chunk_parental_01"

    state = AgentState(query=query)
    state.retrieved_chunks = [reranked[0]]
    state = await research_agent.analyze(state)

    assert state.draft_summary["confidence_score"] >= 0.80
    metric_values = [str(m["value"]) for m in state.draft_summary["key_metrics"]]
    assert "12" in metric_values

    state = verifier_agent.verify(state)
    report = state.final_output["verification_report"]
    assert report["is_faithful"] is True
    assert report["hallucination_score"] == 0.0


# =====================================================================
# 5. Real-World Document Regression Suite (Google Privacy Policy & Entity Protection)
# =====================================================================

DOC_GOOGLE_PRIVACY_0 = {
    "chunk_id": "chunk_google_privacy_00",
    "doc_id": "6bc24243-18f6-4205-9d68-81fe4a86638e",
    "title": "Google Privacy Policy",
    "content": "GOOGLE PRIVACY POLICY When you use our services, you're trusting us with your information. This Privacy Policy is meant to help you understand what information we collect, why we collect it, and how you can update, manage, export, and delete your information. Effective May 26, 2026. We build a range of services that help millions of people daily to explore and interact with the world in new ways."
}

DOC_GOOGLE_PRIVACY_2 = {
    "chunk_id": "chunk_google_privacy_02",
    "doc_id": "6bc24243-18f6-4205-9d68-81fe4a86638e",
    "title": "Google Privacy Policy",
    "content": "YOUR PRIVACY CONTROLS Personalization and Activity Controls: Across many of our services, you can adjust history and personalization controls to make choices about whether we save some types of data in your Google Account and how we use it to personalize your experience. EXPORTING, REMOVING & DELETING YOUR INFORMATION You can export a copy of content in your Google Account if you want to back it up or use it with a service outside of Google. To delete your information, you can delete your content from specific Google services, search for and delete specific items using My Activity, delete specific Google products, or delete your entire Google Account."
}

DOC_GOOGLE_PRIVACY_3 = {
    "chunk_id": "chunk_google_privacy_03",
    "doc_id": "6bc24243-18f6-4205-9d68-81fe4a86638e",
    "title": "Google Privacy Policy",
    "content": "With domain administrators: If you're a student or work for an organization that uses Google services, your domain administrator and resellers who manage your account will have access to your Google Account. They may be able to access and retain information stored in your account like your email, view statistics regarding your account, change your account password, suspend or terminate your account access, receive your account information to satisfy legal requests, and restrict your ability to delete or edit your information or privacy settings."
}

DOC_GOOGLE_PRIVACY_4 = {
    "chunk_id": "chunk_google_privacy_04",
    "doc_id": "6bc24243-18f6-4205-9d68-81fe4a86638e",
    "title": "Google Privacy Policy",
    "content": "Activity on Google Services: When you search for something using a general area, your search will use an area of at least 3 square kilometers, or expand until the area represents the locations of at least 1,000 people. This helps protect your privacy. Partner with Google: There are over 2 million non-Google websites and apps that partner with Google to show ads."
}


@pytest.mark.asyncio
async def test_regression_privacy_policy_effective_date():
    """
    Issue 1: Short factual query failure on 'When did this privacy policy take effect?'
    Document opens with 'Effective May 26, 2026.'
    Ensures derivational suffix normalization ('effective' -> 'effect') matches query 'effect',
    extracts the effective date, and passes verification.
    """
    query = "When did this privacy policy take effect?"
    state = AgentState(query=query)
    state.retrieved_chunks = [DOC_GOOGLE_PRIVACY_0]
    state = await research_agent.analyze(state)

    summary = state.draft_summary["executive_summary"]
    assert "I don't have information about this in the provided documents." not in summary
    assert "May 26, 2026" in summary
    assert state.draft_summary["confidence_score"] >= 0.80

    state = verifier_agent.verify(state)
    report = state.final_output["verification_report"]
    assert report["is_faithful"] is True
    assert report["hallucination_score"] == 0.0
    assert len(report["unsupported_claims"]) == 0


@pytest.mark.asyncio
async def test_regression_download_google_data_export_paraphrase():
    """
    Issue 2: Paraphrase failure on 'Can I download my Google data to use somewhere else?'
    Retrieves chunk containing both Personalization and Export sections.
    Ensures synonym normalization ('download' -> 'export') selects the Export section
    ('export a copy of content... to use it with a service outside of Google') rather than
    the Personalization section, and passes verification.
    """
    query = "Can I download my Google data to use somewhere else?"
    state = AgentState(query=query)
    state.retrieved_chunks = [DOC_GOOGLE_PRIVACY_2]
    state = await research_agent.analyze(state)

    summary = state.draft_summary["executive_summary"]
    assert "I don't have information about this in the provided documents." not in summary
    assert "export a copy of content in your Google Account" in summary or "use it with a service outside of Google" in summary
    assert state.draft_summary["confidence_score"] >= 0.80

    state = verifier_agent.verify(state)
    report = state.final_output["verification_report"]
    assert report["is_faithful"] is True
    assert report["hallucination_score"] == 0.0
    assert len(report["unsupported_claims"]) == 0


@pytest.mark.asyncio
async def test_regression_student_school_managed_account():
    """
    Issue 3: Verifier over-correction regression on:
    'If I'm a student and my school uses Google, can the school see my account?'
    Candidate chunk explains domain administrator access.
    Ensures keyword deduplication ('school' count 1 instead of 2) and perception verb handling ('see')
    prevent topical false rejection, and claim relevance primacy verifies grounded claims faithfully.
    """
    query = "If I'm a student and my school uses Google, can the school see my account?"
    state = AgentState(query=query)
    state.retrieved_chunks = [DOC_GOOGLE_PRIVACY_3]
    state = await research_agent.analyze(state)

    summary = state.draft_summary["executive_summary"]
    assert "I don't have information about this in the provided documents." not in summary
    assert "domain administrator" in summary or "administrator" in summary

    state = verifier_agent.verify(state)
    report = state.final_output["verification_report"]
    assert report["is_faithful"] is True
    assert report["hallucination_score"] == 0.0
    assert len(report["unsupported_claims"]) == 0


@pytest.mark.asyncio
async def test_regression_ads_partner_metrics_sentence_scoping():
    """
    Issue 4: Metric cross-contamination in:
    'How many websites and apps partner with Google to show ads?'
    Chunk contains '3 square kilometers', '1,000 people' in sentence 1, and '2 million' in sentence 2.
    Ensures metric extraction is scoped to topical sentences, extracting '2 million' while strictly
    excluding unrelated metrics ('3', '1,000') from distant sentences.
    """
    query = "How many websites and apps partner with Google to show ads?"
    state = AgentState(query=query)
    state.retrieved_chunks = [DOC_GOOGLE_PRIVACY_4]
    state = await research_agent.analyze(state)

    summary = state.draft_summary["executive_summary"]
    assert "I don't have information about this in the provided documents." not in summary

    metric_values = [str(m["value"]) for m in state.draft_summary["key_metrics"]]
    assert "2 million" in metric_values
    assert "3" not in metric_values
    assert "1,000" not in metric_values

    state = verifier_agent.verify(state)
    report = state.final_output["verification_report"]
    assert report["is_faithful"] is True
    assert report["hallucination_score"] == 0.0
    assert len(report["unsupported_claims"]) == 0


@pytest.mark.asyncio
async def test_regression_entity_conflation_google_vacation_rejection():
    """
    Issue 5 & Proper Noun Capitalization Guard:
    1. Entity Conflation: 'How many vacation days do Google employees get?' against
       synthetic Vacation Policy which never mentions Google.
       Must reject with graceful no-information response.
    2. Capitalization Guard: Sentence-initial common words (e.g. 'The Company provides...')
       must NOT be misdetected as named entities and must NOT cause false rejections.
    """
    from app.search.reranker import extract_query_named_entities

    # Sub-check A: Sentence-initial capitalization does not extract common words as named entities
    assert extract_query_named_entities("The Company provides 15 vacation days per year.") == []
    assert extract_query_named_entities("Policy allows remote work on Fridays?") == []
    assert extract_query_named_entities("What happens if an employee loses their laptop?") == []
    assert extract_query_named_entities("Does Google have a vacation policy?") == ["googl"]
    assert extract_query_named_entities("AWS provides cloud hosting") == ["aws"]

    # Sub-check B: Non-entity query 'The Company provides how many vacation days?' answers faithfully
    valid_query = "The Company provides how many vacation days?"
    valid_state = AgentState(query=valid_query)
    valid_state.retrieved_chunks = [DOC_VACATION]
    valid_state = await research_agent.analyze(valid_state)
    assert valid_state.draft_summary["confidence_score"] >= 0.80
    valid_metrics = [str(m["value"]) for m in valid_state.draft_summary["key_metrics"]]
    assert "15" in valid_metrics

    # Sub-check C: Entity conflation rejection: query names 'Google', but Vacation Policy has no Google mention
    query = "How many vacation days do Google employees get?"

    # 1. Reranker relevance gate: rejects chunk due to missing named entity
    reranked = cross_encoder_reranker.rerank(query, CORPUS_REAL_DOCS, filter_irrelevant=True)
    assert reranked == [], f"Expected reranker to reject chunks lacking named entity 'Google', got: {reranked}"

    # 2. ResearchAgent topical relevance gate: fails topical match
    state = AgentState(query=query)
    state.retrieved_chunks = CORPUS_REAL_DOCS
    state = await research_agent.analyze(state)

    summary = state.draft_summary["executive_summary"]
    assert "I don't have information about this in the provided documents." in summary
    assert state.draft_summary["confidence_score"] == 0.0
    assert state.draft_summary["key_metrics"] == []
    assert state.draft_summary["verifiable_claims"] == []

    # 3. VerifierAgent confirms faithful lack-of-knowledge admission
    state = verifier_agent.verify(state)
    report = state.final_output["verification_report"]
    assert report["is_faithful"] is True
    assert report["hallucination_score"] == 0.0
    assert len(report["unsupported_claims"]) == 0
