from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import time
import json
from app.db.session import get_db
from app.models.schemas import QueryRequest, QueryResponse, AnalyticalSummary, VerificationReport
from app.models.state import AgentState
from app.search.hybrid_retriever import hybrid_retriever
from app.search.reranker import cross_encoder_reranker
from app.agents.router import router as context_router
from app.agents.research_agent import research_agent
from app.agents.verifier_agent import verifier_agent
from app.api.ingest import IN_MEMORY_CHUNKS
from app.config import settings
from typing import Optional
import redis.asyncio as aioredis
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Redis-backed response caching with graceful fallback
_redis_client: Optional[aioredis.Redis] = None

def get_redis_client() -> Optional[aioredis.Redis]:
    global _redis_client
    if _redis_client is None and settings.REDIS_URL:
        try:
            _redis_client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0
            )
        except Exception as e:
            logger.warning(f"Failed to initialize Redis client ({e}).")
            _redis_client = None
    return _redis_client

async def get_cached_response(cache_key: str) -> Optional[QueryResponse]:
    """Retrieves and deserializes QueryResponse from Redis; returns None on miss or error."""
    try:
        client = get_redis_client()
        if client is not None:
            data = await client.get(cache_key)
            if data:
                return QueryResponse.model_validate_json(data)
    except Exception as e:
        logger.warning(f"Redis cache lookup error ({e}), falling back to fresh query execution.")
    return None

async def set_cached_response(cache_key: str, response: QueryResponse, ttl_seconds: int = 3600):
    """Serializes and caches QueryResponse in Redis with TTL; fails gracefully on error."""
    try:
        client = get_redis_client()
        if client is not None:
            await client.set(cache_key, response.model_dump_json(), ex=ttl_seconds)
    except Exception as e:
        logger.warning(f"Redis cache write error ({e}).")

@router.post("/query", response_model=QueryResponse)
async def query_pipeline(
    request: QueryRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Executes the complete Autonomous Multi-Agent Analysis Pipeline:
    1. Checks semantic response cache
    2. Routes query intent (ContextRouter)
    3. Runs Hybrid Retrieval (BM25 + pgvector via RRF)
    4. Applies Cross-Encoder Reranker
    5. Dispatches to ResearchAgent for structured JSON output
    6. Verifies assertions against ground truth context (VerifierAgent)
    """
    start_time = time.perf_counter()

    # Cache check (Redis-backed with graceful fallback)
    cache_key = f"{request.query}_{request.top_k}_{request.enable_reranking}"
    cached_result = await get_cached_response(cache_key)
    if cached_result is not None:
        lookup_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return cached_result.model_copy(update={
            "cached": True,
            "execution_time_ms": lookup_duration_ms
        })

    # 1. Initialize State
    state = AgentState(query=request.query)

    # 2. Dynamic Routing
    state = context_router.route(state)

    # 3. Hybrid Retrieval (BM25 + pgvector via RRF)
    retrieved = await hybrid_retriever.retrieve(
        query=request.query,
        session=session,
        top_k=request.top_k * 2 if request.enable_reranking else request.top_k,
        in_memory_chunks=IN_MEMORY_CHUNKS
    )

    # 4. Cross-Encoder Reranking
    if request.enable_reranking and retrieved:
        retrieved = cross_encoder_reranker.rerank(
            request.query,
            retrieved,
            top_k=request.top_k,
            filter_irrelevant=True
        )
    else:
        retrieved = retrieved[:request.top_k]

    state.retrieved_chunks = retrieved

    # 5. Autonomous Research & Synthesis Agent
    state = await research_agent.analyze(state)

    # 6. Verification Agent (Fact-checking & anti-hallucination)
    verification_report = None
    if request.enable_verification:
        state = verifier_agent.verify(state)
        v_data = state.final_output.get("verification_report")
        if v_data:
            verification_report = VerificationReport(**v_data)

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

    # Assemble response
    draft = state.draft_summary or {}
    analysis = AnalyticalSummary(
        query=request.query,
        executive_summary=draft.get("executive_summary", "Analysis completed."),
        key_metrics=draft.get("key_metrics", []),
        verifiable_claims=draft.get("verifiable_claims", []),
        confidence_score=draft.get("confidence_score", 0.9),
        source_citations=draft.get("source_citations", [])
    )

    # Ensure each chunk dict has chunk_index and doc_id for DocumentChunk validation
    formatted_chunks = []
    for idx, c in enumerate(retrieved):
        chunk_dict = dict(c)
        if "chunk_index" not in chunk_dict or chunk_dict["chunk_index"] is None:
            chunk_dict["chunk_index"] = chunk_dict.get("metadata", {}).get("chunk_index", idx)
        if "doc_id" not in chunk_dict or not chunk_dict["doc_id"]:
            chunk_dict["doc_id"] = chunk_dict.get("metadata", {}).get("doc_id", "unknown")
        formatted_chunks.append(chunk_dict)

    response = QueryResponse(
        query=request.query,
        analysis=analysis,
        retrieved_chunks=formatted_chunks,
        verification=verification_report,
        execution_time_ms=duration_ms,
        cached=False
    )

    # Cache response in Redis
    await set_cached_response(cache_key, response, ttl_seconds=3600)
    return response
