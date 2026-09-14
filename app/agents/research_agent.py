import json
import re
from typing import Dict, Any, List
import httpx
from app.config import settings
from app.models.schemas import AnalyticalSummary, MetricFinding
from app.models.state import AgentState, AgentThoughtStep
from app.agents.tools import AgentTools
import logging

logger = logging.getLogger(__name__)

class ResearchAgent:
    """
    Autonomous research agent utilizing tool calling, structured JSON output
    enforcement, and synthesis across retrieved context chunks.
    """

    SYSTEM_PROMPT = """You are an Autonomous Research & Analysis Agent.
Your objective is to analyze the provided retrieved document chunks and produce a structured, verifiable analytical report.
Rules:
1. Every claim must cite the specific chunk_id from which it was extracted.
2. Extract all quantitative metrics with exact values and confidence scores.
3. Do NOT hallucinate. If context does not answer the question, state it explicitly.
4. Output MUST be valid JSON matching the schema below:
{
  "executive_summary": "High-level synthesis",
  "key_metrics": [
    {"metric_name": "Metric name", "value": "123", "source_chunk_id": "chunk_xxx", "confidence": 0.95}
  ],
  "verifiable_claims": [
    "Claim 1 with evidence",
    "Claim 2 with evidence"
  ],
  "confidence_score": 0.95,
  "source_citations": ["chunk_xxx"]
}
"""

    async def analyze(self, state: AgentState) -> AgentState:
        query = state.query
        chunks = state.retrieved_chunks

        # Format context for prompt
        formatted_chunks = "\n\n".join([
            f"[Chunk ID: {c.get('chunk_id')}]\n{c.get('content', '')}"
            for c in chunks
        ])

        # Attempt to call OpenAI API if key provided
        if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "your_openai_api_key_here":
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                        json={
                            "model": settings.LLM_MODEL,
                            "response_format": {"type": "json_object"},
                            "messages": [
                                {"role": "system", "content": self.SYSTEM_PROMPT},
                                {"role": "user", "content": f"Query: {query}\n\nRetrieved Context:\n{formatted_chunks}"}
                            ],
                            "temperature": 0.1
                        }
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    state.draft_summary = parsed
                    state.thought_history.append(AgentThoughtStep(
                        agent_name="ResearchAgent",
                        thought="Successfully generated structured analytical report via LLM.",
                        action="generate_structured_json",
                        observation=f"Extracted {len(parsed.get('key_metrics', []))} metrics and {len(parsed.get('verifiable_claims', []))} claims."
                    ))
                    return state
            except Exception as e:
                logger.warning(f"LLM API call failed ({e}). Using deterministic analytical synthesis engine.")

        # Deterministic analysis engine (offline / mock / local testing mode)
        # 1. Tool execution: Extract numerical metrics
        all_metrics: List[MetricFinding] = []
        citations = []
        for c in chunks:
            c_id = c.get("chunk_id", "chunk_unknown")
            citations.append(c_id)
            extracted = AgentTools.extract_numbers_and_percentages(c.get("content", ""))
            for item in extracted:
                all_metrics.append(MetricFinding(
                    metric_name=item["context"],
                    value=item["value"],
                    source_chunk_id=c_id,
                    confidence=0.92
                ))

        # 2. Build synthesis summary
        combined_text = " ".join([c.get("content", "") for c in chunks])
        first_sentence = combined_text.split(".")[0].strip() if "." in combined_text else combined_text[:150].strip()

        # Extract concrete claim sentences from retrieved chunks
        extracted_claims = []
        for c in chunks:
            content = c.get("content", "")
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', content) if len(s.strip()) > 15]
            for s in sentences:
                if s not in extracted_claims:
                    extracted_claims.append(s)
                if len(extracted_claims) >= 3:
                    break
            if len(extracted_claims) >= 3:
                break

        summary = AnalyticalSummary(
            query=query,
            executive_summary=f"Analysis based on {len(chunks)} verified document chunks: {first_sentence}.",
            key_metrics=all_metrics[:5],
            verifiable_claims=extracted_claims if extracted_claims else ([first_sentence] if first_sentence else []),
            confidence_score=0.88,
            source_citations=citations[:5]
        )

        state.draft_summary = summary.model_dump()
        state.thought_history.append(AgentThoughtStep(
            agent_name="ResearchAgent",
            thought="Analyzed chunks, applied regex metric extraction tool, and assembled Pydantic schema.",
            action="deterministic_synthesis",
            observation=f"Extracted {len(all_metrics)} metrics across {len(chunks)} chunks."
        ))
        return state

research_agent = ResearchAgent()
