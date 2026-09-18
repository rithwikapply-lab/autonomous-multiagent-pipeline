import json
import re
from typing import Dict, Any, List
import httpx
from app.config import settings
from app.models.schemas import AnalyticalSummary, MetricFinding
from app.models.state import AgentState, AgentThoughtStep
from app.agents.tools import AgentTools
from app.search.reranker import (
    STOP_WORDS, _stem, extract_discriminative_keywords,
    extract_query_named_entities, cross_encoder_reranker
)
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
3. Do NOT hallucinate. If the retrieved context does not answer the question or contains no relevant information, you MUST set "executive_summary": "I don't have information about this in the provided documents.", "key_metrics": [], "verifiable_claims": [], and "confidence_score": 0.0.
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

        # If no chunks provided or retrieval yielded no relevant context
        if not chunks:
            summary = AnalyticalSummary(
                query=query,
                executive_summary="I don't have information about this in the provided documents.",
                key_metrics=[],
                verifiable_claims=[],
                confidence_score=0.0,
                source_citations=[]
            )
            state.draft_summary = summary.model_dump()
            state.thought_history.append(AgentThoughtStep(
                agent_name="ResearchAgent",
                thought="No relevant document chunks found in knowledge base for query.",
                action="conclude_no_context",
                observation="Returned standard no-information response."
            ))
            return state

        # Check if chunks contain substantive discriminative query keywords and required entities
        disc_keywords = extract_discriminative_keywords(query)
        query_entities = extract_query_named_entities(query)
        context_text = " ".join([(c.get("content", "") + " " + c.get("title", "")).lower() for c in chunks])
        c_tokens = set([_stem(w) for w in re.findall(r'\b[a-zA-Z0-9_]+\b', context_text)])

        top_rerank_score = max([c.get("rerank_score", -999.0) for c in chunks], default=-999.0)

        # Named entity grounding check: if query names a specific proper noun, candidate chunks must mention it
        if query_entities and not any(ent in c_tokens for ent in query_entities):
            has_topical_match = False
        elif disc_keywords:
            matched_disc = [dk for dk in disc_keywords if dk in c_tokens]
            coverage = len(matched_disc) / len(disc_keywords)
            # High neural cross-encoder confidence (rerank_score >= 0.0) indicates strong semantic relevance,
            # allowing topical match when paraphrase/synonym coverage is partial (e.g. laptop ~ equipment).
            if top_rerank_score >= 0.0 and len(matched_disc) >= 1:
                has_topical_match = True
            else:
                has_topical_match = coverage > 0.50
        else:
            q_tokens = [
                _stem(w) for w in re.findall(r'\b[a-zA-Z0-9_]+\b', query.lower())
                if w not in STOP_WORDS and len(w) > 2
            ]
            has_topical_match = any(qt in c_tokens for qt in q_tokens) if q_tokens else True
        if not has_topical_match:
            summary = AnalyticalSummary(
                query=query,
                executive_summary="I don't have information about this in the provided documents.",
                key_metrics=[],
                verifiable_claims=[],
                confidence_score=0.0,
                source_citations=[]
            )
            state.draft_summary = summary.model_dump()
            state.thought_history.append(AgentThoughtStep(
                agent_name="ResearchAgent",
                thought="Provided context chunks do not address the query topic.",
                action="conclude_no_information",
                observation="Returned standard no-information response."
            ))
            return state

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
        # 1. Tool execution: Extract numerical metrics scoped to topical sentences
        combined_text = " ".join([c.get("content", "") for c in chunks])
        non_entity_kws = [k for k in disc_keywords if k not in query_entities] if disc_keywords else []
        target_tokens = non_entity_kws if non_entity_kws else (disc_keywords if disc_keywords else q_tokens)

        all_metrics: List[MetricFinding] = []
        citations = []
        for c in chunks:
            c_id = c.get("chunk_id", "chunk_unknown")
            citations.append(c_id)
            c_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', c.get("content", "")) if len(s.strip()) > 10]
            for s in c_sentences:
                s_tokens = set([_stem(w) for w in re.findall(r'\b[a-zA-Z0-9_]+\b', s.lower())])
                is_topical_s = any(t in s_tokens for t in target_tokens) if target_tokens else True
                if not is_topical_s:
                    continue
                extracted = AgentTools.extract_numbers_and_percentages(s)
                for item in extracted:
                    all_metrics.append(MetricFinding(
                        metric_name=item["context"],
                        value=item["value"],
                        source_chunk_id=c_id,
                        confidence=0.92
                    ))

        # Fallback if no topical metrics found but candidate sentences exist
        if not all_metrics:
            for c in chunks:
                c_id = c.get("chunk_id", "chunk_unknown")
                extracted = AgentTools.extract_numbers_and_percentages(c.get("content", ""))
                for item in extracted:
                    all_metrics.append(MetricFinding(
                        metric_name=item["context"],
                        value=item["value"],
                        source_chunk_id=c_id,
                        confidence=0.92
                    ))

        # 2. Build synthesis summary
        # Select candidate sentences scored by keyword overlap and metric relevance
        candidate_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', combined_text) if len(s.strip()) > 15]
        topical_sentences = []
        scored_candidates = []
        if candidate_sentences:
            from app.search.reranker import IRREGULAR_STEMS
            action_synonym_stems = set(IRREGULAR_STEMS.values())
            for s in candidate_sentences:
                s_tokens = set(_stem(w) for w in re.findall(r'\b[a-zA-Z0-9_]+\b', s.lower()))
                matches = [t for t in target_tokens if t in s_tokens] if target_tokens else []
                if matches:
                    has_metric = any(str(m.value) in s for m in all_metrics)
                    # Weight action verbs / normalized synonyms (e.g. export, los) with extra priority
                    action_weight = sum(2.0 for t in matches if t in action_synonym_stems)
                    score = len(matches) * 2.0 + action_weight + (2.0 if has_metric else 0.0)
                    scored_candidates.append((score, s))

            scored_candidates.sort(key=lambda x: x[0], reverse=True)
            topical_sentences = [s for _, s in scored_candidates]
        best_sentence = topical_sentences[0] if topical_sentences else (candidate_sentences[0] if candidate_sentences else combined_text[:150].strip())

        # Extract concrete claim sentences from retrieved chunks addressing query topic
        extracted_claims = []
        for _, s in scored_candidates:
            if s not in extracted_claims:
                extracted_claims.append(s)
            if len(extracted_claims) >= 3:
                break

        summary = AnalyticalSummary(
            query=query,
            executive_summary=f"Analysis based on {len(chunks)} verified document chunks: {best_sentence}.",
            key_metrics=all_metrics[:5],
            verifiable_claims=extracted_claims if extracted_claims else ([best_sentence] if best_sentence else []),
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
