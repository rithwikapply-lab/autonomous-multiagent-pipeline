from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

class DocumentChunk(BaseModel):
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    doc_id: str
    content: str
    chunk_index: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
    score: Optional[float] = None

class DocumentIngestRequest(BaseModel):
    doc_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    text_content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    chunk_size: int = 500
    chunk_overlap: int = 50

class DocumentIngestResponse(BaseModel):
    doc_id: str
    chunks_created: int
    status: str
    indexed_at: datetime = Field(default_factory=datetime.utcnow)

class QueryRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, description="Number of document chunks to retrieve, minimum 1")
    enable_reranking: bool = True
    enable_verification: bool = True
    metadata_filter: Optional[Dict[str, Any]] = None

class MetricFinding(BaseModel):
    metric_name: str = Field(description="Name of the measured or identified metric")
    value: str = Field(description="Quantitative or qualitative value")
    source_chunk_id: Optional[str] = Field(description="Chunk ID or citation supporting this value")
    confidence: float = Field(description="Confidence between 0.0 and 1.0")

class VerificationReport(BaseModel):
    is_faithful: bool = Field(description="Whether all assertions are backed by retrieved context")
    hallucination_score: float = Field(description="Estimated hallucination probability (0.0 to 1.0)")
    verified_claims: List[str] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)
    suggested_corrections: Optional[str] = None

class AnalyticalSummary(BaseModel):
    query: str
    executive_summary: str = Field(description="Concise high-level synthesis of findings")
    key_metrics: List[MetricFinding] = Field(default_factory=list, description="Extracted quantitative metrics")
    verifiable_claims: List[str] = Field(default_factory=list, description="Ground truth assertions backed by evidence")
    confidence_score: float = Field(description="Overall confidence in the synthesis")
    source_citations: List[str] = Field(default_factory=list, description="IDs of cited document chunks")

class QueryResponse(BaseModel):
    query: str
    analysis: AnalyticalSummary
    retrieved_chunks: List[DocumentChunk]
    verification: Optional[VerificationReport] = None
    execution_time_ms: float
    cached: bool = False
