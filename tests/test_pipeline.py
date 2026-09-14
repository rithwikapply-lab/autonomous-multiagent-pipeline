import pytest
import asyncio
from app.models.schemas import DocumentIngestRequest, QueryRequest
from app.api.ingest import ingest_document
from app.api.query import query_pipeline
from app.agents.tools import AgentTools
from app.agents.router import ContextRouter
from app.models.state import AgentState

def test_agent_tools_calculation():
    result = AgentTools.calculate("(45000 / 18) * 60")
    assert result["status"] == "success"
    assert result["result"] == 150000.0

def test_agent_context_router():
    router = ContextRouter()
    state = AgentState(query="Compare the latency between 8B model and commercial API")
    state = router.route(state)
    assert state.intent == "quantitative_comparison"
    assert len(state.search_queries) >= 2

@pytest.mark.asyncio
async def test_end_to_end_pipeline_flow():
    # 1. Ingest
    ingest_req = DocumentIngestRequest(
        doc_id="test_doc_01",
        title="Microservice Performance Report",
        text_content="The microservice achieved 99.95% uptime and processed 15,000 requests per second with sub-50ms latency."
    )
    ingest_res = await ingest_document(ingest_req, session=None)
    assert ingest_res.status == "success"
    assert ingest_res.chunks_created >= 1

    # 2. Query
    query_req = QueryRequest(query="What was the uptime and throughput?", top_k=2)
    query_res = await query_pipeline(query_req, session=None)
    assert query_res.query == "What was the uptime and throughput?"
    assert query_res.execution_time_ms > 0
    assert len(query_res.retrieved_chunks) > 0
    assert query_res.analysis is not None
