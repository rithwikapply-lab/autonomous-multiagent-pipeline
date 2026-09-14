from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
from app.models.state import AgentState
from app.agents.router import router as context_router
from app.search.hybrid_retriever import hybrid_retriever
from app.search.reranker import cross_encoder_reranker
from app.agents.research_agent import research_agent
from app.agents.verifier_agent import verifier_agent
from app.api.ingest import IN_MEMORY_CHUNKS

router = APIRouter()

@router.get("/stream")
async def stream_analysis(query: str):
    """
    Streams multi-agent reasoning steps, tool actions, and final synthesis
    in real-time using Server-Sent Events (SSE).
    """
    async def event_generator():
        yield {"event": "start", "data": json.dumps({"query": query, "status": "Pipeline initiated"})}
        await asyncio.sleep(0.05)

        # Step 1: Router
        state = AgentState(query=query)
        state = context_router.route(state)
        yield {
            "event": "thought",
            "data": json.dumps({
                "agent": "ContextRouter",
                "intent": state.intent,
                "search_queries": state.search_queries
            })
        }
        await asyncio.sleep(0.05)

        # Step 2: Hybrid Retrieval
        yield {"event": "thought", "data": json.dumps({"agent": "HybridRetriever", "action": "Executing BM25 + pgvector RRF"})}
        chunks = await hybrid_retriever.retrieve(query=query, top_k=5, in_memory_chunks=IN_MEMORY_CHUNKS)
        chunks = cross_encoder_reranker.rerank(query, chunks, top_k=3)
        state.retrieved_chunks = chunks
        yield {
            "event": "retrieval",
            "data": json.dumps({"retrieved_count": len(chunks), "top_chunk_ids": [c.get("chunk_id") for c in chunks]})
        }
        await asyncio.sleep(0.05)

        # Step 3: Research Agent
        yield {"event": "thought", "data": json.dumps({"agent": "ResearchAgent", "action": "Synthesizing evidence and extracting metrics"})}
        state = await research_agent.analyze(state)
        await asyncio.sleep(0.05)

        # Step 4: Verification Agent
        yield {"event": "thought", "data": json.dumps({"agent": "VerifierAgent", "action": "Auditing claims against retrieved context"})}
        state = verifier_agent.verify(state)

        # Final Payload
        yield {
            "event": "complete",
            "data": json.dumps({
                "analysis": state.draft_summary,
                "verification": state.final_output.get("verification_report")
            })
        }

    return EventSourceResponse(event_generator())
